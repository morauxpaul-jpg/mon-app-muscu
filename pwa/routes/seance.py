"""Blueprint séance — choix, saisie (prefaite ou libre), skip/save/miss/reset.

Logique portée depuis app.py lignes 1555-1722 (choix_seance) et 2048-2676 (ma séance).
"""
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, abort

from core.data import (
    get_hist, get_prog,
    replace_exo_rows, delete_exo_rows, delete_session_rows, mark_session_missed,
)
from core.dates import today_paris, today_paris_str, now_paris, DAYS_FR, MONTHS_FR
from core.muscu import calc_1rm, get_base_name, fix_muscle, auto_muscles

bp = Blueprint("seance", __name__)

MUSCLE_LIST = ["Pecs", "Dos", "Épaules", "Biceps", "Triceps", "Avant-bras", "Abdos",
               "Quadriceps", "Ischio-jambiers", "Fessiers", "Mollets", "Autre"]
VARIANTS = ["Standard", "Barre", "Haltères", "Banc", "Poulie", "Machine", "Lesté"]
BW_EXOS = {"Dips", "Tractions"}


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────

def _normalize_hist(hist, prog):
    prog_seances = {k: v for k, v in prog.items() if not k.startswith("_")}
    muscle_mapping = {ex["name"]: ex.get("muscle", "Autre")
                      for s in prog_seances for ex in prog_seances[s]}
    for r in hist:
        base = get_base_name(r["Exercice"])
        if base in muscle_mapping:
            r["Muscle"] = muscle_mapping[base]
        r["Muscle"] = fix_muscle(r["Exercice"], r["Muscle"])
    return hist, prog_seances


def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _iso_week(date_):
    return date_.isocalendar().week


def _date_label(date_):
    return f"{DAYS_FR[date_.weekday()]} {date_.day:02d}/{date_.month:02d}/{date_.year}"


def _is_real_perf(r):
    if r["Exercice"] == "SESSION":
        return False
    if r["Poids"] > 0 or r["Reps"] > 0:
        return True
    return "SKIP" in (r.get("Remarque") or "")


def _find_done_session(date_iso, hist):
    """Si une séance a été effectivement réalisée ce jour-là, retourne son nom."""
    day_rows = [r for r in hist if r["Date"] == date_iso]
    real = [r for r in day_rows if _is_real_perf(r)]
    if not real:
        return None
    counts = {}
    for r in real:
        counts.setdefault(r["Séance"], set()).add(r["Exercice"])
    return max(counts.items(), key=lambda kv: len(kv[1]))[0]


def _exo_curr_rows(hist, semaine, seance, exercice):
    return [r for r in hist
            if r["Semaine"] == semaine and r["Séance"] == seance and r["Exercice"] == exercice]


def _exo_completed(curr_rows):
    if not curr_rows:
        return False
    has_data = any(r["Poids"] > 0 or r["Reps"] > 0 for r in curr_rows)
    has_skip = any("SKIP" in (r.get("Remarque") or "") for r in curr_rows)
    return has_data or has_skip


def _last_variant(hist, seance, exo_base):
    """Dernière variante utilisée pour cet exo dans cette séance."""
    matches = [r for r in hist
               if r["Séance"] == seance and exo_base in r["Exercice"]]
    if not matches:
        return "Standard"
    last = matches[-1]["Exercice"]
    if "(" in last:
        v = last.split("(")[1].replace(")", "").strip()
        return v if v in VARIANTS else "Standard"
    return "Standard"


def _best_record(hist, exo_final, is_bw):
    """Renvoie {best_weight, best_1rm, best_reps} pour la variante exacte."""
    matches = [r for r in hist if r["Exercice"] == exo_final and r["Reps"] > 0]
    if not matches:
        return None
    if is_bw:
        return {"reps": max(r["Reps"] for r in matches)}
    best_w = max(r["Poids"] for r in matches)
    best_1rm = max(calc_1rm(r["Poids"], r["Reps"]) for r in matches)
    return {"weight": best_w, "one_rm": round(best_1rm, 1)}


