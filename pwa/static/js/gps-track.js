/**
 * Distance parcourue, à partir des positions du GPS.
 *
 * CE QUE ÇA FAIT ET NE FAIT PAS. Le navigateur ne donne des positions que
 * pendant que la page est visible : écran éteint ou application en arrière-
 * plan, Android suspend la page et les positions cessent d'arriver. Le suivi
 * garde donc l'écran allumé tant qu'il tourne (comme le chrono de repos), et
 * il COMPTE les interruptions au lieu de faire comme si de rien n'était. Un
 * compteur qui sous-estime en silence est pire que pas de compteur.
 *
 * Les positions brutes ne se somment pas telles quelles :
 *   • une position imprécise (rayon de 50 m) ajoute des mètres inventés ;
 *   • à l'arrêt, le point saute de quelques mètres à chaque relevé et le
 *     total grimpe alors qu'on ne bouge pas ;
 *   • un recalage soudain déplace le point de 200 m d'un coup.
 * Chaque filtre ci-dessous répond à l'un de ces trois cas, et chaque rejet
 * est compté — c'est ce qui permet de dire à l'utilisateur ce qu'on a ignoré.
 *
 * Module autonome, sans DOM : `tests/js/test_gps_track.js` l'exerce sous Node
 * en lui poussant des positions à la main.
 */
'use strict';

(function () {
  // Au-delà, la position est trop floue pour qu'un déplacement soit crédible.
  var PRECISION_MAX_M = 25;
  // En deçà, c'est le tremblement du GPS à l'arrêt, pas un déplacement.
  var BRUIT_M = 6;
  // 12 m/s ≈ 43 km/h : au-delà, c'est un recalage, pas une foulée.
  var VITESSE_MAX_MS = 12;
  // Silence plus long : on a perdu le signal (ou l'écran s'est éteint). Un
  // téléphone en économie d'énergie peut espacer ses relevés à 20-30 s sans
  // que rien ne soit perdu ; c'est au-delà que la ligne droite devient un
  // mauvais raccourci.
  var TROU_S = 30;
  // On alerte sur UN long silence, jamais sur leur somme. Un téléphone en
  // économie d'énergie donne une position toutes les 35 s pendant toute la
  // course : la somme grimpe à plusieurs minutes sans qu'un seul mètre soit
  // perdu, et l'avertissement resterait allumé du début à la fin. Un
  // avertissement permanent ne veut plus rien dire.
  //
  // La somme ne sait pas distinguer « lent mais régulier » de « quelques vrais
  // trous » ; la durée du PIRE trou, si. C'est lui qui fausse le total :
  // l'écran s'éteint, on fait le tour du pâté de maisons, et la ligne droite
  // entre les deux points ne vaut plus rien.
  var TROU_ALERTE_S = 60;

  var R_TERRE_M = 6371000;

  function rad(d) { return (d * Math.PI) / 180; }

  /** Distance en mètres entre deux points, formule de haversine. */
  function distanceM(a, b) {
    var dLat = rad(b.lat - a.lat);
    var dLon = rad(b.lon - a.lon);
    var s = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R_TERRE_M * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
  }

  /**
   * Accumulateur de distance. On lui pousse des positions ; il dit ce qu'il
   * a retenu, ce qu'il a écarté et pourquoi.
   */
  function creerSuivi(options) {
    var opts = options || {};
    var precisionMax = opts.precisionMax || PRECISION_MAX_M;
    var bruit = opts.bruit != null ? opts.bruit : BRUIT_M;
    var vitesseMax = opts.vitesseMax || VITESSE_MAX_MS;
    var trou = opts.trou || TROU_S;

    var metres = 0;
    var dernier = null;          // dernière position RETENUE
    var rejets = { precision: 0, saut: 0, immobile: 0 };
    var trous = [];              // secondes de chaque interruption

    return {
      /**
       * Pousse une position. Retourne ce qui a été fait, pour que l'appelant
       * puisse l'afficher plutôt que de le deviner.
       */
      ajouter: function (pos) {
        var p = {
          lat: Number(pos.lat), lon: Number(pos.lon),
          precision: Number(pos.precision), t: Number(pos.t),
        };
        if (!isFinite(p.lat) || !isFinite(p.lon) || !isFinite(p.t)) {
          return { retenu: false, raison: "invalide" };
        }
        if (isFinite(p.precision) && p.precision > precisionMax) {
          rejets.precision++;
          return { retenu: false, raison: "precision" };
        }
        if (!dernier) { dernier = p; return { retenu: true, metres: 0 }; }

        var dt = (p.t - dernier.t) / 1000;
        if (dt <= 0) return { retenu: false, raison: "invalide" };

        var d = distanceM(dernier, p);
        // Trop rapide pour être vrai : c'est le GPS qui se recale.
        if (d / dt > vitesseMax) {
          rejets.saut++;
          return { retenu: false, raison: "saut" };
        }
        // Sous le bruit : on ne bouge pas, et on GARDE l'ancien point comme
        // référence. Sinon le tremblement s'accumulerait mètre par mètre.
        if (d < bruit) {
          rejets.immobile++;
          return { retenu: false, raison: "immobile" };
        }
        // Silence long : on ajoute la ligne droite, qui est un MINIMUM, et
        // on note le trou pour pouvoir dire que le total est peut-être bas.
        if (dt > trou) trous.push(Math.round(dt));

        metres += d;
        dernier = p;
        return { retenu: true, metres: d };
      },

      /** Distance retenue, en kilomètres, arrondie au mètre. */
      km: function () { return Math.round(metres) / 1000; },

      /** De quoi expliquer le chiffre plutôt que de le faire croire exact. */
      etat: function () {
        return {
          km: Math.round(metres) / 1000,
          rejets: { precision: rejets.precision, saut: rejets.saut,
                    immobile: rejets.immobile },
          trous: trous.slice(),
          secondesPerdues: trous.reduce(function (a, b) { return a + b; }, 0),
        };
      },

      /**
       * Phrase à montrer sous le compteur, ou "" s'il n'y a rien à signaler.
       * Le silence vaut confiance : on ne parle que d'un vrai problème.
       */
      avertissement: function () {
        var pire = trous.length ? Math.max.apply(null, trous) : 0;
        if (pire >= TROU_ALERTE_S) {
          return "Signal perdu " + Math.round(pire) + " s d'affilée — la " +
                 "distance est peut-être sous-estimée.";
        }
        if (rejets.precision >= 10 && metres === 0) {
          return "Signal trop imprécis pour mesurer la distance.";
        }
        return "";
      },

      reinitialiser: function () {
        metres = 0; dernier = null; trous = [];
        rejets = { precision: 0, saut: 0, immobile: 0 };
      },
    };
  }

  window.GpsTrack = {
    creerSuivi: creerSuivi,
    distanceM: distanceM,
    SEUILS: {
      precisionMax: PRECISION_MAX_M, bruit: BRUIT_M,
      vitesseMax: VITESSE_MAX_MS, trou: TROU_S, trouAlerte: TROU_ALERTE_S,
    },
  };
})();
