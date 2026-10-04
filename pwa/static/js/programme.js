// Éditeur de programme (composant Alpine `programmeApp`).
// Données posées par templates/programme.html avant ce script : BORNES,
// PROG_IS_VIP, et les blocs JSON #prog-initial / #catalog-data.
function programmeApp() {
  return {
    isVip: !!window.PROG_IS_VIP,
    prog: {},
    planning: {},
    rotation: [],
    cardio: [],
    programName: '',
    seanceOrder: [],
    originSeanceNames: [],
    origin: null,
    catalogPrograms: [],
    programmes: [],
    seanceProg: {},
    editingName: false,
    saveState: '',
    _saveTimer: null,
    renameModal: { open: false, id: null, name: '' },
    // Pourquoi une séance n'a pas pu être créée ou renommée.
    seanceMsg: '',
    // Renommage d'exercice en attente de réponse : {ancien, nouveau, series, etat}.
    renommage: null,

    // Alpine applique x-model AVANT que x-for ait créé les <option> : le
    // navigateur ne trouve pas la valeur et retombe sur la première option
    // (« Repos »). Les données restent justes (état Alpine + serveur), mais
    // l'écran affiche « Repos » partout dès qu'on revient sur la page.
    // On resynchronise donc après le rendu, et à chaque fois que la liste
    // des séances change (ajout, renommage, suppression).
    syncPlanningSelects() {
      var self = this;
      this.$nextTick(function () {
        document.querySelectorAll('#planning select[data-day]').forEach(function (sel) {
          var want = self.planning[sel.dataset.day] || '';
          if (sel.value !== want) sel.value = want;
        });
      });
    },

    init() {
      var initial = JSON.parse(document.getElementById('prog-initial').textContent);
      this.prog = initial.seances || {};
      this.planning = initial.planning || {};
      this.rotation = initial.rotation || [];
      this.cardio = initial.cardio || [];
      this.programName = initial.name || 'Mon programme';
      this.seanceOrder = initial.seance_order || [];
      this.originSeanceNames = initial.origin_seance_names || [];
      this.origin = initial.origin || null;
      this.catalogPrograms = JSON.parse(document.getElementById('catalog-data').textContent);
      this.programmes = initial.programmes || [];
      this.seanceProg = initial.seance_prog || {};

      this.syncPlanningSelects();
      var self = this;
      this.$watch('seanceOrder', function () { self.syncPlanningSelects(); });
      this.$watch('planning', function () { self.syncPlanningSelects(); });

      // Filet anti-perte : si l'utilisateur quitte l'onglet ou navigue avant
      // que la sauvegarde différée (500 ms) n'ait eu lieu, on la force
      // immédiatement (keepalive permet à la requête d'aboutir après départ).
      var self = this;
      var flush = function () {
        if (self._dirty) {
          if (self._saveTimer) { clearTimeout(self._saveTimer); self._saveTimer = null; }
          self.doSave();
        }
      };
      document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'hidden') flush();
      });
      window.addEventListener('pagehide', flush);
    },

    // Le cycle = les séances planifiées, dans l'ordre des jours ; à défaut
    // de deux séances planifiées, toutes les séances dans leur ordre.
    basculerRotation(on) {
      if (!on) { this.rotation = []; this.scheduleSave(); return; }
      var jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'];
      var cycle = [];
      var self = this;
      jours.forEach(function (j) {
        var s = self.planning[j];
        if (s && cycle.indexOf(s) < 0) cycle.push(s);
      });
      this.rotation = cycle.length >= 2 ? cycle : this.seanceOrder.slice();
      this.scheduleSave();
    },

    scheduleSave() {
      this.saveState = 'Modifié…';
      this._dirty = true;
      if (this._saveTimer) clearTimeout(this._saveTimer);
      var self = this;
      this._saveTimer = setTimeout(function() { self.doSave(); }, 500);
    },

    _dirty: false,

    async doSave() {
      this.saveState = 'Sauvegarde…';
      try {
        var resp = await fetch('/programme/state', {
          method: 'POST',
          keepalive: true,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: this.programName,
            planning: this.planning,
            rotation: this.rotation,
            seances: this.prog,
            seance_order: this.seanceOrder,
            programmes: this.programmes,
            seance_prog: this.seanceProg,
            cardio: this.cardio,
          }),
        });
        if (resp.ok) {
          this._dirty = false;
          this.saveState = '\u2713 Sauvegard\u00e9';
          var self = this;
          setTimeout(function () { if (self.saveState === '\u2713 Sauvegard\u00e9') self.saveState = ''; }, 1500);
        } else {
          this.saveState = '\u26a0 Erreur';
        }
      } catch (e) {
        this.saveState = '\u26a0 Hors ligne';
      }
    },

    _genProgId() {
      return 'p_' + Math.random().toString(16).slice(2, 10);
    },

    // ── Programmes (dossiers) ──
    seancesIn(progId) {
      var target = progId || null;
      var sp = this.seanceProg || {};
      return this.seanceOrder.filter(function (s) {
        return (sp[s] || null) === target;
      });
    },
    canAddProgramme() {
      if (this.isVip) return true;
      return (this.programmes || []).length < 1;
    },
    addProgramme(name) {
      name = (name || '').trim();
      if (!name) return;
      if (!this.canAddProgramme()) return;
      var id = this._genProgId();
      while (this.programmes.some(function (p) { return p.id === id; })) id = this._genProgId();
      var entry = { id: id, name: name };
      this.programmes.push(entry);
      this.scheduleSave();
    },
    renameProgramme(id, name) {
      name = (name || '').trim();
      if (!name) return;
      var i = this.programmes.findIndex(function (p) { return p.id === id; });
      if (i < 0) return;
      if (this.programmes[i].name === name) return;
      // Remplace l'objet pour forcer la réactivité Alpine
      this.programmes[i] = { id: this.programmes[i].id, name: name };
      this.scheduleSave();
    },
    openRenameModal(pg) {
      this.renameModal = { open: true, id: pg.id, name: pg.name };
      var self = this;
      this.$nextTick(function () {
        if (self.$refs.renameInput) {
          self.$refs.renameInput.focus();
          self.$refs.renameInput.select();
        }
      });
    },
    closeRenameModal() {
      this.renameModal = { open: false, id: null, name: '' };
    },
    confirmRenameModal() {
      var n = (this.renameModal.name || '').trim();
      if (!n) return;
      this.renameProgramme(this.renameModal.id, n);
      this.closeRenameModal();
    },
    deleteProgramme(id) {
      this.programmes = this.programmes.filter(function (p) { return p.id !== id; });
      // Séances du programme supprimé → Non classé
      for (var s in this.seanceProg) {
        if (this.seanceProg[s] === id) delete this.seanceProg[s];
      }
      this.scheduleSave();
    },
    moveProgramme(id, dir) {
      var i = this.programmes.findIndex(function (p) { return p.id === id; });
      if (i < 0) return;
      var j = dir === 'up' ? i - 1 : i + 1;
      if (j < 0 || j >= this.programmes.length) return;
      var tmp = this.programmes[i];
      this.programmes[i] = this.programmes[j];
      this.programmes[j] = tmp;
      this.scheduleSave();
    },
    moveSeanceToProg(sname, progId) {
      if (!this.prog[sname]) return;
      if (progId === '__none__' || !progId) {
        delete this.seanceProg[sname];
      } else {
        if (!this.programmes.some(function (p) { return p.id === progId; })) return;
        this.seanceProg[sname] = progId;
      }
      this.scheduleSave();
    },

    // ── Séances ──
    addSeance(name, progId) {
      name = (name || '').trim();
      if (!name) return;
      if (this.prog[name]) {
        // Avant, la création échouait EN SILENCE : le champ se vidait,
        // rien n'apparaissait, et on ne pouvait que conclure à un bug.
        // Les séances sont uniques tous programmes confondus parce que
        // l'historique les retrouve par leur nom — donc on dit qui le
        // détient, sinon on le cherche dans le mauvais programme.
        this.seanceMsg = "« " + name + " » existe déjà dans "
          + (this.programmeDe(name) || "un autre programme")
          + ". Les noms de séance servent à retrouver ton historique : "
          + "ils doivent rester uniques. Essaie « " + name + " B ».";
        return;
      }
      if (this.seanceOrder.length >= BORNES.seances) {
        this.seanceMsg = "Tu as atteint " + BORNES.seances + " séances, le maximum. "
          + "Supprime une séance qui ne sert plus pour en créer une autre.";
        return;
      }
      this.seanceMsg = '';
      this.prog[name] = [];
      this.seanceOrder.push(name);
      if (progId && this.programmes.some(function (p) { return p.id === progId; })) {
        this.seanceProg[name] = progId;
      }
      this.scheduleSave();
    },
    deleteSeance(name) {
      delete this.prog[name];
      delete this.seanceProg[name];
      this.seanceOrder = this.seanceOrder.filter(function (s) { return s !== name; });
      for (var d in this.planning) {
        if (this.planning[d] === name) this.planning[d] = '';
      }
      this.rotation = this.rotation.filter(function (s) { return s !== name; });
      if (this.rotation.length < 2) this.rotation = [];
      this.scheduleSave();
    },
    renommerExo(sname, exIdx, nouveau) {
      nouveau = (nouveau || '').trim();
      var exo = (this.prog[sname] || [])[exIdx];
      if (!exo || !nouveau || nouveau === exo.name) return;
      var ancien = exo.name;
      exo.name = nouveau;
      this.scheduleSave();
      // Corriger une faute (les séries doivent suivre) ou scinder un
      // exercice en deux variantes (prise neutre / prise large : elles
      // restent à l'ancien nom) ? L'éditeur ne peut pas le deviner : il
      // demande, seulement s'il y a des séries à emmener.
      var self = this;
      this.renommage = null;
      fetch('/programme/exo/historique', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ancien: ancien, nouveau: nouveau })
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (d && d.ok && d.series > 0) {
          self.renommage = { ancien: ancien, nouveau: nouveau, series: d.series, etat: '',
                             id: exo.id || '', exo: exo };
        }
      }).catch(function () {});
    },

    // L'identifiant de l'exercice (core/exercice_ids.py) décide : « oui »
    // le garde — ses séries le suivent sous le nouveau nom, et les autres
    // exemplaires du même exercice prennent ce nom ; « non » en fait un
    // nouvel exercice (le serveur lui calcule un identifiant neuf).
    suivreRenommage(oui) {
      var rn = this.renommage;
      if (!rn) return;
      if (!oui) {
        if (rn.exo) { delete rn.exo.id; this.scheduleSave(); }
        this.renommage = null;
        return;
      }
      var self = this;
      if (rn.id) {
        Object.keys(this.prog).forEach(function (s) {
          (self.prog[s] || []).forEach(function (e) {
            if (e && e.id === rn.id && e.name !== rn.nouveau) e.name = rn.nouveau;
          });
        });
        this.scheduleSave();
      }
      rn.etat = 'encours';
      fetch('/programme/exo/historique', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ancien: rn.ancien, nouveau: rn.nouveau, suivre: true, id: rn.id })
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d || !d.ok) throw new Error('echec');
        self.renommage = null;
        self.seanceMsg = d.deplacees + " série" + (d.deplacees > 1 ? "s" : "")
          + " de « " + rn.ancien + " » suivent désormais « " + rn.nouveau + " ».";
      }).catch(function () {
        rn.etat = 'echec';
      });
    },

    programmeDe(name) {
      var pid = this.seanceProg[name];
      var trouve = this.programmes.filter(function (p) { return p.id === pid; })[0];
      return trouve ? trouve.name : null;
    },

    renameSeance(oldName, newName) {
      newName = (newName || '').trim();
      if (!newName || newName === oldName) return;
      if (this.prog[newName]) {
        this.seanceMsg = "« " + newName + " » existe déjà dans "
          + (this.programmeDe(newName) || "un autre programme") + ".";
        return;
      }
      // Le renommage passe par le serveur : lui seul peut renommer
      // l'historique. Le faire en local laissait les séries sous l'ancien
      // nom, et la séance repartait à zéro sans rien dire.
      var self = this;
      this.seanceMsg = '';
      fetch('/programme/seance/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: oldName, new_name: newName })
      }).then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, d: d }; });
      }).then(function (res) {
        if (!res.ok) {
          self.seanceMsg = res.d && res.d.error === 'pris'
            ? "« " + newName + " » existe déjà dans " + res.d.programme + "."
            : "Le renommage a échoué. Rien n'a été modifié.";
          return;
        }
        // Le serveur a déjà tout déplacé : on aligne l'écran dessus
        // sans redemander une sauvegarde, qui écraserait son travail.
        var newProg = {};
        for (var i = 0; i < self.seanceOrder.length; i++) {
          var k = self.seanceOrder[i];
          if (k === oldName) newProg[newName] = self.prog[k];
          else newProg[k] = self.prog[k];
        }
        self.prog = newProg;
        self.seanceOrder = self.seanceOrder.map(function (x) {
          return x === oldName ? newName : x;
        });
        if (self.seanceProg[oldName]) {
          self.seanceProg[newName] = self.seanceProg[oldName];
          delete self.seanceProg[oldName];
        }
        for (var d in self.planning) {
          if (self.planning[d] === oldName) self.planning[d] = newName;
        }
        self.rotation = self.rotation.map(function (x) {
          return x === oldName ? newName : x;
        });
        self.seanceMsg = res.d.series
          ? "Séance renommée, et " + res.d.series + " série(s) d'historique "
            + "ont suivi."
          : "Séance renommée.";
        self.syncPlanningSelects();
      }).catch(function () {
        self.seanceMsg = "Le renommage a échoué. Rien n'a été modifié.";
      });
    },

    moveSeanceInProg(name, dir) {
      // Déplace la séance parmi ses voisines du même programme
      var pid = this.seanceProg[name] || null;
      var siblings = this.seancesIn(pid);
      var posInGroup = siblings.indexOf(name);
      if (posInGroup < 0) return;
      var swapName = dir === 'up' ? siblings[posInGroup - 1] : siblings[posInGroup + 1];
      if (!swapName) return;
      var i = this.seanceOrder.indexOf(name);
      var j = this.seanceOrder.indexOf(swapName);
      if (i < 0 || j < 0) return;
      var tmp = this.seanceOrder[i];
      this.seanceOrder[i] = this.seanceOrder[j];
      this.seanceOrder[j] = tmp;
      this.scheduleSave();
    },
    detailSeances(progId) {
      // Le détail d'un programme du catalogue, lu dans #catalog-data plutôt
      // qu'écrit dans la page : vingt programmes dépliés côté serveur
      // pesaient 88 ko qu'on ne regardait presque jamais.
      var p = this.catalogPrograms.find(function (x) { return x.id === progId; });
      return (p && p.seances_preview) || [];
    },
    addSeanceFromCatalog(progId, seanceName, destProg) {
      var p = this.catalogPrograms.find(function (x) { return x.id === progId; });
      if (!p) return;
      var sp = p.seances_preview.find(function (x) { return x.name === seanceName; });
      if (!sp) return;
      // Nom unique : suffixe " (N)" si déjà pris
      var finalName = seanceName;
      var n = 2;
      while (this.prog[finalName]) { finalName = seanceName + ' (' + (n++) + ')'; }
      this.prog[finalName] = sp.exercises.map(function (e) {
        return { name: e.name, sets: e.sets, muscle: e.muscle };
      });
      this.seanceOrder.push(finalName);
      if (destProg && destProg !== '__none__' && this.programmes.some(function (x) { return x.id === destProg; })) {
        this.seanceProg[finalName] = destProg;
      }
      this.scheduleSave();
    },

    // ── Exercices ──
    // Mêmes bornes que le serveur (routes/programme.py, MAX_SERIES…) :
    // sinon l'éditeur affichait 50 séries que la sauvegarde ramenait à 20.
    bornerSeries(v) {
      var n = parseInt(v, 10);
      if (!n || n < 1) return 3;
      return Math.min(BORNES.series, n);
    },
    addExo(sname, exo) {
      var name = (exo.name || '').trim();
      if (!name || !this.prog[sname]) return;
      if (this.prog[sname].length >= BORNES.exos) {
        this.seanceMsg = "« " + sname + " » a déjà " + BORNES.exos
          + " exercices, le maximum pour une séance. Crée une deuxième séance.";
        return;
      }
      var muscle = (exo.muscles || []).join(',') || 'Autre';
      this.prog[sname].push({
        name: name,
        sets: this.bornerSeries(exo.sets),
        muscle: muscle,
      });
      this.scheduleSave();
    },
    deleteExo(sname, idx) {
      if (!this.prog[sname]) return;
      this.prog[sname].splice(idx, 1);
      this.scheduleSave();
    },
    moveExo(sname, idx, dir) {
      var lst = this.prog[sname];
      if (!lst) return;
      var j = dir === 'up' ? idx - 1 : idx + 1;
      if (j < 0 || j >= lst.length) return;
      var tmp = lst[idx]; lst[idx] = lst[j]; lst[j] = tmp;
      this.scheduleSave();
    },
    reorderExo(sname, from, to) {
      var lst = this.prog[sname];
      if (!lst || from === to || from < 0 || to < 0 || from >= lst.length || to >= lst.length) return;
      var item = lst.splice(from, 1)[0];
      lst.splice(to, 0, item);
      this.scheduleSave();
    },
    toggleMuscle(ex, muscle, checked) {
      var parts = (ex.muscle || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
      var has = parts.indexOf(muscle) >= 0;
      if (checked && !has) parts.push(muscle);
      else if (!checked && has) parts.splice(parts.indexOf(muscle), 1);
      ex.muscle = parts.join(',') || 'Autre';
      this.scheduleSave();
    },

    // ── Cardio planifié ──
    removeCardio(i) {
      this.cardio.splice(i, 1);
      this.scheduleSave();
    },
  };
}
