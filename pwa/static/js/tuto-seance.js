/**
 * Bulles de la page Séance : trois, chacune au moment où elle sert.
 * Utilise le moteur partagé TutoEngine (tuto-engine.js).
 *
 * Huit bulles d'affilée s'ouvraient avant la première série (RPE, chrono,
 * « Terminer »…) : au jour 1, quatorze avec celles de l'accueil (audit du
 * 18/10, m9). Désormais :
 *   1. à l'arrivée : la série en cours, et « Série faite » ;
 *   2. après la première série faite : le repos, la série suivante prête ;
 *   3. après le premier exercice fini : la suite, et « Terminer la séance ».
 *
 * localStorage « tutoSeanceSeen » : "1" ou "2" = bulles déjà vues, "true" =
 * fini (ou « Passer » touché). L'effacer (Plus › Gestion) relance les trois.
 * seance.js signale les gestes : « seance:serie-faite », « seance:exercice-fini ».
 */
(function () {
  "use strict";

  var STORAGE_KEY = "tutoSeanceSeen";

  function vues() {
    try {
      var v = localStorage.getItem(STORAGE_KEY);
      return v === "true" ? 3 : (parseInt(v, 10) || 0);
    } catch (e) { return 3; }   // stockage refusé : aucune bulle plutôt qu'à chaque page
  }

  function noter(n) {
    try { localStorage.setItem(STORAGE_KEY, n >= 3 ? "true" : String(n)); } catch (e) {}
  }

  // getClientRects et non offsetParent : celui-ci est nul pour un élément
  // en position fixe, comme la barre du chrono.
  function visible(el) {
    return !!(el && !el.hidden && el.getClientRects().length > 0);
  }

  function serieEnCours() {
    var toutes = document.querySelectorAll(".serie-encours");
    for (var i = 0; i < toutes.length; i++) if (visible(toutes[i])) return toutes[i];
    return null;
  }

  function openFirstExo(cb) {
    if (serieEnCours()) return cb();
    var el = document.querySelector("#exo-anchor-0");
    var d = el && el._x_dataStack && el._x_dataStack[0];
    if (d && !d.open) { d.open = true; setTimeout(cb, 320); return; }
    cb();
  }

  // Montre la bulle n (1, 2 ou 3) si c'est son tour et que rien d'autre
  // n'est ouvert. Rien n'est noté tant qu'elle n'a pas été vue.
  function montrer(n, etape) {
    if (vues() !== n - 1) return;
    if (!window.TutoEngine || document.getElementById("tuto-overlay")) return;
    window.TutoEngine.run([etape], {
      onFinish: function (comment) { noter(comment === "passer" ? 3 : n); },
    });
  }

  function bulleArrivee() {
    if (!serieEnCours() && !document.querySelector("#exo-anchor-0")) return;
    // La bulle d'accueil parle d'un bouton qu'on vient de toucher : arrivé
    // ici, elle n'a plus lieu d'être.
    try { localStorage.setItem("tutoSeen", "true"); } catch (e) {}
    montrer(1, {
      target: function () { return serieEnCours() || document.querySelector("#exo-anchor-0"); },
      title: "Une série à la fois",
      text: "La charge et les répétitions sont déjà proposées. Fais ta série, corrige les chiffres si besoin, puis touche « Série faite ».",
      finalLabel: "C'est parti",
      onEnter: openFirstExo,
    });
  }

  function bulleRepos() {
    // Le chrono apparaît juste après le geste : on lui laisse le temps.
    setTimeout(function () {
      var chrono = document.getElementById("rest-timer");
      var avecChrono = visible(chrono);
      montrer(2, {
        target: avecChrono ? "#rest-timer" : null,
        center: !avecChrono,
        title: "Série enregistrée",
        text: (avecChrono ? "Le chrono de repos tourne en bas de l'écran et sonne quand c'est reparti. " : "")
          + "La série suivante est prête avec la même charge. Une série faite se corrige en la touchant.",
        finalLabel: "OK",
      });
    }, 500);
  }

  function bulleExerciceFini() {
    montrer(3, {
      center: true,
      title: "Premier exercice terminé",
      text: "Touche « Exercice suivant » pour continuer. À la fin, « Terminer la séance », tout en bas, enregistre ta séance et ton ressenti. Rien ne se perd, même sans réseau.",
      finalLabel: "Compris",
    });
  }

  function initTutoSeance(options) {
    options = options || {};
    if (options.force) noter(0);
    if (vues() >= 3) return;
    document.addEventListener("seance:serie-faite", bulleRepos);
    document.addEventListener("seance:exercice-fini", bulleExerciceFini);
    setTimeout(bulleArrivee, 700);
  }

  window.initTutoSeance = initTutoSeance;
  window.replayTutoSeance = function () { initTutoSeance({ force: true }); };
})();
