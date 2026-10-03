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
