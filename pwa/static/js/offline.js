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

  // `cle` (facultative) identifie ce qui est envoyé — un exercice d'une
  // séance. Un envoi plus récent pour la même clé REMPLACE l'ancien encore
  // en attente : l'enregistrement d'un exercice réécrit toutes ses séries,
  // donc rejouer un état périmé après le récent effacerait des séries.
  var _enVol = null;   // id de l'élément en cours d'envoi : on n'y touche pas

  function enqueue(url, formData, cle) {
    var data = {};
    formData.forEach(function (val, key) {
      data[key] = val;
    });
    var q = getQueue();
    if (cle) {
      q = q.filter(function (it) { return it.cle !== cle || it.id === _enVol; });
    }
    q.push({ id: Date.now() + "-" + Math.random().toString(36).slice(2, 8),
             url: url, data: data, ts: Date.now(), cle: cle || null });
    saveQueue(q);
    updateBadge();
  }

  // Un envoi direct a réussi pour cette clé : ce qui attendait pour elle est
  // plus ancien, le rejouer écraserait l'état que le serveur vient de recevoir.
  function drop(cle) {
    if (!cle) return;
    saveQueue(getQueue().filter(function (it) { return it.cle !== cle || it.id === _enVol; }));
    updateBadge();
  }

  function csrfCourant() {
    var m = document.querySelector && document.querySelector('meta[name="csrf-token"]');
    return (m && m.getAttribute("content")) || "";
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
    existing.textContent = q.length + " envoi(s) en attente";
    existing.title = "Enregistrées sur l'appareil, elles partiront au retour du réseau.";
  }

  // ── Synchronisation ───────────────────────────────────────
  // SÉQUENTIELLE et dans l'ordre de saisie : deux enregistrements du même
  // exercice rejoués en parallèle laissaient gagner le plus rapide, pas le
  // plus récent. On s'arrête au premier échec pour ne pas désordonner la
  // suite (le reste repartira au prochain retour de réseau).
  var _syncing = false;
  var DELAI_REJEU = 8000;

  function syncQueue() {
    if (_syncing) return Promise.resolve(0);
    if (getQueue().length === 0) return Promise.resolve(0);
    _syncing = true;
    var synced = 0;

    function retirer(id) {
      saveQueue(getQueue().filter(function (it) { return it.id !== id; }));
    }

    function step() {
      var queue = getQueue();
      if (!queue.length) return Promise.resolve();
      var item = queue[0];
      _enVol = item.id;
      // Le jeton CSRF gardé avec l'envoi a pu changer (reconnexion entre-
      // temps) : le serveur répondait 400 et la tête de file restait bloquée
      // pour toujours. On rejoue avec le jeton de la page actuelle.
      var data = Object.assign({}, item.data);
      var jeton = csrfCourant();
      if (jeton) data._csrf = jeton;
      // Délai : au sous-sol, le téléphone se croit en ligne et la requête ne
      // revient jamais. Sans lui, le rejeu restait pendu — et « Terminer »,
      // qui l'attend, restait figé sur « Enregistrement… » (audit du 03/10,
      // I3). Abandonné, l'envoi reste en tête de file pour la prochaine fois.
      var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
      var minuterie = ctrl ? setTimeout(function () { ctrl.abort(); }, DELAI_REJEU) : null;
      return fetch(item.url, {
        method: "POST",
        body: new URLSearchParams(data),
        headers: { "Content-Type": "application/x-www-form-urlencoded",
                   "X-CSRFToken": jeton },
        credentials: "same-origin",
        redirect: "follow",
        signal: ctrl ? ctrl.signal : undefined,
      }).then(function (resp) {
        if (minuterie) clearTimeout(minuterie);
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
        if (!resp.ok && !resp.redirected) {
          // Refus définitif (données refusées, et non réseau, session ou
          // quota) : il bloquait toute la file derrière lui. On le met de
          // côté — gardé, pas jeté — et on continue.
          var s = resp.status;
          if (s >= 400 && s < 500 && [401, 403, 408, 429].indexOf(s) < 0) {
            mettreDeCote(item);
            retirer(item.id);
            updateBadge();
            return step();
          }
          throw new Error("http " + s);
        }
        synced++;
        retirer(item.id);
        updateBadge();
        return step();
      });
    }

    return step()
      .catch(function () {})
      .then(function () {
        _enVol = null;
        _syncing = false;
        updateBadge();
        if (synced > 0) {
          showToast(synced + " série(s) enregistrée(s) — tout est à jour.", "ok");
        }
        return synced;
      });
  }

  var REJET_KEY = "muscu_offline_rejets";
  function mettreDeCote(item) {
    try {
      var r = JSON.parse(localStorage.getItem(REJET_KEY) || "[]");
      r.push(item);
      localStorage.setItem(REJET_KEY, JSON.stringify(r.slice(-50)));
    } catch (e) {}
    showToast("Un envoi a été refusé par le serveur — il reste gardé sur l'appareil.", "warn");
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

  // Se déconnecter avec des séries encore en file les effaçait sans un mot.
  // Premier appui : on prévient et on arrête. Second appui (dans les 8 s) :
  // l'utilisateur a choisi, on purge et on part.
  var _logoutArme = 0;
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || (form.getAttribute("action") || "") !== "/logout") return;
    var n = getQueue().length;
    if (n > 0 && Date.now() - _logoutArme > 8000) {
      e.preventDefault();
      _logoutArme = Date.now();
      showToast(n + " envoi(s) pas encore parti(s) : ils seront perdus. " +
                "Reconnecte le réseau d'abord, ou touche encore « Déconnexion ».", "warn");
      return;
    }
    // On laisse le POST partir mais on purge d'abord (synchrone pour localStorage,
    // best-effort pour le cache async qui aura le temps de s'exécuter).
    purgeOnLogout();
  }, true);

  // ── API publique ──────────────────────────────────────────
  // seance.js met lui-même en file quand il est hors ligne, pour pouvoir
  // mettre la carte à jour immédiatement. Sans ça l'utilisateur n'avait
  // AUCUN retour : la série semblait perdue, et il la ressaisissait.
  window.OfflineQueue = {
    enqueue: function (url, formData, cle) { enqueue(url, formData, cle); },
    drop: drop,
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
    // Une fois par jour, ou quand la liste change (planning modifié) : la
    // semaine entière, c'est jusqu'à quinze pages à rendre côté serveur.
    var cle = new Date().toDateString() + "|" + urls.join(",");
    var deja = null;
    try { deja = localStorage.getItem("pack_horsligne"); } catch (e) {}
    if (deja === cle) { afficherPackPret(); return; }
    navigator.serviceWorker.ready
      .then(function (reg) {
        if (!reg.active) return;
        // Le service worker répond quand tout est gardé : on l'annonce.
        var canal = new MessageChannel();
        canal.port1.onmessage = function (ev) {
          var r = ev.data || {};
          if (r.ok && r.ok === r.total) {
            try { localStorage.setItem("pack_horsligne", cle); } catch (e) {}
            afficherPackPret();
          }
        };
        reg.active.postMessage({ type: "PRECACHE", urls: urls }, [canal.port2]);
      })
      .catch(function () {});
  }

  function afficherPackPret() {
    var p = document.getElementById("pack-horsligne");
    if (p) p.hidden = false;
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
