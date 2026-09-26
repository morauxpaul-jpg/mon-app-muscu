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
    "no navel, wearing plain fitted dark grey shorts. Pure black background, "
    "soft studio lighting. The WHOLE figure, head to feet, fits inside the "
    "frame with a small margin — never crop a limb. Square 1:1, minimal, no "
    "text, no watermark, no logo, no floor grid"
)

# Quelques fiches décrivent l'exercice PAR RAPPORT à un autre (« même principe
# que le curl classique ») : lisible pour un humain qui connaît le curl,
# inutilisable pour un modèle d'image, qui dessine alors n'importe quoi.
# Pour celles-là seulement, le geste est écrit ici.
GESTES = {
    # Le départ d'un Arnold press, c'est deux haltères devant la poitrine :
    # exactement un curl. Seule la fin du mouvement le distingue.
    "Arnold press": "standing, both arms fully extended STRAIGHT UP overhead, "
                    "one dumbbell locked out above each shoulder, palms facing "
                    "forward at the top of a shoulder press",
    # Deux essais : d'abord par terre sans banc, puis sur un banc mais bras
    # tendus — c'est-à-dire un développé couché. Le verrouillage est l'image
    # iconique du banc, le modèle y retombe si on ne l'interdit pas.
    "Barre au front": "lying flat on their back on a weight bench, upper arms "
                      "vertical and STILL, elbows folded to a sharp angle so "
                      "the forearms point back over the head and the barbell "
                      "almost touches the forehead. The arms are NOT locked "
                      "out and the bar is NOT above the chest",
    # Deux essais : un haltère court tenu d'une main, puis la bonne barre
    # mais bras quasi tendus, barre à la taille.
    "Curl barre": "standing, both hands gripping ONE long straight barbell, "
                  "one hand near each end, palms facing up, upper arms "
                  "vertical and pinned to the sides, elbows folded so the "
                  "forearms point UP and the bar is already raised to chest "
                  "height. The arms are NOT hanging down",
    "Développé incliné": "lying back on a bench inclined at 30-45 degrees, "
                         "pressing a barbell straight up above the upper chest",
    "Fentes alternées": "mid-lunge, one leg forward with the knee bent at 90 "
                        "degrees, the other knee lowered towards the floor, "
                        "torso upright",
    "Fentes sautées": "jumping upward out of a deep lunge, both feet off the "
                      "floor, legs swapping in mid-air",
    "Élévations latérales haltères": "standing, arms raised straight out "
                                     "sideways to shoulder height, a light "
                                     "dumbbell in each hand. The arms are NOT "
                                     "hanging down and there is NO barbell",
    # ── Les huit que la référence a tirés vers sa propre pose ──────
    # La référence montre un mannequin DEBOUT, une barre à hauteur de
    # poitrine. Huit exercices sont ressortis exactement comme ça, alors que
    # leur fiche disait autre chose : les tractions « suspendu à une barre
    # fixe » ont donné un homme debout, barre derrière la nuque. Interdire
    # la pose de la référence en général n'a pas suffi ; ici on la nomme.
    "Tractions": "HANGING from a high horizontal bar by both hands, palms "
                 "facing forward, arms overhead, FEET OFF THE GROUND and "
                 "clear of it, pulling the chin up to the bar. The mannequin "
                 "is NOT standing and there is NO barbell across the "
                 "shoulders",
    "Tractions (ou tirage vertical)": "HANGING from a high horizontal bar by "
                                      "both hands, arms overhead, FEET OFF "
                                      "THE GROUND, pulling the chin up to "
                                      "the bar. The mannequin is NOT standing",
    "Tractions lestées": "HANGING from a high horizontal bar by both hands, "
                         "arms overhead, FEET OFF THE GROUND, a weight plate "
                         "hanging from a belt at the waist. The mannequin is "
                         "NOT standing",
    "Rowing barre": "standing but BENT FORWARD at the hips to about 45 "
                    "degrees, back flat, the barbell hanging from straight "
                    "arms and pulled up to the navel. The torso is NOT "
                    "upright",
    "Tirage vertical": "SEATED at a lat pulldown machine, thighs under the "
                       "pads, both hands gripping a wide bar hanging from "
                       "the cable above, pulling it down to the upper chest. "
                       "The mannequin is NOT standing",
    "Tirage horizontal poulie": "SEATED on the floor pad of a low cable row "
                                "machine, legs out in front and slightly "
                                "bent, pulling a handle back to the stomach, "
                                "torso upright. The mannequin is NOT standing",
    "Développé incliné haltères": "lying back on a bench inclined at 30-45 "
                                   "degrees, pressing ONE DUMBBELL IN EACH "
                                   "HAND straight up above the upper chest. "
                                   "The mannequin is NOT standing and there "
                                   "is NO barbell",
    "Développé militaire haltères": "standing, pressing ONE DUMBBELL IN EACH "
                                    "HAND from shoulder height up to full "
                                    "extension overhead. There is NO barbell",
}

