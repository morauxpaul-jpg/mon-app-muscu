// Service worker — Network First avec mise à jour automatique.
// IMPORTANT : incrémenter CACHE_VERSION à chaque déploiement pour forcer le refresh.
const CACHE_VERSION = "v89-2026-06-10-onboarding-submit-fix";
const CACHE = "muscu-pwa-" + CACHE_VERSION;

const APP_SHELL = [
  "/accueil",
  "/seance",
  "/static/css/tokens.css",
  "/static/css/theme.css",
  "/static/css/components.css",
  "/static/css/icons.css",
  "/static/css/glass.css",
  "/static/css/tutorial.css",
  "/static/img/icons.svg",
  "/static/js/sw-register.js",
  "/static/js/offline.js",
  "/static/js/alpine-sort.min.js",
  "/static/js/alpine.min.js",
  "/static/js/tuto-engine.js",
  "/static/js/tutorial.js",
  "/static/js/tuto-seance.js",
  "/static/js/ui-fx.js",
  "/static/js/prefetch.js",
  "/static/js/exercise-library.js",
  "/static/css/timer.css",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/changelog.json",
  "/manifest.json",
];

// ── Install : pré-cache du shell, activation immédiate ────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

// ── Activate : nettoie tous les anciens caches ────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("muscu-pwa-") && k !== CACHE)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Chrono de repos : notification planifiée côté SW ──────────────
// Le client poste { type: 'SCHEDULE_TIMER', delay, title, body } au début
// du repos. On arme un setTimeout dans le SW et on garde la promesse vivante
// via event.waitUntil pour que le SW ne soit pas tué pendant l'attente.
// À l'échéance : on n'affiche la notif QUE si aucune fenêtre n'est au premier
// plan (sinon la page gère elle-même le bip + l'affichage de la barre).
let _restTimeout = null;
let _restResolve = null;

function _clearRestTimer() {
  if (_restTimeout) {
    clearTimeout(_restTimeout);
    _restTimeout = null;
  }
  if (_restResolve) {
    // Résout la promesse waitUntil en attente pour libérer le SW proprement.
    _restResolve();
    _restResolve = null;
  }
}

// ── Message : skipWaiting + planification du chrono de repos ──
self.addEventListener("message", (event) => {
  const data = event.data;
  if (data === "SKIP_WAITING") {
    self.skipWaiting();
    return;
  }
  if (!data || typeof data !== "object") return;

  if (data.type === "CANCEL_TIMER") {
    _clearRestTimer();
    return;
  }

  if (data.type === "SCHEDULE_TIMER") {
    _clearRestTimer();
    const delay = Math.max(0, Number(data.delay) || 0);
    const title = data.title || "Repos terminé !";
    const body = data.body || "C'est reparti — série suivante";

    event.waitUntil(
      new Promise((resolve) => {
        _restResolve = resolve;
        _restTimeout = setTimeout(() => {
          _restTimeout = null;
          _restResolve = null;
          self.clients
            .matchAll({ type: "window", includeUncontrolled: true })
            .then((clients) => {
              // App au premier plan → la page gère (bip + barre). Pas de notif.
              const visible = clients.some(
                (c) => c.visibilityState === "visible"
              );
              if (visible) {
                resolve();
                return;
              }
              return self.registration
                .showNotification(title, {
                  body: body,
                  icon: "/static/icon-192.png",
                  badge: "/static/icon-192.png",
                  tag: "rest-timer",
                  renotify: true,
                  vibrate: [200, 100, 200],
                })
                .then(resolve)
                .catch(resolve);
            })
            .catch(resolve);
        }, delay);
      })
    );
  }
});

// ── Notification click : ouvre l'app ─────────────────────────────
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      if (clients.length > 0) {
        return clients[0].focus();
      }
      return self.clients.openWindow("/accueil");
    })
  );
});

// ── Fetch : Stale-While-Revalidate pour navigations HTML, Network First sinon ─
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  // Ignore les requêtes cross-origin (Plotly CDN, etc.)
  if (url.origin !== self.location.origin) return;

  const isNav = req.mode === "navigate" ||
                (req.headers.get("accept") || "").includes("text/html");

  if (isNav) {
    // Network First : toujours chercher le HTML frais côté serveur,
    // fallback sur le cache si offline.
    event.respondWith(
      fetch(req)
        .then((resp) => {
          if (resp && resp.status === 200 && resp.type === "basic") {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return resp;
        })
        .catch(() =>
          caches.open(CACHE).then((c) =>
            c.match(req).then((cached) => cached || c.match("/accueil"))
          )
        )
    );
    return;
  }

  // Assets statiques : Network First avec fallback cache.
  event.respondWith(
    fetch(req)
      .then((resp) => {
        if (resp && resp.status === 200 && resp.type === "basic") {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return resp;
      })
      .catch(() => caches.match(req).then((cached) => cached || caches.match("/accueil")))
  );
});
