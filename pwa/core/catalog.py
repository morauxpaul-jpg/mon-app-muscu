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
    "fb_deb_3j": {
        "id": "fb_deb_3j",
        "title": "Full Body Débutant",
        "subtitle": "3 séances / semaine · corps entier",
        "freq": 3,
        "level": "débutant",
        "tags": ["débutant", "salle", "maison léger"],
        "description": "Le meilleur choix pour démarrer : 3 séances identiques qui travaillent tout le corps. Progression rapide sur les bases.",
        "seances": {
            "Full Body A": [
                _ex("Squat", 4, "Quadriceps,Fessiers", "8-10"),
                _ex("Développé couché", 4, "Pecs,Triceps", "8-10"),
                _ex("Rowing barre", 4, "Dos,Biceps", "8-10"),
                _ex("Développé militaire", 3, "Épaules,Triceps", "10-12"),
                _ex("Curl biceps", 3, "Biceps", "10-12"),
                _ex("Gainage", 3, "Abdos", "30-60s"),
            ],
            "Full Body B": [
                _ex("Soulevé de terre", 4, "Dos,Ischio-jambiers,Fessiers", "6-8"),
                _ex("Développé incliné haltères", 4, "Pecs,Épaules", "8-10"),
                _ex("Tractions (ou tirage vertical)", 4, "Dos,Biceps", "6-10"),
                _ex("Fentes haltères", 3, "Quadriceps,Fessiers", "10-12"),
                _ex("Extensions triceps poulie", 3, "Triceps", "10-12"),
                _ex("Crunch", 3, "Abdos", "15-20"),
            ],
            "Full Body C": [
                _ex("Presse à cuisses", 4, "Quadriceps,Fessiers", "10-12"),
                _ex("Dips (ou pompes lestées)", 4, "Pecs,Triceps", "8-12"),
                _ex("Rowing haltère", 4, "Dos,Biceps", "10-12"),
                _ex("Élévations latérales", 3, "Épaules", "12-15"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "10-12"),
                _ex("Relevé de jambes", 3, "Abdos", "12-15"),
            ],
        },
    },

    "ppl_6j": {
        "id": "ppl_6j",
        "title": "Push / Pull / Legs",
        "subtitle": "6 séances / semaine · intermédiaire & avancé",
        "freq": 6,
        "level": "intermédiaire,avancé",
        "tags": ["intermédiaire", "avancé", "salle"],
        "description": "Le grand classique PPL : 2 cycles push/pull/legs par semaine. Volume élevé, idéal pour progresser quand les bases sont solides.",
        "seances": {
            "Push": [
                _ex("Développé couché", 4, "Pecs,Triceps", "6-8"),
                _ex("Développé militaire", 4, "Épaules,Triceps", "8-10"),
                _ex("Développé incliné haltères", 3, "Pecs,Épaules", "8-10"),
                _ex("Élévations latérales", 4, "Épaules", "12-15"),
                _ex("Dips", 3, "Triceps,Pecs", "8-12"),
                _ex("Extensions triceps poulie", 3, "Triceps", "10-12"),
            ],
            "Pull": [
                _ex("Soulevé de terre", 4, "Dos,Ischio-jambiers,Fessiers", "5-6"),
                _ex("Tractions", 4, "Dos,Biceps", "6-10"),
                _ex("Rowing barre", 4, "Dos,Biceps", "8-10"),
                _ex("Tirage horizontal poulie", 3, "Dos", "10-12"),
                _ex("Curl barre", 3, "Biceps", "8-10"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "10-12"),
            ],
            "Legs": [
                _ex("Squat", 4, "Quadriceps,Fessiers", "6-8"),
                _ex("Presse à cuisses", 4, "Quadriceps,Fessiers", "10-12"),
                _ex("Soulevé de terre roumain", 4, "Ischio-jambiers,Fessiers", "8-10"),
                _ex("Leg curl", 3, "Ischio-jambiers", "10-12"),
                _ex("Leg extension", 3, "Quadriceps", "12-15"),
                _ex("Mollets debout", 4, "Mollets", "12-15"),
            ],
        },
    },

    "upper_lower_4j": {
        "id": "upper_lower_4j",
        "title": "Upper / Lower",
        "subtitle": "4 séances / semaine · intermédiaire",
        "freq": 4,
        "level": "intermédiaire",
        "tags": ["intermédiaire", "salle"],
        "description": "2 haut + 2 bas du corps par semaine. Excellent compromis volume / récupération pour progresser sans y passer sa vie.",
        "seances": {
            "Upper A": [
                _ex("Développé couché", 4, "Pecs,Triceps", "6-8"),
                _ex("Rowing barre", 4, "Dos,Biceps", "6-8"),
                _ex("Développé militaire", 3, "Épaules,Triceps", "8-10"),
                _ex("Tractions", 3, "Dos,Biceps", "6-10"),
                _ex("Curl barre", 3, "Biceps", "10-12"),
                _ex("Extensions triceps poulie", 3, "Triceps", "10-12"),
            ],
            "Lower A": [
                _ex("Squat", 4, "Quadriceps,Fessiers", "6-8"),
                _ex("Soulevé de terre roumain", 4, "Ischio-jambiers,Fessiers", "8-10"),
                _ex("Presse à cuisses", 3, "Quadriceps,Fessiers", "10-12"),
                _ex("Leg curl", 3, "Ischio-jambiers", "10-12"),
                _ex("Mollets debout", 4, "Mollets", "12-15"),
                _ex("Gainage", 3, "Abdos", "30-60s"),
            ],
            "Upper B": [
                _ex("Développé incliné haltères", 4, "Pecs,Épaules", "8-10"),
                _ex("Tirage horizontal poulie", 4, "Dos", "8-10"),
                _ex("Élévations latérales", 4, "Épaules", "12-15"),
                _ex("Dips", 3, "Triceps,Pecs", "8-12"),
                _ex("Curl marteau", 3, "Biceps,Avant-bras", "10-12"),
                _ex("Face pull", 3, "Épaules,Dos", "12-15"),
            ],
            "Lower B": [
                _ex("Soulevé de terre", 4, "Dos,Ischio-jambiers,Fessiers", "5-6"),
                _ex("Fentes haltères", 4, "Quadriceps,Fessiers", "10-12"),
                _ex("Leg extension", 3, "Quadriceps", "12-15"),
                _ex("Hip thrust", 3, "Fessiers", "10-12"),
                _ex("Mollets assis", 4, "Mollets", "12-15"),
                _ex("Relevé de jambes", 3, "Abdos", "12-15"),
            ],
        },
    },

    "fb_maison_3j": {
        "id": "fb_maison_3j",
        "title": "Full Body Maison",
        "subtitle": "3 séances / semaine · équipement minimal",
        "freq": 3,
        "level": "débutant,intermédiaire",
        "tags": ["maison", "débutant", "intermédiaire", "peu d'équipement"],
        "description": "Fait avec très peu : poids du corps, haltères ou élastiques suffisent. Parfait pour s'entraîner chez soi sans sacrifier la progression.",
        "seances": {
            "Maison A": [
                _ex("Pompes", 4, "Pecs,Triceps", "max-1"),
                _ex("Squat (poids du corps ou lesté)", 4, "Quadriceps,Fessiers", "15-20"),
                _ex("Rowing haltère (ou élastique)", 4, "Dos,Biceps", "10-12"),
                _ex("Fentes alternées", 3, "Quadriceps,Fessiers", "10-12"),
                _ex("Gainage", 3, "Abdos", "30-60s"),
            ],
            "Maison B": [
                _ex("Pompes déclinées (pieds surélevés)", 4, "Pecs,Épaules", "max-1"),
                _ex("Hip thrust (sol)", 4, "Fessiers,Ischio-jambiers", "12-15"),
                _ex("Tractions australiennes (ou tirage élastique)", 4, "Dos,Biceps", "10-12"),
                _ex("Squat bulgare", 3, "Quadriceps,Fessiers", "10-12"),
                _ex("Crunch", 3, "Abdos", "15-20"),
            ],
            "Maison C": [
                _ex("Pompes diamant", 4, "Triceps,Pecs", "max-1"),
                _ex("Fentes sautées", 3, "Quadriceps,Fessiers", "10-12"),
                _ex("Curl haltères (ou élastique)", 3, "Biceps", "10-12"),
                _ex("Élévations latérales haltères", 3, "Épaules", "12-15"),
                _ex("Mountain climbers", 3, "Abdos", "30-45s"),
                _ex("Relevé de jambes", 3, "Abdos", "12-15"),
            ],
        },
    },
}


