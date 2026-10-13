"""Mes recettes et aliments — la page qui les crée, les corrige et les supprime.

Les calculs sont dans core/nutrition_recettes.py, la table dans
core/db_aliments.py (v49). Une fois enregistrés, la recherche du repas les
propose comme n'importe quel aliment (routes/nutrition.py).

Une saisie refusée (nom en double, poids cuit invraisemblable…) rouvre
l'éditeur avec ce qui a été tapé : une recette de quinze ingrédients ne se
perd pas sur une faute.
"""
import json
import logging
from datetime import timedelta

from flask import Blueprint, g, redirect, render_template, request, url_for

from core.analytics import paywall
from core.data import (
    AlimentsIndisponibles, enregistrer_aliment_perso, list_aliments_perso,
    list_nutrition_recents, supprimer_aliment_perso,
)
from core.dates import today_paris
from core.foods_data import FOODS
from core.limiter import limiter
from core.nutrition_aliments import MAX_GRAMS, aliment_propre, recents as aliments_recents
from core.nutrition_recettes import (
    MAX_PERSO, aliment_saisi, doublon, nombre, nom_propre, par_part,
    pour_la_recherche, rafraichir_recents, recette,
)

logger = logging.getLogger(__name__)

bp = Blueprint("nutrition_recettes", __name__)

RECENTS_JOURS = 60


def _fiche(row: dict) -> dict:
    """Ce que la liste affiche d'un de mes aliments."""
    food = aliment_propre(row.get("food")) or {}
    rec = row.get("recette") if isinstance(row.get("recette"), dict) else None
    return {"id": row.get("id"), "nom": row.get("nom") or food.get("n", ""),
            "recette": rec is not None, "parts": (rec or {}).get("parts"),
            "ingredients": len((rec or {}).get("ingredients") or []),
            "part": par_part(food) if food.get("u") else None}


def _edition_depuis_ligne(row: dict) -> dict:
    """L'éditeur prérempli avec un aliment enregistré."""
    rec = row.get("recette") if isinstance(row.get("recette"), dict) else None
    if rec is not None:
        return {"type": "recette", "id": row["id"], "nom": row.get("nom", ""),
                "ingredients": rec.get("ingredients") or [], "parts": rec.get("parts") or 1,
                "poids_cuit": rec.get("poids_cuit") or ""}
    food = aliment_propre(row.get("food")) or {"k": 0, "p": 0, "c": 0, "f": 0, "u": []}
    lbl, pour = next(((u[0], u[1]) for u in food.get("u") or [] if u[0] != "100 g"), ("", 100))
    r = pour / 100
    def val(x):
        return f"{round(food[x] * r, 1):g}"
    return {"type": "aliment", "id": row["id"], "nom": row.get("nom", ""), "pour_g": pour,
            "portion": "" if lbl == "1 portion" else lbl,
            "kcal": val("k"), "p": val("p"), "c": val("c"), "f": val("f")}


def _edition_depuis_saisie(f, type_, aliment_id) -> dict:
    """L'éditeur rouvert sur ce qui a été tapé (saisie refusée)."""
    if type_ == "recette":
        try:
            brut = json.loads(f.get("ingredients") or "[]")
        except (ValueError, TypeError):
            brut = []
        items = []
        for it in brut if isinstance(brut, list) else []:
            food = aliment_propre(it)
            grams = nombre((it or {}).get("grams"), MAX_GRAMS) if isinstance(it, dict) else None
            if food and grams:
                items.append({**food, "grams": grams})
        return {"type": "recette", "id": aliment_id, "nom": nom_propre(f.get("nom")),
                "ingredients": items, "parts": (f.get("parts") or "")[:3],
                "poids_cuit": (f.get("poids_cuit") or "")[:6]}
    return {"type": "aliment", "id": aliment_id, "nom": nom_propre(f.get("nom")),
            **{k: (f.get(k) or "")[:10] for k in ("pour_g", "kcal", "p", "c", "f")},
            "portion": nom_propre(f.get("portion"))[:30]}


def _page(rows, edition=None, erreur="", dispo=True, status=200, message=""):
    recettes = [_fiche(r) for r in rows if r.get("recette")]
    aliments = [_fiche(r) for r in rows if not r.get("recette")]
    donnees = None
    if edition and edition.get("type") == "recette":
        # La recherche d'ingrédients : mes aliments (sauf la recette ouverte),
        # mes récents, puis la base d'aliments courants.
        autres = [r for r in rows if r.get("id") != edition.get("id")]
        perso = pour_la_recherche(autres)
        try:
            debut = (today_paris() - timedelta(days=RECENTS_JOURS)).isoformat()
            recents = rafraichir_recents(aliments_recents(list_nutrition_recents(debut)), perso)
        except Exception as e:
            logger.warning("recettes : récents indisponibles: %s", e)
            recents = []
        donnees = {"foods": FOODS, "recents": recents, "perso": perso, "edition": edition}
    return render_template(
        "nutrition_aliments.html", active="plus", recettes=recettes, aliments=aliments,
        edition=edition, erreur=erreur, dispo=dispo, donnees=donnees, message=message,
        plein=len(rows) >= MAX_PERSO, max_perso=MAX_PERSO,
    ), status


