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
# Une absence ne se dessine pas : « there is NO barbell », seul, a produit
# une barre trois fois de suite — le modèle n'avait que le mot « barbell »
# sous les yeux. Une négation ne vient qu'APRÈS avoir dit ce qu'il faut
# dessiner, jamais à sa place.
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
    "Curl biceps": "standing, both hands gripping ONE long straight barbell, "
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
    "Élévations latérales": "standing, arms raised straight out "
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
    "Soulevé de terre roumain": "standing, knees almost straight, HINGED "
                                "FORWARD at the hips so the torso is close "
                                "to horizontal, back flat, the barbell "
                                "sliding down the front of the legs to "
                                "mid-shin. The torso is NOT upright",
    "Développé haltères": "lying FACE UP on a flat bench, one dumbbell in "
                            "each hand pressed straight up above the chest, "
                            "arms extended. The mannequin is NOT face down",
    "Oiseau": "standing but BENT FORWARD at the hips to about 45 degrees, "
              "back flat, arms hanging then opened out sideways like wings, "
              "a light dumbbell in each hand. The torso is NOT upright",
    "Squat bulgare": "in a split stance with the REAR foot resting on top of "
                     "a bench behind, front knee bent deep, torso upright. "
                     "The mannequin is NOT sitting on the bench",
    "Dips sur chaise": "back to a chair, both hands gripping the front edge "
                       "of the seat behind them, hips OFF the seat and "
                       "lowered towards the floor, legs out in front, elbows "
                       "bent. The mannequin is NOT sitting on the chair",
    "Leg curl": "lying FACE DOWN on a leg curl machine, knees BENT so the "
                "heels are pulled up towards the buttocks against the roller "
                "pad. The legs are NOT straight",
    "Curl haltères (ou élastique)": "standing, holding TWO SEPARATE "
                                    "SHORT DUMBBELLS, one in each hand, with a "
                                    "clear empty gap between the two hands — "
                                    "nothing connects them. Palms facing up, "
                                    "elbows pinned to the sides, both forearms "
                                    "curled up to chest height",
    "Dips sur chaise": "facing away from a chair, both hands behind them "
                       "gripping the front edge of the seat, ARMS SUPPORTING "
                       "THE WHOLE BODY, hips hanging in the air in FRONT of "
                       "the chair and lowered towards the floor, legs "
                       "stretched out. The buttocks do not touch the chair "
                       "and the mannequin is NOT seated",
    "Squat bulgare": "in a deep split stance, the REAR foot resting on top of "
                     "a bench BEHIND the mannequin with the toes pointing "
                     "down, front foot flat on the floor well in front of "
                     "the bench, front knee bent to 90 degrees, torso "
                     "upright. The buttocks are in the air, well away from "
                     "the bench, and the mannequin is NOT seated",
    "Tractions australiennes": "lying FACE UP under a low horizontal bar, "
                               "body straight and rigid from heels to head, "
                               "heels on the floor, both hands gripping the "
                               "bar above the chest, pulling the chest up to "
                               "it. Show it from a low side angle so the "
                               "back and shoulder blades are visible",
    "Tractions australiennes (ou tirage élastique)": "lying FACE UP under a "
                               "low horizontal bar, body straight and rigid "
                               "from heels to head, both hands gripping the "
                               "bar above the chest, pulling the chest up to "
                               "it. Show it from a low side angle so the "
                               "back and shoulder blades are visible",
    # ── Machines guidees ──────────────────────────────────────────
    # Une machine ne se devine pas : sans description du bati, le modele
    # dessine un banc quelconque et des poids qui flottent.
    "Leg curl assis": "SITTING DOWN on a seated leg curl machine, back "
                      "against the backrest, a thick pad clamped across the "
                      "TOPS of both thighs, ankles hooked under a roller pad. "
                      "Show the END of the movement: the knees are FULLY "
                      "BENT, both lower legs folded back and tucked under "
                      "the seat, so the BACK of each thigh faces the camera. "
                      "Strict side view. The mannequin is NOT lying down and "
                      "the legs are NOT straight out in front",
    "Élévations frontales": "standing, holding TWO SEPARATE SHORT "
                            "DUMBBELLS, one in each hand, with a clear empty "
                            "gap between the two hands — nothing connects "
                            "them. Both arms are COMPLETELY STRAIGHT at the "
                            "elbow, raised FORWARD in front of the chest up "
                            "to shoulder height, palms facing down. The "
                            "elbows are not bent at all",
    "Machine adducteurs": "SEATED on an adductor machine: upright back "
                          "against a padded backrest, both knees SPREAD "
                          "APART with the inner side of each thigh pressed "
                          "against a vertical padded lever, squeezing the "
                          "thighs back together. The weight stack is visible "
                          "behind the seat",
    # Premier essai : debout À CÔTÉ de la machine. « Seated » ne suffit pas,
    # il faut dire où sont les fesses et ce que fait le dos.
    "Machine abducteurs": "SITTING DOWN on an abductor machine, buttocks on "
                          "the seat pad and back leaning against the "
                          "backrest, both feet off the floor on the machine's "
                          "footrests, knees bent, thighs SPREAD WIDE APART "
                          "pushing outwards against a padded lever on the "
                          "outer side of each thigh. The mannequin is NOT "
                          "standing and NOT beside the machine",
    # Premier essai : deux haltères sur une barre droite, donc un développé.
    # Il faut décrire ce que les mains TIENNENT, et que ça sort du bâti.
    "Écarté machine": "SITTING DOWN on a pec deck machine, back against the "
                     "backrest, each hand gripping the end of a long PADDED "
                     "ARM that is bolted to the machine frame behind the "
                     "shoulders; the two arms swing horizontally and are "
                     "closing together in front of the chest, elbows slightly "
                     "bent. There is NO dumbbell and NO barbell — nothing is "
                     "held loose, everything is attached to the machine",
    "Pompes diamant": "in a push-up position, the two hands placed close "
                      "together directly under the chest so the thumbs and "
                      "index fingers form a diamond, elbows tucked in "
                      "close to the ribs",
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
    "Pectoraux (bas)": ("lower chest",
                        "the lower half of the pectoral muscles, still ON "
                        "the chest, above the ribs",
                        " Do not paint the stomach, the waist or the hips."),
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
    "Épaules (deltoïdes antérieurs)": ("front deltoids",
                                      "the FRONT of both shoulders, just "
                                      "below the collarbone", ""),
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
    "Adducteurs": ("inner thighs",
                   "the INNER side of both thighs, between the groin and "
                   "the knee", ""),
    "Fessiers (moyen fessier)": ("outer glutes",
                                 "the OUTER side of the hips, just below the "
                                 "waist", ""),
    # Un corps entier tout rouge ne désigne rien : pas de coloriage.
    "Corps entier": None,
}


