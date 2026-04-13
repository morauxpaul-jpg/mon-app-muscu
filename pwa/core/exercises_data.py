"""Fiches info des exercices courants — affichées via le bouton "?" en séance.

Chaque entrée contient :
- name : nom complet de l'exercice
- muscles : liste [principal, secondaire1, ...]
- description : explication du mouvement (3-4 phrases)
- tips : liste de 3 conseils d'exécution
- image : nom du fichier SVG dans /static/img/exercises/

Contient aussi :
- EQUIPMENT_FOR_EXERCISE : matériel requis par exercice
- EXERCISE_SUBSTITUTIONS : remplacement si le matériel manque
"""
import re


EXERCISES_INFO = {
    # ── POITRINE ───────────────────────────────────────────────────────
    "Développé couché": {
        "name": "Développé couché",
        "muscles": ["Pectoraux", "Triceps", "Épaules antérieures"],
        "description": "Allongé sur un banc plat, saisir la barre au-dessus de la poitrine. Descendre la barre de manière contrôlée jusqu'à effleurer le milieu du sternum, puis pousser jusqu'à l'extension des bras. C'est le mouvement de base pour développer la masse des pectoraux.",
        "tips": [
            "Pieds à plat au sol, omoplates serrées contre le banc",
            "Ne fais pas rebondir la barre sur la poitrine",
            "Aligne tes poignets au-dessus de tes coudes en position basse",
        ],
        "image": "bench-press.svg",
    },
    "Développé incliné": {
        "name": "Développé incliné",
        "muscles": ["Pectoraux (haut)", "Épaules antérieures", "Triceps"],
        "description": "Même principe que le développé couché mais sur un banc incliné à 30-45°. L'inclinaison recrute davantage le faisceau claviculaire des pectoraux et les épaules. Descendre la barre vers le haut de la poitrine.",
        "tips": [
            "Ne pas trop incliner le banc (max 45°) pour garder le focus sur les pecs",
            "Trajectoire légèrement oblique, barre vers le haut de la poitrine",
            "Omoplates rétractées comme pour le couché",
        ],
        "image": "bench-press.svg",
    },
    "Pompes": {
        "name": "Pompes",
        "muscles": ["Pectoraux", "Triceps", "Épaules antérieures"],
        "description": "En appui sur les mains (largeur d'épaules) et les pieds, fléchir les bras pour descendre le buste jusqu'à effleurer le sol. Remonter en poussant. Le corps reste gainé comme une planche du début à la fin.",
        "tips": [
            "Corps gainé de la tête aux pieds, pas de dos creux",
            "Descendre jusqu'à frôler le sol, coudes à 45° du corps",
            "Expirer en poussant vers le haut",
        ],
        "image": "pushup.svg",
    },
    "Pompes déclinées (pieds surélevés)": {
        "name": "Pompes déclinées",
        "muscles": ["Pectoraux (haut)", "Épaules", "Triceps"],
        "description": "Variante des pompes classiques avec les pieds surélevés sur un banc ou une chaise. La déclinaison augmente la charge sur le haut des pectoraux et les épaules. Plus les pieds sont hauts, plus les épaules travaillent.",
        "tips": [
            "Commence avec une faible surélévation et augmente progressivement",
            "Garde le corps bien aligné, ne laisse pas le bassin s'affaisser",
            "Mains légèrement plus larges que les épaules",
        ],
        "image": "pushup.svg",
    },
    "Pompes diamant": {
        "name": "Pompes diamant",
        "muscles": ["Triceps", "Pectoraux (intérieur)", "Épaules"],
        "description": "Pompes avec les mains rapprochées, pouces et index formant un losange (diamant). Cette position étroite des mains transfère l'effort principal sur les triceps et l'intérieur des pectoraux.",
        "tips": [
            "Mains collées sous le sternum, pouces et index qui se touchent",
            "Coudes le long du corps en descendant",
            "Si trop difficile, commence sur les genoux",
        ],
        "image": "pushup.svg",
    },
    "Dips": {
        "name": "Dips",
        "muscles": ["Pectoraux (bas)", "Triceps", "Épaules antérieures"],
        "description": "Sur des barres parallèles, se soulever bras tendus puis descendre en fléchissant les coudes. Remonter en poussant. Pencher le buste en avant cible les pecs, rester droit cible les triceps.",
        "tips": [
            "Penche légèrement le buste en avant pour cibler les pectoraux",
            "Descends jusqu'à ce que les bras forment un angle de 90°",
            "Contrôle la descente, ne tombe pas",
        ],
        "image": "dip.svg",
    },

    # ── DOS ────────────────────────────────────────────────────────────
    "Rowing barre": {
        "name": "Rowing barre",
        "muscles": ["Dos (grand dorsal)", "Biceps", "Rhomboïdes"],
        "description": "Debout, penché en avant à environ 45°, tirer la barre vers le nombril en serrant les omoplates. Reposer en contrôlant la descente. Le dos reste plat tout au long du mouvement.",
        "tips": [
            "Serre les omoplates en haut du mouvement",
            "Tire le coude vers l'arrière, pas les mains vers le haut",
            "Garde le dos plat et les genoux légèrement fléchis",
        ],
        "image": "row.svg",
    },
    "Rowing haltère": {
        "name": "Rowing haltère",
        "muscles": ["Dos (grand dorsal)", "Biceps", "Rhomboïdes"],
        "description": "Un genou et une main en appui sur un banc, tirer l'haltère vers la hanche avec le bras libre. Ce mouvement unilatéral corrige les déséquilibres et permet une grande amplitude.",
        "tips": [
            "Dos plat et parallèle au sol",
            "Tire le coude vers le plafond, pas juste la main",
            "Contrôle la descente pour maximiser le travail du dos",
        ],
        "image": "row.svg",
    },
    "Tractions": {
        "name": "Tractions",
        "muscles": ["Dos (grand dorsal)", "Biceps", "Avant-bras"],
        "description": "Suspendu à une barre fixe en prise pronation (paumes vers l'avant), se hisser jusqu'à ce que le menton dépasse la barre. Redescendre lentement. L'exercice roi du dos au poids du corps.",
        "tips": [
            "Initie le mouvement avec les dorsaux, pas les bras",
            "Descente contrôlée, pas de chute libre",
            "Si trop dur, utilise une bande élastique en assistance",
        ],
        "image": "pullup.svg",
    },
    "Tirage vertical": {
        "name": "Tirage vertical (poulie haute)",
        "muscles": ["Dos (grand dorsal)", "Biceps", "Rhomboïdes"],
        "description": "Assis à la poulie haute, tirer la barre vers le haut de la poitrine en rapprochant les omoplates. Alternative en salle aux tractions, avec possibilité de régler la charge précisément.",
        "tips": [
            "Tire avec les coudes, pas les mains — imagine tirer les coudes vers les hanches",
            "Omoplates vers le bas et l'arrière",
            "Ne tire pas derrière la nuque, toujours devant",
        ],
        "image": "pullup.svg",
    },
    "Tirage horizontal poulie": {
        "name": "Tirage horizontal (poulie basse)",
        "muscles": ["Dos (milieu)", "Biceps", "Rhomboïdes"],
        "description": "Assis à la poulie basse, tirer la poignée vers l'abdomen en gardant le buste quasi vertical. Excellent pour l'épaisseur du dos et la posture. Serrer les omoplates en fin de mouvement.",
        "tips": [
            "Ne recule pas le buste en tirant (pas de triche)",
            "Serre bien les omoplates 1 seconde en position contractée",
            "Relâche en contrôlant, laisse les omoplates s'écarter",
        ],
        "image": "row.svg",
    },
    "Tractions australiennes (ou tirage élastique)": {
        "name": "Tractions australiennes",
        "muscles": ["Dos (grand dorsal)", "Biceps", "Rhomboïdes"],
        "description": "Allongé sous une barre basse (ou un TRX), tirer le buste vers la barre en gardant le corps gainé. Exercice de tirage horizontal au poids du corps, excellent pour débuter ou s'entraîner à la maison.",
        "tips": [
            "Corps bien droit de la tête aux talons",
            "Plus tes pieds sont avancés, plus c'est difficile",
            "Serre les omoplates en haut du mouvement",
        ],
        "image": "row.svg",
    },
    "Soulevé de terre": {
        "name": "Soulevé de terre",
        "muscles": ["Dos (érecteurs)", "Fessiers", "Ischio-jambiers", "Trapèzes"],
        "description": "Debout devant une barre au sol, saisir la barre et soulever en poussant dans le sol avec les jambes tout en redressant le dos. Le mouvement combine une poussée des jambes et une extension du dos. C'est l'exercice le plus complet de la musculation.",
        "tips": [
            "Pousse le sol avec les jambes, ne tire pas avec le dos",
            "Garde la barre collée au corps pendant tout le mouvement",
            "Ne jamais arrondir le bas du dos — mieux vaut alléger que tricher",
        ],
        "image": "deadlift.svg",
    },
    "Soulevé de terre roumain": {
        "name": "Soulevé de terre roumain (RDL)",
        "muscles": ["Ischio-jambiers", "Fessiers", "Dos (érecteurs)"],
        "description": "Debout, barre en main, pencher le buste vers l'avant en poussant les fesses en arrière, jambes quasi tendues. Descendre jusqu'à sentir l'étirement des ischio-jambiers, puis remonter en contractant les fessiers.",
        "tips": [
            "Les genoux restent très légèrement fléchis, pas verrouillés",
            "Pousse les fesses en arrière comme pour fermer une porte",
            "Dos plat en permanence, le mouvement vient des hanches",
        ],
        "image": "deadlift.svg",
    },
    "Oiseau": {
        "name": "Oiseau (élévation postérieure)",
        "muscles": ["Épaules (deltoïdes postérieurs)", "Rhomboïdes", "Trapèzes"],
        "description": "Penché en avant à 90°, écarter les bras sur les côtés avec des haltères légers. Le mouvement cible l'arrière des épaules et le haut du dos. Essentiel pour l'équilibre épaules avant/arrière.",
        "tips": [
            "Léger pli au coude, bras quasi tendus",
            "Serre les omoplates en haut du mouvement",
            "Poids légers et contrôle > poids lourds et élan",
        ],
        "image": "lateral-raise.svg",
    },
    "Shrug": {
        "name": "Shrug (haussement d'épaules)",
        "muscles": ["Trapèzes (supérieurs)"],
        "description": "Debout, haltères ou barre en main, hausser les épaules vers les oreilles en contractant les trapèzes. Maintenir 1 seconde en haut, puis redescendre lentement.",
        "tips": [
            "Monte les épaules bien haut vers les oreilles",
            "Ne roule pas les épaules, mouvement vertical uniquement",
            "Tiens la contraction en haut 1-2 secondes",
        ],
        "image": "shrug.svg",
    },
    "Face pull": {
        "name": "Face pull",
        "muscles": ["Épaules (deltoïdes postérieurs)", "Rhomboïdes", "Rotateurs externes"],
        "description": "À la poulie haute avec une corde, tirer vers le visage en écartant les mains. Les coudes restent hauts. Exercice clé pour la santé des épaules et la posture.",
        "tips": [
            "Coudes hauts, au niveau des oreilles",
            "Écarte les mains en fin de mouvement, rotation externe",
            "Poids léger, focus sur la contraction",
        ],
        "image": "face-pull.svg",
    },

    # ── ÉPAULES ────────────────────────────────────────────────────────
    "Développé militaire": {
        "name": "Développé militaire",
        "muscles": ["Épaules (deltoïdes)", "Triceps", "Trapèzes"],
        "description": "Debout ou assis, pousser la barre ou les haltères au-dessus de la tête jusqu'à l'extension complète des bras. Mouvement fondamental pour les épaules. Gainage abdominal obligatoire pour protéger le dos.",
        "tips": [
            "Gainage abdominal serré, ne cambre pas excessivement le dos",
            "La barre part du niveau du menton, pas de derrière la nuque",
            "Expire en poussant, inspire en descendant",
        ],
        "image": "overhead-press.svg",
    },
    "Élévations latérales": {
        "name": "Élévations latérales",
        "muscles": ["Épaules (deltoïdes latéraux)"],
        "description": "Debout, bras le long du corps avec haltères légers, monter les bras sur les côtés jusqu'à hauteur d'épaules. Mouvement d'isolation essentiel pour la largeur des épaules.",
        "tips": [
            "Léger pli au coude fixe pendant tout le mouvement",
            "Ne monte pas plus haut que les épaules",
            "Contrôle la descente, ne laisse pas tomber les bras",
        ],
        "image": "lateral-raise.svg",
    },

    # ── BRAS ───────────────────────────────────────────────────────────
    "Curl biceps": {
        "name": "Curl biceps",
        "muscles": ["Biceps", "Avant-bras"],
        "description": "Debout, bras tendus le long du corps, fléchir les coudes pour amener la charge vers les épaules. Le haut du bras reste immobile, seul l'avant-bras bouge. Mouvement de base pour les biceps.",
        "tips": [
            "Ne balance pas le corps pour tricher — coudes fixes",
            "Contrôle la phase négative (descente) sur 2-3 secondes",
            "Serre les biceps en haut du mouvement",
        ],
        "image": "curl.svg",
    },
    "Curl barre": {
        "name": "Curl barre",
        "muscles": ["Biceps", "Avant-bras"],
        "description": "Même principe que le curl classique mais avec une barre droite ou EZ. La barre permet de charger plus lourd. La barre EZ est plus confortable pour les poignets.",
        "tips": [
            "Coudes collés au corps, ne les laisse pas partir en avant",
            "Si tu triches avec le dos, baisse le poids",
            "Prise à largeur d'épaules pour le maximum d'activation",
        ],
        "image": "curl.svg",
    },
    "Curl marteau": {
        "name": "Curl marteau",
        "muscles": ["Biceps (brachial)", "Avant-bras (brachio-radial)"],
        "description": "Curl avec les haltères en prise neutre (pouces vers le haut). Cette prise travaille davantage le brachial et le brachio-radial, donnant de l'épaisseur au bras vu de côté.",
        "tips": [
            "Pouces vers le haut tout au long du mouvement",
            "Alternance bras gauche / bras droit ou les deux ensemble",
            "Ne balance pas, mouvement strict",
        ],
        "image": "curl.svg",
    },
    "Extensions triceps": {
        "name": "Extensions triceps",
        "muscles": ["Triceps"],
        "description": "Étendre les bras en gardant les coudes fixes, que ce soit à la poulie, avec haltère au-dessus de la tête ou allongé (skullcrusher). L'objectif est d'isoler les trois faisceaux du triceps.",
        "tips": [
            "Coudes fixes — seuls les avant-bras bougent",
            "Extension complète en bas pour bien étirer le muscle",
            "Poids modéré, la technique prime",
        ],
        "image": "extension.svg",
    },
    "Extensions triceps poulie": {
        "name": "Extensions triceps à la poulie",
        "muscles": ["Triceps"],
        "description": "Face à la poulie haute, pousser la barre ou la corde vers le bas en gardant les coudes collés au corps. Extension complète en bas, puis remonter lentement. Idéal pour finir les triceps après les mouvements composés.",
        "tips": [
            "Coudes collés au corps, ne les laisse pas partir",
            "Contracte fort en bas pendant 1 seconde",
            "Remonte lentement, ne laisse pas la poulie tirer tes mains",
        ],
        "image": "extension.svg",
    },

    # ── JAMBES ─────────────────────────────────────────────────────────
    "Squat": {
        "name": "Squat",
        "muscles": ["Quadriceps", "Fessiers", "Ischio-jambiers", "Lombaires"],
        "description": "Barre sur les trapèzes, descendre en fléchissant hanches et genoux simultanément. Descendre au moins jusqu'à la parallèle (cuisses parallèles au sol), puis remonter en poussant dans le sol. Le roi des exercices pour les jambes.",
        "tips": [
            "Genoux dans l'axe des pieds, ne les laisse pas rentrer vers l'intérieur",
            "Dos droit, regard vers l'avant, pas vers le sol",
            "Descends au moins jusqu'à la parallèle pour un travail complet",
        ],
        "image": "squat.svg",
    },
    "Presse à cuisses": {
        "name": "Presse à cuisses (Leg press)",
        "muscles": ["Quadriceps", "Fessiers", "Ischio-jambiers"],
        "description": "Assis sur la machine, pieds sur la plateforme à largeur d'épaules, pousser pour étendre les jambes puis revenir en fléchissant. Permet de charger lourd avec moins de stress sur le dos qu'un squat.",
        "tips": [
            "Ne verrouille jamais les genoux en extension complète",
            "Pieds à largeur d'épaules, descente jusqu'à 90° de flexion",
            "Garde le bas du dos bien plaqué contre le dossier",
        ],
        "image": "leg-machine.svg",
    },
    "Leg curl": {
        "name": "Leg curl",
        "muscles": ["Ischio-jambiers"],
        "description": "Allongé sur la machine face au sol, fléchir les genoux pour amener les talons vers les fessiers. Mouvement d'isolation pour l'arrière des cuisses, complémentaire du leg extension.",
        "tips": [
            "Mouvement contrôlé, pas d'élan ni de mouvement brusque",
            "Contracte bien les ischio-jambiers en haut 1 seconde",
            "Ne soulève pas les hanches du coussin",
        ],
        "image": "leg-machine.svg",
    },
    "Leg extension": {
        "name": "Leg extension",
        "muscles": ["Quadriceps"],
        "description": "Assis sur la machine, étendre les genoux pour soulever le coussin avec les tibias. Mouvement d'isolation pur pour les quadriceps, excellent en échauffement ou en finition.",
        "tips": [
            "Ne verrouille pas complètement en extension, garde une micro-flexion",
            "Contrôle la descente sur 2-3 secondes",
            "Poids modéré, focus sur la contraction du quad",
        ],
        "image": "leg-machine.svg",
    },
    "Fentes": {
        "name": "Fentes",
        "muscles": ["Quadriceps", "Fessiers", "Ischio-jambiers"],
        "description": "Faire un grand pas en avant et descendre le genou arrière vers le sol. Le genou avant reste au-dessus de la cheville. Remonter en poussant avec la jambe avant. Excellent pour l'équilibre et le travail unilatéral.",
        "tips": [
            "Genou avant au-dessus de la cheville, pas devant les orteils",
            "Dos droit, regard devant",
            "Descends jusqu'à ce que le genou arrière frôle le sol",
        ],
        "image": "lunge.svg",
    },
    "Fentes alternées": {
        "name": "Fentes alternées",
        "muscles": ["Quadriceps", "Fessiers", "Ischio-jambiers"],
        "description": "Version dynamique des fentes : alterner jambe gauche et jambe droite à chaque répétition. Depuis la position debout, faire un pas en avant, descendre, remonter, puis changer de jambe.",
        "tips": [
            "Grand pas en avant pour que le genou ne dépasse pas les orteils",
            "Garde le buste droit et le regard devant",
            "Rythme régulier, ne précipite pas le mouvement",
        ],
        "image": "lunge.svg",
    },
    "Fentes sautées": {
        "name": "Fentes sautées",
        "muscles": ["Quadriceps", "Fessiers", "Mollets"],
        "description": "Version explosive des fentes : depuis la position basse, sauter pour changer de jambe en l'air. Exercice pliométrique intense qui développe la puissance et l'endurance musculaire.",
        "tips": [
            "Atterris en douceur, amortis avec les jambes",
            "Commence par des fentes classiques si tu débutes",
            "Garde le buste droit même pendant le saut",
        ],
        "image": "lunge.svg",
    },
    "Squat bulgare": {
        "name": "Squat bulgare",
        "muscles": ["Quadriceps", "Fessiers", "Ischio-jambiers"],
        "description": "Fente avec le pied arrière surélevé sur un banc. Descendre en fléchissant le genou avant jusqu'à la parallèle. Cette surélévation augmente l'amplitude et l'intensité par rapport aux fentes classiques.",
        "tips": [
            "Le pied avant suffisamment loin du banc pour que le genou reste au-dessus de la cheville",
            "Buste légèrement incliné vers l'avant pour cibler les fessiers",
            "Descends jusqu'à ce que la cuisse avant soit parallèle au sol",
        ],
        "image": "lunge.svg",
    },
    "Hip thrust": {
        "name": "Hip thrust",
        "muscles": ["Fessiers", "Ischio-jambiers"],
        "description": "Dos appuyé sur un banc, barre sur les hanches, pousser les hanches vers le plafond en contractant fort les fessiers. Le meilleur exercice d'isolation pour les fessiers selon les études EMG.",
        "tips": [
            "Serre fort les fessiers en haut pendant 1-2 secondes",
            "Ne cambre pas le bas du dos, le mouvement vient des hanches",
            "Regarde vers l'avant (menton vers la poitrine), pas le plafond",
        ],
        "image": "hip-thrust.svg",
    },
    "Hip thrust (sol)": {
        "name": "Hip thrust au sol (Glute bridge)",
        "muscles": ["Fessiers", "Ischio-jambiers"],
        "description": "Allongé au sol, pieds à plat, pousser les hanches vers le plafond en serrant les fessiers. Version sans banc du hip thrust, idéale pour s'entraîner à la maison. On peut ajouter un haltère sur les hanches.",
        "tips": [
            "Pieds proches des fessiers, écartés largeur de hanches",
            "Contracte les fessiers en haut, ne pousse pas avec le dos",
            "Pour plus de difficulté, fais-le sur une jambe",
        ],
        "image": "hip-thrust.svg",
    },
    "Mollets debout": {
        "name": "Mollets debout",
        "muscles": ["Mollets (gastrocnémiens)"],
        "description": "Debout, monter sur la pointe des pieds contre une résistance (machine, marche avec haltères). Amplitude complète : étirer en bas, contracter en haut. Les mollets répondent bien aux séries longues.",
        "tips": [
            "Amplitude maximale : descends bien le talon en bas, monte sur la pointe",
            "Tiens la contraction en haut 1-2 secondes",
            "Séries longues (12-20 reps) plus efficaces pour les mollets",
        ],
        "image": "calf-raise.svg",
    },
    "Mollets assis": {
        "name": "Mollets assis",
        "muscles": ["Mollets (soléaire)"],
        "description": "Assis sur la machine à mollets, résistance sur les genoux, monter sur la pointe des pieds. Position assise cible le soléaire (couche profonde du mollet). Complément au mollet debout.",
        "tips": [
            "Amplitude complète comme pour les mollets debout",
            "Plus lent et contrôlé que debout",
            "Complémentaire aux mollets debout pour un développement complet",
        ],
        "image": "calf-raise.svg",
    },

    # ── ABDOMINAUX ─────────────────────────────────────────────────────
    "Crunch": {
        "name": "Crunch",
        "muscles": ["Abdominaux (grand droit)"],
        "description": "Allongé au sol, genoux fléchis, enrouler le buste pour rapprocher les côtes du bassin. Seules les épaules et le haut du dos décollent du sol. Mouvement court mais efficace pour le grand droit.",
        "tips": [
            "Ne tire pas sur la nuque avec les mains",
            "Expire en montant, contracte fort les abdos",
            "Mouvement court et contrôlé, pas besoin de monter haut",
        ],
        "image": "core.svg",
    },
    "Gainage": {
        "name": "Gainage (Planche)",
        "muscles": ["Abdominaux", "Transverse", "Lombaires"],
        "description": "En appui sur les avant-bras et les pieds, maintenir le corps parfaitement aligné. Exercice isométrique de base pour renforcer toute la ceinture abdominale et améliorer la stabilité du tronc.",
        "tips": [
            "Serre les abdos et les fessiers, corps comme une planche",
            "Ne creuse pas le dos et ne lève pas les fesses",
            "Respire normalement, ne bloque pas la respiration",
        ],
        "image": "core.svg",
    },
    "Planche": {
        "name": "Planche (Gainage)",
        "muscles": ["Abdominaux", "Transverse", "Lombaires"],
        "description": "En appui sur les avant-bras et les pieds, maintenir le corps parfaitement aligné. Exercice isométrique fondamental pour la stabilité du tronc. Progresser en augmentant la durée.",
        "tips": [
            "Corps aligné de la tête aux talons",
            "Serre les abdos et les fessiers simultanément",
            "Si trop facile, essaie sur une main ou en levant un pied",
        ],
        "image": "core.svg",
    },
    "Relevé de jambes": {
        "name": "Relevé de jambes",
        "muscles": ["Abdominaux (partie basse)", "Fléchisseurs de hanches"],
        "description": "Allongé au sol ou suspendu à une barre, lever les jambes tendues vers le plafond. Cet exercice cible la partie inférieure des abdominaux et les fléchisseurs de hanches.",
        "tips": [
            "Jambes aussi tendues que possible pendant la montée",
            "Contrôle la descente, ne laisse pas les jambes tomber",
            "Si trop difficile, fléchis les genoux",
        ],
        "image": "core.svg",
    },
    "Mountain climbers": {
        "name": "Mountain climbers",
        "muscles": ["Abdominaux", "Épaules", "Quadriceps"],
        "description": "En position de pompe, ramener alternativement les genoux vers la poitrine rapidement. Exercice cardio et gainage dynamique qui fait monter le rythme cardiaque tout en travaillant les abdominaux.",
        "tips": [
            "Garde les hanches basses, au niveau des épaules",
            "Rythme soutenu pour l'effet cardio",
            "Mains sous les épaules, bras bien tendus",
        ],
        "image": "core.svg",
    },

    # ── EXERCICES MAISON SPÉCIFIQUES ───────────────────────────────────
    "Squat (poids du corps ou lesté)": {
        "name": "Squat au poids du corps",
        "muscles": ["Quadriceps", "Fessiers", "Ischio-jambiers"],
        "description": "Squat sans barre : descendre en fléchissant hanches et genoux, bras devant pour l'équilibre. On peut tenir un haltère ou un sac lesté contre la poitrine (goblet squat) pour augmenter la difficulté.",
        "tips": [
            "Même technique que le squat barre : dos droit, genoux dans l'axe",
            "Bras devant ou tenant un poids contre la poitrine",
            "Descends au moins à la parallèle",
        ],
        "image": "squat.svg",
    },
    "Rowing haltère (ou élastique)": {
        "name": "Rowing haltère ou élastique",
        "muscles": ["Dos (grand dorsal)", "Biceps", "Rhomboïdes"],
        "description": "Penché en avant, tirer un haltère ou un élastique vers la hanche. Même mouvement que le rowing haltère classique, adaptable avec un élastique fixé sous le pied pour s'entraîner à la maison.",
        "tips": [
            "Dos plat, genoux légèrement fléchis",
            "Tire le coude vers le plafond",
            "Avec élastique : fixe-le sous le pied, même trajectoire",
        ],
        "image": "row.svg",
    },
    "Curl haltères (ou élastique)": {
        "name": "Curl haltères ou élastique",
        "muscles": ["Biceps", "Avant-bras"],
        "description": "Curl classique avec haltères ou un élastique passé sous les pieds. L'élastique offre une résistance progressive : plus tu montes, plus c'est dur, ce qui est idéal pour la contraction de pic.",
        "tips": [
            "Coudes collés au corps tout le mouvement",
            "Contrôle la descente sur 2-3 secondes",
            "Avec élastique : prends-le plus court pour plus de résistance",
        ],
        "image": "curl.svg",
    },
    "Élévations latérales haltères": {
        "name": "Élévations latérales haltères",
        "muscles": ["Épaules (deltoïdes latéraux)"],
        "description": "Identique aux élévations latérales classiques, réalisées avec des haltères légers. Debout, monter les bras tendus sur les côtés jusqu'à hauteur d'épaules. Peut aussi se faire avec des bouteilles d'eau.",
        "tips": [
            "Poids légers : ce n'est pas un exercice de force",
            "Légère flexion du coude maintenue tout au long",
            "Monte les bras comme si tu versais une bouteille d'eau",
        ],
        "image": "lateral-raise.svg",
    },
    "Fentes haltères": {
        "name": "Fentes avec haltères",
        "muscles": ["Quadriceps", "Fessiers", "Ischio-jambiers"],
        "description": "Fentes classiques avec un haltère dans chaque main. Le poids additionnel augmente l'intensité et travaille aussi la prise (avant-bras). Alterner les jambes ou avancer en marchant.",
        "tips": [
            "Haltères le long du corps, pas sur les épaules",
            "Même technique que les fentes classiques",
            "Pas plus large pour un meilleur équilibre",
        ],
        "image": "lunge.svg",
    },

    # ── EXERCICES AVEC NOMS COMPOSÉS (CATALOGUE) ──────────────────────
    "Développé incliné haltères": {
        "name": "Développé incliné haltères",
        "muscles": ["Pectoraux (haut)", "Épaules antérieures", "Triceps"],
        "description": "Développé incliné réalisé avec des haltères au lieu d'une barre. L'amplitude est plus grande et chaque bras travaille indépendamment, corrigeant les déséquilibres. Descente profonde, les haltères encadrent la poitrine.",
        "tips": [
            "Inclinaison du banc à 30-45°",
            "Descends les haltères au niveau des pectoraux, pas au-dessus",
            "Contrôle la descente, ne laisse pas les haltères tomber",
        ],
        "image": "bench-press.svg",
    },
    "Tractions (ou tirage vertical)": {
        "name": "Tractions / Tirage vertical",
        "muscles": ["Dos (grand dorsal)", "Biceps", "Avant-bras"],
        "description": "Tractions à la barre fixe ou tirage vertical à la poulie haute selon l'équipement. Le mouvement de traction verticale est essentiel pour développer la largeur du dos. Si les tractions sont trop difficiles, le tirage à la poulie permet de régler la charge.",
        "tips": [
            "Initie le mouvement avec les dorsaux, pas les bras",
            "Prise légèrement plus large que les épaules",
            "Si tu n'arrives pas à faire de tractions, utilise des élastiques en assistance",
        ],
        "image": "pullup.svg",
    },
    "Dips (ou pompes lestées)": {
        "name": "Dips / Pompes lestées",
        "muscles": ["Pectoraux (bas)", "Triceps", "Épaules antérieures"],
        "description": "Dips sur barres parallèles ou pompes avec un sac lesté si pas de barres. Les dips sont un mouvement composé puissant pour le haut du corps. Alternative aux développés couchés très efficace.",
        "tips": [
            "Penche le buste en avant pour cibler les pecs",
            "Descends jusqu'à un angle de 90° aux coudes",
            "Si pas de barres, fais des pompes avec un sac à dos lesté",
        ],
        "image": "dip.svg",
    },
}


