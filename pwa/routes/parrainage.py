"""Blueprint parrainage — lien d'invitation + récompense en jours VIP.

Boucle : chaque user a un `referral_code` → lien `/?ref=CODE`. Un nouvel
arrivant qui complète l'onboarding via ce lien déclenche `apply_referral` :
parrain et filleul reçoivent des jours de VIP à durée limitée (`vip_until`).
"""
import logging

from flask import Blueprint, render_template, request, jsonify, g

from core import db as core_db
from core.analytics import track
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("parrainage", __name__)

REFERRER_VIP_DAYS = 30   # parrain : par filleul qui complète l'onboarding
REFEREE_VIP_DAYS = 14    # filleul : à l'arrivée via un lien d'invitation


def apply_referral(user_id: str, ref_code: str) -> bool:
    """Crédite parrain + filleul UNE seule fois. Retourne True si crédité.

    Garde-fous : code valide, pas d'auto-parrainage, filleul pas déjà parrainé.
    """
    ref_code = (ref_code or "").strip().lower()
    if not ref_code:
        return False
    try:
        if core_db.get_referred_by(user_id):
            return False  # déjà parrainé → une seule fois
        referrer_id = core_db.get_user_by_referral_code(ref_code)
        if not referrer_id or referrer_id == user_id:
            return False  # code inconnu ou auto-parrainage
        core_db.set_referred_by(user_id, referrer_id)
        core_db.grant_vip_days(user_id, REFEREE_VIP_DAYS)
        core_db.grant_vip_days(referrer_id, REFERRER_VIP_DAYS)
        track("referral_signup", {"referrer": referrer_id}, user_id=user_id)
        return True
    except Exception as e:
        logger.error("apply_referral FAILED user=%s ref=%s: %s", user_id, ref_code, e)
        return False


@bp.route("/parrainage")
def index():
    code = ""
    count = 0
    try:
        code = core_db.get_or_create_referral_code(g.user_id)
        count = core_db.count_referrals(g.user_id)
    except Exception as e:
        logger.error("/parrainage load FAILED user=%s: %s", g.user_id, e)
    return render_template(
        "parrainage.html", active="plus",
        referral_code=code, referral_count=count,
        referrer_days=REFERRER_VIP_DAYS, referee_days=REFEREE_VIP_DAYS,
    )


@bp.route("/parrainage/share", methods=["POST"])
@limiter.limit("30 per minute")
def share():
    track("referral_shared", {"method": (request.get_json(silent=True) or {}).get("method", "")})
    return ("", 204)
