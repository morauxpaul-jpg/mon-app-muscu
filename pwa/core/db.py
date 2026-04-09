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
import time
from typing import Optional

from supabase import create_client, Client

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
_TTL = 600.0


def _cache_get(key: str):
    entry = _data_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _TTL:
        return entry["value"]
    return None


def _cache_set(key: str, value):
    _data_cache[key] = {"value": value, "ts": time.time()}


def _cache_invalidate(key: str):
    _data_cache.pop(key, None)


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
    clear+update du Sheet). Simple et cohérent avec l'usage existant."""
    client = get_client()
    client.table("history").delete().eq("user_id", user_id).execute()
    if rows:
        payload = [_row_to_supabase(user_id, r) for r in rows]
        for i in range(0, len(payload), 500):
            client.table("history").insert(payload[i:i + 500]).execute()
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
    hist = get_hist(user_id)
    kept = [r for r in hist
            if not (r["Semaine"] == semaine and r["Séance"] == seance and r["Exercice"] == exercice)]
    save_hist(user_id, kept + new_rows)


def delete_exo_rows(user_id: str, semaine: int, seance: str, exercice: str):
    hist = get_hist(user_id)
    kept = [r for r in hist
            if not (r["Semaine"] == semaine and r["Séance"] == seance and r["Exercice"] == exercice)]
    save_hist(user_id, kept)


def delete_session_rows(user_id: str, semaine: int, seance: str):
    hist = get_hist(user_id)
    kept = [r for r in hist if not (r["Semaine"] == semaine and r["Séance"] == seance)]
    save_hist(user_id, kept)


def mark_session_missed(user_id: str, semaine: int, seance_name: str, date_str: str):
    hist = get_hist(user_id)
    already = any(r for r in hist
                  if r["Date"] == date_str and r["Exercice"] == "SESSION"
                  and (r["Séance"] == seance_name or seance_name == "Séance manquée"))
    if already:
        return
    hist.append({
        "Semaine": semaine,
        "Séance": seance_name,
        "Exercice": "SESSION",
        "Série": 1,
        "Reps": 0,
        "Poids": 0.0,
        "Remarque": "SÉANCE MANQUÉE 🚩",
        "Muscle": "Autre",
        "Date": date_str,
    })
    save_hist(user_id, hist)


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
