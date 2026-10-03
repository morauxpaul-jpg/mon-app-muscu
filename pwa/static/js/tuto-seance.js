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
      // Les cibles suivent la saisie série par série : l'ancien tableau
      // (.sets-table, placeholder « reps », sélecteur « — ») n'existe plus,
      // et trois bulles sur sept flottaient au centre de l'écran.
      target: "#exo-anchor-0 .serie-encours",
      title: "Une série à la fois",
      text: "Chaque exercice se déplie sur sa série en cours. Les séries faites se replient en une ligne, que tu peux toucher pour corriger.",
      onEnter: function (cb) { openFirstExo(cb); },
    },
    {
      target: '#exo-anchor-0 .serie-encours input[inputmode="numeric"]',
      title: "Les répétitions",
      text: "Le chiffre en gris est ton objectif. Fait tel quel ? Touche « Série faite » directement. Sinon, tape ce que tu as vraiment fait.",
      onEnter: function (cb) { openFirstExo(cb); },
    },
    {
      target: function () {
        return document.querySelector('#exo-anchor-0 .serie-encours input[inputmode="decimal"]')
            || document.querySelector("#exo-anchor-0 .serie-encours");
      },
      title: "Le poids",
      text: "Saisis le poids en kg. S'il est pré-rempli depuis ta dernière séance, tu peux le corriger.",
    },
    {
      target: function () {
        return document.querySelector("#exo-anchor-0 .serie-options .serie-puce")
            || document.querySelector("#exo-anchor-0 .serie-encours");
      },
      title: "Le RPE (optionnel)",
      text: "Le RPE note la difficulté ressentie : 6 = facile, 8 = il restait 2 reps en réserve, 10 = échec. Il se cache derrière « RPE, remarque » — ignore-le si tu ne veux pas l'utiliser.",
    },
    {
      target: "#exo-anchor-0 .serie-valider",
      title: "Série faite",
      text: "Touche « Série faite » : la série est enregistrée tout de suite, et le chrono de repos démarre. Sans réseau, elle est gardée sur le téléphone et part au retour du réseau.",
    },
    {
      target: '[data-tuto-seance="chrono"]',
      title: "Le chrono de repos",
      text: "Le chrono de repos s'affiche en bas de l'écran. Tu peux changer sa durée ou le passer.",
      onEnter: function (cb) { scrollToThen('[data-tuto-seance="chrono"]', cb); },
    },
    {
      target: '[data-tuto-seance="finish"]',
      title: "Terminer la séance",
      text: "Une fois tes exercices faits, touche « Terminer la séance » pour noter ta séance. Ce qui n'était pas encore parti est envoyé avant : rien ne se perd.",
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
