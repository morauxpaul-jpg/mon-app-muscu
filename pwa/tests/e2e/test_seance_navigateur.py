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
    env = dict(os.environ, PORT=str(port), FLASK_SECRET_KEY="e2e", PYTHONUTF8="1", FAUX_IA="lent")
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


def test_une_page_deja_vue_souvre_meme_si_le_reseau_ne_repond_pas(page, serveur):
    """I4, côté ouverture de page : au sous-sol, le téléphone se croit en
    ligne et la requête ne revient jamais. Le service worker attendait le
    réseau indéfiniment — écran blanc — alors que la page était en cache."""
    url = serveur + "/seance?mode=prefaite&name=Push"
    # Le service worker contrôle la page et l'a gardée.
    page.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller !== null",
                           timeout=15000)
    page.goto(url)
    page.wait_for_selector(".serie-valider")
    # Désormais, le serveur ne répond plus aux pages (le SW compris).
    page.context.route("**/seance?**", lambda route: None)
    debut = time.time()
    page.goto(url, timeout=15000)
    page.wait_for_selector(".serie-valider", timeout=15000)
    assert time.time() - debut < 8, "la copie gardée arrive après le délai, pas après l'abandon"
    page.context.unroute("**/seance?**")


def test_terminer_ne_reste_pas_fige_derriere_la_file(page, serveur):
    """Audit du 03/10, R1 : une série en file, le réseau ne répond toujours
    pas, et l'on touche « Terminer ». Le rejeu de la file n'avait aucun
    délai : le bouton restait sur « Enregistrement… » indéfiniment."""
    page.context.route("**/seance/save-exo", lambda route: None)
    _serie_faite(page, 5, 100)
    page.locator("#exo-anchor-0 .exo-etat").filter(has_text="Gardé sur l'appareil").wait_for(timeout=12000)
    debut = time.time()
    _terminer(page)
    page.wait_for_url("**/accueil**", timeout=25000)
    assert time.time() - debut < 20, "« Terminer » a fini par rendre la main, mais trop tard"
    # Rien n'est perdu : la série et le bilan attendent, dans l'ordre.
    file = page.evaluate("JSON.parse(localStorage.getItem('muscu_offline_queue'))")
    assert [i["url"].rsplit("/", 1)[-1] for i in file] == ["save-exo", "finish"]


# ── La valeur grisée (audit du 03/10, R2) ────────────────────────


def test_serie_faite_sans_taper_enregistre_la_valeur_proposee(page, serveur):
    """Le champ Reps affiche l'objectif « 5 » en gris. Toucher « Série faite »
    sans taper repliait la série avec « — » et n'écrivait rien."""
    carte = page.locator("#exo-anchor-0")
    assert carte.get_by_label("Répétitions série 1", exact=True).get_attribute("placeholder") == "5"
    carte.get_by_label("Poids série 1", exact=True).fill("60")
    carte.locator(".serie-encours").nth(0).locator(".serie-valider").click()
    assert _attendre(lambda: _series(serveur) == [(1, 5, 60.0)])


def test_sans_charge_ni_reps_la_serie_nest_pas_pretendue_faite(page, serveur):
    carte = page.locator("#exo-anchor-0")
    carte.locator(".serie-encours").nth(0).locator(".serie-valider").click()
    time.sleep(0.8)
    assert _series(serveur) == []
    assert "Indique tes répétitions" in carte.locator(".exo-etat").inner_text()
    # La série 1 est toujours celle qu'on remplit.
    assert page.evaluate("Alpine.$data(document.querySelector('#exo-anchor-0')).indexCourant()") == 0


# ── Le premier écran (audit du 03/10, Q3) ────────────────────────


def test_la_premiere_serie_tient_dans_le_premier_ecran(page, serveur):
    """Le premier champ de reps était à 836 px sur un compte neuf (sous
    l'écran de 812 px) et à 1 355 px avec un historique : il fallait défiler
    avant de noter quoi que ce soit. Le champ ET « Série faite » doivent être
    visibles au-dessus de la barre de navigation, sans défiler."""
    page.evaluate("window.scrollTo(0, 0)")
    pos = page.evaluate("""() => {
      const s = document.querySelector('#exo-anchor-0 .serie-encours');
      const nav = document.querySelector('.bottom-nav').getBoundingClientRect().top;
      return {champ: s.querySelector('input').getBoundingClientRect().top,
              bouton: s.querySelector('.serie-valider').getBoundingClientRect().bottom, nav};
    }""")
    assert pos["champ"] > 0 and pos["bouton"] <= pos["nav"], pos


