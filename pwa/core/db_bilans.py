"""Les bilans de séance — la table `session_notes` (migration v34).

Avant cette migration les bilans vivaient dans le blob du programme. Le module
tolère l'absence de la colonne `duration_min` (migration v35) pour qu'une base
en retard n'empêche pas d'écrire un bilan.
"""
import datetime as _dt
import logging

from core.db_base import _fetch_all, get_client
from core.db_historique import _norm_date

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
# Bilans de séance (migration v34 : table session_notes, une ligne par
# (user, date, séance)). Avant la migration, les bilans vivaient dans
# programs.data["_session_notes"] avec une purge à 84 jours — l'appelant
# (routes/seance.py) garde ce repli si la table est absente.
# ────────────────────────────────────────────────────────────

# Colonne ajoutée par la migration v35 ; sans elle on écrit le bilan sans durée.
_session_duration_supported = True


def _mark_duration_unsupported():
    global _session_duration_supported
    _session_duration_supported = False
    logger.warning("session_notes.duration_min absente (migration v35 ?) "
                   "— durée de séance non enregistrée")


def _session_note_columns() -> str:
    base = "rating, comment, updated_at"
    return base + ", duration_min" if _session_duration_supported else base


def upsert_session_note(user_id: str, date_str: str, seance: str,
                        rating: int | None, comment: str | None,
                        duration_min: int | None = None) -> None:
    client = get_client()
    payload = {
        "user_id": user_id,
        "date": _norm_date(date_str),
        "seance": seance,
        "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    # Seuls les champs fournis s'écrivent. Terminer une 2e fois en « Passer »
    # (durée seule) remettait note et commentaire à vide (audit du 03/10, M1).
    if rating:
        payload["rating"] = int(rating)
    if comment and comment.strip():
        payload["comment"] = comment[:500]
    if duration_min and _session_duration_supported:
        payload["duration_min"] = int(duration_min)
    try:
        client.table("session_notes").upsert(
            payload, on_conflict="user_id,date,seance").execute()
    except Exception as e:
        # Colonne duration_min absente (migration v35 non appliquée) : on
        # ré-essaie sans elle plutôt que de perdre la note et le commentaire.
        if "duration_min" not in str(e).lower():
            raise
        _mark_duration_unsupported()
        payload.pop("duration_min", None)
        client.table("session_notes").upsert(
            payload, on_conflict="user_id,date,seance").execute()


def get_session_note(user_id: str, date_str: str, seance: str) -> dict | None:
    """{rating, comment, duration_min, ts} ou None. Lève si la table est
    absente (repli géré par l'appelant)."""
    client = get_client()
    try:
        resp = (
            client.table("session_notes")
            .select(_session_note_columns())
            .eq("user_id", user_id)
            .eq("date", _norm_date(date_str))
            .eq("seance", seance)
            .limit(1)
            .execute()
        )
    except Exception as e:
        if "duration_min" not in str(e).lower():
            raise
        _mark_duration_unsupported()
        resp = (
            client.table("session_notes")
            .select(_session_note_columns())
            .eq("user_id", user_id)
            .eq("date", _norm_date(date_str))
            .eq("seance", seance)
            .limit(1)
            .execute()
        )
    rows = resp.data or []
    if not rows:
        return None
    r = rows[0]
    out = {"ts": str(r.get("updated_at") or "")[:16].replace("T", " ")}
    if r.get("rating"):
        out["rating"] = int(r["rating"])
    if r.get("comment"):
        out["comment"] = r["comment"]
    if r.get("duration_min"):
        out["duration_min"] = int(r["duration_min"])
    return out


def list_session_notes(user_id: str) -> list[dict]:
    """Tous les bilans de l'user (export, stats)."""
    client = get_client()
    cols = "date, seance, rating, comment"
    if _session_duration_supported:
        cols += ", duration_min"
    try:
        rows = _fetch_all(lambda: (
            client.table("session_notes").select(cols)
            .eq("user_id", user_id).order("date")
        ))
    except Exception as e:
        if "duration_min" not in str(e).lower():
            raise
        _mark_duration_unsupported()
        rows = _fetch_all(lambda: (
            client.table("session_notes").select("date, seance, rating, comment")
            .eq("user_id", user_id).order("date")
        ))
    return [{"date": str(r.get("date") or "")[:10], "seance": r.get("seance") or "",
             "rating": r.get("rating"), "comment": r.get("comment"),
             "duration_min": r.get("duration_min")} for r in rows]


def rename_session_notes(user_id: str, old_name: str, new_name: str) -> int:
    """Suit le renommage d'une séance : sans lui, ses bilans restaient sous
    l'ancien nom, introuvables (audit du 03/10, M2)."""
    if not old_name or old_name == new_name:
        return 0
    resp = (get_client().table("session_notes").update({"seance": new_name})
            .eq("user_id", user_id).eq("seance", old_name).execute())
    return len(resp.data or [])
