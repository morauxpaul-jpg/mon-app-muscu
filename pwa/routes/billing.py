"""Blueprint billing — abonnements Premium via Stripe Checkout.

Flux :
  - POST /billing/checkout : crée une session Stripe Checkout (carte, Apple Pay,
    Google Pay) pour le plan choisi et redirige vers la page de paiement Stripe.
  - GET  /billing/success  : retour après paiement → vérifie la session côté
    serveur et active le VIP immédiatement (filet, en plus du webhook).
  - POST /billing/webhook  : Stripe notifie les événements (paiement réussi,
    abonnement annulé/expiré, remboursement, litige) → source de vérité pour le tier. Public + exempté
    CSRF (sécurisé par la signature Stripe, pas par la session).
  - POST /billing/portal   : ouvre le portail client Stripe (gérer/annuler).

Prix définis inline (price_data) : aucun ID de prix à pré-créer ni à stocker,
fonctionne à l'identique en mode test et en mode live — il suffit de changer la
clé secrète. Variables d'env : STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET.
"""
import logging

from flask import (
    Blueprint, request, redirect, url_for, render_template, session, g,
)

from core.db import _env
from core import db as core_db
from core.limiter import limiter
from core.stripe_client import (
    client as _stripe, to_plain as _to_plain, resoudre_client as _resolve_customer_id,
)
from core.analytics import track
from core import stripe_remboursements as remb

logger = logging.getLogger(__name__)

bp = Blueprint("billing", __name__)

# Plans proposés. amount = centimes d'euro.
PLANS = {
    "monthly":  {"label": "Premium mensuel", "amount": 499,  "mode": "subscription", "interval": "month"},
    "annual":   {"label": "Premium annuel",  "amount": 3999, "mode": "subscription", "interval": "year"},
    "lifetime": {"label": "Premium à vie",   "amount": 7999, "mode": "payment",      "interval": None},
}


def _base_url() -> str:
    return request.url_root.rstrip("/")


# ── Helpers customer / abonnements ───────────────────────────────
def _active_subscriptions(stripe, customer_id):
    if not customer_id:
        return []
    try:
        res = _to_plain(stripe.Subscription.list(customer=customer_id, status="active", limit=10))
        return res.get("data") or []
    except Exception as e:
        logger.error("billing list subs FAILED: %s", e)
        return []


def detect_current_plan():
    """Plan d'abonnement actif de l'utilisateur courant : 'monthly' | 'annual'
    | None (lifetime, VIP manuel, ou pas d'abonnement). Best-effort."""
    stripe = _stripe()
    if not stripe:
        return None
    subs = _active_subscriptions(stripe, _resolve_customer_id(stripe))
    if not subs:
        return None
    try:
        items = ((subs[0].get("items") or {}).get("data")) or []
        interval = (((items[0].get("price") or {}).get("recurring") or {}).get("interval"))
        if interval == "year":
            return "annual"
        if interval == "month":
            return "monthly"
    except Exception:
        pass
    return "monthly"


def _supersede_and_cancel(stripe, sub_id):
    """Annule un ancien abonnement lors d'un upgrade. On marque d'abord
    metadata.superseded=1 : le webhook customer.subscription.deleted saura
    alors NE PAS rétrograder l'utilisateur (qui vient justement d'upgrader)."""
    if not sub_id:
        return
    try:
        stripe.Subscription.modify(sub_id, metadata={"superseded": "1"})
    except Exception as e:
        logger.warning("billing supersede modify FAILED %s: %s", sub_id, e)
    try:
        stripe.Subscription.cancel(sub_id)
        logger.info("billing: ancien abonnement %s annulé (upgrade)", sub_id)
    except Exception as e:
        logger.warning("billing cancel old sub FAILED %s: %s", sub_id, e)


def _handle_upgrade_cancel(stripe, meta, new_sub_id):
    """Si la session portait un previous_subscription (upgrade), l'annule."""
    prev = (meta or {}).get("previous_subscription")
    if prev and prev != new_sub_id:
        _supersede_and_cancel(stripe, prev)


def _activate_vip(user_id: str, customer_id=None) -> None:
    """Passe l'utilisateur en VIP et mémorise son customer Stripe (best-effort :
    la colonne stripe_customer_id peut ne pas exister si la migration SQL n'a
    pas encore été appliquée — on n'échoue pas le passage VIP pour autant)."""
    # Pas de try ici : si le passage VIP échoue, le webhook doit répondre
    # en erreur pour que Stripe rejoue — sinon le payeur reste gratuit.
    core_db.set_user_tier(user_id, "vip")
    # Event funnel : émis hors contexte requête authentifiée (webhook) → user_id
    # explicite, tier forcé 'vip'.
    track("vip_activated", user_id=user_id, tier="vip")
    if customer_id:
        try:
            core_db.set_stripe_customer(user_id, customer_id)
        except Exception as e:
            logger.error("billing store customer FAILED user=%s: %s", user_id, e)


