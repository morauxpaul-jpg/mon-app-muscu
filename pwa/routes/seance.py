"""Blueprint séance — choix, saisie (prefaite ou libre), skip/save/miss/reset.

Logique portée depuis app.py lignes 1555-1722 (choix_seance) et 2048-2676 (ma séance).
"""
import json
import logging
from datetime import timedelta
from flask import Blueprint, render_template, request, redirect, url_for, abort, jsonify, g, session

logger = logging.getLogger(__name__)

from core.data import (
    get_hist, get_prog, clear_user_cache,
    replace_exo_rows, append_exo_rows, delete_exo_rows, delete_session_rows, mark_session_missed,
)
from core.dates import (today_paris, today_paris_str, logical_today_paris, now_paris,
                        continuous_week, DAYS_FR, MONTHS_FR)
from core.limiter import limiter
from core.muscu import BW_EXOS, MUSCLE_LIST, VARIANTS, auto_muscles
from core.exercises_data import filter_exos_by_equipment, detect_isometric
from core.body_map import get_body_polygons
from core.hist import is_logged as _is_real_perf
from core.analytics import track

# Le calcul de la séance vit dans core/ : ce fichier n'est plus que la couche
# HTTP — les routes, le formulaire, le rendu. Les six modules ci-dessous ne
# touchent ni à Flask ni à la base : on leur passe l'historique et le
# programme, ils rendent des dictionnaires. Cf. CONTEXT.md et
# tests/test_couche_seance.py.
from core.seance_semaine import (_date_label, _display_week, _find_done_session,
                                 _iso_week, _normalize_hist, _parse_date)
from core.seance_historique import (_best_record, _exo_completed, _exo_curr_rows,
                                    _last_session_sets, _norm, _previous_weeks_data,
                                    _recup_status, _suggestion_for)
from core.seance_contexte import (_build_all_exo_contexts, _reconstruct_history_exos)
from core.seance_calques import (_appliquer_substituts, _apply_seance_order,
                                 _purge_old_session_notes, _update_extras,
                                 _update_libre_draft, purger_les_calques)
from core.seance_saisie import (_form_date, _known_exo_names, _parse_session_note,
                                _pr_check, _reps_saisies, _rows_from_sets, _session_duration_min,
                                _session_totals)
from core.seance_cardio import (UNITES_CARDIO, _build_cardio_done,
                                completer_mesures)

bp = Blueprint("seance", __name__)

