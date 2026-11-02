"""Séance créée par le coach, de bout en bout : un compte PRO dont la
dernière séance date de plusieurs mois demande une reprise ; le coach
propose la séance (IA simulée, 3 s : la page suit la tâche), les charges
conseillées viennent de l'historique, et la séance ajoutée au programme
s'ouvre avec ces charges allégées pré-remplies."""
import pytest

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect


def test_une_reprise_creee_par_le_coach_pre_remplit_des_charges_allegees(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 390, "height": 844}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('notifPrompted','1');localStorage.setItem('tutoSeen','true');"
                        "localStorage.setItem('tutoSeanceSeen','true');")
    pg = ctx.new_page()
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.on("console", lambda m: erreurs.append(m.text)
          if ("Alpine" in m.text or "Content Security Policy" in m.text) else None)
    # Compte PRO, historique de six semaines arrêté le 12/06/2026 : la pause
    # dépasse 120 jours, d'où −45 %. Développé couché : 82,5 kg au plus haut
    # de ses trois dernières séances → 45 kg (arrondi à 2,5 kg).
    pg.goto(serveur + "/test-seed")

    pg.goto(serveur + "/coach")
    pg.locator("#coach-seance-lien").click()
    pg.wait_for_url("**/coach/seance")
    expect(pg.locator("#cs-pause")).to_contain_text("−45 %")
    expect(pg.get_by_label("Reprise après une pause")).to_be_checked()
    pg.locator("#cs-demande").fill("épaule fragile")
    pg.get_by_role("button", name="Créer la séance").click()
    expect(pg.locator("#cs-etat")).to_contain_text("Le coach prépare ta séance")
    resultat = pg.locator("#cs-resultat")
    expect(resultat).to_be_visible(timeout=15000)
    expect(pg.locator("#cs-nom")).to_have_text("Reprise")
    lignes = pg.locator("#cs-exos li")
    expect(lignes).to_have_count(3)
    expect(lignes.nth(0)).to_contain_text("Développé couché · 3 × 8-10")
    expect(lignes.nth(0)).to_contain_text("Reprise : 45 kg, −45 % de tes 82,5 kg habituels.")
    expect(lignes.nth(1)).to_contain_text("Reprise : 4 reps, −45 % de tes 9 habituelles")
    expect(lignes.nth(2).locator(".cs-exo-conseil")).to_have_count(0)    # gainage : jamais fait

    pg.get_by_role("button", name="Ajouter à mon programme").click()
    pg.wait_for_url("**/seance?mode=prefaite&name=Reprise**")
    pg.wait_for_selector("#exo-anchor-0")
    pg.evaluate("Alpine.$data(document.querySelector('#exo-anchor-0')).open = true")
    carte = pg.locator("#exo-anchor-0")
    expect(carte.locator(".exo-suggestion")).to_contain_text("Reprise : 45 kg, −45 % de tes 82,5 kg habituels")
    expect(carte.get_by_label("Poids série 1", exact=True)).to_have_value("45")

    # La séance est dans le programme, hors planning.
    prog = pg.evaluate("() => fetch('/test-programme').then(r => r.json())")
    assert [e["name"] for e in prog["Reprise"]] == ["Développé couché", "Tractions", "Gainage"]
    assert "Reprise" not in prog["_planning"].values()
    assert erreurs == [], erreurs
