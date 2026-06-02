/**
 * Tutoriel d'accueil (onboarding des onglets) + démos de fonctionnalités.
 * Utilise le moteur partagé TutoEngine (tuto-engine.js).
 */
(function () {
  "use strict";

  var STORAGE_KEY = "tutoSeen";

  var STEPS = [
    {
      target: '[data-tuto="welcome"]',
      title: "Bienvenue sur Muscu Tracker",
      text: "Ce rapide tutoriel te présente les 4 onglets de l'app. Tu ne le verras qu'une seule fois — tu pourras le relancer depuis Plus › Gestion.",
      center: true,
    },
    {
      target: '[data-tuto="dashboard"]',
      title: "Accueil — ton tableau de bord",
      text: "Le résumé de ta semaine : planning, séance du jour, statistiques et série (streak) en un coup d'œil.",
    },
    {
      target: '[data-tuto="seance"]',
      title: "Séance — logger ton entraînement",
      text: "Choisis ta séance, saisis reps + poids (+ RPE si tu veux). Un chrono de repos se lance entre les séries, et chaque exercice a sa fiche détaillée.",
    },
    {
      target: '[data-tuto="progres"]',
      title: "Progrès — suivre ton évolution",
      text: "Calendrier, volume hebdomadaire, carte du corps, records et table des maxima (RM). Touche un jour du calendrier pour revoir la séance.",
    },
    {
      target: '[data-tuto="plus"]',
      title: "Plus — tout le reste",
      text: "Coach IA, programme, nutrition, cardio, calcul de plaques, gestion… et ce tutoriel, à relancer quand tu veux.",
    },
    {
      target: null,
      title: "C'est parti ! 💪",
      text: "Tu connais l'essentiel. Lance ta première séance — et bon entraînement !",
      center: true,
      finalLabel: "Commencer",
    },
  ];

  function initTutorial(options) {
    options = options || {};
    if (!options.force) {
      try { if (localStorage.getItem(STORAGE_KEY) === "true") return; } catch (e) {}
    }
    var p = location.pathname || "";
    if (p.indexOf("/onboarding") === 0 || p.indexOf("/login") === 0) return;
    if (!document.querySelector(".bottom-nav")) return;

    var launch = function () {
      if (!window.TutoEngine) return;
      window.TutoEngine.run(STEPS, { storageKey: STORAGE_KEY });
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", launch);
    } else {
      launch();
    }
  }

  function playFeatureDemo(featureSteps, options) {
    options = options || {};
    if (!Array.isArray(featureSteps) || !featureSteps.length) return;
    if (!window.TutoEngine) return;
    var filtered = featureSteps.filter(function (s) {
      if (!s.target || s.center) return true;
      return !!document.querySelector(s.target);
    });
    if (!filtered.length) return;
    window.TutoEngine.run(filtered, { onFinish: options.onFinish || function () {} });
  }

  function checkPendingDemo() {
    var pending = null;
    try { pending = sessionStorage.getItem("pending_demo"); } catch (e) { return; }
    if (!pending) return;
    try { sessionStorage.removeItem("pending_demo"); } catch (e) {}
    var demo;
    try { demo = JSON.parse(pending); } catch (e) { return; }
    if (!demo || !demo.steps) return;
    if (demo.url && location.pathname !== demo.url) return;
    setTimeout(function () { playFeatureDemo(demo.steps); }, 600);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", checkPendingDemo);
  } else {
    checkPendingDemo();
  }

  window.initTutorial = initTutorial;
  window.replayTutorial = function () {
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
    if (window.TutoEngine) window.TutoEngine.run(STEPS, { storageKey: STORAGE_KEY });
  };
  window.playFeatureDemo = playFeatureDemo;
})();
