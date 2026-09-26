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
    "clean 3D render of ONE single mannequin — exactly one figure, one single "
    "frozen pose, never a sequence and never two figures in the same image. "
    "Shop-window mannequin made of flat matte grey clay: completely smooth "
    "blank egg-shaped head with NO face at all — no eyes, no nose, no mouth, "
    "no ears, no hair. Smooth featureless torso, no skin texture, no nipples, "
    "no navel, wearing plain fitted dark grey shorts. Pure black background, soft studio "
    "lighting, the figure fills the frame, square 1:1, minimal, no text, "
    "no watermark, no logo, no floor grid"
)

# Quelques fiches décrivent l'exercice PAR RAPPORT à un autre (« même principe
# que le curl classique ») : lisible pour un humain qui connaît le curl,
# inutilisable pour un modèle d'image, qui dessine alors n'importe quoi.
# Pour celles-là seulement, le geste est écrit ici.
GESTES = {
    # Le depart d'un Arnold press, c'est deux halteres devant la poitrine :
    # exactement un curl. Seule la fin du mouvement le distingue.
    "Arnold press": "standing, both arms fully extended STRAIGHT UP overhead, "
                    "one dumbbell locked out above each shoulder, palms facing "
                    "forward at the top of a shoulder press",
    # Premier essai : allonge par terre, sans banc, avec une barre bancale.
    "Barre au front": "lying flat on their back on a weight bench, upper arms "
                      "pointing straight up and STILL, elbows bent so that the "
                      "barbell is lowered down to just above the forehead",
    # Premier essai : un seul haltere court tenu d'une main.
    "Curl barre": "standing, both hands gripping ONE long straight barbell, "
                  "one hand near each end of the bar, palms facing up, elbows "
                  "pinned to the sides, the bar curled up to chest height",
    "Développé incliné": "lying back on a bench inclined at 30-45 degrees, "
                            "pressing a barbell straight up above the upper chest",
    "Fentes alternées": "mid-lunge, one leg forward with the knee bent at 90 "
                         "degrees, the other knee lowered towards the floor, "
                         "torso upright",
    "Fentes sautées": "jumping upward out of a deep lunge, both feet off the "
                       "floor, legs swapping in mid-air",
    "Élévations latérales haltères": "standing, arms raised straight out "
                                       "sideways to shoulder height, a light "
                                       "dumbbell in each hand",
}

# Pas de muscle en couleur dans l'illustration : la fiche affiche déjà une
# carte anatomique juste en dessous (`exo-info-bodymap`), calculée à partir
# des muscles déclarés — donc juste à 100 %. Le modèle d'image, lui, recopiait
# la zone rouge de l'image de référence : tous les exercices ressortaient avec
# les épaules en rouge, y compris le curl. Un seul rôle par image : celle-ci
# montre le GESTE.
# Le rouge ne peut pas être « le muscle de la fiche » tel quel : « Dos (grand
# dorsal) » ne dit pas à un modèle d'image où peindre, et « Triceps » sans
# précision se retrouve régulièrement peint sur les biceps. Chaque libellé est
# traduit en une ZONE : le nom anatomique, puis où elle se trouve sur le corps.
ZONES = {
    "Quadriceps": "quadriceps, on the FRONT of both thighs",
    "Ischio-jambiers": "hamstrings, on the BACK of both thighs",
    "Fessiers": "gluteal muscles of the buttocks",
    "Mollets (gastrocnémiens)": "calf muscles on the BACK of both lower legs",
    "Mollets (soléaire)": "lower calf, on the BACK of both lower legs just "
                           "above the ankle",
    "Pectoraux": "pectoral muscles across the chest",
    "Pectoraux (bas)": "LOWER pectoral muscles, the bottom edge of the chest",
    "Pectoraux (haut)": "UPPER pectoral muscles, just below the collarbones",
    "Pectoraux (milieu + intérieur)": "INNER pectoral muscles, along the "
                                       "middle of the chest",
    "Dos (grand dorsal)": "latissimus dorsi, the broad fan-shaped muscles on "
                          "both sides of the BACK, below the armpits",
    "Dos (milieu)": "mid-back muscles between the shoulder blades",
    "Dos (érecteurs)": "erector spinae, the two columns running along the "
                       "lower spine",
    "Lombaires": "lower back muscles either side of the lumbar spine",
    "Trapèzes (supérieurs)": "upper trapezius, the slope between the neck and "
                               "the shoulders",
    "Trapèzes (partie haute)": "upper trapezius, the slope between the neck "
                                "and the shoulders",
    "Épaules": "deltoid muscles capping both shoulders",
    "Épaules (deltoïdes)": "deltoid muscles capping both shoulders",
    "Épaules (3 faisceaux)": "deltoid muscles capping both shoulders",
    "Épaules (deltoïdes latéraux)": "SIDE deltoids, on the outer edge of both "
                                      "shoulders",
    "Épaules (deltoïdes postérieurs)": "REAR deltoids, at the BACK of both "
                                         "shoulders",
    "Biceps": "biceps, on the FRONT of both upper arms",
    "Biceps (brachial)": "biceps, on the FRONT of both upper arms",
    "Biceps (longue portion)": "biceps, on the FRONT of both upper arms",
    "Triceps": "triceps, on the BACK of both upper arms",
    "Triceps (3 chefs)": "triceps, on the BACK of both upper arms",
    "Triceps (longue portion)": "triceps, on the BACK of both upper arms",
    "Abdominaux": "rectus abdominis, the front of the stomach",
    "Abdominaux (grand droit)": "rectus abdominis, the front of the stomach",
    "Abdominaux (partie basse)": "LOWER abdominals, below the navel",
    "Obliques": "oblique muscles on both sides of the waist",
    # Un corps entier tout rouge ne désigne rien : pas de coloriage.
    "Corps entier": None,
}