# ── Matériel requis par exercice ───────────────────────────────────────
# Utilisé par catalog.build_program() pour substituer les exercices
# quand l'utilisateur n'a pas le matériel.
# Clés possibles : barre, halteres, banc_plat, banc_inclinable,
#   barre_traction, elastiques, kettlebell, trx, machine
EQUIPMENT_FOR_EXERCISE = {
    "Développé couché":           ["banc_plat"],
    "Développé incliné haltères": ["banc_inclinable", "halteres"],
    "Développé militaire":        ["barre"],
    "Squat":                      ["barre"],
    "Soulevé de terre":           ["barre"],
    "Soulevé de terre roumain":   ["barre"],
    "Rowing barre":               ["barre"],
    "Tractions":                  ["barre_traction"],
    "Tractions (ou tirage vertical)": ["barre_traction"],
    "Tirage vertical":            ["machine"],
    "Tirage horizontal poulie":   ["machine"],
    "Extensions triceps poulie":  ["machine"],
    "Presse à cuisses":           ["machine"],
    "Leg curl":                   ["machine"],
    "Leg extension":              ["machine"],
    "Curl barre":                 ["barre"],
    "Hip thrust":                 ["banc_plat"],
    "Face pull":                  ["elastiques"],
    "Dips":                       ["barre_traction"],
    "Dips (ou pompes lestées)":   ["barre_traction"],
    "Mollets debout":             ["machine"],
    "Mollets assis":              ["machine"],
    "Fentes haltères":            ["halteres"],
    "Curl marteau":               ["halteres"],
    "Élévations latérales":       ["halteres"],
    "Rowing haltère":             ["halteres"],
    "Développé incliné":          ["banc_inclinable"],
    "Shrug":                      ["halteres"],
}

