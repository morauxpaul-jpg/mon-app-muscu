"""Blueprint programme — planning hebdo + édition des séances/exos.

Inclut aussi (depuis Phase 4+) : export/import de séances en JSON,
réinitialisation d'une séance prédéfinie, et changement de programme
(catalogue) — déplacé depuis Gestion."""
import io
import json
import logging
import re
import uuid

from flask import (
    Blueprint, render_template, request, redirect, url_for, send_file, jsonify, g
)

from core.data import get_prog, save_prog, get_onboarding
from core.dates import DAYS_FR
from core.muscu import auto_muscles
from core import catalog

logger = logging.getLogger(__name__)

bp = Blueprint("programme", __name__)

MUSCLE_LIST = ["Pecs", "Dos", "Trapèzes", "Épaules", "Biceps", "Triceps", "Avant-bras", "Abdos",
               "Quadriceps", "Ischio-jambiers", "Fessiers", "Adducteurs", "Abducteurs", "Mollets", "Autre"]

EXPORT_FORMAT = "muscutracker_program_v1"


def _ensure_planning(prog):
    planning = prog.setdefault("_planning", {})
    for d in DAYS_FR:
        planning.setdefault(d, "")
    return planning


def _gen_prog_id() -> str:
    return "p_" + uuid.uuid4().hex[:8]


def _ensure_programmes(prog):
    """Migre l'ancien schéma (dict plat de séances) vers le nouveau schéma
    multi-programmes : _programmes = liste de {id, name} et _seance_prog = map
    seance_name → prog_id. Les séances non mappées tombent dans "Non classé".
    """
    progs = prog.get("_programmes")
    mapping = prog.get("_seance_prog")
    seance_names = [k for k in prog.keys() if not k.startswith("_")]

    if not isinstance(progs, list):
        progs = []
    if not isinstance(mapping, dict):
        mapping = {}

    if not progs:
        # Premier chargement avec l'ancien schéma : crée un programme par
        # défaut et y assigne toutes les séances existantes.
        default_name = (prog.get("_name") or "").strip()
        origin = prog.get("_origin")
        if not default_name and origin:
            src = catalog.get_program(origin)
            if src:
                default_name = src["title"]
        if not default_name:
            default_name = "Mon programme"
        default_id = _gen_prog_id()
        progs = [{"id": default_id, "name": default_name[:80]}]
        for sname in seance_names:
            mapping[sname] = default_id
    else:
        # Normalise : garde uniquement les entrées valides
        valid_ids = {p.get("id") for p in progs if isinstance(p, dict) and p.get("id")}
        existing = set(seance_names)
        mapping = {s: pid for s, pid in mapping.items() if s in existing and pid in valid_ids}

    prog["_programmes"] = progs
    prog["_seance_prog"] = mapping
    return progs, mapping


def _gen_profile_id() -> str:
    return "pf_" + uuid.uuid4().hex[:8]


def _ensure_profiles(prog):
    """Seed un profil d'entraînement par défaut si absent. Chaque programme
    se voit attribuer un `profile_id` par défaut s'il n'en a pas encore.
    Le profil actif est stocké dans `_active_profile`.
    """
    profiles = prog.get("_profiles")
    if not isinstance(profiles, list) or not profiles:
        default_id = _gen_profile_id()
        profiles = [{"id": default_id, "name": "Par défaut"}]
    # Normalise : garde id+name uniquement
    clean = []
    for p in profiles:
        if isinstance(p, dict) and p.get("id") and p.get("name"):
            clean.append({"id": p["id"], "name": str(p["name"])[:40]})
    if not clean:
        clean = [{"id": _gen_profile_id(), "name": "Par défaut"}]
    profiles = clean

    valid_ids = {p["id"] for p in profiles}
    active = prog.get("_active_profile")
    if active not in valid_ids:
        active = profiles[0]["id"]

    # Attribue un profil à chaque programme si manquant
    for pg in (prog.get("_programmes") or []):
        if isinstance(pg, dict):
            pid = pg.get("profile_id")
            if pid not in valid_ids:
                pg["profile_id"] = active

    prog["_profiles"] = profiles
    prog["_active_profile"] = active
    return profiles, active


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
    cleaned = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_") or "MonProgramme"
    return f"{cleaned}_MuscuTracker.json"


