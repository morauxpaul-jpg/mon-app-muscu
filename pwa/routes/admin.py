"""Blueprint admin — stats, gestion VIP, fiche user.

Accès restreint par ADMIN_EMAILS (variable d'env, séparateur virgule).
Exemple : ADMIN_EMAILS="moraux.paul@gmail.com"
"""
import logging

from flask import Blueprint, render_template, request, redirect, url_for, session, abort, jsonify, Response

from core import db as core_db
from core import push as core_push
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("admin", __name__)


from core.admin_acces import adresses_admin as _admin_emails, connecte_par_google  # noqa: E402


def _require_admin():
    """404 si l'appelant n'est pas admin — et une trace pour savoir pourquoi.

    Un refus ressemblait à une page inexistante, y compris pour l'administrateur
    lui-même : variable `ADMIN_EMAILS` absente et adresse non autorisée
    donnaient exactement le même 404 muet. Le journal distingue maintenant les
    deux cas, sans jamais recopier d'adresse ni le contenu de la variable.

    Le 404 reste un 404 : il ne faut pas révéler à un inconnu que la page
    existe. Le diagnostic va dans les logs de l'hébergeur, que seul le
    propriétaire lit.
    """
    email = (session.get("email") or "").strip().lower()
    autorises = _admin_emails()
    if not autorises:
        logger.warning("admin refuse : ADMIN_EMAILS absente ou vide "
                       "dans l'environnement (path=%s)", request.path)
        abort(404)
    if not email:
        logger.warning("admin refuse : aucune adresse en session (path=%s)",
                       request.path)
        abort(404)
    if email not in autorises:
        logger.warning("admin refuse : l'adresse de la session n'est pas dans "
                       "ADMIN_EMAILS, qui en compte %d (path=%s)",
                       len(autorises), request.path)
        abort(404)
    # L'adresse seule ne prouve rien : elle vient d'un jeton que n'importe
    # quelle méthode de connexion Supabase peut produire (audit du 03/10, CC2).
    if not connecte_par_google(session):
        logger.warning("admin refuse : session sans connexion Google "
                       "(reconnexion necessaire) (path=%s)", request.path)
        abort(404)


@bp.route("/admin/blob")
def blob():
    """Ce que pèse chaque clé du blob programme — lecture seule.

    Cette page existe pour que la mesure se fasse **là où vit la clé
    `service_role`**, chez l'hébergeur. La faire en local obligerait à
    rapatrier la clé, ce qui est exactement ce qu'on veut éviter.

    Elle ne rend aucun contenu : que des noms de clés `_x`, des tailles et des
    comptages (cf. `core/blob_stats.py`). Le texte se colle donc n'importe où.
    """
    _require_admin()
    from core.blob_stats import analyser, analyser_historique, rapport
    try:
        blobs = core_db.list_all_program_blobs()
    except Exception as e:
        logger.error("/admin/blob lecture failed: %s", type(e).__name__)
        return Response("Lecture impossible.\n", mimetype="text/plain"), 503
    if not blobs:
        return Response("Aucun programme en base.\n", mimetype="text/plain")
    # L'historique est mesuré à part et sans bloquer : c'est un complément,
    # pas la raison d'être de la page. Une lecture qui échoue ne doit pas
    # priver du reste.
    hist = None
    try:
        hist = analyser_historique(core_db.list_history_shape())
    except Exception as e:
        logger.warning("/admin/blob historique indisponible: %s", type(e).__name__)
    return Response(rapport(analyser(blobs), hist) + "\n", mimetype="text/plain")


@bp.route("/admin")
def index():
    _require_admin()
    try:
        users = core_db.list_all_users_with_tier()
    except Exception as e:
        logger.error("/admin list failed: %s", e)
        users = []
    try:
        stats = core_db.get_admin_stats()
    except Exception as e:
        logger.error("/admin stats failed: %s", e)
        stats = {"total_rows": 0, "total_tonnage": 0, "total_seances": 0, "active_7d": 0, "active_30d": 0}
    vip_count = sum(1 for u in users if u.get("tier") == "vip")
    return render_template(
        "admin.html",
        active="plus",
        users=users,
        vip_count=vip_count,
        total_count=len(users),
        current_email=session.get("email", ""),
        stats=stats,
        admob=_etat_admob(),
        partage=_etat_partage(),
        schema=_etat_schema(),
    )


def _etat_schema() -> dict:
    from core.schema import etat_a_jour
    return etat_a_jour(core_db.get_client)


def _etat_partage() -> dict:
    from core.partage import etat
    return etat()