def _previous_weeks_data(hist, exo_final, seance, s_act, n_weeks=2):
    """Semaines précédentes avec leurs séries, + semaines manquées."""
    f_h = [r for r in hist if r["Exercice"] == exo_final and r["Séance"] == seance]
    hist_weeks_all = sorted({r["Semaine"] for r in f_h if r["Semaine"] < s_act})
    hist_weeks = [w for w in hist_weeks_all
                  if any(r["Semaine"] == w and r["Poids"] > 0 for r in f_h)]
    missed = {r["Semaine"] for r in hist
              if r["Séance"] == seance and r["Exercice"] == "SESSION" and r["Semaine"] < s_act}

    if not hist_weeks:
        return []

    weeks_to_show = hist_weeks[-n_weeks:]
    min_w = weeks_to_show[0]
    combined = sorted(set(weeks_to_show) | {w for w in missed if w >= min_w})
    out = []
    for w in combined:
        if w in missed and w not in weeks_to_show:
            out.append({"week": w, "missed": True, "rows": []})
        else:
            rows = [r for r in f_h if r["Semaine"] == w and r["Poids"] > 0]
            rows.sort(key=lambda r: int(r["Série"] or 0))
            out.append({"week": w, "missed": False, "rows": rows})
    return out


def _recup_status(hist, s_act):
    """Statut de récupération par muscle pour la semaine active."""
    muscles = ["Pecs", "Dos", "Épaules", "Biceps", "Triceps", "Abdos", "Quadriceps", "Mollets"]
    now = now_paris().replace(tzinfo=None)
    out = []
    for m in muscles:
        trained = [r for r in hist if r["Semaine"] == s_act and m in (r.get("Muscle") or "")]
        color, label = "#00FF7F", "PRÊT"
        if trained:
            dates = [r["Date"] for r in trained if r.get("Date")]
            if dates:
                last = max(dates)
                try:
                    diff = (now - datetime.strptime(last, "%Y-%m-%d")).days
                    if diff < 1:
                        color, label = "#FF453A", "REPAR."
                    elif diff < 2:
                        color, label = "#FFA500", "RECON."
                except ValueError:
                    pass
        out.append({"muscle": m, "color": color, "label": label})
    return out


def _last_session_sets(hist, exo_final, seance, s_act):
    """Retourne les séries de la dernière semaine où cet exo a été réalisé,
    sous forme de liste de dicts {reps, poids}. Utilisé pour le pré-remplissage
    des poids et l'affichage inline 'Dernière fois'."""
    matches = [r for r in hist
               if r["Exercice"] == exo_final and r["Séance"] == seance
               and r["Semaine"] < s_act and r["Poids"] > 0]
    if not matches:
        # Chercher dans toutes les séances si pas trouvé dans la même séance
        matches = [r for r in hist
                   if r["Exercice"] == exo_final
                   and r["Semaine"] < s_act and r["Poids"] > 0]
    if not matches:
        return []
    last_week = max(r["Semaine"] for r in matches)
    last = [r for r in matches if r["Semaine"] == last_week]
    last.sort(key=lambda r: int(r["Série"] or 0))
    return [{"reps": int(r["Reps"]), "poids": float(r["Poids"])} for r in last]


def _build_exo_context(hist, exo_obj, seance, s_act, is_extra=False):
    """Construit le dict passé au template pour un exercice."""
    base = exo_obj["name"]
    p_sets = int(exo_obj.get("sets", 3))
    muscle = exo_obj.get("muscle", "Autre")
    rest_seconds = int(exo_obj.get("rest_seconds", 90))

    var = _last_variant(hist, seance, base)
    exo_final = f"{base} ({var})" if var != "Standard" else base
    is_bw = base in BW_EXOS and var != "Lesté"

    curr = _exo_curr_rows(hist, s_act, seance, exo_final)
    curr.sort(key=lambda r: int(r["Série"] or 0))
    completed = _exo_completed(curr)
    record = _best_record(hist, exo_final, is_bw)
    prev_weeks = _previous_weeks_data(hist, exo_final, seance, s_act, n_weeks=2)

    # Dernière séance pour pré-remplissage poids + affichage inline
    last_sets = _last_session_sets(hist, exo_final, seance, s_act)

    # Sets à afficher dans l'éditeur : au moins p_sets, ou autant que déjà saisis
    n_rows = max(p_sets, len(curr)) if curr else p_sets
    sets = []
    existing_by_idx = {int(r["Série"] or 0): r for r in curr}
    for i in range(1, n_rows + 1):
        r = existing_by_idx.get(i, {})
        reps_val = int(r.get("Reps") or 0)
        poids_val = float(r.get("Poids") or 0)
        # Pré-remplir le poids depuis la dernière séance si pas encore saisi
        if poids_val == 0 and reps_val == 0 and not completed and i <= len(last_sets):
            poids_val = last_sets[i - 1]["poids"]
        sets.append({
            "serie": i,
            "reps": reps_val,
            "poids": poids_val,
            "remarque": r.get("Remarque") or "",
        })

    # Résumé inline : "80kg × 8, 85kg × 6"
    if last_sets:
        last_summary = ", ".join(
            f"{s['poids']:g}kg × {s['reps']}" for s in last_sets
        )
    else:
        last_summary = ""

    return {
        "base": base,
        "muscle": muscle,
        "p_sets": p_sets,
        "rest_seconds": rest_seconds,
        "is_extra": is_extra,
        "variant": var,
        "exo_final": exo_final,
        "is_bw": is_bw,
        "completed": completed,
        "record": record,
        "prev_weeks": prev_weeks,
        "sets": sets,
        "last_summary": last_summary,
    }


