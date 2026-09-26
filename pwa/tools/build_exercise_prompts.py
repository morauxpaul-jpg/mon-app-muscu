# -*- coding: utf-8 -*-
"""Écrit `exercise_prompts.json` : un prompt d'illustration par exercice.

Le style est décrit UNE fois et répété à l'identique partout — c'est ce qui
donne 87 images qui se ressemblent plutôt que 87 images différentes. Le nom
de fichier attendu vient de la même fonction que celle qui le cherche à
l'exécution (`illustration_slug`), donc les deux ne peuvent pas diverger.

    cd pwa && python tools/build_exercise_prompts.py
"""
import io
import json
import os
import sys

# La console Windows est en cp1252 : sans ça, un simple accent dans un
# message fait planter le script après que le travail est fait.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.exercises_data import EXERCISES_INFO, illustration_slug  # noqa: E402

SORTIE = os.path.join(os.path.dirname(__file__), "exercise_prompts.json")

STYLE = (
    "clean 3D render, neutral grey matte mannequin, no facial features, "
    "plain very dark navy background, soft studio lighting, centered full "
    "body, square 1:1, minimal, no text, no watermark, no logo, no floor grid"
)

GABARIT = (
    "{style}. The mannequin is performing: {geste}. "
    "Highlight the {muscle} in soft red-orange, the rest of the body stays grey. "
    "Camera angle: {angle}."
)


def _angle(nom):
    """Poussées et tirages se lisent de profil ; élévations et écartés, de face."""
    n = nom.lower()
    if any(m in n for m in ("elevation", "élévation", "latéra", "latera",
                            "écarté", "ecarte", "oiseau", "papillon")):
        return "front view, slight 3/4"
    if any(m in n for m in ("squat", "fente", "presse", "soulevé", "souleve",
                            "hip thrust")):
        return "side view, 3/4 angle"
    return "side view"


def construire():
    entrees = []
    for nom, fiche in sorted(EXERCISES_INFO.items()):
        description = (fiche.get("description") or "").split(".")[0].strip()
        entrees.append({
            "nom": nom,
            "fichier": illustration_slug(nom) + ".png",
            "prompt": GABARIT.format(
                style=STYLE,
                geste=f"{nom} ({description})" if description else nom,
                muscle=(fiche.get("muscles") or ["the target muscle"])[0],
                angle=_angle(nom),
            ),
        })
    return entrees


if __name__ == "__main__":
    entrees = construire()
    io.open(SORTIE, "w", encoding="utf-8", newline="\n").write(
        json.dumps(entrees, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(entrees)} prompts → {SORTIE}")
