"""Blueprint onboarding (Phase 4) — flow multi-étapes post-login.

Parcours :
  GET  /onboarding              → affiche le questionnaire Alpine.js (4 étapes)
  POST /onboarding/submit       → valide les infos et sauvegarde onboarding
                                  + profile (prenom) + éventuellement clone
                                  le programme choisi dans `programs`, puis
                                  redirige vers /.

L'état des 4 étapes vit côté client (Alpine.js). Le serveur ne gère qu'un
seul POST final avec tous les champs — plus simple et idempotent.

Le `before_request` global (app.py) redirige vers /onboarding tant que la
row `onboarding` est vide pour l'user. Les routes `/onboarding/*` sont
exemptées de cette gate pour éviter la boucle de redirection.
"""
from flask import Blueprint, render_template, request, redirect, url_for, g, session

from core.data import (save_onboarding, save_profile, save_prog_body, get_onboarding,
                       get_prog, get_profile, upsert_body_weight)
from core.dates import today_paris_str
from core import catalog
from core.analytics import track

import logging

logger = logging.getLogger(__name__)

bp = Blueprint("onboarding", __name__, url_prefix="/onboarding")


@bp.route("", methods=["GET"])
def index():
    # Si l'user a déjà fait l'onboarding et revient ici (via "refaire"),
    # on affiche quand même le formulaire vide.
    existing = get_onboarding() or {}
    # Ajouter equipment_details depuis le programme si disponible
    if "equipment_details" not in existing:
        prog = get_prog() or {}
        existing["equipment_details"] = prog.get("_equipment_details", [])
    # Poids et taille vivent dans `profiles`, pas dans `onboarding` : on les
    # rapatrie pour qu'un re-onboarding ne les redemande pas à blanc.
    try:
        profil = get_profile() or {}
        for cle in ("poids_kg", "taille_cm"):
            if profil.get(cle):
                existing.setdefault(cle, profil[cle])
    except Exception as e:
        logger.warning("onboarding: profil illisible (%s)", e)
    is_vip = bool(getattr(g, "is_vip_full", False))
    return render_template(
        "onboarding.html",
        active=None,
        catalog_programs=catalog.list_programs(is_vip=is_vip),
        existing=existing,
    )


@bp.route("/recommend", methods=["POST"])
def recommend():
    """Endpoint JSON appelé par Alpine.js après l'étape 3 pour obtenir
    les IDs de programmes recommandés."""
    from flask import jsonify
    data = request.get_json(silent=True) or {}
    is_vip = bool(getattr(g, "is_vip_full", False))
    ids = catalog.recommend(
        niveau=data.get("niveau", ""),
        frequence=int(data.get("frequence") or 3),
        equipement=data.get("equipement", ""),
        objectif=data.get("objectif", ""),
        is_vip=is_vip,
    )
    return jsonify({"recommended": ids})