# Exercices dont la cible est physiquement cachée par la pose : à plat
# ventre, les abdos regardent le sol, et aucun angle ne montre à la fois le
# gainage et sa ceinture abdominale. Deux générations de suite ont mis le
# rouge sur les LOMBAIRES — l'opposé exact du muscle travaillé. Une
# anatomie fausse affichée pendant la série est pire que pas de rouge du
# tout ; la pose, elle, se reconnaît seule.
SANS_ROUGE = {
    "Gainage",
    "Planche",
    "Mountain climbers",
}


def _zone(fiche, nom=None):
    """Le muscle à peindre en rouge, décrit pour un modèle d'image.

    Renvoie None quand il n'y a rien à désigner — mieux vaut pas de rouge
    du tout qu'un rouge au mauvais endroit, qui apprend une anatomie fausse.
    """
    if nom in SANS_ROUGE:
        return None
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
# La camera doit VOIR le muscle. Sans cette consigne, le modèle peignait la
# face qu'il avait sous les yeux : sur une planche (abdos vers le sol) le
# rouge partait sur les lombaires, sur un hip thrust (fessiers dessous) sur
# l'avant de la cuisse, sur un soulevé de terre (érecteurs derrière) sur le
# flanc. Trois fois la même erreur, jamais la même formulation en cause.
CAMERA = (" Choose the viewing angle so that the {ancre} faces the viewer and "
          "is fully visible — if the pose would hide it, turn the camera or "
          "the body until it shows.")

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


def _coloriage(fiche, nom=None):
    zone = _zone(fiche, nom)
    if not zone:
        return SANS_COLORIAGE
    ancre, description, exclusion = zone
    return (COLORIAGE.format(zone=description, exclusion=exclusion, ancre=ancre)
            + CAMERA.format(ancre=ancre))


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
                muscle=_coloriage(fiche, nom),
            ),
        })
    return entrees


if __name__ == "__main__":
    entrees = construire()
    io.open(SORTIE, "w", encoding="utf-8", newline="\n").write(
        json.dumps(entrees, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(entrees)} prompts → {SORTIE}")
