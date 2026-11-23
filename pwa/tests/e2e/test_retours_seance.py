"""Retours du propriétaire du 23/11 sur la séance, joués dans un navigateur.

- Les reps avant la charge (« comme on le dit, comme « Dernière fois » »).
- « Réinitialiser » un exercice : la séance avait son « Recommencer », pas
  l'exercice.
- « Modifier » en haut de la séance mène à cette séance dans Programme,
  ouverte.
"""
import json
import time
import urllib.request

import pytest

sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture()
def page(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');"
                        "localStorage.setItem('tutoSeanceSeen','true');")
    pg = ctx.new_page()
    pg.erreurs = []
    pg.on("console", lambda m: pg.erreurs.append(m.text[:200])
          if ("Alpine" in m.text or "Content Security Policy" in m.text) else None)
    pg.on("pageerror", lambda e: pg.erreurs.append(str(e)[:200])
          if "Transition was" not in str(e) else None)
    pg.goto(serveur + "/test-vierge?ab=1")
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    pg.wait_for_selector(".serie-valider")
    yield pg
    ctx.close()


def _historique(serveur):
    with urllib.request.urlopen(serveur + "/test-historique") as r:
        return json.loads(r.read())


def _attendre(condition, delai=10):
    fin = time.time() + delai
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.1)
    return False


def test_les_reps_viennent_avant_la_charge(page):
    serie = page.locator("#exo-anchor-0 .serie-encours").first
    etiquettes = serie.locator(".serie-etiq").all_inner_texts()
    assert [e.upper() for e in etiquettes] == ["REPS", "KG"]
    reps = serie.get_by_label("Répétitions série 1", exact=True).bounding_box()
    kg = serie.get_by_label("Poids série 1", exact=True).bounding_box()
    assert reps["x"] < kg["x"]
    assert page.erreurs == []


def test_reinitialiser_un_exercice_efface_ses_series_du_jour(page, serveur):
    carte = page.locator("#exo-anchor-0")
    # Rien à effacer : pas de bouton.
    sync_api.expect(carte.get_by_role("button", name="Réinitialiser")).to_be_hidden()
    carte.get_by_label("Répétitions série 1", exact=True).fill("5")
    carte.get_by_label("Poids série 1", exact=True).fill("100")
    carte.locator(".serie-encours").first.locator(".serie-valider").click()
    assert _attendre(lambda: len(_historique(serveur)) == 1)

    carte.get_by_role("button", name="Réinitialiser").click()
    with page.expect_navigation():
        carte.get_by_role("button", name="Confirmer").click()
    page.wait_for_selector(".serie-valider")
    assert _historique(serveur) == []
    # Ni brouillon ni envoi en attente pour faire revenir la série.
    carte = page.locator("#exo-anchor-0")
    assert carte.get_by_label("Répétitions série 1", exact=True).input_value() == ""
    assert carte.evaluate("c => Alpine.$data(c).open") is True
    assert page.erreurs == []


def test_modifier_ouvre_la_seance_dans_le_programme(page, serveur):
    with page.expect_navigation():
        page.get_by_role("link", name="Modifier la séance Push dans le programme").click()
    assert page.url.endswith("/programme?seance=Push")
    page.wait_for_timeout(500)
    ouvertes = page.evaluate("""() => [...document.querySelectorAll('.prog-seance')]
        .map(c => [c.querySelector('.exo-title').textContent, Alpine.$data(c).open])""")
    assert ouvertes == [["Push", True], ["Pull", False]]
    assert page.erreurs == []
