"""Ce qu'un exercice garde d'une séance à l'autre.

Le repos choisi dans la barre du chrono (1:00, 1:30, 2:00, 3:00) ne valait
que pour le repos en cours : le suivant repartait à la valeur du programme
(retour du 14/10, « le chrono n'enregistre pas si je le change »). Il est
désormais écrit dans le programme, pour cet exercice seulement : un appui un
jour de fatigue ne change pas les autres (audit du 30/09, R12).
"""
import logging

from flask import Blueprint, jsonify, request

from core.data import get_prog, save_prog
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("seance_exo", __name__)

REPOS_MIN, REPOS_MAX = 30, 300     # mêmes bornes que l'éditeur (programme_entrees)


def _exercice_du_programme(prog, seance, exo_id, base):
    """L'entrée du programme : par identifiant stable d'abord (il survit aux
    renommages), sinon par nom. None si l'exercice n'y est pas (ajouté pour
    aujourd'hui, séance libre)."""
    exos = prog.get(seance)
    if not isinstance(exos, list):
        return None
    if exo_id:
        for ex in exos:
            if isinstance(ex, dict) and ex.get("id") == exo_id:
                return ex
    for ex in exos:
        if isinstance(ex, dict) and ex.get("name") == base:
            return ex
    return None


@bp.route("/seance/repos", methods=["POST"])
@limiter.limit("30 per minute")
def retenir_repos():
    data = request.get_json(silent=True) or {}
    seance = str(data.get("seance") or "")
    exo_id = str(data.get("exo_id") or "")
    base = str(data.get("base") or "")
    try:
        sec = int(data.get("rest_seconds"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "durée illisible"}), 400
    sec = max(REPOS_MIN, min(REPOS_MAX, sec))
    prog = get_prog()
    ex = _exercice_du_programme(prog, seance, exo_id, base)
    if ex is None:
        # Le navigateur le garde alors pour lui (seance.js, repos_par_exo).
        return jsonify({"ok": False, "error": "exercice absent du programme"}), 404
    if ex.get("rest_seconds") != sec:
        ex["rest_seconds"] = sec
        save_prog(prog)
    return jsonify({"ok": True, "rest_seconds": sec})
