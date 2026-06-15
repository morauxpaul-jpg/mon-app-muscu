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
