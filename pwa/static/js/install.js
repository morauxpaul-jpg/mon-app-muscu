/**
 * Expérience d'installation PWA pro — détection plateforme + bon comportement.
 *
 * - Android / Chrome desktop : bouton « Installer » → boîte d'installation
 *   native en 1 tap (via l'événement beforeinstallprompt capturé tôt en <head>).
 * - iPhone / iPad (Safari) : Apple n'expose AUCUNE API d'installation → on
 *   ouvre un guide visuel (Partager → Sur l'écran d'accueil).
 * - Déjà installée (mode standalone) : bouton « Ouvrir l'app ».
 *
 * Aucune dépendance (la landing ne charge pas Alpine).
 */
(function () {
  "use strict";

  var ua = navigator.userAgent || navigator.vendor || "";
  var isIOS =
    /iphone|ipad|ipod/i.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var isAndroid = /android/i.test(ua);
  var isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  // Safari iOS (pas Chrome/Firefox iOS, qui ne savent pas installer)
  var isIOSSafari = isIOS && !/crios|fxios|edgios/i.test(ua);

  var btn = document.getElementById("install-btn");
  var label = document.getElementById("install-btn-label");
  if (!btn) return;

  // ── Déjà installée : le bouton ouvre l'app ──────────────────────
  if (isStandalone) {
    if (label) label.textContent = "Ouvrir l'application";
    btn.addEventListener("click", function () {
      window.location.href = "/accueil";
    });
    return;
  }

  // ── Android / desktop : prompt natif si disponible ──────────────
  function tryNativePrompt() {
    var dp = window.__deferredInstallPrompt;
    if (!dp) return false;
    dp.prompt();
    dp.userChoice.then(function (choice) {
      if (choice && choice.outcome === "accepted") {
        hideButton();
      }
      window.__deferredInstallPrompt = null;
    });
    return true;
  }

  // Quand l'événement arrive après le chargement, on (re)active le bouton.
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    window.__deferredInstallPrompt = e;
    btn.removeAttribute("disabled");
  });

  // Installée avec succès → on retire le bouton.
  window.addEventListener("appinstalled", function () {
    hideButton();
    try { localStorage.setItem("pwa_installed", "1"); } catch (e) {}
  });

  function hideButton() {
    btn.style.display = "none";
  }

  // ── Clic principal ──────────────────────────────────────────────
  btn.addEventListener("click", function () {
    if (tryNativePrompt()) return;        // Android / Chrome desktop
    if (isIOSSafari) { showIOSGuide(); return; }
    if (isIOS) { showIOSChromeNote(); return; }  // iOS hors Safari
    // Android sans event (déjà refusé, ou critères PWA non encore réunis) :
    showAndroidFallback();
  });

  // ── Guide iOS (Safari) ──────────────────────────────────────────
  function overlay(innerHTML) {
    var o = document.createElement("div");
    o.className = "install-overlay";
    o.innerHTML =
      '<div class="install-sheet" role="dialog" aria-modal="true">' +
      '<button class="install-close" aria-label="Fermer">&times;</button>' +
      innerHTML +
      "</div>";
    o.addEventListener("click", function (e) {
      if (e.target === o || e.target.classList.contains("install-close")) o.remove();
    });
    document.body.appendChild(o);
    return o;
  }

  function showIOSGuide() {
    overlay(
      '<h3 class="install-h">Installer sur iPhone</h3>' +
      '<p class="install-p">En 2 étapes, depuis Safari :</p>' +
      '<ol class="install-steps">' +
        '<li><span class="install-num">1</span><div>Appuie sur <strong>Partager</strong>' +
          '<span class="install-share-ic" aria-hidden="true">' +
            '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 12v7a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-7"/></svg>' +
          "</span> dans la barre du bas.</div></li>" +
        '<li><span class="install-num">2</span><div>Choisis <strong>« Sur l\'écran d\'accueil »</strong>' +
          '<span class="install-plus-ic" aria-hidden="true">' +
            '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="4"/><path d="M12 8v8"/><path d="M8 12h8"/></svg>' +
          "</span> puis <strong>Ajouter</strong>.</div></li>" +
      "</ol>" +
      '<p class="install-hint">L\'icône Muscu Tracker apparaîtra sur ton écran d\'accueil, comme une vraie app.</p>' +
      '<div class="install-arrow" aria-hidden="true">▼</div>'
    );
  }

  function showIOSChromeNote() {
    overlay(
      '<h3 class="install-h">Ouvre cette page dans Safari</h3>' +
      '<p class="install-p">Sur iPhone, l\'installation se fait depuis <strong>Safari</strong>. ' +
      "Ouvre cette adresse dans Safari, puis appuie de nouveau sur « Installer l'app ».</p>"
    );
  }

  function showAndroidFallback() {
    overlay(
      '<h3 class="install-h">Installer l\'application</h3>' +
      '<p class="install-p">Ouvre le menu <strong>⋮</strong> de ton navigateur ' +
      "(en haut à droite) puis choisis <strong>« Installer l\'application »</strong> " +
      "ou <strong>« Ajouter à l\'écran d\'accueil »</strong>.</p>"
    );
  }
})();