# ────────────────────────────────────────────────────────────────
# Vue principale : choix ou édition
# ────────────────────────────────────────────────────────────────
@bp.route("/seance")
def seance():
    try:
        hist = get_hist()
        prog = get_prog()
    except Exception as e:
        logger.error("seance() DB failed: %s", e)
        return render_template(
            "error.html", code=503,
            message="Impossible de charger ta séance. Vérifie ta connexion et réessaie.",
        ), 503
    hist, prog_seances = _normalize_hist(hist, prog)
    _settings = prog.get("_settings", {})
    auto_rest_timer = _settings.get("auto_rest_timer", True)
    auto_prefill_weight = _settings.get("auto_prefill_weight", True)
    show_rpe = _settings.get("show_rpe", True)
    show_overload_hint = _settings.get("show_overload_hint", True)

    # « Aujourd'hui logique » : avant 04h du matin, on considère encore
    # la journée précédente — la séance faite « tard hier soir » est ainsi
    # rangée au bon jour.
    logical_today = logical_today_paris()
    logical_today_str = logical_today.strftime("%Y-%m-%d")

    date_iso = request.args.get("date") or logical_today_str
    target_date = _parse_date(date_iso) or logical_today
    date_iso = target_date.strftime("%Y-%m-%d")
    s_act = _iso_week(target_date)
    s_display = _display_week(target_date, prog, hist)
    week_offset = s_act - s_display  # to convert ISO week → display week

    mode = request.args.get("mode")   # "prefaite" | "libre" | None
    name = request.args.get("name")   # nom séance (prefaite) ou libre
    today = logical_today

    done_name = _find_done_session(date_iso, hist)

    # ── Vue choix (pas de mode choisi) ────────────────────────────
    if not mode:
        if date_iso == logical_today_str and not done_name:
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

        # Regroupe les séances par programme pour un affichage clair,
        # filtré par profil d'entraînement actif (s'il y en a plusieurs).
        programmes = prog.get("_programmes") or []
        seance_prog = prog.get("_seance_prog") or {}
        profiles = prog.get("_profiles") or []
        active_profile = prog.get("_active_profile")
        active_programmes = programmes
        if len(profiles) > 1 and active_profile:
            valid_pids = {p.get("id") for p in profiles if isinstance(p, dict)}
            fallback_pid = profiles[0].get("id") if profiles else None
            for pg in programmes:
                if isinstance(pg, dict) and pg.get("profile_id") not in valid_pids:
                    pg["profile_id"] = fallback_pid
            active_programmes = [p for p in programmes if isinstance(p, dict) and p.get("profile_id") == active_profile]
        prog_by_id = {p["id"]: p["name"] for p in active_programmes if isinstance(p, dict) and p.get("id")}
        _planning = prog.get("_planning") or {}
        _day_idx = {d: i for i, d in enumerate(DAYS_FR)}
        _s_day = {}
        for _d, _sn in _planning.items():
            if _sn and _sn not in _s_day:
                _s_day[_sn] = _day_idx.get(_d, 99)
        _sort_key = lambda s: (_s_day.get(s, 999), s)
        seance_order = sorted(prog_seances.keys(), key=_sort_key)
        groups = []
        for p in active_programmes:
            pid = p.get("id") if isinstance(p, dict) else None
            if not pid:
                continue
            snames = sorted([s for s in seance_order if seance_prog.get(s) == pid], key=_sort_key)
            if snames:
                groups.append({"name": p.get("name") or "Programme", "seances": snames})
        # Séances orphelines : n'apparaissent que si le profil actif n'est pas
        # filtré (ou s'il n'y a qu'un profil).
        if len(profiles) <= 1:
            unclassified = [s for s in seance_order if not seance_prog.get(s) or seance_prog.get(s) not in prog_by_id]
            if unclassified:
                label_uncl = "Non classé" if groups else "Mes séances"
                groups.append({"name": label_uncl, "seances": unclassified})

        # ── Séance de rattrapage : uniquement la séance de la VEILLE si
        # elle était planifiée, pas faite, et pas marquée comme manquée.
        # (Choix produit : au-delà d'un jour, on n'incite plus à rattraper.)
        makeup_suggestions = []
        if date_iso == logical_today_str:
            planning_map = prog.get("_planning", {})
            seance_names_set = set(prog_seances.keys())
            # Séances déjà faites sur une date donnée (par nom).
            done_by_date = {}
            for r in hist:
                if _is_real_perf(r) and r.get("Date") and r.get("Séance"):
                    done_by_date.setdefault(r["Date"], set()).add(r["Séance"])
            # Pour chaque nom de séance, collecte toutes les dates où elle
            # a été faite (sert à détecter un rattrapage déjà effectué).
            done_dates_by_seance = {}
            for d_iso, names in done_by_date.items():
                for n in names:
                    done_dates_by_seance.setdefault(n, set()).add(d_iso)

            for offset in (1,):  # veille uniquement
                d = logical_today - timedelta(days=offset)
                d_name_fr = DAYS_FR[d.weekday()]
                planned = planning_map.get(d_name_fr, "")
                if not planned or planned not in seance_names_set:
                    continue
                d_iso = d.strftime("%Y-%m-%d")
                # Déjà faite ce jour-là ?
                if planned in done_by_date.get(d_iso, set()):
                    continue
                # Déjà rattrapée entre d+1 et aujourd'hui ?
                rattrape = False
                for off2 in range(1, offset + 1):
                    d2 = d + timedelta(days=off2)
                    d2_iso = d2.strftime("%Y-%m-%d")
                    # Un jour où cette même séance était déjà planifiée
                    # ne compte pas comme rattrapage.
                    d2_name_fr = DAYS_FR[d2.weekday()]
                    if planning_map.get(d2_name_fr) == planned:
                        continue
                    if planned in done_by_date.get(d2_iso, set()):
                        rattrape = True
                        break
                if rattrape:
                    continue
                # Marquée manquée explicitement ?
                marked_missed = any(
                    r for r in hist
                    if r.get("Date") == d_iso
                    and r.get("Exercice") == "SESSION"
                    and "MANQUÉE" in (r.get("Remarque") or "")
                )
                if marked_missed:
                    continue
                makeup_suggestions.append({
                    "seance": planned,
                    "date_iso": d_iso,
                    "day_label": f"{d_name_fr} {d.day:02d}/{d.month:02d}",
                    "offset": offset,
                })

        # ── Cardio planifié ce jour-là (généré par le générateur IA) ──
        target_day_name = DAYS_FR[target_date.weekday()]
        cardio_today = [
            c for c in (prog.get("_cardio") or [])
            if isinstance(c, dict) and target_day_name in (c.get("jours") or [])
        ]

        return render_template(
            "seance_choix.html",
            active="seance",
            date_iso=date_iso,
            date_label=label,
            titre=titre,
            subtitle_text=subtitle_text,
            subtitle_color=subtitle_color,
            done_name=done_name,
            seance_names=sorted(prog_seances.keys(), key=_sort_key),
            prog_seances=prog_seances,
            planning=prog.get("_planning", {}),
            jours_map=prog.get("_jours", {}),
            prog_groups=groups,
            makeup_suggestions=makeup_suggestions,
            cardio_today=cardio_today,
        )

    # ── Vue édition : mode prefaite ───────────────────────────────
    if mode == "prefaite":
        if not name or name not in prog_seances:
            return redirect(url_for("seance.seance", date=date_iso))

        exos_prog = list(prog_seances[name])
        # Filtrage équipement : si l'utilisateur n'est pas en profil salle,
        # on substitue les exos qui exigent du matériel qu'il n'a pas. Couvre
        # aussi le cas où l'équipement a changé après la création du programme.
        _equipement = (prog.get("_equipement") or "").strip().lower()
        if _equipement and _equipement != "salle":
            exos_prog = filter_exos_by_equipment(
                exos_prog, prog.get("_equipment_details") or []
            )
        logger.info("seance ordre exos seance=%s exos=%s",
                    name, [e.get("name") for e in exos_prog])
        # Extras : stockés dans prog sous "_extras" par (seance, date) pour partage entre sessions
        extras_key = f"{name}|{date_iso}"
        # Échanges du jour : le programme reste intact, seule la séance
        # d'aujourd'hui voit la variante.
        exos_prog = _appliquer_substituts(prog, extras_key, exos_prog)
        extras = prog.get("_extras", {}).get(extras_key, [])
        all_exos = [(e, False) for e in exos_prog] + [(e, True) for e in extras]

        exos_ctx = _build_all_exo_contexts(hist, all_exos, name, s_act, date_iso,
                                           auto_prefill_weight, show_overload_hint)

        # Reconstruit depuis l'historique les exos faits ce jour-là mais absents
        # de la liste (extras effacés au finish, exo retiré du programme…).
        covered = {_norm(e["exo_final"]) for e in exos_ctx}
        recon = _reconstruct_history_exos(hist, name, s_act, date_iso, covered, len(exos_ctx))
        if recon:
            n_extras = len(extras)
            if n_extras:
                # Les extras live doivent rester le dernier bloc contigu
                # (indexation du formulaire remove-extra).
                exos_ctx = exos_ctx[:-n_extras] + recon + exos_ctx[-n_extras:]
            else:
                exos_ctx = exos_ctx + recon

        # Ordre personnalisé (drag dans la séance en cours)
        exos_ctx = _apply_seance_order(prog, extras_key, exos_ctx)

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
            s_display=s_display,
            week_offset=week_offset,
            exos=exos_ctx,
            exos_done=exos_done,
            exos_total=exos_total,
            unites_cardio=UNITES_CARDIO,
            recup=_recup_status(hist, s_act),
            vol_curr=int(vol_curr),
            vol_prev=int(vol_prev),
            vol_ratio=vol_ratio,
            vol_overload=(vol_curr >= vol_prev and vol_prev > 0),
            all_prog_exos=list(all_prog_exos.values()),
            custom_exercises=prog.get("_custom_exercises", []),
            known_exo_names=_known_exo_names(hist, prog, prog_seances),
            muscle_list=MUSCLE_LIST,
            variants=VARIANTS,
            auto_rest_timer=auto_rest_timer,
            show_rpe=show_rpe,
            cardio_done=_build_cardio_done(hist, name, date_iso),
            session_note=_load_session_note(prog, date_iso, name),
            body_polygons=get_body_polygons(),
        )

    # ── Vue édition : mode libre ──────────────────────────────────
    if mode == "libre":
        libre_name = name or "Séance Libre"
        libre_exos = prog.get("_libre_draft", {}).get(f"{libre_name}|{date_iso}", [])
        all_exos = [(e, False) for e in libre_exos]
        exos_ctx = _build_all_exo_contexts(hist, all_exos, libre_name, s_act, date_iso,
                                           auto_prefill_weight, show_overload_hint)

        # Reconstruit depuis l'historique : le brouillon libre est effacé au
        # finish, donc une séance libre passée n'a plus que son historique.
        covered = {_norm(e["exo_final"]) for e in exos_ctx}
        exos_ctx = exos_ctx + _reconstruct_history_exos(
            hist, libre_name, s_act, date_iso, covered, len(exos_ctx))

        # Ordre personnalisé (drag dans la séance en cours)
        exos_ctx = _apply_seance_order(prog, f"{libre_name}|{date_iso}", exos_ctx)

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
            s_display=s_display,
            week_offset=week_offset,
            exos=exos_ctx,
            exos_done=exos_done,
            exos_total=exos_total,
            unites_cardio=UNITES_CARDIO,
            recup=_recup_status(hist, s_act),
            vol_curr=0, vol_prev=0, vol_ratio=0, vol_overload=False,
            all_prog_exos=list(all_prog_exos.values()),
            custom_exercises=prog.get("_custom_exercises", []),
            known_exo_names=_known_exo_names(hist, prog, prog_seances),
            muscle_list=MUSCLE_LIST,
            variants=VARIANTS,
            auto_rest_timer=auto_rest_timer,
            show_rpe=show_rpe,
            cardio_done=_build_cardio_done(hist, libre_name, date_iso),
            session_note=_load_session_note(prog, date_iso, libre_name),
            body_polygons=get_body_polygons(),
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


