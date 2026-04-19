"""Catalogue de programmes prédéfinis pour l'onboarding (Phase 4).

Chaque programme est un dict {seance_name: [exos]} compatible avec le format
`programs.data` existant. Les exos suivent la structure utilisée dans
routes/programme.py : {"name": str, "sets": int, "muscle": str}.

Les reps ne sont PAS stockées (cf CONTEXT.md point 5) — elles sont juste
affichées à titre indicatif dans l'UI onboarding via le champ `reps_hint`.
"""
from copy import deepcopy
from core.dates import DAYS_FR


# ── Planning auto selon la fréquence ─────────────────────────────────
_PLANNING_BY_FREQ = {
    2: ["Lundi", "Jeudi"],
    3: ["Lundi", "Mercredi", "Vendredi"],
    4: ["Lundi", "Mardi", "Jeudi", "Vendredi"],
    5: ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"],
    6: ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"],
}


def planning_for(freq: int, seance_names: list[str]) -> dict:
    """Retourne un dict {jour_fr: nom_seance} (vide = repos), en répartissant
    les séances de façon cyclique sur les jours d'entraînement."""
    freq = max(2, min(6, int(freq or 3)))
    days = _PLANNING_BY_FREQ[freq]
    planning = {d: "" for d in DAYS_FR}
    if not seance_names:
        return planning
    for i, d in enumerate(days):
        planning[d] = seance_names[i % len(seance_names)]
    return planning


# ── Exercices d'un programme (format dict) ───────────────────────────
def _ex(name, sets, muscle, reps_hint="8-12"):
    return {"name": name, "sets": sets, "muscle": muscle, "_reps_hint": reps_hint}


