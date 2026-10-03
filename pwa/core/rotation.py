"""Quelle séance est prévue tel jour.

Le planning (`_planning`) associe un jour de semaine à une séance. Il ne sait
pas alterner : un Full Body A/B sur 3 jours donnait A-B-A chaque semaine, B
une seule fois, jamais en tête ; un PPL sur 2 jours perdait sa séance Legs,
tronquée à la construction (audit du 03/10, rotation).

`_rotation` (facultatif) est la liste des séances dans l'ordre du cycle. Les
jours d'entraînement restent ceux du planning (jour non vide) ; la séance de
chacun avance dans le cycle d'une semaine à l'autre :

    A/B sur Lun-Mer-Ven : A B A, puis B A B, puis A B A…
    Push/Pull/Legs sur Lun-Jeu : Push Pull, Legs Push, Pull Legs…

Le rang d'un jour ne dépend que du calendrier (semaines écoulées depuis le
début du programme), pas de l'historique : le calendrier, l'accueil, la page
séance et le rappel du soir disent la même chose, et un jour passé ne change
pas de séance après coup.

Sans `_rotation` valide (moins de deux séances existantes), tout se passe
comme avant : la séance du jour est celle du planning.
"""
from datetime import date, datetime, timedelta

from core.dates import DAYS_FR, WEEK_EPOCH, monday_of


def rotation_de(prog: dict) -> list[str]:
    """Cycle de séances valide, ou [] : seules les séances existantes comptent,
    et un cycle d'une seule séance n'en est pas un."""
    prog = prog or {}
    rot = prog.get("_rotation")
    if not isinstance(rot, list):
        return []
    out = [s for s in rot if isinstance(s, str) and s and isinstance(prog.get(s), list)]
    return out if len(set(out)) >= 2 else []


def _jours_entrainement(prog: dict) -> list[str]:
    planning = (prog or {}).get("_planning") or {}
    return [d for d in DAYS_FR if planning.get(d)]


def _debut(prog: dict) -> date:
    """Jour où le cycle commence : début du programme, sinon une date fixe."""
    raw = (prog or {}).get("_started_at")
    if raw:
        try:
            return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return WEEK_EPOCH


def seance_prevue(prog: dict, d: date) -> str:
    """Nom de la séance prévue le jour `d`, ou "" (repos)."""
    planning = (prog or {}).get("_planning") or {}
    jour = DAYS_FR[d.weekday()]
    rot = rotation_de(prog)
    if not rot:
        return planning.get(jour) or ""
    jours = _jours_entrainement(prog)
    if jour not in jours:
        return ""
    debut = _debut(prog)
    semaines = (monday_of(d) - monday_of(debut)).days // 7
    # Programme commencé un mercredi : le premier jour d'entraînement à partir
    # de ce mercredi ouvre le cycle (séance A), pas le lundi déjà passé.
    deja_passes = sum(1 for j in jours if DAYS_FR.index(j) < debut.weekday())
    rang = semaines * len(jours) + jours.index(jour) - deja_passes
    return rot[rang % len(rot)]


def planning_semaine(prog: dict, d: date) -> dict:
    """{jour: séance} pour la semaine (lundi → dimanche) qui contient `d`."""
    lundi = monday_of(d)
    return {DAYS_FR[i]: seance_prevue(prog, lundi + timedelta(days=i)) for i in range(7)}


def rotation_nettoyee(rot, noms_existants) -> list[str]:
    """`_rotation` à enregistrer : les séances qui existent encore, ou [] si
    le cycle n'a plus de sens (moins de deux séances distinctes)."""
    if not isinstance(rot, list):
        return []
    noms = set(noms_existants)
    out = [s for s in rot if isinstance(s, str) and s in noms]
    return out if len(set(out)) >= 2 else []
