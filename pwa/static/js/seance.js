/**
 * Écran de saisie de séance.
 *
 * Extrait de seance_edit.html (qui portait ~750 lignes de script inline, donc
 * non testables, non mises en cache et incompatibles avec une CSP stricte).
 *
 * Principe : chaque « Série faite » ENREGISTRE (envoi partiel : les séries
 * remplies). Avant, elle ne faisait que cocher la ligne en vert ; seul
 * « Enregistrer » écrivait, et « Terminer » effaçait les brouillons — une
 * séance entière cochée pouvait disparaître sans un mot (audit du 30/09, C1).
 *
 * Un envoi qui ne répond pas en 8 s, ou qui échoue côté réseau, part dans la
 * file hors-ligne : au sous-sol, le téléphone se croit souvent en ligne, et
 * `navigator.onLine` seul laissait le bouton bloqué sur « En cours… ».
 * « Terminer » envoie d'abord ce qui reste, et n'efface un brouillon que
 * quand le serveur (ou la file) a la donnée. Le formulaire HTML reste
 * fonctionnel sans JavaScript.
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

  // ── Envoi d'un formulaire de carte ───────────────────────────────
  // Tous les blocs exercice de la page, pour que « Terminer » puisse
  // envoyer ce qui reste avant de clore la séance.
  var BLOCS = [];
  var DELAI_ENVOI = 8000;
  // « Terminer » n'attend pas la file plus longtemps que ça.
  var DELAI_FIN = 6000;

  function lireChamps(form) {
    var champs = {};
    new FormData(form).forEach(function (v, k) { champs[k] = v; });
    return champs;
  }

  // La file hors-ligne attend un objet qui sait `forEach(valeur, clé)`.
  function versFormData(champs) {
    return {
      forEach: function (cb) {
        Object.keys(champs).forEach(function (k) { cb(champs[k], k); });
      },
    };
  }

  // → {statut: "ok", d} | {statut: "reseau"} | {statut: "refus", d}.
  // « reseau » = rien de sûr n'est arrivé : délai dépassé, pas de réponse,
  // erreur serveur, quota. La donnée doit alors partir dans la file.
  function posterFormulaire(url, champs) {
    var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    var minuterie = ctrl ? setTimeout(function () { ctrl.abort(); }, DELAI_ENVOI) : null;
    return fetch(url, {
      method: "POST",
      body: new URLSearchParams(champs),
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "X-CSRFToken": csrf(),
      },
      credentials: "same-origin",
      signal: ctrl ? ctrl.signal : undefined,
    })
      .then(function (r) {
        if (r.status >= 500 || r.status === 408 || r.status === 429) return { statut: "reseau" };
        return r.json().then(function (d) {
          return (r.ok && d && d.ok) ? { statut: "ok", d: d } : { statut: "refus", d: d || {} };
        });
      })
      // Pas de réponse, délai dépassé, ou une page HTML à la place du JSON
      // (session expirée) : la file rejouera, et saura reconnaître la session.
      .catch(function () { return { statut: "reseau" }; })
      .then(function (res) {
        if (minuterie) clearTimeout(minuterie);
        return res;
      });
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
      // Dans l'app Android : pas de pub plein écran pendant la séance.
      if (window.MTAds && window.MTAds.setInSession) window.MTAds.setInSession(true);
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
      if (window.MTAds && window.MTAds.setInSession) window.MTAds.setInSession(false);
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
    // Clé de la file hors-ligne : un envoi plus récent du même exercice
    // remplace celui qui attendait.
    var cle = draftKey;
    return {
      open: !data.completed,
      saving: false,
      // Révision des séries : `_rev` bouge à chaque modification,
      // `_revServeur` est la dernière que le serveur (ou la file) a reçue.
      _rev: 0,
      _revServeur: 0,
      // "" | "envoi" | "ok" | "attente" | "erreur" — affiché sous les séries.
      etat: "",
      _enCours: null,
      _suite: null,
      skipArme: false,
      // Panneau « aujourd'hui, à la place : ». Replié par défaut : on
      // change d'exercice de temps en temps, pas à chaque séance.
      showVariantes: false,
      // Le second rang (tout le groupe musculaire) reste replié :
      // c'est lui qui noyait les vraies variantes.
      showAutresVariantes: false,
      exoInfo: data.info || {},
      variant: data.variant,
      _initialVariant: data.variant,
      isBw: data.is_bw || false,
      isBwBase: data.is_bw_base || false,
      get showWeight() { return !this.isBwBase || this.variant === "Lesté"; },
      restSeconds: data.rest_seconds || 90,
      supersetAvec: data.superset_avec || "",
      supersetDe: data.superset_de || "",
      restPrescrit: !!data.rest_prescrit,
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
        BLOCS.push(this);
        try {
          var saved = localStorage.getItem(draftKey);
          if (saved) {
            var d = JSON.parse(saved);
            if (d.sets && d.sets.length) this.sets = d.sets;
            if (d.variant) this.variant = d.variant;
            // Un brouillon est, par définition, ce que le serveur n'a pas.
            this._rev = 1;
          }
        } catch (e) {}
        var self = this;
        this.$watch("sets", function () { self._rev++; self._saveDraft(); });
        this.$watch("variant", function (val) {
          self._rev++;
          self._saveDraft();
          self._fetchVariantHistory(val);
        });
        if (this.variant !== this._initialVariant) {
          this._fetchVariantHistory(this.variant);
        }
        if (this.isIso) this.isoRemaining = this.targetSeconds;
        // Après le brouillon : une série déjà remplie s'ouvre repliée.
        this._majFaits();
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
        this._majFaits();
      },
      removeSet: function (i) {
        if (this.sets.length > 1) this.sets.splice(i, 1);
        // Les index glissent après un retrait : on les recalcule plutôt que
        // de les décaler à la main, sinon une série faite se rouvre toute seule.
        this._majFaits();
      },

      // ── Saisie série par série ───────────────────────────────────
      // Une série remplie se replie en une ligne ; seule la courante reste
      // ouverte, avec deux champs larges. Sur 375 px, les six colonnes du
      // tableau donnaient 67 px à Reps, 70 à Poids et 25 au sélecteur de RPE.
      //
      // Le repli est de l'AFFICHAGE : `serializedSets()` envoie toujours
      // toutes les séries. Ce qui écrit, c'est « Série faite » (envoi partiel).
      faits: [],
      optionsDe: -1,

      _estRemplie: function (s) {
        return !!s && s.reps !== "" && s.reps != null && Number(s.reps) > 0;
      },
      _majFaits: function () {
        var self = this;
        this.faits = [];
        this.sets.forEach(function (s, i) {
          if (self._estRemplie(s)) self.faits.push(i);
        });
      },
      estFait: function (i) { return this.faits.indexOf(i) >= 0; },
      // La première série non repliée. -1 = tout est fait.
      indexCourant: function () {
        for (var i = 0; i < this.sets.length; i++) {
          if (this.faits.indexOf(i) < 0) return i;
        }
        return -1;
      },
      // Les reps que le champ affiche en gris : la suggestion, sinon le bas
      // de la fourchette du programme (« 8-12 » → 8). 0 si rien à proposer.
      _repsProposees: function () {
        var s = this.suggestion;
        if (s && Number(s.reps) > 0) return Number(s.reps);
        var m = /\d+/.exec(String(this.targetReps || ""));
        return m ? parseInt(m[0], 10) : 0;
      },

      serieFaite: function (i) {
        var s = this.sets[i];
        // Le champ affichait l'objectif en gris ; toucher « Série faite »
        // sans taper repliait la série avec « — » et n'enregistrait RIEN
        // (audit du 03/10, I2). Chez Hevy ou Strong, la valeur grisée est
        // celle qu'on valide : on fait de même. Sans valeur à proposer, on
        // ne prétend pas que la série est faite.
        if (s && !this._estRemplie(s)) {
          var reps = this._repsProposees();
          var sansPoids = this.showWeight && (s.poids === "" || s.poids == null);
          var poidsPropose = this.suggestion && Number(this.suggestion.poids) > 0
            ? Number(this.suggestion.poids) : 0;
          // Une charge qu'on n'a ni tapée ni vue proposée ne s'invente pas :
          // « 5 × 0 kg » au développé couché fausserait records et suggestion.
          if (!(reps > 0) || (sansPoids && !poidsPropose)) {
            this.etat = "vide";
            toast(sansPoids ? "Indique tes répétitions et ta charge avant de valider."
                            : "Indique tes répétitions avant de valider la série.", "error");
            return;
          }
          s.reps = reps;
          if (sansPoids) s.poids = poidsPropose;
        }
        if (this.faits.indexOf(i) < 0) this.faits.push(i);
        this.optionsDe = -1;
        // Le repos démarrait sur la frappe d'un champ ; il démarre maintenant
        // sur un geste voulu. `onSetFilled` ne se déclenche qu'une fois par
        // série, donc les deux chemins ne se marchent pas dessus.
        this.onSetFilled(i);
        // Et la série part en base : cocher en vert sans écrire, c'était
        // promettre ce qu'on ne tenait pas.
        if (this._estRemplie(this.sets[i])) this._envoyer("partiel");
      },
      rouvrir: function (i) {
        this.faits = this.faits.filter(function (x) { return x !== i; });
        this.optionsDe = -1;
      },
      // Le poids s'écrit avec une virgule partout où c'est du TEXTE. Dans un
      // champ nombre, le navigateur s'en charge ; dans une phrase, non.
      _kg: function (v) { return String(v).replace(".", ","); },

      objectifTexte: function () {
        if (!this.suggestion || !this.suggestion.reps) return "";
        var t = "objectif " + this.suggestion.reps;
        if (this.showWeight && this.suggestion.poids) {
          t += " × " + this._kg(this.suggestion.poids) + " kg";
        }
        return t;
      },

      resumeSerie: function (s) {
        var bouts = [];
        if (s.reps !== "" && s.reps != null) bouts.push(s.reps + " reps");
        if (this.showWeight && s.poids !== "" && s.poids != null) {
          // Virgule décimale : le résumé est du texte, pas un champ nombre,
          // donc le navigateur ne la met pas à notre place.
          bouts.push(this._kg(s.poids) + " kg");
        }
        if (s.rpe) bouts.push("RPE " + s.rpe);
        if (s.remarque) bouts.push(s.remarque);
        return bouts.length ? bouts.join(" · ") : "—";
      },
      clearWeights: function () {
        this.sets.forEach(function (s) { s.poids = ""; });
      },

      onSetFilled: function (i) {
        markSessionActive();
        var cur = this.sets[i];
        if (!cur) return;
        if (!(cur.reps !== "" && cur.reps != null && Number(cur.reps) > 0)) return;
        if (this._firedSets.indexOf(i) >= 0) return;
        this._firedSets.push(i);
        // Superset : pas de repos entre les deux exercices. Après le premier,
        // on passe au second ; après le second, repos, puis retour au premier.
        if (this.supersetAvec) { allerAuPartenaire(this._carte(), 1); return; }
        this.startRestTimer();          // ne fait rien si le chrono auto est coupé
        if (this.supersetDe) allerAuPartenaire(this._carte(), -1);
      },

      // Le repos prescrit par le programme (180 s au squat) passe avant le
      // dernier préréglage touché dans la barre : un appui sur « 1:00 » un
      // jour de fatigue remplaçait le repos de TOUS les exercices, à vie.
      // Le préréglage reste le repos des exercices sans prescription.
      _dureeRepos: function () {
        return (this.restPrescrit ? this.restSeconds : 0) ||
               parseInt(localStorage.getItem("restTimerDefault"), 10) ||
               this.restSeconds || 90;
      },
      startRestTimer: function () {
        if (!CONFIG.autoRestTimer) return;
        if (window.RestTimer) window.RestTimer.start(this._dureeRepos());
      },
      manualRestTimer: function () {
        if (window.RestTimer) window.RestTimer.start(this._dureeRepos());
      },

      // ── Enregistrement ──
      _carte: function () {
        return this.$el && this.$el.closest ? this.$el.closest(".exo-card") : null;
      },
      _form: function () {
        var c = this._carte();
        return c ? c.querySelector('form[action="/seance/save-exo"]') : null;
      },
      _aDesSeries: function () {
        var self = this;
        return this.sets.some(function (s) { return self._estRemplie(s); });
      },
      // Ce que « Terminer » doit encore envoyer.
      _aEnvoyer: function () {
        return this._rev !== this._revServeur && this._aDesSeries();
      },
      etatTexte: function () {
        return {
          envoi: "Enregistrement…",
          ok: "Enregistré",
          attente: "Gardé sur l'appareil — envoi au retour du réseau",
          erreur: "Pas enregistré — touche « Enregistrer » pour réessayer",
          vide: "Indique tes répétitions (et ta charge) avant de valider",
        }[this.etat] || "";
      },

      // mode "partiel" (Série faite, Terminer) : les séries remplies seules.
      // mode "complet" (Enregistrer) : toutes, les vides deviennent SKIP.
      // Résout "ok" | "attente" | "erreur" pour l'état le plus récent : un
      // envoi demandé pendant qu'un autre est en vol part juste après lui.
      _envoyer: function (mode) {
        var self = this;
        if (this._enCours) {
          if (this._suite !== "complet") this._suite = mode;
          return this._enCours;
        }
        if (mode === "partiel" && !this._aDesSeries()) return Promise.resolve("ok");
        var form = this._form();
        if (!form) return Promise.resolve("erreur");
        var rev = this._rev;
        var champs = lireChamps(form);
        champs.sets_json = this.serializedSets();
        champs._csrf = csrf();
        if (mode === "partiel") champs.partiel = "1";
        this.etat = "envoi";
        if (mode === "complet") this.saving = true;

        var envoi = navigator.onLine
          ? posterFormulaire(form.action, champs)
          : Promise.resolve({ statut: "reseau" });
        var p = envoi
          .then(function (res) {
            if (res.statut === "ok") {
              self._recu(res.d, rev, mode);
              return "ok";
            }
            if (res.statut === "reseau" && window.OfflineQueue) {
              window.OfflineQueue.enqueue(form.action, versFormData(champs), cle);
              // En file = en sûreté : « Terminer » n'a pas à le renvoyer. Le
              // brouillon reste, il ne coûte rien et survit à un rechargement.
              if (self._rev === rev) self._revServeur = rev;
              return "attente";
            }
            if (window.console) console.warn("save-exo refusé", res.d);
            return "erreur";
          })
          .then(function (statut) {
            self.etat = statut;
            self.saving = false;
            self._enCours = null;
            var suite = self._suite;
            self._suite = null;
            if (suite && (suite === "complet" || self._rev !== self._revServeur)) {
              return self._envoyer(suite);
            }
            return statut;
          });
        this._enCours = p;
        return p;
      },

      _recu: function (d, rev, mode) {
        if (this._rev === rev) {
          this._revServeur = rev;
          try { localStorage.removeItem(draftKey); } catch (e) {}
        }
        // Ce qui attendait pour cet exercice est plus ancien que ce que le
        // serveur vient de recevoir : le rejouer l'écraserait.
        if (window.OfflineQueue && window.OfflineQueue.drop) window.OfflineQueue.drop(cle);
        var card = this._carte();
        this.completed = !!d.completed;
        this.record = d.record || this.record;
        this.suggestion = d.suggestion || null;
        this.suggestionApplied = false;
        this.lastSummary = d.last_summary || this.lastSummary;
        if (card) card.classList.toggle("done", this.completed);
        refreshProgress(d.volume);
        if (d.pr) showPr(card, d.pr);
        // « Enregistrer » ou dernière série faite : on referme la carte et on
        // ouvre la suivante — l'utilisateur n'a rien à chercher.
        var fini = mode === "complet" || (!this.isIso && this.indexCourant() === -1);
        if (mode === "complet" && !this.supersetAvec) this.startRestTimer();
        if (this.completed && fini) {
          this.open = false;
          openNextPending(card);
        }
      },

      save: function (ev) {
        var form = ev.target.closest("form");
        if (!form) return;
        ev.preventDefault();
        var self = this;
        this._envoyer("complet").then(function (statut) {
          if (statut === "attente") {
            var card = self._carte();
            self.completed = true;
            self.open = false;
            if (card) card.classList.add("done");
            refreshProgress();
            openNextPending(card);
            toast("Gardé sur l'appareil — envoi au retour du réseau.", "warn");
          } else if (statut === "erreur") {
            toast("Pas enregistré — tes séries restent sur l'appareil.", "error");
          }
        });
      },

      // « Skip » sur un exercice qui a déjà des séries les effaçait sans
      // question. Premier appui : on arme (« Effacer ? »),
      // second appui dans les 5 s : on efface. Le serveur refuse aussi un
      // SKIP sans confirmation s'il a des séries réelles.
      skip: function (ev) {
        var form = ev.target.closest("form");
        if (!form) return;
        ev.preventDefault();
        var self = this;
        var aDesSeries = this._aDesSeries() || this.completed;
        if (aDesSeries && !this.skipArme) {
          this.skipArme = true;
          setTimeout(function () { self.skipArme = false; }, 5000);
          return;
        }
        this.skipArme = false;
        var champs = lireChamps(form);
        champs._csrf = csrf();
        if (aDesSeries) champs.confirme = "1";
        var card = this._carte();
        function fini() {
          try { localStorage.removeItem(draftKey); } catch (e) {}
          self._revServeur = self._rev;
          self.completed = true;
          self.open = false;
          if (card) card.classList.add("done");
          refreshProgress();
          openNextPending(card);
        }
        var envoi = navigator.onLine
          ? posterFormulaire(form.action, champs)
          : Promise.resolve({ statut: "reseau" });
        return envoi.then(function (res) {
          if (res.statut === "ok") {
            if (window.OfflineQueue && window.OfflineQueue.drop) window.OfflineQueue.drop(cle);
            fini();
          } else if (res.statut === "reseau" && window.OfflineQueue) {
            window.OfflineQueue.enqueue(form.action, versFormData(champs), cle);
            fini();
            toast("Gardé sur l'appareil — envoi au retour du réseau.", "warn");
          } else if (res.d && res.d.a_confirmer) {
            self.skipArme = true;
            setTimeout(function () { self.skipArme = false; }, 5000);
          } else {
            toast("Pas enregistré — réessaie.", "error");
          }
        });
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
        this._envoyer("partiel");
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

  // Superset : ouvre la carte voisine (sens 1 = suivante, -1 = précédente)
  // si elle n'est pas terminée, et l'amène à l'écran.
  function allerAuPartenaire(card, sens) {
    if (!card) return;
    var autre = sens > 0 ? card.nextElementSibling : card.previousElementSibling;
    while (autre && !autre.classList.contains("exo-card")) {
      autre = sens > 0 ? autre.nextElementSibling : autre.previousElementSibling;
    }
    if (!autre || autre.classList.contains("done")) return;
    try {
      var comp = window.Alpine && window.Alpine.$data(autre);
      if (comp) comp.open = true;
    } catch (e) {}
    setTimeout(function () {
      autre.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
  }

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
    // Les unités viennent du serveur (`core/seance_cardio.py`, servies dans
    // `#seance-config`) : une seule table, et la règle de conversion avec.
    var UNITS = CONFIG.cardioUnits || {};
    return {
      open: false,
      activite: "Course",
      duree: "",
      distance: "",
      vitesse: "",
      calories: "",
      incline: 0,
      units: function () { return UNITS[this.activite] || UNITS["Autre"] || {}; },
      // Combien d'unités de distance pour une unité de vitesse. La règle est
      // nommée côté serveur : la deviner à partir du LIBELLÉ, comme avant,
      // marchait par accident — « Allure (min/500m) » ne tombait dans aucun
      // cas et l'allure du rameur ne se calculait jamais.
      _facteur: function () {
        var t = parseFloat(this.duree) || 0, r = this.units().regle;
        if (!r || t <= 0) return 0;
        return r === "par_heure" ? t / 60 : (r === "m_par_min" ? t / 1000 : t);
      },
      _arrondi: function (n) {
        return n.toFixed(this.units().pas === "1" ? 0 : 2);
      },
      autoVitesse: function () {
        var f = this._facteur(), d = parseFloat(String(this.distance).replace(",", "."));
        if (!f || !d) return "";
        return this._arrondi(d / f);
      },
      // Le sens que le formulaire ne savait pas faire : le tapis affiche
      // 10 km/h pendant 30 min, c'est la distance qu'on ignore.
      autoDistance: function () {
        var f = this._facteur(), v = parseFloat(String(this.vitesse).replace(",", "."));
        if (!f || !v) return "";
        return this._arrondi(v * f);
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

    function erreurFinish(msg) {
      var el = document.getElementById("finish-erreur");
      if (!el) {
        el = document.createElement("p");
        el.id = "finish-erreur";
        el.setAttribute("role", "alert");
        el.className = "finish-erreur";
        var save = document.getElementById("finish-save");
        save.parentNode.insertBefore(el, save);
      }
      el.textContent = msg;
    }

    // Avant de clore : tout ce qui n'est pas encore chez le serveur part.
    // Rien n'est effacé tant qu'une série n'est ni en base ni dans la file.
    function submitFinish() {
      var save = document.getElementById("finish-save");
      var skipBtn = document.getElementById("finish-skip");
      save.disabled = true;
      skipBtn.disabled = true;
      save.textContent = "Enregistrement…";
      var restants = BLOCS.filter(function (b) { return b._aEnvoyer(); });
      Promise.all(restants.map(function (b) { return b._envoyer("partiel"); }))
        .then(function (statuts) {
          if (statuts.indexOf("erreur") >= 0) {
            save.disabled = false;
            skipBtn.disabled = false;
            save.textContent = "Enregistrer la séance";
            erreurFinish("Des séries n'ont pas pu être enregistrées. Rien n'est " +
                         "effacé : réessaie dans un instant.");
            return;
          }
          var Q = window.OfflineQueue;
          if (Q && Q.pending() > 0 && navigator.onLine) {
            // On tente de vider la file, mais on n'attend pas plus de
            // quelques secondes : ce qui reste part derrière le bilan, dans
            // l'ordre, au retour du réseau (audit du 03/10, I3).
            var delai = new Promise(function (r) { setTimeout(r, DELAI_FIN); });
            return Promise.race([Q.sync(), delai])
              .then(function () { terminer(Q.pending() > 0); });
          }
          terminer(!navigator.onLine || (Q && Q.pending() > 0));
        });
    }

    function terminer(parLaFile) {
      document.getElementById("finish-duration-input").value = String(elapsedMinutes());
      if (window.RestTimer) window.RestTimer.finishSession();
      clearAllDrafts();
      clearActiveSession();
      if (parLaFile && window.OfflineQueue) {
        // Des séries attendent le réseau : le bilan passe derrière elles dans
        // la file, dans l'ordre. On ne laisse pas l'utilisateur bloqué.
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
      // Un formulaire pris en main par le script (Enregistrer, Skip) gère son
      // propre bouton : écraser son texte cassait le libellé réactif et le
      // laissait sur « En cours… ».
      if (e.defaultPrevented || form.dataset.noLoading != null) return;
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
