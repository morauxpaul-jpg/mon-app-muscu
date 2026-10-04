"""Blueprint programme — planning hebdo + édition des séances/exos.

Inclut aussi (depuis Phase 4+) : export/import de séances en JSON,
réinitialisation d'une séance prédéfinie, et changement de programme
(catalogue) — déplacé depuis Gestion."""
import io
import json
import logging
import re
from urllib.parse import quote

from flask import (
    Blueprint, render_template, request, redirect, url_for, send_file, jsonify, g
)

from core.data import (get_prog, save_prog, save_prog_body, get_onboarding,
                       rename_seance_rows)
from core.dates import DAYS_FR
from core.limiter import limiter
from core.rotation import rotation_de, rotation_nettoyee
from core.muscu import MUSCLE_LIST, auto_muscles
from core import catalog
from core.programmes_dossiers import (ensure_programmes, fusionner_dans_le_programme_en_cours,
                                      gen_prog_id, remplacer_programme_en_cours)
from core.analytics import paywall

logger = logging.getLogger(__name__)

bp = Blueprint("programme", __name__)


EXPORT_FORMAT = "muscutracker_program_v1"


# Bornes de l'éditeur. Sans elles, une séance à 10 000 séries rendait la
# page de séance inutilisable et gonflait le blob du programme (audit du
# 03/10, M11). Mêmes bornes qu'à l'import (`routes/gestion.py`).
MAX_SERIES = 20
MAX_EXOS_PAR_SEANCE = 30
MAX_SEANCES = 40
NOM_EXO_MAX = 80
NOM_SEANCE_MAX = 60


def _series(valeur, defaut=3) -> int:
    """Nombre de séries borné à [1, MAX_SERIES]."""
    try:
        n = int(float(valeur))
    except (TypeError, ValueError):
        return defaut
    return max(1, min(MAX_SERIES, n))


def _exo_entry(name, sets, muscle, src=None):
    """Entrée d'exercice normalisée. `reps` (fourchette cible, ex. « 8-12 ») et
    `rest_seconds` viennent du catalogue / du générateur / de l'éditeur ; ils
    sont conservés à chaque réécriture (sans eux, un programme n'est plus une
    prescription mais une simple liste de noms). Toutes les écritures passent
    ici : c'est ici que les bornes s'appliquent."""
    src = src or {}
    name = str(name or "").strip()[:NOM_EXO_MAX]
    sets = _series(sets)
    muscle = (str(muscle or "").strip() or "Autre")[:NOM_EXO_MAX]
    reps = str(src.get("reps") or "").strip()[:20]
    try:
        rest = int(src.get("rest_seconds") or 90)
    except (TypeError, ValueError):
        rest = 90
    out = {"name": name, "sets": sets, "muscle": muscle,
           "rest_seconds": max(30, min(300, rest))}
    if reps:
        out["reps"] = reps
    # Superset : cet exercice s'enchaîne avec le suivant, sans repos entre
    # les deux (le chrono part après le second).
    if src.get("superset") is True:
        out["superset"] = True
    return out


def _ensure_planning(prog):
    planning = prog.setdefault("_planning", {})
    for d in DAYS_FR:
        planning.setdefault(d, "")
    return planning


# Dossiers de programmes : la logique vit dans core/programmes_dossiers.py,
# partagée avec le générateur (qui ne peut pas importer ce blueprint).
_gen_prog_id = gen_prog_id
_ensure_programmes = ensure_programmes


def _sort_seances_by_planning(names, planning):
    """Trie les noms de séances par jour de la semaine (lun→dim).
    Les séances sans jour assigné vont en fin de liste."""
    day_index = {d: i for i, d in enumerate(DAYS_FR)}
    seance_day = {}
    for day, sname in (planning or {}).items():
        if sname and sname not in seance_day:
            seance_day[sname] = day_index.get(day, 99)
    return sorted(names, key=lambda s: (seance_day.get(s, 999), s))


