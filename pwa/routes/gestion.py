"""Blueprint gestion — paramètres + opérations avancées (danger).

Le planning et le CRUD du programme sont déjà gérés dans /programme.
Cette page regroupe : paramètres d'affichage, auto-assignation des muscles,
reset soft, reset total, vider l'archive.
"""
import json
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, Response

from core.data import get_hist, get_prog, save_prog, save_hist, get_profile, get_onboarding
from core.limiter import limiter
from core.muscu import auto_muscles

bp = Blueprint("gestion", __name__)

DEFAULT_SETTINGS = {
    "auto_collapse": True,
    "show_1rm": True,
    "theme_animations": True,
    "auto_rest_timer": True,
    "auto_prefill_weight": True,
    "show_previous_weeks": 2,
    "notifications": False,
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
        active="plus",
        settings=settings,
        nb_seances=nb_seances,
        nb_exos=nb_exos,
        nb_hist=nb_hist,
        nb_archive=nb_archive,
    )


@bp.route("/gestion/redo-onboarding", methods=["POST"])
def redo_onboarding():
    """Force l'user à refaire l'onboarding (sans rien effacer)."""
    session.pop("onboarded", None)
    return redirect(url_for("onboarding.index"))


@bp.route("/gestion/settings", methods=["POST"])
def update_settings():
    prog = get_prog()
    s = _get_settings(prog)
    s["auto_collapse"] = request.form.get("auto_collapse") == "on"
    s["show_1rm"] = request.form.get("show_1rm") == "on"
    s["theme_animations"] = request.form.get("theme_animations") == "on"
    s["auto_rest_timer"] = request.form.get("auto_rest_timer") == "on"
    s["auto_prefill_weight"] = request.form.get("auto_prefill_weight") == "on"
    s["notifications"] = request.form.get("notifications") == "on"
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
@limiter.limit("3 per minute")
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


@bp.route("/gestion/reset-total", methods=["POST"])
@limiter.limit("3 per minute")
def reset_total():
    if request.form.get("confirm") != "yes":
        return redirect(url_for("gestion.gestion"))
    prog = get_prog()
    prog.pop("_archive", None)
    prog.pop("_legacy_volume", None)
    prog.pop("_extras", None)
    prog.pop("_libre_draft", None)
    save_prog(prog)
    save_hist([])
    return redirect(url_for("gestion.gestion") + "?reset=total")


@bp.route("/gestion/export")
def export_data():
    """Exporte toutes les données utilisateur en JSON."""
    prog = get_prog()
    hist = get_hist()
    profile = get_profile() or {}
    onboarding = get_onboarding() or {}
    payload = {
        "version": 1,
        "exported_at": date.today().isoformat(),
        "programme": prog,
        "historique": hist,
        "profil": {k: v for k, v in profile.items() if k != "id"},
        "onboarding": {k: v for k, v in onboarding.items() if k not in ("user_id", "id")},
    }
    filename = f"muscu-tracker-backup-{date.today().isoformat()}.json"
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/gestion/import", methods=["POST"])
@limiter.limit("5 per minute")
def import_data():
    """Importe des données depuis un fichier JSON."""
    f = request.files.get("file")
    if not f:
        return redirect(url_for("gestion.gestion") + "?import=error")
    try:
        data = json.loads(f.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return redirect(url_for("gestion.gestion") + "?import=error")

    if "programme" in data:
        save_prog(data["programme"])
    if "historique" in data:
        save_hist(data["historique"])

    return redirect(url_for("gestion.gestion") + "?import=ok")


