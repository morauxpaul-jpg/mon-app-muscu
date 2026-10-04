"""Raconter la progression.

Elle existait dans la fiche de chaque exercice, mais personne ne la poussait
à l'utilisateur : le débutant de la semaine 3 ne savait pas qu'il avait pris
10 kg au squat (audit du 03/10, profil 2). L'accueil le lui dit.

Un fait marquant compare le meilleur des deux dernières semaines au meilleur
d'une fenêtre plus ancienne (3 à 8 semaines avant) sur le même exercice :
charge pour un exercice chargé, répétitions au poids du corps. Seuls les
gains nets comptent (≥ 2,5 kg ou ≥ 2 reps), les plus forts d'abord.
"""
from core.muscu import BW_EXOS, get_base_name

FENETRE_RECENTE = 2           # semaines
FENETRE_ANCIENNE = (3, 8)     # semaines avant la semaine courante
GAIN_KG_MIN = 2.5
GAIN_REPS_MIN = 2


def _perf(r) -> bool:
    exo = str(r.get("Exercice") or "")
    return (int(r.get("Reps") or 0) > 0 and exo != "SESSION" and not exo.startswith("CARDIO:")
            and "SKIP" not in str(r.get("Remarque") or ""))


def faits_marquants(hist, semaine_courante: int, limite: int = 2) -> list:
    """[{exo, gain, unite, semaines, texte}] du plus fort gain relatif au moins fort."""
    par_exo: dict = {}
    for r in hist or []:
        if _perf(r) and r.get("Semaine"):
            par_exo.setdefault(r["Exercice"], []).append(r)
    faits = []
    for exo, rows in par_exo.items():
        au_pdc = get_base_name(exo) in BW_EXOS or all(float(r.get("Poids") or 0) <= 0 for r in rows)
        mesure = (lambda r: int(r["Reps"])) if au_pdc else (lambda r: float(r.get("Poids") or 0))
        recents = [r for r in rows if semaine_courante - int(r["Semaine"]) < FENETRE_RECENTE]
        anciens = [r for r in rows if FENETRE_ANCIENNE[0] <= semaine_courante - int(r["Semaine"])
                   <= FENETRE_ANCIENNE[1]]
        if not recents or not anciens:
            continue
        avant, apres = max(map(mesure, anciens)), max(map(mesure, recents))
        gain = apres - avant
        if gain < (GAIN_REPS_MIN if au_pdc else GAIN_KG_MIN) or avant <= 0:
            continue
        semaines = semaine_courante - min(int(r["Semaine"]) for r in anciens if mesure(r) == avant)
        unite = "reps" if au_pdc else "kg"
        valeur = f"{gain:g}".replace(".", ",")
        faits.append({"exo": exo, "gain": gain, "unite": unite, "semaines": semaines,
                      "relatif": gain / avant,
                      "texte": f"{exo} : +{valeur} {unite} en {semaines} semaines"})
    faits.sort(key=lambda f: -f["relatif"])
    return faits[:limite]
