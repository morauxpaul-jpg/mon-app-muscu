"""Un repas détaillé aliment par aliment.

Le formulaire « Aliments » additionnait le panier côté navigateur et
n'envoyait que quatre totaux : « Riz 150 g, Poulet 120 g » devenait une note
et 612 kcal, impossible de corriger le riz sans tout refaire (audit du 03/10,
nutrition). Désormais chaque aliment est une ligne de la table `nutrition`,
avec sa quantité (`grams`) et ses valeurs pour 100 g (`food`) :

* les calories et macros sont recalculées ICI à partir des valeurs pour
  100 g — le navigateur ne fixe plus les totaux ;
* une quantité se corrige après coup (`recalculer`) ;
* les aliments déjà mangés reviennent en tête de la recherche (`recents`).
"""
import math

MAX_ITEMS = 25
MAX_GRAMS = 3000
MAX_UNITES = 4


def _nombre(v, plafond):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(n) or n < 0 or n > plafond:
        return None
    return n


def aliment_propre(f) -> dict | None:
    """Valeurs pour 100 g validées (nom, kcal, p, c, f, marque, code, unités),
    ou None. Une graisse pure plafonne à 900 kcal, un macro à 100 g."""
    if not isinstance(f, dict):
        return None
    nom = str(f.get("n") or "").strip()[:80]
    k = _nombre(f.get("k"), 950)
    p, c, l = (_nombre(f.get(x), 100) for x in ("p", "c", "f"))
    if not nom or None in (k, p, c, l):
        return None
    out = {"n": nom, "k": round(k, 1), "p": round(p, 1), "c": round(c, 1), "f": round(l, 1)}
    marque = str(f.get("brand") or "").strip()[:40]
    if marque:
        out["brand"] = marque
    code = "".join(ch for ch in str(f.get("code") or "") if ch.isdigit())[:14]
    if code:
        out["code"] = code
    unites = []
    for u in (f.get("u") or [])[:MAX_UNITES + 1]:
        if isinstance(u, (list, tuple)) and len(u) == 2:
            g = _nombre(u[1], MAX_GRAMS)
            lbl = str(u[0] or "").strip()[:30]
            if g and lbl and not lbl.startswith("comme la dernière fois"):
                unites.append([lbl, int(round(g))])
    if unites:
        out["u"] = unites[:MAX_UNITES]
    return out


def _macros(food: dict, grams: float) -> dict:
    r = grams / 100
    return {"calories": int(round(food["k"] * r)), "protein": int(round(food["p"] * r)),
            "carbs": int(round(food["c"] * r)), "fat": int(round(food["f"] * r))}


def ligne_aliment(item, date_iso: str, meal_type: str) -> dict | None:
    """Ligne `nutrition` pour un aliment du panier ({…aliment, grams})."""
    food = aliment_propre(item)
    grams = _nombre((item or {}).get("grams"), MAX_GRAMS) if isinstance(item, dict) else None
    if not food or not grams or grams < 1:
        return None
    note = food["n"] + (f" ({food['brand']})" if food.get("brand") else "")
    return {"date": date_iso, "meal_type": meal_type, **_macros(food, grams),
            "note": note[:200], "grams": round(grams, 1), "food": food}


def lignes_panier(items, date_iso: str, meal_type: str) -> list[dict]:
    if not isinstance(items, list):
        return []
    lignes = (ligne_aliment(it, date_iso, meal_type) for it in items[:MAX_ITEMS])
    return [ln for ln in lignes if ln]


def recalculer(row: dict, grams) -> dict | None:
    """Champs à écrire pour une nouvelle quantité, ou None si la ligne ne
    permet pas de recalculer (repas saisi en bloc, sans quantité)."""
    g = _nombre(grams, MAX_GRAMS)
    if not g or g < 1 or not row:
        return None
    food = aliment_propre(row.get("food"))
    if food:
        return {**_macros(food, g), "grams": round(g, 1)}
    ancien = _nombre(row.get("grams"), MAX_GRAMS)
    if not ancien:
        return None
    r = g / ancien
    return {k: int(round(int(row.get(k) or 0) * r)) for k in ("calories", "protein", "carbs", "fat")} \
        | {"grams": round(g, 1)}


def recents(rows, limite: int = 30) -> list[dict]:
    """Aliments déjà notés, les plus fréquents puis les plus récents d'abord,
    avec la dernière quantité en première portion (« comme la dernière fois »).
    `rows` arrive trié du plus récent au plus ancien."""
    vus: dict = {}
    for i, r in enumerate(rows or []):
        food = aliment_propre(r.get("food"))
        if not food:
            continue
        cle = (food["n"].lower(), food.get("code", ""))
        if cle in vus:
            vus[cle]["_nb"] += 1
            continue
        g = _nombre(r.get("grams"), MAX_GRAMS)
        unites = list(food.get("u") or [])
        if g and g >= 1:
            unites = [["comme la dernière fois", int(round(g))]] + unites
        if not any(u[1] == 100 for u in unites):
            unites.append(["100 g", 100])
        vus[cle] = {**food, "u": unites, "g": food.get("brand") or "Récent",
                    "r": -1, "recent": True, "_nb": 1, "_rang": i}
    tries = sorted(vus.values(), key=lambda f: (-f["_nb"], f["_rang"]))[:limite]
    for f in tries:
        f.pop("_nb", None)
        f.pop("_rang", None)
    return tries
