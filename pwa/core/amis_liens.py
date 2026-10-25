"""Amis (v52) : ce que d'autres parties de l'app déclenchent.

- la fin de séance publie la séance terminée dans le fil (`publier_fin_de_seance`) ;
- la fin de l'inscription d'un compte arrivé par un lien d'ami envoie sa
  demande (`demande_apres_inscription`).

Ni l'un ni l'autre ne fait jamais échouer la route qui l'appelle.
"""
import logging

from core import amis as calc
from core import db as core_db

logger = logging.getLogger(__name__)

# Posé par la page publique (`/?ref=CODE&ami=1`) pour quelqu'un qui n'est
# pas connecté ; il survit au passage par Google, comme `pending_ref`.
COOKIE_AMI = "pending_ami"


def compte_du_code(code):
    code = calc.lire_code(code)
    return core_db.get_user_by_referral_code(code) if code else None


def publier_fin_de_seance(user_id: str, seance: str, date_str: str, hist, duree_min) -> None:
    """La séance terminée rejoint le fil : nom, date, durée, tonnage,
    records (`core.amis.ligne_fil`). Ni note ni commentaire."""
    from core import debrief as core_debrief
    try:
        faits = core_debrief.collect_facts(hist, seance, date_str)
        ligne = calc.ligne_fil(core_db.session_id_for(user_id, date_str, seance),
                               date_str, seance, faits, duree_min)
        core_db.publier_seance(user_id, ligne)
    except Exception as e:
        logger.error("fil : séance non publiée user=%s : %s", user_id, e)


def demande_apres_inscription(user_id: str, code: str) -> str:
    """La demande part vers le titulaire du code, qui l'accepte ou non."""
    try:
        autre = compte_du_code(code)
        return core_db.demander(user_id, autre) if autre else "inconnu"
    except Exception as e:
        logger.error("demande d'ami après inscription FAILED user=%s : %s", user_id, e)
        return ""
