"""Notifications push, newsletter et relance des inactifs.

Les abonnements push (`push_subscriptions`), l'opt-in newsletter, et ce qu'il
faut pour cibler une relance sans harceler : dernière activité par utilisateur,
plafond d'une relance tous les 27 jours, et les deux lectures globales dont le
planificateur de rappels a besoin.
"""
import datetime as _dt
import logging

from core.db_base import _fetch_all, get_client
from core.db_historique import _norm_date
from core.db_profil import _profile_upsert

logger = logging.getLogger(__name__)

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


def delete_push_subscription(endpoint: str, user_id: str | None = None) -> None:
    """Supprime un abonnement par endpoint. Avec `user_id` (route utilisateur),
    on ne peut supprimer que les siens ; sans (cron : abonnement mort), libre."""
    if not endpoint:
        return
    client = get_client()
    q = client.table("push_subscriptions").delete().eq("endpoint", endpoint)
    if user_id:
        q = q.eq("user_id", user_id)
    q.execute()


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


def set_newsletter_optin(user_id: str, opt_in: bool, email: str = "") -> None:
    """Enregistre le consentement newsletter sur le profil (migration v31).
    Mémorise l'e-mail + la date au moment de l'opt-in (preuve RGPD)."""
    import datetime as _dt
    payload = {"id": user_id, "newsletter_opt_in": bool(opt_in)}
    if opt_in:
        payload["newsletter_opt_in_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        if email:
            payload["newsletter_email"] = email.strip().lower()
    else:
        # On garde la date/e-mail tels quels en cas de retrait (historique) —
        # seul le flag passe à false : on n'enverra plus rien.
        pass
    _profile_upsert(user_id, payload)


def list_newsletter_emails() -> list[str]:
    """E-mails distincts ayant consenti à la newsletter (pour export Brevo)."""
    client = get_client()
    try:
        resp = (
            client.table("profiles")
            .select("newsletter_email")
            .eq("newsletter_opt_in", True)
            .execute()
        )
    except Exception as e:
        logger.error("list_newsletter_emails FAILED: %s", e)
        return []
    seen = []
    for r in (resp.data or []):
        em = (r.get("newsletter_email") or "").strip().lower()
        if em and em not in seen:
            seen.append(em)
    return seen


def _last_activity_by_user() -> dict:
    """{user_id: 'YYYY-MM-DD' de la dernière perf réelle}. Lit la vue SQL
    `user_last_activity` (migration v34) — un seul agrégat côté base — et
    retombe sur un parcours paginé de `history` si la vue est absente/vide."""
    client = get_client()
    out: dict = {}
    try:
        resp = client.table("user_last_activity").select("user_id, last_date").execute()
        for r in (resp.data or []):
            uid, d = r.get("user_id"), str(r.get("last_date") or "")[:10]
            if uid and d:
                out[uid] = d
    except Exception as e:
        logger.info("user_last_activity indisponible (%s) — repli sur history", e)
    if out:
        return out
    rows = _fetch_all(lambda: (
        client.table("history").select("user_id, date, reps, poids").order("id")
    ))
    for r in rows:
        if int(r.get("reps") or 0) <= 0 and float(r.get("poids") or 0) <= 0:
            continue
        uid = r.get("user_id")
        d = str(r.get("date") or "")[:10]
        if uid and d and d > out.get(uid, ""):
            out[uid] = d
    return out


def get_inactive_users(min_days: int = 3, max_days: int = 30) -> dict:
    """{user_id: date de dernière séance} des comptes dont la dernière perf
    remonte à entre `min_days` et `max_days` jours — cibles de relance (ni
    actifs, ni partis depuis trop longtemps). Exclut les comptes sans
    historique. La date sert à savoir si une relance appartient à l'arrêt
    EN COURS ou à un arrêt précédent."""
    try:
        last_by_user = _last_activity_by_user()
    except Exception as e:
        logger.error("get_inactive_users FAILED: %s", e)
        return {}
    today = _dt.date.today()
    lo = (today - _dt.timedelta(days=max_days)).isoformat()
    hi = (today - _dt.timedelta(days=min_days)).isoformat()
    return {uid: last for uid, last in last_by_user.items() if lo <= last <= hi}


def get_inactive_user_ids(min_days: int = 3, max_days: int = 30) -> set:
    """Les user_id de `get_inactive_users`."""
    return set(get_inactive_users(min_days, max_days))


def list_push_subscriptions_for_users(user_ids: set) -> list[dict]:
    """Abonnements push des users donnés : [{user_id, sub, endpoint,
    last_reactivation_at, reactivation_count}]. Les deux derniers champs
    (migration v34) servent au dédoublonnage des relances ; absents = jamais
    relancé."""
    if not user_ids:
        return []
    client = get_client()
    try:
        rows = _fetch_all(lambda: client.table("push_subscriptions").select("*").order("id"))
        out = []
        for r in rows:
            if r.get("user_id") in user_ids:
                out.append({
                    "user_id": r.get("user_id"),
                    "endpoint": r.get("endpoint"),
                    "sub": _row_to_subscription(r),
                    "last_reactivation_at": r.get("last_reactivation_at"),
                    "reactivation_count": int(r.get("reactivation_count") or 0),
                })
        return out
    except Exception as e:
        logger.error("list_push_subscriptions_for_users FAILED: %s", e)
        return []


def list_all_programs() -> list[dict]:
    """[{user_id, data}] pour tous les comptes — cron des rappels de séance.

    Le planning vit dans `programs.data['_planning']` : sans lecture groupée,
    il faudrait une requête par utilisateur à chaque heure. On ne prend que
    les deux colonnes utiles.
    """
    client = get_client()
    try:
        return _fetch_all(lambda: (
            client.table("programs").select("user_id, data").order("user_id")
        ))
    except Exception as e:
        logger.error("list_all_programs FAILED: %s", e)
        return []


def users_trained_on(date_str: str) -> set:
    """user_id ayant au moins une perf réelle à cette date (pour ne pas
    rappeler une séance déjà faite)."""
    client = get_client()
    try:
        rows = _fetch_all(lambda: (
            client.table("history").select("user_id, reps, poids")
            .eq("date", _norm_date(date_str)).order("id")
        ))
    except Exception as e:
        logger.error("users_trained_on FAILED: %s", e)
        return set()
    return {r["user_id"] for r in rows
            if r.get("user_id")
            and (int(r.get("reps") or 0) > 0 or float(r.get("poids") or 0) > 0)}


def mark_reactivation_sent(endpoint: str, count: int) -> None:
    """Mémorise l'envoi d'une relance sur un abonnement (colonnes v34).
    Best-effort : sans la migration, l'update échoue et on continue."""
    if not endpoint:
        return
    client = get_client()
    try:
        (
            client.table("push_subscriptions")
            .update({
                "last_reactivation_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                "reactivation_count": int(count),
            })
            .eq("endpoint", endpoint)
            .execute()
        )
    except Exception as e:
        logger.warning("mark_reactivation_sent FAILED (migration v34 ?): %s", e)
