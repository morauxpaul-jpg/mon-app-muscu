"""Blueprint progrès — carte du corps, hall of fame, calendrier, volume, poids.

Le suivi détaillé d'un mouvement vit sur sa propre page (/progres/exercice).

Logique portée depuis app.py body_map_section (863-1299) et tab_st (2681-2713).
"""
import calendar
import logging
from datetime import date, timedelta

from flask import Blueprint, render_template, request, g, redirect, url_for

from core.data import (
    get_hist, get_prog, get_onboarding, get_profile, save_profile,
    list_body_weight, upsert_body_weight, delete_body_weight,
)
from core.dates import today_paris, today_paris_str, DAYS_FR
from core.limiter import limiter
from core.muscu import calc_1rm, get_base_name, fix_muscle, get_rep_table
from core.body_map import get_body_polygons
from core import strength, exercise_stats
from core.exercises_data import get_exercise_info
from core.hist import is_cardio, is_muscu_perf, is_perf, tonnage

logger = logging.getLogger(__name__)

bp = Blueprint("progres", __name__)

# Zones SVG de la carte du corps. Le 1RM de référence (« std ») n'est plus une
# constante : il dépend du poids de corps et du sexe (cf. core/strength.py).
MUSCLES = {
    "Pecs":            {"zid_f": "z-pecs",    "zid_b": None},
    "Dos":             {"zid_f": None,        "zid_b": "z-dos"},
    "Trapèzes":        {"zid_f": None,        "zid_b": "z-trapezes"},
    "Épaules":         {"zid_f": "z-epaules", "zid_b": "z-epaules-b"},
    "Biceps":          {"zid_f": "z-biceps",  "zid_b": None},
    "Triceps":         {"zid_f": None,        "zid_b": "z-triceps"},
    "Avant-bras":      {"zid_f": "z-avbras",  "zid_b": "z-avbras-b"},
    "Abdos":           {"zid_f": "z-abdos",   "zid_b": None},
    "Quadriceps":      {"zid_f": "z-quad",    "zid_b": None},
    "Ischio-jambiers": {"zid_f": None,        "zid_b": "z-ischio"},
    "Fessiers":        {"zid_f": None,        "zid_b": "z-fessiers"},
    "Adducteurs":      {"zid_f": "z-adducteurs", "zid_b": None},
    "Abducteurs":      {"zid_f": "z-abducteurs", "zid_b": None},
    "Mollets":         {"zid_f": "z-mollets", "zid_b": "z-mollets-b"},
}
FILTER_MUSCLES = list(MUSCLES.keys())

MAKEUP_WINDOW_DAYS = 3  # même tolérance que l'accueil (routes/accueil.py)


def _was_made_up(planned, d, today, planning_map, done_dates_by_seance, window=MAKEUP_WINDOW_DAYS):
    """True si la séance `planned` planifiée le jour `d` (passé, non faite ce
    jour-là) a été rattrapée dans les `window` jours suivants — sur un jour qui
    n'est pas lui-même planifié pour cette même séance. Réplique la logique de
    routes/accueil.py:_day_status pour cohérence accueil ↔ calendrier."""
    for off in range(1, window + 1):
        d2 = d + timedelta(days=off)
        if d2 > today:
            break
        d2_name_fr = DAYS_FR[d2.weekday()]
        if planning_map.get(d2_name_fr) == planned:
            continue  # jour où la même séance est re-planifiée → pas un rattrapage
        if planned in done_dates_by_seance.get(d2.isoformat(), set()):
            return True
    return False


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


def _build_muscle_data(df_p, start_monday=None, poids_kg=None, sexe=None):
    out = {}
    stds = strength.standards(poids_kg, sexe)
    for m, info in MUSCLES.items():
        md = _muscle_rows(df_p, m)
        md_valid = [r for r in md if r["Reps"] > 0]

        std = stds.get(m) or 0
        rm_max = max((r["1RM"] for r in md_valid), default=0)
        pct = min((rm_max / std) * 100, 150) if std > 0 else 0

        best_w, best_r = 0, 0
        last_sessions, top_exos, evo = [], [], []

        if md_valid:
            best = max(md_valid, key=lambda r: r["1RM"])
            best_w = float(best["Poids"])
            best_r = int(best["Reps"])

            # 4 dernières semaines (PR hebdo = set avec le plus gros poids).
            # Semaine RELATIVE au début du programme (S1, S2, …), dérivée de
            # la date — cohérent avec le graphique de volume. Les lignes sans
            # date (archive) gardent les records mais sortent du découpage hebdo.
            by_week = {}
            for r in md_valid:
                w = _rel_week(r.get("Date"), start_monday)
                if w is None:
                    continue
                by_week.setdefault(w, []).append(r)
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
            "std": std,
            "level": strength.level_for(pct) if rm_max > 0 else "",
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
        "biggest_distance": round(biggest_distance, 2),
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


