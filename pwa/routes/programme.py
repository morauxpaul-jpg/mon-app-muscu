"""Blueprint programme — planning hebdo + édition des séances/exos."""
from flask import Blueprint, render_template, request, redirect, url_for

from core.data import get_prog, save_prog
from core.dates import DAYS_FR
from core.muscu import auto_muscles

bp = Blueprint("programme", __name__)

MUSCLE_LIST = ["Pecs", "Dos", "Épaules", "Biceps", "Triceps", "Avant-bras", "Abdos",
               "Quadriceps", "Ischio-jambiers", "Fessiers", "Mollets", "Autre"]


def _ensure_planning(prog):
    planning = prog.setdefault("_planning", {})
    for d in DAYS_FR:
        planning.setdefault(d, "")
    return planning


def _seance_items(prog):
    """Liste ordonnée des séances du programme (exclut les clés techniques _*)."""
    return [(k, v) for k, v in prog.items() if not k.startswith("_")]


@bp.route("/programme")
def programme():
    prog = get_prog()
    _ensure_planning(prog)
    seances = _seance_items(prog)
    return render_template(
        "programme.html",
        active="programme",
        seances=seances,
        planning=prog["_planning"],
        days_fr=DAYS_FR,
        muscle_list=MUSCLE_LIST,
        seance_names=[s for s, _ in seances],
    )


# ── Planning ─────────────────────────────────────────────────────
@bp.route("/programme/planning", methods=["POST"])
def save_planning():
    prog = get_prog()
    planning = _ensure_planning(prog)
    for day in DAYS_FR:
        val = request.form.get(f"plan_{day}", "")
        planning[day] = "" if val == "__rest__" else val
    save_prog(prog)
    return redirect(url_for("programme.programme") + "#planning")


# ── Séances ──────────────────────────────────────────────────────
@bp.route("/programme/seance/new", methods=["POST"])
def new_seance():
    name = (request.form.get("name") or "").strip()
    if not name:
        return redirect(url_for("programme.programme"))
    prog = get_prog()
    if name not in prog:
        prog[name] = []
    save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{name}")


@bp.route("/programme/seance/delete", methods=["POST"])
def delete_seance():
    name = request.form["name"]
    prog = get_prog()
    if name in prog and not name.startswith("_"):
        prog.pop(name)
    save_prog(prog)
    return redirect(url_for("programme.programme"))


@bp.route("/programme/seance/move", methods=["POST"])
def move_seance():
    """Monte une séance (direction=up) dans l'ordre du dict programme."""
    name = request.form["name"]
    direction = request.form.get("direction", "up")
    prog = get_prog()
    seances = [k for k in prog.keys() if not k.startswith("_")]
    technical = {k: v for k, v in prog.items() if k.startswith("_")}
    if name not in seances:
        return redirect(url_for("programme.programme"))
    i = seances.index(name)
    j = i - 1 if direction == "up" else i + 1
    if 0 <= j < len(seances):
        seances[i], seances[j] = seances[j], seances[i]
    new_prog = {k: prog[k] for k in seances}
    new_prog.update(technical)
    save_prog(new_prog)
    return redirect(url_for("programme.programme") + f"#s-{name}")


# ── Exercices ────────────────────────────────────────────────────
@bp.route("/programme/exo/add", methods=["POST"])
def add_exo():
    f = request.form
    seance = f["seance"]
    name = (f.get("name") or "").strip()
    if not name:
        return redirect(url_for("programme.programme") + f"#s-{seance}")
    try:
        sets = int(f.get("sets") or 3)
    except ValueError:
        sets = 3
    muscles = f.getlist("muscles")
    muscle = ",".join(muscles) if muscles else (auto_muscles(name) or "Autre")
    prog = get_prog()
    if seance in prog:
        prog[seance].append({"name": name, "sets": sets, "muscle": muscle})
        save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{seance}")


@bp.route("/programme/exo/update", methods=["POST"])
def update_exo():
    f = request.form
    seance = f["seance"]
    idx = int(f["index"])
    prog = get_prog()
    if seance not in prog or idx >= len(prog[seance]):
        return redirect(url_for("programme.programme"))
    ex = prog[seance][idx]
    try:
        ex["sets"] = int(f.get("sets") or ex.get("sets", 3))
    except ValueError:
        pass
    muscles = f.getlist("muscles")
    if muscles:
        ex["muscle"] = ",".join(muscles)
    save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{seance}")


@bp.route("/programme/exo/delete", methods=["POST"])
def delete_exo():
    f = request.form
    seance = f["seance"]
    idx = int(f["index"])
    prog = get_prog()
    if seance in prog and 0 <= idx < len(prog[seance]):
        prog[seance].pop(idx)
        save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{seance}")


@bp.route("/programme/exo/move", methods=["POST"])
def move_exo():
    f = request.form
    seance = f["seance"]
    idx = int(f["index"])
    direction = f.get("direction", "up")
    prog = get_prog()
    if seance not in prog:
        return redirect(url_for("programme.programme"))
    lst = prog[seance]
    j = idx - 1 if direction == "up" else idx + 1
    if 0 <= j < len(lst):
        lst[idx], lst[j] = lst[j], lst[idx]
        save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{seance}")
