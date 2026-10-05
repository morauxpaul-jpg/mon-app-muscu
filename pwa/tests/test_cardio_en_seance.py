"""Deux blocs du même cardio dans une séance sont deux blocs (audit du 30/09, I6).

10 min de rameur en échauffement puis 8 min en finisher : `add-cardio`
remplaçait le premier par le second (1 ligne, 8 min), et un échec
d'écriture était avalé puis la page revenait comme si tout allait bien.
"""
from conftest import USER_ID, CSRF
from test_cardio_mesures import compte, JOUR  # noqa: F401  (fixture)


def _ajouter(client, minutes):
    return client.post("/seance/add-cardio", data={
        "mode": "prefaite", "name": "Push", "seance_name": "Push", "date": JOUR,
        "activite": "Rameur", "duree_min": str(minutes), "distance_km": "",
        "vitesse": "", "_csrf": CSRF,
    }, headers={"X-CSRFToken": CSRF})


def _rameur(fake):
    return sorted((r["serie"], r["duree_min"]) for r in fake.tables.get("history", [])
                  if r["exercice"] == "CARDIO:Rameur")


def test_deux_blocs_du_meme_cardio_sont_gardes(compte, logged_in):
    _ajouter(logged_in, 10)
    _ajouter(logged_in, 8)
    assert _rameur(compte) == [(1, 10), (2, 8)]


def test_supprimer_un_bloc_garde_lautre(compte, logged_in):
    _ajouter(logged_in, 10)
    _ajouter(logged_in, 8)
    logged_in.post("/seance/delete-cardio", data={
        "mode": "prefaite", "name": "Push", "seance_name": "Push", "date": JOUR,
        "activite": "Rameur", "serie": "1", "_csrf": CSRF,
    }, headers={"X-CSRFToken": CSRF})
    assert _rameur(compte) == [(2, 8)]


def test_la_page_de_seance_montre_les_deux_blocs(compte, logged_in):
    _ajouter(logged_in, 10)
    _ajouter(logged_in, 8)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={JOUR}").get_data(as_text=True)
    assert html.count('name="activite" value="Rameur"') >= 2
    assert 'name="serie" value="2"' in html


def test_un_echec_decriture_se_voit(compte, logged_in, monkeypatch):
    import core.db_historique as dh

    def panne(*a, **k):
        raise RuntimeError("coupure")

    monkeypatch.setattr(dh, "_insert_history", panne)
    r = _ajouter(logged_in, 10)
    assert r.status_code == 503
    assert "pas pu être enregistré" in r.get_data(as_text=True)
