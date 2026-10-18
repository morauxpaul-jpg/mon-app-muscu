"""Suivi corporel — l'onglet « Corps » de Progrès (/progres/corps).

Demande du propriétaire (18/10/2026) : le poids et les photos au même
endroit, hors de la page Progrès déjà chargée ; « en ajoutant les photos on
ne pense pas forcément à se peser ». La page réunit donc :
  - la carte « Poids corporel » (gratuite, comme avant ; calcul dans
    core/poids_courbe.py, enregistrement par /progres/poids) ;
  - les photos de progression (PRO) : ajouter (face, profil, dos), comparer
    deux photos du même angle avec l'écart et le poids, télécharger,
    supprimer. Calculs dans core/photos_corps.py, fichiers dans
    core/db_photos.py ;
  - sous les photos, une invitation à se peser quand les photos récentes
    n'ont pas de pesée ce jour-là.

Qui voit quoi :
  - les photos et leur ajout sont PRO (essai compris) ; un compte gratuit
    voit le poids et un aperçu verrouillé ;
  - un fichier ne se sert qu'à son propriétaire, PRO ou non : un compte
    redevenu gratuit garde le droit de télécharger et de supprimer ses
    photos (l'export RGPD pointe vers elles).

La comparaison se choisit par l'adresse (?angle=face&avant=12&apres=40) :
la page marche sans script, sauf l'ajout, qui doit réduire la photo dans
le navigateur avant l'envoi (static/js/photos.js).
"""
import hashlib
import logging

from flask import Blueprint, Response, abort, g, jsonify, redirect, render_template, request, url_for

from core.analytics import track
from core.data import (
    PhotosIndisponibles, enregistrer_photo, get_photo, get_profile, list_body_weight,
    list_photos, supprimer_photo,
)
from core.dates import today_paris, today_paris_str
from core.db import lire_fichier
from core.limiter import limiter
from core.photos_corps import (
    ANGLES, LIBELLES, OCTETS_MAX, PHOTOS_MAX, angle_valide, comparaison, date_valide,
    est_jpeg, fiche, index_pesees, par_angle, pesee_manquante,
)
from core.poids_courbe import carte_poids

logger = logging.getLogger(__name__)

bp = Blueprint("corps", __name__)


def _pro() -> bool:
    return bool(getattr(g, "is_vip", False))


def _photos(pesees: list) -> dict:
    """Le contexte de la partie photos (PRO), ou {} hors PRO."""
    if not _pro():
        return {}
    dispo = True
    try:
        photos = list_photos()
    except PhotosIndisponibles:
        photos, dispo = [], False
    groupes = par_angle([fiche(p, pesees) for p in photos])
    angle = (angle_valide(request.args.get("angle"))
             or next((a for a in ANGLES if groupes[a]), "face"))
    liste = groupes[angle]
    return {
        "dispo": dispo, "angle": angle, "libelle": LIBELLES[angle],
        "angles": [(a, LIBELLES[a], len(groupes[a])) for a in ANGLES],
        "liste": list(reversed(liste)),
        "comparaison": comparaison(liste, request.args.get("avant"), request.args.get("apres")),
        "seule": liste[0] if len(liste) == 1 else None,
        "total": len(photos), "plein": len(photos) >= PHOTOS_MAX, "photos_max": PHOTOS_MAX,
        "erreur": request.args.get("erreur") == "suppression",
        "pesee": pesee_manquante(photos, pesees, today_paris()),
    }


@bp.route("/progres/corps")
def page():
    try:
        entrees = list_body_weight(limit=5000)
    except Exception as e:      # migration v33 absente : la page sans le poids
        logger.error("corps list_body_weight FAILED: %s", e)
        entrees = []
    profil = get_profile() or {}
    pesees = index_pesees(entrees)
    return render_template(
        "corps.html", active="progres", onglet="corps",
        weight=carte_poids(entrees, goal=profil.get("objectif_nutrition") or ""),
        ph=_photos(pesees), today_iso=today_paris_str(),
    )


@bp.route("/progres/photos")
def ancienne_page():
    """L'ancienne page des photos (18/10, avant l'onglet Corps) : liens déjà
    envoyés, favoris."""
    return redirect(url_for("corps.page", **request.args.to_dict()) + "#photos")


