"""La politique de sécurité (CSP) bloque, et l'app marche quand même.

Audit du 06/10 (m6) : la CSP complète n'était qu'en observation, avec
`unsafe-inline` et `unsafe-eval`. Elle bloque désormais (core/csp.py) : plus
de onclick="…", plus de <script> sans jeton, Alpine dans sa version CSP qui
n'accepte qu'une expression simple par attribut. Un oubli ne se voit pas à
l'écran — le bouton ne fait juste plus rien. D'où :

- toutes les pages, pour chaque profil, sans une erreur Alpine ni un refus
  de la CSP dans la console ;
- les gestes réécrits pour l'occasion, joués pour de vrai : bibliothèque
  d'exercices, renommage, déplacement, fiche d'exercice, repas, disques.
"""
import json
import urllib.request

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PAGES = ["/accueil", "/seance", "/seance?mode=prefaite&name=Push", "/seance?mode=libre",
         "/cardio", "/cardio/import", "/nutrition", "/nutrition/aliments",
         "/nutrition/aliments?nouveau=recette", "/nutrition/aliments?nouveau=aliment",
         "/progres", "/progres/exercice?exo=Squat", "/progres/corps",
         "/programme", "/plus", "/gestion", "/gestion/import-muscu", "/coach", "/generator",
         "/parrainage", "/amis", "/premium", "/plaques", "/faq", "/cgv", "/confidentialite",
         "/mentions-legales"]
# (profil, connexion, pages)
PROFILS = [
    ("public", None, ["/", "/login"]),
    ("gratuit", "/test-login", PAGES),
    ("pro", "/test-login?vip=1", PAGES),
    ("admin", "/test-login?vip=1&admin=1", ["/admin", "/admin/funnel"]),
]


def _contexte(navigateur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    # Tutoriels déjà vus : leurs bulles recouvriraient les boutons.
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');"
                        "localStorage.setItem('tutoSeanceSeen','true');")
    return ctx


def _espionner(pg):
    """Erreurs Alpine, refus de la CSP et exceptions JS de la page."""
    erreurs = []

    def console(m):
        t = m.text
        if "Content Security Policy" in t or "Alpine" in t or "Refused to" in t:
            erreurs.append(t[:300])
    pg.on("console", console)
    # /login sans Supabase configuré (serveur de démonstration) : attendu.
    pg.on("pageerror", lambda e: None if "supabaseUrl is required" in str(e)
          else erreurs.append("pageerror: " + str(e)[:300]))
    return erreurs


def _programme(serveur):
    with urllib.request.urlopen(serveur + "/test-programme") as r:
        return json.loads(r.read())


@pytest.mark.parametrize("profil,connexion,pages", PROFILS, ids=[p[0] for p in PROFILS])
def test_aucune_page_ne_heurte_la_csp(serveur, navigateur, profil, connexion, pages):
    ctx = _contexte(navigateur)
    pg = ctx.new_page()
    erreurs = _espionner(pg)
    if connexion:
        pg.goto(serveur + "/test-seed")
        pg.goto(serveur + connexion)
    vues = {}
    for u in pages:
        n = len(erreurs)
        rep = pg.goto(serveur + u, wait_until="load")
        politique = rep.headers.get("content-security-policy", "")
        assert "script-src 'self'" in politique and "unsafe-eval" not in politique, (u, politique)
        # Les volets repliés aussi : leur contenu n'est évalué qu'à l'ouverture.
        for resume in pg.query_selector_all("details > summary"):
            if resume.is_visible():
                resume.click()
        pg.wait_for_timeout(250)
        if len(erreurs) > n:
            vues[u] = erreurs[n:]
    ctx.close()
    assert vues == {}


def test_la_politique_bloque_vraiment_un_script_sans_jeton(serveur, navigateur):
    """Sinon les autres tests ne prouveraient rien."""
    ctx = _contexte(navigateur)
    pg = ctx.new_page()
    erreurs = _espionner(pg)
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/accueil")
    pg.evaluate("""() => { const s = document.createElement('script');
                           s.textContent = 'window.__injecte = 1';
                           document.body.appendChild(s); }""")
    assert pg.evaluate("() => window.__injecte") is None
    assert any("Content Security Policy" in e for e in erreurs)
    ctx.close()


