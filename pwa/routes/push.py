"""Blueprint push — abonnement aux notifications push (relance des inactifs).

  GET  /push/config       : clé publique VAPID (pour PushManager côté client)
  POST /push/subscribe    : enregistre un PushSubscription (toJSON)
  POST /push/unsubscribe  : supprime un abonnement (par endpoint)
  POST /push/repos        : programme le push de fin de repos (écran éteint)
  POST /push/repos/annuler: l'annule (nouveau repos, « Passer », fin de séance)

Disponible à TOUS les users (free inclus) : la relance cible surtout les
comptes gratuits qui décrochent.
"""
import hmac
import logging
import os

from flask import Blueprint, jsonify, request, g

from core import db as core_db
from core import push as core_push
from core import push_repos
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("push", __name__)


def _cron_authorized() -> bool:
    """Vrai si la requête porte le secret cron (env CRON_SECRET).

    Le secret est accepté via l'en-tête `X-Cron-Secret` UNIQUEMENT (une query
    string finit dans les logs d'accès). Comparaison à temps constant. Si
    CRON_SECRET n'est pas configuré, l'endpoint est fermé.
    """
    expected = (os.getenv("CRON_SECRET", "") or "").strip()
    if not expected:
        return False
    # En-tête uniquement : un secret passé en query string se retrouve dans
    # les logs d'accès de l'hébergeur et dans les referrers.
    provided = (request.headers.get("X-Cron-Secret") or "").strip()
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


@bp.route("/push/repos", methods=["POST"])
@limiter.limit("60 per minute")
def programmer_repos():
    """Le navigateur annonce un repos : « fini dans `dans` secondes, sur cet
    appareil ». Le serveur enverra le push de fin, écran éteint compris
    (core/push_repos.py). L'abonnement est relu en base : on ne programme
    que vers ses propres appareils."""
    data = request.get_json(silent=True) or {}
    endpoint = str(data.get("endpoint") or "")
    if not endpoint or not core_push.is_configured():
        return jsonify({"ok": False}), 400
    abonnement = next((s for s in core_db.list_push_subscriptions(g.user_id)
                       if s.get("endpoint") == endpoint), None)
    if abonnement is None:
        return jsonify({"ok": False, "error": "appareil inconnu"}), 404
    jeton = push_repos.programmer(g.user_id, abonnement, data.get("dans"),
                                  nom=data.get("nom") or "", url=_url_locale(data.get("url")))
    return jsonify({"ok": bool(jeton)}), (200 if jeton else 400)


@bp.route("/push/repos/annuler", methods=["POST"])
@limiter.limit("60 per minute")
def annuler_repos():
    endpoint = str((request.get_json(silent=True) or {}).get("endpoint") or "")
    if endpoint:
        push_repos.annuler(g.user_id, endpoint)
    return ("", 204)


def _url_locale(url):
    """La notification ramène à la séance : un chemin de l'app, rien d'autre."""
    url = str(url or "")
    return url if url.startswith("/") and not url.startswith("//") else "/seance"


@bp.route("/push/unsubscribe", methods=["POST"])
@limiter.limit("30 per minute")
def unsubscribe():
    endpoint = (request.get_json(silent=True) or {}).get("endpoint") or ""
    try:
        # Scopé au propriétaire : on ne peut désabonner que ses propres appareils.
        core_db.delete_push_subscription(endpoint, user_id=g.user_id)
    except Exception as e:
        logger.error("/push/unsubscribe FAILED: %s", e)
    return ("", 204)


@bp.route("/tasks/reminders", methods=["POST"])
@limiter.limit("60 per hour")
def cron_reminders():
    """Rappels de séance — à appeler CHAQUE HEURE par un scheduler.

    Envoie un push aux personnes qui ont une séance planifiée aujourd'hui, ne
    l'ont pas encore faite, et ont choisi cette heure de rappel. Contrairement
    aux rappels locaux (qui exigeaient que l'app soit ouverte), celui-ci part
    même app fermée.

        curl -X POST -H "X-Cron-Secret: …" https://…/tasks/reminders
    """
    if not _cron_authorized():
        return jsonify({"error": "unauthorized"}), 401
    from core import recap, reminders
    result = reminders.run_reminders()
    # Le dimanche à 19 h, même passage : le récap de la semaine. Indépendant
    # du rappel, un échec de l'un n'empêche pas l'autre.
    try:
        result["recap"] = recap.run_recap_hebdo()
    except Exception as e:
        logger.error("récap hebdo FAILED: %s", e)
    # Toutes les 4 semaines : reprendre ses photos de progression (PRO).
    try:
        from core import rappel_photos
        result["photos"] = rappel_photos.run_rappel_photos()
    except Exception as e:
        logger.error("rappel photos FAILED: %s", e)
    if not result.get("ok"):
        code = 503 if result.get("error") == "unconfigured" else 500
        return jsonify(result), code
    return jsonify(result)


@bp.route("/tasks/reactivation", methods=["POST"])
@limiter.limit("12 per hour")
def cron_reactivation():
    """Endpoint cron : envoie la relance push aux inactifs.

    Pas de session — sécurisé par CRON_SECRET (en-tête X-Cron-Secret seulement).
    Public + exempté de CSRF (cf. app.py _PUBLIC_PATHS / _CSRF_EXEMPT_PATHS).
    À appeler par un scheduler externe (Railway cron, cron-job.org, GitHub Actions)
    une fois par jour :  curl -X POST -H "X-Cron-Secret: …" https://…/tasks/reactivation
    """
    if not _cron_authorized():
        return jsonify({"error": "unauthorized"}), 401
    # Tâche quotidienne : on en profite pour appliquer la rétention de la
    # mesure d'usage (13 mois). Best-effort, n'empêche jamais la relance.
    try:
        from core import db as core_db
        core_db.purge_old_events()
    except Exception as e:
        logger.warning("purge_old_events FAILED: %s", e)
    result = core_push.run_reactivation_push(min_days=3, max_days=30)
    if not result.get("ok"):
        code = 503 if result.get("error") == "unconfigured" else 500
        return jsonify(result), code
    return jsonify(result)
