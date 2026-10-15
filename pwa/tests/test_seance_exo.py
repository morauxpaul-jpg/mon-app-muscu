"""Ce qu'un exercice garde d'une séance à l'autre (routes/seance_exo.py).

Retour du 14/10 : « le chrono n'enregistre pas si je le change ». La durée
touchée dans la barre ne valait que pour le repos en cours."""
from conftest import CSRF, USER_ID


def _programme(fake):
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push 1": [{"name": "Développé couché", "sets": 4, "muscle": "Pecs", "rest_seconds": 90, "id": "e_couche"},
                   {"name": "Écartés poulie", "sets": 3, "muscle": "Pecs", "rest_seconds": 90}],
        "_planning": {"Lundi": "Push 1"}, "_settings": {},
    }}).execute()


def _repos(client, **corps):
    return client.post("/seance/repos", json=corps, headers={"X-CSRFToken": CSRF})


def _exos(fake):
    return fake.tables["programs"][-1]["data"]["Push 1"]


def test_la_duree_choisie_est_ecrite_pour_cet_exercice(fake_db, logged_in):
    _programme(fake_db)
    r = _repos(logged_in, seance="Push 1", exo_id="e_couche", base="Développé couché", rest_seconds=120)
    assert r.status_code == 200 and r.get_json() == {"ok": True, "rest_seconds": 120}
    assert [e["rest_seconds"] for e in _exos(fake_db)] == [120, 90]


def test_sans_identifiant_on_retrouve_l_exercice_par_son_nom(fake_db, logged_in):
    _programme(fake_db)
    _repos(logged_in, seance="Push 1", exo_id="", base="Écartés poulie", rest_seconds=60)
    assert [e["rest_seconds"] for e in _exos(fake_db)] == [90, 60]


def test_les_bornes_de_l_editeur_s_appliquent(fake_db, logged_in):
    _programme(fake_db)
    _repos(logged_in, seance="Push 1", exo_id="e_couche", base="Développé couché", rest_seconds=900)
    assert _exos(fake_db)[0]["rest_seconds"] == 300


def test_un_exercice_ajoute_aujourd_hui_ne_touche_pas_le_programme(fake_db, logged_in):
    _programme(fake_db)
    r = _repos(logged_in, seance="Push 1", exo_id="", base="Pull-over", rest_seconds=60)
    assert r.status_code == 404
    assert [e["rest_seconds"] for e in _exos(fake_db)] == [90, 90]


def test_une_duree_illisible_est_refusee(fake_db, logged_in):
    _programme(fake_db)
    assert _repos(logged_in, seance="Push 1", base="Développé couché", rest_seconds="vite").status_code == 400
