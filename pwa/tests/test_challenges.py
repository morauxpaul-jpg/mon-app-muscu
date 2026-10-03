"""Tests du moteur de défis hebdo (core/challenges) — fonctions pures."""
import datetime as dt

from core import challenges as ch


def _row(date, seance, exo, poids, reps, semaine):
    return {"Date": date, "Séance": seance, "Exercice": exo,
            "Poids": poids, "Reps": reps, "Semaine": semaine}


def test_sessions_challenge_counts_distinct_sessions():
    w = 100
    rows = [
        _row("2025-01-06", "Push", "DC", 80, 8, w),
        _row("2025-01-06", "Push", "Dips", 0, 12, w),   # même séance → 1
        _row("2025-01-08", "Pull", "Tractions", 0, 10, w),
        _row("2025-01-10", "Legs", "Squat", 100, 5, w),
    ]
    title, emoji, desc, cur, target, unit = ch._ch_sessions(rows, w)
    assert cur == 3 and target == 3


def test_tonnage_challenge_sums_volume():
    w = 100
    rows = [_row("2025-01-06", "Push", "DC", 100, 10, w),   # 1000
            _row("2025-01-07", "Pull", "Rowing", 50, 10, w)]  # 500
    *_, cur, target, unit = ch._ch_tonnage(rows, w)
    assert cur == 1500 and target == 10000 and unit == "kg"


def test_new_exo_challenge_detects_unseen_exercise():
    w = 100
    rows = [
        _row("2024-12-10", "Push", "Développé couché", 80, 8, w - 2),  # vu avant
        _row("2025-01-06", "Push", "Développé couché", 80, 8, w),      # pas nouveau
        _row("2025-01-08", "Pull", "Soulevé de terre", 120, 5, w),     # nouveau
    ]
    *_, cur, target, unit = ch._ch_new_exo(rows, w)
    assert cur == 1 and target == 1


def test_beat_volume_uses_last_week_or_default():
    w = 100
    # Sans semaine précédente → objectif amical fixe.
    *_, cur, target, unit = ch._ch_beat_volume([], w)
    assert target == 8000
    # Avec une semaine précédente → cible = volume précédent + 1.
    rows = [_row("2024-12-30", "Push", "DC", 100, 10, w - 1)]  # last = 1000
    *_, cur, target, unit = ch._ch_beat_volume(rows, w)
    assert target == 1001


def test_weekly_challenge_shape_and_not_done_when_empty():
    c = ch.weekly_challenge([], today=dt.date(2025, 6, 16))  # un lundi
    assert set(["id", "week", "title", "current", "target", "pct", "done", "unit"]).issubset(c)
    assert c["done"] is False
    assert 0 <= c["pct"] <= 100


def test_weekly_challenge_rotates_by_week():
    # Deux semaines distinctes → l'index de défi suit la semaine continue.
    c1 = ch.weekly_challenge([], today=dt.date(2025, 6, 16))
    c2 = ch.weekly_challenge([], today=dt.date(2025, 6, 23))
    assert c1["week"] + 1 == c2["week"]


# ── Cibles relatives (audit du 03/10) ────────────────────────────


def test_seances_visent_le_planning_de_la_semaine():
    from core.dates import DAYS_FR
    prog = {"A": [], "B": [], "_planning": {**{d: "" for d in DAYS_FR}, "Lundi": "A", "Jeudi": "B"}}
    c = ch.weekly_challenge([], today=dt.date(2025, 6, 16), prog=prog)   # un lundi
    title, emoji, desc, cur, target, unit = ch._ch_sessions([], 100, {"prevues": 2})
    assert target == 2 and title == "Tes 2 séances de la semaine"
    assert ch._ch_sessions([], 100, {"prevues": 1})[0] == "Ta séance de la semaine"
    assert c["target"] >= 1


def test_tonnage_suit_la_moyenne_des_semaines_actives():
    w = 100
    rows = [_row("2024-12-09", "Push", "DC", 100, 30, w - 4),     # 3 000
            _row("2024-12-23", "Push", "DC", 100, 50, w - 2),     # 5 000
            # w-3 et w-1 : vacances, ne font pas baisser la barre
            _row("2025-01-06", "Push", "DC", 100, 10, w)]         # 1 000 cette semaine
    title, *_, cur, target, unit = ch._ch_tonnage(rows, w)
    assert (cur, target, unit) == (1000, 4500, "kg")              # 4 000 × 1,05 → 4 500
    assert title == "Soulève 4 500 kg"


def test_tonnage_au_poids_du_corps_relatif():
    w = 100
    rows = [_row("2024-12-23", "Home", "Pompes", 0, 200, w - 1),
            _row("2025-01-06", "Home", "Pompes", 0, 50, w)]
    *_, cur, target, unit = ch._ch_tonnage(rows, w)
    assert (cur, target, unit) == (50, 210, "reps")
