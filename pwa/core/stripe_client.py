"""Stripe côté serveur : le client, le client Stripe d'un utilisateur, et la
résiliation qui précède la suppression d'un compte.

Sorti de `routes/billing.py` pour que la suppression de compte
(`routes/gestion.py`) puisse résilier sans importer un autre blueprint.
"""
import json
import logging

from flask import session

from core.db import _env
from core.data import get_profile

logger = logging.getLogger(__name__)


def client():
    """Module stripe configuré, ou None si non installé / non configuré."""
    key = _env("STRIPE_SECRET_KEY")
    if not key:
        return None
    try:
        import stripe
    except ImportError:
        logger.error("billing: paquet stripe absent")
        return None
    stripe.api_key = key
    return stripe


def to_plain(obj):
    """Convertit un objet Stripe en dict Python simple.

    ⚠️ Le SDK Stripe v15 n'expose PAS `.get()` sur ses objets (StripeObject) :
    `obj.get("x")` lève AttributeError. Mais `str(obj)` renvoie du JSON valide.
    On normalise donc tout en dict avant lecture. Les dicts simples (tests)
    passent au travers inchangés."""
    try:
        d = json.loads(str(obj))
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return obj


def resoudre_client(stripe, profile=None):
    """ID client Stripe : depuis le profil, sinon recherche par email."""
    if profile is None:
        try:
            profile = get_profile() or {}
        except Exception:
            profile = {}
    cid = profile.get("stripe_customer_id")
    if cid:
        return cid
    email = (session.get("email") or "").strip()
    if email:
        try:
            res = to_plain(stripe.Customer.list(email=email, limit=1))
            data = res.get("data") or []
            if data:
                return data[0]["id"]
        except Exception as e:
            logger.error("billing resolve customer FAILED: %s", e)
    return None


def resilier_avant_suppression(stripe) -> None:
    """Résilie tout abonnement Stripe encore vivant de l'utilisateur courant,
    AVANT que son compte soit supprimé. Sans ça, il restait prélevé chaque
    mois pour un compte qui n'existait plus.

    Lève une exception si Stripe ne répond pas : l'appelant doit alors
    REFUSER la suppression — mieux vaut un compte encore là qu'un prélèvement
    orphelin. Les abonnements sont marqués `account_deleted` : le webhook
    d'annulation qui suit ne recrée pas de profil pour un compte effacé."""
    if not stripe:
        return  # Stripe non configuré : rien n'a pu être souscrit.
    customer_id = resoudre_client(stripe)
    if not customer_id:
        return
    res = to_plain(stripe.Subscription.list(customer=customer_id, status="all", limit=100))
    for sub in res.get("data") or []:
        if sub.get("status") in ("canceled", "incomplete_expired"):
            continue
        stripe.Subscription.modify(sub["id"], metadata={"account_deleted": "1"})
        stripe.Subscription.cancel(sub["id"])
        logger.info("billing: abonnement %s résilié (suppression du compte)", sub["id"])
