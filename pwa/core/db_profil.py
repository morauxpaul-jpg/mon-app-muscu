"""Profil, onboarding et poids de corps — la table `profiles`.

Le profil porte le tier VIP : son cache a un TTL court pour qu'un passage PRO
se propage vite. Le poids de corps est ici parce qu'il sert au profil (les
standards de force en dépendent) autant qu'au suivi.
"""
import logging

from core import db_base
from core.db_base import _cache_get, _cache_invalidate, _cache_set, get_client

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
# Profil (Phase 4 — onboarding)
# ────────────────────────────────────────────────────────────

def get_profile(user_id: str) -> dict:
    """Profil (tier, prénom, poids, quotas…). Cache court (_PROFILE_TTL) :
    lu par before_request à chaque requête d'un FREE + par la plupart des
    pages — sans cache c'était un aller-retour Supabase par appel."""
    key = f"profile:{user_id}"
    cached = _cache_get(key, db_base._PROFILE_TTL)
    if cached is not None:
        return dict(cached)
    client = get_client()
    resp = (
        client.table("profiles")
        .select("*")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    data = (resp.data if resp else None) or {}
    _cache_set(key, data)
    return dict(data)


# Colonnes de `profiles` ajoutées par des migrations récentes. Si l'une manque
# (migration pas encore appliquée), l'upsert entier échouerait — on la retire
# et on réessaie plutôt que de perdre l'écriture.
_PROFILE_OPTIONAL_COLS = ("coach_memory",)


def _profile_upsert(user_id: str, payload: dict) -> None:
    """Toute écriture de profil passe ici : upsert + invalidation du cache."""
    client = get_client()
    try:
        client.table("profiles").upsert({"id": user_id, **payload}).execute()
    except Exception as e:
        missing = [c for c in _PROFILE_OPTIONAL_COLS
                   if c in payload and c in str(e).lower()]
        if not missing:
            raise
        logger.warning("profiles : colonne(s) %s absente(s) — écriture partielle", missing)
        reduced = {k: v for k, v in payload.items() if k not in missing}
        if reduced:
            client.table("profiles").upsert({"id": user_id, **reduced}).execute()
    _cache_invalidate(f"profile:{user_id}")


def save_profile(user_id: str, fields: dict):
    """Upsert sur public.profiles (id = user_id). Phase 4 : doit pouvoir
    créer la row si elle n'existe pas encore (nouveau user qui passe
    l'onboarding pour la première fois)."""
    _profile_upsert(user_id, fields)


# ────────────────────────────────────────────────────────────
# Onboarding (Phase 4)
# ────────────────────────────────────────────────────────────

def get_onboarding(user_id: str) -> dict:
    """Retourne la row onboarding de l'user, ou {} si jamais complétée.
    Cache 60 s (ne change qu'au (re)onboarding)."""
    key = f"onboarding:{user_id}"
    cached = _cache_get(key)
    if cached is not None:
        return dict(cached)
    client = get_client()
    resp = (
        client.table("onboarding")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    data = (resp.data if resp else None) or {}
    _cache_set(key, data)
    return dict(data)


def save_onboarding(user_id: str, fields: dict):
    """Upsert sur public.onboarding. Les champs attendus :
    prenom, age, sexe, niveau, frequence, objectif, equipement."""
    client = get_client()
    payload = {"user_id": user_id, **fields}
    client.table("onboarding").upsert(payload).execute()
    _cache_invalidate(f"onboarding:{user_id}")

# ────────────────────────────────────────────────────────────
# Poids corporel (migration v33) — une pesée par jour
# ────────────────────────────────────────────────────────────

def list_body_weight(user_id: str, limit: int = 400) -> list[dict]:
    """Pesées de l'user, de la plus ancienne à la plus récente :
    [{date, poids_kg}]. `limit` borne les plus récentes."""
    client = get_client()
    resp = (
        client.table("body_weight")
        .select("date, poids_kg")
        .eq("user_id", user_id)
        .order("date", desc=True)
        .limit(limit)
        .execute()
    )
    rows = resp.data or []
    out = [{"date": str(r.get("date") or "")[:10], "poids_kg": float(r.get("poids_kg") or 0)}
           for r in rows]
    out.sort(key=lambda r: r["date"])
    return out


def upsert_body_weight(user_id: str, date_str: str, poids_kg: float) -> None:
    """Enregistre (ou remplace) la pesée du jour `date_str` (YYYY-MM-DD)."""
    client = get_client()
    client.table("body_weight").upsert({
        "user_id": user_id,
        "date": date_str,
        "poids_kg": round(float(poids_kg), 1),
    }, on_conflict="user_id,date").execute()


def delete_body_weight(user_id: str, date_str: str) -> None:
    client = get_client()
    (
        client.table("body_weight").delete()
        .eq("user_id", user_id)
        .eq("date", date_str)
        .execute()
    )
