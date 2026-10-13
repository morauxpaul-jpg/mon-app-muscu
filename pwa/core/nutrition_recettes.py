"""Mes aliments et mes recettes (table `aliments_perso`, migration v49).

Les pâtes carbonara reviennent trois fois en septembre dans le carnet, à
1 150, 897 puis 880 kcal : la même assiette, ressaisie de mémoire à chaque
fois (relevé du 12/10). Une recette se saisit une fois — ses ingrédients
pesés, le nombre de parts — puis s'ajoute comme n'importe quel aliment.

Une recette EST un aliment : ses valeurs pour 100 g sont celles du plat
entier rapportées à son poids. Le panier, la correction de quantité et les
« récents » marchent donc tels quels (core/nutrition_aliments.py). Le poids
du plat cuit est facultatif : une part vaut 1/N de la recette dans les deux
cas, mais seul le poids cuit permet de manger « au poids » (les pâtes
doublent de poids en cuisant, la viande en perd).

Un aliment perso se saisit comme sur l'étiquette : valeurs pour 100 g, ou
pour une portion (« 1 barre = 45 g »).

Les repas déjà notés gardent leurs valeurs : corriger une recette ne
réécrit pas le passé.
"""
import math

from core.nutrition_aliments import MAX_GRAMS, aliment_propre

MAX_PERSO = 200
MAX_INGREDIENTS = 40
MAX_PARTS = 50
MAX_POIDS_RECETTE = 20000      # 20 kg de préparation
KCAL_MAX_100G = 950            # comme aliment_propre : l'huile fait 900
MACROS_MAX_100G = 105          # 100 g, plus les arrondis de l'étiquette
LIBELLE_PART = "1 part"


def nombre(v, plafond):
    """Nombre positif ou nul, virgule acceptée ; None si vide ou hors bornes."""
    if isinstance(v, str):
        v = v.strip().replace(",", ".")
        if not v:
            return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(n) or n < 0 or n > plafond:
        return None
    return n


def nom_propre(v) -> str:
    return " ".join(str(v or "").split())[:80]


def _cle(nom: str) -> str:
    return nom_propre(nom).lower()


def _invraisemblable(food: dict) -> str:
    if food["k"] > KCAL_MAX_100G:
        return "plus de 950 kcal pour 100 g"
    if food["p"] + food["c"] + food["f"] > MACROS_MAX_100G:
        return "plus de 100 g de protéines, glucides et lipides pour 100 g"
    return ""


def aliment_saisi(nom, pour_g, kcal, p, c, f, portion="") -> tuple:
    """(aliment pour 100 g, erreur) depuis une étiquette : valeurs pour
    `pour_g` grammes. Sans calories, elles se déduisent des macros
    (4 kcal par gramme de protéines ou de glucides, 9 de lipides)."""
    nom = nom_propre(nom)
    if not nom:
        return None, "Donne un nom à cet aliment."
    pour = nombre(pour_g, MAX_GRAMS) if str(pour_g or "").strip() else 100.0
    if not pour or pour < 1:
        return None, "Indique pour combien de grammes sont ces valeurs (1 à 3 000 g)."
    macros = [nombre(x, MAX_GRAMS) if str(x or "").strip() else 0.0 for x in (p, c, f)]
    if None in macros:
        return None, "Protéines, glucides et lipides : des grammes, 0 ou plus."
    k = nombre(kcal, 10 * MAX_GRAMS) if str(kcal or "").strip() else None
    if str(kcal or "").strip() and k is None:
        return None, "Calories : un nombre, 0 ou plus."
    if k is None:
        k = 4 * macros[0] + 4 * macros[1] + 9 * macros[2]
    r = 100 / pour
    brut = {"n": nom, "k": round(k * r, 1), "p": round(macros[0] * r, 1),
            "c": round(macros[1] * r, 1), "f": round(macros[2] * r, 1)}
    faute = _invraisemblable(brut)
    if faute:
        return None, f"Ces valeurs font {faute} : vérifie l'étiquette et le poids."
    portion = nom_propre(portion)[:30]
    unites = []
    if round(pour) != 100:
        unites.append([portion or "1 portion", int(round(pour))])
    elif portion:
        unites.append([portion, 100])
    unites.append(["100 g", 100])
    return aliment_propre({**brut, "u": unites}), ""


