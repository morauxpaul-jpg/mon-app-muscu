"""Blueprint progrès — carte du corps + hall of fame + zoom mouvement.

Logique portée depuis app.py body_map_section (863-1299) et tab_st (2681-2713).
"""
from flask import Blueprint, render_template, request

from core.data import get_hist, get_prog
from core.muscu import calc_1rm, get_base_name, fix_muscle, get_rep_estimations

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


def _build_svg_context(muscle_data):
    """Prépare le dict {muscle: {fill_f, fill_b, opacity}} passé à la template SVG."""
    svg = {}
    for m, d in muscle_data.items():
        active = d["pct"] > 0
        svg[m] = {
            "fill_f": f"url(#gf{_sid(m)})" if active else "#1a2a3a",
            "fill_b": f"url(#gb{_sid(m)})" if active else "#1a2a3a",
            "opacity": "0.92" if active else "0.12",
            "col": d["col"],
            "active": active,
            "sid": _sid(m),
        }
    return svg


@bp.route("/progres")
def progres():
    hist = get_hist()
    prog = get_prog()
    hist = _normalize(hist, prog)

    # df_p = perfs réelles (Reps > 0), avec 1RM calculé
    df_p = [r for r in hist if r["Reps"] > 0]
    for r in df_p:
        r["1RM"] = calc_1rm(r["Poids"], r["Reps"])

    muscle_data = _build_muscle_data(df_p)
    svg_ctx = _build_svg_context(muscle_data)

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
        if df_e:
            best = max(df_e, key=lambda r: (r["Poids"], r["Reps"]))
            one_rm = calc_1rm(best["Poids"], best["Reps"])
            # Évolution par semaine : max poids par semaine
            by_week = {}
            for r in df_e:
                w = int(r["Semaine"])
                if r["Poids"] > by_week.get(w, -1):
                    by_week[w] = r["Poids"]
            weeks = sorted(by_week.keys())
            chart_x = weeks
            chart_y = [by_week[w] for w in weeks]
            # Table historique triée semaine desc
            table = sorted(df_e, key=lambda r: (-int(r["Semaine"]), -r["Poids"]))
            zoom = {
                "exo": sel_exo,
                "best_w": best["Poids"],
                "best_r": int(best["Reps"]),
                "one_rm": round(one_rm, 1),
                "rep_ests": get_rep_estimations(one_rm),
                "chart_x": chart_x,
                "chart_y": chart_y,
                "table": table,
            }

    return render_template(
        "progres.html",
        active="progres",
        muscle_data=muscle_data,
        svg_ctx=svg_ctx,
        display_muscles=list(MUSCLES.keys()),
        filter_muscles=FILTER_MUSCLES,
        selected_muscles=selected_muscles,
        podium=podium,
        all_exos=all_exos,
        sel_exo=sel_exo,
        zoom=zoom,
        has_data=bool(df_p),
    )