# ── Catalogue ────────────────────────────────────────────────────────
CATALOG = {

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  DÉBUTANT (moins de 6 mois)                                ║
    # ╚══════════════════════════════════════════════════════════════╝

    "fb_deb_3j": {
        "id": "fb_deb_3j",
        "title": "Full Body Débutant — Salle",
        "subtitle": "3 séances / semaine · corps entier · salle",
        "freq": 3,
        "level": "débutant",
        "tags": ["débutant", "salle", "tous"],
        "description": "Le meilleur choix pour démarrer : 2 séances alternées (A/B) qui travaillent tout le corps. Progression rapide sur les bases.",
        "explanation": "Tout le corps à chaque séance — idéal pour commencer et progresser vite",
        "difficulty": 1,
        "duration": "~60 min",
        "icon": "🏋️",
        "seances": {
            "Full Body A": [
                _ex("Squat", 3, "Quadriceps,Fessiers", "12"),
                _ex("Développé couché", 3, "Pecs,Triceps", "12"),
                _ex("Rowing barre", 3, "Dos,Biceps", "12"),
                _ex("Développé militaire haltères", 3, "Épaules,Triceps", "12"),
                _ex("Curl biceps", 3, "Biceps", "12"),
                _ex("Extensions triceps poulie", 3, "Triceps", "12"),
            ],
            "Full Body B": [
                _ex("Presse à cuisses", 3, "Quadriceps,Fessiers", "12"),
                _ex("Développé incliné haltères", 3, "Pecs,Épaules", "12"),
                _ex("Tirage vertical", 3, "Dos,Biceps", "12"),
                _ex("Élévations latérales", 3, "Épaules", "12"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "12"),
                _ex("Dips machine", 3, "Triceps,Pecs", "12"),
            ],
        },
    },

    "fb_deb_maison_3j": {
        "id": "fb_deb_maison_3j",
        "title": "Full Body Débutant — Maison",
        "subtitle": "3 séances / semaine · haltères · maison",
        "freq": 3,
        "level": "débutant",
        "tags": ["débutant", "maison", "haltères", "tous"],
        "description": "Programme maison avec haltères : 2 séances alternées couvrant tout le corps. Parfait pour démarrer chez soi.",
        "explanation": "Tout le corps avec haltères — s'entraîner chez soi et progresser",
        "difficulty": 1,
        "duration": "~45 min",
        "icon": "🏠",
        "seances": {
            "Maison A": [
                _ex("Squat gobelet", 3, "Quadriceps,Fessiers", "12-15"),
                _ex("Pompes", 3, "Pecs,Triceps", "12-15"),
                _ex("Rowing haltère", 3, "Dos,Biceps", "12-15"),
                _ex("Développé haltères assis", 3, "Épaules,Triceps", "12-15"),
                _ex("Curl haltères", 3, "Biceps", "12-15"),
                _ex("Extension triceps haltère", 3, "Triceps", "12-15"),
            ],
            "Maison B": [
                _ex("Fentes haltères", 3, "Quadriceps,Fessiers", "12-15"),
                _ex("Floor press haltères", 3, "Pecs,Triceps", "12-15"),
                _ex("Tirage élastique", 3, "Dos,Biceps", "12-15"),
                _ex("Élévations latérales haltères", 3, "Épaules", "12-15"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "12-15"),
                _ex("Kickback triceps", 3, "Triceps", "12-15"),
            ],
        },
    },

    "fb_pdc_3j": {
        "id": "fb_pdc_3j",
        "title": "Full Body Poids du Corps",
        "subtitle": "3 séances / semaine · aucun équipement",
        "freq": 3,
        "level": "débutant",
        "tags": ["débutant", "poids du corps", "maison", "forme générale"],
        "description": "Zéro matériel requis : corps et motivation suffisent. 2 circuits alternés pour travailler tout le corps.",
        "explanation": "Rien que ton corps — parfait pour commencer sans équipement",
        "difficulty": 1,
        "duration": "~40 min",
        "icon": "🤸",
        "seances": {
            "PDC A": [
                _ex("Squats", 3, "Quadriceps,Fessiers", "15-20"),
                _ex("Pompes", 3, "Pecs,Triceps", "max"),
                _ex("Tractions australiennes", 3, "Dos,Biceps", "10-15"),
                _ex("Pike push-ups", 3, "Épaules,Triceps", "10-15"),
                _ex("Gainage", 3, "Abdos", "30-60s"),
                _ex("Mountain climbers", 3, "Abdos", "30-45s"),
            ],
            "PDC B": [
                _ex("Fentes", 3, "Quadriceps,Fessiers", "15-20"),
                _ex("Pompes diamant", 3, "Triceps,Pecs", "max"),
                _ex("Rowing inversé", 3, "Dos,Biceps", "10-15"),
                _ex("Dips sur chaise", 3, "Triceps,Pecs", "10-15"),
                _ex("Gainage latéral", 3, "Abdos", "30-45s"),
                _ex("Burpees", 3, "Quadriceps,Abdos", "10-15"),
            ],
        },
    },

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  INTERMÉDIAIRE (6 mois à 2 ans)                            ║
    # ╚══════════════════════════════════════════════════════════════╝

    "upper_lower_4j": {
        "id": "upper_lower_4j",
        "title": "Upper / Lower — Salle",
        "subtitle": "4 séances / semaine · intermédiaire · salle",
        "freq": 4,
        "level": "intermédiaire",
        "tags": ["intermédiaire", "salle", "masse", "force"],
        "description": "2 haut + 2 bas du corps par semaine. Excellent compromis volume / récupération pour progresser.",
        "explanation": "Alternance haut du corps / bas du corps — équilibre et récupération optimale",
        "difficulty": 2,
        "duration": "~65 min",
        "icon": "↕️",
        "seances": {
            "Upper A": [
                _ex("Développé couché", 4, "Pecs,Triceps", "8"),
                _ex("Rowing barre", 4, "Dos,Biceps", "8"),
                _ex("Développé militaire", 3, "Épaules,Triceps", "10"),
                _ex("Tirage vertical", 3, "Dos,Biceps", "10"),
                _ex("Curl biceps", 3, "Biceps", "12"),
                _ex("Extensions triceps poulie", 3, "Triceps", "12"),
            ],
            "Lower A": [
                _ex("Squat", 4, "Quadriceps,Fessiers", "6"),
                _ex("Soulevé de terre roumain", 3, "Ischio-jambiers,Fessiers", "10"),
                _ex("Presse à cuisses", 3, "Quadriceps,Fessiers", "10"),
                _ex("Leg curl", 3, "Ischio-jambiers", "12"),
                _ex("Mollets debout", 4, "Mollets", "15"),
            ],
            "Upper B": [
                _ex("Développé incliné haltères", 4, "Pecs,Épaules", "10"),
                _ex("Rowing haltère", 4, "Dos,Biceps", "10"),
                _ex("Élévations latérales", 3, "Épaules", "15"),
                _ex("Face pull", 3, "Épaules,Dos", "15"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "12"),
                _ex("Dips", 3, "Triceps,Pecs", "10"),
            ],
            "Lower B": [
                _ex("Front squat", 4, "Quadriceps,Fessiers", "8"),
                _ex("Hip thrust", 3, "Fessiers", "12"),
                _ex("Fentes marchées", 3, "Quadriceps,Fessiers", "10"),
                _ex("Leg extension", 3, "Quadriceps", "12"),
                _ex("Mollets assis", 4, "Mollets", "15"),
            ],
        },
    },

    "upper_lower_maison_4j": {
        "id": "upper_lower_maison_4j",
        "title": "Upper / Lower — Maison",
        "subtitle": "4 séances / semaine · haltères · maison",
        "freq": 4,
        "level": "intermédiaire",
        "tags": ["intermédiaire", "maison", "haltères", "masse"],
        "description": "Programme upper/lower avec haltères uniquement. Idéal pour progresser chez soi avec du matériel minimal.",
        "explanation": "Haut / bas du corps en alternance — haltères seulement",
        "difficulty": 2,
        "duration": "~50 min",
        "icon": "🏠",
        "seances": {
            "Upper A": [
                _ex("Floor press haltères", 4, "Pecs,Triceps", "10"),
                _ex("Rowing haltère", 4, "Dos,Biceps", "10"),
                _ex("Développé haltères", 3, "Épaules,Triceps", "10"),
                _ex("Curl haltères", 3, "Biceps", "12"),
                _ex("Extension triceps haltère", 3, "Triceps", "12"),
            ],
            "Lower A": [
                _ex("Squat gobelet", 4, "Quadriceps,Fessiers", "12"),
                _ex("Soulevé de terre roumain haltères", 3, "Ischio-jambiers,Fessiers", "10"),
                _ex("Fentes haltères", 3, "Quadriceps,Fessiers", "10"),
                _ex("Mollets debout", 4, "Mollets", "15"),
            ],
            "Upper B": [
                _ex("Pompes lestées", 4, "Pecs,Triceps", "max"),
                _ex("Rowing unilatéral haltère", 4, "Dos,Biceps", "10"),
                _ex("Élévations latérales haltères", 3, "Épaules", "15"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "12"),
                _ex("Kickback triceps", 3, "Triceps", "12"),
            ],
            "Lower B": [
                _ex("Squat bulgare", 4, "Quadriceps,Fessiers", "10"),
                _ex("Hip thrust", 3, "Fessiers,Ischio-jambiers", "12"),
                _ex("Fentes latérales", 3, "Quadriceps,Fessiers", "12"),
                _ex("Mollets unilatéral", 4, "Mollets", "15"),
            ],
        },
    },

    "ppl_6j": {
        "id": "ppl_6j",
        "title": "Push / Pull / Legs 6j — Salle",
        "subtitle": "6 séances / semaine · intermédiaire · salle",
        "freq": 6,
        "level": "intermédiaire",
        "tags": ["intermédiaire", "salle", "masse", "hypertrophie"],
        "description": "Le grand classique PPL : 2 cycles push/pull/legs par semaine. Volume élevé, idéal pour l'hypertrophie.",
        "explanation": "Push (pousser) / Pull (tirer) / Legs (jambes) × 2 par semaine",
        "difficulty": 3,
        "duration": "~75 min",
        "icon": "🔄",
        "seances": {
            "Push": [
                _ex("Développé couché", 4, "Pecs,Triceps", "8"),
                _ex("Développé incliné haltères", 3, "Pecs,Épaules", "10"),
                _ex("Développé militaire", 3, "Épaules,Triceps", "10"),
                _ex("Élévations latérales", 3, "Épaules", "15"),
                _ex("Extensions triceps poulie", 3, "Triceps", "12"),
                _ex("Dips", 3, "Triceps,Pecs", "10"),
            ],
            "Pull": [
                _ex("Tractions", 4, "Dos,Biceps", "8"),
                _ex("Rowing barre", 4, "Dos,Biceps", "8"),
                _ex("Tirage vertical prise serrée", 3, "Dos,Biceps", "10"),
                _ex("Face pull", 3, "Épaules,Dos", "15"),
                _ex("Curl barre", 3, "Biceps", "10"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "12"),
            ],
            "Legs": [
                _ex("Squat", 4, "Quadriceps,Fessiers", "6"),
                _ex("Presse à cuisses", 3, "Quadriceps,Fessiers", "10"),
                _ex("Leg curl", 3, "Ischio-jambiers", "12"),
                _ex("Leg extension", 3, "Quadriceps", "12"),
                _ex("Fentes", 3, "Quadriceps,Fessiers", "10"),
                _ex("Mollets debout", 4, "Mollets", "15"),
            ],
        },
    },

    "ppl_5j": {
        "id": "ppl_5j",
        "title": "Push / Pull / Legs 5j — Salle",
        "subtitle": "5 séances / semaine · intermédiaire · salle",
        "freq": 5,
        "level": "intermédiaire",
        "tags": ["intermédiaire", "salle", "masse", "hypertrophie"],
        "description": "PPL en rotation sur 5 jours : Sem 1 Push/Pull/Legs/Push/Pull, Sem 2 Legs/Push/Pull/Legs/Push, etc.",
        "explanation": "Le même PPL mais sur 5 jours — chaque muscle 1.5× par semaine",
        "difficulty": 3,
        "duration": "~70 min",
        "icon": "🔄",
        "seances": {
            "Push": [
                _ex("Développé couché", 4, "Pecs,Triceps", "8"),
                _ex("Développé incliné haltères", 3, "Pecs,Épaules", "10"),
                _ex("Développé militaire", 3, "Épaules,Triceps", "10"),
                _ex("Élévations latérales", 3, "Épaules", "15"),
                _ex("Extensions triceps poulie", 3, "Triceps", "12"),
                _ex("Dips", 3, "Triceps,Pecs", "10"),
            ],
            "Pull": [
                _ex("Tractions", 4, "Dos,Biceps", "8"),
                _ex("Rowing barre", 4, "Dos,Biceps", "8"),
                _ex("Tirage vertical prise serrée", 3, "Dos,Biceps", "10"),
                _ex("Face pull", 3, "Épaules,Dos", "15"),
                _ex("Curl barre", 3, "Biceps", "10"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "12"),
            ],
            "Legs": [
                _ex("Squat", 4, "Quadriceps,Fessiers", "6"),
                _ex("Presse à cuisses", 3, "Quadriceps,Fessiers", "10"),
                _ex("Leg curl", 3, "Ischio-jambiers", "12"),
                _ex("Leg extension", 3, "Quadriceps", "12"),
                _ex("Fentes", 3, "Quadriceps,Fessiers", "10"),
                _ex("Mollets debout", 4, "Mollets", "15"),
            ],
        },
    },

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  AVANCÉ (plus de 2 ans)                                    ║
    # ╚══════════════════════════════════════════════════════════════╝

    "ppl_avance_6j": {
        "id": "ppl_avance_6j",
        "title": "PPL Avancé 6j — Salle",
        "subtitle": "6 séances / semaine · avancé · force + hypertrophie",
        "freq": 6,
        "level": "avancé",
        "tags": ["avancé", "salle", "force", "hypertrophie"],
        "description": "PPL avec alternance force (A) et hypertrophie (B). Volume et intensité élevés pour les pratiquants confirmés.",
        "explanation": "Push/Pull/Legs en double : jour A force, jour B hypertrophie",
        "difficulty": 4,
        "duration": "~80 min",
        "icon": "🔥",
        "seances": {
            "Push A (Force)": [
                _ex("Développé couché", 5, "Pecs,Triceps", "5"),
                _ex("Développé militaire", 4, "Épaules,Triceps", "6"),
                _ex("Dips lestés", 3, "Triceps,Pecs", "8"),
                _ex("Élévations latérales", 4, "Épaules", "12"),
                _ex("Barre au front", 3, "Triceps", "10"),
            ],
            "Push B (Hypertrophie)": [
                _ex("Développé incliné haltères", 4, "Pecs,Épaules", "10"),
                _ex("Arnold press", 3, "Épaules,Triceps", "12"),
                _ex("Écartés poulie", 3, "Pecs", "15"),
                _ex("Élévations latérales", 4, "Épaules", "15"),
                _ex("Extensions triceps poulie corde", 3, "Triceps", "15"),
            ],
            "Pull A (Force)": [
                _ex("Tractions lestées", 5, "Dos,Biceps", "5"),
                _ex("Rowing barre", 4, "Dos,Biceps", "6"),
                _ex("Curl barre", 4, "Biceps", "8"),
                _ex("Face pull", 3, "Épaules,Dos", "15"),
            ],
            "Pull B (Hypertrophie)": [
                _ex("Tirage vertical", 4, "Dos,Biceps", "10"),
                _ex("Rowing haltère", 4, "Dos,Biceps", "12"),
                _ex("Curl incliné haltères", 3, "Biceps", "12"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "12"),
                _ex("Shrugs", 3, "Dos,Épaules", "15"),
            ],
            "Legs A (Force)": [
                _ex("Squat", 5, "Quadriceps,Fessiers", "5"),
                _ex("Soulevé de terre", 3, "Dos,Ischio-jambiers,Fessiers", "5"),
                _ex("Presse à cuisses", 3, "Quadriceps,Fessiers", "8"),
                _ex("Mollets debout", 4, "Mollets", "12"),
            ],
            "Legs B (Hypertrophie)": [
                _ex("Front squat", 4, "Quadriceps,Fessiers", "8"),
                _ex("Soulevé de terre roumain", 4, "Ischio-jambiers,Fessiers", "10"),
                _ex("Leg curl", 4, "Ischio-jambiers", "12"),
                _ex("Leg extension", 4, "Quadriceps", "12"),
                _ex("Fentes", 3, "Quadriceps,Fessiers", "10"),
                _ex("Mollets assis", 4, "Mollets", "15"),
            ],
        },
    },

    "upper_lower_avance_5j": {
        "id": "upper_lower_avance_5j",
        "title": "Upper / Lower Avancé 5j — Salle",
        "subtitle": "5 séances / semaine · avancé · force",
        "freq": 5,
        "level": "avancé",
        "tags": ["avancé", "salle", "force"],
        "description": "5 séances : 2 force, 2 hypertrophie, 1 mixte. Programme complet pour les avancés qui veulent progresser en force.",
        "explanation": "Alternance force / hypertrophie / mixte sur 5 jours",
        "difficulty": 4,
        "duration": "~75 min",
        "icon": "💪",
        "seances": {
            "Upper Force": [
                _ex("Développé couché", 5, "Pecs,Triceps", "3"),
                _ex("Rowing barre", 5, "Dos,Biceps", "3"),
                _ex("Développé militaire", 4, "Épaules,Triceps", "5"),
                _ex("Tractions lestées", 4, "Dos,Biceps", "5"),
            ],
            "Lower Force": [
                _ex("Squat", 5, "Quadriceps,Fessiers", "3"),
                _ex("Soulevé de terre", 5, "Dos,Ischio-jambiers,Fessiers", "3"),
                _ex("Front squat", 3, "Quadriceps,Fessiers", "5"),
            ],
            "Upper Hypertrophie": [
                _ex("Développé incliné haltères", 4, "Pecs,Épaules", "10"),
                _ex("Rowing haltère", 4, "Dos,Biceps", "10"),
                _ex("Élévations latérales", 4, "Épaules", "15"),
                _ex("Curl biceps", 3, "Biceps", "12"),
                _ex("Extensions triceps poulie", 3, "Triceps", "12"),
            ],
            "Lower Hypertrophie": [
                _ex("Squat", 4, "Quadriceps,Fessiers", "8"),
                _ex("Soulevé de terre roumain", 4, "Ischio-jambiers,Fessiers", "10"),
                _ex("Fentes", 3, "Quadriceps,Fessiers", "12"),
                _ex("Leg curl", 3, "Ischio-jambiers", "12"),
                _ex("Mollets debout", 4, "Mollets", "15"),
            ],
            "Upper Mixte": [
                _ex("Développé couché", 4, "Pecs,Triceps", "6"),
                _ex("Tractions", 4, "Dos,Biceps", "8"),
                _ex("Arnold press", 3, "Épaules,Triceps", "10"),
                _ex("Face pull", 3, "Épaules,Dos", "15"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "12"),
            ],
        },
    },

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  OBJECTIF PERTE DE POIDS / SÈCHE                          ║
    # ╚══════════════════════════════════════════════════════════════╝

    "circuit_salle_3j": {
        "id": "circuit_salle_3j",
        "title": "Circuit Training — Salle",
        "subtitle": "3 séances / semaine · perte de poids · salle",
        "freq": 3,
        "level": "débutant,intermédiaire",
        "tags": ["débutant", "intermédiaire", "salle", "perte de poids"],
        "description": "Format circuit : 4 tours, 45s par exercice, 15s repos. Brûle un max de calories tout en gardant le muscle.",
        "explanation": "Enchaînement rapide d'exercices — cardio + muscu combinés",
        "difficulty": 2,
        "duration": "~45 min",
        "icon": "🔥",
        "seances": {
            "Circuit": [
                _ex("Squat", 4, "Quadriceps,Fessiers", "45s"),
                _ex("Pompes", 4, "Pecs,Triceps", "45s"),
                _ex("Rowing machine", 4, "Dos,Biceps", "45s"),
                _ex("Fentes", 4, "Quadriceps,Fessiers", "45s"),
                _ex("Dips machine", 4, "Triceps,Pecs", "45s"),
                _ex("Presse à cuisses", 4, "Quadriceps,Fessiers", "45s"),
                _ex("Gainage", 4, "Abdos", "30s"),
            ],
        },
    },

    "circuit_maison_3j": {
        "id": "circuit_maison_3j",
        "title": "Circuit Maison — Poids du Corps",
        "subtitle": "3 séances / semaine · perte de poids · sans matériel",
        "freq": 3,
        "level": "débutant,intermédiaire",
        "tags": ["débutant", "intermédiaire", "maison", "poids du corps", "perte de poids"],
        "description": "2 circuits maison sans matériel. Intensité maximale pour brûler des calories sans bouger de chez soi.",
        "explanation": "HIIT au poids du corps — aucun matériel nécessaire",
        "difficulty": 2,
        "duration": "~35 min",
        "icon": "🏃",
        "seances": {
            "Circuit A": [
                _ex("Burpees", 4, "Quadriceps,Abdos", "45s"),
                _ex("Squats", 4, "Quadriceps,Fessiers", "45s"),
                _ex("Pompes", 4, "Pecs,Triceps", "45s"),
                _ex("Mountain climbers", 4, "Abdos", "45s"),
                _ex("Gainage", 4, "Abdos", "30s"),
                _ex("Fentes sautées", 4, "Quadriceps,Fessiers", "45s"),
            ],
            "Circuit B": [
                _ex("Jump squats", 4, "Quadriceps,Fessiers", "45s"),
                _ex("Pompes diamant", 4, "Triceps,Pecs", "45s"),
                _ex("Fentes", 4, "Quadriceps,Fessiers", "45s"),
                _ex("Gainage latéral", 4, "Abdos", "30s"),
                _ex("High knees", 4, "Quadriceps,Abdos", "45s"),
                _ex("Superman", 4, "Dos,Fessiers", "45s"),
            ],
        },
    },

    "hiit_muscu_4j": {
        "id": "hiit_muscu_4j",
        "title": "HIIT + Muscu — Salle",
        "subtitle": "4 séances / semaine · sèche · salle",
        "freq": 4,
        "level": "intermédiaire",
        "tags": ["intermédiaire", "salle", "sèche", "perte de poids"],
        "description": "Muscu classique + 10 min HIIT cardio à chaque séance. Le combo parfait pour sécher en gardant la masse.",
        "explanation": "Upper/Lower + finisher HIIT — sèche optimale",
        "difficulty": 3,
        "duration": "~55 min",
        "icon": "⚡",
        "seances": {
            "Upper + HIIT": [
                _ex("Développé couché", 3, "Pecs,Triceps", "10"),
                _ex("Rowing barre", 3, "Dos,Biceps", "10"),
                _ex("Développé militaire", 3, "Épaules,Triceps", "12"),
                _ex("Curl biceps", 3, "Biceps", "12"),
                _ex("Extensions triceps poulie", 3, "Triceps", "12"),
            ],
            "Lower + HIIT": [
                _ex("Squat", 3, "Quadriceps,Fessiers", "10"),
                _ex("Fentes", 3, "Quadriceps,Fessiers", "12"),
                _ex("Leg curl", 3, "Ischio-jambiers", "12"),
                _ex("Mollets debout", 3, "Mollets", "15"),
            ],
        },
    },

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  OBJECTIF FORCE PURE                                       ║
    # ╚══════════════════════════════════════════════════════════════╝

    "force_5x5_3j": {
        "id": "force_5x5_3j",
        "title": "5×5 Force — Salle",
        "subtitle": "3 séances / semaine · force · salle",
        "freq": 3,
        "level": "débutant,intermédiaire",
        "tags": ["débutant", "intermédiaire", "salle", "force"],
        "description": "Le programme StrongLifts 5×5 : 3 mouvements composés, 5 séries de 5 reps, alternance A/B. Simple et redoutablement efficace.",
        "explanation": "5 séries × 5 reps sur les mouvements de base — force pure",
        "difficulty": 2,
        "duration": "~45 min",
        "icon": "🏆",
        "seances": {
            "Force A": [
                _ex("Squat", 5, "Quadriceps,Fessiers", "5"),
                _ex("Développé couché", 5, "Pecs,Triceps", "5"),
                _ex("Rowing barre", 5, "Dos,Biceps", "5"),
            ],
            "Force B": [
                _ex("Squat", 5, "Quadriceps,Fessiers", "5"),
                _ex("Développé militaire", 5, "Épaules,Triceps", "5"),
                _ex("Soulevé de terre", 1, "Dos,Ischio-jambiers,Fessiers", "5"),
            ],
        },
    },

    "force_athle_4j": {
        "id": "force_athle_4j",
        "title": "Force Athlétique 4j — Salle",
        "subtitle": "4 séances / semaine · force · salle",
        "freq": 4,
        "level": "intermédiaire,avancé",
        "tags": ["intermédiaire", "avancé", "salle", "force"],
        "description": "Un jour par mouvement principal : Squat, Bench, Deadlift, OHP. Pour ceux qui veulent être forts sur les barres.",
        "explanation": "Un mouvement roi par jour — spécialisation force athlétique",
        "difficulty": 3,
        "duration": "~60 min",
        "icon": "🥇",
        "seances": {
            "Jour Squat": [
                _ex("Squat", 5, "Quadriceps,Fessiers", "3"),
                _ex("Front squat", 3, "Quadriceps,Fessiers", "5"),
                _ex("Presse à cuisses", 3, "Quadriceps,Fessiers", "8"),
            ],
            "Jour Bench": [
                _ex("Développé couché", 5, "Pecs,Triceps", "3"),
                _ex("Développé incliné haltères", 3, "Pecs,Épaules", "6"),
                _ex("Dips lestés", 3, "Triceps,Pecs", "8"),
            ],
            "Jour Deadlift": [
                _ex("Soulevé de terre", 5, "Dos,Ischio-jambiers,Fessiers", "3"),
                _ex("Soulevé de terre roumain", 3, "Ischio-jambiers,Fessiers", "6"),
                _ex("Rowing barre", 3, "Dos,Biceps", "6"),
            ],
            "Jour OHP": [
                _ex("Développé militaire", 5, "Épaules,Triceps", "3"),
                _ex("Push press", 3, "Épaules,Triceps", "5"),
                _ex("Élévations latérales", 3, "Épaules", "12"),
            ],
        },
    },

    # ╔══════════════════════════════════════════════════════════════╗
    # ║  PROGRAMMES COMPLÉMENTAIRES                                ║
    # ╚══════════════════════════════════════════════════════════════╝

    "ppl_deb_3j": {
        "id": "ppl_deb_3j",
        "title": "Push / Pull / Legs Débutant — 3j",
        "subtitle": "3 séances / semaine · push/pull/legs · salle",
        "freq": 3,
        "level": "débutant,intermédiaire",
        "tags": ["débutant", "intermédiaire", "salle", "ppl"],
        "description": "Une introduction au PPL : un jour pousser, un jour tirer, un jour jambes. Parfait pour se familiariser avec les splits avant de passer à 5/6 jours.",
        "explanation": "PPL simplifié sur 3 jours — le split le plus populaire, version accessible",
        "difficulty": 2,
        "duration": "~60 min",
        "icon": "🚀",
        "seances": {
            "Push (Pecs / Épaules / Triceps)": [
                _ex("Développé couché", 4, "Pecs,Triceps", "8-10"),
                _ex("Développé incliné haltères", 3, "Pecs,Épaules", "10-12"),
                _ex("Développé militaire haltères", 3, "Épaules,Triceps", "10-12"),
                _ex("Élévations latérales", 3, "Épaules", "12-15"),
                _ex("Extensions triceps poulie", 3, "Triceps", "12"),
            ],
            "Pull (Dos / Biceps)": [
                _ex("Tractions assistées", 4, "Dos,Biceps", "8-10"),
                _ex("Rowing barre", 4, "Dos,Biceps", "8-10"),
                _ex("Tirage vertical", 3, "Dos,Biceps", "10-12"),
                _ex("Face pull", 3, "Épaules,Dos", "15"),
                _ex("Curl biceps", 3, "Biceps", "10-12"),
            ],
            "Legs (Jambes)": [
                _ex("Squat", 4, "Quadriceps,Fessiers", "8-10"),
                _ex("Soulevé de terre roumain", 3, "Ischio-jambiers,Fessiers", "8-10"),
                _ex("Presse à cuisses", 3, "Quadriceps,Fessiers", "12"),
                _ex("Leg curl", 3, "Ischio-jambiers", "12"),
                _ex("Mollets debout", 4, "Mollets", "15"),
            ],
        },
    },

    "glutes_focus_4j": {
        "id": "glutes_focus_4j",
        "title": "Spécial Fessiers / Glutes — 4j",
        "subtitle": "4 séances / semaine · fessiers · salle",
        "freq": 4,
        "level": "intermédiaire",
        "tags": ["intermédiaire", "salle", "fessiers", "jambes"],
        "description": "Programme orienté développement des fessiers avec 2 séances Glutes et 2 séances upper-body pour équilibrer. Volume adapté pour maximiser l'hypertrophie.",
        "explanation": "Double dose de fessiers + haut du corps — volume ciblé glutes",
        "difficulty": 2,
        "duration": "~60 min",
        "icon": "🍑",
        "seances": {
            "Glutes A": [
                _ex("Hip thrust", 4, "Fessiers,Ischio-jambiers", "10-12"),
                _ex("Squat bulgare", 4, "Quadriceps,Fessiers", "10"),
                _ex("Soulevé de terre roumain", 3, "Ischio-jambiers,Fessiers", "10-12"),
                _ex("Abductions hanches", 3, "Abducteurs,Fessiers", "15"),
                _ex("Kickback poulie", 3, "Fessiers", "12"),
            ],
            "Glutes B": [
                _ex("Squat", 4, "Quadriceps,Fessiers", "8-10"),
                _ex("Fentes marchées", 3, "Quadriceps,Fessiers", "10"),
                _ex("Pont fessiers une jambe", 3, "Fessiers", "12"),
                _ex("Good morning", 3, "Ischio-jambiers,Fessiers", "10-12"),
                _ex("Mollets assis", 4, "Mollets", "15"),
            ],
            "Upper push": [
                _ex("Développé couché", 4, "Pecs,Triceps", "8-10"),
                _ex("Développé militaire haltères", 3, "Épaules,Triceps", "10"),
                _ex("Élévations latérales", 4, "Épaules", "12-15"),
                _ex("Dips machine", 3, "Triceps,Pecs", "10-12"),
            ],
            "Upper pull": [
                _ex("Tirage vertical", 4, "Dos,Biceps", "10-12"),
                _ex("Rowing haltère", 4, "Dos,Biceps", "10"),
                _ex("Face pull", 3, "Épaules,Dos", "15"),
                _ex("Curl haltères", 3, "Biceps", "10-12"),
            ],
        },
    },

    "bras_spe_4j": {
        "id": "bras_spe_4j",
        "title": "Spécialisation Bras — 4j",
        "subtitle": "4 séances / semaine · bras · salle",
        "freq": 4,
        "level": "intermédiaire,avancé",
        "tags": ["intermédiaire", "avancé", "salle", "bras"],
        "description": "Pour ceux qui veulent des bras massifs : 2 journées upper-body classiques + 2 journées dédiées biceps/triceps avec volume élevé.",
        "explanation": "2 journées spécifiques bras + haut du corps — spécialisation pure",
        "difficulty": 3,
        "duration": "~55 min",
        "icon": "💪",
        "seances": {
            "Upper A (Push)": [
                _ex("Développé couché", 4, "Pecs,Triceps", "8"),
                _ex("Développé incliné haltères", 3, "Pecs,Épaules", "10"),
                _ex("Développé militaire", 3, "Épaules,Triceps", "8"),
                _ex("Élévations latérales", 3, "Épaules", "12-15"),
            ],
            "Upper B (Pull)": [
                _ex("Tractions", 4, "Dos,Biceps", "8-10"),
                _ex("Rowing barre", 4, "Dos,Biceps", "8"),
                _ex("Tirage horizontal", 3, "Dos", "10-12"),
                _ex("Shrug barre", 3, "Trapèzes", "12"),
            ],
            "Bras volume A": [
                _ex("Curl barre EZ", 4, "Biceps", "8-10"),
                _ex("Extensions triceps poulie", 4, "Triceps", "10-12"),
                _ex("Curl incliné haltères", 3, "Biceps", "10-12"),
                _ex("Dips lestés", 3, "Triceps,Pecs", "8-10"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "12"),
                _ex("Extensions triceps haltère", 3, "Triceps", "12"),
            ],
            "Bras volume B": [
                _ex("Curl pupitre", 4, "Biceps", "10"),
                _ex("Barre au front", 4, "Triceps", "10"),
                _ex("Curl poulie basse", 3, "Biceps", "12"),
                _ex("Kickback triceps", 3, "Triceps", "12"),
                _ex("Curl concentration", 3, "Biceps", "12"),
                _ex("Corde triceps poulie", 3, "Triceps", "15"),
            ],
        },
    },

    "pdc_avance_4j": {
        "id": "pdc_avance_4j",
        "title": "Street Workout Avancé — Poids du corps",
        "subtitle": "4 séances / semaine · poids du corps · avancé",
        "freq": 4,
        "level": "avancé",
        "tags": ["avancé", "aucun", "pdc", "street"],
        "description": "Programme poids du corps avancé avec progressions vers muscle-up, handstand push-up et pistol squat. Pour ceux qui veulent devenir très forts sans matériel.",
        "explanation": "Progressions vers muscle-up / handstand / pistol — niveau street workout",
        "difficulty": 3,
        "duration": "~50 min",
        "icon": "🤸",
        "seances": {
            "Push avancé": [
                _ex("Pompes arc-en-ciel", 4, "Pecs,Triceps", "6-8"),
                _ex("Pompes en équilibre mur", 4, "Épaules,Triceps", "5-8"),
                _ex("Pompes explosives", 3, "Pecs,Triceps", "5"),
                _ex("Dips barre lestés", 3, "Triceps,Pecs", "8-10"),
                _ex("Extensions triceps mur", 3, "Triceps", "10"),
            ],
            "Pull avancé": [
                _ex("Tractions lestées", 4, "Dos,Biceps", "6-8"),
                _ex("Tractions commando", 3, "Dos,Biceps", "8-10"),
                _ex("Rowing australien pieds surélevés", 4, "Dos", "10-12"),
                _ex("Tractions tempo 3-1-3", 3, "Dos,Biceps", "5-6"),
                _ex("Curl australien", 3, "Biceps", "10"),
            ],
            "Legs avancé": [
                _ex("Pistol squat assisté", 4, "Quadriceps,Fessiers", "6-8"),
                _ex("Squat sauté", 4, "Quadriceps,Fessiers", "8"),
                _ex("Fentes bulgares", 3, "Quadriceps,Fessiers", "10"),
                _ex("Pont fessiers une jambe", 3, "Fessiers,Ischio-jambiers", "10-12"),
                _ex("Mollets une jambe", 4, "Mollets", "15"),
            ],
            "Core / conditioning": [
                _ex("L-sit progression", 4, "Abdos", "20s"),
                _ex("Dragon flag négatifs", 3, "Abdos", "5-6"),
                _ex("Planche gainage", 3, "Abdos", "45s"),
                _ex("Mountain climbers", 3, "Abdos,Quadriceps", "30"),
                _ex("Burpees", 3, "Pecs,Quadriceps,Épaules", "15"),
            ],
        },
    },

    "seche_muscu_5j": {
        "id": "seche_muscu_5j",
        "title": "Sèche Musculation — 5j",
        "subtitle": "5 séances / semaine · sèche · salle",
        "freq": 5,
        "level": "intermédiaire,avancé",
        "tags": ["intermédiaire", "avancé", "salle", "sèche"],
        "description": "Programme orienté sèche : split 5 jours avec volume élevé et finishers cardio en fin de séance pour brûler un max de calories tout en préservant la masse.",
        "explanation": "Split 5j + finishers cardio — préserve le muscle en déficit calorique",
        "difficulty": 3,
        "duration": "~55 min",
        "icon": "🔥",
        "seances": {
            "Pecs / Triceps": [
                _ex("Développé incliné haltères", 4, "Pecs,Épaules", "10-12"),
                _ex("Développé couché", 4, "Pecs,Triceps", "8-10"),
                _ex("Écarté poulie", 3, "Pecs", "12-15"),
                _ex("Extensions triceps poulie", 4, "Triceps", "12"),
                _ex("Barre au front", 3, "Triceps", "12"),
            ],
            "Dos / Biceps": [
                _ex("Tirage vertical", 4, "Dos,Biceps", "10-12"),
                _ex("Rowing barre", 4, "Dos,Biceps", "8-10"),
                _ex("Tirage horizontal", 3, "Dos", "12"),
                _ex("Curl barre EZ", 4, "Biceps", "10-12"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "12"),
            ],
            "Jambes": [
                _ex("Squat", 4, "Quadriceps,Fessiers", "8-10"),
                _ex("Presse à cuisses", 4, "Quadriceps,Fessiers", "12"),
                _ex("Soulevé de terre roumain", 3, "Ischio-jambiers,Fessiers", "10"),
                _ex("Leg extension", 3, "Quadriceps", "15"),
                _ex("Mollets debout", 4, "Mollets", "15"),
            ],
            "Épaules / Abdos": [
                _ex("Développé militaire", 4, "Épaules,Triceps", "10"),
                _ex("Élévations latérales", 4, "Épaules", "15"),
                _ex("Face pull", 3, "Épaules,Dos", "15"),
                _ex("Crunch lesté", 4, "Abdos", "15"),
                _ex("Relevés de jambes", 3, "Abdos", "15"),
            ],
            "Full / Finisher": [
                _ex("Deadlift", 3, "Dos,Ischio-jambiers,Fessiers", "8"),
                _ex("Fentes marchées", 3, "Quadriceps,Fessiers", "12"),
                _ex("Tractions", 3, "Dos,Biceps", "max"),
                _ex("Burpees", 4, "Pecs,Quadriceps,Épaules", "15"),
                _ex("Mountain climbers", 3, "Abdos,Quadriceps", "45s"),
            ],
        },
    },
}


