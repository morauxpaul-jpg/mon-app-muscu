// Enregistre le service worker pour rendre l'app installable et offline-friendly.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/service-worker.js", { scope: "/" })
      .catch((err) => console.warn("SW registration failed:", err));
  });
}