@bp.route("/seance/save-exo", methods=["POST"])
@limiter.limit("60 per minute")
def save_exo():
    """Enregistre les séries d'un exercice.

    Deux modes de réponse :
      - JSON (Accept: application/json) → la page met à jour la carte sans
        recharger : record battu, progression, volume. C'est le chemin normal.
      - redirection → repli sans JavaScript (formulaire classique).
    """
    f = request.form
    seance = f["seance_name"]
    exo_base = f["exo_base"]
    variant = f["variant"]
    muscle = f["muscle"]
    date_str = _form_date(f)
    semaine = _iso_week(_parse_date(date_str) or logical_today_paris())
    is_bw = f.get("is_bw") == "1"
    try:
        sets = json.loads(f.get("sets_json", "[]"))
    except json.JSONDecodeError:
        sets = []
    if not isinstance(sets, list):
        sets = []
    # « Série faite » enregistre au fil de l'eau (partiel=1) : seules les
    # séries remplies partent. Sans ça, les séries pas encore faites
    # s'écriraient en SKIP au milieu de l'exercice.
    partiel = f.get("partiel") == "1"
    if partiel:
        sets = [s for s in sets if isinstance(s, dict) and _reps_saisies(s) > 0]

    exo_final = f"{exo_base} ({variant})" if variant != "Standard" else exo_base
    if partiel and not sets:
        # Rien de rempli : on ne touche à rien (surtout pas aux séries déjà
        # en base) — c'est un envoi vide, pas un effacement.
        return jsonify({"ok": True, "completed": False, "pr": None})
    new_rows = _rows_from_sets(sets, semaine=semaine, seance=seance,
                               exo_final=exo_final, muscle=muscle,
                               date_str=date_str, is_bw=is_bw)

    wants_json = "application/json" in (request.headers.get("Accept") or "")
    try:
        hist_before = get_hist() if wants_json else []
        pr = _pr_check(hist_before, new_rows, exo_final, is_bw) if wants_json else None
        replace_exo_rows(date_str, seance, exo_final, new_rows)
        clear_user_cache()
    except Exception as e:
        logger.error("save-exo FAILED seance=%s exo=%s: %s", seance, exo_final, e)
        if wants_json:
            return jsonify({"ok": False,
                            "error": "Enregistrement impossible. Tes séries sont "
                                     "gardées sur l'appareil — réessaie."}), 503
        return render_template(
            "error.html", code=503,
            message="Impossible de sauvegarder la série. Tes données sont conservées — réessaie dans un instant.",
        ), 503

    if not wants_json:
        return _back_to_editor(f)

    hist, _ = _normalize_hist(get_hist(), get_prog())
    totals = _session_totals(hist, seance, date_str)
    completed = _exo_completed(_exo_curr_rows(hist, date_str, seance, exo_final))
    return jsonify({
        "ok": True,
        "completed": completed,
        "pr": pr,
        "volume": totals["volume"],
        "sets_done": totals["sets"],
        "record": _best_record(hist, exo_final, is_bw),
        "suggestion": _suggestion_for(hist, exo_final, seance, date_str, is_bw),
        "last_summary": ", ".join(
            "%gkg × %d" % (r["Poids"], r["Reps"]) for r in new_rows if r["Reps"] > 0
        ),
    })


