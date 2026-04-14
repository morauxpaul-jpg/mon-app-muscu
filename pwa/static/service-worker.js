// Service worker — Network First avec mise à jour automatique.
// IMPORTANT : incrémenter CACHE_VERSION à chaque déploiement pour forcer le refresh.
const CACHE_VERSION = "v21-2026-04-14";
const CACHE = "muscu-pwa-" + CACHE_VERSION;

const APP_SHELL = [
  "/accueil",
  "/seance",
  "/static/css/theme.css",
  "/static/css/components.css",
  "/static/css/tutorial.css",
  "/static/js/sw-register.js",
  "/static/js/offline.js",
  "/static/js/alpine.min.js",
  "/static/js/tutorial.js",
  "/static/js/tuto-seance.js",
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

// ── Message : permet au client de forcer skipWaiting + notifications ─
self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
  if (event.data && event.data.type === "SHOW_NOTIFICATION") {
    self.registration.showNotification(event.data.title, {
      body: event.data.body,
      icon: "/static/icon-192.png",
      tag: event.data.tag || "muscu-reminder",
      badge: "/static/icon-192.png",
    });
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

// ── Fetch : Network First avec fallback cache ─────────────────────
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  // Ignore les requêtes cross-origin (Plotly CDN, etc.)
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    fetch(req)
      .then((resp) => {
        // Réponse OK → on met en cache et on retourne
        if (resp && resp.status === 200 && resp.type === "basic") {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return resp;
      })
      .catch(() => caches.match(req).then((cached) => cached || caches.match("/accueil")))
  );
});
