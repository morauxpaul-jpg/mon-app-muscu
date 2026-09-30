"""Bilan d'une séance (note, commentaire, durée) : lecture et écriture.

Sorti de routes/seance.py (audit du 30/09, M11) : la page de séance le lit,
la fin de séance l'écrit, le debrief le relit. Table `session_notes`
(migration v34), repli sur l'ancien stockage dans le programme.
"""
import logging

from core.seance_calques import _purge_old_session_notes

logger = logging.getLogger(__name__)


def _save_session_note(prog, date_str, seance_name, note):
    """Écrit le bilan dans la table `session_notes` (migration v34). Repli sur
    l'ancien stockage dans le programme si la table n'existe pas encore."""
    from core.data import upsert_session_note
    try:
        upsert_session_note(date_str, seance_name, note.get("rating"),
                            note.get("comment"), note.get("duration_min"))
        # La table a pris le relais : on purge l'ancien emplacement.
        if isinstance(prog.get("_session_notes"), dict):
            prog["_session_notes"].pop(f"{seance_name}|{date_str}", None)
            if not prog["_session_notes"]:
                prog.pop("_session_notes", None)
        return
    except Exception as e:
        logger.warning("session_notes indisponible (%s) — repli sur le programme", e)
    _purge_old_session_notes(prog)
    prog.setdefault("_session_notes", {})[f"{seance_name}|{date_str}"] = note


def _load_session_note(prog, date_str, seance_name):
    """Bilan d'une séance : table v34 d'abord, ancien stockage ensuite."""
    from core.data import get_session_note
    try:
        note = get_session_note(date_str, seance_name)
        if note:
            return note
    except Exception:
        pass
    return (prog.get("_session_notes") or {}).get(f"{seance_name}|{date_str}")
