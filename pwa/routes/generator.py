"""Blueprint générateur de programme IA — feature VIP.

Flow :
  GET  /generator           : formulaire (objectif, niveau, fréquence, matériel,
                              contraintes, durée). VIP only (paywall sinon).
  POST /generator/generate  : construit un prompt structuré, appelle Claude, lui
                              demande un JSON STRICT de programme, le parse et le
                              valide, puis le renvoie pour prévisualisation.
  POST /generator/apply     : re-valide le programme reçu et l'enregistre via
                              save_prog (même chemin sûr que l'import).

Anti-coût : quota quotidien (events `program_generated`) + backstop Flask-Limiter.
Le parseur `parse_and_validate` est une fonction PURE (sans I/O) → testable.
"""
import json
import logging

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, g

from core.data import get_prog, save_prog
from core.dates import DAYS_FR, today_paris_str
from core.db import _env
from core import db as core_db
from core.limiter import limiter
from core.analytics import track, paywall
from core.exercises_data import EXERCISES_INFO

logger = logging.getLogger(__name__)

bp = Blueprint("generator", __name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 2600
WEEKLY_GEN_QUOTA = 3  # générations / semaine glissante (7 j) / VIP — protège le coût API

# Muscles canoniques (alignés sur seance.MUSCLE_LIST / body map).
MUSCLES = [
    "Pecs", "Dos", "Trapèzes", "Épaules", "Biceps", "Triceps", "Avant-bras",
    "Abdos", "Quadriceps", "Ischio-jambiers", "Fessiers", "Adducteurs",
    "Abducteurs", "Mollets", "Autre",
]
_MUSCLES_SET = {m.lower() for m in MUSCLES}

OBJECTIFS = ["Prise de masse", "Force", "Sèche / perte de gras", "Endurance", "Remise en forme"]
NIVEAUX = ["Débutant", "Intermédiaire", "Avancé"]
LIEUX = ["Salle de sport", "Maison (haltères)", "Maison (poids du corps)"]


# ────────────────────────────────────────────────────────────────
# Validation (fonction pure — testée)
# ────────────────────────────────────────────────────────────────
def _clean_muscle(raw: str) -> str:
    """Normalise un libellé muscle (éventuellement composé « Pecs,Triceps »).
    Garde les tokens reconnus ; si aucun, renvoie « Autre »."""
    parts = [p.strip() for p in str(raw or "").replace("/", ",").split(",") if p.strip()]
    kept = []
    for p in parts:
        match = next((m for m in MUSCLES if m.lower() == p.lower()), None)
        if match and match not in kept:
            kept.append(match)
    return ",".join(kept) if kept else "Autre"


def parse_and_validate(raw) -> dict:
    """Parse + valide un programme généré (texte JSON ou dict déjà parsé).

    Retourne un dict normalisé :
        {"name": str, "notes": str,
         "seances": {nom: [{"name","sets","muscle","reps"}]},
         "planning": {jour_fr: nom_seance}}

    Lève ValueError si la structure est inexploitable. Tolérant aux blocs de
    code Markdown (```json … ```) qu'un LLM ajoute parfois.
    """
    if isinstance(raw, (dict, list)):
        data = raw
    else:
        text = str(raw or "").strip()
        if text.startswith("```"):
            # Retire la 1ère ligne (```json) et la dernière (```).
            lines = text.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        if not text:
            raise ValueError("réponse vide")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON invalide : {e}")

    if not isinstance(data, dict):
        raise ValueError("le programme doit être un objet JSON")

    raw_seances = data.get("seances")
    if not isinstance(raw_seances, dict) or not raw_seances:
        raise ValueError("aucune séance dans le programme")

    seances: dict = {}
    for sname, exos in raw_seances.items():
        name = str(sname or "").strip()[:60]
        if not name or name.startswith("_") or not isinstance(exos, list):
            continue
        cleaned = []
        for e in exos:
            if not isinstance(e, dict):
                continue
            ex_name = str(e.get("name") or "").strip()[:80]
            if not ex_name:
                continue
            try:
                sets = int(e.get("sets") or 3)
            except (TypeError, ValueError):
                sets = 3
            sets = max(1, min(8, sets))
            reps = str(e.get("reps") or "").strip()[:20]
            cleaned.append({
                "name": ex_name,
                "sets": sets,
                "muscle": _clean_muscle(e.get("muscle")),
                "reps": reps,
            })
        if cleaned:
            seances[name] = cleaned[:12]
        if len(seances) >= 6:
            break

    if not seances:
        raise ValueError("aucune séance valide après nettoyage")

    # Planning : ne garde que les jours FR connus pointant vers une séance réelle.
    raw_planning = data.get("planning") if isinstance(data.get("planning"), dict) else {}
    planning = {d: "" for d in DAYS_FR}
    for d in DAYS_FR:
        val = str(raw_planning.get(d, "") or "").strip()
        if val in seances:
            planning[d] = val
    # Filet : si le LLM n'a fourni aucun planning exploitable, répartit en cyclique.
    if not any(planning.values()):
        from core.catalog import planning_for
        planning = planning_for(len(seances), list(seances.keys()))

    name = str(data.get("name") or "Programme IA").strip()[:80] or "Programme IA"
    notes = str(data.get("notes") or "").strip()[:600]
    return {"name": name, "notes": notes, "seances": seances, "planning": planning}


# ────────────────────────────────────────────────────────────────
# Prompt
# ────────────────────────────────────────────────────────────────
def _known_exercises() -> str:
    """Liste des exercices reconnus par l'app (illustrations + substitutions)."""
    return ", ".join(sorted(EXERCISES_INFO.keys()))


def _build_prompt(params: dict) -> str:
    return (
        "Tu es un coach de musculation expert. Génère un programme d'entraînement "
        "personnalisé et COHÉRENT à partir des informations ci-dessous.\n\n"
        f"- Objectif : {params['objectif']}\n"
        f"- Niveau : {params['niveau']}\n"
        f"- Fréquence : {params['frequence']} séances par semaine\n"
        f"- Lieu / matériel : {params['lieu']}\n"
        f"- Durée souhaitée par séance : {params['duree']} min\n"
        f"- Contraintes / blessures / préférences : {params['contraintes'] or 'aucune'}\n\n"
        "RÈGLES STRICTES :\n"
        f"- Produis EXACTEMENT {params['frequence']} séance(s) distincte(s) "
        "(ou un split cyclé cohérent réparti sur ces jours).\n"
        "- Pour chaque exercice : un nombre de séries réaliste (3 à 5) et une "
        "fourchette de répétitions adaptée à l'objectif.\n"
        "- Le champ \"muscle\" DOIT être l'un de ces libellés (ou une combinaison "
        "séparée par des virgules) : " + ", ".join(MUSCLES) + ".\n"
        "- Privilégie autant que possible des exercices de cette liste connue (pour "
        "les illustrations) : " + _known_exercises() + ".\n"
        "- Adapte le matériel au lieu indiqué (pas de machine de salle si « maison »).\n\n"
        "RÉPONDS UNIQUEMENT avec un objet JSON valide, sans texte avant ni après, "
        "au format EXACT suivant :\n"
        "{\n"
        '  "name": "Nom court du programme",\n'
        '  "notes": "2-3 phrases : logique du programme et conseil de progression",\n'
        '  "seances": {\n'
        '    "Nom de séance": [\n'
        '      {"name": "Nom exercice", "sets": 4, "reps": "8-12", "muscle": "Pecs,Triceps"}\n'
        "    ]\n"
        "  },\n"
        '  "planning": {"Lundi": "Nom de séance", "Mardi": "", ...}\n'
        "}\n"
        "Les jours du planning doivent être en français (Lundi…Dimanche), valeur "
        "vide pour un jour de repos."
    )


# ────────────────────────────────────────────────────────────────
# Quota
# ────────────────────────────────────────────────────────────────
def _gen_used_week(user_id: str) -> int:
    """Nb de générations réussies sur les 7 derniers jours (via la table events).
    Best-effort : si la table n'existe pas encore (migration v28 non appliquée),
    renvoie 0 — le backstop Flask-Limiter protège alors seul contre l'abus."""
    import datetime as _dt
    since = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=7)).isoformat()
    try:
        client = core_db.get_client()
        resp = (
            client.table("events").select("id", count="exact")
            .eq("user_id", user_id).eq("event", "program_generated")
            .gte("created_at", since).execute()
        )
        return int(getattr(resp, "count", None) or 0)
    except Exception as e:
        logger.warning("generator quota lookup failed: %s", e)
        return 0


