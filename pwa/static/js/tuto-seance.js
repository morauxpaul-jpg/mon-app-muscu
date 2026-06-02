/**
 * Tutoriel de la page Séance (saisie d'un entraînement).
 * Utilise le moteur partagé TutoEngine (tuto-engine.js).
 */
(function () {
  "use strict";

  var STORAGE_KEY = "tutoSeanceSeen";

  function openFirstExo(cb) {
    var el = document.querySelector("#exo-anchor-0");
    if (!el) return cb();
    var d = el._x_dataStack && el._x_dataStack[0];
    if (d && !d.open) { d.open = true; setTimeout(cb, 320); return; }
    cb();
  }

  function scrollToThen(selector, cb) {
    var el = document.querySelector(selector);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(cb, 360);
  }

  var STEPS = [
    {
      target: "#exo-anchor-0",
      title: "Tes exercices du jour",
      text: "Voici tes exercices, dans l'ordre de ton programme. Touche un exercice (ou son +) pour le déplier.",
    },
    {
      target: "#exo-anchor-0 .sets-table",
      title: "Le tableau de saisie",
      text: "Chaque exercice se déplie sur un tableau : une ligne par série. C'est ici que tu notes ta performance.",
      onEnter: function (cb) { openFirstExo(cb); },
    },
    {
      target: '#exo-anchor-0 input[placeholder="reps"]',
      title: "Les répétitions",
      text: "Saisis le nombre de répétitions de la série. Exemple : 10.",
      onEnter: function (cb) { openFirstExo(cb); },
    },
    {
      target: function () {
        return document.querySelector('#exo-anchor-0 input[placeholder="kg"]')
            || document.querySelector("#exo-anchor-0 .sets-table");
      },
      title: "Le poids",
      text: "Saisis le poids en kg. S'il est pré-rempli depuis ta dernière séance, tu peux le corriger.",
    },
    {
      target: function () {
        return document.querySelector("#exo-anchor-0 .sets-table select")
            || document.querySelector("#exo-anchor-0 .sets-table");
      },
      title: "Le RPE (optionnel)",
      text: "Le RPE note la difficulté ressentie : 6 = facile, 8 = il restait 2 reps en réserve, 10 = échec. Pratique pour piloter ton intensité — laisse « — » si tu ne veux pas l'utiliser.",
    },
    {
      target: '[data-tuto-seance="chrono"]',
      title: "Le chrono de repos",
      text: "Après chaque série validée, un chrono de repos se lance en bas de l'écran. Tu peux changer sa durée ou le passer.",
      onEnter: function (cb) { scrollToThen('[data-tuto-seance="chrono"]', cb); },
    },
    {
      target: '[data-tuto-seance="finish"]',
      title: "Terminer la séance",
      text: "Une fois tous tes exercices faits, touche « Terminer la séance » : tout est enregistré dans ton historique.",
      finalLabel: "Compris !",
      onEnter: function (cb) { scrollToThen('[data-tuto-seance="finish"]', cb); },
    },
  ];

  function initTutoSeance(options) {
    options = options || {};
    if (!options.force) {
      try { if (localStorage.getItem(STORAGE_KEY) === "true") return; } catch (e) { return; }
    }
    // Le tuto d'accueil est prioritaire.
    try { if (localStorage.getItem("tutoSeen") !== "true") return; } catch (e) { return; }
    if (document.getElementById("tuto-overlay")) return;
    setTimeout(function () {
      if (window.TutoEngine) window.TutoEngine.run(STEPS, { storageKey: STORAGE_KEY });
    }, 700);
  }

  window.initTutoSeance = initTutoSeance;
  window.replayTutoSeance = function () {
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
    if (window.TutoEngine) window.TutoEngine.run(STEPS, { storageKey: STORAGE_KEY });
  };
})();