def _program_display_name(prog) -> str:
    """Nom du programme pour l'export. Prend _name si défini, sinon le titre
    du catalogue d'origine, sinon 'MonProgramme'."""
    name = (prog.get("_name") or "").strip()
    if name:
        return name
    origin = prog.get("_origin")
    if origin:
        src = catalog.get_program(origin)
        if src:
            return src["title"]
    return "MonProgramme"


@bp.route("/programme")
def programme():
    try:
        prog = get_prog()
    except Exception as e:
        logger.error("programme() DB failed: %s", e)
        return render_template(
            "error.html", code=503,
            message="Impossible de charger le programme. Vérifie ta connexion.",
        ), 503
    _ensure_planning(prog)
    programmes, seance_prog = _ensure_programmes(prog)
    profiles, active_profile = _ensure_profiles(prog)
    save_prog(prog)  # persiste la migration si c'était la première fois
    seances = _seance_items(prog)

    current_origin = prog.get("_origin")
    current_program_meta = None
    if current_origin:
        p = catalog.get_program(current_origin)
        if p:
            current_program_meta = {
                "id": p["id"], "title": p["title"], "subtitle": p["subtitle"],
            }

    # Payload JSON pour l'app Alpine (édition sans refresh)
    ui_state = {
        "name": _program_display_name(prog),
        "planning": dict(prog["_planning"]),
        "seances": {
            sname: [
                {"name": e.get("name", ""), "sets": int(e.get("sets") or 3),
                 "muscle": e.get("muscle") or "Autre"}
                for e in exos
            ]
            for sname, exos in seances
        },
        "seance_order": [s for s, _ in seances],
        "origin_seance_names": sorted(_origin_seance_names(prog)),
        "origin": prog.get("_origin"),
        "programmes": [{"id": p["id"], "name": p["name"], "profile_id": p.get("profile_id") or active_profile} for p in programmes],
        "seance_prog": dict(seance_prog),
        "profiles": [{"id": p["id"], "name": p["name"]} for p in profiles],
        "active_profile": active_profile,
    }

    return render_template(
        "programme.html",
        active="plus",
        seances=seances,
        planning=prog["_planning"],
        days_fr=DAYS_FR,
        muscle_list=MUSCLE_LIST,
        seance_names=[s for s, _ in seances],
        origin_seance_names=_origin_seance_names(prog),
        catalog_programs=catalog.list_programs(is_vip=bool(getattr(g, "is_vip", False))),
        current_program_meta=current_program_meta,
        ui_state=ui_state,
    )


