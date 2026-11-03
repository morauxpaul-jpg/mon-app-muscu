"""Un nom tapé dans l'éditeur de programme est rangé, sous les yeux.

« developpe incline halteres » entre au programme comme « Développé
incliné », équipement Haltères (core/noms_exercices.py) : l'éditeur le montre
dès l'enregistrement, sans rechargement, et la page n'a aucune erreur
Alpine ni de la CSP (la pastille d'équipement est une expression de plus).
"""
import json
import urllib.request

import pytest

sync_api = pytest.importorskip("playwright.sync_api")


def test_un_nouvel_exercice_est_range_dans_l_editeur(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');")
    pg = ctx.new_page()
    erreurs = []
    pg.on("console", lambda m: erreurs.append(m.text)
          if ("Alpine" in m.text or "Content Security Policy" in m.text) else None)
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/programme")
    carte = pg.locator("div.card:has(> .exo-head .exo-title:text-is('Push'))")
    carte.locator(".exo-head").click()
    carte.get_by_placeholder("Nom de l'exercice").fill("developpe incline halteres")
    carte.get_by_role("button", name="Ajouter l'exercice").click()

    ligne = carte.locator(".prog-exo-row").last
    sync_api.expect(ligne.locator(".prog-exo-rename")).to_have_value("Développé incliné", timeout=5000)
    sync_api.expect(ligne.locator(".prog-exo-materiel")).to_have_text("Haltères")
    with urllib.request.urlopen(serveur + "/test-programme") as r:
        push = json.loads(r.read())["Push"]
    assert (push[-1]["name"], push[-1].get("materiel")) == ("Développé incliné", "Haltères")
    assert erreurs == []
    ctx.close()


def test_ranger_et_laisser_dans_gestion(serveur, navigateur):
    """Retour du 03/11 : « Pec deck (machine) » restait proposé après le
    rangement, et rien ne permettait d'écarter « Overhead triceps extension »
    → « Extension triceps haltère » (deux exercices). Dans un vrai
    navigateur : « Laisser » part du même formulaire (formaction), avec son
    jeton CSRF, puis le rangement coché passe et la liste se vide."""
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');")
    pg = ctx.new_page()
    erreurs = []
    pg.on("console", lambda m: erreurs.append(m.text)
          if ("Alpine" in m.text or "Content Security Policy" in m.text) else None)
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(serveur + "/test-vierge?rang=1")
    pg.goto(serveur + "/gestion")
    carte = pg.locator("#aligner")
    sync_api.expect(carte).to_contain_text("Ranger mes exercices (2)")
    assert "Hevy" not in pg.content() and "Strong" not in pg.content()

    carte.get_by_role("button", name="Laisser Overhead triceps extension tel quel").click()
    sync_api.expect(pg.locator(".rang-retour")).to_contain_text("Proposition laissée")
    sync_api.expect(carte).to_contain_text("Ranger mes exercices (1)")
    sync_api.expect(carte).to_contain_text("1 proposition laissée de côté")

    case = carte.locator('input[name="aligner"][value="Pec deck (machine)"]')
    case.check()
    carte.get_by_role("button", name="Ranger les exercices cochés").click()
    carte.get_by_role("button", name="Confirmer").click()
    sync_api.expect(pg.locator(".rang-retour")).to_contain_text("séries rangées")
    sync_api.expect(carte.locator('input[name="aligner"]')).to_have_count(0)
    with urllib.request.urlopen(serveur + "/test-programme") as r:
        bras = json.loads(r.read())["Bras"]
    assert [(e["name"], e.get("materiel")) for e in bras] == [
        ("Écarté machine", "Machine"), ("Overhead triceps extension", None)]

    carte.get_by_role("button", name="Les revoir").click()
    sync_api.expect(carte.locator('input[name="aligner"][value="Overhead triceps extension"]')).to_have_count(1)
    assert erreurs == []
    ctx.close()
