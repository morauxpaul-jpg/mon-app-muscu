"""Tier PRO, Stripe et parrainage — qui a accès à quoi.

Le tier vit dans `profiles`; le lien vers le client Stripe aussi. Le parrainage
crédite des jours de VIP à durée limitée (`vip_until`), ce qui fait deux façons
d'être PRO : payant et offert. `vip_until_active` est la seule à trancher.
"""
import datetime as _dt
import logging
from typing import Optional

from core.db_base import get_client
from core.db_profil import _profile_upsert

logger = logging.getLogger(__name__)

# ── Tier PRO / gratuit ───────────────────────────────────────────
def set_user_tier(user_id: str, tier: str) -> None:
    """Upsert profiles.tier pour un user. tier ∈ {'free', 'vip'}."""
    if tier not in ("free", "vip"):
        raise ValueError(f"tier invalide: {tier}")
    _profile_upsert(user_id, {"tier": tier})


# ── Stripe (abonnements Premium) ─────────────────────────────────
def set_stripe_customer(user_id: str, customer_id: str) -> None:
    """Mémorise l'ID client Stripe sur le profil (pour le portail + le mapping
    customer→user lors des webhooks d'annulation). Nécessite la colonne
    profiles.stripe_customer_id (migration v27)."""
    if not customer_id:
        return
    _profile_upsert(user_id, {"stripe_customer_id": customer_id})


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


def essai_restant(vip_until, maintenant=None):
    """« encore 5 h », « encore 3 jours »… pour un essai `vip_until` encore
    valide ; None sinon. Sans ça, l'essai ne disait jamais quand il finissait
    et se refermait sans un mot."""
    if not vip_until:
        return None
    try:
        fin = _dt.datetime.fromisoformat(str(vip_until).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=_dt.timezone.utc)
    reste = fin - (maintenant or _dt.datetime.now(_dt.timezone.utc))
    heures = reste.total_seconds() / 3600
    if heures <= 0:
        return None
    if heures < 1:
        return "moins d'une heure"
    if heures < 48:
        return f"encore {int(heures)} h"
    return f"encore {int(heures // 24)} jours"


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
        _profile_upsert(user_id, {"referral_code": code})
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
    _profile_upsert(user_id, {"referred_by": referrer_id})


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
    _profile_upsert(user_id, {"vip_until": new_until})


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
