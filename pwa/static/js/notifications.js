/**
 * Notifications de rappel — utilise l'API Notification du navigateur.
 *
 * Fonctionne uniquement si :
 * - Le navigateur supporte les Notifications
 * - L'utilisateur a donné la permission
 * - Le setting "notifications" est activé dans les paramètres
 *
 * Stratégie : au chargement de la page, vérifie si un rappel est dû
 * aujourd'hui et l'affiche si non déjà montré (via localStorage).
 */
(function () {
  "use strict";

  var NOTIF_KEY_PREFIX = "muscu_notif_";

  function alreadyShown(key) {
    try {
      return localStorage.getItem(NOTIF_KEY_PREFIX + key) === "1";
    } catch (e) {
      return false;
    }
  }

  function markShown(key) {
    try {
      localStorage.setItem(NOTIF_KEY_PREFIX + key, "1");
    } catch (e) {}
  }

  function showNotif(title, body, tag) {
    if (!("Notification" in window)) return;
    if (Notification.permission !== "granted") return;

    try {
      new Notification(title, {
        body: body,
        icon: "/static/icon-192.png",
        tag: tag,
        badge: "/static/icon-192.png",
      });
    } catch (e) {
      // Mobile Safari doesn't support new Notification()
      // Use SW showNotification instead
      if (navigator.serviceWorker && navigator.serviceWorker.ready) {
        navigator.serviceWorker.ready.then(function (reg) {
          reg.showNotification(title, {
            body: body,
            icon: "/static/icon-192.png",
            tag: tag,
            badge: "/static/icon-192.png",
          });
        });
      }
    }
  }

  /**
   * Appelé depuis accueil.html avec les infos du jour.
   * @param {Object} opts
   * @param {string} opts.todaySeance - Nom de la séance du jour (vide si repos)
   * @param {boolean} opts.todayDone - true si la séance du jour est faite
   * @param {number} opts.streak - Nombre de semaines consécutives
   * @param {boolean} opts.notifEnabled - true si les notifications sont activées
   */
  window.checkDailyNotifications = function (opts) {
    if (!opts.notifEnabled) return;
    if (!("Notification" in window)) return;
    if (Notification.permission !== "granted") return;

    var today = new Date().toISOString().slice(0, 10);
    var hour = new Date().getHours();

    // Rappel matin (avant 14h) : "C'est jour de [séance] !"
    if (opts.todaySeance && !opts.todayDone && hour < 14) {
      var morningKey = "morning_" + today;
      if (!alreadyShown(morningKey)) {
        markShown(morningKey);
        showNotif(
          "💪 C'est jour de " + opts.todaySeance + " !",
          "Bonne séance aujourd'hui !",
          "morning-reminder"
        );
      }
    }

    // Rappel soir (après 18h) : séance non faite
    if (opts.todaySeance && !opts.todayDone && hour >= 18) {
      var eveningKey = "evening_" + today;
      if (!alreadyShown(eveningKey)) {
        markShown(eveningKey);
        showNotif(
          "⚠️ Séance non faite",
          "Tu n'as pas encore fait ta séance aujourd'hui !",
          "evening-reminder"
        );
      }
    }

    // Streak en danger (après 19h, séance du jour pas faite, streak > 2)
    if (
      opts.todaySeance &&
      !opts.todayDone &&
      opts.streak > 2 &&
      hour >= 19
    ) {
      var streakKey = "streak_" + today;
      if (!alreadyShown(streakKey)) {
        markShown(streakKey);
        showNotif(
          "🔥 Streak en danger !",
          "Tu as " +
            opts.streak +
            " semaines de streak, ne laisse pas tomber !",
          "streak-danger"
        );
      }
    }

    // Nettoyage des vieilles clés (> 3 jours)
    try {
      var cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - 3);
      var cutoffStr = cutoff.toISOString().slice(0, 10);
      for (var i = localStorage.length - 1; i >= 0; i--) {
        var k = localStorage.key(i);
        if (k && k.startsWith(NOTIF_KEY_PREFIX)) {
          var dateInKey = k.slice(NOTIF_KEY_PREFIX.length).split("_").pop();
          if (dateInKey < cutoffStr) {
            localStorage.removeItem(k);
          }
        }
      }
    } catch (e) {}
  };
})();
