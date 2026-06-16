/**
 * Pubs AdMob — actives UNIQUEMENT dans l'app native (Capacitor) ET pour les
 * comptes Free. Sur le web / la PWA installée : ce script ne fait rien
 * (window.Capacitor absent → return immédiat).
 *
 * Stratégie produit (volontairement discrète) :
 * - Bandeau : accueil, progrès et hub Plus seulement — jamais pendant la
 *   saisie de séance.
 * - Interstitiel (pub vidéo) : à l'arrivée sur l'accueil après « Terminer la
 *   séance », plafonné à 1 toutes les 4 h.
 *
 * Les IDs d'annonces viennent de window.__ADS__ (injecté par base.html pour
 * les non-VIP, valeurs depuis l'env Railway, défauts = IDs de TEST Google).
 */
(function () {
  "use strict";

  var CONF = window.__ADS__ || {};
  var C = window.Capacitor;
  if (!C || typeof C.isNativePlatform !== "function" || !C.isNativePlatform()) {
    return; // web / PWA : aucune pub
  }
  var AdMob = C.Plugins && C.Plugins.AdMob;
  if (!AdMob || !CONF.banner) return;

  var initDone = AdMob.initialize({}).catch(function () {});

  // ── Bandeau bas de page (au-dessus de la bottom-nav) ─────────────
  var BANNER_PAGES = ["/accueil", "/progres", "/plus"];

  function showBanner() {
    // Marge = hauteur RÉELLE de la bottom-nav (safe-area incluse) pour que le
    // bandeau se pose juste au-dessus, sans la recouvrir (fallback 64).
    var nav = document.querySelector(".bottom-nav");
    var navH = nav ? Math.round(nav.getBoundingClientRect().height) : 64;
    initDone
      .then(function () {
        return AdMob.showBanner({
          adId: CONF.banner,
          adSize: "ADAPTIVE_BANNER",
          position: "BOTTOM_CENTER",
          margin: navH,
        });
      })
      .then(function () {
        document.body.classList.add("has-ad-banner");
      })
      .catch(function () {});
  }

  if (BANNER_PAGES.indexOf(location.pathname) !== -1) {
    showBanner();
  }

  // ── Interstitiel de fin de séance (max 1 / 4 h) ──────────────────
  var INTERSTITIAL_CAP_MS = 4 * 60 * 60 * 1000;

  function interstitialAllowed() {
    try {
      var last = parseInt(localStorage.getItem("ads_last_interstitial") || "0", 10);
      return Date.now() - last > INTERSTITIAL_CAP_MS;
    } catch (e) {
      return true;
    }
  }

  // Au clic « Terminer la séance » : on pose un jalon, la pub s'affichera à
  // l'arrivée sur l'accueil (ne bloque jamais l'enregistrement de la séance).
  document.addEventListener(
    "submit",
    function (e) {
      var f = e.target;
      if (f && (f.getAttribute("action") || "").indexOf("/seance/finish") !== -1) {
        try { sessionStorage.setItem("ads_show_interstitial", "1"); } catch (e2) {}
      }
    },
    true
  );

  var pending = false;
  try { pending = sessionStorage.getItem("ads_show_interstitial") === "1"; } catch (e) {}
  if (pending && location.pathname === "/accueil") {
    try { sessionStorage.removeItem("ads_show_interstitial"); } catch (e) {}
    if (CONF.interstitial && interstitialAllowed()) {
      initDone
        .then(function () {
          return AdMob.prepareInterstitial({ adId: CONF.interstitial });
        })
        .then(function () {
          try { localStorage.setItem("ads_last_interstitial", String(Date.now())); } catch (e) {}
          return AdMob.showInterstitial();
        })
        .catch(function () {});
    }
  }
})();
