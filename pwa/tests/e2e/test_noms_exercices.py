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
