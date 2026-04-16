"""Blueprint progrès — carte du corps + hall of fame + zoom mouvement + calendrier + volume.

Logique portée depuis app.py body_map_section (863-1299) et tab_st (2681-2713).
"""
import calendar
import logging
from datetime import date, timedelta

from flask import Blueprint, render_template, request

from core.data import get_hist, get_prog
from core.dates import today_paris, DAYS_FR
from core.muscu import calc_1rm, get_base_name, fix_muscle, get_rep_estimations, get_rep_table
from core.body_map import get_body_polygons

logger = logging.getLogger(__name__)

bp = Blueprint("progres", __name__)

MUSCLES = {
    "Pecs":            {"std": 140, "zid_f": "z-pecs",    "zid_b": None},
    "Dos":             {"std": 160, "zid_f": None,        "zid_b": "z-dos"},
    "Épaules":         {"std": 90,  "zid_f": "z-epaules", "zid_b": "z-epaules-b"},
    "Biceps":          {"std": 60,  "zid_f": "z-biceps",  "zid_b": None},
    "Triceps":         {"std": 70,  "zid_f": None,        "zid_b": "z-triceps"},
    "Avant-bras":      {"std": 45,  "zid_f": "z-avbras",  "zid_b": "z-avbras-b"},
    "Abdos":           {"std": 60,  "zid_f": "z-abdos",   "zid_b": None},
    "Quadriceps":      {"std": 180, "zid_f": "z-quad",    "zid_b": None},
    "Ischio-jambiers": {"std": 110, "zid_f": None,        "zid_b": "z-ischio"},
    "Fessiers":        {"std": 140, "zid_f": None,        "zid_b": "z-fessiers"},
    "Adducteurs":      {"std": 80,  "zid_f": "z-adducteurs", "zid_b": None},
    "Abducteurs":      {"std": 80,  "zid_f": "z-abducteurs", "zid_b": None},
    "Mollets":         {"std": 110, "zid_f": "z-mollets", "zid_b": "z-mollets-b"},
}
FILTER_MUSCLES = list(MUSCLES.keys())


def _get_col(pct):
    if pct == 0:
        return "#1a2a3a"
    if pct < 40:
        return "#FF453A"
    if pct < 70:
        return "#FF9F0A"
    if pct < 95:
        return "#58CCFF"
    return "#00FF7F"


def _get_volume_col(vol_pct):
    """Couleur par volume relatif (pourcentage du total de la période)."""
    if vol_pct == 0:
        return "#555555"       # gris — non travaillé
    if vol_pct <= 20:
        return "#7EC8E3"       # bleu clair
    if vol_pct <= 50:
        return "#3B82F6"       # bleu moyen
    if vol_pct <= 80:
        return "#2563EB"       # bleu vif
    return "#00FFFF"           # cyan néon — dominant


def _sid(m):
    out = m.lower()
    for a, b in [("é","e"),("è","e"),("ê","e"),("à","a"),("â","a"),("î","i"),("-",""),(" ","")]:
        out = out.replace(a, b)
    return out


def _normalize(hist, prog):
    prog_seances = {k: v for k, v in prog.items() if not k.startswith("_")}
    muscle_mapping = {ex["name"]: ex.get("muscle", "Autre")
                      for s in prog_seances for ex in prog_seances[s]}
    for r in hist:
        base = get_base_name(r["Exercice"])
        if base in muscle_mapping:
            r["Muscle"] = muscle_mapping[base]
        r["Muscle"] = fix_muscle(r["Exercice"], r["Muscle"])
    # Ajoute l'archive si présente
    archive = prog.get("_archive", [])
    for a in archive:
        try:
            a_reps = int(float(a.get("Reps", 0) or 0))
            a_poids = float(a.get("Poids", 0) or 0)
            a_sem = int(float(a.get("Semaine", 0) or 0))
        except (ValueError, TypeError):
            continue
        if a_reps <= 0:
            continue
        base = get_base_name(str(a.get("Exercice", "")))
        muscle = muscle_mapping.get(base, a.get("Muscle", "")) or ""
        muscle = fix_muscle(a.get("Exercice", ""), muscle)
        hist.append({
            "Semaine": a_sem, "Séance": "", "Exercice": str(a.get("Exercice", "")),
            "Série": 0, "Reps": a_reps, "Poids": a_poids,
            "Remarque": "", "Muscle": muscle, "Date": "",
        })
    return hist


