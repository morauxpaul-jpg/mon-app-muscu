"""Ce qu'un exercice garde d'une séance à l'autre.

Le repos choisi dans la barre du chrono (1:00, 1:30, 2:00, 3:00) ne valait
que pour le repos en cours : le suivant repartait à la valeur du programme
(retour du 14/10, « le chrono n'enregistre pas si je le change »). Il est
désormais écrit dans le programme, pour cet exercice seulement : un appui un
jour de fatigue ne change pas les autres (audit du 30/09, R12).

Les réglages de la machine (même retour) : une ligne libre par exercice et
équipement, sur la carte (core/memoire_exo.py).
"""
import logging

from flask import Blueprint, jsonify, request

from core.data import get_prog, save_prog
from core.dates import logical_today_paris_str
from core.limiter import limiter
from core.memoire_exo import cle_reglages, noter_reglages
from core.passes_seance import seance_de_base

logger = logging.getLogger(__name__)

bp = Blueprint("seance_exo", __name__)

REPOS_MIN, REPOS_MAX = 30, 300     # mêmes bornes que l'éditeur (programme_entrees)


def _exercice_du_programme(prog, seance, exo_id, base):
    """L'entrée du programme : par identifiant stable d'abord (il survit aux
    renommages), sinon par nom. None si l'exercice n'y est pas (ajouté pour
    aujourd'hui, séance libre)."""
    exos = prog.get(seance_de_base(seance, prog))    # « Push 1 · 2 » : Push 1
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


@bp.route("/seance/reglages", methods=["POST"])
@limiter.limit("30 per minute")
def noter_reglages_machine():
    """JSON depuis la carte ; formulaire quand la file hors-ligne le rejoue
    (une salle en sous-sol est le cas normal)."""
    data = request.get_json(silent=True) or request.form
    base = str(data.get("base") or "").strip()
    if not base:
        return jsonify({"ok": False, "error": "exercice manquant"}), 400
    cle = cle_reglages(str(data.get("exo_id") or ""), base, str(data.get("variant") or "Standard"))
    prog = get_prog()
    texte = noter_reglages(prog, cle, data.get("texte"), logical_today_paris_str())
    save_prog(prog)
    return jsonify({"ok": True, "texte": texte})
