"""Analytics produit — events de conversion (funnel), auto-hébergés sur Supabase.

Principe : **fire-and-forget**. Une erreur de tracking ne doit JAMAIS casser une
requête utilisateur. Tous les appels sont best-effort et avalent les exceptions.

Les events alimentent la console admin (`/admin/funnel`). Pas de tiers
(PostHog/Mixpanel), donc pas de bannière de consentement : tout est écrit côté
serveur en `service_role` (cf. core.db.insert_event, table `events`).
"""
import logging

from flask import g, has_request_context, render_template, request

from core import db as core_db

logger = logging.getLogger(__name__)


def _est_un_prechargement() -> bool:
    """Une page chargée d'avance (prefetch.js, au survol ou au toucher d'un
    lien) n'a pas été VUE. Toucher quatre cartes de « Plus » sans cliquer
    enregistrait quatre « offre vue » (audit du 30/09, R13) : le funnel
    comptait des murs que personne n'avait vus.

    Seules les lectures sont concernées : un POST est toujours un geste."""
    if not has_request_context() or request.method != "GET":
        return False
    if request.headers.get("X-Prefetch") == "1":
        return True
    mode = request.headers.get("Sec-Fetch-Mode")
    return mode is not None and mode != "navigate"


def track(event: str, props: dict | None = None, *,
          user_id: str | None = None, tier: str | None = None) -> None:
    """Enregistre un event de funnel. Best-effort — n'échoue jamais l'appelant.

    - `user_id` : par défaut lu depuis `flask.g` (contexte requête authentifiée).
      À passer explicitement hors de ce contexte (ex : webhook Stripe, où la
      requête n'est pas authentifiée et `g.user_id` est absent).
    - `tier` : par défaut déduit de `g.is_vip` ('vip' / 'free').
    """
    if _est_un_prechargement():
        return
    try:
        uid = user_id if user_id is not None else getattr(g, "user_id", None)
        t = tier if tier is not None else ("vip" if getattr(g, "is_vip", False) else "free")
        core_db.insert_event(uid, event, props or {}, t)
    except Exception as e:  # pragma: no cover - défensif
        logger.warning("analytics track(%s) failed: %s", event, e)


def paywall(feature: str, status: int = 200):
    """Rend le mur VIP plein écran en loggant un `paywall_viewed`.

    Centralise l'instrumentation des points de blocage VIP : au lieu d'ajouter
    un `track()` à chacun des ~7 `render_template("vip_wall.html", …)`, les
    routes appellent `return paywall("Coach IA")` (ou `paywall("Export", 403)`).
    """
    track("paywall_viewed", {"feature": feature})
    html = render_template("vip_wall.html", active="plus", feature=feature)
    return (html, status) if status != 200 else html
