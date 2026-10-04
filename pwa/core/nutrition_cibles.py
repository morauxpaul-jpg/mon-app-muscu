"""Objectifs nutritionnels : calories, macros, et le jour d'entraînement.

Jusqu'ici les macros étaient trois pourcentages de la cible calorique, et la
cible la même tous les jours (audit du 03/10, nutrition à 5) :

* 30 % de protéines à 2 000 kcal font 150 g, à 3 200 kcal 240 g : la dose
  dépendait des calories, pas du corps qui les utilise. On part désormais du
  poids — 1,8 g/kg (2,2 g/kg en sèche, pour préserver le muscle en déficit),
  plafonnés à 40 % des calories pour un gros gabarit. Les lipides restent à
  25 % (jamais sous 0,7 g/kg), les glucides prennent le reste.
* Un jour de jambes ne demande pas la même chose qu'un dimanche au canapé.
  Les jours d'entraînement reçoivent plus de glucides, les jours de repos
  moins, pour une moyenne de la semaine inchangée : l'écart entre les deux
  vaut 15 % de la cible, réparti selon le nombre de séances. Protéines et
  lipides ne bougent pas. Désactivable dans le profil (`_nutrition.cycle`).

Jour d'entraînement = séance prévue au planning, ou séance faite ce jour-là
(une séance hors planning compte aussi).
"""
from datetime import date, timedelta

ACTIVITE_FACTOR = {
    "sedentaire": 1.2,
    "leger": 1.375,
    "actif": 1.55,
    "tres_actif": 1.725,
    "athlete": 1.9,
}
AJUSTEMENT_OBJECTIF = {"masse": 400, "maintien": 0, "seche": -400}

KCAL_PER_G = {"protein": 4, "carbs": 4, "fat": 9}
PROT_G_KG = {"masse": 1.8, "maintien": 1.8, "seche": 2.2}
PROT_MAX_PART = 0.40
FAT_PART = 0.25
FAT_MIN_G_KG = 0.7

CYCLE_ECART = 0.15      # écart entraînement − repos, en part de la cible


def _bmr(poids_kg, taille_cm, age, sexe):
    """Mifflin-St Jeor."""
    base = 10 * poids_kg + 6.25 * taille_cm - 5 * age
    return base + 5 if sexe == "H" else base - 161


def custom_cal(prog) -> int:
    """Cible calorique manuelle de l'user (0 = auto). Stockée dans `prog`
    (JSONB, sans migration Supabase) et non dans la table `profiles`."""
    try:
        return max(0, min(10000, int(((prog or {}).get("_nutrition") or {}).get("calories_custom") or 0)))
    except (TypeError, ValueError):
        return 0


def cycle_actif(prog) -> bool:
    """Cible modulée selon l'entraînement ? Oui par défaut."""
    return ((prog or {}).get("_nutrition") or {}).get("cycle", True) is not False


def repartir(calories: float, poids: float, objectif: str) -> dict:
    """Grammes de protéines, glucides, lipides pour une cible donnée."""
    prot = min(PROT_G_KG.get(objectif, 1.8) * poids, PROT_MAX_PART * calories / 4)
    fat = max(FAT_PART * calories / 9, FAT_MIN_G_KG * poids)
    carbs = max(0.0, (calories - 4 * prot - 9 * fat) / 4)
    return {"protein": int(round(prot)), "carbs": int(round(carbs)), "fat": int(round(fat))}


def _pourcentages(macros_g: dict, calories: float) -> dict:
    if calories <= 0:
        return {"protein": 0, "carbs": 0, "fat": 0}
    return {k: int(round(macros_g[k] * KCAL_PER_G[k] * 100 / calories)) for k in macros_g}