@bp.route("/seance/skip-exo", methods=["POST"])
@limiter.limit("60 per minute")
def skip_exo():
    f = request.form
    seance = f["seance_name"]
    variant = f["variant"]
    exo_base = f["exo_base"]
    exo_final = f"{exo_base} ({variant})" if variant != "Standard" else exo_base
    date_str = _form_date(f)
    wants_json = "application/json" in (request.headers.get("Accept") or "")
    # Des séries réelles déjà enregistrées ne s'effacent pas sur un doigt qui
    # glisse : « Skip » les remplaçait par une ligne SKIP, sans question.
    if f.get("confirme") != "1":
        deja = [r for r in get_hist()
                if r.get("Date") == date_str and r["Séance"] == seance
                and r["Exercice"] == exo_final and r["Reps"] > 0]
        if deja:
            if wants_json:
                return jsonify({"ok": False, "a_confirmer": True, "series": len(deja)}), 409
            return _back_to_editor(f)
    semaine = _iso_week(_parse_date(date_str) or logical_today_paris())
    new_rows = [{
        "Semaine": semaine, "Séance": seance, "Exercice": exo_final,
        "Série": 1, "Reps": 0, "Poids": 0.0,
        "Remarque": "SKIP", "Muscle": f.get("muscle", "Autre"),
        "Date": date_str,
    }]
    replace_exo_rows(date_str, seance, exo_final, new_rows)
    clear_user_cache()
    if wants_json:
        return jsonify({"ok": True, "completed": True, "skipped": True})
    return _back_to_editor(f)


