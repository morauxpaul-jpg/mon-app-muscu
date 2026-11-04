/**
 * Une séance prévue un jour à venir s'enregistre aujourd'hui.
 *
 * Audit du 06/10 (I-1) : l'accueil proposait « Prochaine séance · Demain » et
 * ouvrait la page datée du lendemain, avec un bandeau « RATTRAPAGE ». Les
 * séries s'y enregistraient à la date de demain (constaté en production le
 * 04/10), et le lendemain la séance paraissait déjà faite.
 *
 * La page porte sa date à plusieurs endroits (#seance-config, champs cachés
 * des formulaires, réordonnancement des cartes). Ce script, chargé avant
 * seance.js et avant Alpine, la ramène au jour du TÉLÉPHONE quand elle est
 * dans le futur :
 *   - en ligne, la page est rouverte pour aujourd'hui : le serveur recalcule
 *     ce qui a déjà été fait aujourd'hui ;
 *   - hors ligne (page gardée par le service worker), la date est réécrite
 *     sur place et un bandeau le dit.
 * Le jour vient du téléphone et non du serveur : la page du jeudi gardée le
 * mardi pour le sous-sol garde sa date quand on l'ouvre le jeudi.
 */
(function (w) {
  'use strict';

  function deuxChiffres(n) { return String(n).padStart(2, '0'); }

  /**
   * Journée logique, comme le serveur (core/dates.py) et base.html : avant 4 h
   * à l'horloge, c'est encore la veille. On lit l'heure affichée puis on recule
   * d'un jour au calendrier : « maintenant moins 4 h » se trompait la nuit du
   * passage à l'heure d'hiver (le 25/10/2026 à 03 h 13, il retombait à 23 h 13
   * heure d'été... du 25, et la page se datait du lendemain).
   */
  function jourLogique(maintenantMs) {
    var d = new Date(maintenantMs == null ? Date.now() : maintenantMs);
    if (d.getHours() < 4) d.setDate(d.getDate() - 1);
    return d.getFullYear() + '-' + deuxChiffres(d.getMonth() + 1) + '-' + deuxChiffres(d.getDate());
  }

  function estAVenir(datePage, aujourdhui) {
    return /^\d{4}-\d{2}-\d{2}$/.test(datePage || '') && datePage > aujourdhui;
  }

  function urlPourAujourdhui(href, aujourdhui, prevue) {
    var u = new URL(href);
    u.searchParams.set('date', aujourdhui);
    u.searchParams.set('prevue', prevue);
    return u.toString();
  }

  function reecrire(doc, ancienne, aujourdhui) {
    var cfg = doc.getElementById('seance-config');
    if (cfg) {
      var c = JSON.parse(cfg.textContent || '{}');
      c.date = aujourdhui;
      cfg.textContent = JSON.stringify(c);
    }
    var champs = doc.querySelectorAll('input[name="date"]');
    for (var i = 0; i < champs.length; i++) {
      if (champs[i].value === ancienne) champs[i].value = aujourdhui;
    }
    var liste = doc.querySelector('[x-data^="seanceReorder("]');
    if (liste) {
      liste.setAttribute('x-data', liste.getAttribute('x-data')
        .split(JSON.stringify(ancienne)).join(JSON.stringify(aujourdhui)));
    }
    var bandeau = doc.getElementById('seance-en-avance');
    if (bandeau) bandeau.hidden = false;
  }

  /** 'rien' | 'rouverte' | 'reecrite' */
  function appliquer(doc, loc, nav, maintenantMs) {
    var cfg = doc && doc.getElementById && doc.getElementById('seance-config');
    if (!cfg) return 'rien';
    var datePage;
    try { datePage = JSON.parse(cfg.textContent || '{}').date; } catch (e) { return 'rien'; }
    var aujourdhui = jourLogique(maintenantMs);
    if (!estAVenir(datePage, aujourdhui)) return 'rien';
    if (!nav || nav.onLine !== false) {
      loc.replace(urlPourAujourdhui(loc.href, aujourdhui, datePage));
      return 'rouverte';
    }
    reecrire(doc, datePage, aujourdhui);
    return 'reecrite';
  }

  w.JourSeance = {
    jourLogique: jourLogique,
    estAVenir: estAVenir,
    urlPourAujourdhui: urlPourAujourdhui,
    appliquer: appliquer,
  };
  if (w.document && w.location) {
    try { appliquer(w.document, w.location, w.navigator); } catch (e) { /* page intacte */ }
  }
})(window);
