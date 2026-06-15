"""Blueprint admin — stats, gestion VIP, fiche user.

Accès restreint par ADMIN_EMAILS (variable d'env, séparateur virgule).
Exemple : ADMIN_EMAILS="moraux.paul@gmail.com"
"""
import logging
import os

from flask import Blueprint, render_template, request, redirect, url_for, session, abort, jsonify

from core import db as core_db
from core import push as core_push
from core.analytics import track
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("admin", __name__)


def _admin_emails() -> set[str]:
    raw = os.getenv("ADMIN_EMAILS", "") or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _require_admin():
    email = (session.get("email") or "").strip().lower()
    if not email or email not in _admin_emails():
        abort(404)


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
    )


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
    try:
        targets = core_db.get_inactive_user_ids(min_days=3, max_days=30)
        subs = core_db.list_push_subscriptions_for_users(targets)
    except Exception as e:
        logger.error("send_reactivation gather FAILED: %s", e)
        return jsonify({"error": "ciblage échoué"}), 500

    payload = {
        "title": "On reprend ? 💪",
        "body": "Ta prochaine séance t'attend. Un petit effort aujourd'hui !",
        "url": "/accueil",
    }
    sent, expired, errors = 0, 0, 0
    for user_id, sub in subs:
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
    try:
        track("reactivation_push_sent", {"sent": sent, "expired": expired, "errors": errors},
              user_id=session.get("user_id"))
    except Exception:
        pass
    logger.info("reactivation push: sent=%s expired=%s errors=%s targets=%s",
                sent, expired, errors, len(targets))
    return jsonify({"ok": True, "sent": sent, "expired": expired,
                    "errors": errors, "targets": len(targets)})


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