# ── Tier Free / PRO ────────────────────────────────────────────────
# Programmes gratuits : les bases essentielles.
# Les autres programmes sont verrouillés et nécessitent un abonnement PRO.
FREE_PROGRAMS = {
    "fb_deb_3j",
    "fb_deb_maison_3j",
    "fb_pdc_3j",
    "upper_lower_4j",
    "ppl_deb_3j",
}


# ── Ordre d'affichage dans l'onboarding ──────────────────────────────
CATALOG_ORDER = [
    # Débutant (Free)
    "fb_deb_3j", "fb_deb_maison_3j", "fb_pdc_3j",
    # Intermédiaire — le PPL 3j et l'Upper/Lower 4j sont Free
    "ppl_deb_3j", "upper_lower_4j", "upper_lower_maison_4j", "ppl_5j", "ppl_6j",
    # Avancé (PRO)
    "ppl_avance_6j", "upper_lower_avance_5j", "pdc_avance_4j",
    # Perte de poids / sèche (PRO sauf circuits)
    "circuit_salle_3j", "circuit_maison_3j", "hiit_muscu_4j", "seche_muscu_5j",
    # Spécialisations (PRO)
    "glutes_focus_4j", "bras_spe_4j",
    # Force (5x5 Free, athlé PRO)
    "force_5x5_3j", "force_athle_4j",
]