# Substitutions : exercice → remplacement quand le matériel manque.
# Le remplacement doit fonctionner avec un minimum d'équipement.
EXERCISE_SUBSTITUTIONS = {
    "Développé couché":           "Pompes",
    "Développé incliné haltères": "Pompes déclinées (pieds surélevés)",
    "Développé incliné":          "Pompes déclinées (pieds surélevés)",
    "Développé militaire":        "Pompes déclinées (pieds surélevés)",
    "Squat":                      "Squat (poids du corps ou lesté)",
    "Soulevé de terre":           "Hip thrust (sol)",
    "Soulevé de terre roumain":   "Hip thrust (sol)",
    "Rowing barre":               "Rowing haltère (ou élastique)",
    "Tractions":                  "Tractions australiennes (ou tirage élastique)",
    "Tractions (ou tirage vertical)": "Tractions australiennes (ou tirage élastique)",
    "Tirage vertical":            "Tractions australiennes (ou tirage élastique)",
    "Tirage horizontal poulie":   "Rowing haltère (ou élastique)",
    "Extensions triceps poulie":  "Pompes diamant",
    "Presse à cuisses":           "Squat bulgare",
    "Leg curl":                   "Hip thrust (sol)",
    "Leg extension":              "Fentes alternées",
    "Curl barre":                 "Curl haltères (ou élastique)",
    "Hip thrust":                 "Hip thrust (sol)",
    "Face pull":                  "Oiseau",
    "Dips":                       "Pompes",
    "Dips (ou pompes lestées)":   "Pompes",
    "Mollets debout":             "Mollets debout",  # can do bodyweight
    "Mollets assis":              "Mollets debout",
}


