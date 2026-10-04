"""Blueprint nutrition — profil métabolique + suivi calories/macros au quotidien.

- Cibles (`core/nutrition_cibles.py`) : Mifflin-St Jeor × activité, ajustée
  selon l'objectif ; protéines en g/kg ; plus de glucides les jours
  d'entraînement, moins les jours de repos.
- Table Supabase `nutrition` : une ligne par aliment (`core/nutrition_aliments.py`)
  ou par repas saisi en bloc (saisie rapide, plats de la semaine).
"""
import json
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, g, jsonify

from core.data import (
    get_profile, save_profile, list_nutrition, insert_nutrition, delete_nutrition,
    sum_nutrition_range, get_prog, save_prog, upsert_body_weight, get_hist,
    insert_nutrition_rows, get_nutrition, update_nutrition, list_nutrition_recents,
)
from core.dates import today_paris_str, today_paris, DAYS_FR
from core.limiter import limiter
from core.analytics import paywall
from core.foods_data import FOODS
from core.nutrition_cibles import (
    compute_targets, custom_cal, cible_pour, cycle_actif, est_jour_entrainement, jours_seances,
)
from core.nutrition_aliments import lignes_panier, recalculer, recents as aliments_recents

logger = logging.getLogger(__name__)

bp = Blueprint("nutrition", __name__)

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

MEAL_TYPES = [
    ("petit_dej", "Petit-déj"),
    ("dejeuner", "Déjeuner"),
    ("diner", "Dîner"),
    ("collation", "Collation"),
]
MEAL_TYPES_MAP = dict(MEAL_TYPES)
RECENTS_JOURS = 60

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


# Noms historiques : `routes/progres.py` recalcule la cible après une pesée.
_compute_targets = compute_targets
_custom_cal = custom_cal