def test_programme_bibliotheque_renommer_et_ajouter(serveur, navigateur):
    ctx = _contexte(navigateur)
    pg = ctx.new_page()
    erreurs = _espionner(pg)
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/programme")
    carte = pg.locator("div.card:has(> .exo-head .exo-title:text-is('Push'))")
    carte.locator(".exo-head").click()

    # La bibliothèque s'ouvre (sortie vers <body>), se filtre, et remplit le champ.
    carte.get_by_role("button", name="Ajouter un exercice").click()
    carte.get_by_role("button", name="Choisir un exercice").click()
    modale = pg.locator("body > div", has=pg.get_by_role("heading", name="Bibliothèque d'exercices"))
    sync_api.expect(modale).to_be_visible()
    modale.get_by_placeholder("Rechercher un exercice...").fill("squat bulgare")
    # Le filtre est appliqué quand seules des lignes « squat » restent visibles,
    # et seuls les groupes qui en ont gardent leur titre.
    pg.wait_for_function("""() => {
        const b = [...document.querySelectorAll('body > div .biblio-ligne')].filter(x => x.offsetParent);
        return b.length > 0 && b.every(x => /squat/i.test(x.textContent)); }""")
    titres = modale.locator(".biblio-groupe:visible").all_inner_texts()
    assert [t.upper() for t in titres] == ["JAMBES"], titres
    choix = modale.locator(".biblio-ligne:visible")
    nom = choix.first.locator(".biblio-nom").inner_text()
    choix.first.click()
    sync_api.expect(modale).to_be_hidden()
    assert carte.get_by_placeholder("Nom de l'exercice").input_value() == nom
    carte.get_by_role("button", name="Ajouter l'exercice").click()
    pg.wait_for_timeout(1200)                      # sauvegarde différée (500 ms)
    assert [e["name"] for e in _programme(serveur)["Push"]][-1] == nom

    # Renommer la séance : le champ s'ouvre prérempli, « OK » renomme sur le serveur.
    carte.get_by_role("button", name="Options de la séance Push").click()
    carte.get_by_role("button", name="Renommer").click()
    champ = carte.locator(".rn-input")
    sync_api.expect(champ).to_be_focused()
    assert champ.input_value() == "Push"
    champ.fill("Push lourd")
    carte.get_by_role("button", name="OK").click()
    pg.wait_for_selector("text=Séance renommée")
    assert "Push lourd" in _programme(serveur)
    assert erreurs == []
    ctx.close()


def test_seance_bibliotheque_deplacer_et_fiche(serveur, navigateur):
    ctx = _contexte(navigateur)
    pg = ctx.new_page()
    erreurs = _espionner(pg)
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    pg.wait_for_selector(".serie-valider")

    # Descendre le premier exercice.
    bases = "() => [...document.querySelectorAll('.exo-card')].map(c => c.dataset.exoBase)"
    avant = pg.evaluate(bases)
    pg.locator("#exo-anchor-0").get_by_role("button", name="Descendre l'exercice").click()
    assert pg.evaluate(bases) == [avant[1], avant[0]] + avant[2:]

    # Fiche d'exercice : s'ouvre, change d'onglet, se ferme.
    pg.locator("#exo-anchor-0 .exo-info-btn", has_text="?").click()
    fiche = pg.locator("#exo-info-modal")
    sync_api.expect(fiche).to_be_visible()
    fiche.get_by_role("button", name="Table RM").click()
    sync_api.expect(pg.locator("#exo-tab-rm")).to_be_visible()
    fiche.get_by_role("button", name="Fermer").click()
    sync_api.expect(fiche).to_be_hidden()

    # « Nouvel exercice » : la bibliothèque remplit nom et muscle.
    pg.get_by_text("Ajouter un exercice", exact=True).click()
    pg.get_by_role("button", name="Nouvel exercice").click()
    pg.get_by_role("button", name="Choisir un exercice").click()
    modale = pg.locator("body > div", has=pg.get_by_role("heading", name="Bibliothèque d'exercices"))
    sync_api.expect(modale).to_be_visible()
    ligne = modale.locator(".biblio-ligne:visible").last
    nom = ligne.locator(".biblio-nom").inner_text()
    ligne.click()
    assert pg.get_by_placeholder("Tape ou choisis un exercice déjà utilisé").input_value() == nom
    assert erreurs == []
    ctx.close()


def test_nutrition_plaques_et_gestion(serveur, navigateur):
    ctx = _contexte(navigateur)
    pg = ctx.new_page()
    erreurs = _espionner(pg)
    pg.goto(serveur + "/test-seed")
    pg.goto(serveur + "/test-login?vip=1")

    # Repas : s'ouvre, change de mode, se referme.
    pg.goto(serveur + "/nutrition")
    pg.locator(".meal-btn", has_text="Déjeuner").click()
    rapide = pg.locator(".mode-btn:visible", has_text="Saisie rapide")
    rapide.click()
    sync_api.expect(rapide).to_have_class("mode-btn active")
    pg.locator(".meal-btn", has_text="Déjeuner").click()
    sync_api.expect(rapide).to_be_hidden()

    # Disques : 100 kg sur une barre de 20 = 40 kg par côté.
    pg.goto(serveur + "/plaques")
    pg.locator("input[x-model\\.number=target]").fill("100")
    sync_api.expect(pg.locator(".plaque-sub")).to_have_text("40 kg par côté")
    sync_api.expect(pg.locator(".plaque-row").first).to_contain_text("25 kg")

    # Renommer un exercice de l'historique : le nombre de séries concernées.
    pg.goto(serveur + "/gestion")
    pg.get_by_text("Renommer un exercice (historique)").click()
    choix = pg.locator("select[name=old_name]")
    choix.select_option(index=1)
    pg.locator("input[name=new_name]").fill("Nom corrigé")
    compte = pg.locator("p", has_text="deviendront").locator("span").first
    assert int(compte.inner_text()) > 0
    assert erreurs == []
    ctx.close()
