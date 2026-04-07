"""Blueprint gestion — paramètres + opérations avancées (danger).

Le planning et le CRUD du programme sont déjà gérés dans /programme.
Cette page regroupe : paramètres d'affichage, auto-assignation des muscles,
reset soft, reset total, vider l'archive.
"""
from flask import Blueprint, render_template, request, redirect, url_for

from core.sheets import get_hist, get_prog, save_prog, save_hist
from core.muscu import auto_muscles

bp = Blueprint("gestion", __name__)

DEFAULT_SETTINGS = {
    "auto_collapse": True,
    "show_1rm": True,
    "theme_animations": True,
    "show_previous_weeks": 2,
}


def _get_settings(prog):
    s = dict(DEFAULT_SETTINGS)
    s.update(prog.get("_settings", {}) or {})
    return s


@bp.route("/gestion")
def gestion():
    prog = get_prog()
    hist = get_hist()
    settings = _get_settings(prog)

    nb_seances = len([k for k in prog if not k.startswith("_")])
    nb_exos = sum(len(prog[k]) for k in prog if not k.startswith("_"))
    nb_hist = len(hist)
    nb_archive = len(prog.get("_archive", []))

    return render_template(
        "gestion.html",
        active="gestion",
        settings=settings,
        nb_seances=nb_seances,
        nb_exos=nb_exos,
        nb_hist=nb_hist,
        nb_archive=nb_archive,
    )


@bp.route("/gestion/settings", methods=["POST"])
def update_settings():
    prog = get_prog()
    s = _get_settings(prog)
    s["auto_collapse"] = request.form.get("auto_collapse") == "on"
    s["show_1rm"] = request.form.get("show_1rm") == "on"
    s["theme_animations"] = request.form.get("theme_animations") == "on"
    try:
        s["show_previous_weeks"] = max(0, min(10, int(request.form.get("show_previous_weeks", 2))))
    except (ValueError, TypeError):
        s["show_previous_weeks"] = 2
    prog["_settings"] = s
    save_prog(prog)
    return redirect(url_for("gestion.gestion"))


@bp.route("/gestion/auto-muscles", methods=["POST"])
def auto_assign():
    prog = get_prog()
    updated, skipped = [], []
    for s in [k for k in prog if not k.startswith("_")]:
        for ex in prog[s]:
            new_m = auto_muscles(ex["name"])
            if new_m:
                ex["muscle"] = new_m
                updated.append(f"{ex['name']} → {new_m}")
            else:
                skipped.append(ex["name"])
    save_prog(prog)
    return redirect(url_for("gestion.gestion") + f"?updated={len(updated)}&skipped={len(skipped)}")


@bp.route("/gestion/reset-soft", methods=["POST"])
def reset_soft():
    prog = get_prog()
    hist = get_hist()

    # Volume legacy : sum(Poids * Reps)
    v_tot = 0
    for r in hist:
        try:
            v_tot += int(float(r.get("Poids", 0) or 0) * float(r.get("Reps", 0) or 0))
        except (ValueError, TypeError):
            pass
    prog["_legacy_volume"] = int(prog.get("_legacy_volume", 0) or 0) + v_tot

    # Archive : par (exo, semaine), garde le set au plus gros poids
    by_key = {}
    for r in hist:
        try:
            reps = int(float(r.get("Reps", 0) or 0))
            poids = float(r.get("Poids", 0) or 0)
            sem = int(float(r.get("Semaine", 0) or 0))
        except (ValueError, TypeError):
            continue
        if reps <= 0:
            continue
        key = (r.get("Exercice", ""), sem)
        cur = by_key.get(key)
        if cur is None or poids > cur["Poids"]:
            by_key[key] = {
                "Exercice": r.get("Exercice", ""),
                "Semaine": sem,
                "Poids": poids,
                "Reps": reps,
                "Muscle": r.get("Muscle", ""),
            }
    archive = prog.get("_archive", []) or []
    archive.extend(by_key.values())
    prog["_archive"] = archive[-2000:]

    save_prog(prog)
    save_hist([])
    return redirect(url_for("gestion.gestion") + "?reset=soft")


