"""La durée du cardio se saisit aussi en secondes (retour du 06/10).

Les deux formulaires (page Cardio, cardio dans une séance) n'avaient qu'un
champ minutes : 25 min 30 s s'enregistrait 25 min, et le chrono tronquait
25:59 en 25. La colonne `duree_min` (v44) est numérique : elle garde les
minutes décimales, sans migration.
"""
from conftest import USER_ID, CSRF
from test_cardio_mesures import compte, JOUR  # noqa: F401  (fixture)

import core.db as db
from core.cardio_duree import format_duree, lire_duree
from core.seance_cardio import _build_cardio_done


def _cardio(fake):
    return [r for r in fake.tables.get("history", [])
            if str(r.get("exercice") or "").startswith("CARDIO:")]


def test_la_page_cardio_garde_les_secondes(compte, logged_in):
    logged_in.post("/cardio/save", data={
        "activite": "Course", "date": JOUR, "duree_min": "25", "duree_sec": "30",
        "distance_km": "5", "_csrf": CSRF}, headers={"X-CSRFToken": CSRF})
    (ligne,) = _cardio(compte)
    assert ligne["duree_min"] == 25.5
    assert ligne["vitesse"] == 11.76            # 5 km en 25,5 min, pas en 25


def test_le_cardio_dune_seance_garde_les_secondes(compte, logged_in):
    logged_in.post("/seance/add-cardio", data={
        "mode": "prefaite", "name": "Push", "seance_name": "Push", "date": JOUR,
        "activite": "Rameur", "duree_min": "8", "duree_sec": "45", "_csrf": CSRF,
    }, headers={"X-CSRFToken": CSRF})
    (ligne,) = _cardio(compte)
    assert ligne["duree_min"] == 8.75
    (bloc,) = _build_cardio_done(db.get_hist(USER_ID), "Push", JOUR)
    assert bloc["duree"] == 8.75
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={JOUR}").get_data(as_text=True)
    assert "8 min 45 s" in html


def test_l_app_relit_des_minutes_entieres_dans_reps(compte, logged_in):
    logged_in.post("/cardio/save", data={
        "activite": "Course", "date": JOUR, "duree_min": "0", "duree_sec": "40",
        "_csrf": CSRF}, headers={"X-CSRFToken": CSRF})
    (r,) = [r for r in db.get_hist(USER_ID) if r["Exercice"].startswith("CARDIO:")]
    assert r["Duree"] == round(40 / 60, 4)
    assert r["Reps"] == 1                       # jamais 0 pour un cardio fait


def test_sans_secondes_rien_ne_change(compte, logged_in):
    logged_in.post("/cardio/save", data={
        "activite": "Course", "date": JOUR, "duree_min": "30", "_csrf": CSRF},
        headers={"X-CSRFToken": CSRF})
    (ligne,) = _cardio(compte)
    assert ligne["duree_min"] == 30


def test_lire_duree():
    assert lire_duree({"duree_min": "25", "duree_sec": "30"}) == 25.5
    assert lire_duree({"duree_min": "", "duree_sec": "90"}) == 1.5
    assert lire_duree({"duree_min": "-3", "duree_sec": "abc"}) == 0
    assert lire_duree({"duree_min": "2,5"}) == 2.5
    assert lire_duree({"duree_min": "99999"}) == 1440


def test_format_duree():
    assert format_duree(25) == "25 min"
    assert format_duree(25.5) == "25 min 30 s"
    assert format_duree(round(17 / 60, 4)) == "17 s"
    assert format_duree(0) == ""
    assert format_duree(None) == ""
