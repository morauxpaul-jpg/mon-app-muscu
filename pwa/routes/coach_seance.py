"""Le coach crée une séance : reprise après une pause, courte, légère, ou
une demande libre (02/11, demande du propriétaire).

Choix du propriétaire : ouvert comme le coach (PRO et essai PRO) ; la
séance entre dans le programme, hors planning ; une reprise allège les
charges selon la durée de la pause. L'IA choisit les exercices, jamais les
charges : core/coach_seance.py les calcule depuis l'historique, ici en
aperçu puis de nouveau à l'ajout (rien de ce que renvoie le navigateur
n'est cru).

    GET  /coach/seance              la page
    POST /coach/seance              lance la création (tâche de fond, core/taches_ia.py)
    GET  /coach/seance/tache/<id>   où en est-elle
    POST /coach/seance/ajouter      la proposition entre dans le programme
"""
import logging

from flask import Blueprint, current_app, g, jsonify, render_template, request, url_for

from core import coach_seance as calc
from core import db as core_db
from core import ia, taches_ia
from core.analytics import compter, paywall, track
from core.data import get_hist, get_prog, save_prog
from core.dates import logical_today_paris
from core.db import _env
from core.limiter import limiter
from core.programme_entrees import MAX_SEANCES, _exo_entry

logger = logging.getLogger(__name__)

bp = Blueprint("coach_seance", __name__)

QUOTA_JOUR = 5            # séances créées par jour et par compte
MAX_TOKENS = 4000         # une séance, réflexion comprise (core/ia.py)
TIMEOUT_IA = 90
EVENEMENT = "coach_seance_creee"


def _ouvert() -> bool:
    """Comme le coach : PRO, ou essai PRO en cours."""
    return bool(getattr(g, "is_vip_full", False) or getattr(g, "is_vip", False))


def _params(f: dict) -> dict:
    type_ = f.get("type") if f.get("type") in calc.TYPES else "reprise"
    try:
        duree = int(f.get("duree") or 45)
    except (TypeError, ValueError):
        duree = 45
    return {"type": type_, "duree": duree if duree in calc.DUREES else 45,
            "demande": " ".join(str(f.get("demande") or "").split())[:300]}


def _apercu(proposition: dict, hist, type_: str, aujourdhui) -> dict:
    """La proposition, les conseils de charge recalculés et la pause."""
    jours = calc.jours_de_pause(hist, aujourdhui)
    f = calc.facteur(type_, jours)
    conseils = calc.conseils(proposition["exercices"], hist, type_, f, aujourdhui)
    return {"proposition": proposition, "pause": jours, "facteur": f, "conseils": conseils,
            "lignes": [{"nom": calc.nom_complet(e), "series": e["sets"], "reps": e["reps"],
                        "conseil": (conseils.get(e["name"]) or {}).get("libelle", "")}
                       for e in proposition["exercices"]]}


