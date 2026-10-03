"""Le RPE saisi pendant la séance arrive jusqu'à la suggestion (audit du 03/10, I1).

Depuis la migration v34, la saisie écrit le RPE dans la colonne `rpe` et plus
dans le texte de la remarque. La suggestion, elle, ne cherchait que le jeton
« @RPE8 » dans la remarque : tout RPE saisi était ignoré. 3 × 8 à RPE 10
donnait « Même charge, vise 9 reps » au lieu de « Consolide ».

Les tests de `overload_suggestion` lui passaient le RPE à la main : ils ne
pouvaient pas voir que la chaîne saisie → base → suggestion était coupée.
On la rejoue ici en entier, par la route.
"""
import datetime as dt
import json

from conftest import CSRF, USER_ID

SEMAINE_1 = dt.date(2026, 9, 14)
SEMAINE_2 = SEMAINE_1 + dt.timedelta(days=7)
JSON_HEADERS = {"Accept": "application/json", "X-CSRFToken": CSRF}


def _programme(fake, reps="8-12"):
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs",
                  "reps": reps, "rest_seconds": 120}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": SEMAINE_1.isoformat(),
    }}).execute()


def _saisir(client, sets, date):
    return client.post("/seance/save-exo", data={
        "_csrf": CSRF, "seance_name": "Push", "exo_base": "Développé couché",
        "variant": "Standard", "muscle": "Pecs", "date": date.isoformat(),
        "mode": "prefaite", "name": "Push", "sets_json": json.dumps(sets),
    }, headers=JSON_HEADERS)


def _suggestion_semaine_2(client):
    r = client.post("/seance/api/variant-history", json={
        "exo_base": "Développé couché", "variant": "Standard", "seance": "Push",
        "date": SEMAINE_2.isoformat(), "s_act": 0, "week_offset": 0,
    }, headers={"X-CSRFToken": CSRF})
    assert r.status_code == 200
    return r.get_json()["suggestion"]


def test_un_echec_a_rpe_10_fait_consolider(fake_db, logged_in):
    _programme(fake_db)
    assert _saisir(logged_in, [{"reps": 8, "poids": 100, "rpe": "10"}] * 3, SEMAINE_1).status_code == 200
    # La donnée est bien là où la saisie l'écrit…
    assert {r["rpe"] for r in fake_db.tables["history"]} == {10.0}
    # … et la suggestion la lit.
    s = _suggestion_semaine_2(logged_in)
    assert s["kind"] == "hold", s
    assert s["why"] == "rpe_high"


def test_une_serie_facile_fait_monter_la_charge(fake_db, logged_in):
    _programme(fake_db)
    _saisir(logged_in, [{"reps": 9, "poids": 100, "rpe": "6.5"}] * 3, SEMAINE_1)
    s = _suggestion_semaine_2(logged_in)
    assert s["kind"] == "load" and s["why"] == "rpe_low", s
    assert s["poids"] == 102.5


def test_sans_rpe_la_regle_des_reps_reste(fake_db, logged_in):
    _programme(fake_db)
    _saisir(logged_in, [{"reps": 9, "poids": 100, "rpe": ""}] * 3, SEMAINE_1)
    s = _suggestion_semaine_2(logged_in)
    assert s["kind"] == "reps" and s["reps"] == 10


def test_lancien_jeton_dans_la_remarque_compte_encore(fake_db, logged_in):
    """Les lignes d'avant la v34 n'ont que « @RPE10 » dans la remarque."""
    _programme(fake_db)
    for n in (1, 2, 3):
        fake_db.table("history").insert({
            "user_id": USER_ID, "semaine": 1, "seance": "Push",
            "exercice": "Développé couché", "serie": n, "reps": 8, "poids": 100.0,
            "remarque": "@RPE10", "muscle": "Pecs", "date": SEMAINE_1.isoformat(),
        }).execute()
    s = _suggestion_semaine_2(logged_in)
    assert s["kind"] == "hold"
