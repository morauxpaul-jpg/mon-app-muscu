"""Le coach affiche ses réponses (retour du 14/10 : « le coach est cassé »).

Depuis le passage d'Alpine en version CSP (10/10), les bulles étaient
rendues par `x-html`, que cette version refuse : chaque réponse arrivait,
était enregistrée et comptée dans le quota… puis s'affichait vide. Le test
de la CSP ouvrait /coach sans conversation : aucune bulle, rien à voir.
Ici : une conversation existante, puis une question posée pour de vrai
(IA simulée qui répond en flux, run_local_fake.py)."""
import pytest

sync_api = pytest.importorskip("playwright.sync_api")


def _page(navigateur, serveur):
    ctx = navigateur.new_context(viewport={"width": 375, "height": 812}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true');")
    pg = ctx.new_page()
    erreurs = []
    pg.on("console", lambda m: erreurs.append(m.text) if "Alpine" in m.text else None)
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    rep = pg.goto(serveur + "/test-seed")
    return ctx, pg, erreurs, rep.json()["conversation_id"]


def test_une_conversation_rouverte_affiche_ses_messages(serveur, navigateur):
    ctx, pg, erreurs, conv = _page(navigateur, serveur)
    pg.goto(f"{serveur}/coach?c={conv}", wait_until="networkidle")
    bulles = pg.locator(".msg-group .msg-bubble")
    textes = [t.strip() for t in bulles.all_inner_texts()]
    ctx.close()
    assert len(textes) == 2 and all(textes), textes
    # Les deux messages de la démo ont la même heure : l'ordre n'est pas fixé.
    assert any("Je stagne à 80 kg" in t for t in textes), textes
    assert any("80 kg × 8" in t for t in textes), textes
    assert erreurs == []


def test_une_question_recoit_une_reponse_lisible(serveur, navigateur):
    ctx, pg, erreurs, _ = _page(navigateur, serveur)
    pg.goto(serveur + "/coach", wait_until="networkidle")
    pg.click("textarea")
    pg.keyboard.type("Comment progresser")
    pg.keyboard.press("Shift+Enter")              # à la ligne, sans envoyer
    pg.keyboard.type("au développé couché ?")
    pg.keyboard.press("Enter")                    # envoie (le raccourci ne partait jamais)
    reponse = pg.locator(".msg-bot .msg-bubble strong", has_text="4 × 6")
    reponse.wait_for(timeout=10000)
    bulle = pg.locator(".msg-group .msg-bot .msg-bubble").last
    texte = bulle.inner_text()
    lien = bulle.locator("a.coach-link").get_attribute("href")
    question = pg.locator(".msg-group .msg-user .msg-bubble").last.inner_text()
    ctx.close()
    assert "Comment progresser\nau développé couché ?" in question
    assert "Ajoute une rep par séance" in texte and "programme" in texte, texte
    assert lien == "/programme"
    assert erreurs == []