def _appeler_ia(prompt: str):
    """(texte, None) ou (None, (corps d'erreur, code)). Hors requête."""
    indispo = ({"error": "Le coach est momentanément indisponible. Réessaie plus tard."}, 503)
    api_key = _env("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("clé IA absente : séance du coach indisponible")
        return None, indispo
    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_IA)
        reponse = client.messages.create(**ia.options("medium"), max_tokens=MAX_TOKENS,
                                         messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        logger.error("/coach/seance anthropic FAILED (%s): %s", type(e).__name__, str(e)[:300])
        return None, indispo
    textes = ia.textes("coach-seance", reponse)
    if textes is None:
        return None, ({"error": "Cette demande n'a pas pu être traitée. Reformule-la : "
                                "ton quota n'a pas été entamé."}, 422)
    return "\n".join(textes).strip(), None


@bp.route("/coach/seance")
def page():
    if not _ouvert():
        return paywall("Séance créée par le coach")
    aujourdhui = logical_today_paris()
    jours = calc.jours_de_pause(get_hist(), aujourdhui)
    return render_template(
        "coach_seance.html", active="plus", types=calc.TYPES, durees=calc.DUREES, pause=jours,
        baisse=round((1 - calc.facteur("reprise", jours)) * 100),
        restantes=max(0, QUOTA_JOUR - compter(g.user_id, EVENEMENT, 1)), quota=QUOTA_JOUR)


@bp.route("/coach/seance", methods=["POST"])
@limiter.limit("10 per hour")
def creer():
    if not _ouvert():
        return jsonify({"error": "Réservé aux membres PRO."}), 403
    params = _params(request.get_json(silent=True) or {})
    user_id = g.user_id
    from core.quota import liberer, reserver
    if not reserver("coach-seance", user_id, lambda: compter(user_id, EVENEMENT, 1), QUOTA_JOUR):
        return jsonify({"error": f"Limite atteinte : {QUOTA_JOUR} séances créées par jour."}), 429

    def travail():
        try:
            aujourdhui = logical_today_paris()
            hist = core_db.get_hist(user_id)
            prompt = calc.consigne_ia(params["type"], params["duree"], params["demande"],
                                      calc.exercices_habituels(hist, aujourdhui),
                                      calc.jours_de_pause(hist, aujourdhui),
                                      core_db.get_profile(user_id) or {})
            raw, erreur = _appeler_ia(prompt)
            if erreur:
                return erreur
            try:
                proposition = calc.lire_reponse(raw)
            except ValueError as e:
                logger.error("/coach/seance réponse illisible (%s) : %s", e, (raw or "")[:200])
                return {"error": "Le coach a renvoyé une séance illisible. Réessaie."}, 502
            track(EVENEMENT, {"type": params["type"], "exos": len(proposition["exercices"])},
                  user_id=user_id, tier="vip")
            apercu = _apercu(proposition, hist, params["type"], aujourdhui)
            return {"ok": True, "type": params["type"], **{k: apercu[k] for k in
                    ("proposition", "lignes", "pause", "facteur")}}, 200
        finally:
            liberer("coach-seance", user_id)

    try:
        tid = taches_ia.lancer(user_id, "coach-seance", travail, current_app._get_current_object())
    except Exception:
        liberer("coach-seance", user_id)
        raise
    corps, code = taches_ia.reponse(tid, user_id)
    return jsonify(corps), code


@bp.route("/coach/seance/tache/<tid>")
@limiter.limit("120 per minute")
def tache(tid):
    if not _ouvert():
        return jsonify({"error": "Réservé aux membres PRO."}), 403
    etat = taches_ia.lire(str(tid)[:64], g.user_id)
    if etat is None:
        return jsonify({"error": "Création introuvable (le serveur a peut-être redémarré). "
                                 "Relance-la : ton quota n'a pas été entamé."}), 404
    corps, code = etat
    return jsonify(corps), code


@bp.route("/coach/seance/ajouter", methods=["POST"])
@limiter.limit("20 per hour")
def ajouter():
    """La séance entre dans le programme (hors planning), avec les conseils
    de charge recalculés ici, depuis l'historique."""
    if not _ouvert():
        return jsonify({"error": "Réservé aux membres PRO."}), 403
    f = request.get_json(silent=True) or {}
    type_ = f.get("type") if f.get("type") in calc.TYPES else "libre"
    try:
        proposition = calc.lire_reponse(f.get("proposition"))
    except ValueError:
        return jsonify({"error": "Séance illisible. Recrée-la."}), 400
    prog = get_prog()
    seances = [k for k in prog if not str(k).startswith("_")]
    if len(seances) >= MAX_SEANCES:
        return jsonify({"error": f"Ton programme a déjà {MAX_SEANCES} séances."}), 400
    nom = calc.nom_libre(proposition["nom"], seances)
    aujourdhui = logical_today_paris()
    apercu = _apercu(proposition, get_hist(), type_, aujourdhui)
    prog[nom] = [_exo_entry(e["name"], e["sets"], e["muscle"], e) for e in proposition["exercices"]]
    fiches = {k: v for k, v in (prog.get(calc.CLE_PROGRAMME) or {}).items() if k in prog}
    fiches[nom] = {"type": type_, "facteur": apercu["facteur"], "pause_jours": apercu["pause"],
                   "cree_le": aujourdhui.isoformat(), "conseils": apercu["conseils"]}
    prog[calc.CLE_PROGRAMME] = fiches
    save_prog(prog)
    track("coach_seance_ajoutee", {"type": type_, "exos": len(prog[nom])})
    return jsonify({"ok": True, "nom": nom,
                    "lien": url_for("seance.seance", mode="prefaite", name=nom)})