# ────────────────────────────────────────────────────────────────
# Checkout
# ────────────────────────────────────────────────────────────────
@bp.route("/billing/checkout", methods=["POST"])
@limiter.limit("10 per minute")
def checkout():
    plan_key = (request.form.get("plan") or "").strip()
    plan = PLANS.get(plan_key)
    if not plan:
        return redirect(url_for("premium.index"))

    stripe = _stripe()
    if not stripe:
        return render_template(
            "error.html", code=503,
            message="Le paiement est momentanément indisponible. Réessaie plus tard.",
        ), 503

    line_item = {
        "quantity": 1,
        "price_data": {
            "currency": "eur",
            "unit_amount": plan["amount"],
            "product_data": {"name": "Muscu Tracker — " + plan["label"]},
        },
    }
    if plan["mode"] == "subscription":
        line_item["price_data"]["recurring"] = {"interval": plan["interval"]}

    params = {
        "mode": plan["mode"],
        "line_items": [line_item],
        "success_url": _base_url() + url_for("billing.success") + "?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": _base_url() + url_for("premium.index"),
        "client_reference_id": g.user_id,
        "metadata": {"user_id": g.user_id, "plan": plan_key},
        "allow_promotion_codes": True,
    }
    email = (session.get("email") or "").strip()
    if email:
        params["customer_email"] = email
    if plan["mode"] == "subscription":
        params["subscription_data"] = {"metadata": {"user_id": g.user_id, "plan": plan_key}}

    # Upgrade : si l'utilisateur est déjà abonné, on note son abonnement courant
    # pour l'annuler une fois le nouveau plan payé (pas de double facturation).
    if getattr(g, "is_vip_full", False):
        try:
            prev_subs = _active_subscriptions(stripe, _resolve_customer_id(stripe))
            if prev_subs:
                params["metadata"]["previous_subscription"] = prev_subs[0]["id"]
                # Réutilise le même client Stripe (évite un doublon de customer).
                params["customer"] = prev_subs[0].get("customer") or _resolve_customer_id(stripe)
                params.pop("customer_email", None)  # customer et customer_email sont exclusifs
        except Exception as e:
            logger.error("billing upgrade detect FAILED: %s", e)

    try:
        cs = stripe.checkout.Session.create(**params)
    except Exception as e:
        logger.error("billing checkout FAILED user=%s plan=%s: %s", g.user_id, plan_key, e)
        return render_template(
            "error.html", code=502,
            message="Le paiement n'a pas pu démarrer. Réessaie dans un instant.",
        ), 502
    track("checkout_started", {"plan": plan_key, "upgrade": bool(getattr(g, "is_vip_full", False))})
    return redirect(cs.url, code=303)


# ────────────────────────────────────────────────────────────────
# Retour après paiement
# ────────────────────────────────────────────────────────────────
@bp.route("/billing/success")
def success():
    sid = (request.args.get("session_id") or "").strip()
    activated = False
    stripe = _stripe()
    if sid and stripe:
        try:
            cs = _to_plain(stripe.checkout.Session.retrieve(sid))
            status = cs.get("status")            # 'complete' quand la session est finalisée
            pstatus = cs.get("payment_status")   # 'paid' / 'no_payment_required'
            ref = cs.get("client_reference_id")
            done = (status == "complete") or (pstatus in ("paid", "no_payment_required"))
            if done and ref == g.user_id:
                _activate_vip(g.user_id, cs.get("customer"))
                _handle_upgrade_cancel(stripe, cs.get("metadata"), cs.get("subscription"))
                # Rafraîchit le cache VIP de la session immédiatement (PAYANT →
                # accès complet : is_vip ET is_vip_full).
                session["is_vip"] = True
                session["is_vip_full"] = True
                import time as _t
                session["is_vip_ts"] = _t.time()
                activated = True
            else:
                logger.warning(
                    "billing success NON activé: status=%s payment=%s ref=%s uid=%s",
                    status, pstatus, ref, getattr(g, "user_id", None),
                )
        except Exception as e:
            logger.error("billing success verify FAILED: %s", e)
    elif not stripe:
        logger.error("billing success: _stripe() None (STRIPE_SECRET_KEY ?)")

    # Dans tous les cas, on invalide le cache VIP de la session : si le webhook
    # a déjà fait passer le tier en base, la prochaine navigation le reflétera
    # (sinon l'utilisateur resterait « free » jusqu'à expiration du TTL).
    if not activated:
        session.pop("is_vip", None)
        session.pop("is_vip_full", None)
        session.pop("is_vip_ts", None)
    return render_template("billing_success.html", active="plus", activated=activated)


