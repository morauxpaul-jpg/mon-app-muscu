"""Retirer une série termine l'exercice et la retire de la base.

Retour du 24/10 : « depuis qu'il n'y a plus de bouton Enregistrer, ça ne
replie plus l'exo quand je retire une série, si j'en fais 1 au lieu de 2
ou 3 ». « Enregistrer » renvoyait toute la carte (m8 l'a retiré) :
- les séries restantes étant toutes faites, rien ne proposait plus
  « Exercice suivant » ;
- une série faite puis retirée restait en base jusqu'à « Terminer », et
  pour de bon si l'app était fermée avant.
"""
import json
import time
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")

EXO = "Développé couché"
CARTE = "document.querySelector('#exo-anchor-0')"


def _contexte(navigateur):
    ctx = navigateur.new_context(viewport={"width": 390, "height": 844}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('notifPrompted','1');"
                        "localStorage.setItem('tutoSeen','true');"
                        "localStorage.setItem('tutoSeanceSeen','true');")
    return ctx


def _base(serveur):
    with urllib.request.urlopen(serveur + "/test-historique") as r:
        lignes = json.loads(r.read())
    return sorted((x["serie"], x["reps"]) for x in lignes
                  if x["exercice"] == EXO and x["reps"] > 0)


def _attendre(condition, delai=10):
    fin = time.time() + delai
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.3)
    return False


def _ouvrir(pg, serveur):
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    pg.wait_for_selector("#exo-anchor-0")
    pg.evaluate(f"Alpine.$data({CARTE}).open = true")
    assert pg.evaluate(f"Alpine.$data({CARTE}).sets.length") == 3


def _serie(pg, n, reps):
    c = pg.locator("#exo-anchor-0")
    c.get_by_label(f"Répétitions série {n}", exact=True).fill(str(reps))
    c.get_by_label(f"Poids série {n}", exact=True).fill("60")
    with pg.expect_response(lambda r: "/seance/save-exo" in r.url):
        c.locator(".serie-encours").nth(n - 1).locator(".serie-valider").click()


def _etat(pg):
    return pg.evaluate(f"""() => {{ const d = Alpine.$data({CARTE});
        return {{series: d.sets.length, toutFait: d.toutFait, completed: d.completed}}; }}""")


def test_une_serie_sur_trois_puis_retrait_des_vides(serveur, navigateur):
    ctx = _contexte(navigateur)
    pg = ctx.new_page()
    _ouvrir(pg, serveur)
    _serie(pg, 1, 8)
    assert _etat(pg)["toutFait"] is False
    for _ in range(2):
        pg.locator("#exo-anchor-0 .serie-puce.danger:visible").last.click()
    assert _etat(pg) == {"series": 1, "toutFait": True, "completed": True}
    # « Exercice suivant », comme après la dernière série prévue.
    pg.locator("#exo-anchor-0 .exo-suivant").wait_for(state="visible", timeout=3000)
    assert _base(serveur) == [(1, 8)]
    ctx.close()


def test_retirer_une_serie_faite_la_retire_de_la_base(serveur, navigateur):
    ctx = _contexte(navigateur)
    pg = ctx.new_page()
    _ouvrir(pg, serveur)
    for n, reps in ((1, 8), (2, 7), (3, 6)):
        _serie(pg, n, reps)
    assert _base(serveur) == [(1, 8), (2, 7), (3, 6)]
    with pg.expect_response(lambda r: "/seance/save-exo" in r.url):
        pg.evaluate(f"Alpine.$data({CARTE}).removeSet(2)")
    assert _attendre(lambda: _base(serveur) == [(1, 8), (2, 7)]), _base(serveur)
    assert _etat(pg)["toutFait"] is True
    pg.reload()
    pg.wait_for_selector("#exo-anchor-0")
    assert pg.evaluate(f"Alpine.$data({CARTE}).sets.length") == 2
    ctx.close()


def test_retirer_la_seule_serie_faite_lefface(serveur, navigateur):
    ctx = _contexte(navigateur)
    pg = ctx.new_page()
    _ouvrir(pg, serveur)
    _serie(pg, 1, 8)
    assert _base(serveur) == [(1, 8)]
    with pg.expect_response(lambda r: "/seance/save-exo" in r.url):
        pg.evaluate(f"Alpine.$data({CARTE}).removeSet(0)")
    assert _attendre(lambda: _base(serveur) == []), _base(serveur)
    assert _etat(pg)["toutFait"] is False
    ctx.close()
