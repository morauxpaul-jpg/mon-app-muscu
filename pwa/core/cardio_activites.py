"""Les activités cardio : liste, MET, unités kilométriques, calories.

Ces constantes et formules vivaient dans `routes/cardio.py`, un blueprint
que quatre autres routes (accueil, séance, progrès, générateur) importaient
pour s'en servir : un module de calcul déguisé en blueprint, noté comme
dette dans tests/test_couche_seance.py. Elles vivent ici ; `routes/cardio.py`
les réimporte sous les mêmes noms.
"""


ACTIVITES = [
    ("Course", "footprints", 10.0),      # MET ≈ 10 (course 10 km/h)
    ("Vélo", "activity", 7.5),
    ("Rameur", "activity", 7.0),
    ("Natation", "activity", 8.0),
    ("Corde", "activity", 11.0),
    ("HIIT", "flame", 9.0),
    ("Marche", "footprints", 3.5),
    ("Elliptique", "activity", 6.5),
    ("Montée d'escaliers", "activity", 8.0),
    ("Autre", "heart", 6.0),
]
ACTIVITES_MAP = {name: (icon, met) for name, icon, met in ACTIVITES}

# Activités dont la valeur "Poids" (stockée) s'interprète comme des km.
# Les autres (Corde = sauts, HIIT = rounds, Montée d'escaliers = marches)
# ne doivent pas être additionnées dans un total kilométrique.
KM_BASED_ACTIVITES = {"Course", "Vélo", "Rameur", "Natation", "Marche", "Elliptique", "Autre"}


def _activity_of(row):
    exo = str(row.get("Exercice") or "")
    return exo.split(":", 1)[1] if ":" in exo else "Autre"


def sum_cardio_km(cardio_rows):
    """Somme la distance en km uniquement pour les activités dont l'unité est le km."""
    return round(sum(
        float(r.get("Poids") or 0)
        for r in cardio_rows
        if _activity_of(r) in KM_BASED_ACTIVITES
    ), 2)

RPE_LABELS = ["Facile", "Modéré", "Intense"]


INCLINE_MET_BONUS = {
    "Marche": 0.35,
    "Course": 0.5,
}


def _adjust_met_for_incline(met, activite, incline_pct):
    """Ajuste le MET en fonction de l'inclinaison (%) pour marche/course."""
    bonus = INCLINE_MET_BONUS.get(activite, 0)
    if bonus and incline_pct > 0:
        return met + (incline_pct * bonus)
    return met


def _estimate_calories(met, minutes, poids_kg):
    """Formule standard : kcal = MET × poids(kg) × temps(h)."""
    if not poids_kg or poids_kg <= 0:
        poids_kg = 70.0
    return int(round(met * poids_kg * (minutes / 60.0)))
