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

from core.data import save_onboarding, save_profile, save_prog, get_onboarding
from core import catalog

bp = Blueprint("onboarding", __name__, url_prefix="/onboarding")


@bp.route("", methods=["GET"])
def index():
    # Si l'user a déjà fait l'onboarding et revient ici (via "refaire"),
    # on affiche quand même le formulaire vide.
    existing = get_onboarding() or {}
    return render_template(
        "onboarding.html",
        active=None,
        catalog_programs=catalog.list_programs(),
        existing=existing,
    )


@bp.route("/recommend", methods=["POST"])
def recommend():
    """Endpoint JSON appelé par Alpine.js après l'étape 3 pour obtenir
    les IDs de programmes recommandés."""
    from flask import jsonify
    data = request.get_json(silent=True) or {}
    ids = catalog.recommend(
        niveau=data.get("niveau", ""),
        frequence=int(data.get("frequence") or 3),
        equipement=data.get("equipement", ""),
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
    niveau = (f.get("niveau") or "").strip()[:20]
    try:
        frequence = max(2, min(6, int(f.get("frequence") or 3)))
    except ValueError:
        frequence = 3
    objectif = (f.get("objectif") or "").strip()[:30]
    equipement = (f.get("equipement") or "").strip()[:30]
    programme_id = (f.get("programme_id") or "").strip()

    # 1. Sauvegarde onboarding + prenom côté profile
    save_onboarding({
        "prenom": prenom,
        "age": age,
        "sexe": sexe,
        "niveau": niveau,
        "frequence": frequence,
        "objectif": objectif,
        "equipement": equipement,
    })
    save_profile({"prenom": prenom})

    # 2. Si l'user a choisi un programme du catalogue, on le clone.
    #    S'il a choisi "custom" (créer mon propre) → on ne touche pas à programs,
    #    il ira sur /programme pour construire le sien.
    if programme_id and programme_id != "custom" and catalog.get_program(programme_id):
        prog = catalog.build_program(programme_id, frequence)
        save_prog(prog)

    session["onboarded"] = True
    return redirect(url_for("accueil.index"))