def _seance_items(prog):
    """Liste ordonnée des séances du programme, triées par jour planifié."""
    planning = prog.get("_planning") or {}
    items = [(k, v) for k, v in prog.items() if not k.startswith("_")]
    day_index = {d: i for i, d in enumerate(DAYS_FR)}
    seance_day = {}
    for day, sname in planning.items():
        if sname and sname not in seance_day:
            seance_day[sname] = day_index.get(day, 99)
    items.sort(key=lambda kv: (seance_day.get(kv[0], 999), kv[0]))
    return items


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
    before = json.dumps(prog, sort_keys=True, default=str)
    _ensure_planning(prog)
    programmes, seance_prog = _ensure_programmes(prog)
    # Migration de schéma uniquement : on n'écrit que si elle a réellement
    # changé quelque chose (un GET ne doit pas écrire à chaque affichage).
    if json.dumps(prog, sort_keys=True, default=str) != before:
        save_prog(prog)
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
        "rotation": rotation_de(prog),
        "seances": {
            sname: [
                {"name": e.get("name", ""), "sets": int(e.get("sets") or 3),
                 "muscle": e.get("muscle") or "Autre",
                 "reps": e.get("reps") or "",
                 "rest_seconds": int(e.get("rest_seconds") or 90),
                 "superset": e.get("superset") is True}
                for e in exos
            ]
            for sname, exos in seances
        },
        "seance_order": [s for s, _ in seances],
        "origin_seance_names": sorted(_origin_seance_names(prog)),
        "origin": prog.get("_origin"),
        "programmes": [{"id": p["id"], "name": p["name"]} for p in programmes],
        "seance_prog": dict(seance_prog),
        "cardio": [
            {"activite": c.get("activite", ""), "duree": int(c.get("duree") or 30),
             "jours": [j for j in (c.get("jours") or []) if j in DAYS_FR]}
            for c in (prog.get("_cardio") or []) if isinstance(c, dict) and c.get("activite")
        ],
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
        catalog_programs=catalog.list_programs(is_vip=bool(getattr(g, "is_vip_full", False))),
        current_program_meta=current_program_meta,
        ui_state=ui_state,
        bornes={"series": MAX_SERIES, "exos": MAX_EXOS_PAR_SEANCE, "seances": MAX_SEANCES},
        nouveau=request.args.get("nouveau") == "1",
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
    for sname in ordered_names[:MAX_SEANCES]:
        exos = raw_seances.get(sname, [])
        if not isinstance(exos, list) or len(sname) > NOM_SEANCE_MAX:
            continue
        cleaned = []
        for e in exos[:MAX_EXOS_PAR_SEANCE]:
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
            cleaned.append(_exo_entry(ex_name, sets, muscle, e))
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

    # Rotation : celle envoyée par l'éditeur (case « Alterner »), sinon
    # l'existante — limitée aux séances qui existent encore.
    raw_rotation = data["rotation"] if "rotation" in data else old.get("_rotation")
    rotation = rotation_nettoyee(raw_rotation, valid_names)
    if rotation:
        new_prog["_rotation"] = rotation

    # _origin et _started_at appartiennent au corps du programme mais ne sont
    # pas envoyés par l'éditeur : on les reprend tels quels.
    for key in ("_origin", "_started_at"):
        if key in old:
            new_prog[key] = old[key]

    # Cardio planifié (_cardio) : si le client en envoie une liste (ex. après
    # suppression dans l'éditeur) on la reprend nettoyée ; sinon on préserve
    # l'existant. Le nettoyage réutilise le validateur du générateur.
    raw_cardio = data.get("cardio")
    if isinstance(raw_cardio, list):
        from routes.generator import _clean_cardio
        cleaned_cardio = _clean_cardio(raw_cardio)
        if cleaned_cardio:
            new_prog["_cardio"] = cleaned_cardio
    elif old.get("_cardio"):
        new_prog["_cardio"] = old["_cardio"]

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
            new_programmes.append({"id": pid, "name": pname})
    # Si le client n'en envoie pas, on réutilise l'ancien état
    if not new_programmes:
        new_programmes = old.get("_programmes") or []

    # Limite : 1 programme en gratuit. On tolère l'état existant (un user qui
    # avait plusieurs programmes avant de repasser free les garde) mais on
    # bloque toute création supplémentaire.
    if not getattr(g, "is_vip_full", False):
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

    # Fusion : le corps remplace les séances/planning/dossiers, TOUT le reste
    # (badges, record de streak, bilans, exos perso, défis, plats…) survit.
    save_prog_body(new_prog)
    return jsonify({"ok": True})


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
    name = (request.form.get("name") or "").strip()[:NOM_SEANCE_MAX]
    if not name:
        return redirect(url_for("programme.programme"))
    if name.startswith("_"):
        return redirect(url_for("programme.programme") + "?seance=reserve")
    prog = get_prog()
    if sum(1 for k in prog if not k.startswith("_")) >= MAX_SEANCES:
        return redirect(url_for("programme.programme") + "?seance=trop")
    if name in prog:
        # Avant, la création échouait EN SILENCE : le formulaire se fermait,
        # rien n'apparaissait, et on ne pouvait que conclure à un bug.
        return redirect(url_for("programme.programme")
                        + f"?seance=pris&par={quote(_programme_de(prog, name))}")
    prog[name] = []
    save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{name}")


