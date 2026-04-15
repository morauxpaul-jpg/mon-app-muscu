(function () {
  "use strict";

  const STORAGE_KEY = "tutoSeen";

  const STEPS = [
    {
      target: '[data-tuto="welcome"]',
      title: "Bienvenue sur Muscu Tracker PRO",
      text: "Ce rapide tutoriel te montre les onglets de l'app. Tu ne le verras qu'une seule fois !",
      center: true,
    },
    {
      target: '[data-tuto="dashboard"]',
      title: "Ton tableau de bord",
      text: "Résumé de ta semaine, planning, stats et streak en un coup d'œil.",
    },
    {
      target: '[data-tuto="seance"]',
      title: "Logger une séance",
      text: "Choisis ta séance, remplis reps + poids. Un chrono de repos se lance entre les séries. Chaque exo a une fiche détaillée (onglet Table RM, mini-carte du corps, lien vers le coach).",
    },
    {
      target: '[data-tuto="progres"]',
      title: "Suis ta progression",
      text: "Graphiques, volume hebdo, carte anatomique du corps, table des maxima (RM) et calculateur 1RM.",
    },
    {
      target: '[data-tuto="plus"]',
      title: "Menu Plus",
      text: "Coach IA (historique sauvegardé), programme, nutrition, arcade, gestion et ce tutoriel depuis cet onglet.",
    },
    {
      target: null,
      title: "C'est parti !",
      text: "Tu connais l'essentiel. Bonne séance ! Retrouve ce tutoriel dans Plus si besoin.",
      center: true,
      finalLabel: "Commencer",
    },
  ];

  let currentStep = 0;
  let overlay, mask, spot, bubble;
  let activeSteps = STEPS;
  let onFinishCallback = null;

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
    activeSteps.forEach((_, i) => {
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
    if (next >= activeSteps.length) return finish();
    currentStep = next;
    renderStep();
  }

  function finish() {
    if (onFinishCallback) {
      try { onFinishCallback(); } catch (e) {}
    } else {
      try { localStorage.setItem(STORAGE_KEY, "true"); } catch (e) {}
    }
    if (overlay) {
      overlay.classList.remove("visible");
      setTimeout(() => { if (overlay) overlay.remove(); overlay = null; }, 350);
    }
    window.removeEventListener("resize", renderStep);
    window.removeEventListener("scroll", renderStep, true);
    activeSteps = STEPS;
    onFinishCallback = null;
  }

  function renderStep() {
    if (!overlay) return;
    const step = activeSteps[currentStep];
    bubble.querySelector("h4").textContent = step.title;
    bubble.querySelector("p").textContent = step.text;

    overlay.querySelectorAll(".tuto-dot").forEach((d, i) => {
      d.classList.toggle("active", i === currentStep);
    });

    const prev = overlay.querySelector("#tuto-prev");
    prev.disabled = currentStep === 0;
    const nextBtn = overlay.querySelector("#tuto-next");
    const isLast = currentStep === activeSteps.length - 1;
    nextBtn.textContent = isLast ? (step.finalLabel || "Commencer") : "Suivant →";

    const target = step.target ? document.querySelector(step.target) : null;

    if (step.center || !target) {
      mask.style.clipPath = "none";
      spot.classList.add("hidden");
      bubble.classList.add("center");
      bubble.style.left = "";
      bubble.style.top = "";
      return;
    }

    bubble.classList.remove("center");
    const r = target.getBoundingClientRect();
    if (r.top < 0 || r.bottom > window.innerHeight) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => positionSpotlight(target), 400);
      return;
    }
    positionSpotlight(target);
  }

  function positionSpotlight(target) {
    if (!overlay) return;
    const r = target.getBoundingClientRect();
    const pad = 8;
    const x = r.left - pad;
    const y = r.top - pad;
    const w = r.width + pad * 2;
    const h = r.height + pad * 2;

    const W = window.innerWidth;
    const H = window.innerHeight;
    mask.style.clipPath =
      `polygon(0 0, 100% 0, 100% 100%, 0 100%, 0 ${y}px, ${x}px ${y}px, ${x}px ${y + h}px, ${x + w}px ${y + h}px, ${x + w}px ${y}px, 0 ${y}px)`;

    spot.classList.remove("hidden");
    spot.style.left = x + "px";
    spot.style.top = y + "px";
    spot.style.width = w + "px";
    spot.style.height = h + "px";

    const bw = Math.min(320, W - 32);
    bubble.style.maxWidth = bw + "px";
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
    const p = location.pathname || "";
    if (p.startsWith("/onboarding") || p.startsWith("/login")) return;
    if (!document.querySelector(".bottom-nav")) return;

    activeSteps = STEPS;
    onFinishCallback = null;
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
    } else {
      start();
    }
  }

  // ── Démo d'une fonctionnalité (réutilise le spotlight) ──
  // Steps : [{ target: selector|null, title, text, center?: bool, finalLabel? }]
  function playFeatureDemo(steps, opts) {
    opts = opts || {};
    if (!Array.isArray(steps) || !steps.length) return;
    if (document.getElementById("tuto-overlay")) return;
    const filtered = steps.filter(function (s) {
      if (!s.target || s.center) return true;
      return !!document.querySelector(s.target);
    });
    if (!filtered.length) return;
    activeSteps = filtered;
    onFinishCallback = opts.onFinish || function () {};
    currentStep = 0;
    buildDom();
    requestAnimationFrame(() => {
      overlay.classList.add("visible");
      renderStep();
    });
  }

  // Au chargement : si une démo est en attente (patch notes), la lancer après un délai
  function checkPendingDemo() {
    let pending = null;
    try { pending = sessionStorage.getItem("pending_demo"); } catch (e) { return; }
    if (!pending) return;
    try { sessionStorage.removeItem("pending_demo"); } catch (e) {}
    let demo;
    try { demo = JSON.parse(pending); } catch (e) { return; }
    if (!demo || !demo.steps) return;
    // Si une url est spécifiée et qu'on n'y est pas → abandon
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
    activeSteps = STEPS;
    onFinishCallback = null;
    start();
  };
  window.playFeatureDemo = playFeatureDemo;
})();
