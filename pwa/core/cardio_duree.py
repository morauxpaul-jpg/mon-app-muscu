"""La durée d'un cardio : minutes ET secondes (retour du 06/10).

Les formulaires n'avaient qu'un champ minutes : 25 min 30 s s'enregistrait
25 min, et le chrono tronquait 25:59 en 25. La colonne `duree_min` (v44) est
numérique : elle garde les minutes décimales (25.5), sans migration.

Dans l'app, une ligne cardio porte la durée exacte sous `Duree` et les
minutes entières sous `Reps`, que des dizaines d'écrans lisent.
"""


def _nombre(v):
    """Valeur numérique positive, ou 0. Accepte la virgule décimale."""
    try:
        n = float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return 0.0
    return n if n > 0 else 0.0


DUREE_MAX_MIN = 1440


def lire_duree(form) -> float:
    """La durée saisie, en minutes : le champ minutes plus le champ secondes
    (`duree_sec`). La colonne `duree_min` est numérique (v44) : 25 min 30 s
    s'y range 25.5. Arrondie au dix-millième, assez pour retrouver la
    seconde ; bornée à une journée."""
    minutes = _nombre(form.get("duree_min")) + _nombre(form.get("duree_sec")) / 60.0
    return round(min(minutes, DUREE_MAX_MIN), 4)


def reps_de(duree) -> int:
    """Les minutes entières que l'app lit dans `Reps` : arrondies, et jamais
    0 pour un cardio fait (40 s comptent comme 1 min, pas comme rien)."""
    duree = float(duree or 0)
    return max(1, int(round(duree))) if duree > 0 else 0


def format_duree(minutes) -> str:
    """« 25 min », « 25 min 30 s », « 40 s » ; vide sans durée."""
    try:
        secondes = int(round(float(minutes or 0) * 60))
    except (TypeError, ValueError):
        return ""
    if secondes <= 0:
        return ""
    mn, s = divmod(secondes, 60)
    if not mn:
        return f"{s} s"
    return f"{mn} min {s} s" if s else f"{mn} min"