def _renommer_partout(prog, ancien, nouveau):
    """Déplace une séance et TOUT ce qui la désigne.

    Sept structures portent le nom d'une séance : le programme lui-même, son
    rattachement (`_seance_prog`), le planning, et quatre calques rangés par
    « séance|date » — exos ajoutés, ordre des cartes, brouillon libre, bilans
    de fin. En oublier un ne casse rien visiblement : ça laisse juste des
    données orphelines qui ne reviendront jamais, et personne ne saura
    pourquoi.
    """
    ordre = [k for k in prog if not k.startswith("_")]
    if ancien not in ordre:
        return False
    # Le dict garde son ordre : on le reconstruit pour que la séance
    # renommée reste à sa place dans la liste.
    technique = {k: v for k, v in prog.items() if k.startswith("_")}
    refait = {}
    for nom in ordre:
        refait[nouveau if nom == ancien else nom] = prog[nom]
    prog.clear()
    prog.update(refait)
    prog.update(technique)

    rattachement = prog.get("_seance_prog")
    if isinstance(rattachement, dict) and ancien in rattachement:
        rattachement[nouveau] = rattachement.pop(ancien)

    planning = prog.get("_planning")
    if isinstance(planning, dict):
        for jour, seance in planning.items():
            if seance == ancien:
                planning[jour] = nouveau

    rotation = prog.get("_rotation")
    if isinstance(rotation, list):
        prog["_rotation"] = [nouveau if s == ancien else s for s in rotation]

    for calque in ("_extras", "_seance_order", "_libre_draft",
                   "_session_notes", "_substituts"):
        store = prog.get(calque)
        if not isinstance(store, dict):
            continue
        for cle in [c for c in store if str(c).rsplit("|", 1)[0] == ancien]:
            date = str(cle).rsplit("|", 1)[-1]
            store[f"{nouveau}|{date}"] = store.pop(cle)
    return True


@bp.route("/programme/seance/rename", methods=["POST"])
@limiter.limit("20 per minute")
def rename_seance():
    """Renomme une séance, dans le programme ET dans l'historique.

    Appelée par la page programme, qui est pilotée côté client : elle
    renommait jusqu'ici en local, donc l'historique restait sous l'ancien
    nom. La séance repartait à zéro — volume, records, progression — sans
    que rien ne le signale.
    """
    data = request.get_json(silent=True) or request.form
    ancien = (data.get("name") or "").strip()
    nouveau = (data.get("new_name") or "").strip()[:80]
    if not ancien or not nouveau or ancien == nouveau:
        return jsonify({"ok": False, "error": "vide"}), 400
    if nouveau.startswith("_"):
        return jsonify({"ok": False, "error": "reserve"}), 400

    prog = get_prog()
    if nouveau in prog:
        # Les séances sont uniques TOUS PROGRAMMES CONFONDUS, parce que
        # l'historique les retrouve par leur nom. On dit donc qui détient
        # déjà ce nom, sinon on le cherche au mauvais endroit.
        return jsonify({"ok": False, "error": "pris",
                        "programme": _programme_de(prog, nouveau)}), 409
    if not _renommer_partout(prog, ancien, nouveau):
        return jsonify({"ok": False, "error": "introuvable"}), 404
    save_prog(prog)
    try:
        lignes = rename_seance_rows(ancien, nouveau)
    except Exception as e:
        logger.error("rename_seance historique FAILED user=%s: %s",
                     getattr(g, "user_id", "?"), e)
        return jsonify({"ok": False, "error": "historique"}), 500
    try:
        from core.data import rename_session_notes
        rename_session_notes(ancien, nouveau)
    except Exception as e:  # table absente (v34) : l'historique est déjà suivi
        logger.warning("rename_seance bilans FAILED: %s", e)
    return jsonify({"ok": True, "series": lignes})


