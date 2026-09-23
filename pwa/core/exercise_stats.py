"""Statistiques par exercice — le cœur de la fiche « un exercice, toute son
histoire ».

Jusqu'ici, Progrès ne proposait qu'un « zoom » : le poids MAXIMAL par semaine.
C'est la stat la moins informative du lot — elle ignore le volume, le nombre
de reps, et ne dit pas si on progresse quand on passe de 3×8 à 4×10 à charge
égale. Hevy et Strong donnent gratuitement l'historique complet, le 1RM estimé
et le volume par séance ; c'est le minimum attendu par quelqu'un qui migre.

Tout est calculé à la lecture depuis l'historique normalisé (aucun stockage).
"""
from core.hist import is_muscu_perf
from core.muscu import calc_1rm, get_base_name


def _norm(s) -> str:
    return (s or "").strip().casefold()


def variants_of(hist, base_name: str) -> list[str]:
    """Variantes réellement utilisées pour ce mouvement (« Squat »,
    « Squat (Barre) »…), les plus récentes d'abord."""
    nb = _norm(base_name)
    seen, out = set(), []
    for r in reversed(hist):
        exo = (r.get("Exercice") or "").strip()
        if not exo or not is_muscu_perf(r):
            continue
        if _norm(get_base_name(exo)) != nb:
            continue
        if _norm(exo) not in seen:
            seen.add(_norm(exo))
            out.append(exo)
    return out


def sessions_for(hist, exercice: str, *, by_base: bool = False) -> list[dict]:
    """Une entrée par séance où cet exercice a été fait, la plus récente
    d'abord :

        {date, seance, sets:[{serie, reps, poids, rpe}], volume, best_set,
         e1rm, reps_total}

    `by_base=True` regroupe toutes les variantes du même mouvement (utile
    quand l'utilisateur alterne barre et haltères).
    """
    target = _norm(exercice)
    rows = []
    for r in hist:
        exo = r.get("Exercice") or ""
        key = _norm(get_base_name(exo)) if by_base else _norm(exo)
        if key != (_norm(get_base_name(exercice)) if by_base else target):
            continue
        if not is_muscu_perf(r) or not r.get("Date"):
            continue
        rows.append(r)

    by_session: dict = {}
    for r in rows:
        key = (r["Date"], r.get("Séance") or "")
        by_session.setdefault(key, []).append(r)

    out = []
    for (date_str, seance), sets in sorted(by_session.items(), reverse=True):
        sets = sorted(sets, key=lambda r: int(r.get("Série") or 0))
        detail = [{
            "serie": int(s.get("Série") or 0),
            "reps": int(s.get("Reps") or 0),
            "poids": float(s.get("Poids") or 0),
            "rpe": s.get("RPE"),
            "exercice": s.get("Exercice") or "",
        } for s in sets]
        volume = int(sum(d["reps"] * d["poids"] for d in detail))
        best = max(detail, key=lambda d: (d["poids"], d["reps"]))
        e1rm = max(calc_1rm(d["poids"], d["reps"]) for d in detail)
        out.append({
            "date": date_str,
            "seance": seance,
            "sets": detail,
            "volume": volume,
            "reps_total": sum(d["reps"] for d in detail),
            "best_set": best,
            "e1rm": round(e1rm, 1),
        })
    return out


def summary(sessions: list[dict]) -> dict:
    """Chiffres d'en-tête : records, totaux, et progression sur la période."""
    if not sessions:
        return {}
    best = max(sessions, key=lambda s: (s["best_set"]["poids"], s["best_set"]["reps"]))
    best_e1rm = max(sessions, key=lambda s: s["e1rm"])
    best_vol = max(sessions, key=lambda s: s["volume"])
    first, last = sessions[-1], sessions[0]
    # Progression = e1RM de la dernière séance vs la première enregistrée.
    delta_pct = None
    if first["e1rm"] > 0 and len(sessions) > 1:
        delta_pct = round((last["e1rm"] - first["e1rm"]) / first["e1rm"] * 100)
    return {
        "sessions": len(sessions),
        "sets_total": sum(len(s["sets"]) for s in sessions),
        "reps_total": sum(s["reps_total"] for s in sessions),
        "volume_total": sum(s["volume"] for s in sessions),
        "best_weight": best["best_set"]["poids"],
        "best_weight_reps": best["best_set"]["reps"],
        "best_weight_date": best["date"],
        "best_e1rm": best_e1rm["e1rm"],
        "best_e1rm_date": best_e1rm["date"],
        "best_volume": best_vol["volume"],
        "best_volume_date": best_vol["date"],
        "first_date": first["date"],
        "last_date": last["date"],
        "delta_pct": delta_pct,
    }


def series(sessions: list[dict], metric: str = "e1rm", limit: int = 20) -> list[dict]:
    """Points du graphique, du plus ancien au plus récent :
    [{date, value}]. `metric` ∈ {e1rm, volume, best_weight, reps}."""
    picker = {
        "e1rm": lambda s: s["e1rm"],
        "volume": lambda s: s["volume"],
        "best_weight": lambda s: s["best_set"]["poids"],
        "reps": lambda s: s["reps_total"],
    }.get(metric, lambda s: s["e1rm"])
    recent = list(reversed(sessions[:limit]))
    return [{"date": s["date"], "value": round(picker(s), 1)} for s in recent]


def sparkline(points: list[dict], width: int = 600, height: int = 160) -> dict:
    """Polyline SVG pour un graphique simple, sans dépendance externe.

    L'app chargeait Plotly (~3,5 Mo) pour tracer une ligne de 8 points ; sur
    mobile c'est plusieurs secondes de données pour rien. Ici, quelques
    coordonnées suffisent — mêmes conventions que la courbe de poids.
    """
    if not points:
        return {}
    values = [p["value"] for p in points]
    lo, hi = min(values), max(values)
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    pad_x, pad_t, pad_b = 10, 14, 20
    inner_w = width - 2 * pad_x
    inner_h = height - pad_t - pad_b
    n = len(points)
    coords = []
    for i, p in enumerate(points):
        x = pad_x + (inner_w * (i / (n - 1)) if n > 1 else inner_w / 2)
        y = pad_t + inner_h * (1 - (p["value"] - lo) / (hi - lo))
        coords.append({"x": round(x, 1), "y": round(y, 1),
                       "value": p["value"], "date": p["date"]})
    return {
        "points": coords,
        "polyline": " ".join(f"{c['x']},{c['y']}" for c in coords),
        "area": (f"{coords[0]['x']},{height - pad_b} "
                 + " ".join(f"{c['x']},{c['y']}" for c in coords)
                 + f" {coords[-1]['x']},{height - pad_b}"),
        "min": lo, "max": hi,
        "width": width, "height": height,
        "last": coords[-1],
    }
