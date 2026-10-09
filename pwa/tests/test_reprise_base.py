"""Lecture coupée retentée une fois, et temps de chaque requête mesuré.

Audit du 06/10 :
* I-3 — le 05/10 à 06:26 UTC, la première requête du matin est tombée sur une
  connexion HTTP/2 que Supabase avait fermée pendant la nuit
  (`<ConnectionTerminated error_code:9 …>`) : `/seance` en 503. Une lecture
  coupée est maintenant rejouée une fois ; une écriture, jamais.
* I-2 — « Série faite » à 2 s en production sans cause isolée : chaque
  requête dit le temps passé à attendre la base et Redis.
"""
import logging

import httpx
import pytest
from flask import Response

from core import chrono, reprise_base


class _Envoi:
    """Échoue `echecs` fois avec `erreur`, puis répond."""

    def __init__(self, erreur, echecs=1):
        self.erreur, self.echecs, self.appels = erreur, echecs, 0

    def __call__(self, methode, *args, **kwargs):
        self.appels += 1
        if self.appels <= self.echecs:
            raise self.erreur
        return "réponse"


COUPURE = httpx.RemoteProtocolError("<ConnectionTerminated error_code:9, last_stream_id:11, "
                                    "additional_data:None>")


def test_une_lecture_coupee_est_rejouee_une_fois(caplog):
    envoi = _Envoi(COUPURE)
    assert reprise_base.avec_reprise(envoi, "GET", "/rest/v1/history") == "réponse"
    assert envoi.appels == 2
    assert "nouvelle tentative" in caplog.text


def test_une_seule_nouvelle_tentative():
    envoi = _Envoi(COUPURE, echecs=2)
    with pytest.raises(httpx.RemoteProtocolError):
        reprise_base.avec_reprise(envoi, "GET", "/rest/v1/history")
    assert envoi.appels == 2


@pytest.mark.parametrize("methode", ["POST", "PATCH", "DELETE"])
def test_une_ecriture_coupee_nest_jamais_rejouee(methode):
    """Elle a pu aboutir avant la coupure : la rejouer risquerait un doublon."""
    envoi = _Envoi(COUPURE)
    with pytest.raises(httpx.RemoteProtocolError):
        reprise_base.avec_reprise(envoi, methode, "/rest/v1/history")
    assert envoi.appels == 1


@pytest.mark.parametrize("erreur", [
    httpx.ReadTimeout("lent"),                       # rejouer doublerait l'attente
    Exception("{'code': '42703', 'message': 'column x does not exist'}"),   # erreur de la base
])
def test_ni_un_delai_ni_une_erreur_de_la_base_ne_sont_rejoues(erreur):
    envoi = _Envoi(erreur)
    with pytest.raises(type(erreur)):
        reprise_base.avec_reprise(envoi, "GET", "/rest/v1/history")
    assert envoi.appels == 1


@pytest.mark.parametrize("erreur", [httpx.ConnectError("refusée"), httpx.ReadError("coupée"),
                                    Exception("<ConnectionTerminated error_code:9>")])
def test_les_autres_coupures_sont_reconnues(erreur):
    assert reprise_base.est_coupure(erreur)


def test_de_bout_en_bout_a_travers_le_vrai_client_postgrest():
    """Le client postgrest réel, branché sur un transport simulé dont la
    première réponse est une coupure : la lecture aboutit quand même."""
    from postgrest import SyncPostgrestClient
    from postgrest.utils import SyncClient
    assert reprise_base.installer()
    appels = []

    def transport(requete):
        appels.append(requete.method)
        if len(appels) == 1:
            raise httpx.RemoteProtocolError("<ConnectionTerminated error_code:9>", request=requete)
        return httpx.Response(200, json=[{"id": 1}])

    pg = SyncPostgrestClient("http://base.test/rest/v1")
    pg.session = SyncClient(base_url="http://base.test/rest/v1",
                            transport=httpx.MockTransport(transport))
    assert pg.from_("history").select("id").execute().data == [{"id": 1}]
    assert appels == ["GET", "GET"]

    appels.clear()
    with pytest.raises(httpx.RemoteProtocolError):
        pg.from_("history").insert({"id": 2}).execute()
    assert appels == ["POST"]


# ── Chronométrage ─────────────────────────────────────────────────


def test_le_temps_base_et_redis_part_dans_server_timing():
    from app import app
    with app.test_request_context("/seance/save-exo", method="POST"):
        chrono.debut()
        chrono.ajouter("base", 0.5)
        chrono.ajouter("base", 0.7)
        chrono.ajouter("redis", 0.1)
        r = chrono.terminer(Response("ok"), "POST", "/seance/save-exo")
    entete = r.headers["Server-Timing"]
    assert 'base;dur=1200;desc="2 appels"' in entete
    assert 'redis;dur=100;desc="1 appel"' in entete
    assert "total;dur=" in entete


def test_une_requete_lente_est_journalisee_avec_le_detail(monkeypatch, caplog):
    from app import app
    caplog.set_level(logging.INFO, logger="core.chrono")
    monkeypatch.setattr(chrono, "SEUIL_LENT_MS", -1)
    with app.test_request_context("/seance/save-exo", method="POST"):
        chrono.debut()
        chrono.ajouter("base", 1.5)
        chrono.ajouter("redis", 0.2)
        chrono.terminer(Response("ok"), "POST", "/seance/save-exo")
    assert "lent : POST /seance/save-exo" in caplog.text
    assert "base 1500 ms (1 requêtes)" in caplog.text and "redis 200 ms (1 appels)" in caplog.text


def test_une_requete_rapide_nest_pas_journalisee(caplog):
    from app import app
    caplog.set_level(logging.INFO, logger="core.chrono")
    with app.test_request_context("/accueil"):
        chrono.debut()
        chrono.terminer(Response("ok"), "GET", "/accueil")
    assert "lent" not in caplog.text


def test_chaque_reponse_porte_server_timing(fake_db, logged_in):
    r = logged_in.get("/accueil")
    assert "total;dur=" in r.headers.get("Server-Timing", "")


def test_les_appels_redis_sont_comptes(fake_db):
    import fakeredis
    from app import app
    from core import partage
    partage.utiliser(fakeredis.FakeRedis(decode_responses=True))
    try:
        with app.test_request_context("/"):
            chrono.debut()
            partage.nouvelle_generation("hist:u-test")
            r = chrono.terminer(Response("ok"), "GET", "/")
        assert "redis;dur=" in r.headers["Server-Timing"]
    finally:
        partage.utiliser(None)
