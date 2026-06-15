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
import datetime as _dt
import os
import json
import logging
import time
from typing import Optional

from supabase import create_client, Client

from core.dates import continuous_week, week_range

logger = logging.getLogger(__name__)


def _continuous_week_of(date_str: str):
    """Index de semaine continu pour une date ISO, ou None si invalide."""
    try:
        return continuous_week(_dt.date.fromisoformat(str(date_str)[:10]))
    except (ValueError, TypeError):
        return None

def _env(name: str) -> str:
    v = os.getenv(name, "") or ""
    v = v.strip().strip('"').strip("'").lstrip("=").strip()
    if v:
        return v
    for k, val in os.environ.items():
        if k.strip() == name:
            v = val.strip().strip('"').strip("'").lstrip("=").strip()
            if v:
                return v
    return ""


_client: Optional[Client] = None


def get_client() -> Client:
    """Client Supabase process-wide avec clé service_role.
    ⚠️ bypass RLS : tous les appels DOIVENT filtrer explicitement par user_id."""
    global _client
    if _client is None:
        url = _env("SUPABASE_URL")
        key = _env("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants dans l'environnement."
            )
        _client = create_client(url, key)
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
    cleaned = []
    for r in rows:
        date_str = str(r.get("date") or "")
        # Semaine = index CONTINU recalculé depuis la date (le n° ISO stocké
        # recommence chaque année → collisions au-delà d'un an d'historique).
        # Repli sur la valeur stockée pour les rares lignes sans date.
        week = _continuous_week_of(date_str)
        if week is None:
            week = int(r.get("semaine") or 1)
        cleaned.append({
            "Semaine": week,
            "Séance": r.get("seance") or "",
            "Exercice": r.get("exercice") or "",
            "Série": int(r.get("serie") or 1),
            "Reps": int(r.get("reps") or 0),
            "Poids": float(r.get("poids") or 0),
            "Remarque": r.get("remarque") or "",
            "Muscle": r.get("muscle") or "",
            "Date": date_str,
        })
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

def _week_bounds(date_str: str):
    """(lundi, dimanche) ISO de la semaine contenant date_str.
    Lève ValueError si la date est invalide — les appelants passent toujours
    une date déjà validée par les routes."""
    return week_range(_dt.date.fromisoformat(str(date_str)[:10]))


def replace_exo_rows(user_id: str, date_str: str, seance: str, exercice: str, new_rows: list[dict]):
    """Supprime les lignes d'un (semaine-de-date, séance, exercice) précis et
    réinsère les nouvelles lignes. Le ciblage de la semaine se fait par PLAGE
    DE DATES (lun→dim) et non par la colonne `semaine` stockée : celle-ci
    contient des n° ISO historiques qui recommencent chaque année."""
    monday, sunday = _week_bounds(date_str)
    client = get_client()
    (
        client.table("history").delete()
        .eq("user_id", user_id)
        .gte("date", monday)
        .lte("date", sunday)
        .eq("seance", seance)
        .eq("exercice", exercice)
        .execute()
    )
    if new_rows:
        payload = [_row_to_supabase(user_id, r) for r in new_rows]
        client.table("history").insert(payload).execute()
    _cache_invalidate(f"hist:{user_id}")


def delete_exo_rows(user_id: str, date_str: str, seance: str, exercice: str):
    monday, sunday = _week_bounds(date_str)
    client = get_client()
    (
        client.table("history").delete()
        .eq("user_id", user_id)
        .gte("date", monday)
        .lte("date", sunday)
        .eq("seance", seance)
        .eq("exercice", exercice)
        .execute()
    )
    _cache_invalidate(f"hist:{user_id}")


