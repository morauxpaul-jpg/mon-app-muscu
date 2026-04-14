"""Blueprint accueil — dashboard, planning hebdo, cadres des jours cliquables.

Logique portée depuis app.py (lignes 1499-1865).
"""
from datetime import timedelta
from flask import Blueprint, render_template

from datetime import date as _date, datetime as _datetime

from core.data import get_hist, get_prog, get_profile, get_onboarding, sum_nutrition_day
from core.dates import now_paris, today_paris, today_paris_str, monday_of, DAYS_FR, MONTHS_FR
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


def _is_cardio_row(row):
    return str(row.get("Exercice") or "").startswith("CARDIO:")


BADGE_DEFS = [
    # (code, label, short description, icon_id)
    ("first_session", "Première séance", "Fais ta toute première séance", "rocket"),
    ("full_week",     "Semaine complète", "Toutes les séances planifiées faites sur la semaine", "check-circle"),
    ("centurion",     "Centurion", "100 séances terminées", "trophy"),
    ("tonnage_10k",   "Tonnage 10k", "10 000 kg soulevés cumulés", "dumbbell"),
    ("tonnage_50k",   "Tonnage 50k", "50 000 kg soulevés cumulés", "dumbbell"),
    ("tonnage_100k",  "Tonnage 100k", "100 000 kg soulevés cumulés", "dumbbell"),
    ("regulier",      "Régulier", "4 semaines consécutives sans manquer une séance", "flame"),
    ("costaud",       "Costaud", "1RM supérieur à ton propre poids sur un exo", "medal-gold"),
]


def _compute_badges(hist, prog, profile, planning_map, streak):
    """Retourne (badges_unlocked:set, new_unlocked:list) et persiste _badges.

    Recalcule les badges à chaque visite de l'accueil. Un badge déjà obtenu
    reste obtenu (on ne peut pas le perdre — `_badges` dans prog en garde la
    liste). Les "new" sont ceux débloqués depuis la dernière visite.
    """
    already = set(prog.get("_badges", []) or [])
    unlocked = set()

    muscu = [r for r in hist if not _is_cardio_row(r) and r.get("Exercice") != "SESSION"]
    muscu_real = [r for r in muscu if r.get("Reps", 0) > 0 and r.get("Poids", 0) > 0]
    cardio = [r for r in hist if _is_cardio_row(r) and int(r.get("Reps") or 0) > 0]

    # Première séance : au moins une perf réelle (muscu OU cardio)
    if muscu_real or cardio:
        unlocked.add("first_session")

    # Séances distinctes (date, Séance) — muscu + cardio
    distinct_sessions = {(r.get("Date"), r.get("Séance")) for r in muscu_real if r.get("Date")}
    for r in cardio:
        if r.get("Date"):
            distinct_sessions.add((r.get("Date"), r.get("Séance")))
    total_sessions_done = len(distinct_sessions)
    if total_sessions_done >= 100:
        unlocked.add("centurion")

    # Tonnage cumulé (muscu uniquement)
    tonnage = int(sum(r["Poids"] * r["Reps"] for r in muscu_real))
    if tonnage >= 10_000:  unlocked.add("tonnage_10k")
    if tonnage >= 50_000:  unlocked.add("tonnage_50k")
    if tonnage >= 100_000: unlocked.add("tonnage_100k")

    # Régulier : 4 semaines consécutives sans manquer une séance planifiée.
    # On approxime : streak >= 4 (streak = semaines consécutives avec au moins
    # une perf), ce qui garantit qu'il n'y a pas eu de semaine sans données.
    if streak >= 4:
        unlocked.add("regulier")

    # Semaine complète : toutes les séances planifiées de la semaine courante
    # ont été faites (comptées dans streak_danger → on réutilise la logique).
    planned = [s for s in planning_map.values() if s]
    if planned:
        # Nombre de séances distinctes faites cette semaine
        try:
            s_act = max(r["Semaine"] for r in muscu_real)
        except ValueError:
            s_act = 0
        if s_act:
            done_this_week = {r["Séance"] for r in muscu_real if r["Semaine"] == s_act}
            planned_set = {p for p in planned if p}
            if planned_set and planned_set.issubset(done_this_week):
                unlocked.add("full_week")

    # Costaud : 1RM > poids de corps sur au moins un exercice
    poids_corps = 0.0
    try:
        poids_corps = float((profile or {}).get("poids_kg") or 0)
    except (TypeError, ValueError):
        poids_corps = 0.0
    if poids_corps > 0 and muscu_real:
        # 1RM Epley
        max_1rm = max((r["Poids"] * (1 + r["Reps"] / 30)) for r in muscu_real)
        if max_1rm > poids_corps:
            unlocked.add("costaud")

    # Union : un badge obtenu reste obtenu
    final = already | unlocked
    new_unlocked = [b for b in unlocked if b not in already]

    if final != already:
        prog["_badges"] = sorted(final)
        try:
            from core.data import save_prog as _save_prog
            _save_prog(prog)
        except Exception:
            pass

    return final, new_unlocked


