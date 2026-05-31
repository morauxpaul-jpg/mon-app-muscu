"""Blueprint gestion — paramètres + opérations avancées (danger).

Le planning et le CRUD du programme sont déjà gérés dans /programme.
Cette page regroupe : paramètres d'affichage, auto-assignation des muscles,
reset soft, reset total, vider l'archive.
"""
import json
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, Response, g

from core.data import get_hist, get_prog, save_prog, save_hist, get_profile, get_onboarding
from core.muscu import auto_muscles, get_base_name
from core.limiter import limiter

MUSCLE_LIST = ["Pecs", "Dos", "Trapèzes", "Épaules", "Biceps", "Triceps", "Avant-bras", "Abdos",
               "Quadriceps", "Ischio-jambiers", "Fessiers", "Adducteurs", "Abducteurs", "Mollets", "Autre"]
PROFIL_OPTIONS = ["Maison", "Salle", "Les deux"]
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

    # Applique les limites Free côté affichage : historique capé à 2 semaines,
    # options premium forcées à off si affichage pour un non-VIP.
    if not getattr(g, "is_vip", False):
        settings["show_previous_weeks"] = min(settings.get("show_previous_weeks", 2), 2)

    nb_seances = len([k for k in prog if not k.startswith("_")])
    nb_exos = sum(len(prog[k]) for k in prog if not k.startswith("_"))
    nb_hist = len(hist)
    nb_archive = len(prog.get("_archive", []))
    custom_exercises = prog.get("_custom_exercises", [])

    # Noms d'exercices distincts présents dans l'historique (hors marqueurs
    # SESSION / cardio), avec le nombre de séries enregistrées pour chacun.
    # Sert à l'outil « Renommer un exercice dans l'historique ».
    exo_counts = {}
    for r in hist:
        ex = (r.get("Exercice") or "").strip()
        if not ex or ex == "SESSION" or ex.startswith("CARDIO:"):
            continue
        exo_counts[ex] = exo_counts.get(ex, 0) + 1
    hist_exercises = [
        {"name": name, "count": cnt}
        for name, cnt in sorted(exo_counts.items(), key=lambda kv: kv[0].lower())
    ]

    return render_template(
        "gestion.html",
        active="plus",
        settings=settings,
        nb_seances=nb_seances,
        nb_exos=nb_exos,
        nb_hist=nb_hist,
        nb_archive=nb_archive,
        custom_exercises=custom_exercises,
        hist_exercises=hist_exercises,
        muscle_list=MUSCLE_LIST,
        profil_options=PROFIL_OPTIONS,
    )


@bp.route("/gestion/redo-onboarding", methods=["POST"])
def redo_onboarding():
    """Force l'user à refaire l'onboarding (sans rien effacer)."""
    session.pop("onboarded", None)
    return redirect(url_for("onboarding.index"))


@bp.route("/gestion/exercice/ajouter", methods=["POST"])
@limiter.limit("20 per minute")
def add_custom_exercise():
    name = (request.form.get("name") or "").strip()
    if not name:
        return redirect(url_for("gestion.gestion"))
    muscle = (request.form.get("muscle") or "").strip()
    if not muscle:
        muscle = auto_muscles(name) or "Autre"
    profil = request.form.get("profil") or "Les deux"
    if profil not in PROFIL_OPTIONS:
        profil = "Les deux"
    prog = get_prog()
    customs = prog.setdefault("_custom_exercises", [])
    if any(e["name"].lower() == name.lower() for e in customs):
        return redirect(url_for("gestion.gestion") + "?exo=duplicate")
    customs.append({"name": name, "muscle": muscle, "profil": profil})
    save_prog(prog)
    return redirect(url_for("gestion.gestion") + "?exo=ok")


@bp.route("/gestion/exercice/supprimer", methods=["POST"])
@limiter.limit("20 per minute")
def delete_custom_exercise():
    idx = request.form.get("index")
    if idx is None:
        return redirect(url_for("gestion.gestion"))
    try:
        idx = int(idx)
    except (ValueError, TypeError):
        return redirect(url_for("gestion.gestion"))
    prog = get_prog()
    customs = prog.get("_custom_exercises", [])
    if 0 <= idx < len(customs):
        customs.pop(idx)
        prog["_custom_exercises"] = customs
        save_prog(prog)
    return redirect(url_for("gestion.gestion") + "?exo=deleted")


@bp.route("/gestion/exercice/renommer", methods=["POST"])
@limiter.limit("10 per minute")
def rename_exercise_history():
    """Renomme un exercice dans TOUT l'historique (match exact sur le nom).

    Usage typique : j'ai loggé « Développé incliné (Barre) » alors que je
    faisais en réalité du décliné — je renomme rétroactivement toutes ces
    séries en « Développé décliné (Barre) ». Le match étant exact, les autres
    variantes (ex. « Développé incliné » standard / haltères) restent intactes.
    """
    old = (request.form.get("old_name") or "").strip()
    new = (request.form.get("new_name") or "").strip()
    if not old or not new or old == new:
        return redirect(url_for("gestion.gestion") + "?rename=noop")

    hist = get_hist()
    new_muscle = auto_muscles(get_base_name(new))
    count = 0
    for r in hist:
        if (r.get("Exercice") or "").strip() == old:
            r["Exercice"] = new
            # Recalcule le muscle d'après le nouveau nom (sinon on garde l'ancien).
            if new_muscle:
                r["Muscle"] = new_muscle
            count += 1

    if count:
        save_hist(hist)
        return redirect(url_for("gestion.gestion") + f"?rename=ok&n={count}")
    return redirect(url_for("gestion.gestion") + "?rename=none")


@bp.route("/gestion/settings", methods=["POST"])
def update_settings():
    prog = get_prog()
    s = _get_settings(prog)
    is_vip = bool(getattr(g, "is_vip", False))
    s["auto_collapse"] = request.form.get("auto_collapse") == "on"
    s["show_1rm"] = request.form.get("show_1rm") == "on"
    s["auto_rest_timer"] = request.form.get("auto_rest_timer") == "on"
    # Options VIP : en Free on force à off quoi qu'il arrive.
    if is_vip:
        s["theme_animations"] = request.form.get("theme_animations") == "on"
        s["auto_prefill_weight"] = request.form.get("auto_prefill_weight") == "on"
        s["notifications"] = request.form.get("notifications") == "on"
    else:
        s["theme_animations"] = False
        s["auto_prefill_weight"] = False
        s["notifications"] = False
    try:
        weeks = int(request.form.get("show_previous_weeks", 2))
    except (ValueError, TypeError):
        weeks = 2
    max_weeks = 10 if is_vip else 2
    s["show_previous_weeks"] = max(0, min(max_weeks, weeks))
    prog["_settings"] = s
    save_prog(prog)
    return redirect(url_for("gestion.gestion"))


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
    """Exporte toutes les données utilisateur en JSON (VIP uniquement)."""
    if not getattr(g, "is_vip", False):
        return render_template("vip_wall.html", active="plus", feature="Export complet"), 403
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
    """Importe des données depuis un fichier JSON (VIP uniquement)."""
    if not getattr(g, "is_vip", False):
        return render_template("vip_wall.html", active="plus", feature="Import complet"), 403
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


