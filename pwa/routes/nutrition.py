"""Blueprint nutrition — profil métabolique + suivi calories/macros au quotidien.

- BMR via Mifflin-St Jeor
- TDEE = BMR × facteur d'activité
- Objectif calorique ajusté selon objectif (Masse/Maintien/Sèche)
- Macros recommandés en % selon objectif
- Table Supabase `nutrition` : un repas par ligne (date, meal_type, macros, note)
"""
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for

from core.data import get_profile, save_profile, list_nutrition, insert_nutrition, delete_nutrition
from core.dates import today_paris_str
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("nutrition", __name__)

ACTIVITE_FACTOR = {
    "sedentaire": 1.2,
    "leger": 1.375,
    "actif": 1.55,
    "tres_actif": 1.725,
    "athlete": 1.9,
}
ACTIVITE_LABELS = [
    ("sedentaire", "Sédentaire", "Peu ou pas d'exercice"),
    ("leger", "Légèrement actif", "1-3 séances / semaine"),
    ("actif", "Actif", "3-5 séances / semaine"),
    ("tres_actif", "Très actif", "6-7 séances / semaine"),
    ("athlete", "Athlète", "Entraînement bi-quotidien"),
]

OBJECTIFS = [
    ("masse", "Prise de masse", "+300 à +500 kcal"),
    ("maintien", "Maintien", "TDEE"),
    ("seche", "Sèche", "-300 à -500 kcal"),
]

# % macros par objectif (protéines / glucides / lipides)
MACRO_SPLIT = {
    "masse": (30, 45, 25),
    "maintien": (25, 50, 25),
    "seche": (35, 40, 25),
}

# kcal par gramme
KCAL_PER_G = {"protein": 4, "carbs": 4, "fat": 9}

MEAL_TYPES = [
    ("petit_dej", "Petit-déj"),
    ("dejeuner", "Déjeuner"),
    ("diner", "Dîner"),
    ("collation", "Collation"),
]
MEAL_TYPES_MAP = dict(MEAL_TYPES)


def _bmr(poids_kg, taille_cm, age, sexe):
    """Mifflin-St Jeor."""
    base = 10 * poids_kg + 6.25 * taille_cm - 5 * age
    return base + 5 if sexe == "H" else base - 161


def _compute_targets(profile):
    """Retourne dict(bmr, tdee, calories_cible, macros_g={protein,carbs,fat}) ou None."""
    try:
        poids = float(profile.get("poids_kg") or 0)
        taille = float(profile.get("taille_cm") or 0)
        age = int(profile.get("age") or 0)
    except (TypeError, ValueError):
        return None
    sexe = (profile.get("sexe") or "").strip().upper()
    activite = (profile.get("activite") or "").strip()
    objectif = (profile.get("objectif_nutrition") or "maintien").strip()

    if poids <= 0 or taille <= 0 or age <= 0 or sexe not in ("H", "F") or activite not in ACTIVITE_FACTOR:
        return None

    bmr = _bmr(poids, taille, age, sexe)
    tdee = bmr * ACTIVITE_FACTOR[activite]

    if objectif == "masse":
        cible = tdee + 400
    elif objectif == "seche":
        cible = tdee - 400
    else:
        cible = tdee

    prot_pct, carbs_pct, fat_pct = MACRO_SPLIT.get(objectif, MACRO_SPLIT["maintien"])
    macros_g = {
        "protein": int(round(cible * (prot_pct / 100) / KCAL_PER_G["protein"])),
        "carbs": int(round(cible * (carbs_pct / 100) / KCAL_PER_G["carbs"])),
        "fat": int(round(cible * (fat_pct / 100) / KCAL_PER_G["fat"])),
    }
    return {
        "bmr": int(round(bmr)),
        "tdee": int(round(tdee)),
        "calories_cible": int(round(cible)),
        "macros_g": macros_g,
        "macros_pct": {"protein": prot_pct, "carbs": carbs_pct, "fat": fat_pct},
        "objectif": objectif,
    }


