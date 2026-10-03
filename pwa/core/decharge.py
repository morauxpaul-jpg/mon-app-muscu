"""Décharge (semaine allégée) : la proposer quand la fatigue s'accumule.

Ni cycle ni décharge jusqu'ici : on montait la charge jusqu'au plateau, puis
on s'arrêtait (audit du 03/10, idée 10, profil avancé). Les signes qu'une
semaine plus légère ferait du bien se lisent dans le carnet :

* la performance recule sur des exercices suivis régulièrement — l'e1RM de la
  semaine passe sous le meilleur des trois semaines d'avant ;
* l'effort monte pour faire autant — RPE moyen de la semaine ≥ 9 ;
* et cela après au moins quatre semaines d'affilée d'entraînement, sans
  semaine déjà allégée.

On propose, on n'impose pas : la carte d'accueil dit pourquoi, et deux
gestes suffisent — alléger cette semaine, ou ignorer. Alléger réduit de
moitié les séries prévues et de 10 % les charges suggérées, pour les seules
séances de cette semaine (`_decharge_semaine`, lu par la séance).

Les seuils restent prudents : mieux vaut ne rien dire qu'alarmer à tort
(un faux positif tous les mois lasserait vite).
"""
from core.muscu import calc_1rm

SEMAINES_MIN = 4          # semaines d'affilée avant de parler de fatigue
RECUL_MIN = 0.03          # e1RM sous le meilleur récent de 3 % au moins
RPE_HAUT = 9.0
EXOS_EN_RECUL_MIN = 2
ALLEGEE_RATIO = 0.6       # une semaine à < 60 % du volume habituel compte comme allégée


def _muscu(r) -> bool:
    exo = str(r.get("Exercice") or "")
    return (int(r.get("Reps") or 0) > 0 and exo != "SESSION"
            and not exo.startswith("CARDIO:")
            and "SKIP" not in str(r.get("Remarque") or ""))


def _par_semaine(hist):
    out: dict = {}
    for r in hist or []:
        if _muscu(r) and r.get("Semaine"):
            out.setdefault(int(r["Semaine"]), []).append(r)
    return out


def _volume(rows) -> float:
    return sum(float(r.get("Poids") or 0) * int(r.get("Reps") or 0) for r in rows)


def _rpe_moyen(rows):
    vals = []
    for r in rows:
        try:
            if r.get("RPE") not in (None, ""):
                vals.append(float(r["RPE"]))
        except (TypeError, ValueError):
            continue
    return sum(vals) / len(vals) if vals else None


def _e1rm_par_exo(rows) -> dict:
    out: dict = {}
    for r in rows:
        if float(r.get("Poids") or 0) <= 0:
            continue
        v = calc_1rm(float(r["Poids"]), int(r["Reps"]))
        if v > out.get(r["Exercice"], 0):
            out[r["Exercice"]] = v
    return out


def diagnostic(hist, semaine_courante: int) -> dict | None:
    """Raisons de proposer une décharge, ou None.

    On juge la DERNIÈRE semaine complète (semaine_courante - 1) : la semaine
    en cours n'est pas finie, son volume et ses records ne disent encore rien.
    Retourne {raisons: [str], exercices: [str], semaines: int}.
    """
    par = _par_semaine(hist)
    derniere = semaine_courante - 1
    if derniere not in par:
        return None

    # Semaines d'affilée jusqu'à la dernière, sans trou.
    suite = 0
    while (derniere - suite) in par:
        suite += 1
    if suite < SEMAINES_MIN:
        return None

    # Une semaine déjà allégée dans la série récente : pas la peine.
    fenetre = [derniere - i for i in range(min(suite, 6))]
    volumes = [_volume(par[w]) for w in fenetre]
    moyenne = sum(volumes) / len(volumes) if volumes else 0
    if moyenne and any(v < ALLEGEE_RATIO * moyenne for v in volumes[1:]):
        return None

    meilleurs: dict = {}
    for w in (derniere - 1, derniere - 2, derniere - 3):
        for exo, v in _e1rm_par_exo(par.get(w, [])).items():
            meilleurs[exo] = max(v, meilleurs.get(exo, 0))
    actuels = _e1rm_par_exo(par[derniere])
    en_recul = sorted(exo for exo, v in actuels.items()
                      if meilleurs.get(exo) and v <= meilleurs[exo] * (1 - RECUL_MIN))

    rpe = _rpe_moyen(par[derniere])
    raisons = []
    if len(en_recul) >= EXOS_EN_RECUL_MIN:
        raisons.append(f"tes charges reculent sur {len(en_recul)} exercices "
                       f"({', '.join(en_recul[:3])}{'…' if len(en_recul) > 3 else ''})")
    if rpe is not None and rpe >= RPE_HAUT:
        raisons.append(f"tes séries sont très dures (RPE moyen {rpe:.1f}".replace(".", ",") + ")")
    # Un seul signe ne suffit pas, sauf un recul net et large.
    if not raisons or (len(raisons) == 1 and len(en_recul) < EXOS_EN_RECUL_MIN + 1):
        return None
    return {"raisons": raisons, "exercices": en_recul, "semaines": suite}


def semaine_allegee(prog, semaine_courante: int) -> bool:
    try:
        return int((prog or {}).get("_decharge_semaine") or 0) == int(semaine_courante)
    except (TypeError, ValueError):
        return False


def a_proposer(hist, prog, semaine_courante: int) -> dict | None:
    """Diagnostic à afficher sur l'accueil, sauf si cette semaine est déjà
    allégée ou que l'utilisateur a ignoré la proposition cette semaine."""
    prog = prog or {}
    if semaine_allegee(prog, semaine_courante):
        return None
    try:
        if int(prog.get("_decharge_ignoree") or 0) == int(semaine_courante):
            return None
    except (TypeError, ValueError):
        pass
    return diagnostic(hist, semaine_courante)


def suggestion_allegee(last_sets, is_bw: bool):
    """(suggestion, charge pré-remplie) d'un exercice en semaine allégée :
    la charge la plus lourde de la dernière fois −10 % (arrondi 2,5 kg), aux
    mêmes reps ; au poids du corps, deux reps de moins."""
    lourd = max(s["poids"] for s in last_sets)
    reps_ref = min(s["reps"] for s in last_sets)
    if lourd > 0 and not is_bw:
        poids = round(lourd * 0.9 / 2.5) * 2.5
        label = f"Semaine allégée : {poids:g} kg × {reps_ref}, loin de l'échec".replace(".", ",")
        return {"kind": "hold", "poids": poids, "reps": reps_ref, "label": label, "why": "decharge"}, poids
    reps = max(1, reps_ref - 2)
    return {"kind": "hold", "poids": None, "reps": reps,
            "label": f"Semaine allégée : {reps} reps, loin de l'échec", "why": "decharge"}, None