@bp.route("/seance/reset-exo", methods=["POST"])
@limiter.limit("10 per minute")
def reset_exo():
    f = request.form
    seance = f["seance_name"]
    variant = f["variant"]
    exo_base = f["exo_base"]
    exo_final = f"{exo_base} ({variant})" if variant != "Standard" else exo_base
    delete_exo_rows(_form_date(f), seance, exo_final)
    clear_user_cache()
    return _back_to_editor(f)


@bp.route("/seance/reset-session", methods=["POST"])
@limiter.limit("10 per minute")
def reset_session():
    f = request.form
    delete_session_rows(_form_date(f), f["seance_name"])
    clear_user_cache()
    return _back_to_editor(f)


@bp.route("/seance/mark-missed", methods=["POST"])
@limiter.limit("10 per minute")
def mark_missed():
    f = request.form
    date_str = f["date"]
    target = _parse_date(date_str) or today_paris()
    semaine = _iso_week(target)
    seance_name = f.get("seance_name") or "Séance manquée"
    mark_session_missed(semaine, seance_name, date_str)
    clear_user_cache()
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


@bp.route("/seance/substitute", methods=["POST"])
@limiter.limit("60 per minute")
def substitute_exo():
    """Échange un exercice du programme contre une variante, pour ce jour.

    Le programme n'est pas touché : la semaine prochaine, l'exercice d'origine
    revient. Sans ça, « aujourd'hui je le fais à la poulie » réécrirait le
    programme pour toujours, et il faudrait penser à le remettre.
    """
    f = request.form
    seance_name = f.get("seance_name") or ""
    date_str = f.get("date") or ""
    origine = (f.get("exo_name") or "").strip()
    vers = (f.get("vers") or "").strip()
    if not origine or not seance_name:
        return _back_to_editor(f)

    prog = get_prog()
    key = f"{seance_name}|{date_str}"
    calque = prog.setdefault("_substituts", {})
    du_jour = calque.get(key, {})
    if vers and _norm(vers) != _norm(origine):
        du_jour[_norm(origine)] = vers
    else:
        # Champ vide, ou variante égale à l'original : c'est un retour en
        # arrière. On efface plutôt que d'écrire un échange neutre, sinon le
        # calque se remplit d'entrées qui ne font rien.
        du_jour.pop(_norm(origine), None)
    if du_jour:
        calque[key] = du_jour
    else:
        calque.pop(key, None)

    from core.data import save_prog
    save_prog(prog)
    return _back_to_editor(f)


@bp.route("/seance/remove-extra", methods=["POST"])
def remove_extra():
    f = request.form
    mode = f["mode"]
    seance_name = f["seance_name"]
    date_str = f["date"]
    # Retrait par nom (robuste au réordonnancement) ; index en repli pour
    # compat (anciens formulaires / homonymes éventuels).
    target_name = (f.get("exo_name") or "").strip()
    try:
        idx = int(f.get("index"))
    except (TypeError, ValueError):
        idx = None
    prog = get_prog()
    key = f"{seance_name}|{date_str}"

    def _remove(lst):
        if target_name:
            for i, e in enumerate(lst):
                if _norm(e.get("name") or "") == _norm(target_name):
                    lst.pop(i)
                    return
        if idx is not None and 0 <= idx < len(lst):
            lst.pop(idx)

    if mode == "libre":
        _update_libre_draft(prog, key, _remove)
    else:
        _update_extras(prog, key, _remove)
    from core.data import save_prog
    save_prog(prog)
    return _back_to_editor(f)


