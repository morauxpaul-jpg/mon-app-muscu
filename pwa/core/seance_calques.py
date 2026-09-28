"""Les calques du jour, posés par-dessus le programme.

« Aujourd'hui je fais mon curl à la poulie » ne doit pas réécrire le
programme : la semaine prochaine, le curl incliné revient tout seul. Les
substitutions, les exercices ajoutés à la volée, le brouillon de séance
libre et l'ordre des cartes sont donc rangés par séance+date dans le blob
du programme, et cette date seule.

Contient aussi la purge des bilans trop vieux, qui suit la même règle de
fenêtre glissante.

Les noms gardent leur préfixe `_` : ils viennent tels quels de
`routes/seance.py`, et le déplacement a été fait sans en renommer un seul
pour que chaque corps de fonction reste comparable au caractère près.
"""
import logging
from datetime import timedelta

from core.dates import logical_today_paris
from core.exercises_data import get_exercise_info
from core.seance_historique import _norm
from core.seance_semaine import _parse_date

logger = logging.getLogger(__name__)

def _appliquer_substituts(prog_dict, key, exos_prog):
    """Échange des exercices pour CETTE séance-là, sans toucher au programme.

    « Aujourd'hui je fais mon curl à la poulie » ne doit pas réécrire le
    programme : la semaine prochaine, le curl incliné revient tout seul. Le
    calque est donc rangé par séance+date, exactement comme les exos ajoutés
    à la volée (`_extras`) et l'ordre des cartes (`_seance_order`).

    Le créneau garde ses séries et ses reps cibles : c'est tout l'intérêt
    de l'échange, on ne resaisit rien.
    """
    remplacements = (prog_dict.get("_substituts") or {}).get(key) or {}
    if not remplacements:
        return exos_prog
    sortie = []
    for exo in exos_prog:
        nouveau = remplacements.get(_norm(exo.get("name") or ""))
        if not nouveau:
            sortie.append(exo)
            continue
        fiche = get_exercise_info(nouveau) or {}
        muscles = fiche.get("muscles") or []
        sortie.append({**exo,
                       "name": nouveau,
                       "muscle": muscles[0] if muscles else exo.get("muscle"),
                       "remplace": exo.get("name") or ""})
    return sortie


def _update_extras(prog_dict, key, mutate_fn):
    extras_all = prog_dict.setdefault("_extras", {})
    lst = extras_all.get(key, [])
    mutate_fn(lst)
    if lst:
        extras_all[key] = lst
    else:
        extras_all.pop(key, None)


def _update_libre_draft(prog_dict, key, mutate_fn):
    drafts = prog_dict.setdefault("_libre_draft", {})
    lst = drafts.get(key, [])
    mutate_fn(lst)
    if lst:
        drafts[key] = lst
    else:
        drafts.pop(key, None)


def _apply_seance_order(prog_dict, key, exos_ctx):
    """Réordonne les cartes d'exos selon l'ordre personnalisé sauvegardé pour
    cette séance+date (drag dans la séance en cours). Les exos absents de
    l'ordre (nouveaux, reconstruits depuis l'historique) restent en fin, dans
    leur ordre d'origine. L'ordre est stocké comme une simple liste de noms de
    base, donc purement cosmétique : il ne touche ni au programme ni à
    l'historique (source de vérité)."""
    order = (prog_dict.get("_seance_order") or {}).get(key)
    if not order:
        return exos_ctx
    norm_order = [_norm(n) for n in order]

    def _rank(e):
        n = _norm(e.get("base") or e.get("exo_final") or "")
        return norm_order.index(n) if n in norm_order else len(norm_order)

    return sorted(exos_ctx, key=_rank)


SESSION_NOTES_KEEP_DAYS = 84  # fenêtre glissante : 12 semaines de bilans


def _purge_old_session_notes(prog_dict, today=None):
    """Retire de `_session_notes` les bilans plus vieux que la fenêtre.
    Sans ça le blob programme (relu et réécrit à chaque interaction) grossit
    d'une entrée par séance, à vie — contrairement à `_extras` et
    `_libre_draft` qui sont nettoyés en fin de séance. Retourne True si
    quelque chose a été retiré."""
    notes = prog_dict.get("_session_notes")
    if not isinstance(notes, dict) or not notes:
        return False
    today = today or logical_today_paris()
    cutoff = (today - timedelta(days=SESSION_NOTES_KEEP_DAYS)).strftime("%Y-%m-%d")
    stale = []
    for k in notes:
        date_part = str(k).rsplit("|", 1)[-1]
        if _parse_date(date_part) is None or date_part < cutoff:
            stale.append(k)
    for k in stale:
        notes.pop(k, None)
    return bool(stale)