# ── Retours du 04/10 (séance réelle sur Android) ─────────────────

CARTE0 = "Alpine.$data(document.querySelector('#exo-anchor-0'))"


def test_une_saisie_non_validee_est_reprise_a_la_relance(page, serveur):
    """Deux reps tapées, pas encore validées, puis on quitte l'app : la relance
    ne proposait pas de reprendre, et la saisie revenait cochée en vert comme
    si elle était enregistrée. Elle revient dans son champ, à valider."""
    page.locator("#exo-anchor-0").get_by_label("Répétitions série 1", exact=True).fill("2")
    page.wait_for_timeout(300)
    ctx = page.context
    page.close()
    pg = ctx.new_page()                                   # relance : nouvel onglet
    pg.goto(serveur + "/")
    pg.wait_for_url("**/seance?**", timeout=5000)
    pg.wait_for_selector(".serie-valider")
    assert pg.evaluate(CARTE0 + ".sets[0].reps") == 2
    assert pg.evaluate(CARTE0 + ".faits") == []            # pas prétendue faite
    assert pg.locator("#exo-anchor-0 .serie-encours").first.is_visible()


def test_le_repos_part_a_serie_faite_avec_le_bon_exercice(page, serveur):
    """Le repos partait en quittant un champ, et la notification affichait
    toujours le premier exercice de la séance."""
    page.evaluate("""() => { window.__repos = [];
        RestTimer.start = function (s, nom) { window.__repos.push(nom); }; }""")
    carte = page.locator("#exo-anchor-0")
    carte.get_by_label("Répétitions série 1", exact=True).fill("6")
    carte.get_by_label("Poids série 1", exact=True).fill("60")
    carte.get_by_label("Répétitions série 1", exact=True).blur()
    page.wait_for_timeout(300)
    assert page.evaluate("window.__repos") == []
    carte.locator(".serie-encours").nth(0).locator(".serie-valider").click()
    assert _attendre(lambda: page.evaluate("window.__repos") == [EXO], 5)


def test_apres_la_derniere_serie_la_carte_reste_ouverte(page, serveur):
    """Refermer la carte après la 3e série empêchait d'en ajouter une. Elle
    reste ouverte, « Exercice suivant » mène à la suite, et le bandeau de
    record ne tasse plus le titre dans une colonne étroite."""
    for k in range(3):
        _serie_faite(page, 8, 40 + 10 * k)
        assert _attendre(lambda: len(_series(serveur)) == k + 1)
    carte = page.locator("#exo-anchor-0")
    assert page.evaluate(CARTE0 + ".open") is True
    carte.locator(".exo-pr").wait_for()
    largeurs = page.evaluate("""() => ({
        titre: document.querySelector('#exo-anchor-0 .exo-title').getBoundingClientRect().width,
        fleches: document.querySelector('#exo-anchor-0 .exo-reorder').getBoundingClientRect().width})""")
    assert largeurs["fleches"] < 60 and largeurs["titre"] > 150, largeurs
    carte.locator(".exo-suivant").click()
    second = "Alpine.$data(document.querySelector('#exo-anchor-1'))"
    assert _attendre(lambda: page.evaluate(second + ".open"), 5)
    # Le défilement s'arrête SUR l'exercice suivant, pas plus bas.
    assert _attendre(lambda: 0 <= page.evaluate(
        "document.querySelector('#exo-anchor-1').getBoundingClientRect().top") <= 60, 5)


def test_lequipement_est_en_tete_de_carte(page, serveur):
    sel = page.locator("#exo-anchor-0 .exo-equipement select")
    assert sel.is_visible()
    haut_equipement = sel.bounding_box()["y"]
    haut_serie = page.locator("#exo-anchor-0 .serie-encours").first.bounding_box()["y"]
    assert haut_equipement < haut_serie