def delete_session_rows(user_id: str, date_str: str, seance: str):
    monday, sunday = _week_bounds(date_str)
    client = get_client()
    (
        client.table("history").delete()
        .eq("user_id", user_id)
        .gte("date", monday)
        .lte("date", sunday)
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


# ── Stripe (abonnements Premium) ─────────────────────────────────
def set_stripe_customer(user_id: str, customer_id: str) -> None:
    """Mémorise l'ID client Stripe sur le profil (pour le portail + le mapping
    customer→user lors des webhooks d'annulation). Nécessite la colonne
    profiles.stripe_customer_id (migration v27)."""
    if not customer_id:
        return
    client = get_client()
    client.table("profiles").upsert(
        {"id": user_id, "stripe_customer_id": customer_id}
    ).execute()


def get_user_by_stripe_customer(customer_id: str) -> Optional[str]:
    """Retrouve l'user_id à partir de l'ID client Stripe (webhook annulation)."""
    if not customer_id:
        return None
    client = get_client()
    resp = (
        client.table("profiles")
        .select("id")
        .eq("stripe_customer_id", customer_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0]["id"] if rows else None


# ── Parrainage + VIP à durée limitée (migration v29) ─────────────
import hashlib as _hashlib


def vip_until_active(vip_until) -> bool:
    """True si un VIP à durée limitée (`profiles.vip_until`) est encore valide."""
    if not vip_until:
        return False
    try:
        s = str(vip_until).replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return dt > _dt.datetime.now(_dt.timezone.utc)
    except (ValueError, TypeError):
        return False


def get_or_create_referral_code(user_id: str) -> str:
    """Code de parrainage stable de l'utilisateur. Généré (déterministe, dérivé
    de l'user_id) et persisté au premier appel. Sert au lien d'invitation et à
    la résolution inverse (`get_user_by_referral_code`)."""
    client = get_client()
    try:
        resp = client.table("profiles").select("referral_code").eq("id", user_id).maybe_single().execute()
        existing = (resp.data or {}).get("referral_code") if resp else None
    except Exception as e:
        logger.error("get_or_create_referral_code read FAILED user=%s: %s", user_id, e)
        existing = None
    if existing:
        return existing
    # Code court, lisible, déterministe (base32 d'un hash de l'user_id).
    digest = _hashlib.sha1(user_id.encode("utf-8")).digest()
    import base64 as _b64
    code = _b64.b32encode(digest).decode("ascii").rstrip("=").lower()[:8]
    try:
        client.table("profiles").upsert({"id": user_id, "referral_code": code}).execute()
    except Exception as e:
        logger.error("get_or_create_referral_code write FAILED user=%s: %s", user_id, e)
    return code


def get_user_by_referral_code(code: str) -> Optional[str]:
    """Retrouve l'id du parrain à partir de son code (résolution du lien ?ref=)."""
    code = (code or "").strip().lower()
    if not code:
        return None
    client = get_client()
    try:
        resp = client.table("profiles").select("id").eq("referral_code", code).limit(1).execute()
        rows = resp.data or []
        return rows[0]["id"] if rows else None
    except Exception as e:
        logger.error("get_user_by_referral_code FAILED code=%s: %s", code, e)
        return None


def set_referred_by(user_id: str, referrer_id: str) -> None:
    """Mémorise le parrain d'un filleul (posé une seule fois côté appelant)."""
    client = get_client()
    client.table("profiles").upsert({"id": user_id, "referred_by": referrer_id}).execute()


def grant_vip_days(user_id: str, days: int) -> None:
    """Étend (cumulatif) le VIP à durée limitée : vip_until = max(now, vip_until
    courant) + days. Utilisé par le parrainage (et réutilisable pour promos)."""
    if days <= 0:
        return
    client = get_client()
    base = _dt.datetime.now(_dt.timezone.utc)
    try:
        resp = client.table("profiles").select("vip_until").eq("id", user_id).maybe_single().execute()
        cur = (resp.data or {}).get("vip_until") if resp else None
        if cur:
            s = str(cur).replace("Z", "+00:00")
            cur_dt = _dt.datetime.fromisoformat(s)
            if cur_dt.tzinfo is None:
                cur_dt = cur_dt.replace(tzinfo=_dt.timezone.utc)
            if cur_dt > base:
                base = cur_dt
    except Exception as e:
        logger.error("grant_vip_days read FAILED user=%s: %s", user_id, e)
    new_until = (base + _dt.timedelta(days=int(days))).isoformat()
    client.table("profiles").upsert({"id": user_id, "vip_until": new_until}).execute()


def count_referrals(user_id: str) -> int:
    """Nombre de filleuls (comptes ayant ce user comme `referred_by`)."""
    client = get_client()
    try:
        resp = client.table("profiles").select("id", count="exact").eq("referred_by", user_id).execute()
        return int(getattr(resp, "count", None) or 0)
    except Exception as e:
        logger.error("count_referrals FAILED user=%s: %s", user_id, e)
        return 0


def get_referred_by(user_id: str) -> Optional[str]:
    """Parrain déjà enregistré pour ce user, ou None."""
    client = get_client()
    try:
        resp = client.table("profiles").select("referred_by").eq("id", user_id).maybe_single().execute()
        return (resp.data or {}).get("referred_by") if resp else None
    except Exception as e:
        logger.error("get_referred_by FAILED user=%s: %s", user_id, e)
        return None


# ── Push web (relance des inactifs, migration v30) ───────────────
def save_push_subscription(user_id: str, sub: dict) -> None:
    """Upsert d'un abonnement push (clé = endpoint, unique). `sub` au format
    PushSubscription.toJSON() : {endpoint, keys:{p256dh, auth}}."""
    endpoint = (sub or {}).get("endpoint")
    keys = (sub or {}).get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("subscription incomplète")
    client = get_client()
    client.table("push_subscriptions").upsert(
        {"user_id": user_id, "endpoint": endpoint,
         "p256dh": keys["p256dh"], "auth": keys["auth"]},
        on_conflict="endpoint",
    ).execute()


def delete_push_subscription(endpoint: str) -> None:
    if not endpoint:
        return
    client = get_client()
    client.table("push_subscriptions").delete().eq("endpoint", endpoint).execute()


def _row_to_subscription(row: dict) -> dict:
    """Ligne DB → format attendu par pywebpush."""
    return {
        "endpoint": row.get("endpoint"),
        "keys": {"p256dh": row.get("p256dh"), "auth": row.get("auth")},
    }


def list_push_subscriptions(user_id: str) -> list[dict]:
    client = get_client()
    try:
        resp = client.table("push_subscriptions").select("*").eq("user_id", user_id).execute()
        return [_row_to_subscription(r) for r in (resp.data or [])]
    except Exception as e:
        logger.error("list_push_subscriptions FAILED user=%s: %s", user_id, e)
        return []


def get_inactive_user_ids(min_days: int = 3, max_days: int = 30) -> set:
    """user_id dont la dernière séance (perf réelle) remonte à entre `min_days`
    et `max_days` jours — cibles de relance (ni actifs, ni partis depuis trop
    longtemps). Exclut les comptes sans historique."""
    import datetime as _dt
    client = get_client()
    try:
        resp = client.table("history").select("user_id, date, reps, poids").execute()
        rows = resp.data or []
    except Exception as e:
        logger.error("get_inactive_user_ids FAILED: %s", e)
        return set()
    last_by_user: dict = {}
    for r in rows:
        if int(r.get("reps") or 0) <= 0 and float(r.get("poids") or 0) <= 0:
            continue
        uid = r.get("user_id")
        d = str(r.get("date") or "")[:10]
        if uid and d and d > last_by_user.get(uid, ""):
            last_by_user[uid] = d
    today = _dt.date.today()
    lo = (today - _dt.timedelta(days=max_days)).isoformat()
    hi = (today - _dt.timedelta(days=min_days)).isoformat()
    return {uid for uid, last in last_by_user.items() if lo <= last <= hi}


def list_push_subscriptions_for_users(user_ids: set) -> list[tuple]:
    """[(user_id, subscription_dict), …] pour un ensemble d'users (envoi groupé)."""
    if not user_ids:
        return []
    client = get_client()
    try:
        resp = client.table("push_subscriptions").select("*").execute()
        out = []
        for r in (resp.data or []):
            if r.get("user_id") in user_ids:
                out.append((r.get("user_id"), _row_to_subscription(r)))
        return out
    except Exception as e:
        logger.error("list_push_subscriptions_for_users FAILED: %s", e)
        return []


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


# ── Analytics produit (events de conversion / funnel) ────────────
def insert_event(user_id, event: str, props: dict | None = None,
                 tier: str | None = None) -> None:
    """Enregistre un event analytics (table `events`, migration v28).

    Best-effort : l'appelant (core.analytics.track) avale déjà les exceptions,
    mais on garde l'écriture minimale et tolérante (user_id peut être None)."""
    client = get_client()
    payload = {
        "user_id": user_id or None,
        "event": str(event)[:64],
        "props": props or {},
    }
    if tier:
        payload["tier"] = tier
    client.table("events").insert(payload).execute()


# Étapes du funnel : (clé, libellé, type, source).
# type 'signup'  → compte auth.users (haut de funnel)
# type 'event'   → distinct user_id ayant émis l'un des events listés
# type 'tier'    → distinct user_id actuellement VIP (profiles.tier)
_FUNNEL_STEPS = [
    ("signup",      "Inscrits",        "signup", None),
    ("onboarding",  "Onboarding fait", "event",  ("onboarding_completed",)),
    ("workout",     "1ʳᵉ séance",      "event",  ("workout_finished",)),
    ("offer",       "Offre vue",       "event",  ("premium_viewed", "paywall_viewed")),
    ("checkout",    "Checkout lancé",  "event",  ("checkout_started",)),
    ("vip",         "VIP",             "tier",   None),
]


def get_funnel_stats(days: int = 30) -> dict:
    """Entonnoir de conversion sur les `days` derniers jours.

    Interprétation (v1, orientée vue d'ensemble) : pour chaque étape, nombre
    d'utilisateurs DISTINCTS ayant atteint l'étape DANS la fenêtre. Le haut de
    funnel = comptes créés dans la fenêtre (auth.users). Les étapes du milieu
    lisent la table `events`. La dernière = users actuellement VIP.

    Retourne {days, steps:[{key,label,users,pct_of_top,pct_of_prev}], coach_msgs}.
    """
    import datetime as _dt
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)).isoformat()
    client = get_client()

    # Events de la fenêtre (un seul fetch, dédup en Python).
    users_by_event: dict[str, set] = {}
    coach_users: set = set()
    try:
        resp = (
            client.table("events")
            .select("user_id, event, created_at")
            .gte("created_at", cutoff)
            .execute()
        )
        for r in (resp.data or []):
            uid = r.get("user_id")
            ev = r.get("event") or ""
            if not uid:
                continue
            users_by_event.setdefault(ev, set()).add(uid)
            if ev == "coach_message":
                coach_users.add(uid)
    except Exception as e:
        logger.error("get_funnel_stats events FAILED: %s", e)

    # Haut de funnel : comptes créés dans la fenêtre.
    cutoff_day = cutoff[:10]
    signups = 0
    try:
        users_resp = client.auth.admin.list_users()
        auth_users = getattr(users_resp, "users", None) or users_resp or []
        for u in auth_users:
            created = getattr(u, "created_at", None) or (u.get("created_at") if isinstance(u, dict) else "")
            if str(created or "")[:10] >= cutoff_day:
                signups += 1
    except Exception as e:
        logger.error("get_funnel_stats signups FAILED: %s", e)

    # VIP actuels (étape finale).
    vip_count = 0
    try:
        prof = client.table("profiles").select("tier").execute()
        vip_count = sum(1 for p in (prof.data or []) if (p.get("tier") or "") == "vip")
    except Exception as e:
        logger.error("get_funnel_stats vip FAILED: %s", e)

    steps = []
    top = None
    prev = None
    for key, label, kind, events in _FUNNEL_STEPS:
        if kind == "signup":
            n = signups
        elif kind == "tier":
            n = vip_count
        else:
            seen: set = set()
            for ev in (events or ()):
                seen |= users_by_event.get(ev, set())
            n = len(seen)
        if top is None:
            top = n or 0
        pct_top = round(100 * n / top, 1) if top else 0.0
        pct_prev = round(100 * n / prev, 1) if prev else 100.0
        steps.append({
            "key": key, "label": label, "users": n,
            "pct_of_top": pct_top, "pct_of_prev": pct_prev,
        })
        prev = n if n else prev
    return {"days": days, "steps": steps, "coach_msgs_users": len(coach_users)}


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