@bp.route("/programme/seance/disponible", methods=["POST"])
@limiter.limit("60 per minute")
def seance_disponible():
    """Ce nom est-il libre, et sinon qui le détient ?"""
    data = request.get_json(silent=True) or request.form
    nom = (data.get("name") or "").strip()
    prog = get_prog()
    if not nom or nom.startswith("_"):
        return jsonify({"libre": False, "error": "reserve"})
    if nom in prog:
        return jsonify({"libre": False, "programme": _programme_de(prog, nom)})
    return jsonify({"libre": True})


def _programme_de(prog, seance_name):
    """Le nom du programme qui contient cette séance, pour le dire à l'écran."""
    pid = (prog.get("_seance_prog") or {}).get(seance_name)
    for pg in prog.get("_programmes") or []:
        if isinstance(pg, dict) and pg.get("id") == pid:
            return pg.get("name") or "un autre programme"
    return "un autre programme"


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
        _exo_entry(e["name"], int(e["sets"]), e["muscle"],
                   {"reps": e.get("_reps_hint"), "rest_seconds": e.get("_rest")})
        for e in src["seances"][name]
    ]
    save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{name}")


# ── Export / Import du PROGRAMME entier ───────────────────────────
@bp.route("/programme/export", methods=["GET"])
def export_program():
    if not getattr(g, "is_vip_full", False):
        return paywall("Export de programme", 403)
    prog = get_prog()
    seances = {}
    for sname, exos in _seance_items(prog):
        seances[sname] = [
            {"name": e.get("name", ""), "sets": int(e.get("sets") or 3),
             "muscle": e.get("muscle") or "Autre",
             "reps": e.get("reps") or "", "rest_seconds": int(e.get("rest_seconds") or 90)}
            for e in exos
        ]
    payload = {
        "_format": EXPORT_FORMAT,
        "name": _program_display_name(prog),
        "seances": seances,
        "_planning": prog.get("_planning", {}),
    }
    if rotation_de(prog):
        payload["_rotation"] = rotation_de(prog)
    buf = io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    return send_file(
        buf,
        mimetype="application/json",
        as_attachment=True,
        download_name=_safe_filename(payload["name"]),
    )


@bp.route("/programme/import", methods=["POST"])
def import_program():
    if not getattr(g, "is_vip_full", False):
        return paywall("Import de programme", 403)
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

    # Le programme importé remplace le programme EN COURS ; les autres
    # dossiers et les données personnelles restent.
    old = get_prog()
    new_prog: dict = {}
    for sname, exos in list(raw_seances.items())[:MAX_SEANCES]:
        if not isinstance(sname, str) or sname.startswith("_") or not isinstance(exos, list):
            continue
        sname = sname.strip()[:NOM_SEANCE_MAX]
        if not sname:
            continue
        cleaned = []
        for e in exos[:MAX_EXOS_PAR_SEANCE]:
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
            cleaned.append(_exo_entry(ex_name, sets, muscle, e))
        new_prog[sname] = cleaned

    # Planning : depuis le fichier si présent, sinon vide
    raw_planning = data.get("_planning") or {}
    new_prog["_planning"] = {
        d: (raw_planning.get(d, "") if isinstance(raw_planning, dict) else "")
        for d in DAYS_FR
    }
    # Nom du programme importé (ne casse rien : _name est libre)
    from core.dates import today_paris_str
    planning = new_prog.pop("_planning")
    nom = str(data.get("name") or "Programme importé")[:80]
    # Programme importé = plus aucune origine catalogue valide (pas d'_origin).
    rotation = rotation_nettoyee(data.get("_rotation"), new_prog)
    save_prog_body(remplacer_programme_en_cours(old, new_prog, planning, nom,
                                                today_paris_str(),
                                                {"_rotation": rotation} if rotation else None))
    return redirect(url_for("programme.programme") + "?program_changed=1")


