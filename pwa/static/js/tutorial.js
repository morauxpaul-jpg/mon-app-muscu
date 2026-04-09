(function () {
  "use strict";

  const STORAGE_KEY = "tutoSeen";

  const STEPS = [
    {
      target: '[data-tuto="welcome"]',
      title: "Bienvenue sur Muscu Tracker PRO 💪",
      text: "Ce rapide tutoriel va te montrer les fonctions clés de l'app. Tu ne le verras qu'une seule fois !",
      center: true,
    },
    {
      target: '[data-tuto="dashboard"]',
      title: "Ton tableau de bord",
      text: "Ici tu retrouves un résumé de tes performances, ta progression et tes stats récentes en un coup d'œil.",
    },
    {
      target: '[data-tuto="seance"]',
      title: "Logger une séance",
      text: "C'est ici que tu enregistres ta séance du jour : exercices, séries, charges. Fais-le juste après ton entraînement !",
    },
    {
      target: '[data-tuto="progres"]',
      title: "Suis ta progression",
      text: "Visualise l'évolution de tes charges et volumes sur chaque exercice, semaine après semaine.",
    },
    {
      target: '[data-tuto="programme"]',
      title: "Configure ton programme",
      text: "Définis tes jours d'entraînement, tes exercices et ta structure de programme pour personnaliser ton suivi.",
    },
    {
      target: '[data-tuto="arcade"]',
      title: "La section Arcade 🎮",
      text: "Un peu de fun entre deux séances ! Des mini-jeux intégrés pour pimenter ton expérience.",
    },
    {
      target: null,
      title: "C'est parti ! 🚀",
      text: "Tu connais maintenant l'essentiel. Bonne séance et bon courage ! Tu peux retrouver ce tutoriel dans les paramètres si besoin.",
      center: true,
      finalLabel: "Commencer",
    },
  ];

  let currentStep = 0;
  let overlay, mask, spot, bubble;

  function buildDom() {
    overlay = document.createElement("div");
    overlay.id = "tuto-overlay";
    overlay.innerHTML =
      '<div id="tuto-mask"></div>' +
      '<div id="tuto-spot" class="hidden"></div>' +
      '<div id="tuto-bubble">' +
      '  <button id="tuto-skip" type="button">Passer ✕</button>' +
      '  <h4></h4><p></p>' +
      '  <div class="tuto-actions">' +
      '    <div class="tuto-dots"></div>' +
      '    <div class="tuto-btns">' +
      '      <button class="tuto-btn" id="tuto-prev" type="button">← Précédent</button>' +
      '      <button class="tuto-btn primary" id="tuto-next" type="button">Suivant →</button>' +
      '    </div>' +
      '  </div>' +
      '</div>';
    document.body.appendChild(overlay);

    mask = overlay.querySelector("#tuto-mask");
    spot = overlay.querySelector("#tuto-spot");
    bubble = overlay.querySelector("#tuto-bubble");

    overlay.querySelector("#tuto-skip").addEventListener("click", finish);
    overlay.querySelector("#tuto-prev").addEventListener("click", () => go(-1));
    overlay.querySelector("#tuto-next").addEventListener("click", () => go(1));

    const dotsHost = overlay.querySelector(".tuto-dots");
    STEPS.forEach((_, i) => {
      const d = document.createElement("span");
      d.className = "tuto-dot";
      d.dataset.i = i;
      dotsHost.appendChild(d);
    });

    window.addEventListener("resize", renderStep);
    window.addEventListener("scroll", renderStep, true);
  }

  function go(delta) {
    const next = currentStep + delta;
    if (next < 0) return;
    if (next >= STEPS.length) return finish();
    currentStep = next;
    renderStep();
  }

  function finish() {
    try { localStorage.setItem(STORAGE_KEY, "true"); } catch (e) {}
    if (overlay) {
      overlay.classList.remove("visible");
      setTimeout(() => { if (overlay) overlay.remove(); overlay = null; }, 350);
    }
    window.removeEventListener("resize", renderStep);
    window.removeEventListener("scroll", renderStep, true);
  }

  function renderStep() {
    if (!overlay) return;
    const step = STEPS[currentStep];
    bubble.querySelector("h4").textContent = step.title;
    bubble.querySelector("p").textContent = step.text;

    overlay.querySelectorAll(".tuto-dot").forEach((d, i) => {
      d.classList.toggle("active", i === currentStep);
    });

    const prev = overlay.querySelector("#tuto-prev");
    prev.disabled = currentStep === 0;
    const nextBtn = overlay.querySelector("#tuto-next");
    const isLast = currentStep === STEPS.length - 1;
    nextBtn.textContent = isLast ? (step.finalLabel || "Commencer") : "Suivant →";

    const target = step.target ? document.querySelector(step.target) : null;

    if (step.center || !target) {
      // No spotlight: full mask, centered bubble
      mask.style.clipPath = "none";
      spot.classList.add("hidden");
      bubble.classList.add("center");
      bubble.style.left = "";
      bubble.style.top = "";
      return;
    }

    bubble.classList.remove("center");
    const r = target.getBoundingClientRect();
    const pad = 8;
    const x = r.left - pad;
    const y = r.top - pad;
    const w = r.width + pad * 2;
    const h = r.height + pad * 2;

    // Cut a hole in the mask using clip-path (evenodd via path)
    const W = window.innerWidth;
    const H = window.innerHeight;
    mask.style.clipPath =
      `polygon(0 0, 100% 0, 100% 100%, 0 100%, 0 ${y}px, ${x}px ${y}px, ${x}px ${y + h}px, ${x + w}px ${y + h}px, ${x + w}px ${y}px, 0 ${y}px)`;

    spot.classList.remove("hidden");
    spot.style.left = x + "px";
    spot.style.top = y + "px";
    spot.style.width = w + "px";
    spot.style.height = h + "px";

    // Position bubble
    const bw = Math.min(320, W - 32);
    bubble.style.maxWidth = bw + "px";
    // Measure after content set
    const bh = bubble.offsetHeight || 180;
    let bx, by;
    const spaceBelow = H - (y + h);
    const spaceAbove = y;

    if (spaceBelow > bh + 20) {
      by = y + h + 12;
      bx = Math.min(Math.max(8, r.left + r.width / 2 - bw / 2), W - bw - 8);
    } else if (spaceAbove > bh + 20) {
      by = y - bh - 12;
      bx = Math.min(Math.max(8, r.left + r.width / 2 - bw / 2), W - bw - 8);
    } else {
      // Side
      by = Math.min(Math.max(8, r.top + r.height / 2 - bh / 2), H - bh - 8);
      bx = (r.left > W / 2) ? Math.max(8, x - bw - 12) : Math.min(W - bw - 8, x + w + 12);
    }
    bubble.style.left = bx + "px";
    bubble.style.top = by + "px";
  }

  function start() {
    if (document.getElementById("tuto-overlay")) return;
    currentStep = 0;
    buildDom();
    requestAnimationFrame(() => {
      overlay.classList.add("visible");
      renderStep();
    });
  }

  function initTutorial(opts) {
    opts = opts || {};
    if (!opts.force) {
      try {
        if (localStorage.getItem(STORAGE_KEY) === "true") return;
      } catch (e) {}
    }
    // Ne pas lancer sur l'onboarding ou login
    const p = location.pathname || "";
    if (p.startsWith("/onboarding") || p.startsWith("/login")) return;
    // Doit avoir la nav (utilisateur connecté)
    if (!document.querySelector(".bottom-nav")) return;

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
    } else {
      start();
    }
  }

  window.initTutorial = initTutorial;
  window.replayTutorial = function () {
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
    start();
  };
})();