# ── Sauvegarde groupée (AJAX sans refresh) ───────────────────────
@bp.route("/programme/state", methods=["POST"])
def save_state():
    """Reçoit l'état complet (nom, planning, séances) et le persiste.
    Préserve les clés techniques (_origin, _settings, _archive, _extras, _libre_draft).
    """
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"ok": False, "error": "invalid_json"}), 400
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "invalid_json"}), 400

    new_name = (data.get("name") or "").strip()[:80]
    raw_seances = data.get("seances") or {}
    raw_planning = data.get("planning") or {}
    seance_order = data.get("seance_order") or []

    if not isinstance(raw_seances, dict) or not isinstance(raw_planning, dict):
        return jsonify({"ok": False, "error": "invalid_shape"}), 400

    old = get_prog()

    # Nouveau dict programme : ordre = seance_order puis reste
    ordered_names = [s for s in seance_order if isinstance(s, str) and s in raw_seances and not s.startswith("_")]
    for s in raw_seances:
        if s not in ordered_names and isinstance(s, str) and not s.startswith("_"):
            ordered_names.append(s)

    new_prog: dict = {}
    for sname in ordered_names:
        exos = raw_seances.get(sname, [])
        if not isinstance(exos, list):
            continue
        cleaned = []
        for e in exos:
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
        new_prog[sname] = cleaned

    # Planning nettoyé
    new_prog["_planning"] = {
        d: (raw_planning.get(d, "") if isinstance(raw_planning.get(d, ""), str) else "")
        for d in DAYS_FR
    }
    # Ne garde un planning que pour les séances qui existent encore
    valid_names = set(new_prog.keys()) - {"_planning"}
    for d in DAYS_FR:
        if new_prog["_planning"][d] and new_prog["_planning"][d] not in valid_names:
            new_prog["_planning"][d] = ""

    if new_name:
        new_prog["_name"] = new_name

    # Préserve les données utilisateur qui n'appartiennent pas au programme
    for key in ("_origin", "_settings", "_archive", "_legacy_volume",
                "_extras", "_libre_draft", "_started_at"):
        if key in old:
            new_prog[key] = old[key]

    # _programmes + _seance_prog (multi-programmes)
    raw_progs = data.get("programmes")
    raw_mapping = data.get("seance_prog")
    new_programmes = []
    if isinstance(raw_progs, list):
        for p in raw_progs:
            if not isinstance(p, dict):
                continue
            pid = (p.get("id") or "").strip()
            pname = (p.get("name") or "").strip()[:80]
            if not pid or not pname:
                continue
            entry = {"id": pid, "name": pname}
            prof = p.get("profile_id")
            if isinstance(prof, str) and prof.strip():
                entry["profile_id"] = prof.strip()
            new_programmes.append(entry)
    # Si le client n'en envoie pas, on réutilise l'ancien état
    if not new_programmes:
        new_programmes = old.get("_programmes") or []

    # Limite 2 programmes pour les non-VIP. On tolère l'état existant
    # (ex: un user qui aurait déjà 3 programmes avant d'être passé free)
    # mais on bloque toute création d'un nouveau programme au-delà.
    if not getattr(g, "is_vip", False):
        old_ids = {p.get("id") for p in (old.get("_programmes") or []) if isinstance(p, dict)}
        added = [p for p in new_programmes if p.get("id") not in old_ids]
        if added and len(new_programmes) > max(1, len(old_ids)):
            return jsonify({"ok": False, "error": "vip_required",
                            "message": "1 programme max en gratuit — passe en PRO pour en créer plus."}), 403

    valid_ids = {p["id"] for p in new_programmes}
    new_mapping = {}
    src_mapping = raw_mapping if isinstance(raw_mapping, dict) else (old.get("_seance_prog") or {})
    existing_names = set(new_prog.keys()) - {"_planning", "_name"}
    for sname, pid in src_mapping.items():
        if sname in existing_names and pid in valid_ids:
            new_mapping[sname] = pid
    new_prog["_programmes"] = new_programmes
    new_prog["_seance_prog"] = new_mapping

    # Profils d'entraînement — préserve l'état existant + normalise les profile_id
    if "_profiles" in old:
        new_prog["_profiles"] = old["_profiles"]
    if "_active_profile" in old:
        new_prog["_active_profile"] = old["_active_profile"]
    _ensure_profiles(new_prog)

    save_prog(new_prog)
    return jsonify({"ok": True})


# ── Profils d'entraînement (Maison / Salle / …) ─────────────────
@bp.route("/programme/profile/switch", methods=["POST"])
def switch_profile():
    pid = (request.form.get("profile_id") or "").strip()
    prog = get_prog()
    _ensure_profiles(prog)
    valid = {p["id"] for p in prog.get("_profiles", [])}
    if pid in valid:
        prog["_active_profile"] = pid
        save_prog(prog)
    return jsonify({"ok": True, "active_profile": prog.get("_active_profile")})


@bp.route("/programme/profile/add", methods=["POST"])
def add_profile():
    name = (request.form.get("name") or "").strip()[:40]
    if not name:
        return jsonify({"ok": False, "error": "empty_name"}), 400
    prog = get_prog()
    _ensure_profiles(prog)
    if not getattr(g, "is_vip", False) and len(prog["_profiles"]) >= 1:
        return jsonify({"ok": False, "error": "vip_required",
                        "message": "1 profil max en gratuit — passe en PRO pour en créer plus."}), 403
    if len(prog["_profiles"]) >= 8:
        return jsonify({"ok": False, "error": "too_many"}), 400
    new_id = _gen_profile_id()
    prog["_profiles"].append({"id": new_id, "name": name})
    prog["_active_profile"] = new_id
    save_prog(prog)
    return jsonify({"ok": True, "profile": {"id": new_id, "name": name}})


