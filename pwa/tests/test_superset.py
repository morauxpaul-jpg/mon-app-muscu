"""Supersets : deux exercices enchaînés sans repos (audit du 03/10)."""
import datetime as dt
import json

from conftest import CSRF, USER_ID

LUNDI = dt.date(2026, 9, 14)
JSON = {"X-CSRFToken": CSRF, "Content-Type": "application/json"}


def _seed(fake_db, superset=True):
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Bras": [{"name": "Curl biceps", "sets": 3, "muscle": "Biceps", "superset": superset},
                 {"name": "Extensions triceps", "sets": 3, "muscle": "Triceps"},
                 {"name": "Shrug", "sets": 3, "muscle": "Trapèzes"}],
        "_planning": {"Lundi": "Bras"}, "_settings": {},
    }}).execute()


def test_les_deux_cartes_se_nomment(fake_db, logged_in):
    _seed(fake_db)
    html = logged_in.get(f"/seance?mode=prefaite&name=Bras&date={LUNDI}").get_data(as_text=True)
    assert "Superset · enchaîne avec Extensions triceps ↓" in html
    assert "Superset · après Curl biceps ↑, puis repos" in html
    assert html.count("exo-card--ss-debut") == 1 and html.count("exo-card--ss-fin") == 1


def test_sans_superset_rien(fake_db, logged_in):
    _seed(fake_db, superset=False)
    html = logged_in.get(f"/seance?mode=prefaite&name=Bras&date={LUNDI}").get_data(as_text=True)
    assert "exo-card--ss" not in html and "Superset ·" not in html


def test_l_editeur_garde_le_drapeau(fake_db, logged_in):
    _seed(fake_db)
    blob = fake_db.tables["programs"][0]["data"]
    state = {"name": "P", "planning": blob["_planning"], "seance_order": ["Bras"],
             "seances": {"Bras": [dict(e) for e in blob["Bras"]]}}
    state["seances"]["Bras"][1]["superset"] = "oui"          # pas un booléen : ignoré
    logged_in.post("/programme/state", data=json.dumps(state), headers=JSON)
    bras = fake_db.tables["programs"][0]["data"]["Bras"]
    assert bras[0].get("superset") is True
    assert "superset" not in bras[1] and "superset" not in bras[2]
    ui = logged_in.get("/programme").get_data(as_text=True)
    assert '"superset": true' in ui
