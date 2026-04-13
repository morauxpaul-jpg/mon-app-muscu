"""Blueprint accueil — dashboard, planning hebdo, cadres des jours cliquables.

Logique portée depuis app.py (lignes 1499-1865).
"""
from datetime import timedelta
from flask import Blueprint, render_template

from datetime import date as _date, datetime as _datetime

from core.data import get_hist, get_prog, get_profile, get_onboarding
from core.dates import now_paris, today_paris, monday_of, DAYS_FR, MONTHS_FR
from core.muscu import get_base_name, fix_muscle

bp = Blueprint("accueil", __name__)


def _normalize_hist(rows, prog):
    """Applique le mapping muscle via le programme + fix_muscle, comme app.py ligne 1466-1468."""
    prog_seances = {k: v for k, v in prog.items() if not k.startswith("_")}
    muscle_mapping = {ex["name"]: ex.get("muscle", "Autre")
                      for s in prog_seances for ex in prog_seances[s]}
    for r in rows:
        base = get_base_name(r["Exercice"])
        mapped = muscle_mapping.get(base)
        if mapped:
            r["Muscle"] = mapped
        r["Muscle"] = fix_muscle(r["Exercice"], r["Muscle"])
    return rows, prog_seances


def _is_real_perf(row):
    """Réplique du filtre app.py 1757-1761 : une ligne 'réelle' (perf enregistrée ou SKIP)."""
    if row["Exercice"] == "SESSION":
        return False
    if row["Poids"] > 0 or row["Reps"] > 0:
        return True
    if "SKIP" in (row.get("Remarque") or ""):
        return True
    return False


def _day_status(day_date, hist_rows, planning_map, today, joined_date=None):
    """Statut d'une journée — porté de _day_status() app.py 1751-1784."""
    d_str = day_date.strftime("%Y-%m-%d")
    day_rows = [r for r in hist_rows if r["Date"] == d_str]
    day_name_fr = DAYS_FR[day_date.weekday()]
    is_rest = day_name_fr in planning_map and not planning_map.get(day_name_fr, "")

    real = [r for r in day_rows if _is_real_perf(r)]
    if real:
        # Séance majoritaire = celle avec le plus d'exos distincts
        counts = {}
        for r in real:
            counts.setdefault(r["Séance"], set()).add(r["Exercice"])
        top = max(counts.items(), key=lambda kv: len(kv[1]))[0]
        return {"status": "done", "title": str(top), "badge": "FAIT", "color": "#00FF7F"}

    if is_rest:
        return {"status": "rest", "title": "Repos", "badge": "REPOS", "color": "#5a7a9a"}

    # Marqueur SESSION "SÉANCE MANQUÉE" explicite
    for r in day_rows:
        if r["Exercice"] == "SESSION" and "MANQUÉE" in (r.get("Remarque") or ""):
            return {"status": "missed", "title": "Manquée", "badge": "MANQUÉE", "color": "#FF453A"}

    # Pour un nouveau compte : ne jamais afficher "manquée" sur des jours
    # antérieurs à l'inscription (l'user n'avait pas encore l'app).
    if joined_date and day_date < joined_date:
        return {"status": "upcoming", "title": "Repos", "badge": "—", "color": "#5a7a9a"}
    if day_date < today:
        return {"status": "missed", "title": "Manquée", "badge": "MANQUÉE", "color": "#FF453A"}
    if day_date == today:
        return {"status": "today", "title": "Séance à faire", "badge": "AUJOURD'HUI", "color": "#58CCFF"}
    return {"status": "upcoming", "title": "Séance à faire", "badge": "À VENIR", "color": "#5a7a9a"}


