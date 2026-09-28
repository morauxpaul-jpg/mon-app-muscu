"""Un refus admin doit rester muet dehors, et parlant dans les logs.

`_require_admin()` répond 404 — jamais 403 — pour qu'un inconnu ne puisse pas
deviner que `/admin` existe. C'est le bon choix, mais il rendait le refus
indéchiffrable **pour l'administrateur lui-même** : variable `ADMIN_EMAILS`
absente et adresse non autorisée donnaient le même écran vide.

Ces tests tiennent les deux bouts : le 404 dehors, et une trace qui nomme la
cause dans le journal de l'hébergeur — sans y recopier d'adresse.
"""
import logging

import pytest

from conftest import USER_ID

PAGES = ("/admin", "/admin/blob", "/admin/newsletter-emails")


@pytest.fixture()
def journal(caplog):
    caplog.set_level(logging.WARNING, logger="routes.admin")
    return caplog


# ── Le refus reste un 404 ────────────────────────────────────────────────

@pytest.mark.parametrize("page", PAGES)
def test_sans_variable_denvironnement_cest_404(page, fake_db, logged_in, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    assert logged_in.get(page).status_code == 404


@pytest.mark.parametrize("page", PAGES)
def test_avec_une_autre_adresse_cest_404(page, fake_db, logged_in, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "quelquun@example.com")
    assert logged_in.get(page).status_code == 404


def test_ladmin_passe(fake_db, logged_in, monkeypatch):
    """Le garde-fou ne doit pas fermer la porte à qui de droit."""
    monkeypatch.setenv("ADMIN_EMAILS", "test@example.com")
    assert logged_in.get("/admin/blob").status_code == 200


def test_la_casse_et_les_espaces_ne_bloquent_pas(fake_db, logged_in, monkeypatch):
    """Une variable recopiée à la main porte souvent une majuscule ou un espace."""
    monkeypatch.setenv("ADMIN_EMAILS", "  Autre@Example.com , TEST@Example.COM ")
    assert logged_in.get("/admin/blob").status_code == 200


# ── Le journal nomme la cause ────────────────────────────────────────────

def test_le_journal_distingue_la_variable_absente(fake_db, logged_in, monkeypatch, journal):
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    logged_in.get("/admin/blob")
    assert "ADMIN_EMAILS absente" in journal.text


def test_le_journal_distingue_ladresse_non_autorisee(fake_db, logged_in, monkeypatch, journal):
    monkeypatch.setenv("ADMIN_EMAILS", "quelquun@example.com")
    logged_in.get("/admin/blob")
    assert "n'est pas dans ADMIN_EMAILS" in journal.text
    assert "ADMIN_EMAILS absente" not in journal.text


def test_le_journal_ne_recopie_aucune_adresse(fake_db, logged_in, monkeypatch, journal):
    """Un log part souvent chez un tiers : il ne doit pas transporter d'adresse.

    Ni celle de la session, ni le contenu de la variable — seulement leur
    nombre, qui suffit à voir qu'elle est mal remplie.
    """
    monkeypatch.setenv("ADMIN_EMAILS", "quelquun@example.com,autre@example.com")
    logged_in.get("/admin/blob")
    for fuite in ("quelquun@example.com", "autre@example.com",
                  "test@example.com", USER_ID):
        assert fuite not in journal.text, f"le journal recopie : {fuite}"
    assert "en compte 2" in journal.text


def test_le_journal_dit_quelle_page_a_ete_refusee(fake_db, logged_in, monkeypatch, journal):
    """Sans le chemin, on ne sait pas si c'est la page cherchée qui a refusé."""
    monkeypatch.setenv("ADMIN_EMAILS", "quelquun@example.com")
    logged_in.get("/admin/blob")
    assert "/admin/blob" in journal.text


def test_un_admin_qui_passe_ne_laisse_pas_de_refus(fake_db, logged_in, monkeypatch, journal):
    monkeypatch.setenv("ADMIN_EMAILS", "test@example.com")
    logged_in.get("/admin/blob")
    assert "admin refuse" not in journal.text
