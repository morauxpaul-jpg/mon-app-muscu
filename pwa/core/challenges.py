"""Défis hebdomadaires — un défi tournant, évalué depuis l'historique.

Principe :
- Le défi de la semaine est choisi de façon déterministe par l'index de
  semaine continu (`continuous_week`) → identique pour tout le monde, change
  chaque lundi, ne se répète qu'après un cycle complet.
- La progression est calculée à la lecture depuis l'historique normalisé de
  l'utilisateur (mêmes clés que routes/accueil : Date, Séance, Exercice,
  Poids, Reps, Semaine). Aucune donnée stockée pour évaluer (sauf le marquage
  « défi validé » côté prog, géré par l'appelant).

`weekly_challenge(hist, today, prog)` → dict prêt pour le template :
  {id, title, emoji, desc, current, target, unit, pct, done}

Les cibles sont RELATIVES à chacun (audit du 03/10) : « 3 séances » ne se
réussissait pas avec un programme sur 2 jours, et « 10 000 kg » était hors
d'atteinte pour un débutant et sans effort pour un confirmé. Le défi des
séances vise donc les séances prévues de la semaine, celui du volume la
moyenne des semaines actives récentes, +5 %. Sans référence (compte neuf,
pas de planning), les anciennes cibles fixes servent de repli.
"""
import math

from core.dates import continuous_week, logical_today_paris
from core.hist import is_cardio as _is_cardio, is_muscu_perf as _is_real_muscu, tonnage


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
    return tonnage(rows)


def _reps(rows):
    return sum(int(r.get("Reps") or 0) for r in rows if _is_real_muscu(r))


def _au_poids_du_corps(hist, w):
    """True si l'utilisateur s'entraîne (presque) sans charge : ≥ 70 % de ses
    séries des 4 dernières semaines (ou de celle-ci, faute de mieux) à 0 kg.

    Deux défis sur cinq se comptaient en kilos : à 0 kg, un programme au poids
    du corps — gratuit, proposé dès l'onboarding — ne pouvait jamais les
    réussir (audit du 30/09, I14). On lui propose les mêmes en répétitions."""
    series = [r for r in hist if _is_real_muscu(r) and (w - 4) <= (r.get("Semaine") or 0) <= w]
    if not series:
        return False
    a_vide = sum(1 for r in series if float(r.get("Poids") or 0) <= 0)
    return a_vide >= 0.7 * len(series)


def _cardio_sessions(rows):
    return {(r.get("Date"), r.get("Séance")) for r in rows
            if _is_cardio(r) and int(r.get("Reps") or 0) > 0 and r.get("Date")}


def _reference(hist, w, mesure, semaines=4):
    """Moyenne de `mesure` sur les semaines ACTIVES parmi les `semaines`
    précédentes (une semaine de vacances ne fait pas baisser la barre), ou 0."""
    valeurs = [v for v in (mesure(_week_rows(hist, x)) for x in range(w - semaines, w)) if v > 0]
    return sum(valeurs) / len(valeurs) if valeurs else 0


def _arrondi_haut(x, pas):
    return int(math.ceil(x / pas) * pas)


def _fmt(n):
    return f"{n:,}".replace(",", " ")


# ── Évaluateurs : (hist, week_idx, ctx) → (title, emoji, desc, current, target, unit)
# ctx : {"prevues": séances prévues cette semaine (planning + rotation)}.
def _ch_sessions(hist, w, ctx=None):
    cur = len(_distinct_sessions(_week_rows(hist, w)))
    n = int((ctx or {}).get("prevues") or 0) or 3
    if (ctx or {}).get("prevues"):
        return (f"Tes {n} séances de la semaine" if n > 1 else "Ta séance de la semaine", "💪",
                "Fais toutes les séances de ton planning cette semaine.", cur, n, "séances")
    return ("3 séances cette semaine", "💪",
            "Enchaîne 3 séances avant dimanche soir.", cur, 3, "séances")


def _ch_tonnage(hist, w, ctx=None):
    if _au_poids_du_corps(hist, w):
        ref = _reference(hist, w, _reps)
        cible = _arrondi_haut(ref * 1.05, 10) if ref else 300
        return (f"{_fmt(cible)} répétitions", "🏋️",
                ("5 % de plus que ta semaine habituelle, toutes séries confondues."
                 if ref else "Cumule 300 répétitions cette semaine, toutes séries confondues."),
                _reps(_week_rows(hist, w)), cible, "reps")
    cur = _volume(_week_rows(hist, w))
    ref = _reference(hist, w, _volume)
    if ref:
        cible = _arrondi_haut(ref * 1.05, 500)
        return (f"Soulève {_fmt(cible)} kg", "🏋️",
                f"5 % de plus que ta semaine habituelle ({_fmt(int(ref))} kg en moyenne).",
                cur, cible, "kg")
    return ("Soulève 10 000 kg", "🏋️",
            "Cumule 10 000 kg de volume (poids × reps) cette semaine.",
            cur, 10000, "kg")


def _ch_cardio(hist, w, ctx=None):
    cur = len(_cardio_sessions(_week_rows(hist, w)))
    return ("1 séance de cardio", "🏃",
            "Ajoute au moins une séance de cardio cette semaine.", cur, 1, "séance")


def _ch_new_exo(hist, w, ctx=None):
    """Tester un exercice non fait au cours des 4 semaines précédentes."""
    prev = {r.get("Exercice") for r in hist
            if _is_real_muscu(r) and (w - 4) <= (r.get("Semaine") or 0) < w}
    this = {r.get("Exercice") for r in _week_rows(hist, w) if _is_real_muscu(r)}
    cur = 1 if (this - prev) else 0
    return ("Teste un nouvel exercice", "✨",
            "Ajoute un exercice que tu n'as pas fait depuis un mois.", cur, 1, "exo")


def _ch_beat_volume(hist, w, ctx=None):
    if _au_poids_du_corps(hist, w):
        last = _reps(_week_rows(hist, w - 1))
        cur = _reps(_week_rows(hist, w))
        if last <= 0:
            return ("250 répétitions", "📈",
                    "Lance-toi un gros volume cette semaine : 250 répétitions.",
                    cur, 250, "reps")
        return ("Bats ton volume", "📈",
                f"Dépasse tes {last} répétitions de la semaine dernière.",
                cur, last + 1, "reps")
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


def weekly_challenge(hist, today=None, prog=None):
    """Défi de la semaine + progression de l'utilisateur (dict pour le template)."""
    w = current_week_index(today)
    cid, fn = CHALLENGES[w % len(CHALLENGES)]
    ctx = {}
    if prog:
        from core.rotation import planning_semaine
        ctx["prevues"] = sum(1 for v in planning_semaine(
            prog, today or logical_today_paris()).values() if v)
    title, emoji, desc, current, target, unit = fn(hist or [], w, ctx)
    target = max(1, int(target))
    current = max(0, int(current))
    pct = min(100, int(round(current * 100 / target)))

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