@bp.route("/nutrition")
def index():
    profile = get_profile() or {}
    targets = _compute_targets(profile)

    date_iso = request.args.get("date") or today_paris_str()

    meals = list_nutrition(date_iso)
    # Agrégats du jour
    totals = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    meals_by_type = {k: [] for k, _ in MEAL_TYPES}
    for m in meals:
        for k in totals:
            totals[k] += int(m.get(k) or 0)
        mt = m.get("meal_type") or "collation"
        meals_by_type.setdefault(mt, []).append(m)

    # Progression donut : % calories consommées / cible
    cal_cible = (targets or {}).get("calories_cible") or 0
    cal_pct = int(min(100, round((totals["calories"] / cal_cible) * 100))) if cal_cible > 0 else 0

    macros_g = (targets or {}).get("macros_g") or {"protein": 0, "carbs": 0, "fat": 0}

    def _pct(val, goal):
        return int(min(100, round((val / goal) * 100))) if goal > 0 else 0

    macros_progress = {
        "protein": {"val": totals["protein"], "goal": macros_g["protein"],
                    "pct": _pct(totals["protein"], macros_g["protein"])},
        "carbs":   {"val": totals["carbs"],   "goal": macros_g["carbs"],
                    "pct": _pct(totals["carbs"], macros_g["carbs"])},
        "fat":     {"val": totals["fat"],     "goal": macros_g["fat"],
                    "pct": _pct(totals["fat"], macros_g["fat"])},
    }

    return render_template(
        "nutrition.html",
        active="plus",
        profile=profile,
        targets=targets,
        date_iso=date_iso,
        totals=totals,
        meals_by_type=meals_by_type,
        meal_types=MEAL_TYPES,
        meal_types_map=MEAL_TYPES_MAP,
        activite_labels=ACTIVITE_LABELS,
        objectifs=OBJECTIFS,
        cal_pct=cal_pct,
        macros_progress=macros_progress,
    )


@bp.route("/nutrition/profile", methods=["POST"])
@limiter.limit("10 per minute")
def save_profile_route():
    f = request.form

    def _num(k, cast, default=0):
        try:
            return cast(f.get(k) or default)
        except (ValueError, TypeError):
            return default

    fields = {
        "poids_kg": _num("poids_kg", float),
        "taille_cm": _num("taille_cm", float),
        "age": _num("age", int),
        "sexe": (f.get("sexe") or "").upper()[:1],
        "activite": (f.get("activite") or "").strip(),
        "objectif_nutrition": (f.get("objectif_nutrition") or "maintien").strip(),
    }
    # Calcul + stockage
    targets = _compute_targets(fields)
    if targets:
        fields["tdee"] = targets["tdee"]
        fields["calories_cible"] = targets["calories_cible"]

    try:
        save_profile(fields)
    except Exception as e:
        logger.error("nutrition save_profile FAILED: %s", e)
    return redirect(url_for("nutrition.index"))


@bp.route("/nutrition/add-meal", methods=["POST"])
@limiter.limit("30 per minute")
def add_meal():
    f = request.form
    date_iso = f.get("date") or today_paris_str()
    try:
        datetime.strptime(date_iso, "%Y-%m-%d")
    except ValueError:
        date_iso = today_paris_str()

    meal_type = (f.get("meal_type") or "collation").strip()
    if meal_type not in MEAL_TYPES_MAP:
        meal_type = "collation"

    def _pos_int(k):
        try:
            return max(0, int(float(f.get(k) or 0)))
        except (ValueError, TypeError):
            return 0

    row = {
        "date": date_iso,
        "meal_type": meal_type,
        "calories": _pos_int("calories"),
        "protein": _pos_int("protein"),
        "carbs": _pos_int("carbs"),
        "fat": _pos_int("fat"),
        "note": (f.get("note") or "").strip()[:200],
    }
    try:
        insert_nutrition(row)
    except Exception as e:
        logger.error("add_meal FAILED: %s", e)
    return redirect(url_for("nutrition.index", date=date_iso))


@bp.route("/nutrition/delete-meal", methods=["POST"])
@limiter.limit("20 per minute")
def remove_meal():
    f = request.form
    try:
        entry_id = int(f.get("id") or 0)
    except (ValueError, TypeError):
        entry_id = 0
    date_iso = f.get("date") or today_paris_str()
    if entry_id > 0:
        try:
            delete_nutrition(entry_id)
        except Exception as e:
            logger.error("delete_meal FAILED: %s", e)
    return redirect(url_for("nutrition.index", date=date_iso))
