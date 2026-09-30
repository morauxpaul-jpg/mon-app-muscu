"""Les conversations du coach — `coach_messages` et `coach_conversations`."""
import datetime as _dt

from core.db_base import _fetch_all, get_client

# ── Messages du coach (migration v26) ────────────────────────────
def list_coach_messages(user_id: str, conversation_id: str | None = None,
                         limit: int = 50) -> list[dict]:
    """Derniers messages du coach (rôle, content, created_at) en ordre
    chronologique. Si `conversation_id` est fourni, ne renvoie que les messages
    de cette conversation."""
    client = get_client()
    q = (
        client.table("coach_messages")
        .select("role, content, created_at")
        .eq("user_id", user_id)
    )
    if conversation_id:
        q = q.eq("conversation_id", conversation_id)
    resp = q.order("created_at", desc=True).limit(limit).execute()
    rows = list(resp.data or [])
    rows.reverse()
    return rows


def insert_coach_message(user_id: str, role: str, content: str,
                         conversation_id: str | None = None) -> None:
    if role not in ("user", "assistant"):
        raise ValueError(f"role invalide: {role}")
    client = get_client()
    row = {"user_id": user_id, "role": role, "content": content}
    if conversation_id:
        row["conversation_id"] = conversation_id
    try:
        client.table("coach_messages").insert(row).execute()
    except Exception:
        # Repli si la colonne conversation_id n'existe pas encore (migration
        # v26 non appliquée) : on insère au moins le message en mode legacy.
        if conversation_id:
            row.pop("conversation_id", None)
            client.table("coach_messages").insert(row).execute()
        else:
            raise


def export_coach(user_id: str) -> dict:
    """Toutes les conversations et tous les messages du coach (export RGPD)."""
    client = get_client()
    conversations = _fetch_all(lambda: (
        client.table("coach_conversations").select("id, title, updated_at")
        .eq("user_id", user_id).order("id")
    ))
    messages = _fetch_all(lambda: (
        client.table("coach_messages").select("conversation_id, role, content, created_at")
        .eq("user_id", user_id).order("id")
    ))
    return {"conversations": conversations, "messages": messages}


def clear_coach_messages(user_id: str) -> None:
    client = get_client()
    client.table("coach_messages").delete().eq("user_id", user_id).execute()


# ── Conversations du coach (migration v26) ───────────────────────────────
def list_coach_conversations(user_id: str, limit: int = 50) -> list[dict]:
    """Conversations du user, les plus récentes d'abord (id, title, updated_at)."""
    client = get_client()
    resp = (
        client.table("coach_conversations")
        .select("id, title, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(resp.data or [])


def create_coach_conversation(user_id: str, title: str = "Nouvelle conversation") -> str | None:
    """Crée une conversation et renvoie son id (ou None si échec)."""
    client = get_client()
    title = (title or "Nouvelle conversation").strip()[:80] or "Nouvelle conversation"
    resp = (
        client.table("coach_conversations")
        .insert({"user_id": user_id, "title": title})
        .execute()
    )
    rows = list(resp.data or [])
    return rows[0]["id"] if rows else None


def rename_coach_conversation(user_id: str, conversation_id: str, title: str) -> None:
    client = get_client()
    title = (title or "").strip()[:80] or "Sans titre"
    (
        client.table("coach_conversations")
        .update({"title": title})
        .eq("user_id", user_id)
        .eq("id", conversation_id)
        .execute()
    )


def touch_coach_conversation(user_id: str, conversation_id: str) -> None:
    """Met à jour updated_at pour faire remonter la conversation en tête de liste."""
    import datetime as _dt
    client = get_client()
    (
        client.table("coach_conversations")
        .update({"updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat()})
        .eq("user_id", user_id)
        .eq("id", conversation_id)
        .execute()
    )


def delete_coach_conversation(user_id: str, conversation_id: str) -> None:
    """Supprime une conversation et ses messages (ON DELETE CASCADE)."""
    client = get_client()
    (
        client.table("coach_conversations")
        .delete()
        .eq("user_id", user_id)
        .eq("id", conversation_id)
        .execute()
    )
