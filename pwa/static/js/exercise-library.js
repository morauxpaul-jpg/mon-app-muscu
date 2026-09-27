/**
 * Bibliothèque d'exercices prédéfinis par groupe musculaire.
 * Utilisée par la modale "Choisir un exercice" dans seance_edit et programme.
 */
var EXERCISE_LIBRARY = {
  "Poitrine": [
    { name: "Développé couché", alias: "bench press", muscles: ["Triceps", "Épaules"], defaultSets: 4, defaultReps: "8-10" },
    { name: "Développé incliné", alias: "Développé incliné haltères Haltères incline bench press", muscles: ["Épaules", "Triceps"], defaultSets: 4, defaultReps: "8-10" },
    { name: "Développé décliné", muscles: ["Triceps"], defaultSets: 3, defaultReps: "8-10" },
    { name: "Écarté couché", muscles: ["Épaules"], defaultSets: 3, defaultReps: "12-15" },
    { name: "Écarté poulie vis-à-vis", alias: "cable fly crossover Écartés poulie Écartés poulie (crossover)", muscles: ["Épaules"], defaultSets: 3, defaultReps: "12-15" },
    { name: "Pompes", alias: "Lesté Pompes lestées push up", muscles: ["Triceps", "Épaules"], defaultSets: 3, defaultReps: "15-20" },
    { name: "Développé machine", alias: "Développé machine (chest press) chest press developpe pectoraux machine machine chest press presse pectoraux seated chest press", muscles: ["Triceps", "Épaules"], defaultSets: 4, defaultReps: "8-12" },
    { name: "Écarté machine", alias: "butterfly chest fly pec deck pec fly Écarté machine (pec deck)", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Dips (pecs)", alias: "Dips lestés Dips machine Lesté Machine", muscles: ["Triceps", "Épaules"], defaultSets: 3, defaultReps: "8-12" },
  ],
  "Dos": [
    { name: "Tractions pronation", alias: "Lesté Tractions lestées chin up pull up", muscles: ["Biceps"], defaultSets: 4, defaultReps: "6-10" },
    { name: "Tractions supination", alias: "Lesté Tractions lestées chin up pull up", muscles: ["Biceps"], defaultSets: 4, defaultReps: "6-10" },
    { name: "Rowing barre", alias: "barbell row", muscles: ["Biceps", "Épaules"], defaultSets: 4, defaultReps: "8-10" },
    { name: "Rowing haltère", alias: "dumbbell row", muscles: ["Biceps"], defaultSets: 3, defaultReps: "8-12" },
    { name: "Tirage vertical prise large", alias: "Tirage vertical (poulie haute) lat pulldown poulie haute pulldown tirage poitrine tirage poitrine poulie haute", muscles: ["Biceps"], defaultSets: 4, defaultReps: "10-12" },
    { name: "Tirage vertical prise serrée", muscles: ["Biceps"], defaultSets: 4, defaultReps: "10-12" },
    { name: "Tirage horizontal prise neutre", alias: "Tirage horizontal (poulie basse) Tirage horizontal poulie cable row poulie basse seated row", muscles: ["Biceps"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Tirage horizontal prise large", alias: "Tirage horizontal (poulie basse) Tirage horizontal poulie cable row poulie basse seated row", muscles: ["Épaules"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Soulevé de terre", alias: "deadlift", muscles: ["Ischio-jambiers", "Fessiers"], defaultSets: 4, defaultReps: "5-8" },
    { name: "Pull-over", muscles: ["Poitrine"], defaultSets: 3, defaultReps: "12-15" },
    { name: "T-bar row", muscles: ["Biceps"], defaultSets: 3, defaultReps: "8-10" },
    { name: "Hyperextension", muscles: ["Ischio-jambiers", "Fessiers"], defaultSets: 3, defaultReps: "12-15" },
  ],
  "Épaules": [
    { name: "Développé militaire", alias: "Développé militaire haltères Haltères military press overhead press shoulder press", muscles: ["Triceps"], defaultSets: 4, defaultReps: "6-10" },
    { name: "Élévations latérales", alias: "Haltères lateral raise side raise Élévations latérales haltères", muscles: [], defaultSets: 4, defaultReps: "12-15" },
    { name: "Élévation frontale", alias: "elevation frontale front raise Élévations frontales", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Oiseau", alias: "Oiseau (élévation postérieure) elevation posterieure rear delt fly élévation postérieure", muscles: ["Dos"], defaultSets: 3, defaultReps: "12-15" },
    { name: "Reverse fly machine", alias: "Reverse fly machine (pec deck inversé) pec deck inverse pec deck inversé rear delt machine reverse pec deck", muscles: ["Dos"], defaultSets: 3, defaultReps: "12-15" },
    { name: "Face pull", muscles: ["Dos"], defaultSets: 3, defaultReps: "15-20" },
    { name: "Arnold press", muscles: ["Triceps"], defaultSets: 3, defaultReps: "8-12" },
    { name: "Shrug", alias: "Shrug (haussement d'épaules) haussement d epaules haussement d'épaules", muscles: [], defaultSets: 3, defaultReps: "10-15" },
  ],
  "Biceps": [
    { name: "Curl barre EZ", alias: "Curl biceps Curl haltères Haltères barbell curl curl australien curl concentration curl poulie basse curl pupitre curl scott", muscles: ["Avant-bras"], defaultSets: 3, defaultReps: "8-12" },
    { name: "Curl alterné", muscles: ["Avant-bras"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Curl marteau", alias: "hammer curl", muscles: ["Avant-bras"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Curl concentré", muscles: [], defaultSets: 3, defaultReps: "10-12" },
    { name: "Curl incliné", alias: "Curl incliné haltères", muscles: [], defaultSets: 3, defaultReps: "10-12" },
    { name: "Curl poulie basse", alias: "Barre Curl barre Curl biceps Curl haltères Haltères barbell curl curl australien curl barre ez curl concentration curl pupitre curl scott", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Curl scott (preacher)", alias: "Barre Curl barre Curl biceps Curl haltères Haltères barbell curl curl australien curl barre ez curl concentration curl poulie basse curl pupitre", muscles: [], defaultSets: 3, defaultReps: "10-12" },
  ],
  "Triceps": [
    { name: "Dips (triceps)", alias: "Dips lestés Dips machine Lesté Machine", muscles: ["Poitrine"], defaultSets: 3, defaultReps: "8-12" },
    { name: "Pushdown poulie corde", alias: "Extensions triceps Extensions triceps poulie triceps pushdown", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Pushdown poulie barre", alias: "Extensions triceps Extensions triceps poulie triceps pushdown", muscles: [], defaultSets: 3, defaultReps: "10-12" },
    { name: "Skull crusher", alias: "Barre au front Barre au front (skull crusher)", muscles: [], defaultSets: 3, defaultReps: "8-12" },
    { name: "Extension nuque", alias: "Extension triceps haltère Extension triceps haltère (au-dessus de la tête) au dessus de la tete au-dessus de la tête extension nuque haltere french press overhead triceps extension", muscles: [], defaultSets: 3, defaultReps: "10-12" },
    { name: "Kick-back triceps", alias: "Kickback triceps kick back kick back triceps kickback poulie", muscles: [], defaultSets: 3, defaultReps: "12-15" },
  ],
  "Jambes": [
    { name: "Squat", muscles: ["Fessiers", "Ischio-jambiers"], defaultSets: 4, defaultReps: "6-10" },
    { name: "Front squat", muscles: ["Fessiers"], defaultSets: 4, defaultReps: "6-10" },
    { name: "Leg press", alias: "Presse à cuisses Presse à cuisses (Leg press)", muscles: ["Fessiers"], defaultSets: 4, defaultReps: "10-12" },
    { name: "Fentes marchées", alias: "walking lunges", muscles: ["Fessiers", "Ischio-jambiers"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Leg extension", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Leg curl couché", alias: "Leg curl (allongé) allonge allongé leg curl allonge leg curl couche leg curl machine lying leg curl", muscles: ["Ischio-jambiers"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Leg curl assis", alias: "seated leg curl", muscles: ["Ischio-jambiers"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Hip thrust", muscles: ["Fessiers"], defaultSets: 4, defaultReps: "8-12" },
    { name: "Bulgarian split squat", alias: "Squat bulgare", muscles: ["Fessiers", "Ischio-jambiers"], defaultSets: 3, defaultReps: "8-12" },
    { name: "RDL (Romanian Deadlift)", alias: "Haltères Soulevé de terre roumain Soulevé de terre roumain (RDL) Soulevé de terre roumain haltères", muscles: ["Ischio-jambiers", "Fessiers"], defaultSets: 3, defaultReps: "8-12" },
    { name: "Goblet squat", alias: "Squat gobelet", muscles: ["Fessiers"], defaultSets: 3, defaultReps: "10-15" },
  ],
  "Abdos": [
    { name: "Crunch", muscles: [], defaultSets: 3, defaultReps: "15-20" },
    { name: "Crunch inversé", muscles: [], defaultSets: 3, defaultReps: "15-20" },
    { name: "Gainage planche", alias: "Gainage (Planche)", muscles: [], defaultSets: 3, defaultReps: "30-60s" },
    { name: "Relevé de jambes suspendu", alias: "leg raise", muscles: [], defaultSets: 3, defaultReps: "10-15" },
    { name: "Russian twist", muscles: [], defaultSets: 3, defaultReps: "20-30" },
    { name: "Roue abdominale", muscles: [], defaultSets: 3, defaultReps: "8-12" },
  ],
  "Adducteurs": [
    { name: "Machine adducteurs", alias: "adductor machine hip adduction", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Squat sumo", muscles: ["Fessiers", "Quadriceps"], defaultSets: 4, defaultReps: "8-12" },
    { name: "Adduction poulie basse", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Fente latérale", alias: "Fentes latérales", muscles: ["Quadriceps", "Fessiers"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Copenhagen plank", muscles: ["Abdos"], defaultSets: 3, defaultReps: "20-30s" },
  ],
  "Abducteurs": [
    { name: "Machine abducteurs", alias: "abductions hanches abductor machine hip abduction", muscles: [], defaultSets: 3, defaultReps: "12-15" },
    { name: "Abduction poulie basse", muscles: ["Fessiers"], defaultSets: 3, defaultReps: "12-15" },
    { name: "Marche latérale", muscles: ["Fessiers"], defaultSets: 3, defaultReps: "15-20" },
    { name: "Clam shell", muscles: ["Fessiers"], defaultSets: 3, defaultReps: "15-20" },
    { name: "Abduction de hanche debout", muscles: ["Fessiers"], defaultSets: 3, defaultReps: "12-15" },
  ],
  "Mollets": [
    { name: "Mollets debout", alias: "calf raise", muscles: [], defaultSets: 4, defaultReps: "12-15" },
    { name: "Mollets assis", muscles: [], defaultSets: 4, defaultReps: "15-20" },
    { name: "Mollets presse à cuisse", alias: "Leg press Presse à cuisses Presse à cuisses (Leg press) leg press", muscles: [], defaultSets: 3, defaultReps: "15-20" },
    { name: "Mollets une jambe", alias: "Mollets unilatéral", muscles: [], defaultSets: 3, defaultReps: "12-15" },
  ],
  "Avant-bras": [
    { name: "Curl poignet", muscles: [], defaultSets: 3, defaultReps: "15-20" },
    { name: "Curl inversé", muscles: ["Biceps"], defaultSets: 3, defaultReps: "10-12" },
    { name: "Extension poignet", muscles: [], defaultSets: 3, defaultReps: "15-20" },
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

/**
 * Recherche dans la bibliothèque.
 *
 * L'ancienne version faisait un `indexOf` brut sur le nom. Trois échecs en
 * découlaient, tous rencontrés à l'usage :
 *   — taper « ecarte » ne trouvait pas « Écarté » (l'accent) ;
 *   — « adducteur machine » ne trouvait pas « Machine adducteurs » (l'ordre) ;
 *   — « pec fly » ne trouvait pas « Pec deck » (le surnom).
 * Le premier est le plus grave : on cherche sans accents au clavier du
 * téléphone, et on conclut que l'exercice n'existe pas.
 */
function normaliserRecherche(texte) {
  return (texte || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")   // accents
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .toLowerCase();
}

function exerciseMatches(ex, requete) {
  var q = normaliserRecherche(requete);
  if (!q) return true;
  var champs = [ex.name, (ex.muscles || []).join(" "), ex.alias || ""];
  var cible = normaliserRecherche(champs.join(" "));
  // Chaque mot tapé doit se retrouver : l'ordre n'a pas d'importance, et
  // un mot en trop ne doit pas faire disparaître le résultat.
  return q.split(" ").every(function (mot) { return cible.indexOf(mot) >= 0; });
}

if (typeof window !== "undefined") {
  window.normaliserRecherche = normaliserRecherche;
  window.exerciseMatches = exerciseMatches;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { normaliserRecherche: normaliserRecherche,
                     exerciseMatches: exerciseMatches,
                     EXERCISE_LIBRARY: EXERCISE_LIBRARY };
}