@bp.route("/seance/reorder", methods=["POST"])
@limiter.limit("60 per minute")
def reorder_exos():
    """Enregistre l'ordre personnalisé des exos d'une séance (drag dans la
    séance en cours). Ordre purement cosmétique : liste de noms de base."""
    data = request.get_json(silent=True) or {}
    seance_name = (data.get("seance_name") or "").strip()
    date_str = (data.get("date") or "").strip()
    order = data.get("order")
    if not seance_name or not isinstance(order, list):
        return {"ok": False}, 400
    order = [str(n).strip() for n in order if str(n).strip()][:200]
    prog = get_prog()
    key = f"{seance_name}|{date_str}"
    store = prog.setdefault("_seance_order", {})
    if order:
        store[key] = order
    else:
        store.pop(key, None)
    from core.data import save_prog
    save_prog(prog)
    return {"ok": True}


@bp.route("/seance/add-cardio", methods=["POST"])
@limiter.limit("20 per minute")
def add_cardio():
    """Ajoute un bloc cardio à la séance muscu en cours (même Séance + Date)."""
    from routes.cardio import ACTIVITES_MAP, RPE_LABELS, _estimate_calories, _adjust_met_for_incline
    from core.data import get_profile
    f = request.form
    target = _parse_date(f.get("date")) or today_paris()
    date_str = target.strftime("%Y-%m-%d")
    semaine = _iso_week(target)
    seance_name = f["seance_name"]

    activite = (f.get("activite") or "Autre").strip()
    if activite not in ACTIVITES_MAP:
        activite = "Autre"
    _icon, met = ACTIVITES_MAP[activite]

    try:
        duree_min = max(0, int(float(f.get("duree_min") or 0)))
    except ValueError:
        duree_min = 0
    try:
        distance_val = max(0.0, float((f.get("distance_km") or "0").replace(",", ".")))
    except ValueError:
        distance_val = 0.0
    try:
        vitesse = max(0.0, float((f.get("vitesse") or "0").replace(",", ".")))
    except ValueError:
        vitesse = 0.0
    # Deux valeurs sur trois suffisent. La vitesse était calculée dans le
    # formulaire mais seulement AFFICHÉE en suggestion : elle n'arrivait
    # jamais jusqu'ici. Et le sens inverse manquait — le tapis affiche
    # 10 km/h pendant 30 min, c'est la distance qu'on ignore.
    distance_val, vitesse = completer_mesures(activite, duree_min, distance_val, vitesse)
    try:
        cal_saisie = int(float(f.get("calories") or 0))
    except ValueError:
        cal_saisie = 0
    rpe = (f.get("rpe") or "").strip()
    if rpe not in RPE_LABELS:
        rpe = ""
    note = (f.get("note") or "").strip()[:80]

    try:
        incline_pct = max(0, min(30, float(f.get("incline") or 0)))
    except (ValueError, TypeError):
        incline_pct = 0
    met = _adjust_met_for_incline(met, activite, incline_pct)

    if cal_saisie > 0:
        calories = cal_saisie
    else:
        profile = get_profile() or {}
        poids_kg = float(profile.get("poids_kg") or 0)
        calories = _estimate_calories(met, duree_min, poids_kg) if duree_min > 0 else 0

    parts = []
    if calories > 0: parts.append(f"Cal:{calories}")
    if incline_pct > 0: parts.append(f"Incl:{incline_pct:g}%")
    if vitesse > 0: parts.append(f"Vit:{vitesse:g}")
    if rpe: parts.append(f"RPE:{rpe}")
    if note: parts.append(note)
    remarque = " | ".join(parts)

    exo_final = f"CARDIO:{activite}"
    rows = [{
        "Semaine": semaine,
        "Séance": seance_name,
        "Exercice": exo_final,
        "Série": 1,
        "Reps": duree_min,
        "Poids": distance_val,
        "Remarque": remarque,
        "Muscle": "Cardio",
        "Date": date_str,
    }]
    # AJOUTER, pas remplacer : 10 min de rameur en échauffement puis 8 min en
    # finisher sont deux blocs. `replace_exo_rows` ne gardait que le second.
    try:
        append_exo_rows(date_str, seance_name, exo_final, rows)
        clear_user_cache()
    except Exception as e:
        logger.error("add-cardio FAILED: %s", e)
        # L'échec était avalé puis la page revenait comme si de rien n'était.
        return render_template(
            "error.html", code=503,
            message="Le cardio n'a pas pu être enregistré. Réessaie dans un instant.",
        ), 503
    return _back_to_editor(f)


@bp.route("/seance/delete-cardio", methods=["POST"])
@limiter.limit("20 per minute")
def delete_cardio():
    from core.data import delete_exo_rows
    f = request.form
    seance_name = f["seance_name"]
    activite = (f.get("activite") or "").strip()
    if not activite:
        return _back_to_editor(f)
    try:
        serie = int(f["serie"]) if (f.get("serie") or "").isdigit() else None
    except ValueError:
        serie = None
    try:
        delete_exo_rows(_form_date(f), seance_name, f"CARDIO:{activite}", serie)
        clear_user_cache()
    except Exception as e:
        logger.error("delete-cardio FAILED: %s", e)
    return _back_to_editor(f)


