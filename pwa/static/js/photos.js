/*
 * Photos de progression, onglet « Corps » de Progrès (templates/corps.html,
 * routes/corps.py).
 *
 * Une photo de téléphone pèse 3 à 8 Mo et porte la position GPS de la prise
 * de vue. Avant l'envoi, la page la redessine dans un canevas : 1 600 px au
 * plus, JPEG ; plus une miniature de 400 px pour la grille. Redessinée, la
 * photo perd toutes ses métadonnées. Le serveur refuse ce qui n'est pas un
 * JPEG de 2 Mo au plus.
 *
 * Les listes « Avant » / « Après » rechargent la comparaison dès qu'on change
 * de photo (le bouton « Comparer » reste pour une page sans script).
 */
(function () {
  "use strict";

  var COTE = 1600, COTE_MINI = 400;

  function charger(fichier) {
    // createImageBitmap applique l'orientation EXIF (photo prise en portrait).
    if (window.createImageBitmap) {
      return createImageBitmap(fichier, { imageOrientation: "from-image" })
        .catch(function () { return createImageBitmap(fichier); })
        .catch(function () { return parImage(fichier); });
    }
    return parImage(fichier);
  }

  function parImage(fichier) {
    return new Promise(function (ok, ko) {
      var url = URL.createObjectURL(fichier);
      var img = new Image();
      img.onload = function () { URL.revokeObjectURL(url); ok(img); };
      img.onerror = function () { URL.revokeObjectURL(url); ko(new Error("illisible")); };
      img.src = url;
    });
  }

  function reduire(source, cote, qualite) {
    var w = source.width || source.naturalWidth, h = source.height || source.naturalHeight;
    var r = Math.min(1, cote / Math.max(w, h));
    var canevas = document.createElement("canvas");
    canevas.width = Math.max(1, Math.round(w * r));
    canevas.height = Math.max(1, Math.round(h * r));
    canevas.getContext("2d").drawImage(source, 0, 0, canevas.width, canevas.height);
    return new Promise(function (ok, ko) {
      canevas.toBlob(function (b) { b ? ok(b) : ko(new Error("toBlob")); }, "image/jpeg", qualite);
    });
  }

  function dire(etat, texte, ko) {
    etat.textContent = texte;
    etat.classList.toggle("ph-ko", !!ko);
  }

  function envoyer(form, fichier) {
    var etat = document.getElementById("ph-etat");
    var angle = form.querySelector('input[name="angle"]:checked');
    var date = form.querySelector('input[name="date"]');
    if (!angle || !date || !date.value) {
      dire(etat, "Choisis l'angle et la date de la photo.", true);
      return Promise.resolve();
    }
    dire(etat, "Préparation de la photo…");
    return charger(fichier).then(function (source) {
      return Promise.all([reduire(source, COTE, 0.82), reduire(source, COTE_MINI, 0.75)]);
    }).then(function (blobs) {
      dire(etat, "Envoi…");
      var donnees = new FormData();
      donnees.append("angle", angle.value);
      donnees.append("date", date.value);
      donnees.append("image", blobs[0], "photo.jpg");
      donnees.append("miniature", blobs[1], "miniature.jpg");
      return fetch("/progres/photos", {
        method: "POST", body: donnees, credentials: "same-origin",
        headers: { "Accept": "application/json" },
      });
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false }; }).then(function (d) {
        if (r.ok && d.ok) {
          dire(etat, d.remplace ? "Photo remplacée." : "Photo ajoutée.");
          // Même adresse que la page, au « #photos » près : changer l'adresse
          // ne ferait que défiler, sans recharger la nouvelle photo.
          var cible = new URL(d.url || "/progres/corps#photos", window.location.href);
          if (cible.pathname + cible.search === window.location.pathname + window.location.search) {
            window.location.hash = cible.hash;
            window.location.reload();
          } else {
            window.location.href = cible.href;
          }
        } else {
          dire(etat, d.error || "L'envoi a échoué. Réessaie dans un instant.", true);
        }
      });
    }).catch(function (e) {
      var horsLigne = navigator.onLine === false || (e && e.name === "TypeError");
      dire(etat, horsLigne
        ? "Pas de réseau : la photo n'est pas partie. Réessaie une fois connecté."
        : "Cette photo n'a pas pu être lue. Essaie avec une autre.", true);
    });
  }

  var form = document.getElementById("ph-form");
  var champ = document.getElementById("ph-fichier");
  if (form && champ) {
    form.addEventListener("submit", function (e) { e.preventDefault(); });
    champ.addEventListener("change", function () {
      var fichier = champ.files && champ.files[0];
      if (!fichier) return;
      envoyer(form, fichier).then(function () { champ.value = ""; });
    });
  }

  // « Garder la dernière pesée » : rien n'est écrit en base (la dernière
  // pesée s'affiche déjà sous les photos, avec sa date) ; l'invitation se
  // tait pour cette date, sur cet appareil.
  var carte = document.getElementById("ph-pesee");
  if (carte) {
    var cle = "pesee-photos-gardee-" + carte.getAttribute("data-date");
    var garder = document.getElementById("ph-garder");
    try { if (localStorage.getItem(cle) === "1") carte.style.display = "none"; } catch (e) {}
    if (garder) {
      garder.addEventListener("click", function () {
        try { localStorage.setItem(cle, "1"); } catch (e) {}
        carte.style.display = "none";
      });
    }
  }

  var choix = document.querySelector(".ph-choix");
  if (choix) {
    choix.querySelectorAll("select").forEach(function (s) {
      s.addEventListener("change", function () { choix.submit(); });
    });
  }
})();