def unique_muscles_for(prog_id: str) -> list[str]:
    """Liste dédoublonnée des muscles ciblés par un programme du catalogue,
    calculée dynamiquement depuis les exos. Sert à afficher les muscles sur
    les cartes catalogue dans /programme."""
    p = CATALOG.get(prog_id)
    if not p:
        return []
    seen: list[str] = []
    for exos in p["seances"].values():
        for ex in exos:
            for m in (ex.get("muscle") or "").split(","):
                m = m.strip()
                if m and m not in seen:
                    seen.append(m)
    return seen


def is_free(prog_id: str) -> bool:
    """Un programme est Free s'il figure dans FREE_PROGRAMS."""
    return prog_id in FREE_PROGRAMS


def list_programs(is_vip: bool = True) -> list[dict]:
    """Liste publique des programmes (métadonnées + preview séances).

    Si ``is_vip`` est False, les programmes hors FREE_PROGRAMS sont retournés
    avec ``locked=True`` ; l'UI se charge de les afficher en mode verrouillé.
    """
    out = []
    for pid in CATALOG_ORDER:
        p = CATALOG[pid]
        locked = (not is_vip) and (pid not in FREE_PROGRAMS)
        seances_preview = []
        for sname, exos in p["seances"].items():
            seances_preview.append({
                "name": sname,
                "exercises": [
                    {"name": e["name"], "sets": e["sets"], "muscle": e["muscle"]}
                    for e in exos
                ],
            })
        out.append({
            "id": p["id"],
            "title": p["title"],
            "subtitle": p["subtitle"],
            "freq": p["freq"],
            "description": p["description"],
            "explanation": p.get("explanation", ""),
            "difficulty": p.get("difficulty", 1),
            "duration": p.get("duration", "~60 min"),
            "icon": p.get("icon", "🏋️"),
            "tags": p["tags"],
            "muscles": unique_muscles_for(pid),
            "nb_seances": len(p["seances"]),
            "seances_preview": seances_preview,
            "locked": locked,
            "pro": pid not in FREE_PROGRAMS,
        })
    return out


