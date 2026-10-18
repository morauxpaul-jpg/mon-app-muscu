"""La carte « Poids corporel » de l'onglet Corps : dernière pesée, variation
sur 30 jours, min / max, et la courbe des 90 derniers jours.

Sortie de routes/progres.py le 18/10/2026, quand le poids a rejoint les
photos dans l'onglet « Corps » (demande du propriétaire : « voir les deux
sous les yeux au même endroit »). Calculs inchangés.
"""
from datetime import date, timedelta

from core.dates import today_paris

WEIGHT_CHART_DAYS = 90


def _jour(s):
    try:
        return date.fromisoformat(str(s))
    except Exception:
        return None


def delta_class(delta, goal):
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


def short_date(iso):
    d = _jour(iso)
    return f"{d.day:02d}/{d.month:02d}" if d else iso


def carte_poids(entries, today=None, goal=""):
    """Contexte de la carte : dernière pesée, variation sur 30 jours, min/max
    de la période, et polyline SVG des 90 derniers jours.
    `entries` = [{date, poids_kg}] triés par date croissante. None si vide."""
    entries = [e for e in (entries or []) if e.get("poids_kg", 0) > 0 and e.get("date")]
    if not entries:
        return None
    today = today or today_paris()
    current = entries[-1]
    cur_date = _jour(current["date"]) or today

    # Variation vs la pesée la plus proche d'il y a 30 jours (≥ 30 j avant)
    ref_date = cur_date - timedelta(days=30)
    older = [e for e in entries if (_jour(e["date"]) or today) <= ref_date]
    delta_30 = round(current["poids_kg"] - older[-1]["poids_kg"], 1) if older else None

    cutoff = (today - timedelta(days=WEIGHT_CHART_DAYS)).isoformat()
    window = [e for e in entries if e["date"] >= cutoff] or entries[-1:]
    values = [e["poids_kg"] for e in window]
    vmin, vmax = min(values), max(values)

    # Polyline : x proportionnel à la date (les trous restent visibles),
    # y entre min-0,5 et max+0,5 kg pour ne pas écraser la courbe.
    W, H, PAD_X, PAD_T, PAD_B = 600, 160, 12, 18, 24
    d0 = _jour(window[0]["date"]) or today
    d1 = _jour(window[-1]["date"]) or today
    span = max(1, (d1 - d0).days)
    lo, hi = vmin - 0.5, vmax + 0.5
    points = []
    for e in window:
        d = _jour(e["date"]) or today
        x = PAD_X + (W - 2 * PAD_X) * ((d - d0).days / span) if len(window) > 1 else W / 2
        y = PAD_T + (H - PAD_T - PAD_B) * (1 - (e["poids_kg"] - lo) / (hi - lo))
        points.append({"x": round(x, 1), "y": round(y, 1), "kg": e["poids_kg"], "date": e["date"]})

    return {
        "current": current["poids_kg"],
        "current_date": current["date"],
        "delta_30": delta_30,
        "delta_class": delta_class(delta_30, goal),
        "min": vmin, "max": vmax,
        "count": len(entries),
        "points": points,
        "polyline": " ".join(f"{p['x']},{p['y']}" for p in points),
        "chart_w": W, "chart_h": H,
        "first_label": short_date(window[0]["date"]),
        "last_label": short_date(window[-1]["date"]),
        "recent": list(reversed(entries[-7:])),
    }