def _muscle_rows(df, m):
    return [r for r in df if m in (r.get("Muscle") or "")]


def _build_muscle_data(df_p):
    out = {}
    for m, info in MUSCLES.items():
        md = _muscle_rows(df_p, m)
        md_valid = [r for r in md if r["Reps"] > 0]

        rm_max = max((r["1RM"] for r in md_valid), default=0)
        pct = min((rm_max / info["std"]) * 100, 120) if info["std"] > 0 else 0

        best_w, best_r = 0, 0
        last_sessions, top_exos, evo = [], [], []

        if md_valid:
            best = max(md_valid, key=lambda r: r["1RM"])
            best_w = float(best["Poids"])
            best_r = int(best["Reps"])

            # 4 dernières semaines (PR hebdo = set avec le plus gros poids)
            by_week = {}
            for r in md_valid:
                by_week.setdefault(r["Semaine"], []).append(r)
            for wk in sorted(by_week.keys(), reverse=True)[:4]:
                wk_rows = by_week[wk]
                br = max(wk_rows, key=lambda r: r["Poids"])
                last_sessions.append({"s": int(wk), "w": float(br["Poids"]), "r": int(br["Reps"])})

            # Top 4 exos par 1RM
            by_exo = {}
            for r in md_valid:
                by_exo.setdefault(r["Exercice"], []).append(r)
            exos_tmp = []
            for name, grp in by_exo.items():
                br = max(grp, key=lambda r: r["1RM"])
                exos_tmp.append({"name": str(name), "w": float(br["Poids"]), "r": int(br["Reps"])})
            top_exos = sorted(exos_tmp, key=lambda e: e["w"] * (1 + e["r"] / 30), reverse=True)[:4]

            # Évolution 1RM par semaine
            for wk in sorted(by_week.keys()):
                best_rm = max(r["1RM"] for r in by_week[wk])
                evo.append({"w": int(wk), "r": round(float(best_rm), 1)})

        out[m] = {
            "pct": round(pct, 1),
            "col": _get_col(pct),
            "rm": round(rm_max, 1),
            "std": info["std"],
            "zid_f": info["zid_f"],
            "zid_b": info["zid_b"],
            "best": {"w": best_w, "r": best_r},
            "last": last_sessions,
            "exos": top_exos,
            "evo": evo,
        }
    return out


def _parse_iso_date(s):
    try:
        return date.fromisoformat(str(s))
    except Exception:
        return None


def _compute_start_monday(rows, prog=None):
    """Lundi de la semaine de début du programme.
    Utilise _started_at du programme si dispo, sinon 1ère séance trackée."""
    if prog:
        started = prog.get("_started_at")
        if started:
            d = _parse_iso_date(started)
            if d:
                return d - timedelta(days=d.weekday())
    dates = [_parse_iso_date(r.get("Date")) for r in rows]
    dates = [d for d in dates if d is not None]
    if not dates:
        return None
    first = min(dates)
    return first - timedelta(days=first.weekday())


def _rel_week(date_str, start_monday):
    """Indice de semaine 1-based relatif à start_monday. None si parse échoue."""
    d = _parse_iso_date(date_str)
    if d is None or start_monday is None:
        return None
    d_monday = d - timedelta(days=d.weekday())
    return (d_monday - start_monday).days // 7 + 1


