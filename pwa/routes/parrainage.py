"""Blueprint parrainage — lien d'invitation + récompense en jours VIP.

Boucle : chaque user a un `referral_code` → lien `/?ref=CODE`. Un nouvel
arrivant qui complète l'onboarding via ce lien déclenche `apply_referral` :
le parrain reçoit des jours de VIP à durée limitée (`vip_until`).

Le filleul ne reçoit plus rien à l'inscription (25/10). Son jour offert
posait `vip_until` avant même sa première séance et lui fermait l'essai de
3 jours (core/essai.py), ouvert seulement à qui n'en a jamais eu : un ami
invité était moins bien traité qu'un inconnu. Il a désormais l'essai de
tout le monde, après sa première séance.
"""
import logging

from flask import Blueprint, render_template, request, jsonify, g

from core import db as core_db
from core.essai import ESSAI_JOURS
from core.analytics import track
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("parrainage", __name__)

# Essai « découverte » volontairement court + restreint (Nutrition + stats
# détaillées seulement, cf. gates g.is_vip_full) : assez pour goûter, trop court
# pour tout extraire et ne plus payer.
REFERRER_VIP_DAYS = 3    # parrain : par filleul qui complète l'onboarding


def apply_referral(user_id: str, ref_code: str) -> bool:
    """Crédite le parrain UNE seule fois par filleul. Retourne True si crédité.

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
        referrer_days=REFERRER_VIP_DAYS, essai_jours=ESSAI_JOURS,
    )


@bp.route("/parrainage/share", methods=["POST"])
@limiter.limit("30 per minute")
def share():
    track("referral_shared", {"method": (request.get_json(silent=True) or {}).get("method", "")})
    return ("", 204)