def _refus(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


@bp.route("/progres/photos", methods=["POST"])
@limiter.limit("60 per hour")
def ajouter():
    if not _pro():
        return _refus("Les photos de progression sont réservées aux membres PRO.", 403)
    angle = angle_valide(request.form.get("angle"))
    jour = date_valide(request.form.get("date"), today_paris())
    if not angle or not jour:
        return _refus("Choisis face, profil ou dos, et une date qui n'est pas dans le futur.")
    fichiers = [request.files.get("image"), request.files.get("miniature")]
    image, miniature = [f.read(OCTETS_MAX + 1) if f else b"" for f in fichiers]
    if len(image) > OCTETS_MAX or len(miniature) > OCTETS_MAX:
        return _refus("Photo trop lourde, même réduite. Réessaie avec une autre.", 413)
    if not est_jpeg(image) or not est_jpeg(miniature):
        return _refus("Ce fichier n'est pas une photo lisible.")
    try:
        photos = list_photos()
        remplace = any(str(p.get("date"))[:10] == jour.isoformat() and p.get("angle") == angle
                       for p in photos)
        if not remplace and len(photos) >= PHOTOS_MAX:
            return _refus(f"Tu as atteint {PHOTOS_MAX} photos : supprimes-en avant d'en ajouter.")
        ligne = enregistrer_photo(jour.isoformat(), angle, image, miniature)
    except PhotosIndisponibles:
        return _refus("Les photos arrivent bientôt : la base de données doit d'abord être mise à jour.", 503)
    except Exception as e:
        logger.error("photo ajout FAILED user=%s: %s", getattr(g, "user_id", "?"), e)
        return _refus("L'envoi a échoué. Réessaie dans un instant.", 502)
    track("photo_ajoutee", {"angle": angle, "remplace": remplace})
    return jsonify({"ok": True, "id": ligne.get("id"), "remplace": remplace,
                    "url": url_for("corps.page", angle=angle) + "#photos"})


@bp.route("/progres/photos/<int:photo_id>/image")
# Une grille compte une requête par miniature : la limite commune (60 par
# minute et par adresse) bloquait la page ouverte deux fois de suite.
@limiter.limit("600 per minute")
def image(photo_id: int):
    """Le fichier, à son propriétaire seulement. `no-cache` : le navigateur
    redemande à chaque fois (réponse 304 sans relire le fichier si rien n'a
    changé). Sans ça, un autre compte ouvert ensuite sur le même téléphone
    pourrait revoir la photo depuis le cache, sans passer par ce contrôle."""
    try:
        photo = get_photo(photo_id)
    except PhotosIndisponibles:
        abort(404)
    if not photo:
        abort(404)
    chemin = photo["miniature"] if request.args.get("mini") else photo["chemin"]
    etiquette = hashlib.sha256(chemin.encode()).hexdigest()[:32]
    entetes = {"Cache-Control": "private, no-cache"}
    telecharger = bool(request.args.get("telecharger"))
    if telecharger:
        nom = f"photo-{photo.get('angle')}-{str(photo.get('date'))[:10]}.jpg"
        entetes["Content-Disposition"] = f"attachment; filename={nom}"
    if etiquette in request.if_none_match:
        reponse = Response(status=304, headers=entetes)
        reponse.set_etag(etiquette)
        return reponse
    try:
        octets = lire_fichier(chemin)
    except Exception as e:
        logger.error("photo lecture FAILED id=%s: %s", photo_id, e)
        abort(502)
    reponse = Response(octets, mimetype="image/jpeg", headers=entetes)
    reponse.set_etag(etiquette)
    return reponse


@bp.route("/progres/photos/<int:photo_id>/supprimer", methods=["POST"])
def supprimer(photo_id: int):
    angle = angle_valide(request.form.get("angle"))
    try:
        supprimer_photo(photo_id)
    except PhotosIndisponibles:
        pass
    except Exception as e:
        logger.error("photo suppression FAILED id=%s: %s", photo_id, e)
        return redirect(url_for("corps.page", angle=angle, erreur="suppression") + "#photos")
    return redirect(url_for("corps.page", angle=angle) + "#photos")
