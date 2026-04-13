// Enregistre le service worker + active la mise à jour automatique.
// À chaque chargement, on demande au SW de checker une nouvelle version.
// Si une nouvelle version est trouvée, on la prend, on l'active et on recharge.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/service-worker.js", { scope: "/" })
      .then((reg) => {
        // Force le check d'update à chaque chargement
        reg.update();

        // Nouvelle version détectée → on l'active dès qu'elle est prête
        reg.addEventListener("updatefound", () => {
          const sw = reg.installing;
          if (!sw) return;
          sw.addEventListener("statechange", () => {
            if (sw.state === "installed" && navigator.serviceWorker.controller) {
              // Une version est en attente → on lui dit de prendre le relais
              sw.postMessage("SKIP_WAITING");
            }
          });
        });
      })
      .catch((err) => console.warn("SW registration failed:", err));

    // Quand le nouveau SW prend le contrôle, on recharge l'app
    let refreshing = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (refreshing) return;
      refreshing = true;
      // Flag pour que le modal patch notes s'affiche APRÈS le reload
      try { localStorage.setItem("pending_changelog", "1"); } catch(e) {}
      window.location.reload();
    });
  });
}
