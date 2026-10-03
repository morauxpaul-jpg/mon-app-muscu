"""Séries par muscle et par semaine.

La carte du corps (routes/progres.py) dit quelle PART du volume va à chaque
muscle : « Pecs 30 % ». Ce n'est pas ce qu'on se demande en salle. On se
demande : « est-ce que je fais assez de séries pour mes pecs cette
semaine ? » — la mesure que suivent Hevy, les coachs et la littérature
(audit du 03/10, axe 4).

Une série compte si elle a été faite (au moins une répétition), hors cardio,
marqueurs de séance et exercices passés. Le muscle principal (le premier de
la colonne Muscle, « Pecs,Triceps ») compte pour 1, les suivants pour ½ :
un développé couché fait travailler les triceps, mais pas autant qu'une
extension.

Repères : 10 à 20 séries par semaine pour un grand groupe musculaire, 6 à 16
pour un petit (Schoenfeld et al., 2017 ; Israetel). Ce sont des ordres de
grandeur, présentés comme tels.
"""
from datetime import timedelta

from core.dates import monday_of
from core.muscu import MUSCLE_LIST

PETITS_MUSCLES = {"Avant-bras", "Abdos", "Mollets", "Trapèzes", "Adducteurs", "Abducteurs"}
REPERE_GRAND = (10, 20)
REPERE_PETIT = (6, 16)


def repere(muscle: str) -> tuple:
    return REPERE_PETIT if muscle in PETITS_MUSCLES else REPERE_GRAND


def _faite(r) -> bool:
    exo = str(r.get("Exercice") or "")
    return (int(r.get("Reps") or 0) > 0 and exo != "SESSION"
            and not exo.startswith("CARDIO:")
            and "SKIP" not in str(r.get("Remarque") or ""))


def _muscles(r) -> list:
    return [m.strip() for m in str(r.get("Muscle") or "").split(",") if m.strip()]


def series_par_muscle(hist, lundi) -> dict:
    """{muscle: séries} pour la semaine du lundi donné, secondaires à ½."""
    debut, fin = lundi.isoformat(), (lundi + timedelta(days=6)).isoformat()
    out: dict = {}
    for r in hist or []:
        d = str(r.get("Date") or "")
        if not (debut <= d <= fin) or not _faite(r):
            continue
        for i, m in enumerate(_muscles(r)):
            out[m] = out.get(m, 0) + (1 if i == 0 else 0.5)
    return out


def _arrondi(x: float):
    return int(x) if float(x).is_integer() else round(x, 1)


def tableau_semaine(hist, aujourd_hui) -> list:
    """Lignes pour la page Progrès : un muscle par ligne, ceux travaillés cette
    semaine ou la précédente, du plus au moins travaillé.

    [{muscle, series, precedente, min, max, statut, pct}] — statut vaut
    « sous », « zone » ou « au-dela » ; pct situe la barre (100 = haut du
    repère, plafonné à 120 pour l'affichage)."""
    lundi = monday_of(aujourd_hui)
    cette = series_par_muscle(hist, lundi)
    avant = series_par_muscle(hist, lundi - timedelta(days=7))
    ordre = {m: i for i, m in enumerate(MUSCLE_LIST)}
    lignes = []
    for m in sorted(set(cette) | set(avant), key=lambda m: (-cette.get(m, 0), ordre.get(m, 99), m)):
        n = cette.get(m, 0)
        bas, haut = repere(m)
        statut = "sous" if n < bas else ("au-dela" if n > haut else "zone")
        lignes.append({
            "muscle": m, "series": _arrondi(n), "precedente": _arrondi(avant.get(m, 0)),
            "min": bas, "max": haut, "statut": statut,
            "pct": min(120, round(n / haut * 100)) if haut else 0,
            "pct_min": round(bas / haut * 100),
        })
    return lignes
