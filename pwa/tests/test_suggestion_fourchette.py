"""La suggestion suit la fourchette de reps du programme (audit du 30/09, I13).

Sur un 3 × 5 réussi à 100 kg, la carte affichait « 3 séries × 5 reps » et,
juste dessous, « Même charge, vise 6 reps » (R15) : la suggestion ne recevait
pas la cible du programme, et ses seuils codés en dur (8 et 12 reps) ne
convenaient qu'à l'hypertrophie.
"""
import json

import pytest

from conftest import CSRF
from core.muscu import overload_suggestion, parse_cible_reps
from test_seance_saisie import MONDAY, JSON_HEADERS, _hist

S = lambda reps, poids, rpe=None: {"reps": reps, "poids": poids, "rpe": rpe}


# ── La fourchette ────────────────────────────────────────────────


@pytest.mark.parametrize("texte,attendu", [
    ("5", (5, 5)), ("8-12", (8, 12)), ("8–12", (8, 12)), ("8 à 12", (8, 12)),
    ("12-8", (8, 12)), ("AMRAP", None), ("", None), (None, None), ("0", None),
])
def test_parse_cible_reps(texte, attendu):
    assert parse_cible_reps(texte) == attendu


# ── La règle ─────────────────────────────────────────────────────


def test_un_5x5_reussi_monte_la_charge():
    s = overload_suggestion([S(5, 100)] * 3, cible=(5, 5))
    assert s["kind"] == "load" and s["poids"] == 102.5 and s["reps"] == 5


def test_un_5x5_rate_vise_5_pas_6():
    s = overload_suggestion([S(5, 100), S(5, 100), S(4, 100)], cible=(5, 5))
    assert s["kind"] == "reps" and s["reps"] == 5


def test_dans_la_fourchette_on_ajoute_une_rep():
    s = overload_suggestion([S(10, 60)] * 3, cible=(8, 12))
    assert s["kind"] == "reps" and s["reps"] == 11


def test_au_haut_de_la_fourchette_on_monte_et_on_repart_du_bas():
    s = overload_suggestion([S(12, 60)] * 3, cible=(8, 12))
    assert s["kind"] == "load" and s["poids"] == 62.5 and s["reps"] == 8


def test_sous_la_fourchette_on_vise_le_bas():
    s = overload_suggestion([S(5, 60)] * 3, cible=(8, 12))
    assert s["reps"] == 8


def test_trop_dur_on_consolide():
    s = overload_suggestion([S(4, 100, "10")] * 3, cible=(5, 5))
    assert s["kind"] == "hold"


def test_sans_cible_rien_ne_change():
    """Séance libre, extras, programme sans fourchette : les anciens seuils."""
    s = overload_suggestion([S(5, 100)] * 3)
    assert s["kind"] == "reps" and s["reps"] == 6


# ── Sur la page ──────────────────────────────────────────────────


def _programme_5x5(fake):
    from conftest import USER_ID
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Force": [{"name": "Squat", "sets": 3, "muscle": "Jambes",
                   "reps": "5", "rest_seconds": 180}],
        "_planning": {"Lundi": "Force"}, "_settings": {},
        "_started_at": MONDAY.isoformat(),
    }}).execute()


def test_la_carte_de_seance_suit_la_cible(fake_db, logged_in):
    import datetime as dt
    _programme_5x5(fake_db)
    semaine_passee = MONDAY - dt.timedelta(days=7)
    for n in (1, 2, 3):
        fake_db.table("history").insert({
            "user_id": "u-test-0001", "semaine": 1, "seance": "Force",
            "exercice": "Squat", "serie": n, "reps": 5, "poids": 100.0,
            "remarque": "", "muscle": "Jambes", "date": semaine_passee.isoformat(),
        }).execute()
    html = logged_in.get(f"/seance?mode=prefaite&name=Force&date={MONDAY.isoformat()}").get_data(as_text=True)
    import re
    # Les données de la carte partent en JSON dans x-data (accents échappés).
    assert "vise 6 reps" not in html
    assert re.search(r'"kind":\s*"load"', html) and re.search(r'"poids":\s*102\.5', html)
    # Et le repos prescrit arrive jusqu'au client, marqué comme tel.
    assert re.search(r'"rest_prescrit":\s*true', html)
    assert re.search(r'"rest_seconds":\s*180', html)


def test_lenregistrement_renvoie_la_suggestion_de_la_cible(fake_db, logged_in):
    _programme_5x5(fake_db)
    r = logged_in.post("/seance/save-exo", data={
        "_csrf": CSRF, "seance_name": "Force", "exo_base": "Squat",
        "variant": "Standard", "muscle": "Jambes", "date": MONDAY.isoformat(),
        "mode": "prefaite", "name": "Force",
        "sets_json": json.dumps([{"reps": 5, "poids": 100}] * 3),
    }, headers=JSON_HEADERS)
    # La suggestion porte sur la PROCHAINE séance : aujourd'hui compte.
    s = json.loads(r.data)["suggestion"]
    assert s is None or "6 reps" not in s["label"]