def recette(nom, ingredients, parts, poids_cuit=None) -> tuple:
    """(aliment pour 100 g, détail, erreur). Le détail garde les ingrédients
    pour pouvoir rouvrir la recette : {ingredients, parts, poids_cuit,
    poids_cru}. Les valeurs sont recalculées ICI, pas reprises du navigateur."""
    nom = nom_propre(nom)
    if not nom:
        return None, None, "Donne un nom à ta recette."
    items = []
    for it in (ingredients if isinstance(ingredients, list) else [])[:MAX_INGREDIENTS]:
        food = aliment_propre(it)
        g = nombre((it or {}).get("grams"), MAX_GRAMS) if isinstance(it, dict) else None
        if food and g and g >= 1:
            items.append({**food, "grams": round(g, 1)})
    if not items:
        return None, None, "Ajoute au moins un ingrédient, avec sa quantité."
    n = nombre(parts, MAX_PARTS)
    if not n or n < 1 or n != int(n):
        return None, None, f"Nombre de parts : un entier de 1 à {MAX_PARTS}."
    n = int(n)
    cru = round(sum(i["grams"] for i in items), 1)
    cuit = nombre(poids_cuit, MAX_POIDS_RECETTE) if str(poids_cuit or "").strip() else None
    if str(poids_cuit or "").strip() and (cuit is None or cuit < 1):
        return None, None, "Poids cuit : en grammes, 20 kg au plus — ou laisse vide."
    base = cuit or cru
    total = {k: sum(i[k] * i["grams"] / 100 for i in items) for k in ("k", "p", "c", "f")}
    food = {"n": nom, **{k: round(v * 100 / base, 1) for k, v in total.items()}}
    faute = _invraisemblable(food)
    if faute:
        return None, None, (f"Avec ce poids cuit, le plat ferait {faute} : "
                            "pèse le plat entier, sans la casserole.")
    part = base / n
    if part > MAX_GRAMS:
        return None, None, "Une part dépasse 3 kg : indique en combien de parts tu la manges."
    # Arrondi « au-dessus à partir de ,5 », comme l'éditeur (Math.round) :
    # round() de Python donnerait 412 g là où l'écran a montré 413.
    food["u"] = [[LIBELLE_PART, max(1, math.floor(part + 0.5))]] + ([["100 g", 100]] if cuit else [])
    detail = {"ingredients": items, "parts": n, "poids_cuit": round(cuit, 1) if cuit else None,
              "poids_cru": cru}
    return aliment_propre(food), detail, ""


def doublon(nom: str, existants, sauf=None) -> bool:
    """Un autre de mes aliments porte-t-il déjà ce nom (casse ignorée) ?"""
    cle = _cle(nom)
    return any(_cle(r.get("nom")) == cle and r.get("id") != sauf for r in existants or [])


def par_part(food: dict) -> dict:
    """Ce que pèse et apporte une part (ou la première portion)."""
    lbl, g = (food.get("u") or [["100 g", 100]])[0]
    r = g / 100
    return {"libelle": lbl, "grams": g, "kcal": int(round(food["k"] * r)),
            "p": int(round(food["p"] * r)), "c": int(round(food["c"] * r)),
            "f": int(round(food["f"] * r))}


def pour_la_recherche(rows) -> list[dict]:
    """Mes aliments au format de la recherche du repas (nutrition.js) : en
    tête de liste (rang −2), avec leur étiquette."""
    out = []
    for r in rows or []:
        food = aliment_propre(r.get("food"))
        if not food or not food.get("u"):
            continue
        out.append({**food, "g": "Ma recette" if r.get("recette") else "Mon aliment",
                    "r": -2, "perso": r.get("id")})
    return out


def rafraichir_recents(recents, perso) -> list[dict]:
    """Un récent qui porte le nom d'un de mes aliments prend ses valeurs
    actuelles (la recette a pu être corrigée depuis) ; la quantité de la
    dernière fois reste proposée en premier."""
    par_nom = {_cle(f["n"]): f for f in perso or []}
    out = []
    for r in recents or []:
        f = par_nom.get(_cle(r.get("n"))) if not r.get("code") else None
        if f:
            derniere = [u for u in r.get("u") or [] if u[0] == "comme la dernière fois"]
            r = {**r, **{k: f[k] for k in ("k", "p", "c", "f")},
                 "u": derniere + [list(u) for u in f["u"]], "g": f["g"], "r": -2,
                 "perso": f["perso"]}
        out.append(r)
    return out
