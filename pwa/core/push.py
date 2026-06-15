"""Push web — config VAPID (env) + envoi via pywebpush. Relance des inactifs.

Variables d'env (Railway) :
  VAPID_PUBLIC_KEY   : clé publique (base64url) — exposée au client (/push/config)
  VAPID_PRIVATE_KEY  : clé privée (base64url, 32 octets) — SECRÈTE
  VAPID_SUBJECT      : contact 'mailto:…' (recommandé par la spec Web Push)

L'envoi est best-effort et tolérant : si la lib ou les clés manquent, on
n'échoue jamais l'appelant (retour 'unconfigured'/'error').
"""
import json
import logging
import os

logger = logging.getLogger(__name__)


def _env(name: str) -> str:
    v = os.getenv(name, "") or ""
    return v.strip().strip('"').strip("'").lstrip("=").strip()


def public_key() -> str:
    return _env("VAPID_PUBLIC_KEY")


def is_configured() -> bool:
    return bool(_env("VAPID_PUBLIC_KEY") and _env("VAPID_PRIVATE_KEY"))


def send_push(subscription: dict, payload: dict) -> str:
    """Envoie une notif à un abonnement. Retourne :
      'ok'           — envoyé
      'expired'      — abonnement mort (404/410) → l'appelant doit le supprimer
      'error'        — échec transitoire
      'unconfigured' — clés/lib absentes
    """
    if not is_configured():
        return "unconfigured"
    try:
        from pywebpush import webpush, WebPushException
        from py_vapid import Vapid01
    except ImportError as e:
        logger.error("pywebpush/py_vapid absent: %s", e)
        return "unconfigured"

    subject = _env("VAPID_SUBJECT") or "mailto:contact@muscu-tracker.app"
    try:
        vapid = Vapid01.from_raw(_env("VAPID_PRIVATE_KEY").encode())
    except Exception as e:
        logger.error("VAPID_PRIVATE_KEY invalide: %s", e)
        return "unconfigured"

    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=vapid,
            vapid_claims={"sub": subject},
            ttl=24 * 3600,
        )
        return "ok"
    except WebPushException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status in (404, 410):
            return "expired"
        logger.warning("push send failed (status=%s): %s", status, e)
        return "error"
    except Exception as e:
        logger.error("push send error: %s", e)
        return "error"


# Payload par défaut de la relance des inactifs (réutilisé par l'admin et le cron).
REACTIVATION_PAYLOAD = {
    "title": "On reprend ? 💪",
    "body": "Ta prochaine séance t'attend. Un petit effort aujourd'hui !",
    "url": "/accueil",
}


def run_reactivation_push(min_days: int = 3, max_days: int = 30,
                          payload: dict | None = None) -> dict:
    """Cible les inactifs abonnés (min_days–max_days sans séance) et leur envoie
    un push de relance. Source de vérité unique pour le bouton admin ET le cron.

    - Ne dépend PAS du contexte requête Flask (utilisable depuis un script cron).
    - Supprime au passage les abonnements morts (404/410).
    - Best-effort : n'échoue jamais sur un envoi individuel.

    Retour : {"ok", "sent", "expired", "errors", "targets"} ou
             {"ok": False, "error": "..."} si le push n'est pas configuré / ciblage KO.
    """
    # Imports différés : évite un cycle core.push ↔ core.db / core.analytics.
    from core import db as core_db
    from core import analytics

    if not is_configured():
        return {"ok": False, "error": "unconfigured"}

    payload = payload or REACTIVATION_PAYLOAD
    try:
        targets = core_db.get_inactive_user_ids(min_days=min_days, max_days=max_days)
        subs = core_db.list_push_subscriptions_for_users(targets)
    except Exception as e:
        logger.error("run_reactivation_push gather FAILED: %s", e)
        return {"ok": False, "error": "gather_failed"}

    sent, expired, errors = 0, 0, 0
    for _user_id, sub in subs:
        status = send_push(sub, payload)
        if status == "ok":
            sent += 1
        elif status == "expired":
            expired += 1
            try:
                core_db.delete_push_subscription(sub.get("endpoint"))
            except Exception:
                pass
        else:
            errors += 1

    try:
        analytics.track("reactivation_push_sent",
                        {"sent": sent, "expired": expired, "errors": errors,
                         "min_days": min_days, "max_days": max_days},
                        user_id=None, tier="system")
    except Exception:
        pass
    logger.info("reactivation push: sent=%s expired=%s errors=%s targets=%s",
                sent, expired, errors, len(targets))
    return {"ok": True, "sent": sent, "expired": expired,
            "errors": errors, "targets": len(targets)}
