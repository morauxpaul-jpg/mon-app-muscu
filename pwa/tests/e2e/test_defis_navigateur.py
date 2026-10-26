"""Défis entre amis, de bout en bout, à deux comptes amis : Paul lance un
défi de régularité qui commence aujourd'hui, Marc l'accepte, termine une
séance, et le classement bouge chez Paul — page Amis et accueil."""
import pytest

from tests.e2e.test_amis_navigateur import _page, _terminer_une_seance

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect


def test_un_defi_lance_accepte_et_le_classement_bouge(serveur, navigateur):
    navigateur.new_page().goto(serveur + "/test-vierge")      # base neuve
    paul = _page(navigateur, serveur, "u-paul", "Paul", "paulpaul")
    marc = _page(navigateur, serveur, "u-marc", "Marc", "marcmarc")

    # Amis d'abord : Marc envoie sa demande avec le code de Paul, Paul accepte.
    marc.locator("#amis-code-ami").fill("PAULPAUL")
    marc.locator("#amis-ajouter .amis-form-code button").click()
    expect(marc.locator("#amis-message")).to_contain_text("Demande envoyée")
    paul.goto(serveur + "/amis")
    paul.get_by_role("button", name="Accepter Marc").click()
    expect(paul.locator("#amis-liste")).to_contain_text("Marc")

    # Paul lance le défi : régularité, 1 semaine, à partir d'aujourd'hui, avec Marc.
    form = paul.locator("#defi-lancer")
    expect(form).to_have_attribute("open", "")
    form.get_by_label("Régularité", exact=False).check()
    form.get_by_label("1 semaine", exact=True).check()
    form.locator("#defi-depart").select_option("aujourdhui")
    form.get_by_label("Marc").check()
    form.get_by_role("button", name="Lancer le défi").click()
    expect(paul.locator("#amis-message")).to_contain_text("Défi lancé")
    defi = paul.locator("article.defi", has_text="Régularité")
    expect(defi).to_contain_text("Pas encore répondu : Marc")

    # Marc reçoit l'invitation et l'accepte.
    marc.goto(serveur + "/amis")
    invitation = marc.locator("article.defi-invitation")
    expect(invitation).to_contain_text("Paul te lance un défi")
    invitation.get_by_role("button", name="Accepter le défi de Paul").click()
    expect(marc.locator("#amis-message")).to_contain_text("tu es dans le défi")
    classement = marc.locator("article.defi .defi-classement")
    expect(classement.locator("li")).to_have_count(2)
    expect(classement).to_contain_text("0 séance")

    # Avant la séance : à égalité, Paul (« Toi ») est classé avec Marc.
    paul.goto(serveur + "/amis")
    lignes = paul.locator("article.defi .defi-classement li")
    expect(lignes).to_have_count(2)
    expect(lignes.nth(0)).to_contain_text("0 séance")
    expect(lignes.nth(1)).to_contain_text("0 séance")

    # Marc termine une séance : il passe premier chez Paul, sur la page Amis et l'accueil.
    _terminer_une_seance(marc, serveur)
    paul.goto(serveur + "/amis")
    expect(lignes.nth(0)).to_contain_text("Marc")
    expect(lignes.nth(0)).to_contain_text("1 séance")
    expect(lignes.nth(0).locator(".defi-rang")).to_have_text("1")
    expect(lignes.nth(1)).to_contain_text("Toi")
    expect(lignes.nth(1).locator(".defi-rang")).to_have_text("2")
    paul.goto(serveur + "/accueil")
    carte = paul.locator("#defis-accueil")
    expect(carte).to_contain_text("Régularité")
    expect(carte.locator(".defi-acc-ligne").nth(0)).to_contain_text("Marc")
    expect(carte.locator(".defi-acc-ligne").nth(0)).to_contain_text("1 séance")

    for p in (paul, marc):
        assert p.erreurs == [], p.erreurs