@bp.route("/programme/profile/rename", methods=["POST"])
def rename_profile():
    pid = (request.form.get("profile_id") or "").strip()
    name = (request.form.get("name") or "").strip()[:40]
    if not pid or not name:
        return jsonify({"ok": False, "error": "invalid"}), 400
    prog = get_prog()
    _ensure_profiles(prog)
    for p in prog["_profiles"]:
        if p["id"] == pid:
            p["name"] = name
            save_prog(prog)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "not_found"}), 404


@bp.route("/programme/profile/delete", methods=["POST"])
def delete_profile():
    pid = (request.form.get("profile_id") or "").strip()
    prog = get_prog()
    _ensure_profiles(prog)
    if len(prog["_profiles"]) <= 1:
        return jsonify({"ok": False, "error": "last_profile"}), 400
    remaining = [p for p in prog["_profiles"] if p["id"] != pid]
    if len(remaining) == len(prog["_profiles"]):
        return jsonify({"ok": False, "error": "not_found"}), 404
    prog["_profiles"] = remaining
    # Les programmes rattachés tombent sur le premier profil restant
    fallback = remaining[0]["id"]
    for pg in prog.get("_programmes") or []:
        if isinstance(pg, dict) and pg.get("profile_id") == pid:
            pg["profile_id"] = fallback
    if prog.get("_active_profile") == pid:
        prog["_active_profile"] = fallback
    save_prog(prog)
    return jsonify({"ok": True, "active_profile": prog["_active_profile"]})


@bp.route("/programme/profile/assign", methods=["POST"])
def assign_programme_profile():
    prog_id = (request.form.get("prog_id") or "").strip()
    profile_id = (request.form.get("profile_id") or "").strip()
    prog = get_prog()
    _ensure_profiles(prog)
    valid = {p["id"] for p in prog["_profiles"]}
    if profile_id not in valid:
        return jsonify({"ok": False, "error": "invalid_profile"}), 400
    for pg in prog.get("_programmes") or []:
        if isinstance(pg, dict) and pg.get("id") == prog_id:
            pg["profile_id"] = profile_id
            save_prog(prog)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "not_found"}), 404


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


# ── Export / Import du PROGRAMME entier ───────────────────────────
@bp.route("/programme/export", methods=["GET"])
def export_program():
    if not getattr(g, "is_vip", False):
        return render_template("vip_wall.html", active="plus", feature="Export de programme"), 403
    prog = get_prog()
    seances = {}
    for sname, exos in _seance_items(prog):
        seances[sname] = [
            {"name": e.get("name", ""), "sets": int(e.get("sets") or 3),
             "muscle": e.get("muscle") or "Autre"}
            for e in exos
        ]
    payload = {
        "_format": EXPORT_FORMAT,
        "name": _program_display_name(prog),
        "seances": seances,
        "_planning": prog.get("_planning", {}),
    }
    buf = io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    return send_file(
        buf,
        mimetype="application/json",
        as_attachment=True,
        download_name=_safe_filename(payload["name"]),
    )


