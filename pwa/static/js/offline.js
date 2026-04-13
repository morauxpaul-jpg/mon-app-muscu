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
    banner.innerHTML = '📡 Mode hors-ligne — les données seront synchronisées au retour du réseau';
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
    existing.textContent = "⏳ " + q.length + " action(s) en attente";
  }

  // ── Synchronisation ───────────────────────────────────────
  function syncQueue() {
    var q = getQueue();
    if (q.length === 0) return;

    var remaining = [];
    var synced = 0;
    var promises = q.map(function (item) {
      var fd = new FormData();
      Object.keys(item.data).forEach(function (k) {
        fd.append(k, item.data[k]);
      });
      return fetch(item.url, {
        method: "POST",
        body: new URLSearchParams(item.data),
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        redirect: "follow",
      })
        .then(function (resp) {
          if (resp.ok || resp.redirected) {
            synced++;
          } else {
            remaining.push(item);
          }
        })
        .catch(function () {
          remaining.push(item);
        });
    });

    Promise.all(promises).then(function () {
      saveQueue(remaining);
      updateBadge();
      if (synced > 0) {
        showToast("✅ " + synced + " donnée(s) synchronisée(s)");
      }
    });
  }

  function showToast(msg) {
    var t = document.createElement("div");
    t.textContent = msg;
    t.style.cssText =
      "position:fixed;top:16px;left:50%;transform:translateX(-50%);" +
      "background:rgba(0,255,127,0.15);border:1px solid rgba(0,255,127,0.4);" +
      "color:#00FF7F;padding:10px 20px;border-radius:12px;font-size:0.9rem;" +
      "z-index:9999;animation:slideIn 0.3s ease-out;";
    document.body.appendChild(t);
    setTimeout(function () {
      t.remove();
    }, 4000);
  }

  // ── Interception des form POST quand offline ──────────────
  document.addEventListener("submit", function (e) {
    if (navigator.onLine) return; // online → laisser le navigateur faire
    var form = e.target;
    if (form.method.toLowerCase() !== "post") return;

    // Ne queue que les formulaires de séance (saisie)
    var action = form.action || "";
    if (
      action.indexOf("/seance/") === -1 &&
      action.indexOf("/seance") === -1
    )
      return;

    e.preventDefault();
    var fd = new FormData(form);
    enqueue(action, fd);
    showToast("📡 Sauvegardé hors-ligne — sera synchronisé au retour du réseau");
  }, true);

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

  // ── Init ──────────────────────────────────────────────────
  window.addEventListener("online", updateStatus);
  window.addEventListener("offline", updateStatus);
  // Au chargement
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      updateStatus();
      disableOfflineLinks();
    });
  } else {
    updateStatus();
    disableOfflineLinks();
  }
})();