@bp.route("/seance/finish", methods=["POST"])
def finish():
    """Termine la séance : enregistre le bilan (note /5 + commentaire, tous deux
    facultatifs — le bouton « Passer » n'envoie rien), nettoie le brouillon libre
    ou les extras, et retourne à l'accueil."""
    f = request.form
    mode = f["mode"]
    seance_name = f["seance_name"]
    date_str = _form_date(f)
    key = f"{seance_name}|{date_str}"
    prog = get_prog()
    changed = False
    if mode == "libre" and "_libre_draft" in prog and key in prog["_libre_draft"]:
        prog["_libre_draft"].pop(key, None)
        changed = True
    if mode == "prefaite" and "_extras" in prog and key in prog["_extras"]:
        prog["_extras"].pop(key, None)
        changed = True
    # Comme les extras : le calque d'échanges ne concerne que la séance du
    # jour. Le garder ferait grossir le blob programme d'une entrée par
    # séance, à vie — et il est relu et réécrit à chaque interaction.
    if "_substituts" in prog and key in prog["_substituts"]:
        prog["_substituts"].pop(key, None)
        changed = True
    # Même règle, et c'est le calque qui y échappait : l'ordre des cartes
    # était écrit et jamais effacé. Les cartes d'une séance terminée sont de
    # toute façon reconstruites depuis l'historique, dans l'ordre où les
    # séries ont été saisies : l'ordre gardé ne servait plus à rien.
    if "_seance_order" in prog and key in prog["_seance_order"]:
        prog["_seance_order"].pop(key, None)
        changed = True
    # Rattrapage : les quatre lignes ci-dessus ne nettoient que la séance
    # qu'on vient de TERMINER. Une séance ouverte puis abandonnée ne passe
    # jamais par ici et garde son calque à vie — mesuré en production, des
    # entrées d'avril et de juin traînaient encore fin septembre.
    if purger_les_calques(prog):
        changed = True

    duration = _session_duration_min(f)
    note = _parse_session_note(f)
    if duration:
        note = note or {"ts": now_paris().strftime("%Y-%m-%d %H:%M")}
        note["duration_min"] = duration
    if note:
        _save_session_note(prog, date_str, seance_name, note)
        if prog.get("_session_notes") is not None:
            changed = True

    if changed:
        from core.data import save_prog
        save_prog(prog)
        clear_user_cache()
    # L'accueil (écran suivant) propose le debrief de CETTE séance.
    session["last_workout"] = {"seance": seance_name, "date": date_str}
    track("workout_finished", {
        "mode": mode, "seance": seance_name,
        "rating": note.get("rating", 0) if note else 0,
        "has_comment": bool(note and note.get("comment")),
        "duration_min": duration,
    })
    return redirect(url_for("accueil.index"))


def _save_session_note(prog, date_str, seance_name, note):
    """Écrit le bilan dans la table `session_notes` (migration v34). Repli sur
    l'ancien stockage dans le programme si la table n'existe pas encore."""
    from core.data import upsert_session_note
    try:
        upsert_session_note(date_str, seance_name, note.get("rating"),
                            note.get("comment"), note.get("duration_min"))
        # La table a pris le relais : on purge l'ancien emplacement.
        if isinstance(prog.get("_session_notes"), dict):
            prog["_session_notes"].pop(f"{seance_name}|{date_str}", None)
            if not prog["_session_notes"]:
                prog.pop("_session_notes", None)
        return
    except Exception as e:
        logger.warning("session_notes indisponible (%s) — repli sur le programme", e)
    _purge_old_session_notes(prog)
    prog.setdefault("_session_notes", {})[f"{seance_name}|{date_str}"] = note


def _load_session_note(prog, date_str, seance_name):
    """Bilan d'une séance : table v34 d'abord, ancien stockage ensuite."""
    from core.data import get_session_note
    try:
        note = get_session_note(date_str, seance_name)
        if note:
            return note
    except Exception:
        pass
    return (prog.get("_session_notes") or {}).get(f"{seance_name}|{date_str}")


# ── Debrief de fin de séance ────────────────────────────────────
# Le coach est une page qu'il faut penser à ouvrir. Ce debrief va au-devant,
# au seul moment où l'attention est garantie : l'écran qui suit la séance.
# PRO complet ; un aperçu gratuit par semaine sert de démonstration honnête
# (on montre le produit réel, pas une capture).
FREE_DEBRIEFS_PER_WEEK = 1