# ────────────────────────────────────────────────────────────────
# Vue principale : choix ou édition
# ────────────────────────────────────────────────────────────────
@bp.route("/seance")
def seance():
    hist = get_hist()
    prog = get_prog()
    hist, prog_seances = _normalize_hist(hist, prog)
    _settings = prog.get("_settings", {})
    auto_rest_timer = _settings.get("auto_rest_timer", True)

    date_iso = request.args.get("date") or today_paris_str()
    target_date = _parse_date(date_iso) or today_paris()
    date_iso = target_date.strftime("%Y-%m-%d")
    s_act = _iso_week(target_date)

    mode = request.args.get("mode")   # "prefaite" | "libre" | None
    name = request.args.get("name")   # nom séance (prefaite) ou libre
    today = today_paris()

    done_name = _find_done_session(date_iso, hist)

    # ── Vue choix (pas de mode choisi) ────────────────────────────
    if not mode:
        if date_iso == today_paris_str() and not done_name:
            titre = "Quelle séance aujourd'hui ?"
            subtitle_text, subtitle_color = "", ""
            label = f"{DAYS_FR[target_date.weekday()]} {target_date.day} {MONTHS_FR[target_date.month-1]}"
        elif done_name:
            titre = f"Séance réalisée · {done_name}"
            subtitle_text, subtitle_color = "RÉALISÉE", "#00FF7F"
            label = f"{DAYS_FR[target_date.weekday()]} {target_date.day} {MONTHS_FR[target_date.month-1]}"
        elif target_date < today:
            titre = "Séance manquée"
            subtitle_text, subtitle_color = "MANQUÉE", "#FF453A"
            label = f"{DAYS_FR[target_date.weekday()]} {target_date.day} {MONTHS_FR[target_date.month-1]}"
        else:
            titre = "Séance à faire"
            subtitle_text, subtitle_color = "À FAIRE", "#58CCFF"
            label = f"{DAYS_FR[target_date.weekday()]} {target_date.day} {MONTHS_FR[target_date.month-1]}"

        return render_template(
            "seance_choix.html",
            active="seance",
            date_iso=date_iso,
            date_label=label,
            titre=titre,
            subtitle_text=subtitle_text,
            subtitle_color=subtitle_color,
            done_name=done_name,
            seance_names=list(prog_seances.keys()),
            prog_seances=prog_seances,
            planning=prog.get("_planning", {}),
            jours_map=prog.get("_jours", {}),
        )

    # ── Vue édition : mode prefaite ───────────────────────────────
    if mode == "prefaite":
        if not name or name not in prog_seances:
            return redirect(url_for("seance.seance", date=date_iso))

        exos_prog = list(prog_seances[name])
        # Extras : stockés dans prog sous "_extras" par (seance, date) pour partage entre sessions
        extras_key = f"{name}|{date_iso}"
        extras = prog.get("_extras", {}).get(extras_key, [])
        all_exos = [(e, False) for e in exos_prog] + [(e, True) for e in extras]

        exos_ctx = [_build_exo_context(hist, e, name, s_act, is_extra=is_extra)
                    for e, is_extra in all_exos]

        # Volume
        vol_curr = sum(r["Poids"] * r["Reps"] for r in hist
                       if r["Séance"] == name and r["Semaine"] == s_act)
        vol_prev = sum(r["Poids"] * r["Reps"] for r in hist
                       if r["Séance"] == name and r["Semaine"] == s_act - 1)
        vol_ratio = min((vol_curr / vol_prev) if vol_prev > 0 else 0, 1.2)

        # Progression : exercices complétés / total
        exos_done = sum(1 for e in exos_ctx if e["completed"])
        exos_total = len(exos_ctx)

        # Exos dispo pour ajout (tous les exos de tous les programmes)
        all_prog_exos = {}
        for _sn, _exos in prog_seances.items():
            for _e in _exos:
                all_prog_exos.setdefault(_e["name"], _e)

        return render_template(
            "seance_edit.html",
            active="seance",
            mode="prefaite",
            seance_name=name,
            date_iso=date_iso,
            date_label=_date_label(target_date),
            is_rattrapage=(date_iso != today_paris_str()),
            s_act=s_act,
            exos=exos_ctx,
            exos_done=exos_done,
            exos_total=exos_total,
            recup=_recup_status(hist, s_act),
            vol_curr=int(vol_curr),
            vol_prev=int(vol_prev),
            vol_ratio=vol_ratio,
            vol_overload=(vol_curr >= vol_prev and vol_prev > 0),
            all_prog_exos=list(all_prog_exos.values()),
            muscle_list=MUSCLE_LIST,
            variants=VARIANTS,
            auto_rest_timer=auto_rest_timer,
        )

    # ── Vue édition : mode libre ──────────────────────────────────
    if mode == "libre":
        libre_name = name or "Séance Libre"
        libre_exos = prog.get("_libre_draft", {}).get(f"{libre_name}|{date_iso}", [])
        exos_ctx = [_build_exo_context(hist, e, libre_name, s_act, is_extra=False)
                    for e in libre_exos]

        exos_done = sum(1 for e in exos_ctx if e["completed"])
        exos_total = len(exos_ctx)

        all_prog_exos = {}
        for _sn, _exos in prog_seances.items():
            for _e in _exos:
                all_prog_exos.setdefault(_e["name"], _e)

        return render_template(
            "seance_edit.html",
            active="seance",
            mode="libre",
            seance_name=libre_name,
            date_iso=date_iso,
            date_label=_date_label(target_date),
            is_rattrapage=(date_iso != today_paris_str()),
            s_act=s_act,
            exos=exos_ctx,
            exos_done=exos_done,
            exos_total=exos_total,
            recup=_recup_status(hist, s_act),
            vol_curr=0, vol_prev=0, vol_ratio=0, vol_overload=False,
            all_prog_exos=list(all_prog_exos.values()),
            muscle_list=MUSCLE_LIST,
            variants=VARIANTS,
            auto_rest_timer=auto_rest_timer,
        )

    abort(404)


