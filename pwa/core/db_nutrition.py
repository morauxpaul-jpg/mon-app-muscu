"""Les repas de la journée — la table `nutrition`.

Lecture, ajout, suppression, et les deux sommes (jour et intervalle) qui
alimentent les compteurs de macros.

Une ligne = un aliment (ou un repas saisi en bloc). `grams` et `food` (valeurs
pour 100 g, migration v40) permettent de corriger une quantité après coup et
de proposer les aliments récents. Sans ces colonnes, l'écriture est retentée
sans elles : le repas est noté, seule la correction de quantité manque.
"""
import logging

from core.db_base import _fetch_all, get_client

logger = logging.getLogger(__name__)

COLONNES_V40 = ("grams", "food")


def _colonne_absente(err) -> bool:
    """Erreur PostgREST « colonne inconnue » (migration v40 pas encore passée)."""
    msg = str(err)
    return "PGRST204" in msg or "schema cache" in msg or any(
        f"'{c}'" in msg or f'"{c}"' in msg for c in COLONNES_V40)


def _sans_v40(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in COLONNES_V40}

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


def list_all_nutrition(user_id: str) -> list[dict]:
    """Tous les repas de l'utilisateur (export RGPD), paginé."""
    client = get_client()
    return _fetch_all(lambda: (
        client.table("nutrition").select("*").eq("user_id", user_id).order("id")
    ))


def insert_nutrition(user_id: str, row: dict) -> None:
    """Ajoute un repas (date, meal_type, calories, protein, carbs, fat, note)."""
    insert_nutrition_rows(user_id, [row])


def insert_nutrition_rows(user_id: str, rows: list[dict]) -> None:
    """Ajoute plusieurs lignes en une requête (un repas détaillé par aliment)."""
    if not rows:
        return
    client = get_client()
    payload = [{"user_id": user_id, **r} for r in rows]
    try:
        client.table("nutrition").insert(payload).execute()
    except Exception as e:
        if not (any(c in r for r in rows for c in COLONNES_V40) and _colonne_absente(e)):
            raise
        logger.warning("nutrition sans colonnes v40, écriture réduite : %s", e)
        client.table("nutrition").insert([_sans_v40(p) for p in payload]).execute()


def get_nutrition(user_id: str, entry_id: int) -> dict | None:
    client = get_client()
    resp = (
        client.table("nutrition").select("*")
        .eq("user_id", user_id).eq("id", int(entry_id))
        .limit(1).execute()
    )
    return (resp.data or [None])[0]


def update_nutrition(user_id: str, entry_id: int, fields: dict) -> None:
    client = get_client()

    def _ecrire(f):
        (client.table("nutrition").update(f)
         .eq("user_id", user_id).eq("id", int(entry_id)).execute())
    try:
        _ecrire(fields)
    except Exception as e:
        if not (any(c in fields for c in COLONNES_V40) and _colonne_absente(e)):
            raise
        _ecrire(_sans_v40(fields))


def list_nutrition_recents(user_id: str, since: str, limit: int = 400) -> list[dict]:
    """Lignes détaillées (avec `food`) depuis `since`, les plus récentes
    d'abord : de quoi proposer « tes aliments habituels »."""
    client = get_client()
    resp = (
        client.table("nutrition").select("id, date, grams, food")
        .eq("user_id", user_id).gte("date", since)
        .order("id", desc=True).limit(limit).execute()
    )
    return resp.data or []


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
    """Totaux nutrition par jour sur une plage de dates.
    Retourne {date_str: {calories, protein, carbs, fat, slots: [meal_type…]}}."""
    client = get_client()
    resp = (
        client.table("nutrition")
        .select("date, meal_type, calories, protein, carbs, fat")
        .eq("user_id", user_id)
        .gte("date", date_from)
        .lte("date", date_to)
        .execute()
    )
    by_date = {}
    for r in (resp.data or []):
        d = r.get("date") or ""
        entry = by_date.setdefault(d, {"calories": 0, "protein": 0, "carbs": 0, "fat": 0, "slots": []})
        if r.get("meal_type") and r["meal_type"] not in entry["slots"]:
            entry["slots"].append(r["meal_type"])
        entry["calories"] += int(r.get("calories") or 0)
        entry["protein"] += int(r.get("protein") or 0)
        entry["carbs"] += int(r.get("carbs") or 0)
        entry["fat"] += int(r.get("fat") or 0)
    return by_date
