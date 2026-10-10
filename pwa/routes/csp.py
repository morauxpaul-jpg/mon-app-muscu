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
