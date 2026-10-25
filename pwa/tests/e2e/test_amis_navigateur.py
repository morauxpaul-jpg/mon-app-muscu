"""Amis, de bout en bout, à deux comptes (et un troisième qui n'est l'ami
de personne) : le lien d'ami copié, ouvert par l'autre, la demande
acceptée, une séance terminée qui arrive dans le fil, l'encouragement et
son compteur. Le non-ami ne voit rien et ne peut pas encourager."""
import pytest

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect


def _page(navigateur, serveur, uid, prenom, code, presse_papier=False):
    ctx = navigateur.new_context(viewport={"width": 390, "height": 844}, locale="fr-FR")
    if presse_papier:
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=serveur)
    ctx.add_init_script("localStorage.setItem('notifPrompted','1');localStorage.setItem('tutoSeen','true');"
                        "localStorage.setItem('tutoSeanceSeen','true');")
    pg = ctx.new_page()
    pg.erreurs = []
    pg.on("pageerror", lambda e: pg.erreurs.append(str(e)))
    pg.on("console", lambda m: pg.erreurs.append(m.text)
          if ("Alpine" in m.text or "Content Security Policy" in m.text) else None)
    pg.goto(f"{serveur}/test-compte?uid={uid}&prenom={prenom}&code={code}")
    pg.wait_for_url("**/amis")
    return pg


def _terminer_une_seance(pg, serveur):
    pg.goto(serveur + "/seance?mode=prefaite&name=Push")
    pg.wait_for_selector("#exo-anchor-0")
    pg.evaluate("Alpine.$data(document.querySelector('#exo-anchor-0')).open = true")
    carte = pg.locator("#exo-anchor-0")
    carte.get_by_label("Répétitions série 1", exact=True).fill("5")
    carte.get_by_label("Poids série 1", exact=True).fill("60")
    with pg.expect_response(lambda r: "/seance/save-exo" in r.url):
        carte.locator(".serie-encours").nth(0).locator(".serie-valider").click()
    pg.locator("#finish-open").click()
    pg.locator("#finish-save").click()
    pg.wait_for_url("**/accueil**", timeout=15000)


def test_deux_comptes_deviennent_amis_et_s_encouragent(serveur, navigateur):
    navigateur.new_page().goto(serveur + "/test-vierge")      # base neuve
    paul = _page(navigateur, serveur, "u-paul", "Paul", "paulpaul", presse_papier=True)
    marc = _page(navigateur, serveur, "u-marc", "Marc", "marcmarc")
    zoe = _page(navigateur, serveur, "u-zoe", "Zoe", "zoezoezo")

    # Paul copie son lien d'ami (le même bloc que la page Parrainage).
    lien = paul.locator("#amis-ajouter .inv-lien").input_value()
    assert lien == serveur + "/?ref=paulpaul&ami=1"
    paul.locator("#amis-ajouter .inv-copier").click()
    expect(paul.get_by_text("Lien copié")).to_be_visible()
    assert paul.evaluate("() => navigator.clipboard.readText()") == lien

    # Marc ouvre le lien : on lui propose d'envoyer la demande, rien n'est encore parti.
    marc.goto(lien)
    marc.wait_for_url("**/amis?code=paulpaul")
    marc.get_by_role("button", name="Envoyer une demande à Paul").click()
    expect(marc.locator("#amis-message")).to_contain_text("Demande envoyée")
    expect(marc.locator("#amis-envoyees")).to_contain_text("Paul")

    # Paul accepte.
    paul.goto(serveur + "/amis")
    paul.get_by_role("button", name="Accepter Marc").click()
    expect(paul.locator("#amis-message")).to_have_text("Vous êtes amis.")
    expect(paul.locator("#amis-liste")).to_contain_text("Marc")

    # Marc termine une séance : elle arrive dans le fil de Paul.
    _terminer_une_seance(marc, serveur)
    paul.goto(serveur + "/amis")
    seance = paul.locator("article.amis-seance", has_text="Marc")
    expect(seance).to_contain_text("Push")
    expect(seance).to_contain_text("300 kg soulevés")
    expect(seance).to_contain_text("Développé couché · 60 kg")

    # Zoé n'est l'amie de personne : rien dans son fil, et pas d'encouragement possible.
    zoe.goto(serveur + "/amis")
    expect(zoe.locator("article.amis-seance")).to_have_count(0)
    sid = seance.get_attribute("id")[2:]
    statut = zoe.evaluate("""([sid]) => fetch('/amis/encourager', {method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded',
                  'X-CSRFToken': document.querySelector('meta[name=csrf-token]').content},
        body: 'compte=u-marc&session=' + sid, redirect: 'manual'}).then(r => r.status)""", [sid])
    assert statut == 404

    # Paul encourage, une fois ; Marc voit le compteur.
    seance.get_by_role("button", name="Encourager Marc pour Push").click()
    expect(paul.locator(f"#s-{sid}")).to_contain_text("Encouragé")
    expect(paul.locator(f"#s-{sid}").get_by_role("button")).to_have_count(0)
    marc.goto(serveur + "/amis")
    expect(marc.locator(f"#s-{sid}")).to_contain_text("1 encouragement")

    # Marc retire Paul : Paul ne voit plus la séance.
    marc.locator("#amis-liste summary", has_text="Retirer").click()
    marc.get_by_role("button", name="Oui, retirer Paul").click()
    expect(marc.locator("#amis-message")).to_contain_text("Ami retiré")
    paul.goto(serveur + "/amis")
    expect(paul.locator(f"#s-{sid}")).to_have_count(0)

    for p in (paul, marc, zoe):
        assert p.erreurs == [], p.erreurs
