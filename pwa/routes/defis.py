"""Défis entre amis (v53) : lancer, inviter, accepter, refuser, annuler.

La page qui les montre est /amis (routes/amis.py, assemblée par
core/defis_liens.py). Gratuit pour tous, comme les amis. Les écritures
passent par core/db_defis.py, qui vérifie que chaque invité est un ami
accepté et que seul le créateur invite ou annule.
"""
import logging

from flask import Blueprint, g, redirect, request, url_for
from flask_limiter.util import get_remote_address

from core import db as core_db
from core import defis as calc
from core.analytics import track
from core.data import get_hist
from core.dates import logical_today_paris
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("defis", __name__)


def _par_compte():
    """Par compte et pas par adresse IP : en salle, on partage souvent le wifi."""
    return getattr(g, "user_id", "") or get_remote_address()


def _retour(message=""):
    return redirect(url_for("amis.index", m=message or None) + "#defis")


def _id():
    try:
        return int(request.form.get("defi") or 0)
    except (TypeError, ValueError):
        return 0


@bp.route("/amis/defis/lancer", methods=["POST"])
@limiter.limit("10 per hour;30 per day", key_func=_par_compte)
def lancer():
    f = request.form
    type_, depart = f.get("type"), f.get("depart")
    try:
        semaines = int(f.get("semaines") or 0)
    except ValueError:
        semaines = 0
    exercice = None
    if type_ == "progression":
        exercice = (f.get("exercice") or "").strip()
        if exercice not in calc.exercices_proposes(get_hist()):
            exercice = None
    if type_ not in calc.TYPES or semaines not in calc.SEMAINES or depart not in calc.DEPARTS \
            or (type_ == "progression" and not exercice):
        return _retour("defi_invalide")
    aujourdhui = logical_today_paris()
    debut, fin = calc.bornes(depart, semaines, aujourdhui)
    invites = [str(i)[:64] for i in f.getlist("amis")][:50]
    try:
        resultat, _ = core_db.creer_defi(g.user_id, type_, exercice, semaines, debut, fin,
                                         invites, aujourdhui)
    except core_db.DefisIndisponibles:
        return _retour("defi_indisponible")
    if resultat == "cree":
        track("defi_lance", {"type": type_, "semaines": semaines, "invites": len(set(invites))})
    return _retour(f"defi_{resultat}")


@bp.route("/amis/defis/inviter", methods=["POST"])
@limiter.limit("30 per hour;100 per day", key_func=_par_compte)
def inviter():
    invites = [str(i)[:64] for i in request.form.getlist("amis")][:50]
    try:
        resultat = core_db.inviter_au_defi(g.user_id, _id(), invites, logical_today_paris())
    except core_db.DefisIndisponibles:
        return _retour("defi_indisponible")
    return _retour(f"defi_{resultat}" if resultat else "")


def _repondre(accepte: bool):
    try:
        resultat = core_db.repondre_au_defi(g.user_id, _id(), accepte, logical_today_paris())
    except core_db.DefisIndisponibles:
        return _retour("defi_indisponible")
    if resultat == "acceptee":
        track("defi_accepte", {})
    return _retour(f"defi_{resultat}" if resultat else "defi_expire")


@bp.route("/amis/defis/accepter", methods=["POST"])
def accepter():
    return _repondre(True)


@bp.route("/amis/defis/refuser", methods=["POST"])
def refuser():
    return _repondre(False)


@bp.route("/amis/defis/annuler", methods=["POST"])
def annuler():
    try:
        ok = core_db.annuler_defi(g.user_id, _id(), logical_today_paris())
    except core_db.DefisIndisponibles:
        return _retour("defi_indisponible")
    return _retour("defi_annule" if ok else "")