# ────────────────────────────────────────────────────────────────
# Routes
# ────────────────────────────────────────────────────────────────
@bp.route("/generator")
def index():
    if not getattr(g, "is_vip_full", False):
        return paywall("Générateur de programme IA")
    track("program_generator_viewed")
    return render_template(
        "generator.html", active="plus",
        objectifs=OBJECTIFS, niveaux=NIVEAUX, lieux=LIEUX,
        quota_remaining=max(0, WEEKLY_GEN_QUOTA - _gen_used_week(g.user_id)),
        quota_limit=WEEKLY_GEN_QUOTA,
    )


@bp.route("/generator/generate", methods=["POST"])
@limiter.limit("10 per hour")
def generate():
    if not getattr(g, "is_vip_full", False):
        return jsonify({"error": "Réservé aux membres PRO."}), 403

    used = _gen_used_week(g.user_id)
    if used >= WEEKLY_GEN_QUOTA:
        return jsonify({
            "error": f"Limite hebdomadaire atteinte ({WEEKLY_GEN_QUOTA}/semaine). Reviens dans quelques jours.",
        }), 429

    f = request.get_json(silent=True) or {}
    params = {
        "objectif": str(f.get("objectif") or "").strip()[:40] or "Prise de masse",
        "niveau": str(f.get("niveau") or "").strip()[:30] or "Intermédiaire",
        "frequence": max(2, min(6, int(f.get("frequence") or 3) if str(f.get("frequence") or "").isdigit() else 3)),
        "lieu": str(f.get("lieu") or "").strip()[:40] or "Salle de sport",
        "duree": max(20, min(120, int(f.get("duree") or 60) if str(f.get("duree") or "").isdigit() else 60)),
        "contraintes": str(f.get("contraintes") or "").strip()[:400],
    }

    api_key = _env("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "Générateur non configuré (ANTHROPIC_API_KEY manquante)."}), 503
    try:
        import anthropic  # type: ignore
    except ImportError:
        return jsonify({"error": "Bibliothèque anthropic absente."}), 503

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": _build_prompt(params)}],
        )
        parts = [getattr(b, "text", "") for b in (response.content or []) if getattr(b, "text", "")]
        raw = "\n".join(parts).strip()
    except Exception as e:
        err_type = type(e).__name__
        err_msg = str(e)[:300]
        logger.error("/generator anthropic FAILED (%s): %s", err_type, err_msg)
        lower = err_msg.lower()
        if "authentication" in lower or ("invalid" in lower and "api" in lower):
            msg = "Clé API Anthropic invalide."
        elif "credit" in lower or "billing" in lower or "quota" in lower:
            msg = "Crédit Anthropic épuisé."
        else:
            msg = f"Erreur Anthropic ({err_type})."
        return jsonify({"error": msg}), 502

    try:
        program = parse_and_validate(raw)
    except ValueError as e:
        logger.error("/generator parse FAILED: %s | raw=%s", e, raw[:200])
        return jsonify({"error": "L'IA a renvoyé un programme illisible. Réessaie."}), 502

    track("program_generated", {
        "objectif": params["objectif"], "niveau": params["niveau"],
        "frequence": params["frequence"], "seances": len(program["seances"]),
    })
    return jsonify({
        "ok": True,
        "program": program,
        "quota_remaining": max(0, WEEKLY_GEN_QUOTA - (used + 1)),
    })


