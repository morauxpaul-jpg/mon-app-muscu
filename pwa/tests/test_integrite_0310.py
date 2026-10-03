"""Correctifs d'intégrité de l'audit du 03/10 (M1, M2, M3, I13)."""
import datetime as dt

import pytest

from conftest import CSRF, USER_ID
from core.dates import continuous_week, logical_today_paris

AUJ = logical_today_paris()


def _prog(fake, data=None):
    fake.table("programs").insert({"user_id": USER_ID, "data": data or {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {}}}).execute()


def _serie(fake, d, seance="Push", exo="Développé couché", reps=8, poids=80.0):
    fake.table("history").insert({
        "user_id": USER_ID, "date": d.isoformat(), "semaine": 1, "seance": seance,
        "exercice": exo, "serie": 1, "reps": reps, "poids": poids, "remarque": "",
        "muscle": "Pecs"}).execute()


# ── M1 : une 2e fin en « Passer » n'efface pas le bilan ──────────────────

def test_terminer_deux_fois_garde_la_note_et_le_commentaire(fake_db, logged_in):
    _prog(fake_db)
    _serie(fake_db, AUJ)
    base = {"_csrf": CSRF, "mode": "prefaite", "seance_name": "Push",
            "date": AUJ.isoformat(), "name": "Push"}
    logged_in.post("/seance/finish", data={**base, "rating": "5", "comment": "PR au DC", "duration_min": "55"})
    logged_in.post("/seance/finish", data={**base, "rating": "", "comment": "", "duration_min": "62"})
    (note,) = fake_db.tables["session_notes"]
    assert (note["rating"], note["comment"], note["duration_min"]) == (5, "PR au DC", 62)


# ── M2 : renommer une séance emporte ses bilans ──────────────────────────

def test_renommer_une_seance_emporte_ses_bilans(fake_db, logged_in):
    _prog(fake_db)
    _serie(fake_db, AUJ)
    fake_db.table("session_notes").insert({"user_id": USER_ID, "date": AUJ.isoformat(),
                                           "seance": "Push", "rating": 4, "comment": "ok"}).execute()
    r = logged_in.post("/programme/seance/rename", json={"name": "Push", "new_name": "Pecs"},
                       headers={"X-CSRFToken": CSRF})
    assert r.status_code == 200
    assert {n["seance"] for n in fake_db.tables["session_notes"]} == {"Pecs"}


# ── M3 : l'historique d'un exercice au poids du corps est visible ───────

def test_les_semaines_precedentes_dun_exercice_au_poids_du_corps(fake_db):
    from core.seance_historique import _previous_weeks_data
    w = continuous_week(AUJ)
    d = (AUJ - dt.timedelta(days=7)).isoformat()
    hist = [{"Date": d, "Séance": "Push", "Exercice": "Pompes", "Reps": 15, "Poids": 0.0,
             "Série": 1, "Semaine": w - 1, "Remarque": ""},
            {"Date": d, "Séance": "Push", "Exercice": "Pompes", "Reps": 0, "Poids": 0.0,
             "Série": 2, "Semaine": w - 1, "Remarque": "SKIP"}]
    (semaine,) = _previous_weeks_data(hist, "Pompes", "Push", w)
    assert semaine["week"] == w - 1
    assert [r["Reps"] for r in semaine["rows"]] == [15], "la série passée (SKIP) reste exclue"


# ── I13 : un échec ne se fait plus passer pour un succès ────────────────

def test_un_repas_qui_ne_senregistre_pas_le_dit(fake_db, logged_in, monkeypatch):
    import routes.nutrition as nut
    def boom(row):
        raise RuntimeError("base injoignable")
    monkeypatch.setattr(nut, "insert_nutrition", boom)
    r = logged_in.post("/nutrition/add-meal", data={"_csrf": CSRF, "calories": "500",
                                                    "date": AUJ.isoformat(), "meal_type": "dejeuner"})
    assert r.status_code == 503
    assert "pas pu être enregistré" in r.get_data(as_text=True)


def test_un_cardio_qui_ne_se_retire_pas_le_dit(fake_db, logged_in, monkeypatch):
    import core.data as data
    def boom(*a, **k):
        raise RuntimeError("base injoignable")
    monkeypatch.setattr(data, "delete_exo_rows", boom)
    r = logged_in.post("/seance/delete-cardio", data={
        "_csrf": CSRF, "seance_name": "Push", "activite": "Course", "date": AUJ.isoformat(),
        "mode": "prefaite", "name": "Push"})
    assert r.status_code == 503