# ────────────────────────────────────────────────────────────────
# Actions POST (form-based, PRG pattern)
# ────────────────────────────────────────────────────────────────

def _back_to_editor(form):
    return redirect(url_for(
        "seance.seance",
        date=form["date"], mode=form["mode"], name=form["name"]
    ))


def _update_extras(prog_dict, key, mutate_fn):
    extras_all = prog_dict.setdefault("_extras", {})
    lst = extras_all.get(key, [])
    mutate_fn(lst)
    if lst:
        extras_all[key] = lst
    else:
        extras_all.pop(key, None)


def _update_libre_draft(prog_dict, key, mutate_fn):
    drafts = prog_dict.setdefault("_libre_draft", {})
    lst = drafts.get(key, [])
    mutate_fn(lst)
    if lst:
        drafts[key] = lst
    else:
        drafts.pop(key, None)


@bp.route("/seance/save-exo", methods=["POST"])
def save_exo():
    f = request.form
    semaine = int(f["semaine"])
    seance = f["seance_name"]
    exo_base = f["exo_base"]
    variant = f["variant"]
    muscle = f["muscle"]
    date_str = f["date"]
    is_bw = f.get("is_bw") == "1"
    sets_json = f.get("sets_json", "[]")
    try:
        sets = json.loads(sets_json)
    except json.JSONDecodeError:
        sets = []

    exo_final = f"{exo_base} ({variant})" if variant != "Standard" else exo_base

    new_rows = []
    for i, s in enumerate(sets, start=1):
        try:
            reps = int(float(s.get("reps") or 0))
        except (ValueError, TypeError):
            reps = 0
        try:
            poids = 0.0 if is_bw else float(s.get("poids") or 0)
        except (ValueError, TypeError):
            poids = 0.0
        new_rows.append({
            "Semaine": semaine,
            "Séance": seance,
            "Exercice": exo_final,
            "Série": i,
            "Reps": reps,
            "Poids": poids,
            "Remarque": s.get("remarque") or "",
            "Muscle": muscle,
            "Date": date_str,
        })

    replace_exo_rows(semaine, seance, exo_final, new_rows)
    return _back_to_editor(f)


