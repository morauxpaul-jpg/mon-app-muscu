"""Les repas de la journée — la table `nutrition`.

Lecture, ajout, suppression, et les deux sommes (jour et intervalle) qui
alimentent les compteurs de macros.
"""
from core.db_base import get_client

# ────────────────────────────────────────────────────────────
# Nutrition (Prompt C)
# ────────────────────────────────────────────────────────────

def list_nutrition(user_id: str, date_str: str) -> list[dict]:
    """Tous les repas loggés à une date donnée (ordre id)."""
    client = get_client()
    resp = (
        client.table("nutrition")
        .select("*")
        .eq("user_id", user_id)
        .eq("date", date_str)
        .order("id")
        .execute()
    )
    return resp.data or []


def insert_nutrition(user_id: str, row: dict) -> None:
    """Ajoute un repas (date, meal_type, calories, protein, carbs, fat, note)."""
    client = get_client()
    payload = {"user_id": user_id, **row}
    client.table("nutrition").insert(payload).execute()


def delete_nutrition(user_id: str, entry_id: int) -> None:
    client = get_client()
    (
        client.table("nutrition").delete()
        .eq("user_id", user_id)
        .eq("id", int(entry_id))
        .execute()
    )

# ── Sommes de macros (jour, intervalle) ──────────────────────────
def sum_nutrition_day(user_id: str, date_str: str) -> dict:
    rows = list_nutrition(user_id, date_str)
    out = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    for r in rows:
        out["calories"] += int(r.get("calories") or 0)
        out["protein"] += int(r.get("protein") or 0)
        out["carbs"] += int(r.get("carbs") or 0)
        out["fat"] += int(r.get("fat") or 0)
    return out


def sum_nutrition_range(user_id: str, date_from: str, date_to: str) -> dict:
    """Totaux nutrition par jour sur une plage de dates. Retourne {date_str: {calories, protein, carbs, fat}}."""
    client = get_client()
    resp = (
        client.table("nutrition")
        .select("date, calories, protein, carbs, fat")
        .eq("user_id", user_id)
        .gte("date", date_from)
        .lte("date", date_to)
        .execute()
    )
    by_date = {}
    for r in (resp.data or []):
        d = r.get("date") or ""
        entry = by_date.setdefault(d, {"calories": 0, "protein": 0, "carbs": 0, "fat": 0})
        entry["calories"] += int(r.get("calories") or 0)
        entry["protein"] += int(r.get("protein") or 0)
        entry["carbs"] += int(r.get("carbs") or 0)
        entry["fat"] += int(r.get("fat") or 0)
    return by_date
