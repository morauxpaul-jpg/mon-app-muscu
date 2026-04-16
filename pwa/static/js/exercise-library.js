/**
 * Bibliothèque d'exercices prédéfinis par groupe musculaire.
 * Utilisée par la modale "Choisir un exercice" dans seance_edit et programme.
 */
var EXERCISE_LIBRARY = {
  "Poitrine": [
    { name: "Développé couché barre", muscles: ["Triceps", "Épaules"], defaultSets: 4, defaultReps: "8-10" },
    { name: "Développé couché haltères", muscles: ["Triceps", "Épaules"], defaultSets: 4, defaultReps: "8-12" },
    { name: "Développé incliné barre", muscles: ["Épaules", "Triceps"], defaultSets: 4, defaultReps: "8-10" },
    { name: "Développé incliné haltères", muscles: ["Épaules", "Triceps"], defaultSets: 4, defaultReps: "10-12" },
    { name: "Développé décliné barre", muscles: ["Triceps"], defaultSets: 3, defaultReps: "8-10" },
    { name: "Écarté couché haltères", muscles: ["Épaules"], defaultSets: 3, defaultReps: "12-15" },
    { name: "Écarté poulie vis-à-vis", muscles: ["Épaules"], defaultSets: 3, defaultReps: "12-15" },
    { name: "Pompes", muscles: ["Triceps", "Épaules"], defaultSets: 3, defaultReps: "15-20" },
    { name: "Pec deck (machine)", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Dips (pecs)", muscles: ["Triceps", "Épaules"], defaultSets: 3, defaultReps: "8-12" },
  ],
  "Dos": [
    { name: "Tractions pronation", muscles: ["Biceps"], defaultSets: 4, defaultReps: "6-10" },
    { name: "Tractions supination", muscles: ["Biceps"], defaultSets: 4, defaultReps: "6-10" },
    { name: "Rowing barre", muscles: ["Biceps", "Épaules"], defaultSets: 4, defaultReps: "8-10" },
    { name: "Rowing haltère", muscles: ["Biceps"], defaultSets: 3, defaultReps: "8-12" },
    { name: "Tirage poitrine poulie haute", muscles: ["Biceps"], defaultSets: 4, defaultReps: "10-12" },
    { name: "Tirage horizontal poulie basse", muscles: ["Biceps"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Soulevé de terre", muscles: ["Ischio-jambiers", "Fessiers"], defaultSets: 4, defaultReps: "5-8" },
    { name: "Pull-over", muscles: ["Poitrine"], defaultSets: 3, defaultReps: "12-15" },
    { name: "T-bar row", muscles: ["Biceps"], defaultSets: 3, defaultReps: "8-10" },
    { name: "Hyperextension", muscles: ["Ischio-jambiers", "Fessiers"], defaultSets: 3, defaultReps: "12-15" },
  ],
  "Épaules": [
    { name: "Développé militaire barre", muscles: ["Triceps"], defaultSets: 4, defaultReps: "6-10" },
    { name: "Développé militaire haltères", muscles: ["Triceps"], defaultSets: 4, defaultReps: "8-10" },
    { name: "Élévation latérale haltères", muscles: [], defaultSets: 4, defaultReps: "12-15" },
    { name: "Élévation frontale", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Oiseau haltères", muscles: ["Dos"], defaultSets: 3, defaultReps: "12-15" },
    { name: "Face pull poulie", muscles: ["Dos"], defaultSets: 3, defaultReps: "15-20" },
    { name: "Arnold press", muscles: ["Triceps"], defaultSets: 3, defaultReps: "8-12" },
    { name: "Shrug barre", muscles: [], defaultSets: 3, defaultReps: "10-15" },
  ],
  "Biceps": [
    { name: "Curl barre EZ", muscles: ["Avant-bras"], defaultSets: 3, defaultReps: "8-12" },
    { name: "Curl haltères alternés", muscles: ["Avant-bras"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Curl marteau", muscles: ["Avant-bras"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Curl concentré", muscles: [], defaultSets: 3, defaultReps: "10-12" },
    { name: "Curl incliné haltères", muscles: [], defaultSets: 3, defaultReps: "10-12" },
    { name: "Curl poulie basse", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Curl scott (preacher)", muscles: [], defaultSets: 3, defaultReps: "10-12" },
  ],
  "Triceps": [
    { name: "Dips (triceps)", muscles: ["Poitrine"], defaultSets: 3, defaultReps: "8-12" },
    { name: "Pushdown poulie corde", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Pushdown poulie barre", muscles: [], defaultSets: 3, defaultReps: "10-12" },
    { name: "Skull crusher barre EZ", muscles: [], defaultSets: 3, defaultReps: "8-12" },
    { name: "Extension nuque haltère", muscles: [], defaultSets: 3, defaultReps: "10-12" },
    { name: "Kick-back triceps", muscles: [], defaultSets: 3, defaultReps: "12-15" },
  ],
  "Jambes": [
    { name: "Squat barre", muscles: ["Fessiers", "Ischio-jambiers"], defaultSets: 4, defaultReps: "6-10" },
    { name: "Front squat", muscles: ["Fessiers"], defaultSets: 4, defaultReps: "6-10" },
    { name: "Leg press", muscles: ["Fessiers"], defaultSets: 4, defaultReps: "10-12" },
    { name: "Fentes marchées", muscles: ["Fessiers", "Ischio-jambiers"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Leg extension", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Leg curl couché", muscles: [], defaultSets: 3, defaultReps: "10-12" },
    { name: "Hip thrust barre", muscles: ["Fessiers"], defaultSets: 4, defaultReps: "8-12" },
    { name: "Bulgarian split squat", muscles: ["Fessiers", "Ischio-jambiers"], defaultSets: 3, defaultReps: "8-12" },
    { name: "RDL (Romanian Deadlift)", muscles: ["Ischio-jambiers", "Fessiers"], defaultSets: 3, defaultReps: "8-12" },
    { name: "Goblet squat", muscles: ["Fessiers"], defaultSets: 3, defaultReps: "10-15" },
  ],
  "Abdos": [
    { name: "Crunch", muscles: [], defaultSets: 3, defaultReps: "15-20" },
    { name: "Crunch inversé", muscles: [], defaultSets: 3, defaultReps: "15-20" },
    { name: "Gainage planche", muscles: [], defaultSets: 3, defaultReps: "30-60s" },
    { name: "Relevé de jambes suspendu", muscles: [], defaultSets: 3, defaultReps: "10-15" },
    { name: "Russian twist", muscles: [], defaultSets: 3, defaultReps: "20-30" },
    { name: "Roue abdominale", muscles: [], defaultSets: 3, defaultReps: "8-12" },
  ],
  "Adducteurs": [
    { name: "Machine adducteurs", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Squat sumo", muscles: ["Fessiers", "Quadriceps"], defaultSets: 4, defaultReps: "8-12" },
    { name: "Adduction poulie basse", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Fente latérale", muscles: ["Quadriceps", "Fessiers"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Copenhagen plank", muscles: ["Abdos"], defaultSets: 3, defaultReps: "20-30s" },
  ],
  "Abducteurs": [
    { name: "Machine abducteurs", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Abduction poulie basse", muscles: ["Fessiers"], defaultSets: 3, defaultReps: "12-15" },
    { name: "Marche latérale élastique", muscles: ["Fessiers"], defaultSets: 3, defaultReps: "15-20" },
    { name: "Clam shell", muscles: ["Fessiers"], defaultSets: 3, defaultReps: "15-20" },
    { name: "Élévation latérale jambe", muscles: ["Fessiers"], defaultSets: 3, defaultReps: "12-15" },
  ],
  "Mollets": [
    { name: "Mollets debout machine", muscles: [], defaultSets: 4, defaultReps: "12-15" },
    { name: "Mollets assis machine", muscles: [], defaultSets: 4, defaultReps: "15-20" },
    { name: "Mollets debout barre", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Mollets presse à cuisse", muscles: [], defaultSets: 3, defaultReps: "15-20" },
    { name: "Mollets une jambe haltère", muscles: [], defaultSets: 3, defaultReps: "12-15" },
  ],
  "Avant-bras": [
    { name: "Curl poignet barre", muscles: [], defaultSets: 3, defaultReps: "15-20" },
    { name: "Curl inversé barre", muscles: ["Biceps"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Extension poignet barre", muscles: [], defaultSets: 3, defaultReps: "15-20" },
    { name: "Farmer walk", muscles: [], defaultSets: 3, defaultReps: "30-40s" },
    { name: "Gripper / pince", muscles: [], defaultSets: 3, defaultReps: "15-20" },
  ],
};

// Groupes musculaires pour les filtres
var EXERCISE_MUSCLE_GROUPS = [
  "Poitrine", "Dos", "Épaules", "Biceps", "Triceps",
  "Jambes", "Abdos", "Adducteurs", "Abducteurs", "Mollets", "Avant-bras"
];

// Mapping groupe biblio → muscle principal dans l'app
var LIBRARY_TO_MUSCLE = {
  "Poitrine": "Pecs",
  "Dos": "Dos",
  "Épaules": "Épaules",
  "Biceps": "Biceps",
  "Triceps": "Triceps",
  "Jambes": "Quadriceps",
  "Abdos": "Abdos",
  "Adducteurs": "Adducteurs",
  "Abducteurs": "Abducteurs",
  "Mollets": "Mollets",
  "Avant-bras": "Avant-bras",
};
