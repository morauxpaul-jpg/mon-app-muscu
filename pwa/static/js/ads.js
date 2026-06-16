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

  // ── Bandeau bas de page ──────────────────────────────────────────
  // Le bandeau natif est un OVERLAY collé en bas qui recouvre la webview et
  // PERSISTE entre les pages (navigation = rechargement, mais l'overlay reste).
  // Pour éviter tout saut de layout, l'espace est réservé AVANT le rendu par un
  // script inline dans <head> (base.html : html.has-ad-banner + --ad-banner-h).
  // Ici on ne fait qu'afficher/cacher le bandeau réel, SANS le recréer entre
  // deux pages à pub (sinon il clignote / disparaît).
  var BANNER_PAGES = ["/accueil", "/progres", "/plus"];
  var BANNER_H = 60; // hauteur réservée (dp), ≥ bandeau adaptatif
  var ACTIVE_KEY = "ads_banner_active";

  function reserve(on) {
    document.documentElement.style.setProperty("--ad-banner-h", (on ? BANNER_H : 0) + "px");
    document.documentElement.classList.toggle("has-ad-banner", !!on);
  }
  function isActive() { try { return sessionStorage.getItem(ACTIVE_KEY) === "1"; } catch (e) { return false; } }
  function setActive(v) { try { v ? sessionStorage.setItem(ACTIVE_KEY, "1") : sessionStorage.removeItem(ACTIVE_KEY); } catch (e) {} }

  function showBanner() {
    reserve(true);
    if (isActive()) {
      // Déjà affiché et persistant entre les pages → juste s'assurer qu'il est
      // visible, sans le recréer (évite le clignotement).
      initDone.then(function () { return AdMob.resumeBanner(); }).catch(function () {});
      return;
    }
    setActive(true);
    initDone
      .then(function () {
        return AdMob.showBanner({
          adId: CONF.banner,
          adSize: "ADAPTIVE_BANNER",
          position: "BOTTOM_CENTER",
        });
      })
      .catch(function () { setActive(false); reserve(false); });
  }

  function hideBanner() {
    // Pages sans pub (ex. séance) : le bandeau natif persiste sinon → on le cache.
    reserve(false);
    if (!isActive()) return;
    setActive(false);
    initDone.then(function () { return AdMob.hideBanner(); }).catch(function () {});
  }

  if (BANNER_PAGES.indexOf(location.pathname) !== -1) {
    showBanner();
  } else {
    hideBanner();
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