def _day_status(day_date, hist_rows, planning_map, today, joined_date=None):
    """Statut d'une journée — porté de _day_status() app.py 1751-1784."""
    d_str = day_date.strftime("%Y-%m-%d")
    day_rows = [r for r in hist_rows if r["Date"] == d_str]
    day_name_fr = DAYS_FR[day_date.weekday()]
    is_rest = day_name_fr in planning_map and not planning_map.get(day_name_fr, "")

    real = [r for r in day_rows if _is_real_perf(r)]
    if real:
        # Si la journée ne contient que du cardio : titre dédié + couleur orange
        cardio_rows = [r for r in real if _is_cardio_row(r)]
        non_cardio = [r for r in real if not _is_cardio_row(r)]
        if cardio_rows and not non_cardio:
            types = {r["Exercice"].split(":", 1)[1] for r in cardio_rows}
            label = ", ".join(sorted(types))
            return {"status": "done", "title": f"Cardio · {label}", "badge": "CARDIO",
                    "color": "#FF7A00", "cardio": True}
        # Séance majoritaire = celle avec le plus d'exos distincts (hors cardio)
        rows_for_top = non_cardio or real
        counts = {}
        for r in rows_for_top:
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
    # Les lignes cardio (Exercice "CARDIO:*") ne doivent pas compter dans le
    # volume muscu (km × min ≠ kg × reps). Elles sont agrégées à part.
    cur_week_muscu = [r for r in cur_week if not _is_cardio_row(r)]
    cur_week_real = [r for r in cur_week_muscu if r["Poids"] > 0]
    vol_week = int(sum(r["Poids"] * r["Reps"] for r in cur_week_muscu))
    vol_week_fmt = f"{vol_week:,}".replace(",", " ")
    sessions_done = len({r["Séance"] for r in cur_week_real})
    total_sessions = len(prog_seances)

    # Streak : semaines consécutives avec au moins une perf (muscu avec poids OU cardio avec durée)
    weeks_with_data = sorted({
        r["Semaine"] for r in hist
        if (r["Poids"] > 0) or (_is_cardio_row(r) and r["Reps"] > 0)
    }, reverse=True)
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
    today_iso = today.strftime("%Y-%m-%d")
    today_done = any(
        r for r in hist
        if r["Date"] == today_iso and (
            r["Poids"] > 0 or (_is_cardio_row(r) and r["Reps"] > 0)
        )
    )
    streak_danger = bool(today_seance and not today_done and today.weekday() < 5)

    # Palier streak — icon_id = symbole SVG dans icons.svg, color = classe icon-*
    if streak >= 24:
        streak_tier = "diamond"
        streak_tier_icon = "gem"
        streak_tier_color = "icon-accent"
        streak_tier_label = "Diamant"
    elif streak >= 12:
        streak_tier = "gold"
        streak_tier_icon = "medal-gold"
        streak_tier_color = "icon-gold"
        streak_tier_label = "Or"
    elif streak >= 8:
        streak_tier = "silver"
        streak_tier_icon = "medal-silver"
        streak_tier_color = "icon-silver"
        streak_tier_label = "Argent"
    elif streak >= 4:
        streak_tier = "bronze"
        streak_tier_icon = "medal-bronze"
        streak_tier_color = "icon-bronze"
        streak_tier_label = "Bronze"
    else:
        streak_tier = "none"
        streak_tier_icon = ""
        streak_tier_color = ""
        streak_tier_label = ""

    # Détail (muscu uniquement — le cardio est compté séparément plus bas)
    exos_count = len({r["Exercice"] for r in cur_week_real})
    sets_count = len(cur_week_real)
    reps_count = sum(r["Reps"] for r in cur_week_muscu)

    # Cardio semaine : total minutes + km sur la semaine active
    cardio_rows = [r for r in cur_week if _is_cardio_row(r)]
    cardio_minutes = sum(int(r.get("Reps") or 0) for r in cardio_rows)
    cardio_km = round(sum(float(r.get("Poids") or 0) for r in cardio_rows), 1)

    # Widget calories — objectif depuis profile, consommé depuis table nutrition
    cal_cible = int(profile.get("calories_cible") or 0)
    try:
        nutr = sum_nutrition_day(today_paris_str()) if cal_cible > 0 else None
    except Exception as e:
        nutr = None
    cal_today = int((nutr or {}).get("calories") or 0)
    cal_pct = int(min(100, round((cal_today / cal_cible) * 100))) if cal_cible > 0 else 0

    # Badges — recalculés à chaque visite, persistés dans prog._badges
    try:
        badges_unlocked, badges_new = _compute_badges(hist, prog, profile, planning_map, streak)
    except Exception as e:
        badges_unlocked, badges_new = set(), []
    badges = [
        {
            "code": code,
            "label": label,
            "desc": desc,
            "icon": icon,
            "unlocked": code in badges_unlocked,
        }
        for (code, label, desc, icon) in BADGE_DEFS
    ]

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
        streak_tier_color=streak_tier_color,
        streak_tier_label=streak_tier_label,
        today_seance=today_seance,
        today_done=today_done,
        notif_enabled=bool(prog.get("_settings", {}).get("notifications", False)),
        exos_count=exos_count,
        sets_count=sets_count,
        reps_count=reps_count,
        prenom=prenom,
        cardio_minutes=cardio_minutes,
        cardio_km=cardio_km,
        cal_today=cal_today,
        cal_cible=cal_cible,
        cal_pct=cal_pct,
        badges=badges,
        badges_new=badges_new,
    )
