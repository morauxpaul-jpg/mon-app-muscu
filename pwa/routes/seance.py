"""Blueprint séance — choix, saisie (prefaite ou libre), skip/save/miss/reset.

Logique portée depuis app.py lignes 1555-1722 (choix_seance) et 2048-2676 (ma séance).
"""
import json
import logging
from datetime import timedelta
from flask import Blueprint, render_template, request, redirect, url_for, abort, jsonify

logger = logging.getLogger(__name__)

from core.data import (
    get_hist, get_prog, clear_user_cache,
    replace_exo_rows, delete_exo_rows, delete_session_rows, echauffements_du_jour,
    echauffements_disponibles,
)
from core.dates import (today_paris_str, logical_today_paris, DAYS_FR, MONTHS_FR)
from core.limiter import limiter
from core.rotation import planning_semaine, seance_prevue
from core.muscu import BW_EXOS, MUSCLE_LIST, VARIANTS, auto_muscles
from core.exercises_data import filter_exos_by_equipment, detect_isometric
from core.exercice_ids import pour_serie
from core.body_map import get_body_polygons
from core.hist import est_echauffement, is_logged as _is_real_perf

# Le calcul de la séance vit dans core/ : ce fichier n'est plus que la couche
# HTTP — les routes, le formulaire, le rendu. Les six modules ci-dessous ne
# touchent ni à Flask ni à la base : on leur passe l'historique et le
# programme, ils rendent des dictionnaires. Cf. CONTEXT.md et
# tests/test_couche_seance.py.
from core.seance_semaine import (_date_label, _display_week, _find_done_session,
                                 _iso_week, _normalize_hist, _parse_date)
from core.seance_historique import (_best_record, _exo_completed, _exo_curr_rows,
                                    _last_session_sets, _norm, _previous_weeks_data,
                                    _suggestion_for, _cible_du_programme)
from core.seance_contexte import (_build_all_exo_contexts, _reconstruct_history_exos)
from core.seance_calques import (_appliquer_substituts, _apply_seance_order,
                                 _update_extras, _update_libre_draft)
from core.seance_saisie import (_form_date, _known_exo_names, _pr_check,
                                _reps_saisies, _rows_from_sets, _session_totals)
from core.seance_cardio import (UNITES_CARDIO, _build_cardio_done)
from core.bilans_seance import _load_session_note
from core.navigation_seance import _back_to_editor

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

        # Regroupe les séances par programme pour un affichage clair.
        programmes = prog.get("_programmes") or []
        seance_prog = prog.get("_seance_prog") or {}
        active_programmes = programmes
        prog_by_id = {p["id"]: p["name"] for p in active_programmes if isinstance(p, dict) and p.get("id")}
        # La semaine affichée, rotation comprise : le Full Body B prévu ce
        # lundi passe devant le A.
        _planning = planning_semaine(prog, target_date)
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
        # Séances orphelines (rattachées à aucun programme).
        unclassified = [s for s in seance_order if not seance_prog.get(s) or seance_prog.get(s) not in prog_by_id]
        if unclassified:
            label_uncl = "Non classé" if groups else "Mes séances"
            groups.append({"name": label_uncl, "seances": unclassified})

        # ── Séance de rattrapage : uniquement la séance de la VEILLE si
        # elle était planifiée, pas faite, et pas marquée comme manquée.
        # (Choix produit : au-delà d'un jour, on n'incite plus à rattraper.)
        makeup_suggestions = []
        if date_iso == logical_today_str:
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
                planned = seance_prevue(prog, d)
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
                    if seance_prevue(prog, d2) == planned:
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
            planning=_planning,
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

        from core.decharge import semaine_allegee
        echauff = echauffements_du_jour(date_iso)
        exos_ctx = _build_all_exo_contexts(hist, all_exos, name, s_act, date_iso,
                                           auto_prefill_weight, show_overload_hint,
                                           decharge=semaine_allegee(prog, s_act),
                                           echauffements=echauff)

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
        # Soulevé à l'échauffement : affiché à part, hors volume de travail.
        vol_echauff = sum(r["Poids"] * r["Reps"] for r in echauff if r["Séance"] == name)

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
            vol_curr=int(vol_curr),
            vol_echauff=int(vol_echauff),
            vol_prev=int(vol_prev),
            vol_ratio=vol_ratio,
            vol_overload=(vol_curr >= vol_prev and vol_prev > 0),
            all_prog_exos=list(all_prog_exos.values()),
            custom_exercises=prog.get("_custom_exercises", []),
            known_exo_names=_known_exo_names(hist, prog, prog_seances),
            muscle_list=MUSCLE_LIST,
            variants=VARIANTS,
            auto_rest_timer=auto_rest_timer,
            show_rpe=show_rpe, echauffements_ok=echauffements_disponibles(),
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
                                           auto_prefill_weight, show_overload_hint,
                                           echauffements=echauffements_du_jour(date_iso))

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
            vol_curr=0, vol_prev=0, vol_ratio=0, vol_overload=False,
            all_prog_exos=list(all_prog_exos.values()),
            custom_exercises=prog.get("_custom_exercises", []),
            known_exo_names=_known_exo_names(hist, prog, prog_seances),
            muscle_list=MUSCLE_LIST,
            variants=VARIANTS,
            auto_rest_timer=auto_rest_timer,
            show_rpe=show_rpe, echauffements_ok=echauffements_disponibles(),
            cardio_done=_build_cardio_done(hist, libre_name, date_iso),
            session_note=_load_session_note(prog, date_iso, libre_name),
            body_polygons=get_body_polygons(),
        )

    abort(404)


