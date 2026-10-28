"""Journaux : INFO sur la sortie standard, WARNING et plus sur la sortie d'erreur.

Railway range en « error » tout ce qui sort sur la sortie d'erreur. Avec un
seul flux, chaque INFO y passait (audit du 06/10, m5).
"""
import io
import logging

import pytest

import app as appmod


def _journal():
    sortie, erreurs = io.StringIO(), io.StringIO()
    appmod._journal_sortie.setStream(sortie)
    appmod._journal_erreurs.setStream(erreurs)
    log = logging.getLogger("test.journaux")
    log.handlers = [appmod._journal_sortie, appmod._journal_erreurs]
    log.propagate = False
    log.setLevel(logging.DEBUG)
    return log, sortie, erreurs


def test_info_va_sur_la_sortie_standard_seulement():
    anciens = (appmod._journal_sortie.stream, appmod._journal_erreurs.stream)
    try:
        log, sortie, erreurs = _journal()
        log.info("tout va bien")
        assert "INFO tout va bien" in sortie.getvalue()
        assert erreurs.getvalue() == ""
    finally:
        appmod._journal_sortie.setStream(anciens[0])
        appmod._journal_erreurs.setStream(anciens[1])


def test_warning_et_erreur_vont_sur_la_sortie_d_erreur_seulement():
    anciens = (appmod._journal_sortie.stream, appmod._journal_erreurs.stream)
    try:
        log, sortie, erreurs = _journal()
        log.warning("attention")
        log.error("ça casse")
        assert sortie.getvalue() == ""
        assert "WARNING attention" in erreurs.getvalue()
        assert "ERROR ça casse" in erreurs.getvalue()
    finally:
        appmod._journal_sortie.setStream(anciens[0])
        appmod._journal_erreurs.setStream(anciens[1])


def test_gunicorn_aussi_info_sur_la_sortie_standard(monkeypatch):
    """« Starting gunicorn », « Booting worker » sortaient en « error »."""
    # gunicorn ne s'importe que sous Unix (fcntl, grp) : la production et la CI
    # tournent sous Linux ; sous Windows, ce test n'a rien à vérifier.
    pytest.importorskip("fcntl", reason="gunicorn : Unix seulement")
    import importlib.util
    import pathlib
    import sys
    from gunicorn.config import Config
    sortie, erreurs = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", sortie)
    monkeypatch.setattr(sys, "stderr", erreurs)
    chemin = pathlib.Path(__file__).resolve().parents[1] / "gunicorn.conf.py"
    spec = importlib.util.spec_from_file_location("conf_gunicorn", chemin)
    conf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conf)
    cfg = Config()
    cfg.set("errorlog", "-")
    cfg.set("logger_class", conf.logger_class)
    log = cfg.logger_class(cfg)
    log.info("Starting gunicorn 23.0.0")
    log.warning("Worker timeout")
    assert "Starting gunicorn" in sortie.getvalue()
    assert "Starting gunicorn" not in erreurs.getvalue()
    assert "Worker timeout" in erreurs.getvalue()
    assert "Worker timeout" not in sortie.getvalue()


def _requete_simulee(module):
    """Une vraie requête httpx (ou httpx2), servie sans réseau."""
    simule = module.MockTransport(lambda r: module.Response(200, json=[]))
    with module.Client(transport=simule) as client:
        client.get("https://exemple.supabase.co/rest/v1/nutrition?user_id=eq.0000-uuid")


def test_les_requetes_http_ne_sont_plus_journalisees():
    """Une ligne INFO « HTTP Request: GET …&user_id=eq.<uuid> » par appel à
    Supabase : du bruit, et l'identifiant de chaque compte dans les journaux.
    httpx sert supabase, httpx2 anthropic 1.x."""
    import httpx
    import httpx2
    anciens = (appmod._journal_sortie.stream, appmod._journal_erreurs.stream)
    noms = ("httpx", "httpx2")
    loggers = [logging.getLogger(n) for n in noms]
    etats = [(lg.handlers, lg.propagate) for lg in loggers]
    racine = logging.getLogger()
    niveau_racine = racine.level
    try:
        # En production, la racine est en INFO (app.py). Sous pytest,
        # basicConfig ne s'applique pas : on la remet comme en production.
        racine.setLevel(logging.INFO)
        sortie, erreurs = io.StringIO(), io.StringIO()
        appmod._journal_sortie.setStream(sortie)
        appmod._journal_erreurs.setStream(erreurs)
        for lg in loggers:
            lg.handlers = [appmod._journal_sortie, appmod._journal_erreurs]
            lg.propagate = False
        _requete_simulee(httpx)
        _requete_simulee(httpx2)
        assert "HTTP Request" not in sortie.getvalue()
        assert "user_id" not in sortie.getvalue() + erreurs.getvalue()
        # Une vraie erreur réseau doit encore se voir.
        loggers[0].warning("connexion refusée")
        loggers[1].error("délai dépassé")
        assert "httpx WARNING connexion refusée" in erreurs.getvalue()
        assert "httpx2 ERROR délai dépassé" in erreurs.getvalue()
    finally:
        appmod._journal_sortie.setStream(anciens[0])
        appmod._journal_erreurs.setStream(anciens[1])
        racine.setLevel(niveau_racine)
        for lg, (handlers, propagate) in zip(loggers, etats):
            lg.handlers, lg.propagate = handlers, propagate


def test_httpcore_aussi_au_niveau_warning():
    racine = logging.getLogger()
    niveau_racine = racine.level
    try:
        racine.setLevel(logging.INFO)  # comme en production (app.py)
        for nom in ("httpcore", "httpcore.http11", "httpcore2", "httpcore2.connection"):
            lg = logging.getLogger(nom)
            assert not lg.isEnabledFor(logging.INFO), nom
            assert lg.isEnabledFor(logging.WARNING), nom
    finally:
        racine.setLevel(niveau_racine)
