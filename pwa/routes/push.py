"""Blueprint push — abonnement aux notifications push (relance des inactifs).

  GET  /push/config       : clé publique VAPID (pour PushManager côté client)
  POST /push/subscribe    : enregistre un PushSubscription (toJSON)
  POST /push/unsubscribe  : supprime un abonnement (par endpoint)

Disponible à TOUS les users (free inclus) : la relance cible surtout les
comptes gratuits qui décrochent.
"""
import hmac
import logging
import os

from flask import Blueprint, jsonify, request, g

from core import db as core_db
from core import push as core_push
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("push", __name__)


def _cron_authorized() -> bool:
    """Vrai si la requête porte le secret cron (env CRON_SECRET).

    Le secret est accepté via l'en-tête `X-Cron-Secret` ou le paramètre `?token=`
    (certains schedulers ne savent envoyer que des query params). Comparaison à
    temps constant. Si CRON_SECRET n'est pas configuré, l'endpoint est fermé.
    """
    expected = (os.getenv("CRON_SECRET", "") or "").strip()
    if not expected:
        return False
    provided = (request.headers.get("X-Cron-Secret")
                or request.args.get("token") or "").strip()
    return bool(provided) and hmac.compare_digest(provided, expected)


@bp.route("/push/config")
def config():
    return jsonify({"public_key": core_push.public_key(),
                    "enabled": core_push.is_configured()})


@bp.route("/push/subscribe", methods=["POST"])
@limiter.limit("30 per minute")
def subscribe():
    sub = request.get_json(silent=True) or {}
    try:
        core_db.save_push_subscription(g.user_id, sub)
    except ValueError:
        return jsonify({"error": "subscription invalide"}), 400
    except Exception as e:
        logger.error("/push/subscribe FAILED user=%s: %s", g.user_id, e)
        return jsonify({"error": "enregistrement échoué"}), 500
    return ("", 204)


@bp.route("/push/unsubscribe", methods=["POST"])
@limiter.limit("30 per minute")
def unsubscribe():
    endpoint = (request.get_json(silent=True) or {}).get("endpoint") or ""
    try:
        core_db.delete_push_subscription(endpoint)
    except Exception as e:
        logger.error("/push/unsubscribe FAILED: %s", e)
    return ("", 204)


@bp.route("/tasks/reactivation", methods=["POST"])
@limiter.limit("12 per hour")
def cron_reactivation():
    """Endpoint cron : envoie la relance push aux inactifs.

    Pas de session — sécurisé par CRON_SECRET (en-tête X-Cron-Secret ou ?token=).
    Public + exempté de CSRF (cf. app.py _PUBLIC_PATHS / _CSRF_EXEMPT_PATHS).
    À appeler par un scheduler externe (Railway cron, cron-job.org, GitHub Actions)
    une fois par jour, p. ex. :  curl -X POST -H "X-Cron-Secret: …" https://…/tasks/reactivation
    """
    if not _cron_authorized():
        return jsonify({"error": "unauthorized"}), 401
    result = core_push.run_reactivation_push(min_days=3, max_days=30)
    if not result.get("ok"):
        code = 503 if result.get("error") == "unconfigured" else 500
        return jsonify(result), code
    return jsonify(result)