def compute_targets(profile, custom=0):
    """dict(bmr, tdee, calories_cible, calories_auto, is_custom, macros_g,
    macros_pct, objectif, poids) ou None si le profil est incomplet."""
    try:
        poids = float(profile.get("poids_kg") or 0)
        taille = float(profile.get("taille_cm") or 0)
        age = int(profile.get("age") or 0)
    except (TypeError, ValueError):
        return None
    sexe = (profile.get("sexe") or "").strip().upper()
    activite = (profile.get("activite") or "").strip()
    objectif = (profile.get("objectif_nutrition") or "maintien").strip()
    if objectif not in AJUSTEMENT_OBJECTIF:
        objectif = "maintien"
    if poids <= 0 or taille <= 0 or age <= 0 or sexe not in ("H", "F") or activite not in ACTIVITE_FACTOR:
        return None

    bmr = _bmr(poids, taille, age, sexe)
    tdee = bmr * ACTIVITE_FACTOR[activite]
    cible_auto = int(round(tdee + AJUSTEMENT_OBJECTIF[objectif]))
    # Cible manuelle (ex. un plan de rééquilibrage à 2 400) : elle PRIME sur
    # le calcul, les macros se répartissent dessus.
    is_custom = custom > 0
    cible = custom if is_custom else cible_auto
    macros_g = repartir(cible, poids, objectif)
    return {
        "bmr": int(round(bmr)),
        "tdee": int(round(tdee)),
        "calories_cible": int(round(cible)),
        "calories_auto": cible_auto,
        "is_custom": is_custom,
        "macros_g": macros_g,
        "macros_pct": _pourcentages(macros_g, cible),
        "objectif": objectif,
        "poids": poids,
    }


# ── Jours d'entraînement ─────────────────────────────────────────

def jours_seances(hist) -> set:
    """Dates (ISO) où au moins une série de muscu ou de cardio a été notée."""
    out = set()
    for r in hist or []:
        d = str(r.get("Date") or "")[:10]
        exo = str(r.get("Exercice") or "")
        if d and exo != "SESSION" and (int(r.get("Reps") or 0) > 0 or exo.startswith("CARDIO:")):
            out.add(d)
    return out


def seances_par_semaine(prog, faits: set, aujourd_hui: date) -> int:
    """Séances par semaine : celles du planning, sinon la moyenne des quatre
    dernières semaines complètes (un carnet sans planning s'entraîne aussi)."""
    planning = (prog or {}).get("_planning") or {}
    n = sum(1 for v in planning.values() if v)
    if n:
        return min(n, 7)
    lundi = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    debut = (lundi - timedelta(days=28)).isoformat()
    fin = (lundi - timedelta(days=1)).isoformat()
    recents = sum(1 for d in faits if debut <= d <= fin)
    return min(7, int(round(recents / 4)))


def est_jour_entrainement(prog, faits: set, d: date) -> bool:
    from core.rotation import seance_prevue
    return d.isoformat() in faits or bool(seance_prevue(prog, d))


def cible_du_jour(targets, seances_semaine: int, entrainement: bool, actif: bool = True) -> dict:
    """Cible du jour : {calories, macros_g, jour ('entrainement'|'repos'|''),
    ecart (kcal, signé)}. Sans modulation (désactivée, 0 ou 7 séances par
    semaine), la cible de base."""
    base = targets["calories_cible"]
    n = int(seances_semaine or 0)
    if not actif or n <= 0 or n >= 7:
        return {"calories": base, "macros_g": dict(targets["macros_g"]), "jour": "", "ecart": 0}
    # n jours à +a, (7 − n) jours à −b, avec n·a = (7 − n)·b et a + b = écart.
    total = CYCLE_ECART * base
    ecart = total * (7 - n) / 7 if entrainement else -total * n / 7
    ecart = int(round(ecart / 10) * 10)
    macros = dict(targets["macros_g"])
    # Tout l'écart passe par les glucides ; un jour de repos ne les fait
    # jamais passer sous zéro (cible très basse et gros gabarit).
    carbs = max(0, macros["carbs"] + int(round(ecart / 4)))
    ecart = (carbs - macros["carbs"]) * 4
    macros["carbs"] = carbs
    return {"calories": base + ecart, "macros_g": macros,
            "jour": "entrainement" if entrainement else "repos", "ecart": ecart}


def cible_pour(profile, prog, hist, d: date):
    """(targets, cible du jour) pour la date `d`, ou (None, None) si le
    profil nutritionnel est incomplet. Seule porte d'entrée des pages."""
    targets = compute_targets(profile or {}, custom_cal(prog))
    if not targets:
        return None, None
    faits = jours_seances(hist)
    jour = cible_du_jour(targets, seances_par_semaine(prog, faits, d),
                         est_jour_entrainement(prog, faits, d), cycle_actif(prog))
    return targets, jour