def _etat_admob() -> str:
    from core.admob import identifiants
    return identifiants()["etat"]


@bp.route("/admin/funnel")
def funnel():
    _require_admin()
    try:
        days = int(request.args.get("days") or 30)
    except (TypeError, ValueError):
        days = 30
    if days not in (7, 30, 90):
        days = 30
    try:
        data = core_db.get_funnel_stats(days)
    except Exception as e:
        logger.error("/admin/funnel FAILED: %s", e)
        data = {"days": days, "steps": [], "coach_msgs_users": 0}
    return render_template("funnel.html", active="plus", funnel=data, days=days)


@bp.route("/admin/send-test-push", methods=["POST"])
@limiter.limit("20 per hour")
def send_test_push():
    """Envoie une notif de test à l'admin lui-même (ignore le filtre d'inactivité)
    — pour vérifier la chaîne VAPID + abonnement + livraison."""
    _require_admin()
    if not core_push.is_configured():
        return jsonify({"error": "Push non configuré (clés VAPID manquantes en env)."}), 503
    uid = session.get("user_id")
    subs = core_db.list_push_subscriptions(uid)
    if not subs:
        return jsonify({"error": "Aucun abonnement sur ce compte. Va dans Gestion → « Activer les notifications » sur cet appareil, puis réessaie."}), 400
    payload = {"title": "Test ✅", "body": "Les notifications push fonctionnent !", "url": "/accueil"}
    sent, expired, errors = 0, 0, 0
    for sub in subs:
        status = core_push.send_push(sub, payload)
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
    return jsonify({"ok": True, "sent": sent, "expired": expired, "errors": errors,
                    "subs": len(subs)})


@bp.route("/admin/send-reactivation", methods=["POST"])
@limiter.limit("5 per hour")
def send_reactivation():
    """Envoie un push de relance aux inactifs abonnés (3–30 j sans séance).
    Déclenché manuellement par l'admin (un cron pourra appeler cette logique)."""
    _require_admin()
    if not core_push.is_configured():
        return jsonify({"error": "Push non configuré (clés VAPID manquantes en env)."}), 503
    result = core_push.run_reactivation_push(min_days=3, max_days=30)
    if not result.get("ok"):
        if result.get("error") == "unconfigured":
            return jsonify({"error": "Push non configuré (clés VAPID manquantes en env)."}), 503
        return jsonify({"error": "ciblage échoué"}), 500
    return jsonify(result)


@bp.route("/admin/newsletter-emails")
def newsletter_emails():
    """Liste des e-mails ayant consenti à la newsletter, en texte brut (un par
    ligne) — à copier-coller dans Brevo. Réservé admin."""
    _require_admin()
    try:
        emails = core_db.list_newsletter_emails()
    except Exception as e:
        logger.error("newsletter_emails FAILED: %s", e)
        emails = []
    body = "\n".join(emails) if emails else "(aucun abonné pour l'instant)"
    return Response(body, mimetype="text/plain; charset=utf-8")


@bp.route("/admin/set-tier", methods=["POST"])
@limiter.limit("30 per minute")
def set_tier():
    _require_admin()
    user_id = (request.form.get("user_id") or "").strip()
    tier = (request.form.get("tier") or "").strip()
    if not user_id or tier not in ("free", "vip"):
        return redirect(url_for("admin.index"))
    try:
        core_db.set_user_tier(user_id, tier)
    except Exception as e:
        logger.error("/admin/set-tier FAILED user=%s tier=%s: %s", user_id, tier, e)
    # Invalide le cache VIP si l'admin modifie son propre tier
    if user_id == session.get("user_id"):
        session.pop("is_vip", None)
    return redirect(url_for("admin.index"))


@bp.route("/admin/user/<user_id>")
@limiter.limit("60 per minute")
def user_details(user_id):
    _require_admin()
    try:
        info = core_db.get_user_details(user_id)
    except Exception as e:
        logger.error("/admin/user FAILED user=%s: %s", user_id, e)
        return jsonify({"error": "fetch failed"}), 500
    return jsonify(info)


@bp.route("/admin/reset-quota", methods=["POST"])
@limiter.limit("20 per minute")
def reset_quota():
    _require_admin()
    user_id = (request.form.get("user_id") or "").strip()
    if not user_id:
        return jsonify({"error": "user_id manquant"}), 400
    try:
        core_db.reset_user_coach_quota(user_id)
    except Exception as e:
        logger.error("/admin/reset-quota FAILED user=%s: %s", user_id, e)
        return jsonify({"error": "reset failed"}), 500
    return jsonify({"ok": True})
