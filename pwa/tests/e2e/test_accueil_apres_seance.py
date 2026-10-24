"""Après la séance du jour, l'accueil dit qu'elle est faite (audit du 18/10).

Constaté : « Terminer la séance » ramène à l'accueil, dont la carte
« Prochaine séance » proposait aussitôt celle de demain avec le gros bouton
vert « FAIRE MAINTENANT ». Elle poussait à enchaîner une deuxième séance le
même jour. Désormais : « Séance du jour faite », la suivante avec son jour,
et un bouton secondaire pour qui veut vraiment avancer.
"""
import pytest


@pytest.fixture()
def pg(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 390, "height": 844}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('notifPrompted','1');localStorage.setItem('tutoSeen','true');"
                        "localStorage.setItem('tutoSeanceSeen','true');")
    page = ctx.new_page()
    page.erreurs = []
    page.on("pageerror", lambda e: page.erreurs.append(str(e)))
    page.goto(serveur + "/test-vierge")          # Push prévue tous les jours
    yield page
    ctx.close()


def test_la_seance_terminee_n_invite_pas_a_en_refaire_une(pg, serveur):
    pg.goto(serveur + "/accueil")
    carte = pg.locator("section.acc-seance")
    assert "COMMENCER" in carte.inner_text().upper()

    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    pg.wait_for_selector("#exo-anchor-0")
    pg.evaluate("Alpine.$data(document.querySelector('#exo-anchor-0')).open = true")
    exo = pg.locator("#exo-anchor-0")
    exo.get_by_label("Répétitions série 1", exact=True).fill("5")
    exo.get_by_label("Poids série 1", exact=True).fill("60")
    with pg.expect_response(lambda r: "/seance/save-exo" in r.url):
        exo.locator(".serie-encours").nth(0).locator(".serie-valider").click()
    pg.locator("#finish-open").click()
    pg.locator("#finish-save").click()
    pg.wait_for_url("**/accueil**", timeout=15000)

    carte = pg.locator("section.acc-seance")
    texte = carte.inner_text().upper()
    assert "SÉANCE DU JOUR FAITE" in texte
    assert "FAIRE MAINTENANT" not in texte
    # La suivante est annoncée avec son jour, pas comme la chose à faire.
    assert "DEMAIN" in texte and "PUSH" in texte
    # Plus de bouton vert principal sur la carte.
    assert carte.locator(".btn.primary").count() == 0
    bouton = carte.locator("a.btn")
    assert bouton.count() == 1 and "EN AVANCE" in bouton.inner_text().upper()
    assert pg.erreurs == []
