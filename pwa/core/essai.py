"""Essai PRO offert à la fin de la première séance.

Audit du 18/10 (I-4) : l'essai (`profiles.vip_until`, v29) ne s'ouvrait que
par parrainage. 0 filleul, donc 0 essai, 0 paiement : personne n'avait jamais
vu le coach ni le debrief complets. Il s'ouvre maintenant tout seul, une
fois, quand une séance avec au moins une série se termine : la personne vient
de voir l'app servir, et le debrief PRO arrive sur l'écran suivant.

« Jamais eu d'essai » = `vip_until` vide : un essai fini, de parrainage ou
celui-ci, laisse sa date passée, et ne se rouvre pas.
"""
import logging

from core import db

logger = logging.getLogger(__name__)

ESSAI_JOURS = 3


def ouvrir_premier_essai(user_id: str, profil: dict) -> str | None:
    """Ouvre l'essai d'un compte gratuit qui n'en a jamais eu. Rend sa date de
    fin (ISO), ou None : déjà PRO, déjà eu un essai, ou écriture refusée."""
    if not user_id or not isinstance(profil, dict):
        return None
    if (profil.get("tier") or "free").strip().lower() == "vip" or profil.get("vip_until"):
        return None
    try:
        return db.grant_vip_days(user_id, ESSAI_JOURS)
    except Exception as e:      # la séance est enregistrée : l'essai attendra
        logger.error("essai : ouverture FAILED user=%s: %s", user_id, e)
        return None
