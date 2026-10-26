"""Progression par exercice, pour le coach IA : une ligne par exercice.

Retour du 26/10 : le coach a écrit « Pec deck : 39 kg, contre 15,8 kg le
12/10 ». Le 12/10, c'était 39 kg ; 15,8 kg était le pushdown du même jour, et
le pec deck du 4/10. Les données étaient justes, mais rangées par séance :
pour suivre un exercice, le modèle devait aller chercher sa charge au milieu
de lignes chargées, et il se trompait de ligne. Ici chaque exercice a sa
ligne, ses séances datées, de la plus récente à la plus ancienne.
"""

MAX_EXOS = 25          # exercices les plus récemment faits
SEANCES_PAR_EXO = 4


def _serie(reps: int, poids: float) -> str:
    return f"{poids:g} kg × {reps}" if poids > 0 else f"poids du corps × {reps}"


def progression_par_exercice(hist) -> str:
    seances: dict = {}       # exercice → date → [(série, reps, poids)]
    for r in hist or []:
        exo = r.get("Exercice") or ""
        d = r.get("Date") or ""
        if not exo or not d or exo == "SESSION" or exo.startswith("CARDIO:"):
            continue
        try:
            reps = int(r.get("Reps") or 0)
            poids = float(r.get("Poids") or 0)
            serie = int(r.get("Série") or 0)
        except (TypeError, ValueError):
            continue
        if reps <= 0:
            continue
        seances.setdefault(exo, {}).setdefault(d, []).append((serie, reps, poids))
    if not seances:
        return "Aucun exercice enregistré."
    exos = sorted(seances, key=lambda e: max(seances[e]), reverse=True)[:MAX_EXOS]
    lignes = []
    for exo in exos:
        dates = sorted(seances[exo], reverse=True)[:SEANCES_PAR_EXO]
        morceaux = []
        for d in dates:
            series = sorted(seances[exo][d])
            # Dates au même format que « 14 DERNIÈRES SÉANCES ».
            morceaux.append(f"{d} : " + ", ".join(_serie(rp, p) for _, rp, p in series))
        lignes.append(f"- {exo} → " + " | ".join(morceaux))
    return "\n".join(lignes)