def _zone(fiche):
    """Le muscle à peindre en rouge, décrit pour un modèle d'image.

    Renvoie None quand il n'y a rien à désigner — mieux vaut pas de rouge
    du tout qu'un rouge au mauvais endroit, qui apprend une anatomie fausse.
    """
    muscles = fiche.get("muscles") or []
    return ZONES.get(muscles[0]) if muscles else None


GABARIT = (
    "{style}. The mannequin is performing: {geste}. "
    "Show the single most RECOGNISABLE instant of this movement — the "
    "position that makes it impossible to confuse with any other exercise, "
    "not necessarily the starting position. "
    "Camera angle: {angle}.{muscle}"
)

# Le coloriage est une phrase à part : elle disparaît entièrement quand il
# n'y a pas de zone à désigner, plutôt que de laisser un « highlight the None ».
COLORIAGE = (
    " Paint ONLY the {zone} in a flat soft red-orange overlay. "
    "Every other part of the body stays plain matte grey — exactly one "
    "red area in the whole image, and it must be the {zone}."
)
SANS_COLORIAGE = (
    " The entire body stays plain matte grey — no coloured muscle anywhere."
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


def _geste(nom, fiche):
    """Ce que le mannequin doit être en train de faire.

    La description complète, pas sa première phrase : celle-ci donne souvent
    la POSITION DE DÉPART, qui est partagée par des exercices opposés. « Barre
    au front » commence par « Allongé sur un banc, barre à bout de bras
    au-dessus de la poitrine » — tronquée là, c'est le développé couché, et
    c'est exactement ce que le modèle avait dessiné. Le mouvement (« fléchir
    les coudes pour descendre la barre vers le front ») est dans la phrase
    suivante.
    """
    if nom in GESTES:
        return f"{nom} — {GESTES[nom]}"
    description = " ".join((fiche.get("description") or "").split()).strip()
    return f"{nom} ({description})" if description else nom


def construire():
    entrees = []
    for nom, fiche in sorted(EXERCISES_INFO.items()):
        entrees.append({
            "nom": nom,
            "fichier": illustration_slug(nom) + ".png",
            "prompt": GABARIT.format(
                style=STYLE,
                geste=_geste(nom, fiche),
                angle=_angle(nom),
                muscle=(COLORIAGE.format(zone=_zone(fiche))
                        if _zone(fiche) else SANS_COLORIAGE),
            ),
        })
    return entrees


if __name__ == "__main__":
    entrees = construire()
    io.open(SORTIE, "w", encoding="utf-8", newline="\n").write(
        json.dumps(entrees, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(entrees)} prompts → {SORTIE}")