# ────────────────────────────────────────────────────────────────
# Actions POST (form-based, PRG pattern)
# ────────────────────────────────────────────────────────────────


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
    # Identifiant stable de l'exercice (core/exercice_ids.py) : la série reste
    # rattachée à l'exercice même s'il est renommé plus tard.
    exo_id = pour_serie(f.get("exo_id"), variant)
    for r in new_rows:
        r["ExoId"] = exo_id

    wants_json = "application/json" in (request.headers.get("Accept") or "")
    try:
        hist_before = get_hist() if wants_json else []
        travail = [r for r in new_rows if not est_echauffement(r)]
        pr = _pr_check(hist_before, travail, exo_final, is_bw) if wants_json else None
        # Pas de clear_user_cache() : replace_exo_rows corrige l'historique en
        # cache avec ce qu'il vient d'écrire. Le vider forçait à relire tout
        # l'historique (et le programme) juste en dessous (audit I15).
        replace_exo_rows(date_str, seance, exo_final, new_rows, exo_id)
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
        "volume_echauffement": int(sum(r["Poids"] * r["Reps"] for r in echauffements_du_jour(date_str)
                                       if r["Séance"] == seance)),
        "sets_done": totals["sets"],
        "record": _best_record(hist, exo_final, is_bw),
        "suggestion": _suggestion_for(hist, exo_final, seance, date_str, is_bw,
                                      _cible_du_programme(get_prog(), seance, exo_base)),
        "last_summary": ", ".join(
            "%gkg × %d" % (r["Poids"], r["Reps"]) for r in travail if r["Reps"] > 0
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
        "Date": date_str, "ExoId": pour_serie(f.get("exo_id"), variant),
    }]
    replace_exo_rows(date_str, seance, exo_final, new_rows, new_rows[0]["ExoId"])
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
    delete_exo_rows(_form_date(f), seance, exo_final, exo_id=pour_serie(f.get("exo_id"), variant))
    clear_user_cache()
    return _back_to_editor(f)


@bp.route("/seance/reset-session", methods=["POST"])
@limiter.limit("10 per minute")
def reset_session():
    f = request.form
    delete_session_rows(_form_date(f), f["seance_name"])
    clear_user_cache()
    return _back_to_editor(f)


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
        suggestion = _suggestion_for(hist, exo_final, seance, date_str, is_bw,
                                     _cible_du_programme(prog, seance, exo_base))

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
