"""Le rythme réel, lu sur la balance, face au rythme visé.

La cible de calories est une estimation (Mifflin-St Jeor × activité,
core/nutrition_cibles.py) : elle peut se tromper de plusieurs centaines de
kcal. La balance, elle, dit ce qui se passe. Sur les six dernières semaines,
la pente des pesées (moindres carrés : une pesée isolée ne fait pas la
tendance) donne le rythme réel en kg par semaine, comparé à la fourchette
conseillée pour l'objectif, en part du poids de corps :

* sèche : perdre 0,5 à 1 % par semaine (Helms, Aragon et Fitschen, 2014) ;
* prise de masse : prendre 0,25 à 0,5 % par semaine (Iraki et al., 2019) ;
* maintien : rester à ±0,25 % par semaine.

Hors fourchette, une nouvelle cible est PROPOSÉE, jamais appliquée seule :
le plus petit changement qui ramène dans la fourchette, à environ 7 700 kcal
par kilo, arrondi à 50 kcal et plafonné à 300 kcal par jour — un pas à la
fois. Après un ajustement, deux semaines sans nouvelle proposition : le
poids met ce temps à répondre. Jamais sous le métabolisme de base.

Pas assez de pesées (3 au moins, sur 14 jours au moins) : on dit ce qui
manque plutôt que d'inventer une tendance.
"""
from datetime import date, timedelta

FENETRE_JOURS = 42
PESEES_MIN = 3
DUREE_MIN_JOURS = 14
KCAL_PAR_KG = 7700
PAS_MAX = 300
ARRONDI = 50
ATTENTE_JOURS = 14
# % du poids de corps par semaine (bas, haut).
FOURCHETTES = {"seche": (-1.0, -0.5), "masse": (0.25, 0.5), "maintien": (-0.25, 0.25)}


def _jour(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def pente_par_jour(points) -> float:
    """Moindres carrés sur (jour, kg) : kg gagnés (+) ou perdus (−) par jour."""
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _ in points)
    return sum((x - mx) * (y - my) for x, y in points) / sxx if sxx else 0.0


def rythme(pesees, objectif: str, aujourdhui: date, cible: int, bmr: int = 0,
           ajuste_le=None) -> dict:
    """Le rythme des six dernières semaines et, s'il le faut, une cible
    proposée. `etat` : « manque » (pas assez de pesées), « dans_la_cible »,
    « en_dessous » ou « au_dessus » (de la fourchette, en kg par semaine)."""
    debut = aujourdhui - timedelta(days=FENETRE_JOURS)
    vues = sorted((d, float(p["poids_kg"])) for p in pesees or []
                  if (d := _jour(p.get("date"))) and debut <= d <= aujourdhui
                  and float(p.get("poids_kg") or 0) > 0)
    duree = (vues[-1][0] - vues[0][0]).days if vues else 0
    base = {"pesees": len(vues), "jours": duree, "fenetre_semaines": FENETRE_JOURS // 7,
            "pesees_min": PESEES_MIN, "duree_min_semaines": DUREE_MIN_JOURS // 7}
    if len(vues) < PESEES_MIN or duree < DUREE_MIN_JOURS:
        return {**base, "etat": "manque"}

    kg_semaine = pente_par_jour([((d - vues[0][0]).days, kg) for d, kg in vues]) * 7
    poids = sum(kg for _, kg in vues) / len(vues)
    bas, haut = FOURCHETTES.get(objectif, FOURCHETTES["maintien"])
    bas_kg, haut_kg = bas * poids / 100, haut * poids / 100
    out = {**base, "etat": "dans_la_cible", "kg_semaine": round(kg_semaine, 2),
           "pct_semaine": round(kg_semaine / poids * 100, 2),
           "fourchette_kg": (round(bas_kg, 2), round(haut_kg, 2)), "proposition": None}
    if bas_kg <= kg_semaine <= haut_kg:
        return out

    # Le plus petit écart qui ramène dans la fourchette : vers la borne la
    # plus proche. Trop lent en sèche (au-dessus de −0,5 %) → manger moins.
    borne = bas_kg if kg_semaine < bas_kg else haut_kg
    out["etat"] = "en_dessous" if kg_semaine < bas_kg else "au_dessus"
    ecart = (borne - kg_semaine) * KCAL_PAR_KG / 7
    pas = max(-PAS_MAX, min(PAS_MAX, int(round(ecart / ARRONDI)) * ARRONDI))
    if not pas:
        out["etat"] = "dans_la_cible"         # écart sous 25 kcal par jour
        return out
    ajuste = _jour(ajuste_le) if ajuste_le else None
    if ajuste and (aujourdhui - ajuste).days < ATTENTE_JOURS:
        out["attente_jusquau"] = (ajuste + timedelta(days=ATTENTE_JOURS)).isoformat()
        return out
    nouvelle = int(cible) + pas
    plancher = -(-int(bmr or 0) // ARRONDI) * ARRONDI      # BMR, arrondi au-dessus
    if pas < 0 and nouvelle < plancher:
        nouvelle = plancher
        if nouvelle >= int(cible):
            out["plancher"] = True            # déjà au métabolisme de base
            return out
    out["proposition"] = {"cible": nouvelle, "ecart": nouvelle - int(cible)}
    return out


OBJECTIFS = {"seche": "En sèche", "masse": "En prise de masse", "maintien": "Au maintien"}


def _kg(x: float) -> str:
    return f"{abs(x):.2f}".replace(".", ",")


def phrases(r: dict, objectif: str) -> dict:
    """Ce que la carte dit : le constat, ce qui est visé, le verdict."""
    if r.get("etat") == "manque":
        return {}
    kg, etat = r["kg_semaine"], r["etat"]
    if abs(kg) < 0.05:
        constat = "ton poids est stable"
    else:
        constat = f"tu {'perds' if kg < 0 else 'prends'} {_kg(kg)} kg par semaine"
    bas, haut = r["fourchette_kg"]
    objectif = objectif if objectif in OBJECTIFS else "maintien"
    vise = {"seche": f"perdre {_kg(haut)} à {_kg(bas)} kg par semaine",
            "masse": f"prendre {_kg(bas)} à {_kg(haut)} kg par semaine",
            "maintien": f"rester entre −{_kg(bas)} et +{_kg(haut)} kg par semaine"}[objectif]
    verdicts = {
        ("seche", "au_dessus"): ("Tu perds moins vite que conseillé." if kg < 0
                                 else "Tu ne perds pas de poids."),
        ("seche", "en_dessous"): "Tu perds plus vite que conseillé : le muscle risque d'y passer.",
        ("masse", "en_dessous"): ("Tu prends moins vite que conseillé." if kg > 0
                                  else "Tu ne prends pas de poids."),
        ("masse", "au_dessus"): "Tu prends plus vite que conseillé : le surplus part surtout en gras.",
        ("maintien", "en_dessous"): "Tu perds du poids.",
        ("maintien", "au_dessus"): "Tu prends du poids.",
    }
    verdict = verdicts.get((objectif, etat), "Tu es dans la fourchette : garde ta cible.")
    return {"constat": constat, "vise": f"{OBJECTIFS[objectif]}, le conseil : {vise}",
            "verdict": verdict}
