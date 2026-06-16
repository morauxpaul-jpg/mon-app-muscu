"""Défis hebdomadaires — un défi tournant, évalué depuis l'historique.

Principe :
- Le défi de la semaine est choisi de façon déterministe par l'index de
  semaine continu (`continuous_week`) → identique pour tout le monde, change
  chaque lundi, ne se répète qu'après un cycle complet.
- La progression est calculée à la lecture depuis l'historique normalisé de
  l'utilisateur (mêmes clés que routes/accueil : Date, Séance, Exercice,
  Poids, Reps, Semaine). Aucune donnée stockée pour évaluer (sauf le marquage
  « défi validé » côté prog, géré par l'appelant).

`weekly_challenge(hist, today)` → dict prêt pour le template :
  {id, title, emoji, desc, current, target, unit, pct, done}
"""
from core.dates import continuous_week, logical_today_paris


def _is_cardio(r):
    return str(r.get("Exercice") or "").startswith("CARDIO:")


def _is_real_muscu(r):
    return (
        not _is_cardio(r)
        and r.get("Exercice") != "SESSION"
        and (float(r.get("Poids") or 0) > 0 or int(r.get("Reps") or 0) > 0)
    )


def _week_rows(hist, week_idx):
    return [r for r in hist if r.get("Semaine") == week_idx]


def _distinct_sessions(rows):
    """(Date, Séance) distincts parmi les perfs réelles (muscu + cardio)."""
    out = set()
    for r in rows:
        if not r.get("Date"):
            continue
        if _is_real_muscu(r) or (_is_cardio(r) and int(r.get("Reps") or 0) > 0):
            out.add((r.get("Date"), r.get("Séance")))
    return out


def _volume(rows):
    return int(sum(float(r.get("Poids") or 0) * int(r.get("Reps") or 0)
                   for r in rows if _is_real_muscu(r)))


def _cardio_sessions(rows):
    return {(r.get("Date"), r.get("Séance")) for r in rows
            if _is_cardio(r) and int(r.get("Reps") or 0) > 0 and r.get("Date")}


# ── Évaluateurs : (hist, week_idx) → (title, emoji, desc, current, target, unit)
def _ch_sessions(hist, w):
    cur = len(_distinct_sessions(_week_rows(hist, w)))
    return ("3 séances cette semaine", "💪",
            "Enchaîne 3 séances avant dimanche soir.", cur, 3, "séances")


def _ch_tonnage(hist, w):
    cur = _volume(_week_rows(hist, w))
    return ("Soulève 10 000 kg", "🏋️",
            "Cumule 10 000 kg de volume (poids × reps) cette semaine.",
            cur, 10000, "kg")


def _ch_cardio(hist, w):
    cur = len(_cardio_sessions(_week_rows(hist, w)))
    return ("1 séance de cardio", "🏃",
            "Ajoute au moins une séance de cardio cette semaine.", cur, 1, "séance")


def _ch_new_exo(hist, w):
    """Tester un exercice non fait au cours des 4 semaines précédentes."""
    prev = {r.get("Exercice") for r in hist
            if _is_real_muscu(r) and (w - 4) <= (r.get("Semaine") or 0) < w}
    this = {r.get("Exercice") for r in _week_rows(hist, w) if _is_real_muscu(r)}
    cur = 1 if (this - prev) else 0
    return ("Teste un nouvel exercice", "✨",
            "Ajoute un exercice que tu n'as pas fait depuis un mois.", cur, 1, "exo")


def _ch_beat_volume(hist, w):
    last = _volume(_week_rows(hist, w - 1))
    cur = _volume(_week_rows(hist, w))
    if last <= 0:
        # Pas de semaine de référence → objectif amical fixe.
        return ("Soulève 8 000 kg", "📈",
                "Lance-toi un gros volume cette semaine : 8 000 kg.",
                cur, 8000, "kg")
    return ("Bats ton volume", "📈",
            f"Dépasse ton volume de la semaine dernière ({last:,} kg).".replace(",", " "),
            cur, last + 1, "kg")


# Ordre = cycle de rotation (un défi par semaine).
CHALLENGES = [
    ("sessions3", _ch_sessions),
    ("tonnage10k", _ch_tonnage),
    ("new_exo", _ch_new_exo),
    ("cardio1", _ch_cardio),
    ("beat_volume", _ch_beat_volume),
]


def current_week_index(today=None):
    return continuous_week(today or logical_today_paris())


def weekly_challenge(hist, today=None):
    """Défi de la semaine + progression de l'utilisateur (dict pour le template)."""
    w = current_week_index(today)
    cid, fn = CHALLENGES[w % len(CHALLENGES)]
    title, emoji, desc, current, target, unit = fn(hist or [], w)
    target = max(1, int(target))
    current = max(0, int(current))
    pct = min(100, int(round(current * 100 / target)))

    def _fmt(n):
        return f"{n:,}".replace(",", " ")

    return {
        "id": cid,
        "week": w,
        "title": title,
        "emoji": emoji,
        "desc": desc,
        "current": current,
        "target": target,
        "current_fmt": _fmt(current),
        "target_fmt": _fmt(target),
        "unit": unit,
        "pct": pct,
        "done": current >= target,
    }