def test_une_serie_dechauffement_part_a_part(page, serveur):
    """Panneau « RPE, remarque » : la case la marque ; elle s'enregistre avec
    son type et le volume d'échauffement s'affiche à part."""
    carte = page.locator("#exo-anchor-0")
    carte.locator(".serie-encours").nth(0).locator(".serie-puce").first.click()
    carte.locator(".serie-echauff").first.click()
    carte.get_by_label("Répétitions série 1", exact=True).fill("10")
    carte.get_by_label("Poids série 1", exact=True).fill("20")
    carte.locator(".serie-encours").nth(0).locator(".serie-valider").click()
    assert _attendre(lambda: [(r["serie"], r.get("type_serie")) for r in _historique(serveur)]
                     == [(1, "echauffement")])
    # La ligne est en base avant que la page ait lu la réponse : attendre
    # l'affichage, ne pas le lire aussitôt (échec de la CI du 04/10).
    sync_api.expect(page.locator("#prog-vol")).to_contain_text("+200 échauff.")
    sync_api.expect(carte.locator(".serie-faite").first).to_contain_text("Échauff.")


def test_case_alterner_enregistre_la_rotation(serveur, navigateur):
    """Page Programme : cocher « Alterner » enregistre le cycle, le décocher
    l'efface (core/rotation.py)."""
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');")
    pg = ctx.new_page()
    pg.goto(serveur + "/test-vierge?ab=1")
    pg.goto(serveur + "/programme")
    pg.select_option('#planning select[data-day="Mercredi"]', "Pull")
    case = pg.locator(".rotation-choix input")
    case.check()
    pg.wait_for_timeout(1200)                     # sauvegarde différée (500 ms)

    def blob():
        with urllib.request.urlopen(serveur + "/test-programme") as r:
            return json.loads(r.read())

    assert blob()["_rotation"] == ["Push", "Pull"]
    assert "Push → Pull" in pg.locator(".rotation-aide").inner_text()
    case.uncheck()
    pg.wait_for_timeout(1200)
    assert "_rotation" not in blob()
    ctx.close()


def test_superset_enchaine_sans_repos_puis_repos_apres_le_second(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script(
        "localStorage.setItem('tutoSeen','true');"
        "localStorage.setItem('tutoSeanceSeen','true');")
    pg = ctx.new_page()
    pg.goto(serveur + "/test-vierge?ss=1")
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    pg.wait_for_selector(".serie-valider")
    pg.evaluate("window.__repos = 0; var s = RestTimer.start;"
                "RestTimer.start = function () { window.__repos++; return s.apply(this, arguments); }; 0")
    assert "enchaîne avec Développé militaire" in pg.locator("#exo-anchor-0").inner_text()

    _serie_faite(pg, 5, 60)
    second = "Alpine.$data(document.querySelector('#exo-anchor-1'))"
    assert _attendre(lambda: pg.evaluate(second + ".open"), 5)
    assert pg.evaluate("window.__repos") == 0               # pas de repos entre les deux

    carte = pg.locator("#exo-anchor-1")
    carte.get_by_label("Répétitions série 1", exact=True).fill("10")
    carte.get_by_label("Poids série 1", exact=True).fill("30")
    carte.locator(".serie-encours").nth(0).locator(".serie-valider").click()
    assert _attendre(lambda: pg.evaluate("window.__repos") == 1, 5)
    ctx.close()


def test_semaine_gardee_hors_ligne(serveur, navigateur):
    """L'accueil fait garder les séances de la semaine ; la pastille le dit ;
    en mode avion, la séance de dans six jours s'ouvre."""
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR",
                                 service_workers="allow")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');"
                        "localStorage.setItem('tutoSeanceSeen','true');")
    pg = ctx.new_page()
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/accueil")
    pg.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller", timeout=15000)
    pg.reload()                                   # le SW contrôle la page : la mise en cache part
    pg.wait_for_selector("#pack-horsligne:not([hidden])", timeout=45000)   # retente à 20 s

    urls = json.loads(pg.locator("#precache-urls").text_content())
    seances = sorted(u for u in urls if "mode=prefaite" in u)
    assert len(seances) == 7                      # « Push » prévue tous les jours
    ctx.set_offline(True)
    pg.goto(serveur + seances[-1])                # la plus lointaine, dans six jours
    pg.wait_for_selector(".serie-valider", timeout=15000)
    ctx.close()


# ── Nutrition : un repas détaillé, aliment par aliment ───────────

def _nutrition(serveur):
    with urllib.request.urlopen(serveur + "/test-nutrition") as r:
        return json.loads(r.read())


