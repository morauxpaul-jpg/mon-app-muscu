"""Refaire une séance le même jour (core/passes_seance.py).

Retour du 14/10 : « si je veux refaire la séance deux fois d'affilée, je ne
peux pas, cela me remet dessus ». Rouvrir Push le jour même rouvrait celle
déjà faite (cochée, remplie), et « Recommencer » l'effaçait."""
import json

from conftest import USER_ID, CSRF
from core.dates import logical_today_paris
from core.passes_seance import prochaine_passe, seance_de_base

JSON_HEADERS = {"Accept": "application/json", "X-CSRFToken": CSRF}


def test_une_seconde_passe_retrouve_sa_seance():
    seances = {"Push 1", "Pull", "Jambes · 2"}
    assert seance_de_base("Push 1 · 2", seances) == "Push 1"
    assert seance_de_base("Push 1 · 3", seances) == "Push 1"
    assert seance_de_base("Push 1", seances) == "Push 1"
    assert seance_de_base("Jambes · 2", seances) == "Jambes · 2", "un vrai nom de séance reste le sien"
    assert seance_de_base("Inconnue · 2", seances) == "Inconnue · 2"


def test_la_passe_suivante_saute_celles_deja_faites():
    jour = "2026-10-15"
    hist = [{"Date": jour, "Séance": "Push"}, {"Date": jour, "Séance": "Push · 2"},
            {"Date": "2026-10-14", "Séance": "Push · 3"}]
    assert prochaine_passe("Push", hist, jour) == "Push · 3"
    assert prochaine_passe("Pull", hist, jour) == "Pull · 2"


# ── Dans l'app ──────────────────────────────────────────────────


def _programme(fake_db):
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs", "reps": "8-12"}],
        "_planning": {"Lundi": "Push"},
    }}).execute()


def _serie(client, seance, reps):
    return client.post("/seance/save-exo", headers=JSON_HEADERS, data={
        "_csrf": CSRF, "seance_name": seance, "exo_base": "Développé couché",
        "variant": "Standard", "muscle": "Pecs", "date": logical_today_paris().isoformat(),
        "mode": "prefaite", "name": seance, "partiel": "1",
        "sets_json": json.dumps([{"reps": reps, "poids": 60}])})


def _lignes(fake_db, seance):
    return [r for r in fake_db.tables.get("history", []) if r["seance"] == seance]


def test_une_seance_faite_peut_etre_refaite_a_part(fake_db, logged_in):
    _programme(fake_db)
    auj = logical_today_paris().isoformat()
    assert _serie(logged_in, "Push", 10).status_code == 200

    choix = logged_in.get(f"/seance?date={auj}").get_data(as_text=True)
    assert "Refaire Push" in choix
    assert f"name=Push%20%C2%B7%202&date={auj}" in choix

    page = logged_in.get("/seance", query_string={"mode": "prefaite", "name": "Push · 2", "date": auj})
    html = page.get_data(as_text=True)
    assert page.status_code == 200 and "DÉVELOPPÉ COUCHÉ" in html
    assert 'name="seance_name" value="Push · 2"' in html

    assert _serie(logged_in, "Push · 2", 8).status_code == 200
    assert [r["reps"] for r in _lignes(fake_db, "Push")] == [10], "la première passe reste intacte"
    assert [r["reps"] for r in _lignes(fake_db, "Push · 2")] == [8]


def test_terminer_la_seconde_passe_lui_donne_son_propre_bilan(fake_db, logged_in):
    _programme(fake_db)
    auj = logical_today_paris().isoformat()
    _serie(logged_in, "Push", 10)
    logged_in.post("/seance/finish", data={"_csrf": CSRF, "mode": "prefaite", "seance_name": "Push",
                                           "date": auj, "rating": "3", "comment": "lourd"})
    _serie(logged_in, "Push · 2", 8)
    r = logged_in.post("/seance/finish", data={"_csrf": CSRF, "mode": "prefaite", "seance_name": "Push · 2",
                                               "date": auj, "rating": "5", "comment": "mieux"})
    assert r.status_code == 302
    bilans = {n["seance"]: n["comment"] for n in fake_db.tables["session_notes"]}
    assert bilans == {"Push": "lourd", "Push · 2": "mieux"}


def test_la_premiere_passe_se_rouvre_toujours_remplie(fake_db, logged_in):
    _programme(fake_db)
    auj = logical_today_paris().isoformat()
    _serie(logged_in, "Push", 10)
    _serie(logged_in, "Push · 2", 8)
    html = logged_in.get("/seance", query_string={"mode": "prefaite", "name": "Push", "date": auj}).get_data(as_text=True)
    assert "Mettre à jour" in html
    choix = logged_in.get(f"/seance?date={auj}").get_data(as_text=True)
    assert "Push%20%C2%B7%203" in choix, "la suivante serait la troisième"
