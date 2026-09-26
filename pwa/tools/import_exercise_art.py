# -*- coding: utf-8 -*-
"""Prépare les illustrations d'exercices pour l'app.

Une image générée arrive en 2000×2000, 1,5 Mo, avec le sujet perdu au milieu
d'un grand fond. Telle quelle, elle est inutilisable : 87 fichiers feraient
130 Mo et la silhouette serait minuscule sur une carte de 130 px.

Ce script fait les quatre opérations qui manquent, et rien d'autre :

  1. **Recadrage sur le sujet** — le fond est uni, on le détecte par écart de
     luminance et on rogne au plus juste, avec une marge constante pour que
     toutes les illustrations aient la même respiration.
  2. **Fond rendu transparent** — l'illustration se pose alors sur n'importe
     quelle surface de l'app sans carré visible, y compris si le thème change.
  3. **Carré** — sinon les cartes sautillent selon la largeur du sujet.
  4. **WebP** — ~25 ko au lieu de 1,5 Mo, pour une taille d'affichage de 400 px
     (le double de l'affichage réel, pour les écrans à forte densité).

    cd pwa && python tools/import_exercise_art.py <dossier_source>
    cd pwa && python tools/import_exercise_art.py <dossier> --apercu
"""
import io
import os
import sys

from PIL import Image, ImageChops, ImageFilter

DESTINATION = os.path.join(os.path.dirname(__file__), "..", "static", "img", "exercises")
TAILLE = 400              # px, soit 2× la plus grande taille d'affichage prévue
MARGE = 0.06              # part de la plus grande dimension du sujet
SEUIL_FOND = 26           # écart de luminance à partir duquel un pixel est « sujet »
QUALITE = 82


def _masque_sujet(im):
    """Masque du sujet : tout ce qui s'écarte de la couleur du fond.

    Le fond n'est pas parfaitement uni (léger dégradé radial), donc on le
    mesure sur les quatre coins plutôt que sur un pixel unique.
    """
    l, h = im.size
    coins = [im.getpixel(p) for p in ((2, 2), (l - 3, 2), (2, h - 3), (l - 3, h - 3))]
    fond = tuple(sum(c[i] for c in coins) // len(coins) for i in range(3))

    ecart = ImageChops.difference(im.convert("RGB"), Image.new("RGB", im.size, fond))
    masque = ecart.convert("L").point(lambda v: 255 if v > SEUIL_FOND else 0)
    # Ferme les trous d'antialiasing sans grignoter la silhouette.
    return masque.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))


def preparer(chemin_source, chemin_sortie, taille=TAILLE):
    im = Image.open(chemin_source).convert("RGB")
    masque = _masque_sujet(im)

    boite = masque.getbbox()
    if not boite:
        raise ValueError(f"{os.path.basename(chemin_source)} : aucun sujet détecté")

    x1, y1, x2, y2 = boite
    cote = max(x2 - x1, y2 - y1)
    marge = int(cote * MARGE)
    cote += 2 * marge
    # Carré centré sur le sujet, quitte à déborder de l'image source : les
    # zones hors cadre sont transparentes, pas noires.
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    boite_carree = (cx - cote // 2, cy - cote // 2, cx + cote // 2, cy + cote // 2)

    rgba = im.convert("RGBA")
    rgba.putalpha(masque)
    decoupe = rgba.crop(boite_carree)
    return decoupe.resize((taille, taille), Image.LANCZOS)


def importer(dossier, destination=DESTINATION, taille=TAILLE):
    os.makedirs(destination, exist_ok=True)
    faits = []
    for nom in sorted(os.listdir(dossier)):
        base, ext = os.path.splitext(nom)
        if ext.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        sortie = os.path.join(destination, base + ".webp")
        img = preparer(os.path.join(dossier, nom), sortie, taille)
        img.save(sortie, "WEBP", quality=QUALITE, method=6)
        faits.append((base + ".webp", os.path.getsize(sortie) // 1024))
    return faits


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        raise SystemExit(1)
    resultats = importer(args[0])
    if not resultats:
        print("aucune image trouvée dans", args[0])
    for nom, ko in resultats:
        print(f"  {nom:34} {ko:4} ko")
    total = sum(ko for _, ko in resultats)
    print(f"{len(resultats)} illustration(s), {total} ko au total")