@bp.route("/generator/apply", methods=["POST"])
@limiter.limit("20 per hour")
def apply():
    if not getattr(g, "is_vip_full", False):
        return paywall("Générateur de programme IA", 403)
    raw = request.form.get("program") or ""
    try:
        program = parse_and_validate(raw)
    except ValueError:
        return redirect(url_for("generator.index") + "?err=apply")

    old = get_prog() or {}
    new_prog: dict = {}
    for sname, exos in program["seances"].items():
        # On NE stocke pas les reps (cf. CONTEXT : reps non persistées) — elles
        # ne servent qu'à l'affichage de la preview.
        new_prog[sname] = [{"name": e["name"], "sets": e["sets"], "muscle": e["muscle"]} for e in exos]
    new_prog["_planning"] = dict(program["planning"])
    new_prog["_name"] = program["name"]
    new_prog.pop("_origin", None)
    # Préserve les données utilisateur indépendantes du programme.
    for key in ("_settings", "_archive", "_legacy_volume", "_extras"):
        if key in old:
            new_prog[key] = old[key]
    new_prog["_started_at"] = today_paris_str()
    save_prog(new_prog)

    track("program_adopted", {"name": program["name"], "seances": len(program["seances"])})
    return redirect(url_for("programme.programme") + "?program_changed=1")
