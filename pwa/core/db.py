"""Couche d'accès Supabase — remplace core/sheets.py en Phase 3.

Phase 3 choix d'archi : le backend Flask utilise la clé `service_role` (bypass
RLS) et filtre manuellement **chaque** requête par `user_id`. L'authentification
de l'utilisateur se fait via Supabase Google OAuth côté client puis un "bridge"
qui valide le JWT et pose `user_id` dans la session Flask. Toutes les fonctions
de ce module exigent explicitement un `user_id`.

Config : deux variables d'env requises
  - SUPABASE_URL
  - SUPABASE_SERVICE_ROLE_KEY   (jamais exposée au client)
"""
import os
import json
import logging
import time
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)

def _env(name: str) -> str:
    v = os.getenv(name, "") or ""
    return v.strip().strip('"').strip("'").lstrip("=").strip()


_SUPABASE_URL = _env("SUPABASE_URL")
_SUPABASE_SERVICE_KEY = _env("SUPABASE_SERVICE_ROLE_KEY")

_client: Optional[Client] = None


def get_client() -> Client:
    """Client Supabase process-wide avec clé service_role.
    ⚠️ bypass RLS : tous les appels DOIVENT filtrer explicitement par user_id."""
    global _client
    if _client is None:
        if not _SUPABASE_URL or not _SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants dans l'environnement."
            )
        _client = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_KEY)
    return _client


# ── Cache mémoire process-wide (TTL 10 min), clé par user_id ──
_data_cache: dict = {}
_TTL = 60.0


def _cache_get(key: str):
    entry = _data_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _TTL:
        return entry["value"]
    return None


def _cache_set(key: str, value):
    _data_cache[key] = {"value": value, "ts": time.time()}


def _cache_invalidate(key: str):
    _data_cache.pop(key, None)


def clear_user_cache(user_id: str):
    """Invalide explicitement toutes les entrées cache d'un utilisateur.
    Appelé après chaque save réussi pour éviter les séances vides au reload."""
    _data_cache.pop(f"hist:{user_id}", None)
    _data_cache.pop(f"prog:{user_id}", None)


# ────────────────────────────────────────────────────────────
# Historique des séries
# ────────────────────────────────────────────────────────────

def get_hist(user_id: str) -> list[dict]:
    """Retourne l'historique de l'user sous la même forme que sheets.get_hist
    (liste de dicts avec clés Semaine/Séance/Exercice/...)."""
    key = f"hist:{user_id}"
    cached = _cache_get(key)
    if cached is not None:
        return [dict(r) for r in cached]

    client = get_client()
    resp = (
        client.table("history")
        .select("*")
        .eq("user_id", user_id)
        .order("id")
        .execute()
    )
    rows = resp.data or []
    cleaned = [{
        "Semaine": int(r.get("semaine") or 1),
        "Séance": r.get("seance") or "",
        "Exercice": r.get("exercice") or "",
        "Série": int(r.get("serie") or 1),
        "Reps": int(r.get("reps") or 0),
        "Poids": float(r.get("poids") or 0),
        "Remarque": r.get("remarque") or "",
        "Muscle": r.get("muscle") or "",
        "Date": str(r.get("date") or ""),
    } for r in rows]
    _cache_set(key, cleaned)
    return [dict(r) for r in cleaned]


def save_hist(user_id: str, rows: list[dict]):
    """Réécrit tout l'historique de l'user (équivalent du write-all
    clear+update du Sheet). Garde une copie de secours en mémoire :
    si l'insert échoue après le delete, on tente de restaurer l'ancien
    historique pour éviter une perte de données."""
    client = get_client()

    # 1. Sauvegarde des anciennes données avant suppression
    backup_resp = (
        client.table("history")
        .select("*")
        .eq("user_id", user_id)
        .order("id")
        .execute()
    )
    backup_rows = backup_resp.data or []

    # 2. Delete + re-insert avec rollback en cas d'échec
    try:
        client.table("history").delete().eq("user_id", user_id).execute()
        if rows:
            payload = [_row_to_supabase(user_id, r) for r in rows]
            for i in range(0, len(payload), 500):
                client.table("history").insert(payload[i:i + 500]).execute()
    except Exception as e:
        logger.error("save_hist FAILED user=%s: %s", user_id, e)
        try:
            if backup_rows:
                for i in range(0, len(backup_rows), 500):
                    client.table("history").insert(backup_rows[i:i + 500]).execute()
                logger.info("save_hist rollback ok user=%s rows=%d", user_id, len(backup_rows))
            else:
                logger.info("save_hist rollback: backup empty user=%s", user_id)
        except Exception as e2:
            logger.error("save_hist rollback FAILED user=%s: %s", user_id, e2)
        raise

    _cache_invalidate(f"hist:{user_id}")