def _date_demandee(raw) -> str:
    try:
        return datetime.strptime(str(raw or ""), "%Y-%m-%d").date().isoformat()
    except ValueError:
        return today_paris_str()


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
    date_iso = _date_demandee(request.args.get("date"))
    selected_date = datetime.strptime(date_iso, "%Y-%m-%d").date()
    try:
        hist = get_hist()
    except Exception as e:
        logger.error("nutrition get_hist FAILED: %s", e)
        hist = []
    targets, jour = cible_pour(profile, prog, hist, selected_date)

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

    # Progression donut : % calories consommées / cible DU JOUR
    cal_cible = (jour or {}).get("calories") or 0
    cal_pct = int(min(100, round((totals["calories"] / cal_cible) * 100))) if cal_cible > 0 else 0
    macros_g = (jour or {}).get("macros_g") or {"protein": 0, "carbs": 0, "fat": 0}

    def _pct(val, goal):
        return int(min(100, round((val / goal) * 100))) if goal > 0 else 0

    macros_progress = {k: {"val": totals[k], "goal": macros_g[k], "pct": _pct(totals[k], macros_g[k])}
                       for k in ("protein", "carbs", "fat")}

    # Semaine : lun→dim de la semaine contenant date_iso, plus la veille du
    # lundi (pour « Reprendre hier » le lundi).
    monday = selected_date - timedelta(days=selected_date.weekday())
    sunday = monday + timedelta(days=6)
    today_iso = today_paris_str()
    try:
        week_totals = sum_nutrition_range((monday - timedelta(days=1)).isoformat(), sunday.isoformat())
    except Exception as e:
        logger.error("nutrition week_totals FAILED: %s", e)
        week_totals = {}
    faits = jours_seances(hist)
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
            "training": est_jour_entrainement(prog, faits, d),
        })
    veille = (selected_date - timedelta(days=1)).isoformat()
    veille_slots = (week_totals.get(veille) or {}).get("slots") or []

    try:
        recents = aliments_recents(list_nutrition_recents(
            (selected_date - timedelta(days=RECENTS_JOURS)).isoformat()))
    except Exception as e:
        # Colonnes v40 absentes ou base indisponible : la recherche marche sans.
        logger.warning("nutrition recents indisponibles: %s", e)
        recents = []

    return render_template(
        "nutrition.html",
        active="plus",
        profile=profile,
        targets=targets,
        jour=jour,
        cycle_actif=cycle_actif(prog),
        date_iso=date_iso,
        veille=veille,
        veille_slots=veille_slots,
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
        foods=FOODS,
        recents=recents,
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
        # Case « Adapter aux jours d'entraînement » : une case décochée
        # n'est pas envoyée, d'où le champ témoin `cycle_form`.
        if f.get("cycle_form"):
            if f.get("cycle"):
                nutri.pop("cycle", None)
            else:
                nutri["cycle"] = False
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
    # Le poids saisi ici vaut pesée du jour : il alimente la courbe de Progrès
    # (et inversement, une pesée dans Progrès met ce profil à jour).
    if 20 <= fields["poids_kg"] < 500:
        try:
            upsert_body_weight(today_paris_str(), fields["poids_kg"])
        except Exception as e:
            logger.error("nutrition upsert_body_weight FAILED: %s", e)
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

    # Panier « Aliments » : une ligne par aliment, macros recalculées ici à
    # partir des valeurs pour 100 g (le navigateur ne fixe plus les totaux).
    if f.get("items"):
        try:
            items = json.loads(f.get("items"))
        except (ValueError, TypeError):
            items = None
        rows = lignes_panier(items, date_iso, meal_type)
        if not rows:
            return render_template("error.html", code=400,
                                   message="Aucun aliment valide dans ce repas."), 400
        try:
            insert_nutrition_rows(rows)
        except Exception as e:
            logger.error("add_meal items FAILED: %s", e)
            return render_template(
                "error.html", code=503,
                message="Le repas n'a pas pu être enregistré. Réessaie dans un instant.",
            ), 503
        return redirect(url_for("nutrition.index", date=date_iso))

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
        # L'échec était journalisé puis redirigé comme un succès : le repas
        # « ajouté » n'apparaissait simplement pas (audit du 03/10, I13).
        return render_template(
            "error.html", code=503,
            message="Le repas n'a pas pu être enregistré. Réessaie dans un instant.",
        ), 503
    return redirect(url_for("nutrition.index", date=date_iso))


@bp.route("/nutrition/edit-meal", methods=["POST"])
@limiter.limit("30 per minute")
def edit_meal():
    """Corrige la quantité d'un aliment déjà noté (macros recalculées)."""
    if _require_vip():
        return redirect(url_for("nutrition.index"))
    f = request.form
    date_iso = _date_demandee(f.get("date"))
    try:
        entry_id = int(f.get("id") or 0)
        grams = float(str(f.get("grams") or "").replace(",", "."))
    except (ValueError, TypeError):
        entry_id, grams = 0, 0
    row = get_nutrition(entry_id) if entry_id > 0 else None
    champs = recalculer(row, grams) if row else None
    if not champs:
        return render_template("error.html", code=400,
                               message="Quantité invalide pour cet aliment."), 400
    try:
        update_nutrition(entry_id, champs)
    except Exception as e:
        logger.error("edit_meal FAILED: %s", e)
        return render_template("error.html", code=503,
                               message="La quantité n'a pas pu être corrigée. Réessaie."), 503
    return redirect(url_for("nutrition.index", date=date_iso))


@bp.route("/nutrition/copier", methods=["POST"])
@limiter.limit("20 per minute")
def copier_repas():
    """« Reprendre hier » : recopie un créneau (petit-déj, déjeuner…) d'un
    jour sur un autre. Le petit-déj de la semaine est souvent le même."""
    if _require_vip():
        return redirect(url_for("nutrition.index"))
    f = request.form
    date_iso = _date_demandee(f.get("date"))
    source = _date_demandee(f.get("source"))
    meal_type = (f.get("meal_type") or "").strip()
    if meal_type not in MEAL_TYPES_MAP or source == date_iso:
        return redirect(url_for("nutrition.index", date=date_iso))
    garder = ("calories", "protein", "carbs", "fat", "note", "grams", "food")
    try:
        rows = [{"date": date_iso, "meal_type": meal_type,
                 **{k: r[k] for k in garder if r.get(k) is not None}}
                for r in list_nutrition(source) if r.get("meal_type") == meal_type]
        insert_nutrition_rows(rows)
    except Exception as e:
        logger.error("copier_repas FAILED: %s", e)
        return render_template("error.html", code=503,
                               message="Le repas n'a pas pu être recopié. Réessaie."), 503
    return redirect(url_for("nutrition.index", date=date_iso))


@bp.route("/nutrition/recherche")
@limiter.limit("20 per minute")
def recherche():
    """Produits du commerce par leur nom (Open Food Facts), à la demande."""
    from core.openfoodfacts import search

    if _require_vip():
        return jsonify({"ok": False, "error": "La recherche fait partie de PRO."}), 403
    q = request.args.get("q") or ""
    if len(q.strip()) < 3:
        return jsonify({"ok": False, "error": "Tape au moins 3 lettres."}), 400
    found = search(q)
    if found is None:
        return jsonify({"ok": False, "error": "Recherche indisponible pour l'instant. Réessaie dans une minute."}), 503
    return jsonify({"ok": True, "foods": found})


@bp.route("/nutrition/barcode/<code>")
@limiter.limit("40 per hour")
def barcode(code):
    """Macros d'un produit emballé à partir de son code-barres.

    Le scan se fait dans le navigateur ; cette route ne fait que l'appel à
    Open Food Facts. Le faire côté serveur plutôt que depuis la page évite
    d'exposer l'utilisateur à un tiers (son adresse IP et ses scans ne sortent
    pas de l'app) et permet de mutualiser le cache entre tous les comptes.
    """
    from core.openfoodfacts import clean_code, lookup

    if _require_vip():
        return jsonify({"ok": False,
                        "error": "Le scan de code-barres fait partie de PRO."}), 403
    clean = clean_code(code)
    if not clean:
        return jsonify({"ok": False, "error": "code invalide"}), 400

    food = lookup(clean)
    if not food:
        return jsonify({"ok": False, "code": clean,
                        "error": "Produit inconnu d'Open Food Facts."}), 200
    return jsonify({"ok": True, "food": food})


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
