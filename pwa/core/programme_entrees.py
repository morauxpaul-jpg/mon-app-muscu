"""Une entrée d'exercice du programme, bornée.

Toutes les écritures du programme passent par `_exo_entry` (éditeur, ajout,
import, Gestion). Sorti de routes/programme.py, plafonné en lignes
(tests/test_mineurs_audit.py).
"""
from core.exercice_ids import valide as valide_exo_id
from core.muscu import VARIANTS

# Bornes de l'éditeur. Sans elles, une séance à 10 000 séries rendait la
# page de séance inutilisable et gonflait le blob du programme (audit du
# 03/10, M11). Mêmes bornes qu'à l'import (`routes/gestion.py`).
MAX_SERIES = 20
MAX_EXOS_PAR_SEANCE = 30
MAX_SEANCES = 40
NOM_EXO_MAX = 80
NOM_SEANCE_MAX = 60


def _series(valeur, defaut=3) -> int:
    """Nombre de séries borné à [1, MAX_SERIES]."""
    try:
        n = int(float(valeur))
    except (TypeError, ValueError):
        return defaut
    return max(1, min(MAX_SERIES, n))


def _exo_entry(name, sets, muscle, src=None):
    """Entrée d'exercice normalisée. `reps` (fourchette cible, ex. « 8-12 ») et
    `rest_seconds` viennent du catalogue / du générateur / de l'éditeur ; ils
    sont conservés à chaque réécriture (sans eux, un programme n'est plus une
    prescription mais une simple liste de noms). Toutes les écritures passent
    ici : c'est ici que les bornes s'appliquent."""
    src = src or {}
    name = str(name or "").strip()[:NOM_EXO_MAX]
    sets = _series(sets)
    muscle = (str(muscle or "").strip() or "Autre")[:NOM_EXO_MAX]
    reps = str(src.get("reps") or "").strip()[:20]
    try:
        rest = int(src.get("rest_seconds") or 90)
    except (TypeError, ValueError):
        rest = 90
    out = {"name": name, "sets": sets, "muscle": muscle,
           "rest_seconds": max(30, min(300, rest))}
    if reps:
        out["reps"] = reps
    # Superset : cet exercice s'enchaîne avec le suivant, sans repos entre
    # les deux (le chrono part après le second).
    if src.get("superset") is True:
        out["superset"] = True
    # Identifiant stable (core/exercice_ids.py) : il survit aux renommages.
    # Absent ou illisible, save_prog en recalcule un.
    if valide_exo_id(src.get("id")):
        out["id"] = src["id"]
    # Équipement par défaut en séance (core/noms_exercices.ranger_nouveaux).
    if src.get("materiel") in VARIANTS and src.get("materiel") != "Standard":
        out["materiel"] = src["materiel"]
    return out