# ── Poids corporel ─────────────────────────────────────────────────────
WEIGHT_CHART_DAYS = 90


def _delta_class(delta, goal):
    """Couleur de la variation selon l'objectif nutrition : en prise de masse
    prendre du poids est positif, en sèche c'est l'inverse ; en maintien (ou
    sans objectif) on reste neutre."""
    if not delta:
        return ""
    if goal == "masse":
        return "weight-good" if delta > 0 else "weight-bad"
    if goal == "seche":
        return "weight-good" if delta < 0 else "weight-bad"
    return ""


def _build_weight_stats(entries, today=None, goal=""):
    """Contexte de la carte « Poids corporel » : dernière pesée, variation sur
    30 jours, min/max de la période, et polyline SVG des 90 derniers jours.
    `entries` = [{date, poids_kg}] triés par date croissante. None si vide."""
    entries = [e for e in (entries or []) if e.get("poids_kg", 0) > 0 and e.get("date")]
    if not entries:
        return None
    today = today or today_paris()
    current = entries[-1]
    cur_date = _parse_iso_date(current["date"]) or today

    # Variation vs la pesée la plus proche d'il y a 30 jours (≥ 30 j avant)
    ref_date = cur_date - timedelta(days=30)
    older = [e for e in entries if (_parse_iso_date(e["date"]) or today) <= ref_date]
    delta_30 = round(current["poids_kg"] - older[-1]["poids_kg"], 1) if older else None

    cutoff = (today - timedelta(days=WEIGHT_CHART_DAYS)).isoformat()
    window = [e for e in entries if e["date"] >= cutoff] or entries[-1:]
    values = [e["poids_kg"] for e in window]
    vmin, vmax = min(values), max(values)

    # Polyline : x proportionnel à la date (les trous restent visibles),
    # y entre min-0,5 et max+0,5 kg pour ne pas écraser la courbe.
    W, H, PAD_X, PAD_T, PAD_B = 600, 160, 12, 18, 24
    d0 = _parse_iso_date(window[0]["date"]) or today
    d1 = _parse_iso_date(window[-1]["date"]) or today
    span = max(1, (d1 - d0).days)
    lo, hi = vmin - 0.5, vmax + 0.5
    points = []
    for e in window:
        d = _parse_iso_date(e["date"]) or today
        x = PAD_X + (W - 2 * PAD_X) * ((d - d0).days / span) if len(window) > 1 else W / 2
        y = PAD_T + (H - PAD_T - PAD_B) * (1 - (e["poids_kg"] - lo) / (hi - lo))
        points.append({"x": round(x, 1), "y": round(y, 1), "kg": e["poids_kg"], "date": e["date"]})

    return {
        "current": current["poids_kg"],
        "current_date": current["date"],
        "delta_30": delta_30,
        "delta_class": _delta_class(delta_30, goal),
        "min": vmin, "max": vmax,
        "count": len(entries),
        "points": points,
        "polyline": " ".join(f"{p['x']},{p['y']}" for p in points),
        "chart_w": W, "chart_h": H,
        "first_label": _short_date(window[0]["date"]),
        "last_label": _short_date(window[-1]["date"]),
        "recent": list(reversed(entries[-7:])),
    }


def _short_date(iso):
    d = _parse_iso_date(iso)
    return f"{d.day:02d}/{d.month:02d}" if d else iso


def _sync_profile_weight():
    """Recopie la dernière pesée dans profiles.poids_kg et recalcule le TDEE /
    la cible calorique (nutrition) pour qu'ils suivent le poids réel."""
    entries = list_body_weight(limit=1)
    if not entries:
        return
    latest = entries[-1]["poids_kg"]
    profile = get_profile() or {}
    if abs(float(profile.get("poids_kg") or 0) - latest) < 0.05:
        return
    fields = {"poids_kg": latest}
    try:
        from routes.nutrition import _compute_targets, _custom_cal
        merged = {**profile, "poids_kg": latest}
        targets = _compute_targets(merged, _custom_cal(get_prog()))
        if targets:
            fields["tdee"] = targets["tdee"]
            fields["calories_cible"] = targets["calories_cible"]
    except Exception as e:  # le poids doit être sauvé même si le calcul échoue
        logger.error("sync_profile_weight targets FAILED: %s", e)
    save_profile(fields)


