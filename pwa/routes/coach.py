"""Blueprint coach — assistant IA musculation via Claude Haiku.

- /coach     : page chat (GET)
- /coach/ask : endpoint JSON (POST) → appelle l'API Anthropic

Rate limit : 20 messages/jour/user via profiles.coach_quota_date +
profiles.coach_quota_count (reset automatique à chaque nouveau jour).
"""
import logging
import os

from flask import Blueprint, render_template, request, jsonify

from core.data import get_prog, get_hist, get_profile, save_profile, get_onboarding
from core.dates import today_paris_str
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("coach", __name__)

DAILY_QUOTA = 20
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 500

SYSTEM_PROMPT_TMPL = (
    "Tu es un coach sportif spécialisé en musculation. "
    "Tu réponds en français, de manière concise et pratique. "
    "Tu connais le programme et l'historique de l'utilisateur. "
    "Tu ne donnes JAMAIS de conseils médicaux — tu renvoies vers un "
    "professionnel de santé si nécessaire. "
    "Tu es encourageant mais honnête.\n\n"
    "Contexte utilisateur :\n"
    "- Prénom : {prenom}\n"
    "- Niveau : {niveau}\n"
    "- Objectif : {objectif}\n"
    "- Équipement : {equipement}\n"
    "- Programme : {programme_resume}\n"
    "- 5 dernières séances : {dernieres_seances}"
)

SUGGESTIONS = [
    "Comment progresser au développé couché ?",
    "Mon programme est-il adapté ?",
    "J'ai mal à l'épaule, que faire ?",
    "Combien de protéines par jour ?",
]


def _programme_resume(prog):
    seances = {k: v for k, v in (prog or {}).items() if not k.startswith("_")}
    if not seances:
        return "aucun programme défini"
    parts = []
    for name, exos in seances.items():
        exo_names = [e.get("name") or "" for e in (exos or [])][:6]
        parts.append(f"{name} ({', '.join(exo_names)})")
    return " | ".join(parts)


def _dernieres_seances(hist):
    """5 dernières séances résumées (date, séance, volume)."""
    if not hist:
        return "aucune séance enregistrée"
    by_date_seance = {}
    for r in hist:
        d = r.get("Date") or ""
        s = r.get("Séance") or ""
        if not d or s == "" or r.get("Exercice") == "SESSION":
            continue
        key = (d, s)
        entry = by_date_seance.setdefault(key, {"sets": 0, "vol": 0})
        try:
            reps = int(r.get("Reps") or 0)
            poids = float(r.get("Poids") or 0)
        except (TypeError, ValueError):
            reps, poids = 0, 0
        if reps > 0:
            entry["sets"] += 1
            entry["vol"] += int(reps * poids)
    if not by_date_seance:
        return "aucune séance récente"
    # tri par date desc
    items = sorted(by_date_seance.items(), key=lambda kv: kv[0][0], reverse=True)[:5]
    return " ; ".join(
        f"{d} {s} ({e['sets']} séries, vol {e['vol']}kg)"
        for (d, s), e in items
    )


def _check_and_bump_quota(profile):
    """Retourne (allowed: bool, count_after: int, limit: int).

    Reset automatique à chaque changement de jour. Si allowed, incrémente
    déjà le compteur et le persiste avant l'appel à l'API (pas de double
    décrément à faire ensuite).
    """
    today = today_paris_str()
    q_date = str(profile.get("coach_quota_date") or "")
    q_count = int(profile.get("coach_quota_count") or 0)
    if q_date != today:
        q_count = 0  # nouveau jour → reset
    if q_count >= DAILY_QUOTA:
        return False, q_count, DAILY_QUOTA
    q_count += 1
    try:
        save_profile({"coach_quota_date": today, "coach_quota_count": q_count})
    except Exception as e:
        logger.error("coach save_profile quota FAILED: %s", e)
    return True, q_count, DAILY_QUOTA


def _quota_remaining(profile):
    today = today_paris_str()
    q_date = str(profile.get("coach_quota_date") or "")
    q_count = int(profile.get("coach_quota_count") or 0)
    if q_date != today:
        q_count = 0
    return max(0, DAILY_QUOTA - q_count)


@bp.route("/coach")
def index():
    try:
        profile = get_profile() or {}
        onboarding = get_onboarding() or {}
    except Exception as e:
        logger.error("/coach load profile/onboarding FAILED: %s", e)
        profile, onboarding = {}, {}
    prenom = (onboarding.get("prenom") or profile.get("prenom") or "").strip()
    remaining = _quota_remaining(profile)
    return render_template(
        "coach.html",
        active="plus",
        prenom=prenom or "l'athlète",
        suggestions=SUGGESTIONS,
        quota_remaining=remaining,
        quota_limit=DAILY_QUOTA,
    )


@bp.route("/coach/ask", methods=["POST"])
@limiter.limit("30 per minute")
def ask():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message vide"}), 400
    if len(message) > 1500:
        message = message[:1500]

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return jsonify({"error": "Coach IA non configuré (ANTHROPIC_API_KEY manquante)."}), 503

    try:
        import anthropic  # type: ignore
    except ImportError:
        return jsonify({"error": "Bibliothèque anthropic absente."}), 503

    # Contexte utilisateur
    try:
        profile = get_profile() or {}
        onboarding = get_onboarding() or {}
        prog = get_prog() or {}
        hist = get_hist() or []
    except Exception as e:
        logger.error("/coach/ask context load FAILED: %s", e)
        profile, onboarding, prog, hist = {}, {}, {}, []

    # Quota (persisté)
    allowed, count_after, limit = _check_and_bump_quota(profile)
    if not allowed:
        return jsonify({
            "error": f"Limite quotidienne atteinte ({limit} messages/jour). Reviens demain.",
            "quota_remaining": 0,
            "quota_limit": limit,
        }), 429

    prenom = (onboarding.get("prenom") or "l'athlète").strip() or "l'athlète"
    niveau = onboarding.get("niveau") or "non précisé"
    objectif = onboarding.get("objectif") or "non précisé"
    equipement = onboarding.get("equipement") or "non précisé"
    if isinstance(equipement, list):
        equipement = ", ".join(str(x) for x in equipement) or "non précisé"

    system_prompt = SYSTEM_PROMPT_TMPL.format(
        prenom=prenom,
        niveau=niveau,
        objectif=objectif,
        equipement=equipement,
        programme_resume=_programme_resume(prog),
        dernieres_seances=_dernieres_seances(hist),
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": message}],
        )
        # Concatène les blocs text (Anthropic renvoie une liste de content blocks)
        reply_parts = []
        for block in response.content or []:
            text = getattr(block, "text", None)
            if text:
                reply_parts.append(text)
        reply = "\n".join(reply_parts).strip() or "Désolé, je n'ai pas pu répondre."
    except Exception as e:
        logger.error("/coach/ask anthropic FAILED: %s", e)
        return jsonify({"error": "L'assistant est indisponible. Réessaie dans un instant."}), 502

    return jsonify({
        "reply": reply,
        "quota_remaining": max(0, limit - count_after),
        "quota_limit": limit,
    })