@bp.route("/programme/import", methods=["POST"])
def import_program():
    if not getattr(g, "is_vip", False):
        return render_template("vip_wall.html", active="plus", feature="Import de programme"), 403
    if request.form.get("confirm") != "yes":
        return redirect(url_for("programme.programme"))
    file = request.files.get("file")
    if not file or not file.filename:
        return redirect(url_for("programme.programme"))
    try:
        data = json.loads(file.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return redirect(url_for("programme.programme") + "?import_err=parse")

    if not isinstance(data, dict) or data.get("_format") != EXPORT_FORMAT:
        return redirect(url_for("programme.programme") + "?import_err=format")

    raw_seances = data.get("seances") or {}
    if not isinstance(raw_seances, dict):
        return redirect(url_for("programme.programme") + "?import_err=format")

    # Construction du nouveau programme : remplace toutes les séances mais
    # préserve _settings / _archive / _legacy_volume / _extras (données de
    # l'user qui n'appartiennent pas au programme partagé).
    old = get_prog()
    new_prog: dict = {}
    for sname, exos in raw_seances.items():
        if not isinstance(sname, str) or sname.startswith("_") or not isinstance(exos, list):
            continue
        cleaned = []
        for e in exos:
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
        new_prog[sname] = cleaned

    # Planning : depuis le fichier si présent, sinon vide
    raw_planning = data.get("_planning") or {}
    new_prog["_planning"] = {
        d: (raw_planning.get(d, "") if isinstance(raw_planning, dict) else "")
        for d in DAYS_FR
    }
    # Nom du programme importé (ne casse rien : _name est libre)
    if data.get("name"):
        new_prog["_name"] = str(data["name"])[:80]
    # Programme importé = plus aucune origine catalogue valide
    new_prog.pop("_origin", None)

    # Préserve les données utilisateur indépendantes du programme
    for key in ("_settings", "_archive", "_legacy_volume", "_extras"):
        if key in old:
            new_prog[key] = old[key]

    from core.dates import today_paris_str
    new_prog["_started_at"] = today_paris_str()
    save_prog(new_prog)
    return redirect(url_for("programme.programme") + "?program_changed=1")


# ── Changer de programme (catalogue) ──────────────────────────────
@bp.route("/programme/change-program", methods=["POST"])
def change_program():
    """Remplace ou fusionne le programme courant avec un autre du catalogue.
    mode=replace (défaut) : écrase toutes les séances actuelles.
    mode=merge : ajoute les séances du nouveau prog qui n'existent pas déjà.
    Conserve historique + settings + archive dans tous les cas.
    """
    prog_id = (request.form.get("programme_id") or "").strip()
    mode = (request.form.get("mode") or "replace").strip()
    if request.form.get("confirm") != "yes":
        return redirect(url_for("programme.programme"))

    if prog_id == "custom":
        prog = get_prog()
        for k in list(prog.keys()):
            if not k.startswith("_"):
                prog.pop(k)
        prog.pop("_origin", None)
        prog.pop("_name", None)
        from core.dates import today_paris_str
        prog["_started_at"] = today_paris_str()
        save_prog(prog)
        return redirect(url_for("programme.programme") + "?program_changed=1")

    src = catalog.get_program(prog_id)
    if not src:
        return redirect(url_for("programme.programme"))

    # Free users : bloque les programmes PRO.
    if not bool(getattr(g, "is_vip", False)) and not catalog.is_free(prog_id):
        return render_template("vip_wall.html", active="plus", feature="Programme PRO"), 403

    old = get_prog()
    # Respecte la fréquence configurée par l'utilisateur (onboarding) plutôt
    # que celle par défaut du catalogue. Sinon un user qui a choisi 2 j/sem
    # se retrouve avec 3 ou 4 séances.
    onb = get_onboarding() or {}
    try:
        user_freq = int(onb.get("frequence") or src["freq"])
    except (TypeError, ValueError):
        user_freq = int(src["freq"])
    built = catalog.build_program(prog_id, user_freq)

    if mode == "merge":
        # Garde les séances existantes, ajoute celles du nouveau qui n'existent pas
        merged: dict = {}
        for sname, exos in _seance_items(old):
            merged[sname] = exos
        for sname, exos in built.items():
            if sname.startswith("_"):
                continue
            if sname not in merged:
                merged[sname] = exos
        # Planning : on garde l'ancien (l'utilisateur a déjà fait ses choix)
        merged["_planning"] = old.get("_planning") or built.get("_planning", {})
        # Pas d'origine unique après merge — c'est devenu un programme custom
        merged.pop("_origin", None)
        for key in ("_settings", "_archive", "_legacy_volume", "_extras",
                    "_libre_draft", "_name"):
            if key in old:
                merged[key] = old[key]
        save_prog(merged)
    else:
        new_prog = built
        for key in ("_settings", "_archive", "_legacy_volume", "_extras",
                    "_libre_draft"):
            if key in old:
                new_prog[key] = old[key]
        # Reset programme start date
        from core.dates import today_paris_str
        new_prog["_started_at"] = today_paris_str()
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
