/**
 * Moteur de tutoriel partagé (spotlight + bulle).
 * Une seule implémentation pour le tuto d'accueil ET le tuto de séance —
 * remplace la duplication entre tutorial.js et tuto-seance.js.
 *
 * API :
 *   TutoEngine.run(steps, { storageKey, onFinish, force })
 *
 * Chaque step : {
 *   target: string(selector) | function():Element | null,
 *   title, text,
 *   center?: bool,            // bulle centrée, pas de spotlight
 *   finalLabel?: string,      // libellé du bouton sur la dernière étape
 *   onEnter?: function(cb)    // hook async avant l'affichage (ex: déplier)
 * }
 */
(function () {
  "use strict";

  var NAV_SAFE = 76;   // hauteur bottom-nav + marge : la bulle ne passe jamais dessous
  var PAD = 10;        // marge autour de la cible surlignée
  var GAP = 14;        // espace entre la cible et la bulle

  var overlay, mask, spot, bubble, titleEl, textEl, dotsHost, prevBtn, nextBtn;
  var steps = [], idx = 0, opts = {}, repositionRAF = null;

  function h(tag, attrs, html) {
    var el = document.createElement(tag);
    if (attrs) for (var k in attrs) el.setAttribute(k, attrs[k]);
    if (html != null) el.innerHTML = html;
    return el;
  }

  function build() {
    overlay = h("div", { id: "tuto-overlay", role: "dialog", "aria-modal": "true" });
    mask = h("div", { id: "tuto-mask" });
    spot = h("div", { id: "tuto-spot", "class": "hidden" });
    bubble = h("div", { id: "tuto-bubble" });

    var skip = h("button", { id: "tuto-skip", type: "button", "aria-label": "Passer le tutoriel" }, "Passer ✕");
    titleEl = h("h4");
    textEl = h("p");
    var actions = h("div", { "class": "tuto-actions" });
    dotsHost = h("div", { "class": "tuto-dots" });
    var btns = h("div", { "class": "tuto-btns" });
    prevBtn = h("button", { id: "tuto-prev", type: "button", "class": "tuto-btn" }, "Précédent");
    nextBtn = h("button", { id: "tuto-next", type: "button", "class": "tuto-btn primary" }, "Suivant");

    btns.appendChild(prevBtn);
    btns.appendChild(nextBtn);
    actions.appendChild(dotsHost);
    actions.appendChild(btns);
    bubble.appendChild(skip);
    bubble.appendChild(titleEl);
    bubble.appendChild(textEl);
    bubble.appendChild(actions);

    overlay.appendChild(mask);
    overlay.appendChild(spot);
    overlay.appendChild(bubble);
    document.body.appendChild(overlay);

    skip.addEventListener("click", finish);
    prevBtn.addEventListener("click", function () { go(-1); });
    nextBtn.addEventListener("click", function () { go(1); });
    // Clic sur le voile (hors cible) = étape suivante, geste naturel.
    mask.addEventListener("click", function () { go(1); });

    steps.forEach(function (_, i) {
      var d = h("span", { "class": "tuto-dot" });
      dotsHost.appendChild(d);
    });

    window.addEventListener("resize", scheduleReposition);
    window.addEventListener("scroll", scheduleReposition, true);
  }

  function resolveTarget(step) {
    if (!step) return null;
    if (typeof step.getTarget === "function") return step.getTarget();
    if (typeof step.target === "function") return step.target();
    if (typeof step.target === "string") return document.querySelector(step.target);
    return null;
  }

  function go(delta) {
    var n = idx + delta;
    if (n < 0) return;
    if (n >= steps.length) return finish();
    idx = n;
    var step = steps[idx];
    if (step && typeof step.onEnter === "function") {
      step.onEnter(function () { render(); });
    } else {
      render();
    }
  }

  function finish() {
    if (typeof opts.onFinish === "function") {
      try { opts.onFinish(); } catch (e) {}
    } else if (opts.storageKey) {
      try { localStorage.setItem(opts.storageKey, "true"); } catch (e) {}
    }
    if (overlay) {
      overlay.classList.remove("visible");
      var o = overlay;
      setTimeout(function () { if (o && o.parentNode) o.parentNode.removeChild(o); }, 300);
      overlay = null;
    }
    window.removeEventListener("resize", scheduleReposition);
    window.removeEventListener("scroll", scheduleReposition, true);
  }

  function scheduleReposition() {
    if (repositionRAF) cancelAnimationFrame(repositionRAF);
    repositionRAF = requestAnimationFrame(function () { reposition(); });
  }

  function render() {
    if (!overlay) return;
    var step = steps[idx];
    titleEl.textContent = step.title || "";
    textEl.textContent = step.text || "";

    overlay.querySelectorAll(".tuto-dot").forEach(function (d, i) {
      d.classList.toggle("active", i === idx);
    });

    prevBtn.style.visibility = idx === 0 ? "hidden" : "visible";
    var isLast = idx === steps.length - 1;
    nextBtn.textContent = isLast ? (step.finalLabel || "Terminer") : "Suivant →";
    try { nextBtn.focus({ preventScroll: true }); } catch (e) {}

    var target = step.center ? null : resolveTarget(step);

    if (!target) {
      // Bulle centrée, pas de spotlight.
      mask.style.clipPath = "none";
      spot.classList.add("hidden");
      bubble.classList.add("center");
      bubble.style.left = "";
      bubble.style.top = "";
      bubble.style.maxWidth = "";
      return;
    }

    bubble.classList.remove("center");
    var r = target.getBoundingClientRect();
    var safeBottom = window.innerHeight - NAV_SAFE;
    // Si la cible n'est pas confortablement visible, on scrolle puis on place.
    if (r.top < 8 || r.bottom > safeBottom) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(function () { place(target); }, 380);
    } else {
      place(target);
    }
  }

  function reposition() {
    var step = steps[idx];
    if (!step || step.center) return;
    var target = resolveTarget(step);
    if (target) place(target);
  }

  function place(target) {
    if (!overlay) return;
    var r = target.getBoundingClientRect();
    var x = r.left - PAD;
    var y = r.top - PAD;
    var w = r.width + PAD * 2;
    var hgt = r.height + PAD * 2;
    var W = window.innerWidth;
    var H = window.innerHeight;
    var safeBottom = H - NAV_SAFE;

    // Découpe du voile pour révéler la cible.
    mask.style.clipPath =
      "polygon(0 0, 100% 0, 100% 100%, 0 100%, 0 " + y + "px, " +
      x + "px " + y + "px, " + x + "px " + (y + hgt) + "px, " +
      (x + w) + "px " + (y + hgt) + "px, " + (x + w) + "px " + y + "px, 0 " + y + "px)";

    spot.classList.remove("hidden");
    spot.style.left = x + "px";
    spot.style.top = y + "px";
    spot.style.width = w + "px";
    spot.style.height = hgt + "px";

    // Largeur de la bulle, puis mesure de la hauteur RÉELLE (texte déjà posé).
    var bw = Math.min(340, W - 24);
    bubble.style.maxWidth = bw + "px";
    bubble.style.left = "0px";
    bubble.style.top = "0px";
    // force un reflow pour obtenir offsetHeight correct
    var bh = bubble.offsetHeight || 160;

    var bx, by;
    var spaceBelow = safeBottom - (y + hgt);
    var spaceAbove = y - 8;

    if (spaceBelow >= bh + GAP) {
      // Sous la cible (cas le plus fréquent).
      by = y + hgt + GAP;
      bx = clamp(r.left + r.width / 2 - bw / 2, 8, W - bw - 8);
    } else if (spaceAbove >= bh + GAP) {
      // Au-dessus.
      by = y - bh - GAP;
      bx = clamp(r.left + r.width / 2 - bw / 2, 8, W - bw - 8);
    } else {
      // Pas la place ni dessus ni dessous : on place sur le côté opposé,
      // sans jamais chevaucher la cible, et clampé dans la zone sûre.
      by = clamp(r.top + r.height / 2 - bh / 2, 8, safeBottom - bh - 8);
      if (r.left > W / 2) {
        bx = Math.max(8, x - bw - GAP);          // à gauche de la cible
      } else {
        bx = Math.min(W - bw - 8, x + w + GAP);  // à droite de la cible
      }
    }
    bubble.style.left = Math.round(bx) + "px";
    bubble.style.top = Math.round(by) + "px";
  }

  function clamp(v, lo, hi) { return Math.min(Math.max(v, lo), hi); }

  function run(stepList, options) {
    if (document.getElementById("tuto-overlay")) return;
    if (!Array.isArray(stepList) || !stepList.length) return;
    steps = stepList;
    opts = options || {};
    idx = 0;
    build();
    var first = steps[0];
    var show = function () {
      requestAnimationFrame(function () {
        if (!overlay) return;
        overlay.classList.add("visible");
        render();
      });
    };
    if (first && typeof first.onEnter === "function") first.onEnter(show);
    else show();
  }

  window.TutoEngine = { run: run };
})();