def _build_cardio_stats(cardio_rows, start_monday):
    """Stats cardio : totaux, records, volume par semaine, répartition par type."""
    if not cardio_rows:
        return None

    from routes.cardio import sum_cardio_km, KM_BASED_ACTIVITES
    total_min = sum(int(r.get("Reps") or 0) for r in cardio_rows)
    total_km = sum_cardio_km(cardio_rows)
    sessions = len(cardio_rows)

    # Minutes par semaine (8 dernières), indexée relatif à la 1ère séance.
    by_week = {}
    for r in cardio_rows:
        w = _rel_week(r.get("Date"), start_monday)
        if w is None:
            continue
        by_week[w] = by_week.get(w, 0) + int(r.get("Reps") or 0)
    weeks_sorted = sorted(by_week.keys())[-8:]
    labels = [f"S{w}" for w in weeks_sorted]
    values = [by_week[w] for w in weeks_sorted]
    max_val = max(values) if values else 1

    # Records
    def _activity(r):
        exo = str(r.get("Exercice") or "")
        return exo.split(":", 1)[1] if ":" in exo else "Autre"

    # Plus longue course
    course_rows = [r for r in cardio_rows if _activity(r) == "Course"]
    longest_run_min = max((int(r.get("Reps") or 0) for r in course_rows), default=0)
    km_rows = [r for r in cardio_rows if _activity(r) in KM_BASED_ACTIVITES]
    biggest_distance = max((float(r.get("Poids") or 0) for r in km_rows), default=0.0)
    longest_session_min = max((int(r.get("Reps") or 0) for r in cardio_rows), default=0)

    # Répartition par type (minutes)
    by_type = {}
    for r in cardio_rows:
        a = _activity(r)
        by_type[a] = by_type.get(a, 0) + int(r.get("Reps") or 0)
    repartition = sorted(by_type.items(), key=lambda kv: -kv[1])

    return {
        "total_min": total_min,
        "total_km": total_km,
        "sessions": sessions,
        "labels": labels,
        "values": values,
        "max_val": max_val,
        "longest_run_min": longest_run_min,
        "biggest_distance": round(biggest_distance, 1),
        "longest_session_min": longest_session_min,
        "repartition": repartition,
    }


def _build_volume_map(hist, period_days=7):
    """Calcule le volume (total séries) par muscle pour une période donnée.
    Retourne {muscle: {sets, vol_pct, color, last_date}} pour la carte du corps."""
    today = today_paris()
    cutoff = (today - timedelta(days=period_days)).isoformat()

    period_rows = [r for r in hist
                   if r.get("Date", "") >= cutoff
                   and r["Reps"] > 0 and r["Exercice"] != "SESSION"]

    # Comptage séries par muscle
    muscle_sets = {}
    muscle_last = {}
    for r in period_rows:
        for m in MUSCLES:
            if m in (r.get("Muscle") or ""):
                muscle_sets[m] = muscle_sets.get(m, 0) + 1
                d = r.get("Date", "")
                if d > muscle_last.get(m, ""):
                    muscle_last[m] = d

    total_sets = sum(muscle_sets.values()) or 1
    result = {}
    for m in MUSCLES:
        sets = muscle_sets.get(m, 0)
        vol_pct = round(sets / total_sets * 100, 1) if sets > 0 else 0
        result[m] = {
            "sets": sets,
            "vol_pct": vol_pct,
            "color": _get_volume_col(vol_pct),
            "last_date": muscle_last.get(m, ""),
        }
    return result


def _build_svg_context(muscle_data, volume_map=None):
    """Prépare le dict {muscle: {fill_f, fill_b, opacity}} passé à la template SVG.
    Si volume_map est fourni, utilise les couleurs basées sur le volume."""
    svg = {}
    for m, d in muscle_data.items():
        if volume_map and m in volume_map:
            vm = volume_map[m]
            active = vm["sets"] > 0
            col = vm["color"]
        else:
            active = d["pct"] > 0
            col = d["col"]
        svg[m] = {
            "fill_f": f"url(#gf{_sid(m)})" if active else "#1a2a3a",
            "fill_b": f"url(#gb{_sid(m)})" if active else "#1a2a3a",
            "opacity": "0.92" if active else "0.12",
            "col": col,
            "active": active,
            "sid": _sid(m),
        }
    return svg


