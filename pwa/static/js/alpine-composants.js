/*
 * Alpine en version CSP (audit du 06/10, m6) : la page n'a plus le droit
 * d'exécuter du code fabriqué à la volée (`unsafe-eval`). Alpine lit donc
 * les attributs avec son propre lecteur, qui n'accepte qu'UNE expression
 * simple (pas de `;`, de `=>`, de `typeof`, de `?.`) et ne voit pas les
 * variables globales. Tout ce qui dépasse vit ici ou dans le script de la
 * page, sous un nom :
 *
 * - les composants (`x-data="exoBlock(…)"`) sont enregistrés auprès d'Alpine ;
 * - `x-au-corps="ouvert"` sort une fenêtre vers <body> quand elle s'ouvre
 *   (sinon un parent `transform` la coince dans sa carte) ;
 * - `$biblio` donne la bibliothèque d'exercices (exercise-library.js).
 *
 * Chargé AVANT alpine.min.js (qui est en `defer`) : les composants sont
 * définis par les scripts de la page, tous exécutés avant Alpine.
 */
(function () {
  "use strict";
  var COMPOSANTS = [
    "exoBlock", "seanceReorder", "cardioBlock", "cardioForm", "coachChat",
    "debriefCard", "gen", "mealForm", "onboardingFlow", "plaqueCalc",
    "programmeApp", "bandeauRetour", "ajoutExoSeance",
  ];

  // Alpine refuse de rendre un objet posé sur `window` : chaque appel rend
  // une copie.
  function copie(v) { return v == null ? v : JSON.parse(JSON.stringify(v)); }

  var BIBLIO = {
    groupes: function () { return copie(window.EXERCISE_MUSCLE_GROUPS) || []; },
    exos: function (groupe) {
      var lib = window.EXERCISE_LIBRARY;
      return copie(lib && lib[groupe]) || [];
    },
    // Même recherche que la page Séance (accents et casse ignorés).
    correspond: function (ex, requete) {
      if (typeof window.exerciseMatches === "function") return window.exerciseMatches(ex, requete);
      return !requete || ex.name.toLowerCase().indexOf(String(requete).toLowerCase()) >= 0;
    },
    // Le muscle du programme qui correspond à un groupe de la bibliothèque.
    muscleDe: function (groupe, defaut) {
      var table = window.LIBRARY_TO_MUSCLE;
      return (table && table[groupe]) || defaut;
    },
  };

  document.addEventListener("alpine:init", function () {
    var Alpine = window.Alpine;
    COMPOSANTS.forEach(function (nom) {
      if (typeof window[nom] === "function") Alpine.data(nom, window[nom]);
    });

    Alpine.directive("au-corps", function (el, directive, outils) {
      var lire = outils.evaluateLater(directive.expression);
      outils.effect(function () {
        lire(function (ouvert) {
          if (ouvert && el.parentNode !== document.body) document.body.appendChild(el);
        });
      });
    });

    Alpine.magic("biblio", function () { return BIBLIO; });
  });
})();
