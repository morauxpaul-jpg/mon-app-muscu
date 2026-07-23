/**
 * Chrono de repos — GLOBAL et PERSISTANT.
 *
 * Chargé par base.html sur toutes les pages authentifiées. L'état ne vit plus
 * dans la page (il disparaissait à chaque navigation / enregistrement d'exo)
 * mais dans localStorage, sous la forme d'une échéance absolue :
 *
 *     rest_timer_state = { end: <ms epoch>, total: <sec>, url: <page séance> }
 *
 * Conséquences :
 *   • changer d'onglet (Accueil, Progrès…) ne coupe plus le repos : la barre
 *     se ré-affiche en pastille discrète, au-dessus de la bottom-nav ;
 *   • enregistrer un exercice (POST + redirect) non plus ;
 *   • quitter l'app puis revenir non plus (l'échéance est absolue).
 *
 * La notification de fin de repos est planifiée par l'OS (Capacitor Local
 * Notifications) ou, à défaut, par le service worker. Elle est ANNULÉE dès que
 * la séance se termine — sinon on recevait un « série suivante » après avoir
 * cliqué sur « Terminer la séance ».
 */
(function () {
  "use strict";

  var STATE_KEY = "rest_timer_state";
  var DEFAULT_KEY = "restTimerDefault"; // durée préférée (préréglages)
  var MUTE_KEY = "restTimerMuted";
  var SESSION_KEY = "active_session";
  var NOTIF_ID = 4242;
  var DONE_GRACE_MS = 90000;  // au-delà, un chrono expiré n'est plus ré-affiché
  var DONE_HIDE_MS = 6000;    // durée d'affichage de l'état « C'est reparti »

  var PRESETS = [60, 90, 120, 180];

  var _state = null;      // null = aucun repos en cours
  var _interval = null;
  var _finished = false;
  var _bar = null;
  var _els = {};
  var _ctx = null;
  var _doneUntil = 0;     // fin de l'affichage « C'est reparti »
  var _origTitle = document.title;

  // ── Persistance ─────────────────────────────────────────────────
  function _load() {
    try {
      var s = JSON.parse(localStorage.getItem(STATE_KEY) || "null");
      return s && s.end ? s : null;
    } catch (e) { return null; }
  }
  function _save() {
    try {
      if (_state) localStorage.setItem(STATE_KEY, JSON.stringify(_state));
      else localStorage.removeItem(STATE_KEY);
    } catch (e) {}
  }
  function _defaultDuration() {
    var d = parseInt(localStorage.getItem(DEFAULT_KEY), 10);
    return d > 0 ? d : 90;
  }
  function _muted() {
    try { return localStorage.getItem(MUTE_KEY) === "1"; } catch (e) { return false; }
  }

  // URL de la séance en cours (pour que la pastille y ramène en un tap).
  function _sessionUrl() {
    if (_isSeancePage()) return location.pathname + location.search;
    if (_state && _state.url) return _state.url;
    try {
      var s = JSON.parse(localStorage.getItem(SESSION_KEY) || "{}");
      if (s.active_session) {
        return "/seance?mode=" + (s.session_mode || "prefaite") +
               "&name=" + encodeURIComponent(s.session_id || "") +
               "&date=" + (s.session_date || "");
      }
    } catch (e) {}
    return "/seance";
  }
  // La page séance expose <div id="rest-timer-host"> : c'est le signal du
  // rendu complet (préréglages + son). Partout ailleurs → pastille.
  function _isSeancePage() {
    return !!document.getElementById("rest-timer-host");
  }

  // ── Son de fin (3 notes, franchement audible) ───────────────────
  function unlockAudio() {
    try {
      if (!_ctx) {
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        _ctx = new AC();
      }
      if (_ctx.state === "suspended") _ctx.resume();
    } catch (e) {}
  }

  function _note(freq, at, dur, peak) {
    var osc = _ctx.createOscillator();
    var gain = _ctx.createGain();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(freq, at);
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(peak, at + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    osc.connect(gain);
    gain.connect(_ctx.destination);
    osc.start(at);
    osc.stop(at + dur + 0.02);
  }

  function playEndSound() {
    if (_muted()) return;
    unlockAudio();
    if (!_ctx) return;
    try {
      var t0 = _ctx.currentTime + 0.02;
      _note(880, t0, 0.18, 0.35);          // La
      _note(880, t0 + 0.20, 0.18, 0.35);
      _note(1318.5, t0 + 0.40, 0.32, 0.40); // Mi — note haute finale
    } catch (e) {}
  }

  // ── Notifications planifiées (OS natif > service worker) ────────
  function _capLN() {
    return (window.Capacitor && window.Capacitor.Plugins &&
            window.Capacitor.Plugins.LocalNotifications) || null;
  }
  function _postSW(msg) {
    try {
      if (!("serviceWorker" in navigator)) return;
      if (navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage(msg);
      } else {
        navigator.serviceWorker.ready.then(function (reg) {
          if (reg && reg.active) reg.active.postMessage(msg);
        }).catch(function () {});
      }
    } catch (e) {}
  }
  function cancelNotifications() {
    _postSW({ type: "CANCEL_TIMER" });
    var ln = _capLN();
    if (ln) { try { ln.cancel({ notifications: [{ id: NOTIF_ID }] }); } catch (e) {} }
  }
  function _ensureNotifPermission() {
    try {
      var ln = _capLN();
      if (ln) { try { ln.requestPermissions(); } catch (e) {} return; }
      if (!("Notification" in window)) return;
      if (Notification.permission === "default") Notification.requestPermission();
    } catch (e) {}
  }
  function _scheduleNotif(seconds) {
    cancelNotifications();
    var ln = _capLN();
    if (ln) {
      try {
        ln.schedule({ notifications: [{
          id: NOTIF_ID,
          title: "Repos terminé !",
          body: "C'est reparti — série suivante",
          schedule: { at: new Date(Date.now() + seconds * 1000), allowWhileIdle: true }
        }] });
        return;
      } catch (e) {}
    }
    _postSW({
      type: "SCHEDULE_TIMER",
      delay: seconds * 1000,
      title: "Repos terminé !",
      body: "C'est reparti — série suivante"
    });
  }

  // ── Construction de la barre (une fois par page) ────────────────
  function _icon(name, extra) {
    return '<svg class="icon icon-sm' + (extra || '') + '"><use href="/static/img/icons.svg#' + name + '"/></svg>';
  }

  function _build() {
    if (_bar) return _bar;
    if (!document.body) return null;
    var full = _isSeancePage();
    var bar = document.createElement("div");
    bar.id = "rest-timer";
    bar.className = "rest-timer-bar" + (full ? "" : " compact");
    bar.hidden = true;
    bar.innerHTML =
      '<div class="rest-timer-bar-progress"></div>' +
      '<div class="rest-timer-bar-content">' +
        '<span class="rest-timer-bar-label label-icon">' + _icon("clock") + '<span class="rt-word">REPOS</span></span>' +
        '<span class="rest-timer-bar-time">1:30</span>' +
        '<div class="rest-timer-bar-presets">' +
          PRESETS.map(function (s) {
            return '<button type="button" data-sec="' + s + '">' + _fmt(s) + '</button>';
          }).join('') +
        '</div>' +
        '<button type="button" class="rest-timer-sound" aria-label="Son du chrono">' + _icon("volume") + '</button>' +
        '<button type="button" class="rest-timer-bar-skip" aria-label="Passer le repos">' + _icon("x") + '</button>' +
      '</div>';
    document.body.appendChild(bar);

    _bar = bar;
    _els.progress = bar.querySelector(".rest-timer-bar-progress");
    _els.label = bar.querySelector(".rest-timer-bar-label");
    _els.time = bar.querySelector(".rest-timer-bar-time");
    _els.sound = bar.querySelector(".rest-timer-sound");
    _els.presets = bar.querySelectorAll(".rest-timer-bar-presets button");

    Array.prototype.forEach.call(_els.presets, function (b) {
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        setDuration(parseInt(b.getAttribute("data-sec"), 10));
      });
    });
    bar.querySelector(".rest-timer-bar-skip").addEventListener("click", function (e) {
      e.stopPropagation();
      skip();
    });
    _els.sound.addEventListener("click", function (e) {
      e.stopPropagation();
      var next = !_muted();
      try { localStorage.setItem(MUTE_KEY, next ? "1" : "0"); } catch (err) {}
      _renderSound();
      if (!next) playEndSound(); // aperçu quand on réactive le son
    });
    // Pastille : un tap ramène à la séance en cours.
    if (!full) {
      bar.addEventListener("click", function () {
        var url = _sessionUrl();
        if (url) location.href = url;
      });
    }
    _renderSound();
    return bar;
  }

  function _renderSound() {
    if (!_els.sound) return;
    var muted = _muted();
    _els.sound.classList.toggle("muted", muted);
    _els.sound.innerHTML = _icon(muted ? "volume-off" : "volume");
  }

  // ── Affichage ───────────────────────────────────────────────────
  function _fmt(sec) {
    var r = Math.max(0, sec);
    var m = Math.floor(r / 60);
    var s = r % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function _remaining() {
    if (!_state) return 0;
    return Math.max(0, Math.ceil((_state.end - Date.now()) / 1000));
  }

  function _paint() {
    if (!_build() || !_state) return;
    var rem = _remaining();
    var txt = _fmt(rem);
    _els.time.textContent = txt;
    _els.progress.style.width = ((rem / (_state.total || 1)) * 100) + "%";
    _highlight(_state.total);
    if (rem > 0) document.title = "Repos " + txt + " — Muscu Tracker";
  }

  function _highlight(sec) {
    Array.prototype.forEach.call(_els.presets || [], function (b) {
      b.classList.toggle("active", parseInt(b.getAttribute("data-sec"), 10) === sec);
    });
  }

  // Cale la barre juste AU-DESSUS de la bottom-nav. On mesure la nav réelle
  // (sa hauteur dépend de la safe-area de l'appareil) plutôt que de se fier à
  // --nav-h : c'est ce décalage figé qui faisait chevaucher les onglets.
  function _position() {
    if (!_bar) return;
    var nav = document.querySelector(".bottom-nav");
    var h = nav ? Math.round(nav.getBoundingClientRect().height) : 0;
    var extra = _bar.classList.contains("compact") ? 10 : 0;
    // La hauteur de la nav inclut déjà la safe-area ; sans nav (onboarding…),
    // on la rajoute nous-mêmes pour ne pas passer sous la barre système.
    _bar.style.bottom = h > 0
      ? (h + extra) + "px"
      : "calc(env(safe-area-inset-bottom) + " + extra + "px)";
  }
  window.addEventListener("resize", _position);
  window.addEventListener("orientationchange", _position);

  function _show() {
    var bar = _build();
    if (!bar) return;
    bar.classList.remove("timer-done");
    _els.label.innerHTML = _icon("clock") + '<span class="rt-word">REPOS</span>';
    bar.hidden = false;
    _position();
  }

  function _hide() {
    if (_bar) _bar.hidden = true;
    document.title = _origTitle;
  }

  function _loop() {
    clearInterval(_interval);
    _interval = setInterval(_tick, 1000);
  }

  function _tick() {
    if (!_state) { clearInterval(_interval); _interval = null; return; }
    _paint();
    if (_remaining() <= 0) {
      clearInterval(_interval);
      _interval = null;
      _onFinished();
    }
  }

  function _onFinished() {
    if (_finished) return; // idempotent (tick + retour au premier plan)
    _finished = true;
    var bar = _build();
    if (bar) {
      bar.hidden = false;
      _position();
      bar.classList.add("timer-done");
      _els.label.innerHTML = _icon("check-circle", " icon-success") + '<span class="rt-word">C\'EST REPARTI</span>';
      _els.time.textContent = "0:00";
      _els.progress.style.width = "0%";
    }
    document.title = "GO ! — Muscu Tracker";
    playEndSound();
    if (navigator.vibrate) { try { navigator.vibrate([200, 100, 200]); } catch (e) {} }
    // On est au premier plan (on vient de biper) → la notif planifiée ferait
    // doublon : on l'annule.
    cancelNotifications();
    _state = null;
    _doneUntil = Date.now() + DONE_HIDE_MS;
    _save();
    setTimeout(function () { if (!_state) _hide(); }, DONE_HIDE_MS);
  }

  // ── API publique ────────────────────────────────────────────────
  function start(seconds) {
    var total = parseInt(seconds, 10) || _defaultDuration();
    _state = { end: Date.now() + total * 1000, total: total, url: _sessionUrl() };
    _finished = false;
    _save();
    _show();
    _paint();
    _loop();
    unlockAudio();          // le lancement vient d'un geste : on débloque l'audio
    _ensureNotifPermission();
    _scheduleNotif(total);
  }

  function setDuration(sec) {
    sec = parseInt(sec, 10);
    if (!(sec > 0)) return;
    try { localStorage.setItem(DEFAULT_KEY, String(sec)); } catch (e) {}
    start(sec);
  }

  function skip() {
    clearInterval(_interval);
    _interval = null;
    _state = null;
    _finished = false;
    _doneUntil = 0;
    _save();
    _hide();
    cancelNotifications();
  }

  /** Fin de séance : le repos n'a plus lieu d'être — barre ET notification
   *  programmée sont supprimées (sinon « série suivante » arrive après coup). */
  function finishSession() {
    skip();
  }

  function isRunning() { return !!_state; }

  // ── Reprise (chargement de page, retour d'app, retour d'onglet) ──
  function _adopt() {
    var stored = _load();
    if (!stored) {
      // On laisse le « C'est reparti » à l'écran le temps prévu, même si un
      // focus survient entre-temps (le repos, lui, est bien terminé).
      if (Date.now() < _doneUntil) return;
      if (_state) { _state = null; clearInterval(_interval); _interval = null; }
      _hide();
      return;
    }
    _state = stored;
    var left = stored.end - Date.now();
    if (left > 0) {
      _finished = false;
      _show();
      _paint();
      _loop();
      return;
    }
    // Le repos s'est terminé pendant l'absence : on le signale s'il vient
    // juste de finir, sinon on nettoie sans bruit.
    clearInterval(_interval);
    _interval = null;
    if (left > -DONE_GRACE_MS) {
      _finished = false;
      _onFinished();
    } else {
      _state = null;
      _save();
      _hide();
    }
  }

  function _onVisible() {
    if (document.hidden) return;
    _adopt();
  }

  document.addEventListener("visibilitychange", _onVisible);
  window.addEventListener("pageshow", _onVisible);
  window.addEventListener("focus", _onVisible);
  // App native : reprise après un passage sur une autre app (TikTok & co).
  try {
    if (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.App) {
      window.Capacitor.Plugins.App.addListener("appStateChange", function (st) {
        if (st && st.isActive) _adopt();
      });
    }
  } catch (e) {}

  // Fin de séance (ou séance marquée manquée) → plus de repos ni de notif.
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (!f || !f.getAttribute) return;
    var action = f.getAttribute("action") || "";
    if (action.indexOf("/seance/finish") !== -1 ||
        action.indexOf("/seance/mark-missed") !== -1) {
      finishSession();
    }
  }, true);

  window.RestTimer = {
    start: start,
    skip: skip,
    setDuration: setDuration,
    finishSession: finishSession,
    cancelNotifications: cancelNotifications,
    playEndSound: playEndSound,
    unlockAudio: unlockAudio,
    isRunning: isRunning,
  };
  // Compatibilité avec les appels existants des templates.
  window.startTimer = start;
  window.skipTimer = skip;
  window.setTimerDuration = setDuration;
  window._playTimerBeep = playEndSound;

  _adopt();
})();
