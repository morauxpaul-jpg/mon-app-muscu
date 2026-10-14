"""L'icône de l'app suit le style « Instrument » : noir et vert, rien d'autre.

L'ancienne était un haltère bleu « en verre », avec reflets et halo : le
style que le propriétaire a voulu quitter. Ces tests gardent la porte
fermée à un retour du dégradé, et vérifient que l'icône supporte d'être
rognée en rond (le manifeste la sert aussi en « maskable »).
"""
import math

import pytest
from PIL import Image

FOND = (0x00, 0x00, 0x00)
VERT = (0xC8, 0xF0, 0x31)


@pytest.mark.parametrize("taille", [192, 512])
def test_licone_a_la_taille_annoncee_par_le_manifeste(taille):
    with Image.open(f"static/icon-{taille}.png") as im:
        assert im.size == (taille, taille)


@pytest.mark.parametrize("taille", [192, 512])
def test_licone_na_que_le_noir_et_le_vert_de_lapp(taille):
    """Tout pixel est du noir, du vert, ou un mélange des deux sur un bord
    adouci. Une troisième couleur, un dégradé ou un reflet sortirait de ce
    segment."""
    with Image.open(f"static/icon-{taille}.png") as im:
        im = im.convert("RGB")
        intrus = []
        for x in range(taille):
            for y in range(taille):
                r, v, b = im.getpixel((x, y))
                t = v / VERT[1]
                attendu = tuple(round(c * t) for c in VERT)
                if max(abs(a - e) for a, e in zip((r, v, b), attendu)) > 6:
                    intrus.append((x, y, (r, v, b)))
        assert not intrus, intrus[:5]


def test_lhaltere_tient_dans_le_cercle_que_android_garde():
    """Une icône « maskable » peut être rognée jusqu'au cercle de 80 % du
    côté. Un disque qui en dépasse serait coupé sur l'écran d'accueil."""
    with Image.open("static/icon-512.png") as im:
        im = im.convert("RGB")
        hors = [(x, y) for x in range(512) for y in range(512)
                if im.getpixel((x, y)) != FOND
                and math.hypot(x - 256, y - 256) > 0.4 * 512]
    assert not hors, hors[:5]