def test_nutrition_repas_detaille_puis_quantite_corrigee(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');")
    pg = ctx.new_page()
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/test-login?vip=1&to=/nutrition")

    # Profil nutritionnel (formulaire ouvert tant qu'il manque).
    pg.locator("#nutri-poids").fill("80")
    pg.locator("#nutri-taille").fill("180")
    pg.locator("#nutri-age").fill("30")
    pg.get_by_role("button", name="Enregistrer").click()
    pg.wait_for_selector("text=OBJECTIF DU JOUR")
    assert pg.locator("text=par kilo de poids de corps").count() == 1

    # Déjeuner : « banane » → premier résultat → ajouter.
    pg.locator(".meal-btn", has_text="Déjeuner").click()
    champ = pg.locator("input[type=search]:visible")
    champ.fill("banane")
    pg.locator(".food-row:visible").first.click()
    pg.get_by_role("button", name="Ajouter au déjeuner").click()
    pg.wait_for_selector(".meal-grams")

    rows = _nutrition(serveur)
    assert [(r["note"], r["grams"], r["calories"]) for r in rows] == [("Banane", 120, 107)]

    # Corriger la quantité : 240 g → calories doublées, recalculées par le serveur.
    pg.get_by_role("button", name="Corriger la quantité").click()
    pg.get_by_label("Quantité en grammes").fill("240")
    pg.get_by_role("button", name="OK").click()
    pg.wait_for_selector(".meal-grams:has-text('240 g')")
    assert [(r["grams"], r["calories"]) for r in _nutrition(serveur)] == [(240, 214)]

    # La banane revient dans « Tes aliments habituels ».
    pg.locator(".meal-btn", has_text="Collation").click()
    pg.locator(".food-row:visible", has_text="Banane").wait_for(timeout=5000)
    assert pg.locator(".food-titre:visible").inner_text() == "TES ALIMENTS HABITUELS"
    assert erreurs == []
    ctx.close()


# ── Renommer un exercice : l'historique suit si on le demande ────

def test_renommer_un_exercice_propose_demmener_ses_series(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');localStorage.setItem('tutoSeanceSeen','true');")
    pg = ctx.new_page()
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    pg.wait_for_selector(".serie-valider")
    _serie_faite(pg, 5, 100)
    assert _attendre(lambda: len(_series(serveur)) == 1)

    pg.goto(serveur + "/programme")
    pg.locator(".exo-head:visible").first.click()
    champ = pg.locator(f'input[aria-label="Nom de cet exercice : {EXO}"]')
    champ.fill("Développé couché barre")
    champ.dispatch_event("change")
    pg.wait_for_selector(".renommage-choix:visible")
    pg.get_by_role("button", name="Oui, emmener mes séries").click()
    pg.wait_for_selector("text=suivent désormais")
    # La série garde le nom sous lequel elle a été faite et reçoit l'identifiant
    # de l'exercice (core/exercice_ids.py) : elle n'est pas réécrite…
    assert _attendre(lambda: [str(r.get("exercise_id") or "")[:2] for r in _historique(serveur)
                              if r["reps"] > 0] == ["e_"])
    assert _series(serveur) == [(1, 5, 100.0)]
    # … et la séance l'affiche sous le nouveau nom (une fois l'éditeur sauvegardé).
    assert _attendre(lambda: '"Développé couché barre"' in urllib.request.urlopen(
        serveur + "/test-programme").read().decode("unicode_escape"))
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    carte = pg.locator('[data-exo-base="Développé couché barre"]')
    carte.wait_for(state="attached")
    assert '"reps": 5' in carte.get_attribute("x-data")
    assert erreurs == []
    ctx.close()


# ── Générateur : l'IA travaille en tâche de fond ─────────────────

def test_generateur_suit_la_tache_jusquau_programme(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');")
    pg = ctx.new_page()
    erreurs, requetes = [], []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.on("request", lambda r: requetes.append(r.url))
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/test-login?vip=1&to=/generator")
    pg.get_by_role("button", name="Générer mon programme").click()
    pg.wait_for_selector(".gen-progres:visible")
    pg.wait_for_selector("text=Programme de test", timeout=20000)
    assert any("/generator/tache/" in u for u in requetes), "la page n'a pas suivi la tâche"
    assert erreurs == []
    ctx.close()


def test_generateur_reprend_apres_un_rechargement(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');")
    pg = ctx.new_page()
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/test-login?vip=1&to=/generator")
    pg.get_by_role("button", name="Générer mon programme").click()
    pg.wait_for_function("() => !!sessionStorage.getItem('gen_tache')", timeout=5000)
    pg.reload()
    pg.wait_for_selector("text=Programme de test", timeout=20000)
    assert pg.evaluate("() => sessionStorage.getItem('gen_tache')") is None
    ctx.close()
