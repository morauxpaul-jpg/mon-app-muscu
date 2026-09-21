"""Suggestion de surcharge progressive (core.muscu.overload_suggestion)."""
from core.muscu import overload_suggestion, parse_rpe


def _sets(*pairs, rpe=None):
    return [{"reps": r, "poids": p, "rpe": rpe} for r, p in pairs]


def test_parse_rpe():
    assert parse_rpe("bonne série @RPE8") == 8.0
    assert parse_rpe("@rpe8.5") == 8.5
    assert parse_rpe("") is None
    assert parse_rpe(None) is None


def test_sans_historique():
    assert overload_suggestion([]) is None
    assert overload_suggestion([{"reps": 0, "poids": 80}]) is None


def test_plafond_de_reps_monte_la_charge():
    s = overload_suggestion(_sets((12, 80), (12, 80), (12, 80)))
    assert s["kind"] == "load" and s["poids"] == 82.5 and s["why"] == "reps_ceiling"
    assert s["reps"] == 10


def test_petite_charge_increment_1kg():
    s = overload_suggestion(_sets((12, 12), (12, 12)))
    assert s["kind"] == "load" and s["poids"] == 13.0


def test_rpe_faible_monte_la_charge():
    s = overload_suggestion(_sets((8, 80), (8, 80), rpe=7))
    assert s["kind"] == "load" and s["why"] == "rpe_low"


def test_rpe_eleve_consolide():
    s = overload_suggestion(_sets((8, 80), (7, 80), rpe=10))
    assert s["kind"] == "hold" and s["poids"] == 80 and s["reps"] == 7


def test_deux_seances_stables_montent_la_charge():
    last = _sets((9, 80), (8, 80))
    prev = _sets((8, 80), (8, 80))
    s = overload_suggestion(last, prev)
    assert s["kind"] == "load" and s["why"] == "two_sessions"


def test_regression_entre_deux_seances_ajoute_une_rep():
    last = _sets((8, 80), (8, 80))
    prev = _sets((10, 80), (9, 80))
    s = overload_suggestion(last, prev)
    assert s["kind"] == "reps" and s["poids"] == 80 and s["reps"] == 9


def test_par_defaut_meme_charge_plus_une_rep():
    s = overload_suggestion(_sets((8, 80), (6, 80)))
    assert s["kind"] == "reps" and s["reps"] == 7
    assert "7 reps" in s["label"]


def test_pyramide_ne_monte_pas_la_charge():
    s = overload_suggestion(_sets((12, 60), (12, 70), (12, 80)))
    assert s["kind"] == "reps" and s["poids"] == 80


def test_poids_de_corps():
    s = overload_suggestion(_sets((10, 0), (9, 0)), is_bw=True)
    assert s["kind"] == "reps" and s["poids"] is None and s["reps"] == 10
