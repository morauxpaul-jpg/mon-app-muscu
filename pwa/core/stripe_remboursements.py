"""Remboursements et litiges Stripe : retirer PRO quand l'argent repart.

Le webhook ne connaissait que le paiement et la fin d'abonnement (audit du
03/10, M7). Un achat « à vie » remboursé, ou un paiement contesté auprès de la
banque (chargeback), laissait le compte PRO pour toujours : l'argent revenait
au client, l'accès restait.

* `charge.refunded` — remboursement TOTAL : retour en gratuit, sauf si le
  client a encore un abonnement actif (un geste commercial sur une mensualité
  ne coupe pas l'abonnement en cours ; sa fin passera par les événements
  d'abonnement). Un remboursement partiel ne change rien.
* `charge.dispute.created` — litige ouvert : retour en gratuit tout de suite
  (sinon l'accès continue pendant les semaines de la procédure).
* `charge.dispute.closed` — litige GAGNÉ : PRO rendu. Perdu : rien à faire.

Chaque fonction est idempotente (rejouer l'événement réécrit le même tier) et
laisse remonter une erreur de base : le webhook répond alors 500 et Stripe
rejoue.
"""
import logging

from core import db as core_db
from core.analytics import track
from core.stripe_client import to_plain

logger = logging.getLogger(__name__)


def _utilisateur(stripe, obj: dict):
    """Compte concerné : metadata.user_id, sinon le client Stripe. Un litige
    ne porte que l'id du paiement : on relit le paiement pour son client."""
    uid = (obj.get("metadata") or {}).get("user_id")
    if uid:
        return uid
    customer = obj.get("customer")
    if not customer and obj.get("charge") and stripe is not None:
        try:
            charge = to_plain(stripe.Charge.retrieve(obj["charge"]))
            uid = (charge.get("metadata") or {}).get("user_id")
            if uid:
                return uid
            customer = charge.get("customer")
        except Exception as e:
            logger.error("stripe litige: paiement %s illisible: %s", obj.get("charge"), e)
            raise
    return core_db.get_user_by_stripe_customer(customer) if customer else None


def _abonnement_actif(stripe, customer) -> bool:
    if not customer or stripe is None:
        return False
    res = to_plain(stripe.Subscription.list(customer=customer, status="active", limit=1))
    return bool(res.get("data"))


def rembourse(stripe, charge: dict) -> str:
    """Traite `charge.refunded`. Retourne ce qui a été fait (journal, tests)."""
    total = int(charge.get("amount") or 0)
    rendu = int(charge.get("amount_refunded") or 0)
    if not (charge.get("refunded") or (total and rendu >= total)):
        return "partiel"
    uid = _utilisateur(stripe, charge)
    if not uid:
        return "inconnu"
    if _abonnement_actif(stripe, charge.get("customer")):
        return "abonnement-actif"
    core_db.set_user_tier(uid, "free")
    track("vip_refunded", {"montant": rendu}, user_id=uid, tier="free")
    logger.info("stripe: remboursement total, PRO retiré user=%s", uid)
    return "retire"


def litige_ouvert(stripe, dispute: dict) -> str:
    uid = _utilisateur(stripe, dispute)
    if not uid:
        return "inconnu"
    core_db.set_user_tier(uid, "free")
    track("stripe_dispute", {"raison": dispute.get("reason") or "", "statut": "ouvert"},
          user_id=uid, tier="free")
    logger.warning("stripe: litige ouvert, PRO suspendu user=%s", uid)
    return "suspendu"


def litige_clos(stripe, dispute: dict) -> str:
    if dispute.get("status") != "won":
        return "perdu"
    uid = _utilisateur(stripe, dispute)
    if not uid:
        return "inconnu"
    core_db.set_user_tier(uid, "vip")
    track("stripe_dispute", {"statut": "gagne"}, user_id=uid, tier="vip")
    logger.info("stripe: litige gagné, PRO rendu user=%s", uid)
    return "rendu"
