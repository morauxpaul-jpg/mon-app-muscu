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

  // Qui attend l'issue d'un envoi (seance.js), par id. En mémoire seulement :
  // la donnée, elle, est dans localStorage.
  var _attentes = {};

  function attendre(id, resolve) {
    (_attentes[id] = _attentes[id] || []).push(resolve);
  }

  // Rend la main à ceux qui attendaient cet envoi. Vrai s'il y en avait.
  function repondre(id, issue) {
    var liste = _attentes[id];
    delete _attentes[id];
    (liste || []).forEach(function (r) { r(issue); });
    return !!(liste && liste.length);
  }

  // `options.json` : l'envoi veut la réponse JSON du serveur (record,
  // volume…), comme l'envoi direct de « Série faite ».
  function enqueue(url, formData, cle, options) {
    var data = {};
    formData.forEach(function (val, key) {
      data[key] = val;
    });
    var id = Date.now() + "-" + Math.random().toString(36).slice(2, 8);
    var q = getQueue();
    if (cle) {
      q = q.filter(function (it) {
        var remplace = it.cle === cle && it.id !== _enVol;
        // Qui attendait l'ancien état attend désormais le nouveau.
        if (remplace && _attentes[it.id]) {
          _attentes[id] = (_attentes[id] || []).concat(_attentes[it.id]);
          delete _attentes[it.id];
        }
        return !remplace;
      });
    }
    var item = { id: id, url: url, data: data, ts: Date.now(), cle: cle || null, essais: 0 };
    if (options && options.json) item.json = true;
    q.push(item);
    saveQueue(q);
    updateBadge();
    return id;
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
  // Chaque série passe par la file : le badge n'apparaît que si un envoi
  // a vraiment échoué (ou hors ligne), pas pendant la seconde où il part.
  function updateBadge() {
    var q = getQueue();
    var existing = document.getElementById("offline-badge");
    var enRetard = q.filter(function (it) { return !it.json || it.essais > 0; }).length;
    if (q.length === 0 || (navigator.onLine && enRetard === 0)) {
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
  // suite, et on réessaie tout seul un peu plus tard (3 s, 6 s… 30 s) :
  // avant, la file n'attendait que le prochain chargement de page.
  var _sync = null;          // la synchronisation en cours (une seule à la fois)
  var DELAI_REJEU = 8000;
  var _echecs = 0;           // échecs réseau d'affilée
  var _relance = null;
  var _ecouteurs = [];       // seance.js : une série arrivée après coup

  function relancerPlusTard() {
    if (_relance || !navigator.onLine || getQueue().length === 0) return;
    _echecs++;
    var delai = Math.min(30000, 3000 * Math.pow(2, _echecs - 1));
    _relance = setTimeout(function () { _relance = null; syncQueue(); }, delai);
  }

  function annoncer(r) {
    _ecouteurs.forEach(function (fn) { try { fn(r); } catch (e) {} });
  }

  function syncQueue() {
    // Déjà en cours : on attend la même (« Terminer » doit savoir quand
    // elle finit), sans envoyer deux fois.
    if (_sync) return _sync;
    if (getQueue().length === 0) return Promise.resolve(0);
    var synced = 0;
    var panne = false;       // réseau ou serveur en défaut : on réessaiera
    var auth = false;        // session expirée : on attend une reconnexion

    function retirer(id) {
      saveQueue(getQueue().filter(function (it) { return it.id !== id; }));
    }
    function restePour(cle) {
      return cle ? getQueue().filter(function (it) { return it.cle === cle; }).length : 0;
    }
    // Un envoi qui a échoué alors qu'un état plus récent du même exercice
    // attend derrière lui : inutile de le rejouer, le plus récent le contient.
    function compterEssai(item) {
      var q = getQueue();
      var depasse = item.cle && q.some(function (it) { return it.cle === item.cle && it.id !== item.id; });
      if (depasse) q = q.filter(function (it) { return it.id !== item.id; });
      // L'échec compte pour ce qui reste de l'exercice (badge « en attente »).
      q.forEach(function (it) {
        if (it.id === item.id || (depasse && it.cle === item.cle)) it.essais = (it.essais || 0) + 1;
      });
      saveQueue(q);
    }
    // Plus rien ne part dans ce tour : ceux qui attendaient l'apprennent
    // (« Gardé sur l'appareil »). Leur envoi reste en file.
    function enAttente() {
      getQueue().forEach(function (it) { repondre(it.id, { statut: "reseau" }); });
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
      var entetes = { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": jeton };
      if (item.json) entetes.Accept = "application/json";
      // Délai : au sous-sol, le téléphone se croit en ligne et la requête ne
      // revient jamais. Sans lui, le rejeu restait pendu — et « Terminer »,
      // qui l'attend, restait figé sur « Enregistrement… » (audit du 03/10,
      // I3). Abandonné, l'envoi reste en tête de file pour la prochaine fois.
      var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
      var minuterie = ctrl ? setTimeout(function () { ctrl.abort(); }, DELAI_REJEU) : null;
      return fetch(item.url, {
        method: "POST",
        body: new URLSearchParams(data),
        headers: entetes,
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
        var lu = item.json && resp.json
          ? resp.json().catch(function () { return null; })
          : Promise.resolve(null);
        return lu.then(function (d) {
          if (!resp.ok && !resp.redirected) {
            // Refus définitif (données refusées, et non réseau, session ou
            // quota) : il bloquait toute la file derrière lui. On le met de
            // côté — gardé, pas jeté — et on continue.
            var s = resp.status;
            if (s >= 400 && s < 500 && [401, 403, 408, 429].indexOf(s) < 0) {
              mettreDeCote(item, item.json);
              retirer(item.id);
              var refus = { cle: item.cle, url: item.url, statut: "refus", d: d || {} };
              refus.attendu = repondre(item.id, refus);
              annoncer(refus);
              updateBadge();
              return step();
            }
            throw new Error("http " + s);
          }
          retirer(item.id);
          var ok = { cle: item.cle, url: item.url, statut: "ok", d: d || {}, reste: restePour(item.cle) };
          ok.attendu = repondre(item.id, ok);
          // Le toast « tout est à jour » ne parle que du retard rattrapé :
          // une série envoyée dans la seconde n'a rien à annoncer.
          if (!ok.attendu) synced++;
          annoncer(ok);
          updateBadge();
          return step();
        });
      }, function (err) {
        if (minuterie) clearTimeout(minuterie);
        throw err;
      }).catch(function (err) {
        if (err && err.message === "auth") auth = true;
        else { panne = true; compterEssai(item); }
        throw err;
      });
    }

    _sync = step()
      .catch(function () {})
      .then(function () {
        _enVol = null;
        _sync = null;
        if (!panne) _echecs = 0;
        updateBadge();
        if (synced > 0) {
          showToast(synced + " série(s) enregistrée(s) — tout est à jour.", "ok");
        }
        var reste = getQueue().length > 0;
        // Une série tapée pendant la fin du tour : elle part maintenant.
        if (reste && !panne && !auth && navigator.onLine) {
          return syncQueue().then(function (n) { return synced + n; });
        }
        if (reste) enAttente();
        if (panne) relancerPlusTard();
        return synced;
      });
    return _sync;
  }

  // « Série faite » : gardée d'abord dans le téléphone, envoyée ensuite.
  // Le téléphone peut s'éteindre ou l'app être fermée juste après le tap :
  // la série est déjà dans la file, elle repartira au prochain lancement.
  // Résout {statut: "ok", d} | {statut: "reseau"} | {statut: "refus", d}.
  function envoyer(url, champs, cle) {
    var formData = { forEach: function (cb) { Object.keys(champs).forEach(function (k) { cb(champs[k], k); }); } };
    var id = enqueue(url, formData, cle, { json: true });
    var issue = new Promise(function (resolve) { attendre(id, resolve); });
    if (navigator.onLine) syncQueue();
    else repondre(id, { statut: "reseau" });
    return issue;
  }

  var REJET_KEY = "muscu_offline_rejets";
  // `discret` : la page qui a fait l'envoi affiche elle-même le refus.
  function mettreDeCote(item, discret) {
    try {
      var r = JSON.parse(localStorage.getItem(REJET_KEY) || "[]");
      r.push(item);
      localStorage.setItem(REJET_KEY, JSON.stringify(r.slice(-50)));
    } catch (e) {}
    if (!discret) showToast("Un envoi a été refusé par le serveur — il reste gardé sur l'appareil.", "warn");
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
    envoyer: envoyer,
    drop: drop,
    pending: function () { return getQueue().length; },
    // Une série de cet exercice attend-elle encore dans la file ?
    contient: function (cle) { return getQueue().some(function (it) { return it.cle === cle; }); },
    sync: syncQueue,
    // fn({cle, statut, d, attendu, reste}) à chaque envoi traité.
    surReponse: function (fn) { _ecouteurs.push(fn); },
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
  // Retour dans l'app (écran rallumé, app ramenée devant) : ce qui attend
  // repart tout de suite, sans attendre la prochaine tentative.
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && navigator.onLine && getQueue().length) {
      if (_relance) { clearTimeout(_relance); _relance = null; }
      syncQueue();
    }
  });
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
