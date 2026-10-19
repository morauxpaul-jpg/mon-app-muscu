"""Premier jour : quatre bulles d'aide, chacune au moment où elle sert.

Audit du 18/10 (m9) : quatorze bulles au premier jour, six sur l'accueil
pour présenter les onglets, huit d'affilée avant la première série ; la
dernière disait « Compris » et laissait sur l'accueil. Les retours
d'utilisateurs disaient l'app peu claire au premier abord.
"""
import pytest


@pytest.fixture()
def pg(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    # Aucun tutoriel vu ; la fenêtre des notifications n'est pas le sujet.
    ctx.add_init_script("localStorage.setItem('notifPrompted','1');")
    page = ctx.new_page()
    page.erreurs = []
    page.on("pageerror", lambda e: page.erreurs.append(str(e)))
    page.goto(serveur + "/test-vierge")
    yield page
    ctx.close()


def _bulle(pg):
    pg.wait_for_selector("#tuto-overlay.visible #tuto-next", timeout=6000)
    return pg.locator("#tuto-overlay.visible #tuto-bubble h4").inner_text()


def _fermer(pg, bouton="#tuto-next"):
    """Touche le bouton, puis attend que la bulle ait disparu (fondu de
    300 ms) : sans cela, on lisait la bulle sortante pour la suivante."""
    pg.locator("#tuto-overlay.visible " + bouton).click()
    pg.wait_for_selector("#tuto-overlay", state="detached")


def _serie_faite(pg):
    carte = pg.locator("#exo-anchor-0")
    n = pg.evaluate("Alpine.$data(document.querySelector('#exo-anchor-0')).indexCourant()") + 1
    carte.get_by_label(f"Répétitions série {n}", exact=True).fill("5")
    carte.get_by_label(f"Poids série {n}", exact=True).fill("60")
    carte.locator(".serie-encours").nth(n - 1).locator(".serie-valider").click()


def test_le_premier_jour_tient_en_quatre_bulles(pg, serveur):
    pg.goto(serveur + "/accueil")
    titres = [_bulle(pg)]
    assert pg.locator("#tuto-next").inner_text() == "Commencer"

    # Le bouton de la bulle ouvre la séance : il ne laisse plus sur l'accueil.
    with pg.expect_navigation():
        pg.locator("#tuto-next").click()
    assert "/seance?mode=prefaite&name=Push" in pg.url

    titres.append(_bulle(pg))                      # arrivée : la série en cours
    _fermer(pg)
    _serie_faite(pg)
    titres.append(_bulle(pg))                      # après la 1re série : le repos
    _fermer(pg)
    _serie_faite(pg)
    pg.wait_for_timeout(400)
    assert pg.locator("#tuto-overlay").count() == 0, "aucune bulle à la 2e série"
    _serie_faite(pg)
    titres.append(_bulle(pg))                      # exercice fini : la suite
    _fermer(pg)

    assert titres == ["Ta première séance est prête", "Une série à la fois",
                      "Série enregistrée", "Premier exercice terminé"]

    # Plus rien ensuite : ni à l'exercice suivant, ni sur l'accueil, ni à la
    # séance d'après.
    pg.wait_for_timeout(400)
    pg.get_by_text("Exercice suivant").first.click()
    pg.wait_for_timeout(800)
    assert pg.locator("#tuto-overlay").count() == 0
    pg.goto(serveur + "/accueil")
    pg.wait_for_timeout(1000)
    assert pg.locator("#tuto-overlay").count() == 0
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    pg.wait_for_selector("#exo-anchor-0")
    pg.wait_for_timeout(1200)
    assert pg.locator("#tuto-overlay").count() == 0
    assert pg.erreurs == []


def test_passer_coupe_toutes_les_bulles_de_la_seance(pg, serveur):
    pg.evaluate("localStorage.setItem('tutoSeen','true')")
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    assert _bulle(pg) == "Une série à la fois"
    _fermer(pg, "#tuto-skip")
    _serie_faite(pg)
    pg.wait_for_timeout(1200)
    assert pg.locator("#tuto-overlay").count() == 0
    assert pg.evaluate("localStorage.getItem('tutoSeanceSeen')") == "true"


def test_la_bulle_d_accueil_ne_s_ouvre_que_sur_l_accueil(pg, serveur):
    pg.goto(serveur + "/progres")
    pg.wait_for_timeout(1200)
    assert pg.locator("#tuto-overlay").count() == 0
    pg.goto(serveur + "/accueil")
    assert _bulle(pg) == "Ta première séance est prête"
