"""Retour d'un utilisateur du 23/10, sur un vrai navigateur.

« Dernière fois affiche le poids de la dernière série : on ne voit pas ce
qu'on a fait la dernière fois, compliqué pour charger plus. » Et « le chrono
ne garde pas entre deux exos » : 90 s inscrites sur chaque exercice par
l'éditeur passaient avant la durée choisie dans la barre.
"""
import datetime as dt

import pytest


@pytest.fixture()
def pg(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 390, "height": 844}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('notifPrompted','1');localStorage.setItem('tutoSeen','true');"
                        "localStorage.setItem('tutoSeanceSeen','true');")
    page = ctx.new_page()
    page.erreurs = []
    page.on("pageerror", lambda e: page.erreurs.append(str(e)))
    page.goto(serveur + "/test-vierge")
    yield page
    ctx.close()


def _ouvrir(pg, serveur, date=None):
    pg.goto(serveur + "/seance?mode=prefaite&name=Push" + (f"&date={date}" if date else ""))
    pg.wait_for_selector("#exo-anchor-0")
    pg.evaluate("Alpine.$data(document.querySelector('#exo-anchor-0')).open = true")


def _serie(pg, carte, reps, poids):
    sel = f"#exo-anchor-{carte}"
    n = pg.evaluate(f"Alpine.$data(document.querySelector('{sel}')).indexCourant()") + 1
    pg.locator(sel).get_by_label(f"Répétitions série {n}", exact=True).fill(str(reps))
    pg.locator(sel).get_by_label(f"Poids série {n}", exact=True).fill(str(poids))
    with pg.expect_response(lambda r: "/seance/save-exo" in r.url):
        pg.locator(sel).locator(".serie-encours").nth(n - 1).locator(".serie-valider").click()
    pg.wait_for_timeout(150)


def _derniere_fois(pg, carte):
    loc = pg.locator(f"#exo-anchor-{carte} .exo-last-session").first
    return loc.inner_text().replace(" ", " ") if loc.count() else ""


def _repos_en_cours(pg):
    return pg.evaluate("(JSON.parse(localStorage.getItem('rest_timer_state') || 'null') || {}).total")


def test_derniere_fois_reste_la_seance_precedente(pg, serveur):
    _ouvrir(pg, serveur, (dt.date.today() - dt.timedelta(days=7)).isoformat())
    for reps, poids in ((5, 60), (5, 62.5), (4, 65)):
        _serie(pg, 0, reps, poids)

    _ouvrir(pg, serveur)
    attendu = "Dernière fois : 60 kg × 5, 62,5 kg × 5, 65 kg × 4"
    assert _derniere_fois(pg, 0) == attendu
    _serie(pg, 0, 5, 67.5)
    _serie(pg, 0, 5, 67.5)
    assert _derniere_fois(pg, 0) == attendu          # et non « 67,5 kg × 5 »

    # Un exercice jamais fait n'a pas de « Dernière fois », même après une série.
    pg.evaluate("Alpine.$data(document.querySelector('#exo-anchor-1')).open = true")
    _serie(pg, 1, 10, 30)
    assert _derniere_fois(pg, 1) == ""
    assert pg.erreurs == []


def test_la_duree_choisie_passe_a_l_exercice_suivant(pg, serveur):
    """Programme enregistré par l'éditeur : 90 s inscrites partout."""
    _ouvrir(pg, serveur)
    for base in ("Développé couché", "Développé militaire"):
        assert pg.evaluate("""(b) => fetch('/seance/repos', {method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({seance: 'Push', base: b, rest_seconds: 90})}).then(r => r.status)""",
                           base) == 200
    _ouvrir(pg, serveur)
    _serie(pg, 0, 5, 60)
    assert _repos_en_cours(pg) == 90
    pg.locator("#rest-timer .rest-timer-bar-presets button[data-sec='180']").click()
    assert _repos_en_cours(pg) == 180

    pg.evaluate("Alpine.$data(document.querySelector('#exo-anchor-1')).open = true")
    _serie(pg, 1, 10, 30)
    assert _repos_en_cours(pg) == 180               # repartait à 90
    assert pg.erreurs == []