# Le rouge ne peut pas être « le muscle de la fiche » tel quel : « Dos (grand
# dorsal) » ne dit pas à un modèle d'image où peindre, et « Triceps » sans
# précision a fini peint sur le torse, près de l'aisselle. Chaque libellé est
# traduit en une ZONE : un nom court qui sert d'ancre, la description de
# l'endroit sur le corps, et pour les zones qui ont raté, ce qu'il ne faut
# surtout PAS peindre — les bornes valent mieux qu'une désignation seule.
#
# Les libellés se répètent (« Triceps », « Triceps (3 chefs) »…) : ils
# partagent la même définition plutôt que trois copies qui divergeront.
BICEPS = ("biceps",
          "the bulge on the FRONT of each upper arm, strictly "
          "BETWEEN the shoulder joint and the elbow",
          " Do not paint the chest, the shoulder or the forearm.")
TRICEPS = ("triceps",
           "the BACK of each upper arm, strictly BETWEEN the "
           "shoulder joint and the elbow",
           " Do not paint the chest, the shoulder or the forearm.")
DELTOIDES = ("deltoids", "the rounded caps of both shoulders", "")
ABDOS = ("abdominals", "the front of the stomach, between the ribs "
         "and the navel", "")
TRAPEZES = ("upper trapezius",
            "the slope between the neck and the shoulders", "")

ZONES = {
    "Quadriceps": ("quadriceps", "the FRONT of both thighs", ""),
    "Ischio-jambiers": ("hamstrings",
                        "the BACK of both thighs", ""),
    "Fessiers": ("glutes", "the buttocks", ""),
    "Mollets (gastrocnémiens)": ("calves",
                                 "the BACK of both lower legs",
                                 ""),
    "Mollets (soléaire)": ("lower calves",
                           "the BACK of both lower legs, just above "
                           "the ankle", ""),
    "Pectoraux": ("pectorals", "across the chest", ""),
    "Pectoraux (bas)": ("lower pectorals",
                        "the BOTTOM edge of the chest",
                        ""),
    "Pectoraux (haut)": ("upper pectorals",
                         "the TOP of the chest, just below the collarbones",
                         ""),
    "Pectoraux (milieu + intérieur)": ("inner pectorals",
                                       "the INNER chest, along its middle "
                                       "line", ""),
    "Dos (grand dorsal)": ("latissimus dorsi",
                           "the broad fan-shaped muscles on both "
                           "sides of the BACK, below the armpits", ""),
    "Dos (milieu)": ("mid-back",
                     "between the shoulder blades", ""),
    "Dos (érecteurs)": ("erector spinae",
                        "the two columns running along the "
                        "lower spine", ""),
    "Lombaires": ("lower back",
                  "either side of the lumbar spine", ""),
    "Trapèzes (supérieurs)": TRAPEZES,
    "Trapèzes (partie haute)": TRAPEZES,
    "Épaules": DELTOIDES,
    "Épaules (deltoïdes)": DELTOIDES,
    "Épaules (3 faisceaux)": DELTOIDES,
    "Épaules (deltoïdes latéraux)": ("side deltoids",
                                     "the OUTER edge of both "
                                     "shoulders", ""),
    "Épaules (deltoïdes postérieurs)": ("rear deltoids",
                                        "the BACK of both "
                                        "shoulders", ""),
    "Biceps": BICEPS,
    "Biceps (brachial)": BICEPS,
    "Biceps (longue portion)": BICEPS,
    "Triceps": TRICEPS,
    "Triceps (3 chefs)": TRICEPS,
    "Triceps (longue portion)": TRICEPS,
    "Abdominaux": ABDOS,
    "Abdominaux (grand droit)": ABDOS,
    "Abdominaux (partie basse)": ("lower abdominals",
                                  "below the navel", ""),
    "Obliques": ("obliques", "both sides of the waist", ""),
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


GABARIT = ("{style}. The mannequin is performing: {geste}.{instant}{muscle} "
           "Camera angle: {angle}.")

# Utile quand le geste vient de la fiche, qui décrit un mouvement entier ;
# inutile quand le geste est écrit à la main, où la position est déjà fixée
# et où cette phrase ne ferait qu'inviter le modèle à la réinterpréter.
INSTANT = (" Show the single most RECOGNISABLE instant of this movement — the "
           "position that makes it impossible to confuse with any other "
           "exercise, not necessarily the starting position.")

# Le coloriage suit immédiatement le geste, tant que le modèle a la pose en
# tête : place en fin de prompt, trois phrases plus loin, le rouge atterrissait
# sur le torse. Il disparaît entièrement quand il n'y a pas de zone à
# désigner, plutôt que de laisser un « paint the None ».
COLORIAGE = (
    " Paint the {ancre} in a flat soft red-orange overlay — {zone}."
    "{exclusion} The red sits exactly there and does not spill onto the parts "
    "next to it. Everything else stays plain matte grey: exactly one red area "
    "in the whole image, on the {ancre}."
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


def _coloriage(fiche):
    zone = _zone(fiche)
    if not zone:
        return SANS_COLORIAGE
    ancre, description, exclusion = zone
    return COLORIAGE.format(zone=description, exclusion=exclusion, ancre=ancre)


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
                instant="" if nom in GESTES else INSTANT,
                muscle=_coloriage(fiche),
            ),
        })
    return entrees


if __name__ == "__main__":
    entrees = construire()
    io.open(SORTIE, "w", encoding="utf-8", newline="\n").write(
        json.dumps(entrees, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(entrees)} prompts → {SORTIE}")