# ────────────────────────────────────────────────────────────────
# Webhook Stripe (public, exempté CSRF — sécurisé par la signature)
# ────────────────────────────────────────────────────────────────
@bp.route("/billing/webhook", methods=["POST"])
def webhook():
    stripe = _stripe()
    if not stripe:
        return "", 503
    secret = _env("STRIPE_WEBHOOK_SECRET")
    if not secret:
        # Sans secret on ne peut pas vérifier l'authenticité → on refuse
        # (jamais de traitement d'un webhook non signé : ce serait une faille
        # permettant à n'importe qui de passer VIP).
        logger.error("billing webhook: STRIPE_WEBHOOK_SECRET absent")
        return "", 503

    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except Exception as e:
        logger.warning("billing webhook signature refusée: %s", e)
        return "", 400

    event = _to_plain(event)  # StripeObject → dict (cf. _to_plain)
    etype = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    logger.info("billing webhook reçu: %s", etype)

    try:
        if etype == "checkout.session.completed":
            uid = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("user_id")
            if uid:
                _activate_vip(uid, obj.get("customer"))
                _handle_upgrade_cancel(stripe, obj.get("metadata"), obj.get("subscription"))
            else:
                # Un paiement abouti qui n'active personne : à voir dans
                # Stripe, jamais en silence (audit du 06/10, 4.1-5).
                logger.error("billing: paiement sans compte associé (session %s, client %s)",
                             obj.get("id"), obj.get("customer"))
                track("paiement_sans_compte", {"session": obj.get("id") or "",
                                               "client": obj.get("customer") or ""},
                      user_id=None, tier="free")
        elif etype == "customer.subscription.deleted":
            _downgrade_from_subscription(obj)
        elif etype == "customer.subscription.updated":
            status = obj.get("status")
            if status in ("canceled", "unpaid", "incomplete_expired"):
                _downgrade_from_subscription(obj)
        # L'argent repart (remboursement total, litige bancaire) : PRO aussi
        # (core/stripe_remboursements.py, audit du 03/10, M7). À abonner dans
        # le tableau de bord Stripe : charge.refunded, charge.dispute.created,
        # charge.dispute.closed.
        elif etype == "charge.refunded":
            logger.info("billing remboursement: %s", remb.rembourse(stripe, obj))
        elif etype == "charge.dispute.created":
            logger.info("billing litige ouvert: %s", remb.litige_ouvert(stripe, obj))
        elif etype == "charge.dispute.closed":
            logger.info("billing litige clos: %s", remb.litige_clos(stripe, obj))
    except Exception as e:
        # 500 : Stripe rejoue l'événement (plusieurs jours, avec délai
        # croissant). Répondre 200 ici laissait un payeur gratuit — ou un
        # résilié PRO — dès qu'une écriture échouait. Les traitements
        # ci-dessus sont idempotents : un rejeu ne double rien.
        logger.error("billing webhook handler FAILED type=%s: %s", etype, e)
        return "", 500
    return "", 200


def _downgrade_from_subscription(obj) -> None:
    """Repasse en free l'utilisateur d'un abonnement annulé/expiré.

    Exception : si l'abonnement a été marqué `superseded` (annulé lors d'un
    upgrade vers un plan supérieur ou le « à vie »), on NE rétrograde PAS —
    l'utilisateur vient au contraire de monter en gamme."""
    if (obj.get("metadata") or {}).get("superseded"):
        logger.info("billing: abonnement supersédé (upgrade) — pas de rétrogradation")
        return
    if (obj.get("metadata") or {}).get("account_deleted"):
        # Résilié par la suppression du compte : rétrograder recréerait un
        # profil pour un compte qui n'existe plus.
        return
    uid = (obj.get("metadata") or {}).get("user_id")
    if not uid:
        # Une erreur de lecture remonte (le webhook rejouera) ; un client
        # inconnu, lui, n'a personne à rétrograder.
        uid = core_db.get_user_by_stripe_customer(obj.get("customer"))
    if uid:
        core_db.set_user_tier(uid, "free")
        # Pendant de `vip_activated` : sans lui, le funnel ne voyait que des
        # entrées (audit du 06/10, 4.1-5).
        track("vip_resilie", {"statut": obj.get("status") or "deleted"}, user_id=uid, tier="free")


# ────────────────────────────────────────────────────────────────
# Portail client (gérer / annuler l'abonnement)
# ────────────────────────────────────────────────────────────────
@bp.route("/billing/portal", methods=["POST"])
@limiter.limit("10 per minute")
def portal():
    stripe = _stripe()
    if not stripe:
        return redirect(url_for("premium.index"))
    customer_id = _resolve_customer_id(stripe)
    if not customer_id:
        return redirect(url_for("premium.index"))
    try:
        ps = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=_base_url() + url_for("premium.index"),
        )
    except Exception as e:
        logger.error("billing portal FAILED: %s", e)
        return redirect(url_for("premium.index"))
    # ps.url est un attribut (OK), mais on sécurise via _to_plain au cas où.
    return redirect(_to_plain(ps).get("url") or ps.url, code=303)
