// Service worker — Network First avec mise à jour automatique.
// CACHE_VERSION : en prod, app.py (route /service-worker.js) suffixe cette
// valeur avec le SHA du commit déployé (RAILWAY_GIT_COMMIT_SHA) → chaque
// déploiement invalide le cache automatiquement. Ne bumper la base que pour
// forcer un refresh en local (pas de SHA) ou changer l'APP_SHELL.
const CACHE_VERSION = "v122";
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
  "/static/js/seance.js",
  "/static/js/exo-info.js",
  "/static/js/barcode.js",
  "/static/css/timer.css",
  "/static/css/rest-timer.css",
  "/static/js/rest-timer.js",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/badge.png",
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

  if (data.type === "PRECACHE") {
    event.waitUntil(precache(data.urls));
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
                  badge: "/static/badge.png",
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

// ── Notification click : ouvre l'app sur l'URL portée par la notif ───
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/accueil";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const c of clients) {
        if ("focus" in c) {
          if ("navigate" in c) { try { c.navigate(url); } catch (e) {} }
          return c.focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});

// ── Pré-cache des séances du jour ────────────────────────────────
// L'app poste les URLs des séances planifiées (aujourd'hui + demain) dès
// qu'elle s'ouvre en ligne. Sans ça, ouvrir sa séance en salle au sous-sol
// renvoyait à l'accueil : l'URL /seance?mode=…&name=…&date=… n'avait jamais
// été visitée, donc jamais mise en cache.
async function precache(urls) {
  const cache = await caches.open(CACHE);
  await Promise.all(
    (urls || []).map((u) =>
      fetch(u, { credentials: "same-origin" })
        .then((resp) => {
          if (resp && resp.status === 200 && resp.type === "basic") {
            return cache.put(u, resp.clone());
          }
        })
        .catch(() => {})
    )
  );
}

// ── Fetch ────────────────────────────────────────────────────────
// Navigations (HTML) : réseau d'abord, cache en secours. Une page fraîche
//   vaut mieux qu'une page d'hier quand le réseau répond.
// Assets versionnés (CSS/JS/SVG) : cache d'abord, rafraîchi en arrière-plan
//   (stale-while-revalidate). Ils changent à chaque déploiement, jamais entre
//   deux, donc les re-télécharger à chaque navigation est du gaspillage.
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  const isNav = req.mode === "navigate" ||
                (req.headers.get("accept") || "").includes("text/html");

  if (isNav) {
    event.respondWith(
      fetch(req)
        .then((resp) => {
          if (resp && resp.status === 200 && resp.type === "basic") {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return resp;
        })
        .catch(async () => {
          const cache = await caches.open(CACHE);
          // 1. La page exacte demandée.
          const exact = await cache.match(req);
          if (exact) return exact;
          // 2. La même page sans les paramètres (une séance ouverte hier
          //    reste utile aujourd'hui : l'utilisateur y retrouve ses exos).
          const bare = await cache.match(url.pathname);
          if (bare) return bare;
          // 3. Dernier recours : l'accueil, mais en le DISANT. Un retour
          //    silencieux à l'accueil ressemble à un bug.
          const home = await cache.match("/accueil");
          if (home) {
            const html = await home.text();
            return new Response(
              html.replace("</body>", OFFLINE_BANNER + "</body>"),
              { headers: { "Content-Type": "text/html; charset=utf-8" } }
            );
          }
          return new Response(OFFLINE_PAGE, {
            status: 503,
            headers: { "Content-Type": "text/html; charset=utf-8" },
          });
        })
    );
    return;
  }

  const isVersionedAsset = url.pathname.startsWith("/static/");
  if (isVersionedAsset) {
    event.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const cached = await cache.match(req);
        const network = fetch(req)
          .then((resp) => {
            if (resp && resp.status === 200 && resp.type === "basic") {
              cache.put(req, resp.clone());
            }
            return resp;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
    return;
  }

  event.respondWith(
    fetch(req).catch(() => caches.match(req).then((c) => c || Response.error()))
  );
});

// Message affiché quand on a dû replier sur l'accueil faute de mieux.
const OFFLINE_BANNER =
  '<div style="position:fixed;left:16px;right:16px;bottom:84px;z-index:99999;' +
  'padding:12px 16px;border-radius:12px;background:rgba(255,159,10,0.95);' +
  'color:#0a0a1a;font:600 0.85rem system-ui;text-align:center;' +
  'box-shadow:0 4px 20px rgba(0,0,0,0.4)">' +
  "Hors ligne \u2014 cette page n'\u00e9tait pas en m\u00e9moire. Voici ton accueil." +
  "</div>";

const OFFLINE_PAGE =
  '<!doctype html><html lang="fr"><head><meta charset="utf-8">' +
  '<meta name="viewport" content="width=device-width,initial-scale=1">' +
  "<title>Hors ligne</title><style>body{margin:0;min-height:100vh;display:flex;" +
  "align-items:center;justify-content:center;background:#0a0a0f;color:#e7e9ee;" +
  "font-family:system-ui,sans-serif;text-align:center;padding:24px}" +
  "h1{font-size:1.2rem;margin:0 0 8px}p{color:#9aa3b2;font-size:0.9rem;line-height:1.5;margin:0}" +
  "button{margin-top:18px;padding:12px 22px;border:0;border-radius:10px;" +
  "background:#78c8ff;color:#0a0a0f;font-size:0.95rem;font-weight:600}</style></head>" +
  "<body><div><h1>Pas de connexion</h1>" +
  "<p>Cette page n'a pas encore \u00e9t\u00e9 mise en m\u00e9moire.<br>" +
  "Tes s\u00e9ries saisies hors ligne sont conserv\u00e9es et partiront au retour du r\u00e9seau.</p>" +
  '<button onclick="location.reload()">R\u00e9essayer</button></div></body></html>';

// ── Push web (relance des inactifs) ──────────────────────────────
// Le clic est géré par le handler `notificationclick` unique ci-dessus
// (il lit event.notification.data.url).
self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) {}
  const title = data.title || "Muscu Tracker";
  const options = {
    body: data.body || "",
    icon: "/static/icon-192.png",
    badge: "/static/badge.png",
    tag: data.tag || "muscu-push",
    vibrate: [120, 60, 120],
    data: { url: data.url || "/accueil" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});
