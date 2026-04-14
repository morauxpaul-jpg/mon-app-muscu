"""Blueprint cardio — saisie d'une séance cardio (chrono + distance + calories + RPE).

Stockage dans la même table `history` que la muscu, avec convention :
  Exercice = "CARDIO:Type"  (ex. "CARDIO:Course")
  Reps     = durée en minutes (int)
  Poids    = distance en km (float, 0 si non applicable)
  Remarque = "FC:145 | Cal:350 | RPE:Modéré"
  Muscle   = "Cardio"
  Série    = 1
"""
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for

from core.data import replace_exo_rows, get_profile
from core.dates import today_paris, today_paris_str, DAYS_FR, MONTHS_FR
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("cardio", __name__)

ACTIVITES = [
    ("Course", "footprints", 10.0),      # MET ≈ 10 (course 10 km/h)
    ("Vélo", "activity", 7.5),
    ("Rameur", "activity", 7.0),
    ("Natation", "activity", 8.0),
    ("Corde", "activity", 11.0),
    ("HIIT", "flame", 9.0),
    ("Marche", "footprints", 3.5),
    ("Elliptique", "activity", 6.5),
    ("Autre", "heart", 6.0),
]
ACTIVITES_MAP = {name: (icon, met) for name, icon, met in ACTIVITES}

RPE_LABELS = ["Facile", "Modéré", "Intense"]


def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _iso_week(d):
    return d.isocalendar().week


def _estimate_calories(met, minutes, poids_kg):
    """Formule standard : kcal = MET × poids(kg) × temps(h)."""
    if not poids_kg or poids_kg <= 0:
        poids_kg = 70.0
    return int(round(met * poids_kg * (minutes / 60.0)))


@bp.route("/cardio")
def new():
    date_iso = request.args.get("date") or today_paris_str()
    target = _parse_date(date_iso) or today_paris()
    date_iso = target.strftime("%Y-%m-%d")
    date_label = f"{DAYS_FR[target.weekday()]} {target.day} {MONTHS_FR[target.month-1]}"

    profile = get_profile() or {}
    poids_kg = float(profile.get("poids_kg") or 0)

    return render_template(
        "cardio.html",
        active="seance",
        date_iso=date_iso,
        date_label=date_label,
        activites=ACTIVITES,
        rpe_labels=RPE_LABELS,
        poids_kg=poids_kg,
    )


@bp.route("/cardio/save", methods=["POST"])
@limiter.limit("20 per minute")
def save():
    f = request.form
    date_str = f.get("date") or today_paris_str()
    target = _parse_date(date_str) or today_paris()
    semaine = _iso_week(target)

    activite = (f.get("activite") or "Autre").strip()
    if activite not in ACTIVITES_MAP:
        activite = "Autre"
    _icon, met = ACTIVITES_MAP[activite]

    try:
        duree_min = max(0, int(float(f.get("duree_min") or 0)))
    except ValueError:
        duree_min = 0
    try:
        distance_km = max(0.0, float((f.get("distance_km") or "0").replace(",", ".")))
    except ValueError:
        distance_km = 0.0
    try:
        fc_moy = int(float(f.get("fc_moy") or 0))
    except ValueError:
        fc_moy = 0

    rpe = (f.get("rpe") or "").strip()
    if rpe not in RPE_LABELS:
        rpe = ""

    # Calories : soit saisies, soit estimées
    try:
        cal_saisie = int(float(f.get("calories") or 0))
    except ValueError:
        cal_saisie = 0
    if cal_saisie > 0:
        calories = cal_saisie
    else:
        try:
            poids_kg = float(f.get("poids_kg") or 0)
        except ValueError:
            poids_kg = 0
        calories = _estimate_calories(met, duree_min, poids_kg) if duree_min > 0 else 0

    note = (f.get("note") or "").strip()

    remarque_parts = []
    if fc_moy > 0:
        remarque_parts.append(f"FC:{fc_moy}")
    if calories > 0:
        remarque_parts.append(f"Cal:{calories}")
    if rpe:
        remarque_parts.append(f"RPE:{rpe}")
    if note:
        remarque_parts.append(note[:60])
    remarque = " | ".join(remarque_parts)

    exo_final = f"CARDIO:{activite}"
    seance_name = f"Cardio {activite}"

    rows = [{
        "Semaine": semaine,
        "Séance": seance_name,
        "Exercice": exo_final,
        "Série": 1,
        "Reps": duree_min,
        "Poids": distance_km,
        "Remarque": remarque,
        "Muscle": "Cardio",
        "Date": date_str,
    }]

    try:
        replace_exo_rows(semaine, seance_name, exo_final, rows)
    except Exception as e:
        logger.error("cardio save FAILED: %s", e)
        return render_template(
            "error.html", code=503,
            message="Impossible de sauvegarder la séance cardio. Réessaie.",
        ), 503

    return redirect(url_for("accueil.index"))
