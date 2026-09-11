"""Blueprint nutrition — profil métabolique + suivi calories/macros au quotidien.

- BMR via Mifflin-St Jeor
- TDEE = BMR × facteur d'activité
- Objectif calorique ajusté selon objectif (Masse/Maintien/Sèche)
- Macros recommandés en % selon objectif
- Table Supabase `nutrition` : un repas par ligne (date, meal_type, macros, note)
"""
import json
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, g

from core.data import (
    get_profile, save_profile, list_nutrition, insert_nutrition, delete_nutrition,
    sum_nutrition_range, get_prog, save_prog,
)
from core.dates import today_paris_str, today_paris, DAYS_FR
from core.limiter import limiter
from core.analytics import paywall

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

# Format du fichier « Mes plats de la semaine » (import JSON, comme le programme).
MEAL_PLAN_FORMAT = "muscu-plats-v1"
MAX_PLATS = 40


def _get_meal_plan(prog):
    """Liste des plats préparés de la semaine (config user, dans `prog`).
    Chaque plat : name, portion, calories, protein, carbs, fat."""
    mp = prog.get("_meal_plan") or {}
    plats = mp.get("plats") if isinstance(mp, dict) else None
    return {
        "label": (mp.get("label") if isinstance(mp, dict) else "") or "",
        "plats": plats if isinstance(plats, list) else [],
    }


def _parse_plats(data):
    """Valide + normalise la liste de plats d'un JSON importé. Accepte les clés
    FR (nom/portion/prot/gluc/lip) et EN (name/protein/carbs/fat)."""
    if not isinstance(data, dict) or data.get("_format") != MEAL_PLAN_FORMAT:
        return None
    raw = data.get("plats")
    if not isinstance(raw, list):
        return None

    def _int(d, *keys):
        for k in keys:
            if k in d:
                try:
                    return max(0, int(round(float(d.get(k) or 0))))
                except (ValueError, TypeError):
                    return 0
        return 0

    plats = []
    for p in raw[:MAX_PLATS]:
        if not isinstance(p, dict):
            continue
        name = (p.get("nom") or p.get("name") or "").strip()[:80]
        if not name:
            continue
        plats.append({
            "name": name,
            "portion": (p.get("portion") or "").strip()[:60],
            "calories": _int(p, "calories", "kcal", "cal"),
            "protein": _int(p, "prot", "protein", "proteines", "p"),
            "carbs": _int(p, "gluc", "carbs", "glucides", "g"),
            "fat": _int(p, "lip", "fat", "lipides", "l"),
        })
    label = str(data.get("semaine") or data.get("label") or "").strip()[:60]
    return {"label": label, "plats": plats}


def _bmr(poids_kg, taille_cm, age, sexe):
    """Mifflin-St Jeor."""
    base = 10 * poids_kg + 6.25 * taille_cm - 5 * age
    return base + 5 if sexe == "H" else base - 161


def _custom_cal(prog):
    """Cible calorique manuelle de l'user (0 = auto). Stockée dans `prog`
    (JSONB, sans migration Supabase) et non dans la table `profiles`."""
    try:
        return max(0, min(10000, int((prog.get("_nutrition") or {}).get("calories_custom") or 0)))
    except (TypeError, ValueError):
        return 0


def _compute_targets(profile, custom_cal=0):
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
    cible_auto = int(round(cible))

    # Cible manuelle : si l'user a fixé sa propre cible calorique (ex. un plan de
    # rééquilibrage à 2400), elle PRIME sur le calcul automatique. Les macros
    # s'ajustent alors sur cette cible (même répartition selon l'objectif).
    is_custom = custom_cal > 0
    if is_custom:
        cible = custom_cal

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
        "calories_auto": cible_auto,
        "is_custom": is_custom,
        "macros_g": macros_g,
        "macros_pct": {"protein": prot_pct, "carbs": carbs_pct, "fat": fat_pct},
        "objectif": objectif,
    }


