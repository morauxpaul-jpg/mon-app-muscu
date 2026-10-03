"""Quotas coach et générateur non contournables en parallèle (audit du 03/10, M8)."""
import threading
import time

from core import quota


def test_reserver_borne_les_appels_simultanes():
    """Dix générations lancées ensemble, une déjà faite, limite 3 : deux
    passent. La base voit chaque réussite avant que sa réservation tombe."""
    nom, uid = "test-gen", "u-concurrent"
    en_base = [1]
    accordes = []

    def tente():
        if quota.reserver(nom, uid, lambda: en_base[0], limite=3):
            accordes.append(1)
            time.sleep(0.05)                  # l'appel à l'IA dure
            en_base[0] += 1                   # événement écrit (synchrone)
            quota.liberer(nom, uid)

    fils = [threading.Thread(target=tente) for _ in range(10)]
    [f.start() for f in fils]
    [f.join() for f in fils]
    assert len(accordes) == 2 and en_base[0] == 3
    assert not quota.reserver(nom, uid, lambda: en_base[0], limite=3)


def test_un_echec_rend_la_reservation():
    nom, uid = "test-gen", "u-echec"
    assert quota.reserver(nom, uid, lambda: 0, 1)
    assert not quota.reserver(nom, uid, lambda: 0, 1)     # l'autre est en cours
    quota.liberer(nom, uid)                               # échec : rien en base
    assert quota.reserver(nom, uid, lambda: 0, 1)


def test_quota_coach_relu_sous_verrou(fake_db, logged_in, monkeypatch):
    """Dix messages simultanés avec un profil lu avant : le compteur avance
    de dix, pas de un."""
    from conftest import USER_ID
    import routes.coach as coach
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip",
                                      "coach_quota_count": 0}).execute()
    from flask import g
    app = logged_in.application
    profil_perime = {"coach_quota_date": "", "coach_quota_count": 0}
    resultats = []

    def envoie():
        with app.test_request_context():
            g.user_id = USER_ID
            resultats.append(coach._check_and_bump_quota(dict(profil_perime))[0])

    fils = [threading.Thread(target=envoie) for _ in range(coach.DAILY_QUOTA + 5)]
    [f.start() for f in fils]
    [f.join() for f in fils]
    assert resultats.count(True) == coach.DAILY_QUOTA
    from core import db
    assert int(db.get_profile(USER_ID)["coach_quota_count"]) == coach.DAILY_QUOTA


def test_route_generateur_compte_les_generations_en_cours(fake_db, logged_in, monkeypatch):
    """Une génération déjà en cours occupe la dernière place : la suivante
    est refusée tout de suite, sans appeler l'IA. Un échec rend la place."""
    import sys
    import types
    from conftest import CSRF, USER_ID
    import routes.generator as gen
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    monkeypatch.setattr(gen, "_gen_used_week", lambda uid: gen.WEEKLY_GEN_QUOTA - 1)
    monkeypatch.setattr("routes.generator._env", lambda *a, **k: "cle-de-test", raising=False)
    appels = []

    class Client:
        def __init__(self, **k):
            self.messages = types.SimpleNamespace(create=self._create)

        def _create(self, **k):
            appels.append(1)
            raise RuntimeError("Internal server error")

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    entete = {"X-CSRFToken": CSRF}

    assert quota.reserver("generateur", USER_ID, lambda: gen.WEEKLY_GEN_QUOTA - 1, gen.WEEKLY_GEN_QUOTA)
    r = logged_in.post("/generator/generate", json={"objectif": "force"}, headers=entete)
    assert r.status_code == 429 and not appels
    quota.liberer("generateur", USER_ID)

    r = logged_in.post("/generator/generate", json={"objectif": "force"}, headers=entete)
    assert r.status_code == 502 and len(appels) == 1          # échec de l'IA
    r = logged_in.post("/generator/generate", json={"objectif": "force"}, headers=entete)
    assert r.status_code == 502 and len(appels) == 2          # la place a été rendue


