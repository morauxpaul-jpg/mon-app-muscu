"""Standards de force relatifs au gabarit.

La carte du corps (Progrès) colore chaque muscle selon un pourcentage : où en
est l'utilisateur par rapport à un niveau de référence. Ce pourcentage était
calculé contre une valeur ABSOLUE identique pour tout le monde (1RM pecs de
140 kg = 100 %). Conséquence : une personne de 55 kg restait « rouge » à vie,
quel que soit son travail, tandis qu'une personne de 100 kg était « verte »
sans effort. Une stat qui ne bouge pas n'est pas une stat.

Ici, la référence est un multiple du POIDS DE CORPS, différencié par sexe.
C'est l'approche des tables de standards courantes (ExRx, Symmetric Strength) :
« développé couché à 1 × son poids de corps » est un repère qui a du sens à
55 comme à 100 kg.

Les ratios visent un niveau INTERMÉDIAIRE (quelques années d'entraînement
régulier) = 100 %. Ce sont des ordres de grandeur, pas une vérité : ils servent
à donner une direction, et l'échelle est volontairement atteignable.

Sans poids de corps connu, on retombe sur les anciennes valeurs absolues pour
ne pas afficher n'importe quoi.
"""

# Multiplicateurs du poids de corps pour un 1RM de niveau intermédiaire, par
# muscle et par sexe. Muscle → (hommes, femmes).
_RATIOS = {
    "Pecs":            (1.00, 0.60),   # développé couché
    "Dos":             (1.00, 0.65),   # rowing / tirage
    "Trapèzes":        (1.30, 0.85),   # shrug
    "Épaules":         (0.65, 0.40),   # développé militaire
    "Biceps":          (0.45, 0.27),   # curl barre
    "Triceps":         (0.50, 0.30),   # extension / dips lesté
    "Avant-bras":      (0.35, 0.22),   # wrist curl
    "Abdos":           (0.50, 0.35),   # relevé lesté / crunch poulie
    "Quadriceps":      (1.40, 1.05),   # squat
    "Ischio-jambiers": (0.90, 0.65),   # leg curl / soulevé jambes tendues
    "Fessiers":        (1.50, 1.25),   # hip thrust
    "Adducteurs":      (0.60, 0.50),
    "Abducteurs":      (0.60, 0.50),
    "Mollets":         (1.20, 0.95),   # mollets debout
}

# Repli historique (aucun poids de corps renseigné) : valeurs absolues d'avant.
_ABSOLUTE = {
    "Pecs": 140, "Dos": 160, "Trapèzes": 80, "Épaules": 90, "Biceps": 60,
    "Triceps": 70, "Avant-bras": 45, "Abdos": 60, "Quadriceps": 180,
    "Ischio-jambiers": 110, "Fessiers": 140, "Adducteurs": 80,
    "Abducteurs": 80, "Mollets": 110,
}

# Bornes de gabarit : un poids saisi hors de cette plage est ignoré (faute de
# frappe, unité en livres…) plutôt que de fausser toute la carte.
_MIN_KG, _MAX_KG = 35.0, 200.0


def _is_female(sexe) -> bool:
    s = str(sexe or "").strip().lower()
    return s.startswith("f") or s in ("femme", "female", "w")


def standard_for(muscle: str, poids_kg=None, sexe=None) -> float:
    """1RM de référence (kg) pour ce muscle, ce gabarit et ce sexe.

    `poids_kg` absent ou aberrant → valeur absolue historique.
    Sexe non renseigné (ou « autre ») → moyenne des deux ratios, pour ne pas
    imposer une référence masculine par défaut.
    """
    ratios = _RATIOS.get(muscle)
    if not ratios:
        return float(_ABSOLUTE.get(muscle, 100))
    try:
        bw = float(poids_kg or 0)
    except (TypeError, ValueError):
        bw = 0.0
    if not (_MIN_KG <= bw <= _MAX_KG):
        return float(_ABSOLUTE.get(muscle, 100))

    s = str(sexe or "").strip().lower()
    if _is_female(s):
        ratio = ratios[1]
    elif s.startswith("h") or s in ("homme", "male", "m"):
        ratio = ratios[0]
    else:
        ratio = (ratios[0] + ratios[1]) / 2
    return round(bw * ratio, 1)


def standards(poids_kg=None, sexe=None) -> dict:
    """{muscle: 1RM de référence} pour tous les muscles de la carte."""
    return {m: standard_for(m, poids_kg, sexe) for m in _ABSOLUTE}


def is_relative(poids_kg=None) -> bool:
    """True si les standards sont calculés sur le gabarit (et non le repli
    absolu) — l'UI l'indique pour que le chiffre soit interprétable."""
    try:
        bw = float(poids_kg or 0)
    except (TypeError, ValueError):
        return False
    return _MIN_KG <= bw <= _MAX_KG


# ── Niveaux ──────────────────────────────────────────────────────
# Le pourcentage seul ne dit pas grand-chose ; un libellé situe l'utilisateur.
LEVELS = [
    (0, "Débutant"),
    (40, "Novice"),
    (70, "Intermédiaire"),
    (100, "Confirmé"),
    (130, "Avancé"),
]


def level_for(pct: float) -> str:
    label = LEVELS[0][1]
    for threshold, name in LEVELS:
        if pct >= threshold:
            label = name
    return label