def _row_to_supabase(user_id: str, r: dict) -> dict:
    date_val = r.get("Date")
    return {
        "user_id": user_id,
        "semaine": int(r.get("Semaine") or 1),
        "seance": r.get("Séance") or "",
        "exercice": r.get("Exercice") or "",
        "serie": int(r.get("Série") or 1),
        "reps": int(r.get("Reps") or 0),
        "poids": float(r.get("Poids") or 0),
        "remarque": r.get("Remarque") or "",
        "muscle": r.get("Muscle") or "",
        "date": date_val if date_val else None,
    }


# ────────────────────────────────────────────────────────────
# Programme (stocké en JSON dans programs.data)
# ────────────────────────────────────────────────────────────

def get_prog(user_id: str) -> dict:
    key = f"prog:{user_id}"
    cached = _cache_get(key)
    if cached is not None:
        return json.loads(json.dumps(cached))

    client = get_client()
    resp = (
        client.table("programs")
        .select("data")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    data = (resp.data or {}).get("data") or {} if resp else {}
    _cache_set(key, data)
    return json.loads(json.dumps(data))


def save_prog(user_id: str, prog_dict: dict):
    client = get_client()
    client.table("programs").upsert({
        "user_id": user_id,
        "data": prog_dict,
    }).execute()
    _cache_invalidate(f"prog:{user_id}")


# ────────────────────────────────────────────────────────────
# Opérations ciblées (réplique de core/sheets.py)
# ────────────────────────────────────────────────────────────

def replace_exo_rows(user_id: str, semaine: int, seance: str, exercice: str, new_rows: list[dict]):
    """Supprime les lignes d'un (semaine, séance, exercice) précis et réinsère
    les nouvelles lignes en une seule requête. Pas de delete-all global."""
    client = get_client()
    (
        client.table("history").delete()
        .eq("user_id", user_id)
        .eq("semaine", int(semaine))
        .eq("seance", seance)
        .eq("exercice", exercice)
        .execute()
    )
    if new_rows:
        payload = [_row_to_supabase(user_id, r) for r in new_rows]
        client.table("history").insert(payload).execute()
    _cache_invalidate(f"hist:{user_id}")


def delete_exo_rows(user_id: str, semaine: int, seance: str, exercice: str):
    client = get_client()
    (
        client.table("history").delete()
        .eq("user_id", user_id)
        .eq("semaine", int(semaine))
        .eq("seance", seance)
        .eq("exercice", exercice)
        .execute()
    )
    _cache_invalidate(f"hist:{user_id}")


def delete_session_rows(user_id: str, semaine: int, seance: str):
    client = get_client()
    (
        client.table("history").delete()
        .eq("user_id", user_id)
        .eq("semaine", int(semaine))
        .eq("seance", seance)
        .execute()
    )
    _cache_invalidate(f"hist:{user_id}")


def mark_session_missed(user_id: str, semaine: int, seance_name: str, date_str: str):
    """Insère une ligne SESSION "manquée" à la date donnée si aucune n'existe
    déjà. Utilise une requête ciblée au lieu de relire tout l'historique."""
    client = get_client()
    resp = (
        client.table("history").select("id")
        .eq("user_id", user_id)
        .eq("date", date_str)
        .eq("exercice", "SESSION")
        .limit(1)
        .execute()
    )
    if resp.data:
        return
    row = {
        "Semaine": semaine,
        "Séance": seance_name,
        "Exercice": "SESSION",
        "Série": 1,
        "Reps": 0,
        "Poids": 0.0,
        "Remarque": "SÉANCE MANQUÉE",
        "Muscle": "Autre",
        "Date": date_str,
    }
    client.table("history").insert(_row_to_supabase(user_id, row)).execute()
    _cache_invalidate(f"hist:{user_id}")


# ────────────────────────────────────────────────────────────
# Profil (Phase 4 — onboarding)
# ────────────────────────────────────────────────────────────

def get_profile(user_id: str) -> dict:
    client = get_client()
    resp = (
        client.table("profiles")
        .select("*")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return (resp.data if resp else None) or {}


def save_profile(user_id: str, fields: dict):
    """Upsert sur public.profiles (id = user_id). Phase 4 : doit pouvoir
    créer la row si elle n'existe pas encore (nouveau user qui passe
    l'onboarding pour la première fois)."""
    client = get_client()
    payload = {"id": user_id, **fields}
    client.table("profiles").upsert(payload).execute()


# ────────────────────────────────────────────────────────────
# Onboarding (Phase 4)
# ────────────────────────────────────────────────────────────

def get_onboarding(user_id: str) -> dict:
    """Retourne la row onboarding de l'user, ou {} si jamais complétée."""
    client = get_client()
    resp = (
        client.table("onboarding")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    return (resp.data if resp else None) or {}


def save_onboarding(user_id: str, fields: dict):
    """Upsert sur public.onboarding. Les champs attendus :
    prenom, age, sexe, niveau, frequence, objectif, equipement."""
    client = get_client()
    payload = {"user_id": user_id, **fields}
    client.table("onboarding").upsert(payload).execute()


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


def list_all_users_with_tier() -> list[dict]:
    """Retourne la liste de tous les users (admin). Combine auth.users (email)
    et public.profiles (tier). Réservé au backend admin — utilise service_role.
    """
    client = get_client()
    # auth.users via Admin API
    try:
        users_resp = client.auth.admin.list_users()
        # Le SDK peut retourner soit une liste directe soit un objet .users
        auth_users = getattr(users_resp, "users", None) or users_resp or []
    except Exception as e:
        logger.error("list_all_users_with_tier auth FAILED: %s", e)
        auth_users = []

    # profiles
    try:
        prof_resp = client.table("profiles").select("id, tier, prenom").execute()
        profiles = {p["id"]: p for p in (prof_resp.data or [])}
    except Exception as e:
        logger.error("list_all_users_with_tier profiles FAILED: %s", e)
        profiles = {}

    out = []
    for u in auth_users:
        uid = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
        email = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else "")
        created = getattr(u, "created_at", None) or (u.get("created_at") if isinstance(u, dict) else "")
        p = profiles.get(uid) or {}
        out.append({
            "id": uid,
            "email": email or "",
            "created_at": str(created or "")[:10],
            "tier": (p.get("tier") or "free"),
            "prenom": (p.get("prenom") or ""),
        })
    out.sort(key=lambda u: u["created_at"], reverse=True)
    return out


def set_user_tier(user_id: str, tier: str) -> None:
    """Upsert profiles.tier pour un user. tier ∈ {'free', 'vip'}."""
    if tier not in ("free", "vip"):
        raise ValueError(f"tier invalide: {tier}")
    client = get_client()
    client.table("profiles").upsert({"id": user_id, "tier": tier}).execute()


def list_coach_messages(user_id: str, limit: int = 50) -> list[dict]:
    """Derniers messages du coach (rôle, content, created_at) en ordre chronologique."""
    client = get_client()
    resp = (
        client.table("coach_messages")
        .select("role, content, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = list(resp.data or [])
    rows.reverse()
    return rows


def insert_coach_message(user_id: str, role: str, content: str) -> None:
    if role not in ("user", "assistant"):
        raise ValueError(f"role invalide: {role}")
    client = get_client()
    client.table("coach_messages").insert({
        "user_id": user_id,
        "role": role,
        "content": content,
    }).execute()


def clear_coach_messages(user_id: str) -> None:
    client = get_client()
    client.table("coach_messages").delete().eq("user_id", user_id).execute()


# ────────────────────────────────────────────────────────────
# Admin — stats globales + fiche user
# ────────────────────────────────────────────────────────────

def get_admin_stats() -> dict:
    """Agrégats cross-users pour le dashboard admin.
    Retourne : total_rows, total_tonnage, total_seances (distinct user+date+seance),
    active_7d, active_30d (distinct user_id avec date récente)."""
    import datetime as _dt
    client = get_client()
    try:
        resp = client.table("history").select("user_id, date, seance, reps, poids").execute()
        rows = resp.data or []
    except Exception as e:
        logger.error("get_admin_stats FAILED: %s", e)
        return {"total_rows": 0, "total_tonnage": 0, "total_seances": 0, "active_7d": 0, "active_30d": 0}

    today = _dt.date.today()
    cutoff_7 = (today - _dt.timedelta(days=7)).isoformat()
    cutoff_30 = (today - _dt.timedelta(days=30)).isoformat()

    tonnage = 0.0
    sessions = set()
    a7, a30 = set(), set()
    for r in rows:
        reps = int(r.get("reps") or 0)
        poids = float(r.get("poids") or 0)
        tonnage += reps * poids
        d = str(r.get("date") or "")[:10]
        uid = r.get("user_id")
        if uid and d:
            sessions.add((uid, d, r.get("seance") or ""))
            if d >= cutoff_30:
                a30.add(uid)
                if d >= cutoff_7:
                    a7.add(uid)
    return {
        "total_rows": len(rows),
        "total_tonnage": int(tonnage),
        "total_seances": len(sessions),
        "active_7d": len(a7),
        "active_30d": len(a30),
    }


def get_user_details(user_id: str) -> dict:
    """Fiche détaillée d'un user pour l'admin."""
    import datetime as _dt
    client = get_client()
    # Historique
    try:
        resp = client.table("history").select("date, seance, reps, poids").eq("user_id", user_id).execute()
        rows = resp.data or []
    except Exception as e:
        logger.error("get_user_details history FAILED user=%s: %s", user_id, e)
        rows = []
    tonnage = 0.0
    sessions = set()
    last_date = ""
    for r in rows:
        tonnage += int(r.get("reps") or 0) * float(r.get("poids") or 0)
        d = str(r.get("date") or "")[:10]
        if d:
            sessions.add((d, r.get("seance") or ""))
            if d > last_date:
                last_date = d
    # Profil + quota coach
    try:
        presp = client.table("profiles").select("tier, prenom, coach_quota_date, coach_quota_count").eq("id", user_id).maybe_single().execute()
        prof = (presp.data if presp else None) or {}
    except Exception as e:
        logger.error("get_user_details profile FAILED user=%s: %s", user_id, e)
        prof = {}
    # Nb msg coach total
    try:
        cresp = client.table("coach_messages").select("id", count="exact").eq("user_id", user_id).execute()
        coach_count = int(getattr(cresp, "count", None) or 0)
    except Exception as e:
        logger.error("get_user_details coach FAILED user=%s: %s", user_id, e)
        coach_count = 0
    today = _dt.date.today().isoformat()
    q_date = str(prof.get("coach_quota_date") or "")
    q_used = int(prof.get("coach_quota_count") or 0) if q_date == today else 0
    return {
        "user_id": user_id,
        "tier": prof.get("tier") or "free",
        "prenom": prof.get("prenom") or "",
        "total_rows": len(rows),
        "total_tonnage": int(tonnage),
        "total_seances": len(sessions),
        "last_date": last_date,
        "coach_msgs_total": coach_count,
        "coach_quota_used": q_used,
    }


def reset_user_coach_quota(user_id: str) -> None:
    """Remet à 0 le quota coach IA du jour pour un user (admin)."""
    client = get_client()
    client.table("profiles").upsert({"id": user_id, "coach_quota_count": 0}).execute()


def sum_nutrition_day(user_id: str, date_str: str) -> dict:
    rows = list_nutrition(user_id, date_str)
    out = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    for r in rows:
        out["calories"] += int(r.get("calories") or 0)
        out["protein"] += int(r.get("protein") or 0)
        out["carbs"] += int(r.get("carbs") or 0)
        out["fat"] += int(r.get("fat") or 0)
    return out
