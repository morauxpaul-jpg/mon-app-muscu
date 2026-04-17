"""Blueprint coach — assistant IA musculation via Claude Haiku.

- /coach     : page chat (GET)
- /coach/ask : endpoint JSON (POST) → appelle l'API Anthropic

Rate limit : 20 messages/jour/user via profiles.coach_quota_date +
profiles.coach_quota_count (reset automatique à chaque nouveau jour).
"""
import logging
import os

from flask import Blueprint, render_template, request, jsonify, redirect, url_for

from core.data import (
    get_prog, get_hist, get_profile, save_profile, get_onboarding,
    list_coach_messages, insert_coach_message, clear_coach_messages,
)
from core.dates import today_paris_str
from core.limiter import limiter
from core import catalog

logger = logging.getLogger(__name__)

bp = Blueprint("coach", __name__)

DAILY_QUOTA = 10
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 500

SYSTEM_PROMPT_TMPL = (
    "Tu es le coach IA intégré à l'application Muscu Tracker PRO (PWA Flask). "
    "Tu réponds en français, concis et pratique. Tu connais le programme, "
    "l'historique et l'app elle-même — profite de cette double connaissance.\n"
    "Tu ne donnes JAMAIS de conseils médicaux — renvoie vers un "
    "professionnel de santé si besoin. Tu es encourageant mais honnête.\n\n"
    "## ONGLETS DE L'APP (tu peux rediriger l'utilisateur avec des liens)\n"
    "- [Accueil](/accueil) : dashboard, planning de la semaine, streak, stats\n"
    "- [Séance](/seance) : reprendre la séance du jour\n"
    "- [Progrès](/progres) : calendrier mensuel, volume hebdo, body map, hall of fame, zoom par exercice\n"
    "- [Programme](/programme) : gérer ses séances, planning hebdo, profils d'entraînement\n"
    "- [Plus](/plus) : hub → Programme, Arcade, Gestion, Tutoriel\n"
    "- [Gestion](/gestion) : paramètres, export/import, notifications, reset\n\n"
    "## LIENS SPÉCIAUX (utilise-les quand pertinent)\n"
    "- Pour proposer un programme du catalogue → lien [nom](/programme?apply=ID) "
    "où ID est l'identifiant du programme. Cela ouvre l'onglet Programme sur la section "
    "'Changer de programme' avec le bon programme pré-sélectionné et surligné.\n"
    "- Pour aider à ajouter une séance précise → lien [nom](/programme#planning) vers le planning.\n\n"
    "## CATALOGUE DES PROGRAMMES DISPONIBLES\n"
    "{catalog_list}\n\n"
    "## CONTEXTE UTILISATEUR\n"
    "- Prénom : {prenom}\n"
    "- Niveau : {niveau}\n"
    "- Objectif : {objectif}\n"
    "- Équipement : {equipement}\n"
    "- Programme actuel : {programme_resume}\n"
    "- 5 dernières séances : {dernieres_seances}\n\n"
    "## RÈGLES DE FORMULATION\n"
    "- Utilise du markdown : **gras**, listes à puce, titres avec ##.\n"
    "- Quand tu mentionnes un programme du catalogue, fais-en un lien cliquable "
    "[Titre du programme](/programme?apply=ID) pour que l'utilisateur puisse y aller en un clic.\n"
    "- Quand tu suggères de consulter une section de l'app, mets un lien [nom onglet](/chemin).\n"
    "- Reste bref : 3-6 phrases max par réponse, sauf si l'utilisateur demande un plan détaillé."
)

SUGGESTIONS = [
    "Comment progresser au développé couché ?",
    "Mon programme est-il adapté ?",
    "J'ai mal à l'épaule, que faire ?",
    "Combien de protéines par jour ?",
]


def _catalog_list_for_prompt():
    """Liste compacte des programmes du catalogue pour le system prompt.

    Format : `- ID : Titre — sous-titre (niveau, X séances)`
    """
    try:
        items = catalog.list_programs() or []
    except Exception as e:
        logger.error("coach catalog list FAILED: %s", e)
        return "(catalogue indisponible)"
    lines = []
    for p in items:
        lines.append(
            f"- `{p['id']}` : {p['title']} — {p['subtitle']} "
            f"({p['nb_seances']} séances, {p['duration']})"
        )
    return "\n".join(lines) or "(vide)"


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
    try:
        messages = list_coach_messages(50) or []
    except Exception as e:
        logger.error("/coach load history FAILED: %s", e)
        messages = []
    prenom = (onboarding.get("prenom") or profile.get("prenom") or "").strip()
    remaining = _quota_remaining(profile)
    prefill = (request.args.get("q") or "").strip()[:500]
    return render_template(
        "coach.html",
        active="plus",
        prenom=prenom or "l'athlète",
        suggestions=SUGGESTIONS,
        quota_remaining=remaining,
        quota_limit=DAILY_QUOTA,
        messages=messages,
        prefill=prefill,
    )


@bp.route("/coach/clear", methods=["POST"])
@limiter.limit("10 per minute")
def clear():
    try:
        clear_coach_messages()
    except Exception as e:
        logger.error("/coach/clear FAILED: %s", e)
    return redirect(url_for("coach.index"))


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
        catalog_list=_catalog_list_for_prompt(),
    )

    # Historique (10 derniers) envoyé comme contexte conversationnel
    try:
        history = list_coach_messages(10) or []
    except Exception as e:
        logger.error("/coach/ask history load FAILED: %s", e)
        history = []
    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    api_messages.append({"role": "user", "content": message})

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=api_messages,
        )
        # Concatène les blocs text (Anthropic renvoie une liste de content blocks)
        reply_parts = []
        for block in response.content or []:
            text = getattr(block, "text", None)
            if text:
                reply_parts.append(text)
        reply = "\n".join(reply_parts).strip() or "Désolé, je n'ai pas pu répondre."
    except Exception as e:
        # On log le détail côté serveur et on renvoie un message parlant au
        # client pour faciliter le debug (sans fuiter la clé API).
        err_type = type(e).__name__
        err_msg = str(e)[:300]
        logger.error("/coach/ask anthropic FAILED (%s): %s", err_type, err_msg)
        # Messages spécifiques pour les erreurs les plus fréquentes
        lower = err_msg.lower()
        if "authentication" in lower or "invalid" in lower and "api" in lower:
            user_msg = "Clé API Anthropic invalide. Vérifie ANTHROPIC_API_KEY dans Railway."
        elif "credit" in lower or "billing" in lower or "quota" in lower:
            user_msg = "Crédit Anthropic épuisé. Ajoute du crédit sur console.anthropic.com."
        elif "not_found" in lower or "model" in lower and "not" in lower:
            user_msg = f"Modèle introuvable côté API. Détail : {err_msg}"
        else:
            user_msg = f"Erreur Anthropic ({err_type}) : {err_msg}"
        return jsonify({"error": user_msg}), 502

    # Persiste le tour de conversation (user puis assistant) pour que
    # l'historique survive aux rechargements et aux autres sessions.
    try:
        insert_coach_message("user", message)
        insert_coach_message("assistant", reply)
    except Exception as e:
        logger.error("/coach/ask persist FAILED: %s", e)

    return jsonify({
        "reply": reply,
        "quota_remaining": max(0, limit - count_after),
        "quota_limit": limit,
    })
