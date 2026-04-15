// Prefetch des liens internes au survol / toucher pour remplir le cache SW avant le clic.
// Déclencheurs : pointerover (desktop) + touchstart (mobile), dédupliqués via un Set.
(function () {
  if (!("fetch" in window)) return;

  var seen = new Set();
  var MAX = 30; // limite soft pour éviter de swamp le cache

  function shouldPrefetch(a) {
    if (!a || !a.href) return false;
    var href = a.getAttribute("href") || "";
    if (!href.startsWith("/")) return false;           // internes uniquement
    if (href.startsWith("//")) return false;
    if (a.target === "_blank") return false;
    if (a.hasAttribute("download")) return false;
    if (a.dataset.noPrefetch != null) return false;
    // évite les endpoints POST/actions (exports, resets, etc.)
    if (/\/(logout|export|reset-|import|redo-onboarding)/.test(href)) return false;
    return true;
  }

  function prefetch(url) {
    if (seen.has(url)) return;
    if (seen.size >= MAX) return;
    seen.add(url);
    try {
      fetch(url, { credentials: "same-origin", mode: "same-origin" }).catch(function () {});
    } catch (e) {}
  }

  function handler(e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var a = t.closest("a");
    if (!shouldPrefetch(a)) return;
    prefetch(a.href);
  }

  document.addEventListener("pointerover", handler, { passive: true, capture: true });
  document.addEventListener("touchstart", handler, { passive: true, capture: true });
})();
