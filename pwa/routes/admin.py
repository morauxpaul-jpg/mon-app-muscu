"""Blueprint admin — stats, gestion VIP, fiche user.

Accès restreint par ADMIN_EMAILS (variable d'env, séparateur virgule).
Exemple : ADMIN_EMAILS="moraux.paul@gmail.com"
"""
import logging
import os

from flask import Blueprint, render_template, request, redirect, url_for, session, abort, jsonify

from core import db as core_db
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