@bp.route("/seance/skip-exo", methods=["POST"])
def skip_exo():
    f = request.form
    semaine = int(f["semaine"])
    seance = f["seance_name"]
    variant = f["variant"]
    exo_base = f["exo_base"]
    exo_final = f"{exo_base} ({variant})" if variant != "Standard" else exo_base
    new_rows = [{
        "Semaine": semaine, "Séance": seance, "Exercice": exo_final,
        "Série": 1, "Reps": 0, "Poids": 0.0,
        "Remarque": "SKIP 🚫", "Muscle": f.get("muscle", "Autre"),
        "Date": f["date"],
    }]
    replace_exo_rows(semaine, seance, exo_final, new_rows)
    return _back_to_editor(f)


@bp.route("/seance/reset-exo", methods=["POST"])
def reset_exo():
    f = request.form
    semaine = int(f["semaine"])
    seance = f["seance_name"]
    variant = f["variant"]
    exo_base = f["exo_base"]
    exo_final = f"{exo_base} ({variant})" if variant != "Standard" else exo_base
    delete_exo_rows(semaine, seance, exo_final)
    return _back_to_editor(f)


@bp.route("/seance/reset-session", methods=["POST"])
def reset_session():
    f = request.form
    delete_session_rows(int(f["semaine"]), f["seance_name"])
    return _back_to_editor(f)


@bp.route("/seance/mark-missed", methods=["POST"])
def mark_missed():
    f = request.form
    date_str = f["date"]
    target = _parse_date(date_str) or today_paris()
    semaine = _iso_week(target)
    seance_name = f.get("seance_name") or "Séance manquée"
    mark_session_missed(semaine, seance_name, date_str)
    return redirect(url_for("accueil.index"))


@bp.route("/seance/add-extra", methods=["POST"])
def add_extra():
    f = request.form
    mode = f["mode"]
    seance_name = f["seance_name"]
    date_str = f["date"]
    name = (f.get("exo_name") or "").strip()
    if not name:
        return _back_to_editor(f)
    muscle = f.get("muscle") or auto_muscles(name) or "Autre"
    sets = int(f.get("sets_count") or 3)
    prog = get_prog()
    key = f"{seance_name}|{date_str}"
    item = {"name": name, "muscle": muscle, "sets": sets}
    if mode == "libre":
        _update_libre_draft(prog, key, lambda lst: lst.append(item))
    else:
        _update_extras(prog, key, lambda lst: lst.append(item))
    from core.data import save_prog
    save_prog(prog)
    return _back_to_editor(f)


@bp.route("/seance/remove-extra", methods=["POST"])
def remove_extra():
    f = request.form
    mode = f["mode"]
    seance_name = f["seance_name"]
    date_str = f["date"]
    idx = int(f["index"])
    prog = get_prog()
    key = f"{seance_name}|{date_str}"

    def _remove(lst):
        if 0 <= idx < len(lst):
            lst.pop(idx)

    if mode == "libre":
        _update_libre_draft(prog, key, _remove)
    else:
        _update_extras(prog, key, _remove)
    from core.data import save_prog
    save_prog(prog)
    return _back_to_editor(f)


@bp.route("/seance/finish", methods=["POST"])
def finish():
    """Termine la séance : nettoie le brouillon libre ou les extras et retourne à l'accueil."""
    f = request.form
    mode = f["mode"]
    seance_name = f["seance_name"]
    date_str = f["date"]
    key = f"{seance_name}|{date_str}"
    prog = get_prog()
    changed = False
    if mode == "libre" and "_libre_draft" in prog and key in prog["_libre_draft"]:
        prog["_libre_draft"].pop(key, None)
        changed = True
    if mode == "prefaite" and "_extras" in prog and key in prog["_extras"]:
        prog["_extras"].pop(key, None)
        changed = True
    if changed:
        from core.data import save_prog
        save_prog(prog)
    return redirect(url_for("accueil.index"))