@bp.route("/progres/poids", methods=["POST"])
@limiter.limit("20 per minute")
def log_weight():
    """Enregistre une pesée (date + kg). Une pesée par jour : re-saisir le
    même jour remplace la valeur."""
    f = request.form
    try:
        kg = float(str(f.get("poids_kg") or "").replace(",", "."))
    except ValueError:
        kg = 0
    date_str = (f.get("date") or "").strip()[:10]
    if _parse_iso_date(date_str) is None or date_str > today_paris_str():
        date_str = today_paris_str()
    if 20 <= kg < 500:
        try:
            upsert_body_weight(date_str, kg)
            _sync_profile_weight()
        except Exception as e:
            logger.error("log_weight FAILED: %s", e)
    return redirect(url_for("progres.progres") + "#poids")


@bp.route("/progres/poids/delete", methods=["POST"])
@limiter.limit("20 per minute")
def delete_weight():
    date_str = (request.form.get("date") or "").strip()[:10]
    if _parse_iso_date(date_str) is not None:
        try:
            delete_body_weight(date_str)
            _sync_profile_weight()
        except Exception as e:
            logger.error("delete_weight FAILED: %s", e)
    return redirect(url_for("progres.progres") + "#poids")


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

    is_vip = bool(getattr(g, "is_vip", False))

    # ── Poids corporel (gratuit) ──────────────────────────────
    profile = get_profile() or {}
    try:
        body_kg = float(profile.get("poids_kg") or 0)
    except (TypeError, ValueError):
        body_kg = 0.0
    # Sexe : sert aux standards de force relatifs (cf. core/strength.py).
    user_sexe = (get_onboarding() or {}).get("sexe") or profile.get("sexe") or ""

    try:
        goal = profile.get("objectif_nutrition") or ""
        weight = _build_weight_stats(list_body_weight(), goal=goal)
    except Exception as e:  # table absente (migration v33 non appliquée) → carte vide
        logger.error("progres list_body_weight FAILED: %s", e)
        weight = None

    # ── Carte du corps — période sélectionnée ────────────────
    bm_period = request.args.get("bm_period", "7")
    try:
        bm_days = int(bm_period)
    except ValueError:
        bm_days = 7
    if bm_days not in (7, 30, 90):
        bm_days = 7
    # Stats avancées (body map + hall of fame + 1RM) : VIP only.
    # Pour les non-VIP on ne calcule rien — le template affiche un aperçu verrouillé.
    if is_vip:
        volume_map = _build_volume_map(hist, period_days=bm_days)
        muscle_data = _build_muscle_data(df_p, start_monday,
                                         poids_kg=body_kg, sexe=user_sexe)
        svg_ctx = _build_svg_context(muscle_data, volume_map)
    else:
        volume_map = {}
        muscle_data = {}
        svg_ctx = {}

    # ── Hall of Fame : top 3 par 1RM (filtré par muscles) ───────
    selected_muscles = request.args.getlist("m") or FILTER_MUSCLES
    if is_vip:
        filtered = [r for r in df_p if any(m in (r.get("Muscle") or "") for m in selected_muscles)]
        by_exo = {}
        for r in filtered:
            cur = by_exo.get(r["Exercice"], 0)
            if r["1RM"] > cur:
                by_exo[r["Exercice"]] = r["1RM"]
        podium = sorted(by_exo.items(), key=lambda kv: kv[1], reverse=True)[:3]
    else:
        podium = []

    # ── Accès aux fiches exercice ───────────────────────────────
    all_exos = sorted({r["Exercice"] for r in df_p})
    sel_exo = request.args.get("exo") or (all_exos[0] if all_exos else None)

    # Raccourcis vers les mouvements les plus travaillés (nb de séances
    # distinctes) : c'est ce qu'on veut suivre, et ça évite de chercher dans
    # une liste déroulante de 40 entrées.
    _by_base = {}
    for r in df_p:
        b = get_base_name(r.get("Exercice") or "")
        if not b or not r.get("Date"):
            continue
        _by_base.setdefault(b, set()).add(r["Date"])
    top_exos = [{"name": b, "sessions": len(d)}
                for b, d in sorted(_by_base.items(), key=lambda kv: -len(kv[1]))[:6]]

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
    # Année hors plage raisonnable (ex: ?cy=99999) → retour au mois courant
    if not (2000 <= cal_year <= 2100):
        cal_year, cal_month = today.year, today.month

    _prog_for_cal = get_prog() or {}
    planning_map = _prog_for_cal.get("_planning", {})
    # Date plancher : ne jamais marquer « manquée » une journée antérieure
    # à la création du compte / au démarrage du programme. Couvre le cas
    # de l'onboarding en fin de semaine (vendredi/samedi) où Lundi/Mercredi
    # apparaissaient à tort comme manqués.
    floor_date = None
    try:
        from datetime import datetime as _dt
        started = _prog_for_cal.get("_started_at")
        if started:
            floor_date = _dt.fromisoformat(str(started)[:10]).date()
        else:
            onb = get_onboarding() or {}
            completed = onb.get("completed_at")
            if completed:
                floor_date = _dt.fromisoformat(str(completed)[:10]).date()
    except (ValueError, TypeError):
        floor_date = None
    hist_dates_done = set()
    hist_dates_missed = set()
    done_dates_by_seance = {}  # date_iso -> set(noms de séances faites) pour le rattrapage
    for r in hist:
        d = r.get("Date", "")
        if not d:
            continue
        if r["Exercice"] == "SESSION" and "MANQUÉE" in (r.get("Remarque") or ""):
            hist_dates_missed.add(d)
        elif r["Poids"] > 0 or r["Reps"] > 0:
            hist_dates_done.add(d)
            sn = r.get("Séance") or ""
            if sn:
                done_dates_by_seance.setdefault(d, set()).add(sn)
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
        elif floor_date and d < floor_date:
            # Avant la création du compte : pas de "manquée".
            status = "rest"
        elif is_training_day:
            # Rattrapage : la séance planifiée a-t-elle été faite dans les
            # jours suivants ? Si oui → neutre "makeup" (gris), comptée comme
            # faite (pas pénalisant), au lieu de "missed" (rouge).
            planned = planning_map.get(day_name_fr, "")
            if planned and _was_made_up(planned, d, today, planning_map, done_dates_by_seance):
                status = "makeup"
                done_count += 1
            else:
                status = "missed"
        else:
            status = "rest"

        if is_training_day and not (floor_date and d < floor_date):
            planned_count += 1

        cal_days.append({
            "day": day_num,
            "weekday": d.weekday(),
            "status": status,
            "is_today": d == today,
            "date_iso": d_str,
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
        std_relative=strength.is_relative(body_kg),
        body_kg=body_kg,
        display_muscles=list(MUSCLES.keys()),
        filter_muscles=FILTER_MUSCLES,
        selected_muscles=selected_muscles,
        podium=podium,
        all_exos=all_exos,
        sel_exo=sel_exo,
        top_exos=top_exos,
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
        weight=weight,
        today_iso=today_paris_str(),
    )


# ────────────────────────────────────────────────────────────────
# Fiche exercice — toute l'histoire d'un mouvement
# ────────────────────────────────────────────────────────────────
# Gratuite volontairement : c'est la base que Hevy et Strong offrent sans
# payer, et sans elle quelqu'un qui migre depuis ces apps perd son outil de
# travail principal. Le PRO se justifie ailleurs (coach, nutrition, body map).

_METRICS = [
    ("e1rm", "Force estimée", "kg"),
    ("best_weight", "Charge max", "kg"),
    ("volume", "Volume", "kg"),
    ("reps", "Répétitions", "reps"),
]


@bp.route("/progres/exercice")
def exercice():
    """Fiche d'un exercice : records, courbe, et toutes les séances faites."""
    name = (request.args.get("exo") or "").strip()
    if not name:
        return redirect(url_for("progres.progres") + "#zoom")

    try:
        hist = get_hist()
        prog = get_prog()
    except Exception as e:
        logger.error("exercice() DB failed: %s", e)
        return render_template(
            "error.html", code=503,
            message="Impossible de charger cet exercice. Vérifie ta connexion.",
        ), 503
    hist = _normalize(hist, prog)

    # Regroupe les variantes du même mouvement par défaut : un « Développé
    # couché » fait tantôt à la barre tantôt aux haltères reste le même
    # mouvement à suivre. Un onglet permet d'isoler une variante.
    variant = (request.args.get("variante") or "").strip()
    by_base = not variant
    sessions = exercise_stats.sessions_for(hist, variant or name, by_base=by_base)
    if not sessions:
        sessions = exercise_stats.sessions_for(hist, name, by_base=True)

    metric = (request.args.get("m") or "e1rm").strip()
    if metric not in {k for k, _l, _u in _METRICS}:
        metric = "e1rm"

    points = exercise_stats.series(sessions, metric)
    base = get_base_name(name)
    summ = exercise_stats.summary(sessions)
    is_vip = bool(getattr(g, "is_vip", False))
    return render_template(
        "exercice.html",
        active="progres",
        exo_name=base,
        variant=variant,
        variants=exercise_stats.variants_of(hist, base),
        sessions=sessions[:60],
        summary=summ,
        is_vip_stats=is_vip,
        chart=exercise_stats.sparkline(points),
        metric=metric,
        metrics=_METRICS,
        metric_unit=next((u for k, _l, u in _METRICS if k == metric), ""),
        info=get_exercise_info(base),
        # Table des maxima : réservée PRO (elle l'était déjà dans Progrès).
        rep_table=get_rep_table(summ.get("best_e1rm", 0)) if is_vip else None,
    )
