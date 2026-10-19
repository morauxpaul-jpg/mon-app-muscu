/**
 * Tutoriel d'accueil (une bulle sur « Commencer ») + démos de fonctionnalités.
 * Utilise le moteur partagé TutoEngine (tuto-engine.js).
 */
(function () {
  "use strict";

  var STORAGE_KEY = "tutoSeen";

  // Une bulle, sur le bouton qui lance la séance (audit du 18/10, m9). Six
  // bulles présentaient les quatre onglets avant le moindre geste, puis
  // « Compris » laissait sur l'accueil ; les retours disaient l'app peu
  // claire au premier abord. Le reste s'apprend en s'entraînant : la séance
  // a ses propres bulles, chacune au moment où elle sert (tuto-seance.js).
  function etapes() {
    var cta = document.querySelector(".next-session-card");
    if (!cta) {
      return [{
        center: true,
        title: "Bienvenue sur Muscu Tracker",
        text: "Séance pour t'entraîner, Progrès pour voir tes courbes, Plus pour ton programme, le coach et la nutrition. Tout est dans les onglets du bas.",
        finalLabel: "Compris",
      }];
    }
    var libelle = (cta.textContent || "").replace(/\s+/g, " ").trim() || "Commencer";
    return [{
      target: ".next-session-card",
      title: "Ta première séance est prête",
      text: "Touche « " + libelle + " » : l'app te guide série par série, avec une charge de départ déjà proposée. Tes progrès, ton programme et le coach sont dans les onglets du bas.",
      finalLabel: libelle,
      action: function () { location.href = cta.href; },
    }];
  }

  function initTutorial(options) {
    options = options || {};
    if (!options.force) {
      try { if (localStorage.getItem(STORAGE_KEY) === "true") return; } catch (e) {}
    }
    // L'accueil seulement : la bulle parle de son bouton. Elle s'ouvrait sur
    // n'importe quelle page vue en premier, séance comprise.
    if ((location.pathname || "") !== "/accueil") return;
    if (!document.querySelector(".bottom-nav")) return;

    var launch = function () {
      if (!window.TutoEngine) return;
      window.TutoEngine.run(etapes(), { storageKey: STORAGE_KEY });
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
    if (window.TutoEngine) window.TutoEngine.run(etapes(), { storageKey: STORAGE_KEY });
  };
  window.playFeatureDemo = playFeatureDemo;
})();
