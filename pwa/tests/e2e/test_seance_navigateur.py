"""La séance, jouée dans un vrai navigateur (Chromium, 375 × 812).

Les autres tests appellent les routes une par une. C'est ce qui a laissé
passer le défaut central de l'audit du 30/09 (R1) : « Série faite » cochait
la série en vert sans rien écrire, « Terminer » effaçait les brouillons — et
chaque route, prise seule, faisait bien ce qu'on lui demandait. Trois séries
cochées, séance terminée, zéro ligne en base.

Ici on rejoue le geste de l'utilisateur de bout en bout, puis on lit la
(fausse) base : en ligne, en mode avion, et quand le réseau ne répond pas
(le sous-sol, où le téléphone se croit en ligne).

Le serveur est `run_local_fake.py` lancé à part, sur un port libre.
Sans Playwright ni Chromium installés, ces tests s'ignorent.
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PWA = Path(__file__).resolve().parents[2]
EXO = "Développé couché"


def _port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def serveur():
    port = _port_libre()
    env = dict(os.environ, PORT=str(port), FLASK_SECRET_KEY="e2e", PYTHONUTF8="1")
    proc = subprocess.Popen([sys.executable, "run_local_fake.py"], cwd=PWA, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/test-historique", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("le serveur de test n'a pas démarré")
    yield base
    proc.kill()


@pytest.fixture(scope="module")
def navigateur():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {e}")
        yield b
        b.close()


@pytest.fixture()
def page(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    # Tutoriels déjà vus : leurs bulles recouvriraient les boutons.
    ctx.add_init_script(
        "localStorage.setItem('tutoSeen','true');"
        "localStorage.setItem('tutoSeanceSeen','true');")
    pg = ctx.new_page()
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    pg.wait_for_selector(".serie-valider")
    yield pg
    ctx.close()


def _historique(serveur):
    with urllib.request.urlopen(serveur + "/test-historique") as r:
        return json.loads(r.read())


def _series(serveur, exo=EXO):
    return sorted(
        (r["serie"], r["reps"], r["poids"]) for r in _historique(serveur)
        if r["exercice"] == exo and r["reps"] > 0)


def _serie_faite(pg, reps, poids):
    """Remplit la série en cours du premier exercice et la valide.

    La série est désignée par son NUMÉRO, lu dans la page : viser « la série
    visible » attrapait parfois la précédente, le temps qu'Alpine la replie."""
    carte = pg.locator("#exo-anchor-0")
    n = pg.evaluate("Alpine.$data(document.querySelector('#exo-anchor-0')).indexCourant()") + 1
    carte.get_by_label(f"Répétitions série {n}", exact=True).fill(str(reps))
    carte.get_by_label(f"Poids série {n}", exact=True).fill(str(poids))
    carte.locator(".serie-encours").nth(n - 1).locator(".serie-valider").click()


def _attendre(condition, delai=15):
    fin = time.time() + delai
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.4)
    return False


def _terminer(pg):
    pg.locator("#finish-open").click()
    pg.locator("#finish-save").click()


# ── En ligne ─────────────────────────────────────────────────────


def test_trois_series_cochees_puis_terminer_sont_en_base(page, serveur):
    """R1, le geste le plus naturel : cocher ses séries, puis « Terminer »,
    sans jamais toucher « Enregistrer »."""
    for poids in (100, 100, 100):
        _serie_faite(page, 5, poids)
    _terminer(page)
    page.wait_for_url("**/accueil**", timeout=15000)
    assert _series(serveur) == [(1, 5, 100.0), (2, 5, 100.0), (3, 5, 100.0)]


def test_chaque_serie_faite_est_en_base_sans_attendre_terminer(page, serveur):
    _serie_faite(page, 8, 60)
    assert _attendre(lambda: _series(serveur) == [(1, 8, 60.0)])
    # … et les séries pas encore faites ne sont PAS écrites en SKIP.
    lignes = [r for r in _historique(serveur) if r["exercice"] == EXO]
    assert len(lignes) == 1
    page.wait_for_function(
        "document.querySelector('#exo-anchor-0 .exo-etat').innerText === 'Enregistré'")


def test_une_serie_saisie_sans_valider_part_quand_meme_a_la_fin(page, serveur):
    carte = page.locator("#exo-anchor-0")
    carte.get_by_label("Répétitions série 1", exact=True).fill("6")
    carte.get_by_label("Poids série 1", exact=True).fill("90")
    _terminer(page)
    page.wait_for_url("**/accueil**", timeout=15000)
    assert _series(serveur) == [(1, 6, 90.0)]


# ── Skip ─────────────────────────────────────────────────────────


def test_skip_demande_confirmation_avant_deffacer_des_series(page, serveur):
    _serie_faite(page, 5, 100)
    assert _attendre(lambda: _series(serveur) == [(1, 5, 100.0)])
    skip = page.locator('#exo-anchor-0 form[action="/seance/skip-exo"] button')
    skip.click()
    assert "Effacer ?" in skip.inner_text()
    time.sleep(0.5)
    assert _series(serveur) == [(1, 5, 100.0)], "un premier appui n'efface rien"
    skip.click()
    assert _attendre(lambda: _series(serveur) == [])


# ── Mode avion ───────────────────────────────────────────────────


def test_mode_avion_les_series_attendent_puis_partent(page, serveur):
    page.context.set_offline(True)
    _serie_faite(page, 5, 100)
    _serie_faite(page, 5, 100)
    etat = page.locator("#exo-anchor-0 .exo-etat")
    assert "Gardé sur l'appareil" in etat.inner_text()
    assert _series(serveur) == []
    _terminer(page)
    page.wait_for_url("**/accueil**", timeout=15000)
    # Le bilan est dans la file, derrière les séries.
    assert page.evaluate("JSON.parse(localStorage.getItem('muscu_offline_queue')).length") == 2
    page.context.set_offline(False)
    # Retour du réseau : la prochaine page ouverte vide la file.
    page.goto(serveur + "/accueil")
    assert _attendre(lambda: _series(serveur) == [(1, 5, 100.0), (2, 5, 100.0)]), \
        "au retour du réseau, la file a tout envoyé"
    assert _attendre(lambda: page.evaluate("window.OfflineQueue.pending()") == 0)


# ── Réseau qui ne répond pas (sous-sol) ──────────────────────────


def test_un_envoi_sans_reponse_part_en_file_au_lieu_de_bloquer(page, serveur):
    """R2 : `navigator.onLine` vaut true, mais la requête ne revient jamais.
    Avant : bouton bloqué sur « En cours… », rien dans la file."""
    page.route("**/seance/save-exo", lambda route: None)   # ne répond jamais
    _serie_faite(page, 5, 100)
    etat = page.locator("#exo-anchor-0 .exo-etat")
    etat.filter(has_text="Gardé sur l'appareil").wait_for(timeout=12000)
    assert page.evaluate("window.OfflineQueue.pending()") == 1
    page.unroute("**/seance/save-exo")
    page.evaluate("window.OfflineQueue.sync()")
    assert _attendre(lambda: _series(serveur) == [(1, 5, 100.0)])
