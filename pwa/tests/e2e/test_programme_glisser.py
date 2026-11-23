"""Éditeur de programme : glisser un exercice au doigt, et des actions rangées.

Retour du 23/11 : « le déplacement d'exo marche mal et n'est pas très
lisible, il y a des boutons partout ». Mesuré avant correction, sur un
téléphone simulé (Pixel 7) :
- chaque glisser provoquait 26 erreurs « Undefined variable: ex » : SortableJS
  pose une copie de la ligne qui suit le doigt, et Alpine l'évaluait hors de
  sa boucle ;
- une ligne d'exercice faisait 255 px de haut (un formulaire complet), avec
  une poignée de 16 px et un appui long de 220 ms pour démarrer ;
- cinq boutons sous chaque séance, quatre sous chaque programme.
"""
import json
import urllib.request

import pytest

sync_api = pytest.importorskip("playwright.sync_api")


# Un téléphone Android : SortableJS choisit son mode tactile d'après lui.
ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36")


def _contexte_tactile(navigateur):
    ctx = navigateur.new_context(viewport={"width": 412, "height": 915}, locale="fr-FR",
                                 has_touch=True, is_mobile=True, device_scale_factor=1,
                                 user_agent=ANDROID)
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');")
    return ctx


def _espionner(pg):
    erreurs = []
    pg.on("console", lambda m: erreurs.append(m.text[:200])
          if ("Alpine" in m.text or "Content Security Policy" in m.text) else None)
    pg.on("pageerror", lambda e: erreurs.append("pageerror: " + str(e)[:200]))
    return erreurs


def _push(serveur):
    with urllib.request.urlopen(serveur + "/test-programme") as r:
        return [e["name"] for e in json.loads(r.read())["Push"]]


def _glisser_au_doigt(pg, depart, arrivee_y):
    """Un vrai geste tactile (événements touch de Chromium), sans appui long."""
    cdp = pg.context.new_cdp_session(pg)

    def toucher(genre, x, y):
        cdp.send("Input.dispatchTouchEvent", {
            "type": genre, "touchPoints": [] if genre == "touchEnd" else [{"x": x, "y": y}]})
    x, y = depart["x"] + depart["width"] / 2, depart["y"] + depart["height"] / 2
    toucher("touchStart", x, y)
    pg.wait_for_timeout(50)
    for i in range(1, 16):
        toucher("touchMove", x, y + (arrivee_y - y) * i / 15)
        pg.wait_for_timeout(25)
    pg.wait_for_timeout(150)
    toucher("touchEnd", x, arrivee_y)


def test_glisser_un_exercice_au_doigt(serveur, navigateur):
    ctx = _contexte_tactile(navigateur)
    pg = ctx.new_page()
    erreurs = _espionner(pg)
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/programme")
    carte = pg.locator("div.card:has(> .exo-head .exo-title:text-is('Push'))")
    carte.locator(".exo-head").click()
    lignes = carte.locator(".prog-exo-row")
    sync_api.expect(lignes).to_have_count(2)
    pg.wait_for_timeout(400)                        # fin de l'animation d'ouverture

    # Une ligne par exercice, lisible d'un coup d'œil ; les réglages repliés.
    assert lignes.first.bounding_box()["height"] < 90
    sync_api.expect(lignes.first.get_by_label("Nombre de séries")).to_be_hidden()
    sync_api.expect(carte.locator(".prog-exo-sous").first).to_have_text("3 séries · Pecs")
    poignee = lignes.first.locator(".prog-exo-poignee").bounding_box()
    assert poignee["width"] >= 44 and poignee["height"] >= 44

    # Le premier passe sous le second, par la poignée, sans appui long.
    seconde = lignes.nth(1).bounding_box()
    _glisser_au_doigt(pg, poignee, seconde["y"] + seconde["height"] * 0.8)
    noms = "els => els.map(e => e.value)"
    attendu = ["Développé militaire", "Développé couché"]
    pg.wait_for_function(f"""() => JSON.stringify([...document.querySelectorAll('.prog-exo-rename')]
        .map(e => e.value).slice(0, 2)) === '{json.dumps(attendu, ensure_ascii=False, separators=(',', ':'))}'""")
    pg.wait_for_timeout(1200)                       # sauvegarde différée (500 ms)
    assert _push(serveur) == attendu
    assert carte.locator(".prog-exo-rename").evaluate_all(noms) == attendu

    # Les lignes suivent toujours leurs données : les réglages ouverts sont
    # ceux du bon exercice, et « Monter » le remet en tête.
    lignes.nth(1).get_by_role("button", name="Réglages de Développé couché").click()
    lignes.nth(1).get_by_role("button", name="Monter l'exercice").click()
    pg.wait_for_timeout(1200)
    assert _push(serveur) == ["Développé couché", "Développé militaire"]
    assert erreurs == []
    ctx.close()


def test_les_actions_de_la_seance_sont_dans_un_menu(serveur, navigateur):
    ctx = _contexte_tactile(navigateur)
    pg = ctx.new_page()
    erreurs = _espionner(pg)
    pg.goto(serveur + "/test-vierge?ab=1")
    pg.goto(serveur + "/programme")
    carte = pg.locator("div.card:has(> .exo-head .exo-title:text-is('Push'))")
    # Rien à l'écran avant « ⋯ » : ni Renommer, ni Supprimer, ni Monter.
    for nom in ("Renommer", "Supprimer la séance", "Descendre la séance"):
        sync_api.expect(carte.get_by_role("button", name=nom)).to_be_hidden()
    carte.get_by_role("button", name="Options de la séance Push").click()
    # Première séance : « Monter » ne ferait rien, il n'est pas proposé.
    sync_api.expect(carte.get_by_role("button", name="Monter la séance")).to_be_hidden()
    carte.get_by_role("button", name="Descendre la séance").click()
    pg.wait_for_timeout(1200)
    titres = pg.locator(".prog-seance .exo-title").all_text_contents()
    assert titres == ["Pull", "Push"]
    assert erreurs == []
    ctx.close()
