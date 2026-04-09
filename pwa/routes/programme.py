"""Blueprint programme — planning hebdo + édition des séances/exos.

Inclut aussi (depuis Phase 4+) : export/import de séances en JSON,
réinitialisation d'une séance prédéfinie, et changement de programme
(catalogue) — déplacé depuis Gestion."""
import io
import json
import re

from flask import (
    Blueprint, render_template, request, redirect, url_for, send_file
)

from core.data import get_prog, save_prog
from core.dates import DAYS_FR
from core.muscu import auto_muscles
from core import catalog

bp = Blueprint("programme", __name__)

MUSCLE_LIST = ["Pecs", "Dos", "Épaules", "Biceps", "Triceps", "Avant-bras", "Abdos",
               "Quadriceps", "Ischio-jambiers", "Fessiers", "Mollets", "Autre"]

EXPORT_FORMAT = "muscutracker_seance_v1"


def _ensure_planning(prog):
    planning = prog.setdefault("_planning", {})
    for d in DAYS_FR:
        planning.setdefault(d, "")
    return planning


def _seance_items(prog):
    """Liste ordonnée des séances du programme (exclut les clés techniques _*)."""
    return [(k, v) for k, v in prog.items() if not k.startswith("_")]


def _origin_seance_names(prog):
    """Retourne le set des noms de séances qui correspondent à une séance
    d'origine du catalogue (utilisé pour afficher le bouton 'Réinitialiser')."""
    origin = prog.get("_origin")
    if not origin:
        return set()
    src = catalog.get_program(origin)
    if not src:
        return set()
    return set(src["seances"].keys())


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_") or "Seance"
    return f"{cleaned}_MuscuTracker.json"


def _unique_seance_name(prog, base: str) -> str:
    if base not in prog:
        return base
    i = 2
    while f"{base} ({i})" in prog:
        i += 1
    return f"{base} ({i})"


@bp.route("/programme")
def programme():
    prog = get_prog()
    _ensure_planning(prog)
    seances = _seance_items(prog)

    current_origin = prog.get("_origin")
    current_program_meta = None
    if current_origin:
        p = catalog.get_program(current_origin)
        if p:
            current_program_meta = {
                "id": p["id"], "title": p["title"], "subtitle": p["subtitle"],
            }

    return render_template(
        "programme.html",
        active="programme",
        seances=seances,
        planning=prog["_planning"],
        days_fr=DAYS_FR,
        muscle_list=MUSCLE_LIST,
        seance_names=[s for s, _ in seances],
        origin_seance_names=_origin_seance_names(prog),
        catalog_programs=catalog.list_programs(),
        current_program_meta=current_program_meta,
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


@bp.route("/programme/seance/reset", methods=["POST"])
def reset_seance():
    """Restaure une séance prédéfinie depuis le catalogue d'origine."""
    name = request.form["name"]
    prog = get_prog()
    origin = prog.get("_origin")
    if not origin:
        return redirect(url_for("programme.programme"))
    src = catalog.get_program(origin)
    if not src or name not in src["seances"]:
        return redirect(url_for("programme.programme"))
    prog[name] = [
        {"name": e["name"], "sets": int(e["sets"]), "muscle": e["muscle"]}
        for e in src["seances"][name]
    ]
    save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{name}")


# ── Export / Import de séances ────────────────────────────────────
@bp.route("/programme/seance/export/<name>", methods=["GET"])
def export_seance(name):
    prog = get_prog()
    if name not in prog or name.startswith("_"):
        return redirect(url_for("programme.programme"))
    payload = {
        "_format": EXPORT_FORMAT,
        "name": name,
        "exos": [
            {"name": e.get("name", ""), "sets": int(e.get("sets") or 3),
             "muscle": e.get("muscle") or "Autre"}
            for e in prog[name]
        ],
    }
    buf = io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    return send_file(
        buf,
        mimetype="application/json",
        as_attachment=True,
        download_name=_safe_filename(name),
    )


@bp.route("/programme/seance/import", methods=["POST"])
def import_seance():
    file = request.files.get("file")
    if not file or not file.filename:
        return redirect(url_for("programme.programme"))
    try:
        data = json.loads(file.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return redirect(url_for("programme.programme") + "?import_err=parse")

    if not isinstance(data, dict) or data.get("_format") != EXPORT_FORMAT:
        return redirect(url_for("programme.programme") + "?import_err=format")

    raw_exos = data.get("exos") or []
    if not isinstance(raw_exos, list):
        return redirect(url_for("programme.programme") + "?import_err=format")

    # Nom : champ form prioritaire (modifiable côté UI), sinon nom du fichier
    name = (request.form.get("name") or data.get("name") or "Séance importée").strip()
    if not name:
        name = "Séance importée"

    mode = (request.form.get("mode") or "").strip()  # "overwrite" | "rename" | ""
    prog = get_prog()

    if name in prog and not name.startswith("_"):
        if mode == "overwrite":
            pass
        elif mode == "rename":
            name = _unique_seance_name(prog, name)
        else:
            # Conflit non résolu — on rename par défaut + flag URL pour info
            name = _unique_seance_name(prog, name)

    cleaned = []
    for e in raw_exos:
        if not isinstance(e, dict):
            continue
        ex_name = (e.get("name") or "").strip()
        if not ex_name:
            continue
        try:
            sets = int(e.get("sets") or 3)
        except (TypeError, ValueError):
            sets = 3
        muscle = (e.get("muscle") or "Autre").strip() or "Autre"
        cleaned.append({"name": ex_name, "sets": sets, "muscle": muscle})

    prog[name] = cleaned
    save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{name}")


# ── Changer de programme (catalogue) ──────────────────────────────
@bp.route("/programme/change-program", methods=["POST"])
def change_program():
    """Remplace le programme courant par un autre du catalogue (ou vide
    pour 'créer mon propre'). Conserve historique + settings + archive."""
    prog_id = (request.form.get("programme_id") or "").strip()
    if request.form.get("confirm") != "yes":
        return redirect(url_for("programme.programme"))

    if prog_id == "custom":
        prog = get_prog()
        for k in list(prog.keys()):
            if not k.startswith("_"):
                prog.pop(k)
        prog.pop("_origin", None)
        save_prog(prog)
        return redirect(url_for("programme.programme") + "?program_changed=1")

    src = catalog.get_program(prog_id)
    if not src:
        return redirect(url_for("programme.programme"))

    old = get_prog()
    new_prog = catalog.build_program(prog_id, src["freq"])
    for key in ("_settings", "_archive", "_legacy_volume", "_extras"):
        if key in old:
            new_prog[key] = old[key]
    save_prog(new_prog)
    return redirect(url_for("programme.programme") + "?program_changed=1")


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
