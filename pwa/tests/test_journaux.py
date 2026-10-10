"""Journaux : INFO sur la sortie standard, WARNING et plus sur la sortie d'erreur.

Railway range en « error » tout ce qui sort sur la sortie d'erreur. Avec un
seul flux, chaque INFO y passait (audit du 06/10, m5).
"""
import io
import logging

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
