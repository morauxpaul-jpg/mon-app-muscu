"""La fin du repos annoncée par le serveur, écran éteint compris.

Retour du 14/10 : « notification qui ne s'affiche pas toujours, quand
j'éteins l'écran je n'ai rien ». Dans l'app installée depuis Chrome, le
minuteur du téléphone gèle avec l'écran ; seul un push du serveur le
réveille (core/push_repos.py)."""
import sys
import types

import pytest

from conftest import CSRF, USER_ID
from core import partage, push, push_repos

ABO = {"endpoint": "https://push.test/abc", "keys": {"p256dh": "p", "auth": "a"}}


@pytest.fixture(autouse=True)
def _propre(monkeypatch):
    partage.reinitialiser()
    push_repos._file.clear()
    monkeypatch.setattr(push_repos, "_demarrer", lambda: None)   # pas de fil en test
    envois = []
    monkeypatch.setattr(push, "send_push",
                        lambda abo, charge, ttl=0, urgence="": envois.append((abo, charge, ttl, urgence)) or "ok")
    yield envois
    push_repos._file.clear()


def test_le_push_part_a_la_fin_du_repos_en_urgence(_propre):
    push_repos.programmer(USER_ID, ABO, 90, nom="Squat", url="/seance?mode=prefaite&name=Jambes", maintenant=1000)
    assert push_repos.envoyer_les_echus(maintenant=1089) == 0, "pas avant la fin"
    assert push_repos.envoyer_les_echus(maintenant=1090) == 1
    abo, charge, ttl, urgence = _propre[0]
    assert abo == ABO and urgence == "high" and ttl == push_repos.TTL_PUSH
    assert charge == {"title": "Repos terminé", "body": "Squat : série suivante",
                      "url": "/seance?mode=prefaite&name=Jambes", "tag": "rest-timer"}
    assert push_repos.envoyer_les_echus(maintenant=2000) == 0, "une seule fois"


def test_passer_le_repos_annule_le_push(_propre):
    push_repos.programmer(USER_ID, ABO, 90, maintenant=1000)
    push_repos.annuler(USER_ID, ABO["endpoint"])
    assert push_repos.envoyer_les_echus(maintenant=1100) == 0
    assert _propre == []


def test_un_nouveau_repos_remplace_le_precedent(_propre):
    push_repos.programmer(USER_ID, ABO, 90, nom="Squat", maintenant=1000)
    push_repos.programmer(USER_ID, ABO, 120, nom="Fentes", maintenant=1030)
    assert push_repos.envoyer_les_echus(maintenant=1100) == 0, "l'ancien ne part pas"
    assert push_repos.envoyer_les_echus(maintenant=1150) == 1
    assert _propre[0][1]["body"] == "Fentes : série suivante"


def test_une_duree_qui_n_est_pas_un_repos_est_ignoree():
    assert push_repos.programmer(USER_ID, ABO, 0, maintenant=1000) is None
    assert push_repos.programmer(USER_ID, ABO, 3600, maintenant=1000) is None
    assert push_repos.programmer(USER_ID, ABO, "vite", maintenant=1000) is None


def test_l_envoi_reveille_le_telephone(monkeypatch):
    """Urgency: high et TTL court arrivent bien jusqu'à pywebpush."""
    import importlib
    vrai = importlib.reload(push)        # sans le faux send_push de la fixture
    appels = []
    monkeypatch.setitem(sys.modules, "pywebpush", types.SimpleNamespace(
        webpush=lambda **k: appels.append(k), WebPushException=Exception))
    monkeypatch.setitem(sys.modules, "py_vapid", types.SimpleNamespace(
        Vapid01=types.SimpleNamespace(from_raw=lambda b: "cle")))
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    assert vrai.send_push(ABO, {"title": "x"}, ttl=120, urgence="high") == "ok"
    assert appels[0]["ttl"] == 120 and appels[0]["headers"] == {"Urgency": "high"}
    assert vrai.send_push(ABO, {"title": "x"}) == "ok"
    assert appels[1]["ttl"] == 24 * 3600 and appels[1]["headers"] is None, "les relances ne changent pas"


# ── Les routes ──────────────────────────────────────────────────


def _abonner(fake_db):
    fake_db.table("push_subscriptions").insert({"user_id": USER_ID, "endpoint": ABO["endpoint"],
                                                "p256dh": "p", "auth": "a"}).execute()


def test_la_route_programme_vers_son_propre_appareil(fake_db, logged_in, monkeypatch):
    monkeypatch.setattr(push, "is_configured", lambda: True)
    _abonner(fake_db)
    r = logged_in.post("/push/repos", headers={"X-CSRFToken": CSRF},
                       json={"endpoint": ABO["endpoint"], "dans": 90, "nom": "Squat", "url": "/seance"})
    assert r.status_code == 200 and r.get_json() == {"ok": True}
    assert len(push_repos._file) == 1 and push_repos._file[0][3] == ABO


def test_un_appareil_inconnu_est_refuse(fake_db, logged_in, monkeypatch):
    monkeypatch.setattr(push, "is_configured", lambda: True)
    r = logged_in.post("/push/repos", headers={"X-CSRFToken": CSRF},
                       json={"endpoint": "https://push.test/autre", "dans": 90})
    assert r.status_code == 404 and push_repos._file == []


def test_la_notification_ne_renvoie_que_vers_l_app(fake_db, logged_in, monkeypatch):
    monkeypatch.setattr(push, "is_configured", lambda: True)
    _abonner(fake_db)
    logged_in.post("/push/repos", headers={"X-CSRFToken": CSRF},
                   json={"endpoint": ABO["endpoint"], "dans": 90, "url": "https://ailleurs.test"})
    assert push_repos._file[0][5] == "/seance"


def test_annuler_par_la_route(fake_db, logged_in, monkeypatch, _propre):
    monkeypatch.setattr(push, "is_configured", lambda: True)
    _abonner(fake_db)
    logged_in.post("/push/repos", headers={"X-CSRFToken": CSRF}, json={"endpoint": ABO["endpoint"], "dans": 1})
    assert logged_in.post("/push/repos/annuler", headers={"X-CSRFToken": CSRF},
                          json={"endpoint": ABO["endpoint"]}).status_code == 204
    import time
    assert push_repos.envoyer_les_echus(maintenant=time.time() + 5) == 0
