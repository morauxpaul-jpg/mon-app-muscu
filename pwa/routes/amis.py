"""Page « Amis » (v52) : ajouter par lien ou par code, accepter, retirer,
le fil des séances terminées des amis acceptés, les encouragements.

Gratuit pour tous (choix du propriétaire, 25/10) : un ami invité doit
pouvoir répondre et voir le fil sans payer.

Qui consent à quoi : utiliser le code d'un ami (lien ou saisie) ENVOIE une
demande ; c'est le titulaire du code qui l'accepte. Un code partagé trop
largement ne donne donc accès à rien sans son accord. Un ami pas encore
inscrit passe par le parrainage (`/?ref=CODE&ami=1`, cookie `pending_ami`) :
la demande part à la fin de son inscription (routes/onboarding.py).

Toutes les lectures et écritures passent par core/db_amis.py, qui applique
la règle de visibilité ; le calcul est dans core/amis.py.
"""
import datetime as _dt
import logging
import uuid

from flask import Blueprint, g, make_response, redirect, render_template, request, url_for
from flask_limiter.util import get_remote_address

from core import amis as calc
from core import db as core_db
from core.amis_liens import COOKIE_AMI, compte_du_code
from core.analytics import track
from core.dates import logical_today_paris
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("amis", __name__)

# Ce que la page dit après une action (?m=…).
MESSAGES = {
    "envoyee": "Demande envoyée. Ton ami la verra dans sa page Amis.",
    "acceptee": "Vous êtes amis.",
    "deja_amis": "Vous êtes déjà amis.",
    "deja_envoyee": "Demande déjà envoyée, en attente de réponse.",
    "soi_meme": "C'est ton propre code.",
    "trop": f"Tu as atteint {calc.MAX_AMIS} amis et demandes.",
    "inconnu": "Aucun compte avec ce code. Vérifie-le avec ton ami.",
    "refusee": "Demande refusée.",
    "annulee": "Demande annulée.",
    "retire": "Ami retiré. Vous ne voyez plus vos séances.",
    "masquees": "Tes séances sont masquées. Tes amis ne voient plus rien.",
    "visibles": "Tes amis voient de nouveau tes séances terminées.",
    "indisponible": "Les amis arrivent bientôt.",
}


def _par_compte():
    """Les limites comptent par compte : en salle, plusieurs personnes
    partagent souvent la même adresse IP."""
    return getattr(g, "user_id", "") or get_remote_address()


def _retour(message="", ancre=""):
    return redirect(url_for("amis.index", m=message or None) + (f"#{ancre}" if ancre else ""))


def _invitation_en_attente():
    """Code reçu par un lien d'ami : ?code=… ou le cookie posé par la page
    publique pour quelqu'un qui n'était pas connecté."""
    return calc.lire_code(request.args.get("code") or request.cookies.get(COOKIE_AMI) or "")


@bp.route("/amis")
def index():
    uid = g.user_id
    message = MESSAGES.get(request.args.get("m") or "", "")
    code = ""
    try:
        code = core_db.get_or_create_referral_code(uid)
    except Exception as e:
        logger.error("/amis code FAILED: %s", e)
    contexte = {"active": "plus", "code": code, "message": message, "indisponible": False,
                "invitation": None, "amis": [], "recues": [], "envoyees": [], "fil": [],
                "masquees": False}
    try:
        lignes = core_db.amities_de(uid)
        profils = core_db.profils([calc.autre(l, uid) for l in lignes] + [uid])
        classes = calc.classer(lignes, uid, profils)
        visibles = calc.visibles(lignes, uid, profils)
        depuis = (logical_today_paris() - _dt.timedelta(days=calc.FIL_JOURS)).isoformat()
        lignes_fil = core_db.fil(uid, visibles, depuis)
        cartes = calc.fil_affiche(lignes_fil, profils,
                                  core_db.encouragements_pour(lignes_fil), uid)
        contexte.update(classes, fil=cartes,
                        masquees=bool((profils.get(uid) or {}).get("seances_masquees")))
    except core_db.AmisIndisponibles:
        contexte.update(indisponible=True, message=MESSAGES["indisponible"])
        return render_template("amis.html", **contexte)

    attente = _invitation_en_attente()
    if attente and attente != code:
        autre = core_db.get_user_by_referral_code(attente)
        deja = {e["compte"] for cle in ("amis", "recues", "envoyees") for e in contexte[cle]}
        if autre and autre != uid and autre not in deja:
            contexte["invitation"] = {"code": attente,
                                      "nom": calc.nom_affiche(core_db.profils([autre]).get(autre))}
    resp = make_response(render_template("amis.html", **contexte))
    # Le cookie d'un lien d'ami ne sert qu'une fois : la carte garde le code.
    # Pas sur un préchargement (prefetch.js), qui n'est pas une visite.
    if request.cookies.get(COOKIE_AMI) and request.headers.get("Sec-Fetch-Mode", "navigate") == "navigate":
        resp.delete_cookie(COOKIE_AMI)
    return resp


@bp.route("/amis/demande", methods=["POST"])
@limiter.limit("20 per hour;50 per day", key_func=_par_compte)
def demande():
    autre = compte_du_code(request.form.get("code"))
    if not autre:
        resultat = "inconnu"
    else:
        try:
            resultat = core_db.demander(g.user_id, autre)
        except core_db.AmisIndisponibles:
            resultat = "indisponible"
    if resultat in ("envoyee", "acceptee"):
        track("ami_demande", {"resultat": resultat})
    resp = _retour(resultat)
    resp.delete_cookie(COOKIE_AMI)
    return resp


@bp.route("/amis/ignorer", methods=["POST"])
def ignorer():
    """« Pas maintenant » sur une invitation reçue par lien : rien n'est envoyé."""
    resp = _retour()
    resp.delete_cookie(COOKIE_AMI)
    return resp


def _action(faire, message):
    try:
        ok = faire(g.user_id, int(request.form.get("id") or 0))
    except (TypeError, ValueError):
        ok = False
    except core_db.AmisIndisponibles:
        return _retour("indisponible")
    return _retour(message if ok else "")


@bp.route("/amis/accepter", methods=["POST"])
def accepter():
    return _action(core_db.accepter, "acceptee")


@bp.route("/amis/refuser", methods=["POST"])
def refuser():
    return _action(core_db.refuser, "refusee")


@bp.route("/amis/annuler", methods=["POST"])
def annuler():
    return _action(core_db.annuler, "annulee")


@bp.route("/amis/retirer", methods=["POST"])
def retirer():
    return _action(core_db.retirer, "retire")


@bp.route("/amis/masquer", methods=["POST"])
def masquer():
    valeur = request.form.get("masquer") == "1"
    try:
        core_db.masquer_seances(g.user_id, valeur)
    except core_db.AmisIndisponibles:
        return _retour("indisponible")
    return _retour("masquees" if valeur else "visibles", "reglage")


@bp.route("/amis/encourager", methods=["POST"])
@limiter.limit("60 per hour;300 per day", key_func=_par_compte)
def encourager():
    compte = str(request.form.get("compte") or "")[:64]
    session_id = str(request.form.get("session") or "")[:64]
    try:
        session_id = str(uuid.UUID(session_id))   # la colonne est un uuid : 400 de PostgREST sinon
    except ValueError:
        return ("", 404)
    try:
        resultat = core_db.encourager(g.user_id, compte, session_id)
    except core_db.AmisIndisponibles:
        return _retour("indisponible")
    if resultat == "interdit":
        return ("", 404)
    if resultat == "ok":
        track("ami_encourage", {})
    return _retour("", f"s-{session_id}")