def test_generation_reussie_renvoie_le_programme_et_le_quota(fake_db, logged_in, monkeypatch):
    import json
    import sys
    import types
    from conftest import CSRF, USER_ID
    import routes.generator as gen
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    monkeypatch.setattr("routes.generator._env", lambda *a, **k: "cle-de-test", raising=False)
    compte = [0]
    monkeypatch.setattr(gen, "_gen_used_week", lambda uid: compte[0])
    monkeypatch.setattr(gen, "track", lambda *a, **k: compte.__setitem__(0, compte[0] + 1))
    reponse = json.dumps({"name": "Force", "seances": {"A": [
        {"name": "Squat", "sets": 5, "reps": "5", "rest_seconds": 180, "muscle": "Quadriceps"}]},
        "planning": {"Lundi": "A"}})

    class Client:
        def __init__(self, **k):
            self.messages = types.SimpleNamespace(create=lambda **k: types.SimpleNamespace(
                content=[types.SimpleNamespace(text=reponse)]))

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    r = logged_in.post("/generator/generate", json={"objectif": "force"}, headers={"X-CSRFToken": CSRF})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    d = r.get_json()
    assert d["ok"] and d["program"]["seances"]["A"][0]["name"] == "Squat"
    assert d["quota_remaining"] == gen.WEEKLY_GEN_QUOTA - 1


def _ia_qui_repond(monkeypatch, texte, appels=None):
    import sys
    import types

    class Client:
        def __init__(self, **k):
            def create(**kw):
                if appels is not None:
                    appels.append(kw)
                return types.SimpleNamespace(content=[types.SimpleNamespace(text=texte)])
            self.messages = types.SimpleNamespace(create=create)

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    monkeypatch.setattr("routes.generator._env", lambda *a, **k: "cle-de-test", raising=False)


PROGRAMME = {"name": "P", "seances": {
    "Haut": [{"name": "Développé couché", "sets": 4, "reps": "8-10", "muscle": "Pecs"}],
    "Bas": [{"name": "Squat", "sets": 5, "reps": "5", "muscle": "Quadriceps"}]},
    "planning": {"Lundi": "Haut", "Jeudi": "Bas"}}


def test_refaire_une_seance_seulement(fake_db, logged_in, monkeypatch):
    import json
    from conftest import CSRF, USER_ID
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    appels = []
    _ia_qui_repond(monkeypatch, "```json\n" + json.dumps({"exercices": [
        {"name": "Pompes", "sets": 4, "reps": "12-15", "rest_seconds": 60, "muscle": "Pecs"}]}) + "\n```", appels)
    r = logged_in.post("/generator/seance", headers={"X-CSRFToken": CSRF}, json={
        "program": PROGRAMME, "seance": "Haut", "consigne": "sans machine",
        "params": {"lieu": "Maison"}})
    d = r.get_json()
    assert r.status_code == 200 and d["ok"] and d["exercices"][0]["name"] == "Pompes"
    prompt = appels[0]["messages"][0]["content"]
    assert "« Haut »" in prompt and "sans machine" in prompt and "Bas : Squat" in prompt
    assert appels[0]["max_tokens"] < 2600                    # une séance, pas un programme


def test_refaire_seance_entrees_invalides(fake_db, logged_in, monkeypatch):
    from conftest import CSRF, USER_ID
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    _ia_qui_repond(monkeypatch, "pas du json")
    h = {"X-CSRFToken": CSRF}
    assert logged_in.post("/generator/seance", headers=h, json={"program": PROGRAMME, "seance": "Jambes"}).status_code == 400
    assert logged_in.post("/generator/seance", headers=h, json={"program": "x", "seance": "Haut"}).status_code == 400
    assert logged_in.post("/generator/seance", headers=h, json={"program": PROGRAMME, "seance": "Haut"}).status_code == 502


def test_refaire_seance_reserve_au_pro(fake_db, logged_in):
    from conftest import CSRF, USER_ID
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    with logged_in.session_transaction() as s:            # compte gratuit
        s["is_vip"] = s["is_vip_full"] = False
    r = logged_in.post("/generator/seance", headers={"X-CSRFToken": CSRF},
                       json={"program": PROGRAMME, "seance": "Haut"})
    assert r.status_code == 403, r.get_data(as_text=True)[:400]
