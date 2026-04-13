"""Fiches info des exercices courants — affichées via le bouton "?" en séance."""

EXERCISES_INFO = {
    "Développé couché": {
        "muscles": "Pectoraux, Triceps, Épaules antérieures",
        "description": "Allongé sur un banc, descendre la barre vers le milieu de la poitrine puis pousser.",
        "tips": "Pieds au sol, omoplates serrées, ne pas rebondir sur la poitrine.",
    },
    "Développé incliné": {
        "muscles": "Pectoraux (haut), Épaules antérieures, Triceps",
        "description": "Même mouvement que le développé couché mais sur un banc incliné à 30-45°.",
        "tips": "Ne pas trop incliner le banc pour garder le focus sur les pecs.",
    },
    "Développé militaire": {
        "muscles": "Épaules (deltoïdes antérieurs et latéraux), Triceps",
        "description": "Debout ou assis, pousser la barre ou les haltères au-dessus de la tête.",
        "tips": "Gainage abdominal serré, ne pas cambrer excessivement le dos.",
    },
    "Squat": {
        "muscles": "Quadriceps, Fessiers, Ischio-jambiers, Lombaires",
        "description": "Barre sur les trapèzes, descendre en fléchissant hanches et genoux jusqu'à la parallèle.",
        "tips": "Genoux dans l'axe des pieds, dos droit, descendre au moins à la parallèle.",
    },
    "Soulevé de terre": {
        "muscles": "Dos (érecteurs), Fessiers, Ischio-jambiers, Trapèzes",
        "description": "Soulever la barre du sol jusqu'à la position debout, dos droit.",
        "tips": "Pousser le sol avec les jambes, garder la barre proche du corps, ne pas arrondir le dos.",
    },
    "Rowing barre": {
        "muscles": "Dos (grand dorsal), Biceps, Rhomboïdes",
        "description": "Penché en avant, tirer la barre vers le nombril.",
        "tips": "Serrer les omoplates en haut du mouvement, contrôler la descente.",
    },
    "Tractions": {
        "muscles": "Dos (grand dorsal), Biceps, Avant-bras",
        "description": "Suspendu à une barre, se hisser jusqu'à ce que le menton dépasse la barre.",
        "tips": "Initier le mouvement avec les dorsaux, pas les bras. Descente contrôlée.",
    },
    "Dips": {
        "muscles": "Pectoraux (bas), Triceps, Épaules antérieures",
        "description": "Sur des barres parallèles, descendre en fléchissant les coudes puis remonter.",
        "tips": "Pencher légèrement le buste en avant pour cibler les pecs.",
    },
    "Curl biceps": {
        "muscles": "Biceps, Avant-bras",
        "description": "Fléchir les coudes pour amener la charge vers les épaules.",
        "tips": "Ne pas balancer le corps, contrôler la phase négative.",
    },
    "Extensions triceps": {
        "muscles": "Triceps",
        "description": "Étendre les bras en gardant les coudes fixes.",
        "tips": "Coudes collés au corps (ou au-dessus de la tête selon la variante).",
    },
    "Élévations latérales": {
        "muscles": "Épaules (deltoïdes latéraux)",
        "description": "Bras le long du corps, monter les haltères sur les côtés à hauteur d'épaules.",
        "tips": "Léger pli au coude, ne pas monter plus haut que les épaules, contrôler la descente.",
    },
    "Leg press": {
        "muscles": "Quadriceps, Fessiers, Ischio-jambiers",
        "description": "Pousser la plateforme avec les pieds en fléchissant les genoux.",
        "tips": "Ne pas verrouiller les genoux en extension, pieds largeur d'épaules.",
    },
    "Leg curl": {
        "muscles": "Ischio-jambiers",
        "description": "Fléchir les genoux contre une résistance pour travailler l'arrière des cuisses.",
        "tips": "Mouvement contrôlé, ne pas utiliser l'élan.",
    },
    "Leg extension": {
        "muscles": "Quadriceps",
        "description": "Étendre les genoux contre une résistance.",
        "tips": "Ne pas verrouiller complètement en extension, contrôler la descente.",
    },
    "Hip thrust": {
        "muscles": "Fessiers, Ischio-jambiers",
        "description": "Dos appuyé sur un banc, pousser les hanches vers le haut avec une barre.",
        "tips": "Serrer les fessiers en haut, ne pas hyper-étendre le dos.",
    },
    "Mollets debout": {
        "muscles": "Mollets (gastrocnémiens)",
        "description": "Monter sur la pointe des pieds contre une résistance.",
        "tips": "Amplitude complète : étirer en bas, contracter en haut.",
    },
    "Crunch": {
        "muscles": "Abdominaux (grand droit)",
        "description": "Allongé, enrouler le buste pour rapprocher les côtes du bassin.",
        "tips": "Ne pas tirer sur la nuque, expirer en montant.",
    },
    "Planche": {
        "muscles": "Abdominaux, Transverse, Lombaires",
        "description": "En appui sur les avant-bras et les pieds, maintenir le corps aligné.",
        "tips": "Serrer les abdos et les fessiers, ne pas creuser le dos.",
    },
    "Pompes": {
        "muscles": "Pectoraux, Triceps, Épaules antérieures",
        "description": "En appui sur les mains et les pieds, fléchir les bras pour descendre le buste.",
        "tips": "Corps gainé, descendre jusqu'à frôler le sol, coudes à 45°.",
    },
    "Tirage vertical": {
        "muscles": "Dos (grand dorsal), Biceps",
        "description": "Tirer la barre vers la poitrine en position assise à la poulie haute.",
        "tips": "Tirer avec les coudes, pas les mains. Omoplates vers le bas et l'arrière.",
    },
    "Rowing haltère": {
        "muscles": "Dos (grand dorsal), Biceps, Rhomboïdes",
        "description": "Un genou et une main sur un banc, tirer l'haltère vers la hanche.",
        "tips": "Dos plat, tirer le coude vers le plafond.",
    },
    "Oiseau": {
        "muscles": "Épaules (deltoïdes postérieurs), Rhomboïdes",
        "description": "Penché en avant, écarter les bras sur les côtés.",
        "tips": "Léger pli au coude, serrer les omoplates en haut du mouvement.",
    },
    "Fentes": {
        "muscles": "Quadriceps, Fessiers, Ischio-jambiers",
        "description": "Faire un grand pas en avant et descendre le genou arrière vers le sol.",
        "tips": "Genou avant au-dessus de la cheville, dos droit.",
    },
    "Shrug": {
        "muscles": "Trapèzes",
        "description": "Hausser les épaules en tenant des haltères ou une barre.",
        "tips": "Monter les épaules vers les oreilles, sans rouler.",
    },
}


def get_exercise_info(name):
    """Retourne la fiche d'un exercice ou None."""
    return EXERCISES_INFO.get(name)


def get_all_exercises_info():
    """Retourne tout le dictionnaire pour le template."""
    return EXERCISES_INFO
