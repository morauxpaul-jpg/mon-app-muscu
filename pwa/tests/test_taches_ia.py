"""Génération IA en tâche de fond (audit du 03/10, I11).

L'appel à l'IA tenait un fil du serveur 10 à 25 s. Il tourne désormais dans
un groupe de fils dédié (`core/taches_ia.py`) : la requête rend la main au
bout de 2 s au plus avec un identifiant, la page réinterroge
`/generator/tache/<id>`.
"""
import json
import sys
import threading
import time
import types

import pytest

from conftest import CSRF, USER_ID
from core import quota, taches_ia
import routes.generator as gen

PROGRAMME = json.dumps({"name": "Force", "seances": {"A": [
    {"name": "Squat", "sets": 5, "reps": "5", "rest_seconds": 180, "muscle": "Quadriceps"}]},
    "planning": {"Lundi": "A"}})


@pytest.fixture()
def ia_lente(fake_db, monkeypatch):
    """Une IA qui répond quand on la libère : on contrôle la durée."""
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    monkeypatch.setattr("routes.generator._env", lambda *a, **k: "cle-de-test", raising=False)
    monkeypatch.setattr(taches_ia, "ATTENTE_REQUETE", 0.05)
    monkeypatch.setattr(gen, "track", lambda *a, **k: None)
    monkeypatch.setattr(gen, "_gen_used_week", lambda uid: 0)
    feu = threading.Event()
    appels = []

    class Client:
        def __init__(self, **k):
            self.messages = types.SimpleNamespace(create=self._create)

        def _create(self, **k):
            appels.append(1)
            feu.wait(5)
            return types.SimpleNamespace(content=[types.SimpleNamespace(text=PROGRAMME)])

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    yield feu, appels
    feu.set()


def _attendre_fin(client, tid, delai=5):
    fin = time.time() + delai
    while time.time() < fin:
        r = client.get(f"/generator/tache/{tid}")
        if r.status_code != 202:
            return r
        time.sleep(0.05)
    raise AssertionError("la tâche ne s'est pas terminée")


def test_la_requete_rend_la_main_pendant_que_lia_travaille(logged_in, ia_lente):
    feu, appels = ia_lente
    debut = time.time()
    r = logged_in.post("/generator/generate", json={"objectif": "Force"}, headers={"X-CSRFToken": CSRF})
    assert time.time() - debut < 1.5            # le fil du serveur est libéré
    assert r.status_code == 202
    tid = r.get_json()["tache"]
    assert logged_in.get(f"/generator/tache/{tid}").status_code == 202
    feu.set()
    fin = _attendre_fin(logged_in, tid)
    assert fin.status_code == 200 and fin.get_json()["program"]["seances"]["A"][0]["name"] == "Squat"
    assert len(appels) == 1


def test_un_second_tap_rejoint_la_generation_en_cours(logged_in, ia_lente):
    feu, appels = ia_lente
    h = {"X-CSRFToken": CSRF}
    t1 = logged_in.post("/generator/generate", json={}, headers=h).get_json()["tache"]
    t2 = logged_in.post("/generator/generate", json={}, headers=h).get_json()["tache"]
    assert t1 == t2
    feu.set()
    _attendre_fin(logged_in, t1)
    assert len(appels) == 1


def test_la_place_du_quota_est_rendue_quand_la_tache_finit(logged_in, ia_lente):
    feu, _ = ia_lente
    tid = logged_in.post("/generator/generate", json={}, headers={"X-CSRFToken": CSRF}).get_json()["tache"]
    assert quota._EN_COURS.get(("generateur", USER_ID)) == 1      # réservée pendant le calcul
    feu.set()
    _attendre_fin(logged_in, tid)
    assert quota._EN_COURS.get(("generateur", USER_ID)) == 0


def test_la_tache_dun_autre_compte_est_introuvable(logged_in, ia_lente, monkeypatch):
    feu, _ = ia_lente
    tid = taches_ia.lancer("autre-compte", "programme", lambda: ({"ok": True}, 200))
    taches_ia.attendre(tid, 1)
    assert logged_in.get(f"/generator/tache/{tid}").status_code == 404
    assert logged_in.get("/generator/tache/nimportequoi").status_code == 404


def test_une_tache_trop_longue_est_declaree_perdue(monkeypatch):
    feu = threading.Event()
    tid = taches_ia.lancer(USER_ID, "programme", lambda: (feu.wait(5), ({"ok": True}, 200))[1])
    monkeypatch.setattr(taches_ia, "DUREE_MAX", 0.0)
    time.sleep(0.01)
    corps, code = taches_ia.lire(tid, USER_ID)
    assert code == 504
    feu.set()


def test_une_exception_dans_la_tache_devient_une_erreur_propre():
    def boum():
        raise RuntimeError("secret interne")
    tid = taches_ia.lancer(USER_ID, "programme", boum)
    corps, code = taches_ia.reponse(tid, USER_ID, 2)
    assert code == 500 and "secret" not in json.dumps(corps)


def test_la_page_suit_la_tache_et_reprend_apres_un_rechargement(fake_db, logged_in):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    html = logged_in.get("/generator").get_data(as_text=True)
    assert "/generator/tache/" in html and "sessionStorage" in html
    assert "la génération continue" in html
