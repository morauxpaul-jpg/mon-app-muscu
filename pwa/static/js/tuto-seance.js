(function () {
  "use strict";

  var STORAGE_KEY = "tutoSeanceSeen";
  var currentStep = 0;
  var overlay, mask, spot, bubble;

  var STEPS = [
    {
      getTarget: function () {
        return document.querySelector("#exo-anchor-0");
      },
      title: "Tes exercices du jour",
      text: "Voici tes exercices du jour. Ils sont dans l'ordre de ton programme. Clique sur le + d'un exercice pour l'ouvrir.",
    },
    {
      getTarget: function () {
        return document.querySelector("#exo-anchor-0 .sets-table");
      },
      title: "Tableau de saisie",
      text: "Chaque exercice se déplie pour montrer le tableau de saisie. Tu vas remplir tes s\u00e9ries ici.",
      onEnter: function (cb) {
        var el = document.querySelector("#exo-anchor-0");
        if (!el) return cb();
        var d = el._x_dataStack && el._x_dataStack[0];
        if (d && !d.open) {
          d.open = true;
          setTimeout(cb, 350);
          return;
        }
        cb();
      },
    },
    {
      getTarget: function () {
        return document.querySelector('#exo-anchor-0 input[placeholder="reps"]');
      },
      title: "Nombre de r\u00e9p\u00e9titions",
      text: "Tape le nombre de r\u00e9p\u00e9titions que tu as fait pour cette s\u00e9rie. Par exemple : 10",
    },
    {
      getTarget: function () {
        return (
          document.querySelector('#exo-anchor-0 input[placeholder="kg"]') ||
          document.querySelector("#exo-anchor-0 .sets-table")
        );
      },
      title: "Poids utilis\u00e9",
      text: "Tape le poids utilis\u00e9 en kg. Si tu as activ\u00e9 le remplissage auto, le poids de ta derni\u00e8re s\u00e9ance est d\u00e9j\u00e0 pr\u00e9-rempli. Tu peux le modifier.",
    },
    {
      getTarget: function () {
        return document.querySelector('[data-tuto-seance="chrono"]');
      },
      title: "Chrono de repos",
      text: "Apr\u00e8s chaque s\u00e9rie, un chrono de repos se lance automatiquement en bas de l'\u00e9cran. Tu peux choisir la dur\u00e9e ou le passer.",
      onEnter: function (cb) {
        var btn = document.querySelector('[data-tuto-seance="chrono"]');
        if (btn) btn.scrollIntoView({ behavior: "smooth", block: "center" });
        setTimeout(cb, 350);
      },
    },
    {
      getTarget: function () {
        return document.querySelector('[data-tuto-seance="finish"]');
      },
      title: "Valider ta s\u00e9ance",
      text: "Quand tu as fini tous tes exercices, clique sur Valider pour enregistrer ta s\u00e9ance. Tes donn\u00e9es sont sauvegard\u00e9es dans ton historique.",
      finalLabel: "Compris !",
      onEnter: function (cb) {
        var btn = document.querySelector('[data-tuto-seance="finish"]');
        if (btn) btn.scrollIntoView({ behavior: "smooth", block: "center" });
        setTimeout(cb, 350);
      },
    },
  ];

  function buildDom() {
    overlay = document.createElement("div");
    overlay.id = "tuto-overlay";
    overlay.innerHTML =
      '<div id="tuto-mask"></div>' +
      '<div id="tuto-spot" class="hidden"></div>' +
      '<div id="tuto-bubble">' +
      '  <button id="tuto-skip" type="button">Passer \u2715</button>' +
      "  <h4></h4><p></p>" +
      '  <div class="tuto-actions">' +
      '    <div class="tuto-dots"></div>' +
      '    <div class="tuto-btns">' +
      '      <button class="tuto-btn" id="tuto-prev" type="button">\u2190 Pr\u00e9c\u00e9dent</button>' +
      '      <button class="tuto-btn primary" id="tuto-next" type="button">Suivant \u2192</button>' +
      "    </div>" +
      "  </div>" +
      "</div>";
    document.body.appendChild(overlay);

    mask = overlay.querySelector("#tuto-mask");
    spot = overlay.querySelector("#tuto-spot");
    bubble = overlay.querySelector("#tuto-bubble");

    overlay.querySelector("#tuto-skip").addEventListener("click", finish);
    overlay.querySelector("#tuto-prev").addEventListener("click", function () {
      go(-1);
    });
    overlay.querySelector("#tuto-next").addEventListener("click", function () {
      go(1);
    });

    var dotsHost = overlay.querySelector(".tuto-dots");
    STEPS.forEach(function (_, i) {
      var d = document.createElement("span");
      d.className = "tuto-dot";
      d.dataset.i = i;
      dotsHost.appendChild(d);
    });

    window.addEventListener("resize", renderStep);
    window.addEventListener("scroll", renderStep, true);
  }

  function go(delta) {
    var next = currentStep + delta;
    if (next < 0) return;
    if (next >= STEPS.length) return finish();
    currentStep = next;
    var step = STEPS[currentStep];
    if (step.onEnter) {
      step.onEnter(function () {
        renderStep();
      });
    } else {
      renderStep();
    }
  }

  function finish() {
    try {
      localStorage.setItem(STORAGE_KEY, "true");
    } catch (e) {}
    if (overlay) {
      overlay.classList.remove("visible");
      setTimeout(function () {
        if (overlay) overlay.remove();
        overlay = null;
      }, 350);
    }
    window.removeEventListener("resize", renderStep);
    window.removeEventListener("scroll", renderStep, true);
  }

  function renderStep() {
    if (!overlay) return;
    var step = STEPS[currentStep];
    bubble.querySelector("h4").textContent = step.title;
    bubble.querySelector("p").textContent = step.text;

    overlay.querySelectorAll(".tuto-dot").forEach(function (d, i) {
      d.classList.toggle("active", i === currentStep);
    });

    var prev = overlay.querySelector("#tuto-prev");
    prev.disabled = currentStep === 0;
    var nextBtn = overlay.querySelector("#tuto-next");
    var isLast = currentStep === STEPS.length - 1;
    nextBtn.textContent = isLast ? (step.finalLabel || "Compris !") : "Suivant \u2192";

    var target = step.getTarget ? step.getTarget() : null;

    if (!target) {
      mask.style.clipPath = "none";
      spot.classList.add("hidden");
      bubble.classList.add("center");
      bubble.style.left = "";
      bubble.style.top = "";
      return;
    }

    bubble.classList.remove("center");

    var r = target.getBoundingClientRect();
    if (r.top < 0 || r.bottom > window.innerHeight) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(function () {
        positionSpotlight(target);
      }, 400);
      return;
    }

    positionSpotlight(target);
  }

  function positionSpotlight(target) {
    if (!overlay) return;
    var r = target.getBoundingClientRect();
    var pad = 8;
    var x = r.left - pad;
    var y = r.top - pad;
    var w = r.width + pad * 2;
    var h = r.height + pad * 2;

    var W = window.innerWidth;
    var H = window.innerHeight;
    mask.style.clipPath =
      "polygon(0 0, 100% 0, 100% 100%, 0 100%, 0 " +
      y + "px, " + x + "px " + y + "px, " +
      x + "px " + (y + h) + "px, " +
      (x + w) + "px " + (y + h) + "px, " +
      (x + w) + "px " + y + "px, 0 " + y + "px)";

    spot.classList.remove("hidden");
    spot.style.left = x + "px";
    spot.style.top = y + "px";
    spot.style.width = w + "px";
    spot.style.height = h + "px";

    var bw = Math.min(320, W - 32);
    bubble.style.maxWidth = bw + "px";
    var bh = bubble.offsetHeight || 180;
    var bx, by;
    var spaceBelow = H - (y + h);
    var spaceAbove = y;

    if (spaceBelow > bh + 20) {
      by = y + h + 12;
      bx = Math.min(Math.max(8, r.left + r.width / 2 - bw / 2), W - bw - 8);
    } else if (spaceAbove > bh + 20) {
      by = y - bh - 12;
      bx = Math.min(Math.max(8, r.left + r.width / 2 - bw / 2), W - bw - 8);
    } else {
      by = Math.min(Math.max(8, r.top + r.height / 2 - bh / 2), H - bh - 8);
      bx =
        r.left > W / 2
          ? Math.max(8, x - bw - 12)
          : Math.min(W - bw - 8, x + w + 12);
    }
    bubble.style.left = bx + "px";
    bubble.style.top = by + "px";
  }

  function start() {
    if (document.getElementById("tuto-overlay")) return;
    currentStep = 0;
    buildDom();
    var step = STEPS[0];
    if (step.onEnter) {
      step.onEnter(function () {
        requestAnimationFrame(function () {
          overlay.classList.add("visible");
          renderStep();
        });
      });
    } else {
      requestAnimationFrame(function () {
        overlay.classList.add("visible");
        renderStep();
      });
    }
  }

  function initTutoSeance(opts) {
    opts = opts || {};
    if (!opts.force) {
      try {
        if (localStorage.getItem(STORAGE_KEY) === "true") return;
      } catch (e) {
        return;
      }
    }
    // Don't run if welcome tutorial hasn't been seen (it takes priority)
    try {
      if (localStorage.getItem("tutoSeen") !== "true") return;
    } catch (e) {
      return;
    }
    // Don't run if another overlay is active
    if (document.getElementById("tuto-overlay")) return;
    // Wait for Alpine to render components
    setTimeout(start, 800);
  }

  window.initTutoSeance = initTutoSeance;
  window.replayTutoSeance = function () {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
    if (document.getElementById("tuto-overlay")) return;
    start();
  };
})();
