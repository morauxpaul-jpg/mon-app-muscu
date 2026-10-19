// Remonte au serveur les erreurs JavaScript de la page (journal Railway,
// « Erreur JS »). Une panne côté navigateur ne laissait aucune trace : le
// coach a affiché des bulles vides sept jours, du 10 au 18/10, sans qu'aucune
// alerte ne parte (audit du 18/10, I-2). Alpine écrit ses erreurs
// d'expression dans la console puis les relance : l'écoute de « error » les
// reçoit aussi.
(function () {
  var envoyes = 0, vus = {};
  var MAX = 5;   // par page chargée : une boucle d'erreurs ne doit rien inonder

  function envoyer(genre, message, source, ligne) {
    try {
      message = String(message || "").slice(0, 300);
      var cle = genre + "|" + message + "|" + (source || "") + "|" + (ligne || "");
      if (!message || vus[cle] || envoyes >= MAX) return;
      // Hors connexion (page de login, pages légales) : la route est réservée
      // aux comptes connectés, l'envoi finirait en redirection.
      var jeton = document.querySelector('meta[name="csrf-token"]');
      if (!jeton || !jeton.content) return;
      vus[cle] = true;
      envoyes += 1;
      var corps = JSON.stringify({
        genre: genre, message: message, source: String(source || "").slice(0, 200),
        ligne: ligne || null, page: location.pathname,
      });
      // keepalive : l'erreur part même si la page se ferme juste après.
      window.fetch("/erreurs/js", {
        method: "POST", keepalive: true, credentials: "same-origin",
        headers: { "Content-Type": "application/json" }, body: corps,
      }).catch(function () {});
    } catch (e) { /* ne jamais casser la page pour un rapport */ }
  }

  window.addEventListener("error", function (ev) {
    if (!ev || !ev.message) return;   // ressource non chargée (image…) : pas une erreur de code
    envoyer("erreur", ev.message, ev.filename, ev.lineno);
  });
  window.addEventListener("unhandledrejection", function (ev) {
    var r = ev && ev.reason;
    envoyer("promesse", (r && (r.message || r)) || "rejet", "", null);
  });
  window.__erreursJs = { envoyer: envoyer };   // tests
})();
