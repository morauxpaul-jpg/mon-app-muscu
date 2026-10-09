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
