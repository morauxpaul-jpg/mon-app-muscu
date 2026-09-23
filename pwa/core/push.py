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


# Relance des inactifs : au plus 3 messages, espacés, puis on laisse la
# personne tranquille. Sans ce plafond, un cron quotidien envoyait la MÊME
# notification tous les jours pendant 27 jours (fenêtre 3→30 j) — le plus
# sûr moyen de se faire désinstaller.
MAX_REACTIVATIONS = 3
MIN_DAYS_BETWEEN = 4  # jours entre deux relances d'une même personne

REACTIVATION_MESSAGES = [
    {"title": "On reprend ? 💪",
     "body": "Ta prochaine séance t'attend — même courte, elle compte.",
     "url": "/accueil"},
    {"title": "Ton programme t'attend",
     "body": "Reprends là où tu t'es arrêté : 20 minutes suffisent pour relancer la machine.",
     "url": "/seance"},
    {"title": "Un dernier coup de pouce 👋",
     "body": "Reviens quand tu veux — ton historique et tes records sont intacts.",
     "url": "/accueil"},
]

# Rétro-compat : l'admin et les tests importent encore ce nom.
REACTIVATION_PAYLOAD = REACTIVATION_MESSAGES[0]


def _should_relaunch(sub: dict, now=None) -> bool:
    """True si cet abonnement peut recevoir une relance maintenant."""
    import datetime as _dt
    count = int(sub.get("reactivation_count") or 0)
    if count >= MAX_REACTIVATIONS:
        return False
    last = sub.get("last_reactivation_at")
    if not last:
        return True
    try:
        dt_last = _dt.datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        if dt_last.tzinfo is None:
            dt_last = dt_last.replace(tzinfo=_dt.timezone.utc)
    except (ValueError, TypeError):
        return True
    now = now or _dt.datetime.now(_dt.timezone.utc)
    return (now - dt_last).days >= MIN_DAYS_BETWEEN


def run_reactivation_push(min_days: int = 3, max_days: int = 30,
                          payload: dict | None = None, force: bool = False) -> dict:
    """Cible les inactifs abonnés (min_days–max_days sans séance) et leur envoie
    un push de relance. Source de vérité unique pour le bouton admin ET le cron.

    - Ne dépend PAS du contexte requête Flask (utilisable depuis un script cron).
    - Supprime au passage les abonnements morts (404/410).
    - Plafonne à MAX_REACTIVATIONS messages espacés de MIN_DAYS_BETWEEN jours
      par personne (`force=True` ignore ce plafond : test admin).
    - Best-effort : n'échoue jamais sur un envoi individuel.

    Retour : {"ok", "sent", "expired", "errors", "targets"} ou
             {"ok": False, "error": "..."} si le push n'est pas configuré / ciblage KO.
    """
    # Imports différés : évite un cycle core.push ↔ core.db / core.analytics.
    from core import db as core_db
    from core import analytics

    if not is_configured():
        return {"ok": False, "error": "unconfigured"}

    try:
        targets = core_db.get_inactive_user_ids(min_days=min_days, max_days=max_days)
        subs = core_db.list_push_subscriptions_for_users(targets)
    except Exception as e:
        logger.error("run_reactivation_push gather FAILED: %s", e)
        return {"ok": False, "error": "gather_failed"}

    sent, expired, errors, skipped = 0, 0, 0, 0
    for sub in subs:
        if not force and not _should_relaunch(sub):
            skipped += 1
            continue
        count = int(sub.get("reactivation_count") or 0)
        # Message différent à chaque relance (le même texte répété est ignoré).
        body = payload or REACTIVATION_MESSAGES[min(count, len(REACTIVATION_MESSAGES) - 1)]
        status = send_push(sub["sub"], body)
        if status == "ok":
            sent += 1
            try:
                core_db.mark_reactivation_sent(sub.get("endpoint"), count + 1)
            except Exception:
                pass
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
                         "skipped": skipped, "min_days": min_days, "max_days": max_days},
                        user_id=None, tier="system")
    except Exception:
        pass
    logger.info("reactivation push: sent=%s skipped=%s expired=%s errors=%s targets=%s",
                sent, skipped, expired, errors, len(targets))
    return {"ok": True, "sent": sent, "expired": expired, "errors": errors,
            "skipped": skipped, "targets": len(targets)}
