"""Blueprint admin — interface minimale pour attribuer le tier VIP.

Accès restreint par ADMIN_EMAILS (variable d'env, séparateur virgule).
Exemple : ADMIN_EMAILS="moraux.paul@gmail.com"
"""
import logging
import os

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session, abort

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
        abort(404)  # 404 plutôt que 403 — on ne dit pas que la page existe


@bp.route("/admin")
def index():
    _require_admin()
    try:
        users = core_db.list_all_users_with_tier()
    except Exception as e:
        logger.error("/admin list failed: %s", e)
        users = []
    vip_count = sum(1 for u in users if u.get("tier") == "vip")
    return render_template(
        "admin.html",
        active="plus",
        users=users,
        vip_count=vip_count,
        total_count=len(users),
        current_email=session.get("email", ""),
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