def auth_user_exists(user_id: str) -> bool:
    """True si le compte auth Supabase existe encore. Lève en cas d'erreur
    transitoire (réseau, API down) — l'appelant décide alors de ne PAS
    déconnecter. Utilisé pour invalider les sessions d'un compte supprimé."""
    client = get_client()
    try:
        resp = client.auth.admin.get_user_by_id(user_id)
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg or "not_found" in msg or "404" in msg:
            return False
        raise
    user = getattr(resp, "user", None) or resp
    uid = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
    return bool(uid)


def delete_user_account(user_id: str) -> None:
    """Suppression DÉFINITIVE d'un compte : toutes les tables + l'utilisateur
    auth Supabase. Exigence des stores (Google Play / App Store) : la
    suppression de compte doit être disponible dans l'app.

    Ordre : données métier d'abord, auth en dernier — si la suppression auth
    échoue, l'utilisateur peut réessayer (les données restantes seront déjà
    parties, les deletes sont idempotents)."""
    client = get_client()
    # coach_conversations en premier : supprime aussi coach_messages liés
    # (ON DELETE CASCADE) ; le delete coach_messages qui suit couvre les
    # éventuels messages legacy sans conversation_id.
    for table, key in (
        ("coach_conversations", "user_id"),
        ("coach_messages", "user_id"),
        ("nutrition", "user_id"),
        ("history", "user_id"),
        ("programs", "user_id"),
        ("onboarding", "user_id"),
        ("profiles", "id"),
    ):
        try:
            client.table(table).delete().eq(key, user_id).execute()
        except Exception as e:
            # Une table optionnelle absente (migration non appliquée) ne doit
            # pas bloquer la suppression du reste.
            logger.error("delete_user_account %s FAILED user=%s: %s", table, user_id, e)
    clear_user_cache(user_id)
    # Compte auth Supabase (Google OAuth) — en dernier.
    client.auth.admin.delete_user(user_id)


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
