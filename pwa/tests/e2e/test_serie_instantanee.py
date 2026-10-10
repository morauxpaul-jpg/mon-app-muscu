"""« Série faite » répond tout de suite, et ne perd rien.

Audit du 06/10 (I-2, axe 12) : en production, le serveur met environ 2 s à
enregistrer une série. La carte attendait sa réponse pour dire
« Enregistré », passer au vert et proposer « Exercice suivant ». Pire : si
l'app était fermée pendant ces 2 s, la série n'était que dans le brouillon
de la carte et ne repartait pas d'elle-même.

Désormais la série est écrite dans la file du téléphone (offline.js) AVANT
de partir. Ici, le serveur ne répond plus (le sous-sol), puis répond de
nouveau : on vérifie ce que voit l'utilisateur et ce qui arrive en base.
"""
import json
import time
import urllib.request

import pytest

pytest.importorskip("playwright.sync_api")

EXO = "Développé couché"


def _contexte(navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');"
                        "localStorage.setItem('tutoSeanceSeen','true');")
    return ctx


def _series(serveur):
    with urllib.request.urlopen(serveur + "/test-historique") as r:
        lignes = json.loads(r.read())
    return sorted((x["serie"], x["reps"], x["poids"]) for x in lignes
                  if x["exercice"] == EXO and x["reps"] > 0)


def _attendre(condition, delai=25):
    fin = time.time() + delai
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.4)
    return False


def _ouvrir_seance(pg, serveur):
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    pg.wait_for_selector(".serie-valider")


def _serie_faite(pg, reps, poids):
    """Remplit la série en cours du premier exercice, la valide, et rend le
    temps (ms, mesuré dans la page) entre le tap et la confirmation."""
    carte = pg.locator("#exo-anchor-0")
    n = pg.evaluate("Alpine.$data(document.querySelector('#exo-anchor-0')).indexCourant()") + 1
    carte.get_by_label(f"Répétitions série {n}", exact=True).fill(str(reps))
    carte.get_by_label(f"Poids série {n}", exact=True).fill(str(poids))
    bouton = carte.locator(".serie-encours").nth(n - 1).locator(".serie-valider")
    bouton.evaluate("""(b) => { window.__t0 = performance.now(); window.__vu = null;
      const tick = () => {
        const e = document.querySelector('#exo-anchor-0 .exo-etat');
        if (e && /Gardé sur l'appareil/.test(e.innerText)) window.__vu = performance.now() - window.__t0;
        else requestAnimationFrame(tick);
      };
      b.click(); requestAnimationFrame(tick); }""")
    pg.wait_for_function("() => window.__vu !== null", timeout=5000)
    return pg.evaluate("window.__vu")


def test_la_serie_est_confirmee_sans_attendre_le_serveur(serveur, navigateur):
    ctx = _contexte(navigateur)
    pg = ctx.new_page()
    _ouvrir_seance(pg, serveur)
    pg.evaluate("window.__pasRecharge = true")
    # Le serveur ne répond plus. Sur le contexte : le service worker aussi.
    ctx.route("**/seance/save-exo", lambda route: None)
    carte = pg.locator("#exo-anchor-0")

    delais = [_serie_faite(pg, 5, 100) for _ in range(3)]
    assert max(delais) < 300, delais                              # avant : la réponse du serveur
    assert "done" in carte.get_attribute("class")                  # carte verte tout de suite
    sync_ok = carte.locator(".exo-suivant").is_visible()
    assert sync_ok, "« Exercice suivant » après la dernière série, sans attendre"
    # Rien n'est en base, mais tout est dans la file du téléphone.
    assert _series(serveur) == []
    file = pg.evaluate("JSON.parse(localStorage.getItem('muscu_offline_queue'))")
    assert file and all(i["url"].endswith("/seance/save-exo") for i in file)

    # Le réseau revient : la file renvoie seule, sans rechargement ni geste.
    ctx.unroute("**/seance/save-exo")
    assert _attendre(lambda: _series(serveur) == [(1, 5, 100.0), (2, 5, 100.0), (3, 5, 100.0)])
    pg.wait_for_function(
        "() => document.querySelector('#exo-anchor-0 .exo-etat').innerText.trim() === 'Enregistré'",
        timeout=10000)
    assert pg.evaluate("window.__pasRecharge") is True, "la page ne s'est pas rechargée"
    assert pg.evaluate("window.OfflineQueue.pending()") == 0
    ctx.close()


def test_une_app_fermee_pendant_lenvoi_ne_perd_rien(serveur, navigateur):
    """Le tap, puis l'app fermée avant la réponse. Avant : la série n'était
    que dans le brouillon de la carte et n'arrivait jamais en base."""
    ctx = _contexte(navigateur)
    pg = ctx.new_page()
    _ouvrir_seance(pg, serveur)
    # Le sous-sol : le téléphone se croit en ligne, l'envoi part et ne revient
    # jamais. (Une route Playwright laisse passer la requête à la fermeture.)
    pg.evaluate("""() => { const f = window.fetch;
      window.fetch = (u, o) => String(u).indexOf('save-exo') >= 0 ? new Promise(() => {}) : f(u, o); }""")
    _serie_faite(pg, 6, 80)
    pg.wait_for_timeout(500)
    pg.close()                                                     # l'app est fermée
    time.sleep(1)
    assert _series(serveur) == [], "rien n'a atteint le serveur"

    # Relancée plus tard, sur n'importe quelle page : la série repart seule.
    pg = ctx.new_page()
    pg.goto(serveur + "/accueil")
    assert _attendre(lambda: _series(serveur) == [(1, 6, 80.0)])
    assert _attendre(lambda: pg.evaluate("window.OfflineQueue.pending()") == 0, 10)
    ctx.close()


def test_une_serie_normale_ne_fait_ni_badge_ni_message(serveur, navigateur):
    """Chaque série passe par la file : le badge « en attente » et le message
    « tout est à jour » ne doivent parler que d'un envoi qui a vraiment
    attendu, pas de la seconde où la série part."""
    ctx = _contexte(navigateur)
    pg = ctx.new_page()
    _ouvrir_seance(pg, serveur)
    pg.evaluate("""() => { window.__vus = [];
      new MutationObserver(() => {
        if (document.getElementById('offline-badge')) window.__vus.push('badge');
        if (/tout est à jour/.test(document.body.innerText)) window.__vus.push('message');
      }).observe(document.body, { childList: true, subtree: true, characterData: true }); }""")
    _serie_faite(pg, 5, 100)
    pg.wait_for_function(
        "() => document.querySelector('#exo-anchor-0 .exo-etat').innerText.trim() === 'Enregistré'",
        timeout=10000)
    pg.wait_for_timeout(500)
    assert _series(serveur) == [(1, 5, 100.0)]
    assert pg.evaluate("window.__vus") == []
    ctx.close()