@bp.route("/submit", methods=["POST"])
def submit():
    f = request.form
    prenom = (f.get("prenom") or "").strip()[:40]
    try:
        age = int(f.get("age") or 0) or None
    except ValueError:
        age = None
    sexe = (f.get("sexe") or "").strip()[:20]

    def _mesure(champ, mini, maxi):
        """Nombre borné, ou None. Un gabarit hors bornes vaut mieux absent :
        `core/strength.py` retombe alors sur ses seuils absolus au lieu de
        calculer des ratios avec une valeur abérrante."""
        try:
            v = float(str(f.get(champ) or "").replace(",", "."))
        except (TypeError, ValueError):
            return None
        return round(v, 1) if mini <= v <= maxi else None

    poids_kg = _mesure("poids_kg", 30, 300)
    taille_cm = _mesure("taille_cm", 100, 250)
    niveau = (f.get("niveau") or "").strip()[:20]
    try:
        frequence = max(2, min(6, int(f.get("frequence") or 3)))
    except ValueError:
        frequence = 3
    objectif = (f.get("objectif") or "").strip()[:30]
    equipement = (f.get("equipement") or "").strip()[:30]
    programme_id = (f.get("programme_id") or "").strip()

    # Équipement détaillé (JSON array depuis le formulaire)
    import json
    try:
        equipment_details = json.loads(f.get("equipment_details") or "[]")
        if not isinstance(equipment_details, list):
            equipment_details = []
    except (json.JSONDecodeError, TypeError):
        equipment_details = []

    # 1. Sauvegarde onboarding + prenom côté profile. completed_at sert
    # de garde-fou anti-« séances manquées » : on ne marque jamais comme
    # manquée une séance planifiée AVANT la création du compte (calendrier,
    # dashboard).
    today_iso = today_paris_str()

    save_onboarding({
        "prenom": prenom,
        "age": age,
        "sexe": sexe,
        "niveau": niveau,
        "frequence": frequence,
        "objectif": objectif,
        "equipement": equipement,
        "completed_at": today_iso,
    })
    # Le profil porte le gabarit : les standards de force le comparent au
    # poids de corps, la page Nutrition en tire le TDEE. Sans lui, les deux
    # basculent sur des valeurs génériques — le calcul existe mais ne sert
    # à personne.
    profil = {"prenom": prenom}
    if poids_kg:
        profil["poids_kg"] = poids_kg
    if taille_cm:
        profil["taille_cm"] = taille_cm
    if age:
        profil["age"] = age
    if sexe:
        # `profiles.sexe` attend H/F ; l'onboarding propose aussi « autre »,
        # qui reste sans valeur ici (les standards retombent sur le masculin).
        initiale = sexe.strip().upper()[:1]
        if initiale in ("H", "F"):
            profil["sexe"] = initiale
    save_profile(profil)

    # Première pesée : la courbe de poids démarre avec un point au lieu d'un
    # écran vide, et la pesée du jour est celle que l'utilisateur vient de
    # donner.
    if poids_kg:
        try:
            upsert_body_weight(today_iso, poids_kg)
        except Exception as e:
            logger.warning("onboarding: première pesée non enregistrée (%s)", e)

    # 2. Si l'user a choisi un programme du catalogue, on le clone.
    #    S'il a choisi "custom" (créer mon propre) → on ne touche pas à programs,
    #    il ira sur /programme pour construire le sien.
    #    Pour un re-onboarding volontaire (refaire depuis Gestion), on écrase
    #    le programme existant. Pour un premier onboarding, on le clone normalement.
    # Free users : on bloque les programmes PRO au niveau submit pour éviter
    # un bypass client-side (un user bidouille le <input hidden>).
    is_vip = bool(getattr(g, "is_vip_full", False))
    if programme_id and programme_id != "custom" and not is_vip and not catalog.is_free(programme_id):
        programme_id = ""
    if programme_id and programme_id != "custom" and catalog.get_program(programme_id):
        # Passer l'équipement pour adapter le programme (substitutions)
        equipment_arg = equipment_details if equipement != "salle" else None
        prog = catalog.build_program(programme_id, frequence, equipment=equipment_arg)
        # _started_at = date d'aujourd'hui à l'onboarding initial. Évite que
        # les jours d'entraînement de la semaine en cours antérieurs à
        # l'inscription soient marqués comme manqués dans le calendrier.
        prog.setdefault("_started_at", today_iso)
        # Remplace le corps du programme ; les données personnelles (badges,
        # record, exos perso…) d'un éventuel re-onboarding sont conservées.
        merged = save_prog_body(prog)
        # L'équipement est une donnée personnelle : posé après la fusion.
        merged["_equipment_details"] = equipment_details
        merged["_equipement"] = equipement
        from core.data import save_prog as _sp
        _sp(merged)

    session["onboarded"] = True
    track("onboarding_completed", {
        "niveau": niveau, "objectif": objectif, "frequence": frequence,
        "programme": programme_id or "custom",
    })

    # Parrainage : si l'onboarding vient d'un lien d'invitation (cookie posé sur
    # la landing), on crédite parrain + filleul une seule fois.
    resp = redirect(url_for("accueil.index"))
    ref = (request.cookies.get("pending_ref") or "").strip()
    if ref:
        resp.delete_cookie("pending_ref")
        from routes.parrainage import apply_referral
        if apply_referral(g.user_id, ref):
            # Le filleul passe en essai VIP immédiatement (revalidation forcée).
            session.pop("is_vip", None)
            session.pop("is_vip_full", None)
    return resp