@bp.route("/accueil")
def index():
    try:
        hist = get_hist()
        prog = get_prog()
        profile = get_profile() or {}
        onboarding = get_onboarding() or {}
    except Exception as e:
        return render_template("accueil.html", active="accueil", error=str(e))
    prenom = (profile.get("prenom") or "").strip()

    # Date d'inscription : utilisée pour ne pas marquer "manquées" les
    # journées antérieures à la création du compte.
    joined_date = None
    completed_at = onboarding.get("completed_at")
    if completed_at:
        try:
            joined_date = _datetime.fromisoformat(str(completed_at).replace("Z", "+00:00")).date()
        except ValueError:
            joined_date = None

    hist, prog_seances = _normalize_hist(hist, prog)
    planning_map = prog.get("_planning", {})

    today = today_paris()
    now = now_paris()
    day_name = DAYS_FR[today.weekday()]
    date_str = f"{today.day} {MONTHS_FR[today.month - 1]} {today.year}"

    # Semaine en cours
    s_act = max((r["Semaine"] for r in hist), default=1)

    # Grille 7 jours (lundi -> dimanche)
    monday = monday_of(today)
    week = []
    for i in range(7):
        d = monday + timedelta(days=i)
        info = _day_status(d, hist, planning_map, today, joined_date)
        week.append({
            "index": i,
            "day_label": DAYS_FR[i],
            "date_short": f"{d.day:02d}/{d.month:02d}",
            "date_iso": d.strftime("%Y-%m-%d"),
            "is_today": d == today,
            **info,
        })

    # Stats semaine
    cur_week = [r for r in hist if r["Semaine"] == s_act]
    cur_week_real = [r for r in cur_week if r["Poids"] > 0]
    vol_week = int(sum(r["Poids"] * r["Reps"] for r in cur_week))
    vol_week_fmt = f"{vol_week:,}".replace(",", " ")
    sessions_done = len({r["Séance"] for r in cur_week_real})
    total_sessions = len(prog_seances)

    # Streak : semaines consécutives avec au moins une perf
    weeks_with_data = sorted({r["Semaine"] for r in hist if r["Poids"] > 0}, reverse=True)
    streak = 0
    for i, w in enumerate(weeks_with_data):
        if i == 0 or w == weeks_with_data[i - 1] - 1:
            streak += 1
        else:
            break

    # Record de streak (stocké dans prog._streak_record)
    streak_record = int(prog.get("_streak_record", 0) or 0)
    if streak > streak_record:
        streak_record = streak
        prog["_streak_record"] = streak_record
        from core.data import save_prog as _save_prog
        _save_prog(prog)

    # Streak en danger ? (aujourd'hui est un jour de séance et pas fait)
    today_day_name = DAYS_FR[today.weekday()]
    today_seance = planning_map.get(today_day_name, "")
    today_done = any(
        r for r in hist
        if r["Date"] == today.strftime("%Y-%m-%d") and r["Poids"] > 0
    )
    streak_danger = bool(today_seance and not today_done and today.weekday() < 5)

    # Palier streak
    if streak >= 24:
        streak_tier = "diamond"
        streak_tier_icon = "💎"
        streak_tier_label = "Diamant"
    elif streak >= 12:
        streak_tier = "gold"
        streak_tier_icon = "🥇"
        streak_tier_label = "Or"
    elif streak >= 8:
        streak_tier = "silver"
        streak_tier_icon = "🥈"
        streak_tier_label = "Argent"
    elif streak >= 4:
        streak_tier = "bronze"
        streak_tier_icon = "🥉"
        streak_tier_label = "Bronze"
    else:
        streak_tier = "none"
        streak_tier_icon = ""
        streak_tier_label = ""

    # Détail
    exos_count = len({r["Exercice"] for r in cur_week_real})
    sets_count = len(cur_week_real)
    reps_count = sum(r["Reps"] for r in cur_week)

    return render_template(
        "accueil.html",
        active="accueil",
        day_name=day_name.upper(),
        date_str=date_str,
        s_act=s_act,
        week=week,
        sessions_done=sessions_done,
        total_sessions=total_sessions,
        vol_week=vol_week_fmt,
        streak=streak,
        streak_record=streak_record,
        streak_danger=streak_danger,
        streak_tier=streak_tier,
        streak_tier_icon=streak_tier_icon,
        streak_tier_label=streak_tier_label,
        today_seance=today_seance,
        today_done=today_done,
        notif_enabled=bool(prog.get("_settings", {}).get("notifications", False)),
        exos_count=exos_count,
        sets_count=sets_count,
        reps_count=reps_count,
        prenom=prenom,
    )
