"""Rapports de la CSP : ce que le navigateur a refusé d'exécuter.

La politique bloque désormais (core/csp.py). Un oubli — un onclick resté
dans un gabarit, un script sans jeton — ne se voit pas à l'écran : le bouton
ne fait simplement plus rien. Le navigateur envoie alors un rapport ici, et
il finit dans les journaux Railway (« CSP bloqué »).

Public (la page de connexion aussi a une politique) et hors CSRF : le
navigateur poste ces rapports lui-même, sans jeton ni cookie.
"""
import logging
from urllib.parse import urlsplit

from flask import Blueprint, request

from core.csp import RAPPORT
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("csp", __name__)

# Un même blocage revient à chaque page vue : on ne le consigne qu'une fois
# par processus, dans la limite de ce plafond.
_DEJA_VUS = set()
_PLAFOND = 200


def _chemin(url: str) -> str:
    """Le chemin seul : pas de domaine ni de paramètres (?ref=…) au journal."""
    try:
        return urlsplit(url or "").path or "?"
    except ValueError:
        return "?"


@bp.route(RAPPORT, methods=["POST"])
@limiter.limit("30 per minute")
def rapport():
    if (request.content_length or 0) > 8192:
        return ("", 413)
    corps = request.get_json(force=True, silent=True) or {}
    r = corps.get("csp-report") if isinstance(corps, dict) else None
    if not isinstance(r, dict):
        return ("", 204)
    directive = str(r.get("effective-directive") or r.get("violated-directive") or "?")[:60]
    bloque = str(r.get("blocked-uri") or "?")[:120]
    page = _chemin(str(r.get("document-uri") or ""))[:120]
    source = f"{_chemin(str(r.get('source-file') or ''))}:{r.get('line-number') or '?'}"[:140]
    extrait = str(r.get("script-sample") or "")[:80]
    cle = (directive, bloque, page, source)
    if cle in _DEJA_VUS:
        return ("", 204)
    if len(_DEJA_VUS) < _PLAFOND:
        _DEJA_VUS.add(cle)
    logger.warning("CSP bloqué : %s (%s) sur %s — %s %s", directive, bloque, page, source, extrait)
    return ("", 204)


# ── Erreurs JavaScript (static/js/erreurs.js) ────────────────────────────
# Le coach est resté vide sept jours en production sans rien dans les
# journaux : l'erreur était dans le navigateur (audit du 18/10, I-2). Chaque
# erreur distincte est consignée une fois par processus, comme les rapports
# de CSP. Réservé aux comptes connectés, jeton CSRF compris (fetch de la page).
_ERREURS_VUES = set()


@bp.route("/erreurs/js", methods=["POST"])
@limiter.limit("20 per minute")
def erreur_js():
    if (request.content_length or 0) > 4096:
        return ("", 413)
    corps = request.get_json(silent=True) or {}
    if not isinstance(corps, dict):
        return ("", 204)
    genre = str(corps.get("genre") or "?")[:20]
    message = " ".join(str(corps.get("message") or "").split())[:300]
    page = _chemin(str(corps.get("page") or ""))[:120]
    source = f"{_chemin(str(corps.get('source') or ''))}:{corps.get('ligne') or '?'}"[:200]
    if not message:
        return ("", 204)
    cle = (genre, message, page, source)
    if cle in _ERREURS_VUES:
        return ("", 204)
    if len(_ERREURS_VUES) < _PLAFOND:
        _ERREURS_VUES.add(cle)
    logger.warning("Erreur JS (%s) sur %s — %s : %s", genre, page, source, message)
    return ("", 204)
