"""Cardio ajouté à une séance de musculation (échauffement, finisher).

Sorti de routes/seance.py (audit du 30/09, M11)."""
import logging

from flask import Blueprint, render_template, request

from core.data import (
    clear_user_cache, append_exo_rows,
)
from core.dates import today_paris
from core.limiter import limiter
from core.navigation_seance import _back_to_editor
from core.seance_semaine import _iso_week, _parse_date
from core.seance_saisie import _form_date
from core.seance_cardio import completer_mesures

logger = logging.getLogger(__name__)

bp = Blueprint("seance_cardio", __name__)


@bp.route("/seance/add-cardio", methods=["POST"])
@limiter.limit("20 per minute")
def add_cardio():
    """Ajoute un bloc cardio à la séance muscu en cours (même Séance + Date)."""
    from core.cardio_activites import ACTIVITES_MAP, RPE_LABELS, _estimate_calories, _adjust_met_for_incline
    from core.data import get_profile
    f = request.form
    target = _parse_date(f.get("date")) or today_paris()
    date_str = target.strftime("%Y-%m-%d")
    semaine = _iso_week(target)
    seance_name = f["seance_name"]

    activite = (f.get("activite") or "Autre").strip()
    if activite not in ACTIVITES_MAP:
        activite = "Autre"
    _icon, met = ACTIVITES_MAP[activite]

    try:
        duree_min = max(0, int(float(f.get("duree_min") or 0)))
    except ValueError:
        duree_min = 0
    try:
        distance_val = max(0.0, float((f.get("distance_km") or "0").replace(",", ".")))
    except ValueError:
        distance_val = 0.0
    try:
        vitesse = max(0.0, float((f.get("vitesse") or "0").replace(",", ".")))
    except ValueError:
        vitesse = 0.0
    # Deux valeurs sur trois suffisent. La vitesse était calculée dans le
    # formulaire mais seulement AFFICHÉE en suggestion : elle n'arrivait
    # jamais jusqu'ici. Et le sens inverse manquait — le tapis affiche
    # 10 km/h pendant 30 min, c'est la distance qu'on ignore.
    distance_val, vitesse = completer_mesures(activite, duree_min, distance_val, vitesse)
    try:
        cal_saisie = int(float(f.get("calories") or 0))
    except ValueError:
        cal_saisie = 0
    rpe = (f.get("rpe") or "").strip()
    if rpe not in RPE_LABELS:
        rpe = ""
    note = (f.get("note") or "").strip()[:80]

    try:
        incline_pct = max(0, min(30, float(f.get("incline") or 0)))
    except (ValueError, TypeError):
        incline_pct = 0
    met = _adjust_met_for_incline(met, activite, incline_pct)

    if cal_saisie > 0:
        calories = cal_saisie
    else:
        profile = get_profile() or {}
        poids_kg = float(profile.get("poids_kg") or 0)
        calories = _estimate_calories(met, duree_min, poids_kg) if duree_min > 0 else 0

    parts = []
    if calories > 0: parts.append(f"Cal:{calories}")
    if incline_pct > 0: parts.append(f"Incl:{incline_pct:g}%")
    if vitesse > 0: parts.append(f"Vit:{vitesse:g}")
    if rpe: parts.append(f"RPE:{rpe}")
    if note: parts.append(note)
    remarque = " | ".join(parts)

    exo_final = f"CARDIO:{activite}"
    rows = [{
        "Semaine": semaine,
        "Séance": seance_name,
        "Exercice": exo_final,
        "Série": 1,
        "Reps": duree_min,
        "Poids": distance_val,
        "Remarque": remarque,
        "Muscle": "Cardio",
        "Date": date_str,
    }]
    # AJOUTER, pas remplacer : 10 min de rameur en échauffement puis 8 min en
    # finisher sont deux blocs. `replace_exo_rows` ne gardait que le second.
    try:
        append_exo_rows(date_str, seance_name, exo_final, rows)
        clear_user_cache()
    except Exception as e:
        logger.error("add-cardio FAILED: %s", e)
        # L'échec était avalé puis la page revenait comme si de rien n'était.
        return render_template(
            "error.html", code=503,
            message="Le cardio n'a pas pu être enregistré. Réessaie dans un instant.",
        ), 503
    return _back_to_editor(f)


@bp.route("/seance/delete-cardio", methods=["POST"])
@limiter.limit("20 per minute")
def delete_cardio():
    from core.data import delete_exo_rows
    f = request.form
    seance_name = f["seance_name"]
    activite = (f.get("activite") or "").strip()
    if not activite:
        return _back_to_editor(f)
    try:
        serie = int(f["serie"]) if (f.get("serie") or "").isdigit() else None
    except ValueError:
        serie = None
    try:
        delete_exo_rows(_form_date(f), seance_name, f"CARDIO:{activite}", serie)
        clear_user_cache()
    except Exception as e:
        logger.error("delete-cardio FAILED: %s", e)
        return render_template(
            "error.html", code=503,
            message="Le cardio n'a pas pu être retiré. Réessaie dans un instant.",
        ), 503
    return _back_to_editor(f)
