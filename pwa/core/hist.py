"""Prédicats partagés sur les lignes d'historique.

Une ligne d'historique a la forme normalisée produite par `db.get_hist()` :
{Semaine, Séance, Exercice, Série, Reps, Poids, Remarque, Muscle, Date, RPE}.

Ces fonctions étaient dupliquées (et divergentes) dans routes/accueil.py,
routes/seance.py, routes/progres.py et core/challenges.py — d'où le bug des
séances au poids du corps qui ne comptaient nulle part : certaines copies
testaient `Poids > 0`, qui est toujours faux pour des pompes ou du gainage.
"""

CARDIO_PREFIX = "CARDIO:"
SESSION_MARKER = "SESSION"


def is_cardio(row) -> bool:
    return str(row.get("Exercice") or "").startswith(CARDIO_PREFIX)


def cardio_activity(row) -> str:
    exo = str(row.get("Exercice") or "")
    return exo.split(":", 1)[1] if ":" in exo else "Autre"


def is_session_marker(row) -> bool:
    """Ligne technique « SESSION » (séance marquée manquée)."""
    return row.get("Exercice") == SESSION_MARKER


def is_perf(row) -> bool:
    """Entraînement réellement effectué (muscu ou cardio).

    Critère : au moins une répétition OU une charge. Le poids seul ne peut pas
    servir de critère — pompes, tractions, gainage, abdos sont enregistrés à
    0 kg, et un cardio stocke ses minutes dans Reps.
    """
    if is_session_marker(row):
        return False
    return int(row.get("Reps") or 0) > 0 or float(row.get("Poids") or 0) > 0


def is_muscu_perf(row) -> bool:
    """Perf réelle hors cardio (volume, records, body map)."""
    return not is_cardio(row) and is_perf(row)


def is_logged(row) -> bool:
    """Perf réelle OU exercice explicitement passé (SKIP).

    Utilisé pour l'affichage « la séance a été ouverte et traitée ce jour-là »
    (calendrier, carte du jour), où un exercice sauté compte comme une trace.
    """
    if is_session_marker(row):
        return False
    return is_perf(row) or "SKIP" in (row.get("Remarque") or "")


def sessions_done(rows) -> set:
    """Séances distinctes réellement faites : {(Date, Séance)}."""
    return {(r.get("Date"), r.get("Séance")) for r in rows
            if r.get("Date") and is_perf(r)}


def tonnage(rows) -> int:
    """Volume muscu cumulé (kg × reps). Le cardio est exclu : ses colonnes
    Poids/Reps portent des km et des minutes."""
    return int(sum(float(r.get("Poids") or 0) * int(r.get("Reps") or 0)
                   for r in rows if is_muscu_perf(r)))
