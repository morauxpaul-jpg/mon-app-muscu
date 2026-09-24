/**
 * Mode Offline — gestion de la file d'attente et synchronisation.
 *
 * Quand l'app est hors-ligne :
 * - Affiche un bandeau "Mode hors-ligne"
 * - Intercepte les soumissions de formulaires de séance
 * - Stocke les données dans localStorage
 * - Quand la connexion revient, POST les données et affiche un toast
 */
(function () {
  "use strict";

  var QUEUE_KEY = "muscu_offline_queue";
  var banner = null;

  // ── Bandeau offline ──────────────────────────────────────
  function createBanner() {
    if (banner) return;
    banner = document.createElement("div");
    banner.id = "offline-banner";
    banner.textContent = "Hors ligne — tu peux continuer, tout est gardé sur l'appareil.";
    banner.style.cssText =
      "position:fixed;top:0;left:0;right:0;z-index:10000;padding:8px 16px;" +
      "background:rgba(255,159,10,0.95);color:#0a0a1a;text-align:center;" +
      "font-size:0.8rem;font-weight:700;letter-spacing:0.5px;" +
      "box-shadow:0 2px 12px rgba(255,159,10,0.4);";
    document.body.appendChild(banner);
    // Décale le contenu
    document.body.style.paddingTop = "36px";
  }

  function removeBanner() {
    if (!banner) return;
    banner.remove();
    banner = null;
    document.body.style.paddingTop = "";
  }

  function updateStatus() {
    if (navigator.onLine) {
      removeBanner();
      syncQueue();
    } else {
      createBanner();
    }
    updateBadge();
  }

  // ── File d'attente localStorage ───────────────────────────
  function getQueue() {
    try {
      return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
    } catch (e) {
      return [];
    }
  }

  function saveQueue(q) {
    try {
      localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
    } catch (e) {}
  }

  function enqueue(url, formData) {
    var data = {};
    formData.forEach(function (val, key) {
      data[key] = val;
    });
    var q = getQueue();
    q.push({ url: url, data: data, ts: Date.now() });
    saveQueue(q);
    updateBadge();
  }

  // ── Badge "en attente de sync" ────────────────────────────
  function updateBadge() {
    var q = getQueue();
    var existing = document.getElementById("offline-badge");
    if (q.length === 0) {
      if (existing) existing.remove();
      return;
    }
    if (!existing) {
      existing = document.createElement("div");
      existing.id = "offline-badge";
      existing.style.cssText =
        "position:fixed;bottom:70px;right:12px;z-index:9999;" +
        "background:rgba(255,159,10,0.9);color:#0a0a1a;border-radius:20px;" +
        "padding:6px 12px;font-size:0.75rem;font-weight:700;" +
        "box-shadow:0 2px 12px rgba(255,159,10,0.5);";
      document.body.appendChild(existing);
    }
    existing.textContent = q.length + " série(s) à envoyer";
    existing.title = "Enregistrées sur l'appareil, elles partiront au retour du réseau.";
  }

  // ── Synchronisation ───────────────────────────────────────
  // SÉQUENTIELLE et dans l'ordre de saisie : deux enregistrements du même
  // exercice rejoués en parallèle laissaient gagner le plus rapide, pas le
  // plus récent. On s'arrête au premier échec pour ne pas désordonner la
  // suite (le reste repartira au prochain retour de réseau).
  var _syncing = false;

  function syncQueue() {
    if (_syncing) return Promise.resolve(0);
    if (getQueue().length === 0) return Promise.resolve(0);
    _syncing = true;
    var synced = 0;

    function step() {
      var queue = getQueue();
      if (!queue.length) return Promise.resolve();
      var item = queue[0];
      return fetch(item.url, {
        method: "POST",
        body: new URLSearchParams(item.data),
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        credentials: "same-origin",
        redirect: "follow",
      }).then(function (resp) {
        // Une redirection vers la landing ou le login = session expirée :
        // la donnée n'a PAS été enregistrée — on la garde dans la file.
        var landedOnAuth = false;
        try {
          var p = new URL(resp.url, window.location.origin).pathname;
          landedOnAuth = resp.redirected && (p === "/" || p === "/login");
        } catch (e) {}
        if (landedOnAuth) {
          showToast("Reconnecte-toi pour envoyer tes séries en attente.", "warn");
          throw new Error("auth");
        }
        if (!resp.ok && !resp.redirected) throw new Error("http " + resp.status);
        synced++;
        saveQueue(getQueue().slice(1));
        updateBadge();
        return step();
      });
    }

    return step()
      .catch(function () {})
      .then(function () {
        _syncing = false;
        updateBadge();
        if (synced > 0) {
          showToast(synced + " série(s) enregistrée(s) — tout est à jour.", "ok");
        }
        return synced;
      });
  }

  var TOAST_COLORS = {
    ok:   ["rgba(52,199,89,0.15)", "rgba(52,199,89,0.45)", "#4FCB8E"],
    warn: ["rgba(255,159,10,0.15)", "rgba(255,159,10,0.45)", "#FF9F0A"],
    info: ["rgba(120,200,255,0.12)", "rgba(120,200,255,0.40)", "#78c8ff"],
  };

  function showToast(msg, kind) {
    var c = TOAST_COLORS[kind] || TOAST_COLORS.info;
    var t = document.createElement("div");
    t.setAttribute("role", "status");
    t.setAttribute("aria-live", "polite");
    t.style.cssText =
      "position:fixed;left:16px;right:16px;bottom:calc(84px + env(safe-area-inset-bottom,0px));" +
      "margin:0 auto;max-width:420px;text-align:center;" +
      "background:" + c[0] + ";border:1px solid " + c[1] + ";color:" + c[2] + ";" +
      "padding:11px 18px;border-radius:12px;font-size:0.88rem;font-weight:500;" +
      "z-index:9999;backdrop-filter:blur(12px);";
    document.body.appendChild(t);
    // Le texte est posé APRÈS l'insertion : un lecteur d'écran n'annonce une
    // zone live que si elle existait déjà au moment où son contenu change.
    // Toast inséré texte compris = message muet pour la synthèse vocale.
    requestAnimationFrame(function () { t.textContent = msg; });
    setTimeout(function () { t.remove(); }, 4000);
  }
  window.showToast = showToast;

  // ── Interception des form POST quand offline ──────────────
  document.addEventListener("submit", function (e) {
    if (navigator.onLine) return; // online → laisser le navigateur faire
    if (e.defaultPrevented) return; // déjà pris en charge (cf. seance.js)
    var form = e.target;
    if (form.method.toLowerCase() !== "post") return;

    // Ne queue que les formulaires de séance (saisie)
    if ((form.action || "").indexOf("/seance") === -1) return;

    e.preventDefault();
    enqueue(form.action, new FormData(form));
    showToast("Gardé sur l'appareil — envoi au retour du réseau.", "warn");
    // Phase de BULLE (pas de capture) : le gestionnaire du formulaire lui-même
    // s'exécute avant nous. Sans ça, seance.js et cette interception mettaient
    // chacun la série en file — deux entrées pour un seul enregistrement.
  }, false);

  // ── Désactiver les liens vers pages serveur-only en offline ─
  function disableOfflineLinks() {
    if (navigator.onLine) return;
    document.querySelectorAll('a[href*="/progres"], a[href*="/programme"], a[href*="/gestion"]').forEach(function (a) {
      a.addEventListener("click", function (e) {
        if (!navigator.onLine) {
          e.preventDefault();
          showToast("📡 Cette page nécessite une connexion internet");
        }
      });
    });
  }

  // ── Purge du cache à la déconnexion ───────────────────────
  // Sur un appareil partagé, les pages perso (/accueil, /seance) restent
  // dans le Cache Storage du SW après logout. On les efface avant de partir,
  // + la file offline et les clés de session locales.
  function purgeOnLogout() {
    try {
      if (window.caches && caches.keys) {
        caches.keys().then(function (keys) {
          keys.filter(function (k) { return k.indexOf("muscu-pwa-") === 0; })
              .forEach(function (k) { caches.delete(k); });
        });
      }
    } catch (e) {}
    try {
      localStorage.removeItem(QUEUE_KEY);
      localStorage.removeItem("active_session");
      localStorage.removeItem("pending_changelog");
    } catch (e) {}
  }

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || (form.getAttribute("action") || "") !== "/logout") return;
    // On laisse le POST partir mais on purge d'abord (synchrone pour localStorage,
    // best-effort pour le cache async qui aura le temps de s'exécuter).
    purgeOnLogout();
  }, true);

  // ── API publique ──────────────────────────────────────────
  // seance.js met lui-même en file quand il est hors ligne, pour pouvoir
  // mettre la carte à jour immédiatement. Sans ça l'utilisateur n'avait
  // AUCUN retour : la série semblait perdue, et il la ressaisissait.
  window.OfflineQueue = {
    enqueue: function (url, formData) { enqueue(url, formData); },
    pending: function () { return getQueue().length; },
    sync: syncQueue,
  };

  // ── Pré-cache des séances du jour ─────────────────────────
  // L'accueil expose les URLs des séances planifiées (aujourd'hui + demain) ;
  // on demande au service worker de les garder pendant qu'il y a du réseau.
  // Sans ça, ouvrir sa séance au sous-sol renvoyait à l'accueil : l'URL
  // n'avait jamais été visitée, donc jamais mise en cache.
  function precacheSessions() {
    if (!navigator.onLine || !navigator.serviceWorker) return;
    var el = document.getElementById("precache-urls");
    if (!el) return;
    var urls;
    try { urls = JSON.parse(el.textContent || "[]"); } catch (e) { return; }
    if (!urls.length) return;
    navigator.serviceWorker.ready
      .then(function (reg) {
        if (reg.active) reg.active.postMessage({ type: "PRECACHE", urls: urls });
      })
      .catch(function () {});
  }

  // ── Init ──────────────────────────────────────────────────
  window.addEventListener("online", updateStatus);
  window.addEventListener("offline", updateStatus);
  // Au chargement
  function init() {
    updateStatus();
    disableOfflineLinks();
    precacheSessions();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
