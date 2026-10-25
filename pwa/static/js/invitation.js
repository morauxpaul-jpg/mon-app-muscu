/*
 * Lien d'invitation : copier ou partager (Web Share, donc WhatsApp sur
 * téléphone). Sorti de parrainage.html pour servir aussi à la page Amis.
 *
 * Chaque bloc `[data-invitation]` porte :
 *   data-chemin  le chemin du lien (« /?ref=abcd2345&ami=1 ») ; le lien
 *                complet suit le domaine de la page (location.origin) ;
 *   data-texte   le message qui accompagne le lien ;
 *   data-suivi   le nom envoyé à /parrainage/share (mesure : « copy »,
 *                « share », préfixé de ce nom s'il n'est pas vide).
 * et, à l'intérieur : .inv-lien (champ), .inv-copier, .inv-partager.
 */
(function (racine) {
  "use strict";

  function lienDe(origine, chemin) {
    return String(origine || "") + String(chemin || "/");
  }

  function brancher(bloc, env) {
    var doc = env.document, nav = env.navigator || {};
    var lien = lienDe(env.location && env.location.origin, bloc.getAttribute("data-chemin"));
    var texte = bloc.getAttribute("data-texte") || "";
    var suivi = bloc.getAttribute("data-suivi") || "";
    var champ = bloc.querySelector(".inv-lien");
    if (champ) champ.value = lien;

    function toast(msg) {
      var t = doc.createElement("div");
      t.textContent = msg;
      t.style.cssText = "position:fixed;left:50%;bottom:96px;transform:translateX(-50%);background:#111;color:#fff;border:1px solid #333;padding:12px 18px;border-radius:4px;font-size:14px;z-index:99999;";
      doc.body.appendChild(t);
      env.setTimeout(function () { t.style.transition = "opacity .4s"; t.style.opacity = "0"; }, 2200);
      env.setTimeout(function () { t.remove(); }, 2700);
    }
    function mesurer(methode) {
      try {
        env.fetch("/parrainage/share", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ method: suivi ? suivi + "_" + methode : methode }), keepalive: true })
          .catch(function () {});
      } catch (e) { /* la mesure ne doit jamais gêner */ }
    }
    function copier() {
      if (champ && champ.select) champ.select();
      var ecrire = nav.clipboard ? nav.clipboard.writeText(lien) : Promise.reject();
      return ecrire.then(function () { toast("Lien copié"); mesurer("copy"); })
        .catch(function () {
          try { doc.execCommand("copy"); toast("Lien copié"); mesurer("copy"); } catch (e) { /* rien */ }
        });
    }
    function partager() {
      if (nav.share) {
        return nav.share({ title: "Muscu Tracker", text: texte, url: lien })
          .then(function () { mesurer("share"); })
          .catch(function (e) { if (!(e && e.name === "AbortError")) return copier(); });
      }
      return copier();
    }
    var b = bloc.querySelector(".inv-copier");
    if (b) b.addEventListener("click", copier);
    b = bloc.querySelector(".inv-partager");
    if (b) b.addEventListener("click", partager);
    return { lien: lien, copier: copier, partager: partager };
  }

  function toutBrancher(env) {
    var blocs = env.document.querySelectorAll("[data-invitation]");
    var out = [];
    for (var i = 0; i < blocs.length; i++) out.push(brancher(blocs[i], env));
    return out;
  }

  racine.Invitation = { lienDe: lienDe, brancher: brancher, toutBrancher: toutBrancher };
  if (racine.document && racine.document.querySelectorAll) toutBrancher(racine);
})(typeof window !== "undefined" ? window : this);