# ── Ordre d'affichage dans l'onboarding ──────────────────────────────
CATALOG_ORDER = ["fb_deb_3j", "upper_lower_4j", "ppl_6j", "fb_maison_3j"]


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


def list_programs() -> list[dict]:
    """Liste publique des programmes (métadonnées seulement, sans séances)."""
    out = []
    for pid in CATALOG_ORDER:
        p = CATALOG[pid]
        out.append({
            "id": p["id"],
            "title": p["title"],
            "subtitle": p["subtitle"],
            "freq": p["freq"],
            "description": p["description"],
            "tags": p["tags"],
            "muscles": unique_muscles_for(pid),
            "nb_seances": len(p["seances"]),
        })
    return out


def get_program(prog_id: str) -> dict | None:
    return CATALOG.get(prog_id)


# ── Recommandation ───────────────────────────────────────────────────
def recommend(niveau: str, frequence: int, equipement: str) -> list[str]:
    """Retourne la liste des IDs programmes recommandés (0 à 3 éléments),
    dans l'ordre de pertinence. Le premier = recommandation principale.

    Règles (CONTEXT.md point 3) :
    - équipement limité / maison → Full Body Maison en priorité
    - débutant → FB Débutant
    - intermédiaire + 4j → Upper/Lower
    - intermédiaire/avancé + 5-6j → PPL
    """
    niveau = (niveau or "").strip().lower()
    equipement = (equipement or "").strip().lower()
    freq = int(frequence or 3)

    home_only = equipement in ("maison", "minimal", "aucun", "élastiques", "elastiques")

    recs: list[str] = []
    if home_only:
        recs.append("fb_maison_3j")

    if niveau in ("débutant", "debutant", "novice"):
        if "fb_deb_3j" not in recs:
            recs.append("fb_deb_3j")
    elif niveau in ("intermédiaire", "intermediaire"):
        if freq >= 5 and "ppl_6j" not in recs:
            recs.append("ppl_6j")
        if freq == 4 and "upper_lower_4j" not in recs:
            recs.append("upper_lower_4j")
        if "upper_lower_4j" not in recs:
            recs.append("upper_lower_4j")
    elif niveau in ("avancé", "avance", "confirmé", "confirme"):
        if "ppl_6j" not in recs:
            recs.append("ppl_6j")
        if freq == 4 and "upper_lower_4j" not in recs:
            recs.append("upper_lower_4j")
    else:
        if "fb_deb_3j" not in recs:
            recs.append("fb_deb_3j")

    # Toujours proposer au moins 2 options
    for fallback in ("fb_deb_3j", "upper_lower_4j", "ppl_6j", "fb_maison_3j"):
        if len(recs) >= 3:
            break
        if fallback not in recs:
            recs.append(fallback)

    return recs[:3]


# ── Construction d'un programme (clone dans programs.data) ───────────
def build_program(prog_id: str, frequence: int) -> dict:
    """Construit un dict programme complet (séances + _planning) à partir
    du catalogue. Retourne un clone profond prêt à être sauvegardé via
    core.data.save_prog()."""
    src = CATALOG.get(prog_id)
    if not src:
        raise ValueError(f"Programme inconnu : {prog_id}")

    prog: dict = {}
    # Copie des séances (retire le _reps_hint qui reste côté catalogue)
    for seance_name, exos in src["seances"].items():
        prog[seance_name] = [
            {"name": e["name"], "sets": int(e["sets"]), "muscle": e["muscle"]}
            for e in exos
        ]

    seance_names = list(src["seances"].keys())
    freq_eff = int(frequence or src["freq"])
    prog["_planning"] = planning_for(freq_eff, seance_names)
    prog["_origin"] = prog_id
    return deepcopy(prog)