@bp.route("/nutrition")
def index():
    # Nutrition = fonctionnalité Premium (offre « équilibrée »). Les comptes
    # gratuits voient le mur PRO plutôt que la page (masque l'avancé + incite).
    if not getattr(g, "is_vip", False):
        return paywall("Nutrition")
    try:
        profile = get_profile() or {}
    except Exception as e:
        logger.error("nutrition get_profile FAILED: %s", e)
        profile = {}
    prog = get_prog()
    targets = _compute_targets(profile, _custom_cal(prog))

    date_iso = request.args.get("date") or today_paris_str()

    # Si la table nutrition n'existe pas encore (SQL non exécuté), on dégrade
    # gracieusement au lieu d'un 500 : l'utilisateur voit la page profil et un
    # message pour qu'il sache que la table manque.
    nutrition_ready = True
    try:
        meals = list_nutrition(date_iso)
    except Exception as e:
        logger.error("nutrition list_nutrition FAILED: %s", e)
        meals = []
        nutrition_ready = False
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

    # Semaine : lun→dim de la semaine contenant date_iso
    try:
        selected_date = datetime.strptime(date_iso, "%Y-%m-%d").date()
    except ValueError:
        selected_date = today_paris()
    monday = selected_date - timedelta(days=selected_date.weekday())
    sunday = monday + timedelta(days=6)
    today_iso = today_paris_str()
    try:
        week_totals = sum_nutrition_range(monday.isoformat(), sunday.isoformat())
    except Exception as e:
        logger.error("nutrition week_totals FAILED: %s", e)
        week_totals = {}
    week_days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        d_iso = d.isoformat()
        cals = (week_totals.get(d_iso) or {}).get("calories", 0)
        week_days.append({
            "date_iso": d_iso,
            "day_label": DAYS_FR[i][:3],
            "day_num": d.day,
            "calories": cals,
            "is_selected": d_iso == date_iso,
            "is_today": d_iso == today_iso,
            "is_future": d_iso > today_iso,
        })

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
        nutrition_ready=nutrition_ready,
        week_days=week_days,
        meal_plan=_get_meal_plan(prog),
        calories_custom=_custom_cal(prog),
    )


def _require_vip():
    """True si free (l'appelant doit alors court-circuiter). Garde anti-bypass
    sur les actions POST nutrition (la page est déjà gatée côté GET)."""
    return not getattr(g, "is_vip", False)


@bp.route("/nutrition/profile", methods=["POST"])
@limiter.limit("10 per minute")
def save_profile_route():
    if _require_vip():
        return redirect(url_for("nutrition.index"))
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

    # Cible calorique manuelle : stockée dans `prog` (JSONB), PAS dans la table
    # `profiles` (colonne inexistante → l'upsert échouerait entièrement).
    custom_cal = max(0, min(10000, _num("calories_custom", int)))
    try:
        prog = get_prog()
        nutri = prog.setdefault("_nutrition", {})
        if custom_cal > 0:
            nutri["calories_custom"] = custom_cal
        else:
            nutri.pop("calories_custom", None)
        save_prog(prog)
    except Exception as e:
        logger.error("nutrition save custom_cal FAILED: %s", e)

    # Calcul + stockage profil (colonnes existantes uniquement).
    targets = _compute_targets(fields, custom_cal)
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
    if _require_vip():
        return redirect(url_for("nutrition.index"))
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


@bp.route("/nutrition/plats/import", methods=["POST"])
@limiter.limit("10 per minute")
def import_plats():
    """Importe la liste des plats de la semaine (JSON collé ou fichier),
    façon import de programme. Remplace la liste précédente."""
    if _require_vip():
        return redirect(url_for("nutrition.index"))
    raw_text = (request.form.get("data") or "").strip()
    if not raw_text:
        file = request.files.get("file")
        if file and file.filename:
            try:
                raw_text = file.read().decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                return redirect(url_for("nutrition.index") + "?plats=parse")
    if not raw_text:
        return redirect(url_for("nutrition.index") + "?plats=empty")
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return redirect(url_for("nutrition.index") + "?plats=parse")

    parsed = _parse_plats(data)
    if parsed is None:
        return redirect(url_for("nutrition.index") + "?plats=format")
    if not parsed["plats"]:
        return redirect(url_for("nutrition.index") + "?plats=empty")

    prog = get_prog()
    prog["_meal_plan"] = parsed
    save_prog(prog)
    return redirect(url_for("nutrition.index") + f"?plats=ok&n={len(parsed['plats'])}")


@bp.route("/nutrition/plats/clear", methods=["POST"])
@limiter.limit("10 per minute")
def clear_plats():
    if _require_vip():
        return redirect(url_for("nutrition.index"))
    prog = get_prog()
    if prog.pop("_meal_plan", None) is not None:
        save_prog(prog)
    return redirect(url_for("nutrition.index") + "?plats=cleared")


@bp.route("/nutrition/delete-meal", methods=["POST"])
@limiter.limit("20 per minute")
def remove_meal():
    if _require_vip():
        return redirect(url_for("nutrition.index"))
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
