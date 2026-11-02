/*
 * « Créer une séance » (page /coach/seance) : lance la création, suit la
 * tâche de fond (202 → /coach/seance/tache/<id> toutes les 1,5 s), montre la
 * proposition, puis l'ajoute au programme. Le texte reçu est posé avec
 * textContent : jamais interprété comme du HTML. Le jeton CSRF est ajouté aux
 * fetch par base.html.
 */
(function () {
  "use strict";
  var form = document.getElementById("cs-form");
  if (!form) return;
  var etat = document.getElementById("cs-etat");
  var bouton = document.getElementById("cs-creer");
  var resultat = document.getElementById("cs-resultat");
  var proposition = null;
  var typeChoisi = "reprise";

  function dire(texte) { etat.textContent = texte || ""; }

  function json(url, corps) {
    var options = corps === undefined ? {} : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps)
    };
    return fetch(url, options).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) { return { code: r.status, d: d }; });
    });
  }

  function suivre(rep) {
    if (rep.code === 202 && rep.d.tache) {
      dire("Le coach prépare ta séance… " + Math.round(rep.d.ecoule || 0) + " s");
      return new Promise(function (ok) { setTimeout(ok, 1500); }).then(function () {
        return json("/coach/seance/tache/" + encodeURIComponent(rep.d.tache)).then(suivre);
      });
    }
    return rep;
  }

  function montrer(d) {
    proposition = d.proposition;
    document.getElementById("cs-nom").textContent = proposition.nom;
    document.getElementById("cs-notes").textContent = proposition.notes || "";
    var liste = document.getElementById("cs-exos");
    liste.textContent = "";
    (d.lignes || []).forEach(function (l) {
      var li = document.createElement("li");
      var nom = document.createElement("span");
      nom.className = "cs-exo-nom";
      nom.textContent = l.nom;
      var series = document.createElement("span");
      series.className = "cs-exo-series";
      series.textContent = " · " + l.series + " × " + (l.reps || "?");
      li.appendChild(nom);
      li.appendChild(series);
      if (l.conseil) {
        var c = document.createElement("span");
        c.className = "cs-exo-conseil";
        c.textContent = l.conseil;
        li.appendChild(c);
      }
      liste.appendChild(li);
    });
    resultat.hidden = false;
    resultat.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var choix = form.querySelector('input[name="type"]:checked');
    typeChoisi = choix ? choix.value : "reprise";
    bouton.disabled = true;
    resultat.hidden = true;
    dire("Le coach prépare ta séance…");
    json("/coach/seance", {
      type: typeChoisi,
      duree: document.getElementById("cs-duree").value,
      demande: document.getElementById("cs-demande").value
    }).then(suivre).then(function (rep) {
      bouton.disabled = false;
      if (rep.code === 200 && rep.d.ok) { dire(""); montrer(rep.d); }
      else dire(rep.d.error || "La création a échoué. Réessaie.");
    }).catch(function () {
      bouton.disabled = false;
      dire("Pas de réseau. Réessaie quand tu es connecté.");
    });
  });

  document.getElementById("cs-refaire").addEventListener("click", function () {
    resultat.hidden = true;
    form.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  document.getElementById("cs-ajouter").addEventListener("click", function () {
    if (!proposition) return;
    var b = this;
    b.disabled = true;
    json("/coach/seance/ajouter", { type: typeChoisi, proposition: proposition }).then(function (rep) {
      if (rep.code === 200 && rep.d.lien) { window.location.href = rep.d.lien; return; }
      b.disabled = false;
      dire(rep.d.error || "L'ajout a échoué. Réessaie.");
    }).catch(function () {
      b.disabled = false;
      dire("Pas de réseau. Réessaie quand tu es connecté.");
    });
  });
})();
