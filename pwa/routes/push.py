"""Blueprint push — abonnement aux notifications push (relance des inactifs).

  GET  /push/config       : clé publique VAPID (pour PushManager côté client)
  POST /push/subscribe    : enregistre un PushSubscription (toJSON)
  POST /push/unsubscribe  : supprime un abonnement (par endpoint)

Disponible à TOUS les users (free inclus) : la relance cible surtout les
comptes gratuits qui décrochent.
"""
import logging

from flask import Blueprint, jsonify, request, g

from core import db as core_db
from core import push as core_push
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("push", __name__)


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