# ── Changer de programme (catalogue) ──────────────────────────────
@bp.route("/programme/change-program", methods=["POST"])
def change_program():
    """Remplace ou fusionne le programme EN COURS avec un autre du catalogue.
    mode=replace (défaut) : remplace les séances du programme en cours.
    mode=merge : ajoute les séances du nouveau prog qui n'existent pas déjà.
    Dans les deux cas, les AUTRES programmes (dossiers) restent intacts —
    avant, « Remplacer » les effaçait tous — ainsi que l'historique et les
    réglages.
    """
    prog_id = (request.form.get("programme_id") or "").strip()
    mode = (request.form.get("mode") or "replace").strip()
    if request.form.get("confirm") != "yes":
        return redirect(url_for("programme.programme"))

    if prog_id == "custom":
        from core.dates import today_paris_str
        save_prog_body(remplacer_programme_en_cours(
            get_prog(), {}, {d: "" for d in DAYS_FR}, "Mon programme", today_paris_str()))
        return redirect(url_for("programme.programme") + "?program_changed=1")

    src = catalog.get_program(prog_id)
    if not src:
        return redirect(url_for("programme.programme"))

    # Free users : bloque les programmes PRO.
    if not bool(getattr(g, "is_vip_full", False)) and not catalog.is_free(prog_id):
        return paywall("Programme PRO", 403)

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

    seances = {k: v for k, v in built.items() if not k.startswith("_")}
    if mode == "merge":
        save_prog_body(fusionner_dans_le_programme_en_cours(old, seances))
    else:
        from core.dates import today_paris_str
        extra = {k: built[k] for k in ("_origin", "_cardio", "_rotation") if k in built}
        save_prog_body(remplacer_programme_en_cours(
            old, seances, built.get("_planning") or {}, src["title"],
            today_paris_str(), extra))
    return redirect(url_for("programme.programme") + "?program_changed=1")


# ── Exercices ────────────────────────────────────────────────────
@bp.route("/programme/exo/add", methods=["POST"])
def add_exo():
    f = request.form
    seance = f["seance"]
    name = (f.get("name") or "").strip()
    if not name:
        return redirect(url_for("programme.programme") + f"#s-{seance}")
    sets = _series(f.get("sets") or 3)
    muscles = f.getlist("muscles")
    muscle = ",".join(muscles) if muscles else (auto_muscles(name) or "Autre")
    reps = (f.get("reps") or "").strip()[:20]
    try:
        rest = int(f.get("rest_seconds") or 90)
    except ValueError:
        rest = 90
    prog = get_prog()
    if seance in prog and len(prog[seance]) >= MAX_EXOS_PAR_SEANCE:
        return redirect(url_for("programme.programme") + "?exo=trop" + f"#s-{seance}")
    if seance in prog:
        prog[seance].append(_exo_entry(name, sets, muscle,
                                       {"reps": reps, "rest_seconds": rest}))
        save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{seance}")


@bp.route("/programme/exo/update", methods=["POST"])
def update_exo():
    f = request.form
    seance = f["seance"]
    try:
        idx = int(f["index"])
    except (KeyError, ValueError):
        return redirect(url_for("programme.programme"))
    prog = get_prog()
    if seance not in prog or not (0 <= idx < len(prog[seance])):
        return redirect(url_for("programme.programme"))
    ex = prog[seance][idx]
    if f.get("sets"):
        ex["sets"] = _series(f.get("sets"), ex.get("sets", 3))
    muscles = f.getlist("muscles")
    if muscles:
        ex["muscle"] = ",".join(muscles)
    if f.get("reps") is not None:
        reps = (f.get("reps") or "").strip()[:20]
        if reps:
            ex["reps"] = reps
        else:
            ex.pop("reps", None)
    if f.get("rest_seconds"):
        try:
            ex["rest_seconds"] = max(30, min(300, int(f["rest_seconds"])))
        except ValueError:
            pass
    save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{seance}")


@bp.route("/programme/exo/delete", methods=["POST"])
def delete_exo():
    f = request.form
    seance = f["seance"]
    try:
        idx = int(f["index"])
    except (KeyError, ValueError):
        return redirect(url_for("programme.programme"))
    prog = get_prog()
    if seance in prog and 0 <= idx < len(prog[seance]):
        prog[seance].pop(idx)
        save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{seance}")


@bp.route("/programme/exo/move", methods=["POST"])
def move_exo():
    f = request.form
    seance = f["seance"]
    try:
        idx = int(f["index"])
    except (KeyError, ValueError):
        return redirect(url_for("programme.programme"))
    direction = f.get("direction", "up")
    prog = get_prog()
    if seance not in prog:
        return redirect(url_for("programme.programme"))
    lst = prog[seance]
    j = idx - 1 if direction == "up" else idx + 1
    if 0 <= idx < len(lst) and 0 <= j < len(lst):
        lst[idx], lst[j] = lst[j], lst[idx]
        save_prog(prog)
    return redirect(url_for("programme.programme") + f"#s-{seance}")