@bp.route("/progres")
def progres():
    try:
        hist = get_hist()
        prog = get_prog()
    except Exception as e:
        logger.error("progres() DB failed: %s", e)
        return render_template(
            "error.html", code=503,
            message="Impossible de charger ta progression. Vérifie ta connexion.",
        ), 503
    hist = _normalize(hist, prog)

    # ── Cardio — statistiques dédiées avant filtrage ──
    cardio_rows = [r for r in hist if str(r.get("Exercice") or "").startswith("CARDIO:")]
    # start_monday : lundi de la semaine de la toute 1ère séance (muscu + cardio)
    # pour numéroter S1, S2, … relatif à quand le user a commencé à tracker.
    start_monday = _compute_start_monday(hist, prog)
    cardio = _build_cardio_stats(cardio_rows, start_monday)

    # Exclure le cardio des stats muscu (sinon il fausse les 1RM, le filtre muscle, etc.)
    hist = [r for r in hist if not str(r.get("Exercice") or "").startswith("CARDIO:")]

    # df_p = perfs réelles (Reps > 0), avec 1RM calculé
    df_p = [r for r in hist if r["Reps"] > 0]
    for r in df_p:
        r["1RM"] = calc_1rm(r["Poids"], r["Reps"])

    # ── Carte du corps — période sélectionnée ────────────────
    bm_period = request.args.get("bm_period", "7")
    try:
        bm_days = int(bm_period)
    except ValueError:
        bm_days = 7
    if bm_days not in (7, 30, 90):
        bm_days = 7
    volume_map = _build_volume_map(hist, period_days=bm_days)

    muscle_data = _build_muscle_data(df_p)
    svg_ctx = _build_svg_context(muscle_data, volume_map)

    # ── Hall of Fame : top 3 par 1RM (filtré par muscles) ───────
    selected_muscles = request.args.getlist("m") or FILTER_MUSCLES
    filtered = [r for r in df_p if any(m in (r.get("Muscle") or "") for m in selected_muscles)]
    by_exo = {}
    for r in filtered:
        cur = by_exo.get(r["Exercice"], 0)
        if r["1RM"] > cur:
            by_exo[r["Exercice"]] = r["1RM"]
    podium = sorted(by_exo.items(), key=lambda kv: kv[1], reverse=True)[:3]

    # ── Zoom mouvement ──────────────────────────────────────────
    all_exos = sorted({r["Exercice"] for r in df_p})
    sel_exo = request.args.get("exo") or (all_exos[0] if all_exos else None)

    zoom = None
    if sel_exo:
        df_e = [r for r in df_p if r["Exercice"] == sel_exo]
        # Enrichit chaque ligne avec son rel_week (S1/S2/…) — utilisé partout
        # en dessous. _rel_week peut renvoyer None si Date manquante → on
        # met 0 par défaut pour garder la ligne visible mais en dernier.
        for r in df_e:
            r["_rw"] = _rel_week(r.get("Date"), start_monday) or 0
        if df_e:
            best = max(df_e, key=lambda r: (r["Poids"], r["Reps"]))
            one_rm = calc_1rm(best["Poids"], best["Reps"])
            # Évolution par semaine : max poids par semaine relative
            by_week = {}
            for r in df_e:
                w = r["_rw"]
                if r["Poids"] > by_week.get(w, -1):
                    by_week[w] = r["Poids"]
            weeks = sorted(by_week.keys())
            chart_x = [f"S{w}" for w in weeks]
            chart_y = [by_week[w] for w in weeks]

            # ── Table historique : filtre par semaine (défaut = dernière) ──
            avail_weeks = sorted({r["_rw"] for r in df_e}, reverse=True)
            try:
                sel_week = int(request.args.get("w") or 0) or avail_weeks[0]
            except (ValueError, TypeError, IndexError):
                sel_week = avail_weeks[0] if avail_weeks else 0
            table = [r for r in df_e if r["_rw"] == sel_week]
            table = sorted(table, key=lambda r: (-r["Poids"], -int(r.get("Série") or 0)))

            zoom = {
                "exo": sel_exo,
                "best_w": best["Poids"],
                "best_r": int(best["Reps"]),
                "one_rm": round(one_rm, 1),
                "rep_ests": get_rep_estimations(one_rm),
                "rep_table": get_rep_table(one_rm),
                "chart_x": chart_x,
                "chart_y": chart_y,
                "table": table,
                "avail_weeks": avail_weeks,
                "sel_week": sel_week,
                "total_sets": len(df_e),
            }

    # ── Calendrier mensuel ──────────────────────────────────
    today = today_paris()
    try:
        cal_year = int(request.args.get("cy", today.year))
        cal_month = int(request.args.get("cm", today.month))
    except (ValueError, TypeError):
        cal_year, cal_month = today.year, today.month
    # Clamp
    if cal_month < 1:
        cal_month, cal_year = 12, cal_year - 1
    elif cal_month > 12:
        cal_month, cal_year = 1, cal_year + 1

    planning_map = get_prog().get("_planning", {})
    hist_dates_done = set()
    hist_dates_missed = set()
    for r in hist:
        d = r.get("Date", "")
        if not d:
            continue
        if r["Exercice"] == "SESSION" and "MANQUÉE" in (r.get("Remarque") or ""):
            hist_dates_missed.add(d)
        elif r["Poids"] > 0 or r["Reps"] > 0:
            hist_dates_done.add(d)
    # Les séances cardio (stockées hors de `hist` désormais) comptent aussi
    # comme des jours "done" dans le calendrier.
    for r in cardio_rows:
        d = r.get("Date", "")
        if d and int(r.get("Reps") or 0) > 0:
            hist_dates_done.add(d)

    cal_weeks = []
    first_day, days_in_month = calendar.monthrange(cal_year, cal_month)
    # first_day: 0=Monday. We want Mon-Sun grid.
    cal_days = []
    planned_count = 0
    done_count = 0
    for day_num in range(1, days_in_month + 1):
        d = date(cal_year, cal_month, day_num)
        d_str = d.isoformat()
        day_name_fr = DAYS_FR[d.weekday()]
        is_training_day = bool(planning_map.get(day_name_fr, ""))

        if d_str in hist_dates_done:
            status = "done"
            if is_training_day:
                done_count += 1
        elif d_str in hist_dates_missed:
            status = "missed"
        elif d > today:
            status = "upcoming" if is_training_day else "rest"
        elif is_training_day:
            status = "missed"
        else:
            status = "rest"

        if is_training_day:
            planned_count += 1

        cal_days.append({
            "day": day_num,
            "weekday": d.weekday(),
            "status": status,
            "is_today": d == today,
        })

    # Build weeks (Mon=0 to Sun=6)
    week_row = [None] * 7
    for cd in cal_days:
        wd = cd["weekday"]
        week_row[wd] = cd
        if wd == 6:
            cal_weeks.append(week_row)
            week_row = [None] * 7
    if any(c is not None for c in week_row):
        cal_weeks.append(week_row)

    cal_rate = round(done_count / planned_count * 100) if planned_count > 0 else 0
    MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                 "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    prev_m, prev_y = (cal_month - 1, cal_year) if cal_month > 1 else (12, cal_year - 1)
    next_m, next_y = (cal_month + 1, cal_year) if cal_month < 12 else (1, cal_year + 1)

    # ── Volume par semaine (8 dernières) ─────────────────────
    # Indexé relatif à la 1ère séance (S1, S2, …) — pas ISO week.
    vol_by_week = {}
    for r in hist:
        if r["Poids"] > 0 and r["Reps"] > 0:
            w = _rel_week(r.get("Date"), start_monday)
            if w is None:
                continue
            vol_by_week[w] = vol_by_week.get(w, 0) + int(r["Poids"] * r["Reps"])
    vol_weeks_sorted = sorted(vol_by_week.keys())[-8:]
    vol_labels = [f"S{w}" for w in vol_weeks_sorted]
    vol_values = [vol_by_week[w] for w in vol_weeks_sorted]
    vol_max = max(vol_values) if vol_values else 1

    return render_template(
        "progres.html",
        active="progres",
        muscle_data=muscle_data,
        svg_ctx=svg_ctx,
        body_polygons=get_body_polygons(),
        volume_map=volume_map,
        bm_days=bm_days,
        display_muscles=list(MUSCLES.keys()),
        filter_muscles=FILTER_MUSCLES,
        selected_muscles=selected_muscles,
        podium=podium,
        all_exos=all_exos,
        sel_exo=sel_exo,
        zoom=zoom,
        has_data=bool(df_p),
        cal_weeks=cal_weeks,
        cal_month_name=MONTHS_FR[cal_month - 1],
        cal_year=cal_year,
        cal_month=cal_month,
        cal_rate=cal_rate,
        prev_m=prev_m, prev_y=prev_y,
        next_m=next_m, next_y=next_y,
        vol_labels=vol_labels,
        vol_values=vol_values,
        vol_max=vol_max,
        cardio=cardio,
    )
