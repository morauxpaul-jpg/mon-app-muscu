"""Une recette créée dans le navigateur, puis notée au déjeuner.

Ce que les tests sans navigateur ne voient pas : l'éditeur Alpine (recherche
d'ingrédients, quantités, parts) sous la CSP, la liste envoyée au serveur, et
la recette retrouvée dans la recherche du repas.
"""
import json
import urllib.request

import pytest

sync_api = pytest.importorskip("playwright.sync_api")


def _ingredient(pg, recherche, nom, grammes):
    pg.get_by_label("Chercher un ingrédient").fill(recherche)
    pg.locator(".food-row", has_text=nom).first.click()
    pg.get_by_label("Quantité").last.fill(str(grammes))


def test_une_recette_se_cree_puis_se_note_au_dejeuner(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');")
    pg = ctx.new_page()
    erreurs = []
    pg.on("console", lambda m: erreurs.append(m.text)
          if ("Alpine" in m.text or "Content Security Policy" in m.text) else None)
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(serveur + "/test-seed")
    pg.goto(serveur + "/test-login?vip=1")

    pg.goto(serveur + "/nutrition/aliments")
    pg.get_by_role("link", name="Nouvelle recette").click()
    # Un nom tapé avant le démarrage d'Alpine est gardé (init du composant).
    pg.get_by_label("Nom", exact=True).fill("Pâtes carbonara")
    pg.wait_for_function("() => { const e = document.querySelector('[x-data]'); return e && e._x_dataStack; }")
    _ingredient(pg, "pates crues", "Pâtes crues", 500)
    _ingredient(pg, "lardons", "Lardons cuits", 200)
    _ingredient(pg, "oeuf entier", "Œuf entier", 200)
    pg.get_by_label("Nombre de parts").fill("4")
    pg.get_by_label("Poids cuit (g)").fill("1500")
    # 500 g de pâtes crues, 200 g de lardons, 4 œufs : la part se lit avant d'enregistrer.
    sync_api.expect(pg.locator(".perso-bilan-part")).to_contain_text("1 part (375 g)")
    pg.get_by_role("button", name="Enregistrer").click()

    sync_api.expect(pg.locator(".perso-ok")).to_contain_text("« Pâtes carbonara » est dans la recherche")
    sync_api.expect(pg.locator(".perso-ligne")).to_contain_text("4 parts · 3 ingrédients")

    pg.goto(serveur + "/nutrition")
    pg.locator(".meal-btn", has_text="Déjeuner").click()
    pg.locator("input[type=search]:visible").fill("carbo")
    ligne = pg.locator(".food-row:visible", has_text="Pâtes carbonara").first
    sync_api.expect(ligne).to_contain_text("Ma recette")
    ligne.click()
    pg.locator("button:visible", has_text="Ajouter au déjeuner").click()
    pg.wait_for_url("**/nutrition?date=*")

    with urllib.request.urlopen(serveur + "/test-nutrition") as r:
        notes = [n for n in json.loads(r.read()) if n.get("note") == "Pâtes carbonara"]
    assert len(notes) == 1 and notes[0]["grams"] == 375 and notes[0]["meal_type"] == "dejeuner"
    assert erreurs == []
    ctx.close()