def get_program(prog_id: str) -> dict | None:
    return CATALOG.get(prog_id)


# ── Recommandation ───────────────────────────────────────────────────
def recommend(niveau: str, frequence: int, equipement: str, is_vip: bool = True) -> list[str]:
    """Retourne la liste des IDs programmes recommandés (3 à 4 éléments),
    dans l'ordre de pertinence. Le premier = recommandation principale.

    Pour les non-VIP, seuls les programmes Free sont recommandés.
    """
    niveau = (niveau or "").strip().lower()
    equipement = (equipement or "").strip().lower()
    freq = int(frequence or 3)

    is_home = equipement in ("maison", "minimal", "aucun", "élastiques", "elastiques")
    is_pdc = equipement in ("aucun", "poids du corps", "rien")

    recs: list[str] = []

    # ── Débutant ──
    if niveau in ("débutant", "debutant", "novice"):
        if is_pdc:
            recs.append("fb_pdc_3j")
        elif is_home:
            recs.append("fb_deb_maison_3j")
        else:
            recs.append("fb_deb_3j")

    # ── Intermédiaire ──
    elif niveau in ("intermédiaire", "intermediaire"):
        if is_home:
            recs.append("upper_lower_maison_4j")
        elif freq >= 5:
            recs.append("ppl_6j" if freq >= 6 else "ppl_5j")
        else:
            recs.append("upper_lower_4j")

    # ── Avancé ──
    elif niveau in ("avancé", "avance", "confirmé", "confirme"):
        if freq >= 6:
            recs.append("ppl_avance_6j")
        else:
            recs.append("upper_lower_avance_5j")

    # ── Fallback ──
    else:
        if is_home:
            recs.append("fb_deb_maison_3j")
        else:
            recs.append("fb_deb_3j")

    # ── Objectifs spécifiques (ajoutés en complément) ──
    # Perte de poids
    if is_pdc:
        _add_if_missing(recs, "circuit_maison_3j")
    elif is_home:
        _add_if_missing(recs, "circuit_maison_3j")
    else:
        _add_if_missing(recs, "circuit_salle_3j")

    # Force
    if not is_home:
        if freq >= 4:
            _add_if_missing(recs, "force_athle_4j")
        else:
            _add_if_missing(recs, "force_5x5_3j")

    # Compléter avec des fallbacks pertinents
    if is_home:
        for fb in ("fb_deb_maison_3j", "fb_pdc_3j", "upper_lower_maison_4j", "circuit_maison_3j"):
            if len(recs) >= 4:
                break
            _add_if_missing(recs, fb)
    else:
        for fb in ("fb_deb_3j", "upper_lower_4j", "ppl_6j", "force_5x5_3j"):
            if len(recs) >= 4:
                break
            _add_if_missing(recs, fb)

    # Non-VIP : on ne recommande que des programmes Free.
    if not is_vip:
        recs = [r for r in recs if r in FREE_PROGRAMS]
        for fb in ("fb_deb_3j", "ppl_deb_3j", "upper_lower_4j", "fb_deb_maison_3j", "fb_pdc_3j"):
            if len(recs) >= 3:
                break
            _add_if_missing(recs, fb)

    return recs[:4]