def _lire():
    try:
        return list_aliments_perso(), True
    except AlimentsIndisponibles:
        return [], False


def _entier(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@bp.route("/nutrition/aliments")
def mes_aliments():
    if not getattr(g, "is_vip", False):
        return paywall("Nutrition")
    rows, dispo = _lire()
    a = request.args
    edition, message = None, ""
    if not dispo:
        return _page(rows, dispo=False)
    if a.get("nouveau") in ("recette", "aliment"):
        edition = {"type": a.get("nouveau"), "id": None, "nom": "", "ingredients": [],
                   "parts": 4, "poids_cuit": "", "pour_g": 100}
    elif _entier(a.get("modifier")):
        row = next((r for r in rows if r.get("id") == _entier(a.get("modifier"))), None)
        edition = _edition_depuis_ligne(row) if row else None
    if _entier(a.get("enregistre")):
        row = next((r for r in rows if r.get("id") == _entier(a.get("enregistre"))), None)
        if row:
            message = (f"C'est enregistré : « {row.get('nom')} » est dans la "
                       "recherche de tes repas.")
    elif a.get("supprime"):
        message = "Supprimé. Les repas déjà notés gardent leurs valeurs."
    return _page(rows, edition=edition, message=message)


@bp.route("/nutrition/aliments/enregistrer", methods=["POST"])
@limiter.limit("30 per minute")
def enregistrer():
    if not getattr(g, "is_vip", False):
        return redirect(url_for("nutrition.index"))
    f = request.form
    type_ = "recette" if f.get("type") == "recette" else "aliment"
    rows, dispo = _lire()
    if not dispo:
        return _page(rows, dispo=False, status=503)
    aliment_id = _entier(f.get("id"))
    if aliment_id is not None and not any(r.get("id") == aliment_id for r in rows):
        return redirect(url_for("nutrition_recettes.mes_aliments"))
    if type_ == "recette":
        try:
            ingredients = json.loads(f.get("ingredients") or "[]")
        except (ValueError, TypeError):
            ingredients = []
        food, detail, erreur = recette(f.get("nom"), ingredients, f.get("parts"), f.get("poids_cuit"))
    else:
        detail = None
        food, erreur = aliment_saisi(f.get("nom"), f.get("pour_g"), f.get("kcal"),
                                     f.get("p"), f.get("c"), f.get("f"), f.get("portion"))
    if not erreur and doublon(food["n"], rows, sauf=aliment_id):
        erreur = f"Tu as déjà « {food['n']} » : choisis un autre nom, ou modifie celui-là."
    if not erreur and aliment_id is None and len(rows) >= MAX_PERSO:
        erreur = f"Tu as atteint {MAX_PERSO} recettes et aliments : supprimes-en un d'abord."
    if erreur:
        return _page(rows, edition=_edition_depuis_saisie(f, type_, aliment_id),
                     erreur=erreur, status=400)
    try:
        nouvel_id = enregistrer_aliment_perso(food["n"], food, detail, aliment_id)
    except AlimentsIndisponibles:
        return _page(rows, dispo=False, status=503)
    except Exception as e:
        logger.error("enregistrer aliment perso FAILED: %s", e)
        return render_template("error.html", code=503,
                               message="L'enregistrement a échoué. Réessaie dans un instant."), 503
    return redirect(url_for("nutrition_recettes.mes_aliments", enregistre=nouvel_id))


@bp.route("/nutrition/aliments/supprimer", methods=["POST"])
@limiter.limit("30 per minute")
def supprimer():
    if not getattr(g, "is_vip", False):
        return redirect(url_for("nutrition.index"))
    aliment_id = _entier(request.form.get("id"))
    if aliment_id:
        try:
            supprimer_aliment_perso(aliment_id)
        except AlimentsIndisponibles:
            return _page([], dispo=False, status=503)
        except Exception as e:
            logger.error("supprimer aliment perso FAILED: %s", e)
            return render_template("error.html", code=503,
                                   message="La suppression a échoué. Réessaie dans un instant."), 503
    return redirect(url_for("nutrition_recettes.mes_aliments", supprime=1))