def _debrief_allowed(prog) -> tuple[bool, str]:
    """(autorisé, raison). La raison sert à l'UI : « PRO » ou « quota »."""
    if getattr(g, "is_vip_full", False):
        return True, "vip"
    from core.dates import continuous_week
    week = continuous_week(logical_today_paris())
    used = (prog.get("_debrief_free") or {}).get(str(week), 0)
    if used < FREE_DEBRIEFS_PER_WEEK:
        return True, "free_trial"
    return False, "quota"


@bp.route("/seance/debrief", methods=["POST"])
@limiter.limit("10 per hour")
def debrief():
    """Trois phrases sur la séance qui vient d'être terminée."""
    from core import debrief as core_debrief
    from core.db import _env

    data = request.get_json(silent=True) or {}
    seance = str(data.get("seance") or "").strip()
    date_str = _form_date({"date": data.get("date")})
    if not seance:
        return jsonify({"ok": False, "error": "séance manquante"}), 400

    prog = get_prog()
    allowed, reason = _debrief_allowed(prog)
    if not allowed:
        return jsonify({"ok": False, "locked": True,
                        "message": "Le debrief après séance fait partie de PRO."}), 200

    hist, _ = _normalize_hist(get_hist(), prog)
    facts = core_debrief.collect_facts(
        hist, seance, date_str, _load_session_note(prog, date_str, seance))
    if not facts:
        return jsonify({"ok": False, "error": "aucune série enregistrée"}), 200

    text = core_debrief.generate(_env("ANTHROPIC_API_KEY"), facts)
    if not text:
        return jsonify({"ok": False, "error": "indisponible"}), 200

    # Consomme l'aperçu gratuit seulement si la génération a abouti.
    if reason == "free_trial":
        from core.dates import continuous_week
        week = str(continuous_week(logical_today_paris()))
        store = prog.setdefault("_debrief_free", {})
        store[week] = int(store.get(week, 0)) + 1
        # Fenêtre glissante : on ne garde que les 4 dernières semaines.
        for k in sorted(store)[:-4]:
            store.pop(k, None)
        from core.data import save_prog
        save_prog(prog)

    track("debrief_generated", {"seance": seance, "tier": reason})
    return jsonify({"ok": True, "text": text, "trial": reason == "free_trial",
                    "volume": facts["volume"], "records": len(facts["records"])})


@bp.route("/seance/api/variant-history", methods=["POST"])
def api_variant_history():
    """Retourne l'historique (last_sets, record, prev_weeks) pour un exo+variante."""
    data = request.get_json(silent=True) or {}
    exo_base = data.get("exo_base", "")
    variant = data.get("variant", "Standard")
    seance = data.get("seance", "")
    s_act = int(data.get("s_act", 0))
    week_offset = int(data.get("week_offset", 0))
    # La date de la séance consultée : « dernière fois » et suggestion se
    # calculent par rapport à elle, pas à la semaine. Repli sur aujourd'hui
    # pour un client servi depuis un cache antérieur à ce champ.
    date_str = _form_date({"date": data.get("date")})

    hist = get_hist()
    prog = get_prog()
    hist, _ = _normalize_hist(hist, prog)

    exo_final = f"{exo_base} ({variant})" if variant != "Standard" else exo_base
    is_bw = exo_base in BW_EXOS and variant != "Lesté"

    last_sets = _last_session_sets(hist, exo_final, seance, date_str)
    record = _best_record(hist, exo_final, is_bw)
    prev_weeks = _previous_weeks_data(hist, exo_final, seance, s_act, n_weeks=2)
    suggestion = None
    if prog.get("_settings", {}).get("show_overload_hint", True) and not detect_isometric(exo_base)[0]:
        suggestion = _suggestion_for(hist, exo_final, seance, date_str, is_bw)

    last_summary = ""
    if last_sets:
        last_summary = ", ".join(f"{s['poids']:g}kg × {s['reps']}" for s in last_sets)

    pw_display = []
    for pw in prev_weeks:
        rows_out = []
        for r in pw.get("rows", []):
            rows_out.append({
                "serie": r.get("Série", 0),
                "reps": r.get("Reps", 0),
                "poids": float(r.get("Poids", 0)),
                "remarque": r.get("Remarque", ""),
                "rpe": r.get("RPE"),
            })
        pw_display.append({
            "week": pw["week"] - week_offset,
            "missed": pw.get("missed", False),
            "rows": rows_out,
        })

    return jsonify({
        "last_sets": last_sets,
        "last_summary": last_summary,
        "record": record,
        "prev_weeks": pw_display,
        "suggestion": suggestion,
    })