def _add_if_missing(lst: list[str], item: str):
    if item not in lst:
        lst.append(item)


# ── Construction d'un programme (clone dans programs.data) ───────────
def build_program(prog_id: str, frequence: int, equipment: list[str] | None = None) -> dict:
    """Construit un dict programme complet (séances + _planning) à partir
    du catalogue. Retourne un clone profond prêt à être sauvegardé via
    core.data.save_prog().

    Si ``equipment`` est fourni (liste des IDs matériel de l'utilisateur),
    les exercices nécessitant du matériel absent sont remplacés par des
    alternatives compatibles.
    """
    from core.exercises_data import (
        EQUIPMENT_FOR_EXERCISE, EXERCISE_SUBSTITUTIONS, check_equipment
    )

    src = CATALOG.get(prog_id)
    if not src:
        raise ValueError(f"Programme inconnu : {prog_id}")

    # banc_inclinable implique aussi banc_plat
    effective_equipment = set(equipment or [])
    if "banc_inclinable" in effective_equipment:
        effective_equipment.add("banc_plat")

    # Cohérence avec la fréquence demandée par l'utilisateur :
    #   - si user_freq <= séances dispo : on tronque la liste pour avoir
    #     exactement user_freq séances distinctes ET user_freq jours planifiés
    #     (corrige le bug : 2 j/sem → 2 séances, pas 3) ;
    #   - si user_freq > séances dispo (programmes cyclés type PPL 5j avec
    #     Push/Pull/Legs sur 5 jours) : on garde toutes les séances du
    #     catalogue et on cycle sur user_freq jours.
    catalog_seance_names = list(src["seances"].keys())
    freq_eff = int(frequence or src["freq"])
    freq_eff = max(2, min(6, freq_eff))
    if freq_eff <= len(catalog_seance_names):
        seance_names = catalog_seance_names[:freq_eff]
    else:
        seance_names = catalog_seance_names

    prog: dict = {}
    # Copie des séances (retire le _reps_hint qui reste côté catalogue)
    for seance_name in seance_names:
        exos = src["seances"][seance_name]
        built_exos = []
        for e in exos:
            name = e["name"]
            muscle = e["muscle"]
            sets = int(e["sets"])
            # Substitution si matériel manquant
            if equipment is not None and not check_equipment(name, effective_equipment):
                alt = EXERCISE_SUBSTITUTIONS.get(name)
                if alt:
                    name = alt
            built_exos.append({"name": name, "sets": sets, "muscle": muscle})
        prog[seance_name] = built_exos

    prog["_planning"] = planning_for(freq_eff, seance_names)
    prog["_origin"] = prog_id
    return deepcopy(prog)
