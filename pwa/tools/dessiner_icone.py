# -*- coding: utf-8 -*-
"""Dessine l'icône de l'app : un haltère vert sur fond noir (style « Instrument »).

Choisie par le propriétaire le 14/10/2026 parmi trois propositions. Deux
couleurs seulement, celles de l'app : fond `--bg-base` (#000000) et
`--accent` (#c8f031). Ni dégradé, ni ombre, ni reflet.

La géométrie est écrite ici, sur une grille de 512 : l'icône se redessine
à l'identique, à n'importe quelle taille, sans fichier source à retrouver.
Le dessin est fait à 8 fois la taille puis réduit par moyenne (BOX), pour
des bords lisses. Pas LANCZOS : il « surcompense » aux angles et laissait
des pixels plus clairs que le vert de l'app (halo vu par tests/test_icone.py).

L'haltère tient dans le cercle central de 80 % : le manifeste sert le même
fichier en « maskable », et Android peut rogner l'icône en rond.

    cd pwa && python tools/dessiner_icone.py
"""
import os
import sys

from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FOND = (0x00, 0x00, 0x00)
VERT = (0xC8, 0xF0, 0x31)
GRILLE = 512
SURECHANTILLON = 8

# (x, y, largeur, hauteur, rayon des coins), sur la grille de 512.
HALTERE = [
    (86, 234, 20, 44, 4),     # embout gauche
    (112, 178, 38, 156, 6),   # petit disque gauche
    (158, 142, 42, 228, 6),   # grand disque gauche
    (200, 243, 112, 26, 0),   # barre
    (312, 142, 42, 228, 6),   # grand disque droit
    (362, 178, 38, 156, 6),   # petit disque droit
    (406, 234, 20, 44, 4),    # embout droit
]

DOSSIER = os.path.join(os.path.dirname(__file__), "..", "static")


def dessiner(taille):
    grand = taille * SURECHANTILLON
    echelle = grand / GRILLE
    im = Image.new("RGB", (grand, grand), FOND)
    d = ImageDraw.Draw(im)
    for x, y, l, h, r in HALTERE:
        boite = [x * echelle, y * echelle,
                 (x + l) * echelle - 1, (y + h) * echelle - 1]
        if r:
            d.rounded_rectangle(boite, radius=r * echelle, fill=VERT)
        else:
            d.rectangle(boite, fill=VERT)
    return im.resize((taille, taille), Image.BOX)


if __name__ == "__main__":
    for taille in (512, 192):
        chemin = os.path.join(DOSSIER, f"icon-{taille}.png")
        dessiner(taille).save(chemin, optimize=True)
        print(f"{os.path.normpath(chemin)} : {os.path.getsize(chemin) // 1024} ko")
