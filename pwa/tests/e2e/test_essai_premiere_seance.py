"""Essai PRO ouvert par la première séance, de bout en bout (audit du 18/10, I-4)."""
import os

import pytest


@pytest.fixture()
def pg(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 390, "height": 844}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('notifPrompted','1');localStorage.setItem('tutoSeen','true');"
                        "localStorage.setItem('tutoSeanceSeen','true');")
    page = ctx.new_page()
    page.erreurs = []
    page.on("pageerror", lambda e: page.erreurs.append(str(e)))
    page.goto(serveur + "/test-vierge")          # compte gratuit, jamais d'essai
    yield page
    ctx.close()


def test_terminer_sa_premiere_seance_ouvre_l_essai(pg, serveur):
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    pg.wait_for_selector("#exo-anchor-0")
    pg.evaluate("Alpine.$data(document.querySelector('#exo-anchor-0')).open = true")
    carte = pg.locator("#exo-anchor-0")
    carte.get_by_label("Répétitions série 1", exact=True).fill("5")
    carte.get_by_label("Poids série 1", exact=True).fill("60")
    with pg.expect_response(lambda r: "/seance/save-exo" in r.url):
        carte.locator(".serie-encours").nth(0).locator(".serie-valider").click()
    pg.locator("#finish-open").click()
    pg.locator("#finish-save").click()
    pg.wait_for_url("**/accueil**", timeout=15000)

    essai = pg.locator(".essai-card")
    essai.wait_for(timeout=5000)
    assert "ESSAI PRO OFFERT" in essai.inner_text()
    capture = os.environ.get("CAPTURE_ESSAI")
    if capture:
        essai.scroll_into_view_if_needed()
        pg.screenshot(path=capture)
    # L'essai vaut tout de suite : la page Plus le montre.
    pg.goto(serveur + "/plus")
    assert "Essai PRO" in pg.locator("body").inner_text()
    assert pg.erreurs == []