# ── Lookup avec correspondance floue ───────────────────────────────────

def get_exercise_info(name):
    """Retourne la fiche d'un exercice. Essaie une correspondance exacte,
    puis supprime les parenthèses et suffixes d'équipement pour trouver
    une fiche de base. Retourne None si rien ne correspond."""
    if not name:
        return None
    # 1. Exact match
    if name in EXERCISES_INFO:
        return EXERCISES_INFO[name]
    # 2. Strip parenthetical notes: "Tractions (ou tirage vertical)" → "Tractions"
    clean = re.sub(r"\s*\(.*?\)", "", name).strip()
    if clean in EXERCISES_INFO:
        return EXERCISES_INFO[clean]
    # 3. Strip equipment suffixes
    for suffix in ("haltères", "haltère", "barre", "poulie", "machine",
                    "élastique", "élastiques", "sol"):
        if clean.endswith(" " + suffix):
            base = clean[: -(len(suffix) + 1)].strip()
            if base in EXERCISES_INFO:
                return EXERCISES_INFO[base]
    # 4. Longest matching prefix
    name_lower = name.lower()
    best_key = None
    best_len = 0
    for key in EXERCISES_INFO:
        if name_lower.startswith(key.lower()) and len(key) > best_len:
            best_key = key
            best_len = len(key)
    if best_key:
        return EXERCISES_INFO[best_key]
    return None


def get_all_exercises_info():
    """Retourne tout le dictionnaire pour le template."""
    return EXERCISES_INFO


def check_equipment(exercise_name, user_equipment):
    """Vérifie si l'utilisateur a le matériel requis pour un exercice.
    Retourne True si oui ou si l'exercice n'a pas de prérequis connu."""
    required = EQUIPMENT_FOR_EXERCISE.get(exercise_name)
    if not required:
        return True
    return all(eq in user_equipment for eq in required)


def get_substitution(exercise_name):
    """Retourne le nom de l'exercice de substitution, ou None."""
    return EXERCISE_SUBSTITUTIONS.get(exercise_name)
