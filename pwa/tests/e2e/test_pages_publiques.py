"""Les deux pages qu'on voit avant d'être connecté, sur un vrai téléphone.

Retour du propriétaire (14/10/2026) : sur la connexion, un grand espace noir
au-dessus du nom et de « Continuer avec Google » ; le bloc était calé en
bas de l'écran. Mesuré ici dans Chromium, à la taille d'un téléphone.
"""
import pytest

sync_api = pytest.importorskip("playwright.sync_api")


@pytest.mark.parametrize("largeur,hauteur", [(384, 854), (375, 667)])
def test_la_connexion_est_centree_dans_l_ecran(serveur, navigateur, largeur, hauteur):
    ctx = navigateur.new_context(viewport={"width": largeur, "height": hauteur})
    page = ctx.new_page()
    page.goto(serveur + "/login", wait_until="networkidle")
    haut = page.locator(".login-wrap > *").first.bounding_box()["y"]
    bas = page.locator("#google").bounding_box()
    vide_dessous = hauteur - (bas["y"] + bas["height"])
    ctx.close()
    # Avant (calé en bas) : 590 px de vide au-dessus et 40 dessous à 384 × 854 ;
    # centré : 265 et 281.
    assert abs(haut - vide_dessous) < 0.15 * hauteur, (haut, vide_dessous)
