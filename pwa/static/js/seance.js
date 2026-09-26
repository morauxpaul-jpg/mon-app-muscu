/**
 * Écran de saisie de séance.
 *
 * Extrait de seance_edit.html (qui portait ~750 lignes de script inline, donc
 * non testables, non mises en cache et incompatibles avec une CSP stricte).
 *
 * Principe : « Enregistrer » n'envoie plus un formulaire qui recharge toute la
 * page — il POSTe en JSON et met à jour la carte sur place. En salle, cela
 * supprime 1 à 2 secondes d'attente entre chaque exercice, et le clavier ne
 * se referme plus. Le formulaire HTML reste présent et fonctionnel : sans
 * JavaScript (ou s'il échoue), la soumission classique prend le relais.
 *
 * Les données de la page arrivent par <script type="application/json"> :
 *   #seance-config  → {mode, seance, date, semaine, weekOffset, autoRestTimer,
 *                      showRpe, exosTotal}
 */
(function () {
  "use strict";

  var CONFIG = readJson("seance-config") || {};
  var DRAFT_PREFIX = "draft_" + CONFIG.seance + "_" + CONFIG.date + "_";
  var SESSION_KEY = "active_session";
  var START_KEY = "seance_start_" + CONFIG.seance + "_" + CONFIG.date;

  function readJson(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try { return JSON.parse(el.textContent || "{}"); } catch (e) { return null; }
  }

  function csrf() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return (m && m.getAttribute("content")) || "";
  }

  // ── Séance en cours + durée ──────────────────────────────────────
  // Le chrono démarre à la PREMIÈRE série saisie, pas à l'ouverture de la
  // page : ouvrir sa séance dans le métro ne doit pas compter.
  function markSessionActive() {
    try {
      if (!localStorage.getItem(START_KEY)) {
        localStorage.setItem(START_KEY, String(Date.now()));
      }
      var existing = JSON.parse(localStorage.getItem(SESSION_KEY) || "{}");
      if (existing.active_session) return;
      localStorage.setItem(SESSION_KEY, JSON.stringify({
        active_session: true,
        session_id: CONFIG.seance,
        session_date: CONFIG.date,
        session_mode: CONFIG.mode,
      }));
    } catch (e) {}
  }

  function elapsedMinutes() {
    try {
      var start = parseInt(localStorage.getItem(START_KEY), 10);
      if (!start) return 0;
      return Math.max(0, Math.min(480, Math.round((Date.now() - start) / 60000)));
    } catch (e) { return 0; }
  }

  function clearActiveSession() {
    try {
      localStorage.removeItem(SESSION_KEY);
      localStorage.removeItem(START_KEY);
    } catch (e) {}
  }

  function clearAllDrafts() {
    try {
      var keys = [];
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k && k.indexOf(DRAFT_PREFIX) === 0) keys.push(k);
      }
      keys.forEach(function (k) { localStorage.removeItem(k); });
    } catch (e) {}
  }

  // ── Bandeau de record ────────────────────────────────────────────
  // Un record battu se fête au moment où il tombe. Le message dit ce qui a
  // été battu et depuis quoi — « Record » seul n'apprend rien.
  function prMessage(pr) {
    if (!pr) return "";
    var v = pr.value;
    if (pr.kind === "first") return "Première fois à " + fmt(v) + " kg — c'est ta référence";
    if (pr.kind === "weight") return "Record : " + fmt(v) + " kg (avant " + fmt(pr.previous) + " kg)";
    if (pr.kind === "reps") return "Record : " + v + " reps (avant " + pr.previous + ")";
    if (pr.kind === "reps_at_weight") {
      return "Record : " + v + " reps à " + fmt(pr.weight) + " kg (avant " + pr.previous + ")";
    }
    return "";
  }

  function fmt(n) {
    var x = Number(n) || 0;
    return String(Math.round(x * 100) / 100);
  }

  function showPr(card, pr) {
    var msg = prMessage(pr);
    if (!msg) return;
    var box = card.querySelector(".exo-pr");
    if (!box) {
      box = document.createElement("div");
      box.className = "exo-pr";
      var head = card.querySelector(".exo-head > div");
      (head || card).appendChild(box);
    }
    box.innerHTML =
      '<svg class="icon icon-sm" aria-hidden="true"><use href="/static/img/icons.svg#trophy"/></svg>' +
      '<span></span>';
    box.querySelector("span").textContent = msg;
    box.classList.remove("exo-pr-in");
    void box.offsetWidth;            // relance l'animation
    box.classList.add("exo-pr-in");
    if (navigator.vibrate) { try { navigator.vibrate([40, 60, 40]); } catch (e) {} }
    if (window.fireConfetti && pr.kind !== "first") {
      try { window.fireConfetti(); } catch (e) {}
    }
  }

  // ── Progression de la séance (barre du haut) ─────────────────────
  function refreshProgress(volume) {
    var done = document.querySelectorAll(".exo-card.done").length;
    var total = CONFIG.exosTotal || document.querySelectorAll(".exo-card").length || 1;
    var doneEl = document.getElementById("prog-done");
    var barEl = document.getElementById("prog-bar");
    var volEl = document.getElementById("prog-vol");
    if (doneEl) doneEl.textContent = done;
    if (barEl) barEl.style.width = Math.round((done / total) * 100) + "%";
    if (volEl && volume != null) {
      volEl.innerHTML =
        '<svg class="icon icon-sm icon-accent" aria-hidden="true"><use href="/static/img/icons.svg#zap"/></svg>' +
        fmt(volume) + " kg";
    }
    var finish = document.getElementById("finish-open");
    if (finish && done >= total && total > 0) finish.classList.add("btn-ready");
  }

  function toast(msg, kind) {
    if (window.showToast) { window.showToast(msg, kind); return; }
    var t = document.createElement("div");
    t.className = "seance-toast" + (kind === "error" ? " seance-toast-error" : "");
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 3500);
  }

  // ── Composant Alpine d'un exercice ───────────────────────────────
  window.exoBlock = function (index, data) {
    var draftKey = DRAFT_PREFIX + data.base + "_" +
                   (data.exo_index != null ? data.exo_index : index);
    return {
      open: !data.completed,
      saving: false,
      exoInfo: data.info || {},
      variant: data.variant,
      _initialVariant: data.variant,
      isBw: data.is_bw || false,
      isBwBase: data.is_bw_base || false,
      get showWeight() { return !this.isBwBase || this.variant === "Lesté"; },
      restSeconds: data.rest_seconds || 90,
      targetReps: data.target_reps || "",
      rpeOptions: ["6", "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10"],
      completed: !!data.completed,

      sets: (data.sets || []).map(function (s) {
        // Le RPE a sa propre colonne depuis la v34 ; on lit encore l'ancien
        // token « @RPE8 » présent dans les remarques d'avant la migration.
        var rawRem = s.remarque || "";
        var rpe = s.rpe != null && s.rpe !== "" ? String(s.rpe) : "";
        var m = rawRem.match(/@RPE(\d+(?:\.5)?)/i);
        if (m) {
          if (!rpe) rpe = m[1];
          rawRem = rawRem.replace(/\s*@RPE\d+(?:\.5)?\s*/i, " ").trim();
        }
        return {
          reps: s.reps != null && s.reps !== "" ? s.reps : "",
          poids: s.poids != null && s.poids !== "" ? s.poids : "",
          remarque: rawRem,
          rpe: rpe,
        };
      }),

      serializedSets: function () {
        return JSON.stringify(this.sets.map(function (s) {
          return {
            reps: s.reps,
            poids: s.poids,
            remarque: (s.remarque || "").trim(),
            rpe: s.rpe || "",
          };
        }));
      },

      lastSummary: data.last_summary || "",
      suggestion: data.suggestion || null,
      suggestionApplied: false,
      record: data.record || null,

      applySuggestion: function () {
        if (!this.suggestion || this.suggestion.poids == null) return;
        for (var i = 0; i < this.sets.length; i++) {
          if (!this.sets[i].reps) this.sets[i].poids = this.suggestion.poids;
        }
        this.suggestionApplied = true;
      },

      prevWeeks: (data.prev_weeks || []).map(function (pw) {
        return {
          week: pw.week - (Number(CONFIG.weekOffset) || 0),
          missed: pw.missed || false,
          cross_session: pw.cross_session || false,
          rows: (pw.rows || []).map(function (r) {
            var rem = (r.Remarque || "").replace(/@RPE(\d+(?:\.5)?)/i, "RPE $1").trim();
            var rpe = r.RPE != null ? r.RPE : null;
            return {
              serie: r["Série"] || 0, reps: r.Reps || 0,
              poids: r.Poids || 0, remarque: rem, rpe: rpe,
            };
          }),
        };
      }),

      // ── Isométrique (gainage, planche, wall sit…) ──
      isIso: !!data.is_isometric,
      targetSeconds: Number(data.target_seconds) || 30,
      isoRunning: false,
      isoEndTime: 0,
      isoRemaining: Number(data.target_seconds) || 30,
      _isoInterval: null,
      _firedSets: [],

      init: function () {
        try {
          var saved = localStorage.getItem(draftKey);
          if (saved) {
            var d = JSON.parse(saved);
            if (d.sets && d.sets.length) this.sets = d.sets;
            if (d.variant) this.variant = d.variant;
          }
        } catch (e) {}
        var self = this;
        this.$watch("sets", function () { self._saveDraft(); });
        this.$watch("variant", function (val) {
          self._saveDraft();
          self._fetchVariantHistory(val);
        });
        if (this.variant !== this._initialVariant) {
          this._fetchVariantHistory(this.variant);
        }
        if (this.isIso) this.isoRemaining = this.targetSeconds;
      },

      _fetchVariantHistory: function (newVariant) {
        var self = this;
        fetch("/seance/api/variant-history", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exo_base: data.base,
            variant: newVariant,
            seance: CONFIG.seance,
            date: CONFIG.date,
            s_act: Number(CONFIG.semaine),
            week_offset: Number(CONFIG.weekOffset),
          }),
        })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            self.lastSummary = d.last_summary || "";
            self.suggestion = d.suggestion || null;
            self.suggestionApplied = false;
            self.record = d.record || null;
            self.prevWeeks = (d.prev_weeks || []).map(function (pw) {
              return { week: pw.week, missed: pw.missed, rows: pw.rows || [],
                       cross_session: pw.cross_session || false };
            });
            if (d.last_sets && d.last_sets.length && !self.completed) {
              for (var i = 0; i < self.sets.length; i++) {
                if (!self.sets[i].reps && i < d.last_sets.length) {
                  self.sets[i].poids = d.last_sets[i].poids;
                }
              }
            }
          })
          .catch(function () {});
      },

      _saveDraft: function () {
        try {
          localStorage.setItem(draftKey,
            JSON.stringify({ sets: this.sets, variant: this.variant }));
        } catch (e) {}
      },

      addSet: function () {
        this.sets.push({ reps: "", poids: "", remarque: "", rpe: "" });
      },
      removeSet: function (i) {
        if (this.sets.length > 1) this.sets.splice(i, 1);
      },
      clearWeights: function () {
        this.sets.forEach(function (s) { s.poids = ""; });
      },

      onSetFilled: function (i) {
        markSessionActive();
        if (!CONFIG.autoRestTimer) return;
        var cur = this.sets[i];
        if (!cur) return;
        if (!(cur.reps !== "" && cur.reps != null && Number(cur.reps) > 0)) return;
        if (this._firedSets.indexOf(i) >= 0) return;
        this._firedSets.push(i);
        this.startRestTimer();
      },

      startRestTimer: function () {
        if (!CONFIG.autoRestTimer) return;
        var dur = parseInt(localStorage.getItem("restTimerDefault"), 10) ||
                  this.restSeconds || 90;
        if (window.RestTimer) window.RestTimer.start(dur);
      },
      manualRestTimer: function () {
        var dur = parseInt(localStorage.getItem("restTimerDefault"), 10) ||
                  this.restSeconds || 90;
        if (window.RestTimer) window.RestTimer.start(dur);
      },

      // ── Enregistrement sans rechargement ──
      save: function (ev) {
        var form = ev.target.closest("form");
        if (!form || this.saving) return;
        ev.preventDefault();
        // Hors ligne : on met en file NOUS-MÊMES et on valide la carte tout
        // de suite. Avant, la page ne bougeait pas après « Enregistrer » :
        // rien n'indiquait que la série était gardée, donc l'utilisateur la
        // ressaisissait — et se retrouvait avec des doublons en attente.
        if (!navigator.onLine) {
          this._queueOffline(form);
          return;
        }
        this.saving = true;
        var self = this;
        var card = form.closest(".exo-card");
        var body = new FormData(form);
        body.set("sets_json", this.serializedSets());
        body.set("_csrf", csrf());

        fetch(form.action, {
          method: "POST",
          body: new URLSearchParams(body),
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "X-CSRFToken": csrf(),
          },
          credentials: "same-origin",
        })
          .then(function (r) {
            if (!r.ok) throw new Error("HTTP " + r.status);
            return r.json();
          })
          .then(function (d) {
            if (!d.ok) throw new Error(d.error || "échec");
            try { localStorage.removeItem(draftKey); } catch (e) {}
            self.completed = !!d.completed;
            self.record = d.record || self.record;
            self.suggestion = d.suggestion || null;
            self.suggestionApplied = false;
            self.lastSummary = d.last_summary || self.lastSummary;
            if (card) card.classList.toggle("done", self.completed);
            refreshProgress(d.volume);
            if (d.pr) showPr(card, d.pr);
            self.startRestTimer();
            // Referme la carte terminée et ouvre la suivante : l'utilisateur
            // n'a rien à chercher entre deux exercices.
            if (self.completed) {
              self.open = false;
              openNextPending(card);
            }
          })
          .catch(function (err) {
            toast("Pas enregistré — tes séries restent sur l'appareil.", "error");
            if (window.console) console.warn("save-exo", err);
          })
          .finally(function () { self.saving = false; });
      },

      _queueOffline: function (form) {
        var body = new FormData(form);
        body.set("sets_json", this.serializedSets());
        body.set("_csrf", csrf());
        try {
          window.OfflineQueue.enqueue(form.action, body);
        } catch (e) {
          form.submit();   // pas de file disponible : comportement d'origine
          return;
        }
        try { localStorage.removeItem(draftKey); } catch (e) {}
        var card = form.closest(".exo-card");
        this.completed = true;
        this.open = false;
        if (card) card.classList.add("done");
        refreshProgress();
        openNextPending(card);
        toast("Gardé sur l'appareil — envoi au retour du réseau.", "warn");
      },

      skip: function (ev) {
        var form = ev.target.closest("form");
        if (!form) return;
        ev.preventDefault();
        if (!navigator.onLine) {
          this._queueOffline(form);
          return;
        }
        var self = this;
        var card = form.closest(".exo-card");
        var body = new FormData(form);
        body.set("_csrf", csrf());
        fetch(form.action, {
          method: "POST",
          body: new URLSearchParams(body),
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "X-CSRFToken": csrf(),
          },
          credentials: "same-origin",
        })
          .then(function (r) { return r.json(); })
          .then(function () {
            try { localStorage.removeItem(draftKey); } catch (e) {}
            self.completed = true;
            self.open = false;
            if (card) card.classList.add("done");
            refreshProgress();
            openNextPending(card);
          })
          .catch(function () { form.submit(); });
      },

      // ── Chrono isométrique ──
      formatIsoTime: function (sec) {
        var s = Math.max(0, Math.ceil(Number(sec) || 0));
        return Math.floor(s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60);
      },
      isoProgressPct: function () {
        if (!this.targetSeconds) return 0;
        var done = this.targetSeconds - this.isoRemaining;
        return Math.min(100, Math.max(0, (done / this.targetSeconds) * 100));
      },
      isoNextSeries: function () {
        for (var i = 0; i < this.sets.length; i++) {
          if (!(Number(this.sets[i].reps) > 0)) return i + 1;
        }
        return this.sets.length + 1;
      },
      isoTick: function () {
        var rem = Math.max(0, Math.ceil((this.isoEndTime - Date.now()) / 1000));
        this.isoRemaining = rem;
        if (rem <= 0) {
          clearInterval(this._isoInterval);
          this._isoInterval = null;
          this.isoRunning = false;
          this.isoFinished();
        }
      },
      isoStart: function () {
        if (this.isoRunning) return;
        markSessionActive();
        var rem = (this.isoRemaining > 0 && this.isoRemaining <= this.targetSeconds)
          ? this.isoRemaining : this.targetSeconds;
        this.isoEndTime = Date.now() + rem * 1000;
        this.isoRunning = true;
        var self = this;
        clearInterval(this._isoInterval);
        this._isoInterval = setInterval(function () { self.isoTick(); }, 250);
      },
      isoPause: function () {
        if (!this.isoRunning) return;
        this.isoRemaining = Math.max(0, Math.ceil((this.isoEndTime - Date.now()) / 1000));
        clearInterval(this._isoInterval);
        this._isoInterval = null;
        this.isoRunning = false;
      },
      isoReset: function () {
        clearInterval(this._isoInterval);
        this._isoInterval = null;
        this.isoRunning = false;
        this.isoRemaining = this.targetSeconds;
        this.isoEndTime = 0;
      },
      isoFinished: function () {
        if (typeof window._playTimerBeep === "function") window._playTimerBeep();
        if (navigator.vibrate) { try { navigator.vibrate([200, 100, 200]); } catch (e) {} }
        var logged = false;
        for (var i = 0; i < this.sets.length; i++) {
          if (!(Number(this.sets[i].reps) > 0)) {
            this.sets[i].reps = this.targetSeconds;
            if (!this.sets[i].poids) this.sets[i].poids = 0;
            logged = true;
            break;
          }
        }
        if (!logged) {
          this.sets.push({ reps: this.targetSeconds, poids: 0, remarque: "", rpe: "" });
        }
        this.isoRemaining = this.targetSeconds;
      },
      isoClearLast: function () {
        for (var i = this.sets.length - 1; i >= 0; i--) {
          if (Number(this.sets[i].reps) > 0) {
            this.sets[i].reps = "";
            this.sets[i].poids = "";
            return;
          }
        }
      },
    };
  };

  // Ouvre le premier exercice non terminé après celui qu'on vient de valider.
  function openNextPending(card) {
    if (!card) return;
    var next = card.nextElementSibling;
    while (next && !next.classList.contains("exo-card")) {
      next = next.nextElementSibling;
    }
    if (!next || next.classList.contains("done")) return;
    try {
      var comp = window.Alpine && window.Alpine.$data(next);
      if (comp) comp.open = true;
    } catch (e) {}
    setTimeout(function () {
      next.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
  }

  // ── Réordonnancement ─────────────────────────────────────────────
  window.seanceReorder = function (mode, name, date) {
    return {
      persistOrder: function () {
        var cards = this.$el.querySelectorAll(":scope > .exo-card");
        var order = Array.prototype.map.call(cards, function (c) {
          return c.dataset.exoBase;
        }).filter(Boolean);
        fetch("/seance/reorder", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: mode, seance_name: name, date: date, order: order }),
        }).catch(function () {});
      },
    };
  };

  window.moveSeanceExo = function (btnEl, dir) {
    var card = btnEl.closest(".exo-card");
    if (!card) return;
    var list = card.parentElement;
    if (dir < 0) {
      var prev = card.previousElementSibling;
      if (!prev || !prev.classList.contains("exo-card")) return;
      list.insertBefore(card, prev);
    } else {
      var next = card.nextElementSibling;
      if (!next || !next.classList.contains("exo-card")) return;
      list.insertBefore(next, card);
    }
    try { card.scrollIntoView({ block: "nearest" }); } catch (e) {}
    try {
      var comp = window.Alpine && window.Alpine.$data(list);
      if (comp && comp.persistOrder) comp.persistOrder();
    } catch (e) {}
  };

  // ── Bloc cardio inline ───────────────────────────────────────────
  window.cardioBlock = function () {
    var UNITS = {
      "Course":              { distLabel: "Distance (km)",       vitLabel: "Vitesse (km/h)",    distStep: "0.01" },
      "Vélo":                { distLabel: "Distance (km)",       vitLabel: "Vitesse (km/h)",    distStep: "0.01" },
      "Rameur":              { distLabel: "Distance (km)",       vitLabel: "Allure (min/500m)", distStep: "0.01" },
      "Natation":            { distLabel: "Distance (km)",       vitLabel: "Vitesse (m/min)",   distStep: "0.01" },
      "Corde":               { distLabel: "Nombre de sauts",     vitLabel: "Sauts/min",         distStep: "1" },
      "HIIT":                { distLabel: "Rounds",              vitLabel: "",                  distStep: "1" },
      "Marche":              { distLabel: "Distance (km)",       vitLabel: "Vitesse (km/h)",    distStep: "0.01" },
      "Elliptique":          { distLabel: "Distance (km)",       vitLabel: "Vitesse (km/h)",    distStep: "0.01" },
      "Montée d'escaliers":  { distLabel: "Étages (ou marches)", vitLabel: "Marches/min",       distStep: "1" },
      "Autre":               { distLabel: "Distance (km)",       vitLabel: "Vitesse (km/h)",    distStep: "0.01" },
    };
    return {
      open: false,
      activite: "Course",
      duree: "",
      distance: "",
      vitesse: "",
      calories: "",
      incline: 0,
      units: function () { return UNITS[this.activite] || UNITS["Autre"]; },
      autoVitesse: function () {
        var d = parseFloat(this.distance), t = parseFloat(this.duree);
        if (!d || !t) return "";
        var u = this.units();
        if (u.vitLabel.indexOf("km/h") >= 0) return (d / (t / 60)).toFixed(2);
        if (u.vitLabel.indexOf("m/min") >= 0) return ((d * 1000) / t).toFixed(0);
        if (u.vitLabel.indexOf("/min") >= 0) return (d / t).toFixed(0);
        return "";
      },
    };
  };

  // ── Bilan de fin de séance ───────────────────────────────────────
  function initFinish() {
    var LABELS = ["", "Difficile", "Moyenne", "Correcte", "Très bonne", "Excellente"];
    var form = document.getElementById("finish-form");
    var modal = document.getElementById("finish-modal");
    if (!form || !modal) return;
    document.body.appendChild(modal);   // hors du <main> animé (position:fixed)

    var stars = modal.querySelectorAll("#finish-stars button");
    var ratingLabel = document.getElementById("finish-rating-label");
    var commentInput = document.getElementById("finish-comment-input");
    var durationEl = document.getElementById("finish-duration");
    var rating = 0;

    function paintStars() {
      Array.prototype.forEach.call(stars, function (b, i) {
        b.classList.toggle("on", i < rating);
        b.setAttribute("aria-pressed", i < rating ? "true" : "false");
      });
      ratingLabel.textContent = LABELS[rating] || "";
    }
    Array.prototype.forEach.call(stars, function (b) {
      b.addEventListener("click", function () {
        rating = parseInt(b.getAttribute("data-star"), 10);
        paintStars();
      });
    });

    function submitFinish() {
      var save = document.getElementById("finish-save");
      var skipBtn = document.getElementById("finish-skip");
      save.disabled = true;
      skipBtn.disabled = true;
      save.textContent = "Enregistrement…";
      document.getElementById("finish-duration-input").value = String(elapsedMinutes());
      if (window.RestTimer) window.RestTimer.finishSession();
      clearAllDrafts();
      clearActiveSession();
      if (!navigator.onLine && window.OfflineQueue) {
        // Hors ligne : la séance est close côté appareil, le bilan part plus
        // tard. On ne laisse pas l'utilisateur bloqué sur la modale.
        window.OfflineQueue.enqueue(form.action, new FormData(form));
        modal.style.display = "none";
        if (window.showToast) {
          window.showToast("Séance terminée — le bilan partira au retour du réseau.", "warn");
        }
        setTimeout(function () { location.href = "/accueil"; }, 900);
        return;
      }
      if (form.requestSubmit) { form.requestSubmit(); return; }
      if (!form.querySelector('input[name="_csrf"]')) {
        var i = document.createElement("input");
        i.type = "hidden"; i.name = "_csrf"; i.value = csrf();
        form.appendChild(i);
      }
      form.submit();
    }

    document.getElementById("finish-open").addEventListener("click", function () {
      paintStars();
      var mins = elapsedMinutes();
      if (durationEl) {
        durationEl.textContent = mins > 0
          ? "Durée : " + (mins >= 60 ? Math.floor(mins / 60) + " h " + (mins % 60) + " min" : mins + " min")
          : "";
      }
      modal.style.display = "flex";
    });
    document.getElementById("finish-save").addEventListener("click", function () {
      document.getElementById("finish-rating").value = rating ? String(rating) : "";
      document.getElementById("finish-comment").value = (commentInput.value || "").trim();
      submitFinish();
    });
    document.getElementById("finish-skip").addEventListener("click", function () {
      document.getElementById("finish-rating").value = "";
      document.getElementById("finish-comment").value = "";
      submitFinish();
    });
    modal.addEventListener("click", function (e) {
      if (e.target === modal) modal.style.display = "none";
    });
    form.addEventListener("submit", function () {
      clearAllDrafts();
      clearActiveSession();
    });
  }

  // ── Boot ─────────────────────────────────────────────────────────
  function boot() {
    initFinish();
    refreshProgress();
    // Retour du réseau : offline.js rejoue la file, puis on recharge pour
    // repartir de ce que le serveur a réellement enregistré.
    window.addEventListener("online", function () {
      if (!window.OfflineQueue || !window.OfflineQueue.pending()) return;
      window.OfflineQueue.sync().then(function (n) {
        if (n > 0) setTimeout(function () { location.reload(); }, 1200);
      });
    });
    // Les formulaires restants (reset, extras, cardio) gardent le rechargement
    // classique : ce sont des actions rares où un aller-retour est acceptable.
    document.addEventListener("submit", function (e) {
      var form = e.target;
      if (form.dataset.noLoading != null) return;
      var btn = form.querySelector('button[type="submit"]');
      if (btn && !btn.classList.contains("loading")) {
        btn.classList.add("loading");
        btn.dataset.origText = btn.textContent;
        btn.textContent = "En cours…";
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
