// Page Nutrition — formulaire d'ajout de repas (composant Alpine `mealForm`).
// Les données (FOODS, MEAL_LABELS, RECENTS) sont posées par le gabarit
// juste avant ce script.
// Base d'aliments (core/foods_data.py) — hors composant Alpine : pas besoin
// de réactivité sur 400 entrées. Index normalisé (sans accents) pour la recherche.
function foodNorm(s) {
  return (s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}
FOODS.forEach(function (f) { f._n = foodNorm(f.n); });
// Aliments déjà notés (60 derniers jours) : en tête de la recherche, et
// proposés tels quels quand le champ est vide.
RECENTS.forEach(function (f) { f._n = foodNorm(f.n); });
var RECENT_NOMS = {};
RECENTS.forEach(function (f) { RECENT_NOMS[f._n] = true; });
var FOOD_POOL = RECENTS.concat(FOODS.filter(function (f) { return !RECENT_NOMS[f._n]; }));

function mealForm() {
  return {
    open_meal: '',
    mode: 'aliments',
    // ── Aliments ──
    q: '',
    results: [],
    basket: [],
    recents: RECENTS,
    offResults: [],
    offBusy: false,
    offError: '',
    offFor: '',
    search() {
      this.offResults = []; this.offError = ''; this.offFor = '';
      var words = foodNorm(this.q).split(/\s+/).filter(Boolean);
      if (!words.length) { this.results = []; return; }
      var scored = [];
      for (var i = 0; i < FOOD_POOL.length; i++) {
        var f = FOOD_POOL[i], ok = true, score = 0;
        for (var w = 0; w < words.length; w++) {
          var pos = f._n.indexOf(words[w]);
          if (pos < 0) { ok = false; break; }
          // Début de mot (nom ou mot interne) = 0, milieu de mot = 3.
          score += (pos === 0 || f._n[pos - 1] === ' ' ? 0 : 3) + pos / 100;
        }
        // « riz » → le riz cuit avant le riz cru (pesé cru, c'est l'exception).
        if (ok && / crue?s?\b/.test(f._n) && !/\bcru/.test(foodNorm(this.q))) score += 0.5;
        if (ok) scored.push([score, f]);
      }
      // Début de mot > milieu de mot ; aliments simples (r=0) avant plats/snacks ; puis nom court.
      scored.sort(function (a, b) {
        return Math.floor(a[0]) - Math.floor(b[0]) || a[1].r - b[1].r || a[0] - b[0]
          || a[1].n.length - b[1].n.length || a[1].n.localeCompare(b[1].n);
      });
      this.results = scored.slice(0, 8).map(function (x) { return x[1]; });
    },
    kcalFor(f, grams) { return Math.round(f.k * grams / 100); },
    pickFood(f) {
      this.basket.push({ food: f, qty: 1, u: 0 });
      this.q = ''; this.results = []; this.offResults = []; this.offError = ''; this.offFor = '';
    },
    grams(b) { return (parseFloat(b.qty) || 0) * b.food.u[b.u][1]; },
    macro(b, key) { return b.food[key] * this.grams(b) / 100; },
    sumBasket(key) {
      var self = this;
      return Math.round(this.basket.reduce(function (s, b) { return s + self.macro(b, key); }, 0));
    },
    // Le serveur recalcule les macros de chaque aliment à partir de ses
    // valeurs pour 100 g : on lui envoie l'aliment et la quantité.
    basketItems() {
      var self = this;
      return JSON.stringify(this.basket.map(function (b) {
        var f = b.food;
        return { n: f.n, k: f.k, p: f.p, c: f.c, f: f.f, brand: f.brand || '', code: f.code || '',
                 u: (f.u || []).filter(function (u) { return u[0] !== 'comme la dernière fois'; }),
                 grams: Math.round(self.grams(b) * 10) / 10 };
      }));
    },
    offSearch() {
      var q = this.q.trim();
      if (q.length < 3 || this.offBusy) return;
      var self = this;
      this.offBusy = true; this.offError = '';
      fetch('/nutrition/recherche?q=' + encodeURIComponent(q), { headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          self.offBusy = false;
          self.offFor = q.toLowerCase();
          if (!d || !d.ok) { self.offError = (d && d.error) || 'Recherche indisponible.'; return; }
          self.offResults = d.foods || [];
          if (!self.offResults.length) self.offError = 'Aucun produit trouvé pour « ' + q + ' ».';
        })
        .catch(function () {
          self.offBusy = false;
          self.offError = 'Pas de réseau — réessaie, ou passe en saisie rapide.';
        });
    },
    mealLabel(mt) {
      var l = (MEAL_LABELS[mt] || mt).toLowerCase();
      return mt === 'collation' ? 'en ' + l : 'au ' + l;
    },
    // ── Scanner ──
    // BarcodeDetector n'existe que sur Chrome/Android (donc l'app native et
    // la PWA Android). Ailleurs on garde la saisie des chiffres à la main
    // plutôt que d'embarquer 250 ko de décodeur pour tout le monde.
    scanSupported: !!(window.BarcodeScan && window.BarcodeScan.supported()),
    scanLive: false,
    scanBusy: false,
    scanError: '',
    scanCode: '',
    openScan(mt) {
      this.mode = 'scan';
      this.scanError = '';
      this.scanCode = '';
      if (!this.scanSupported) return;
      var self = this;
      this.$nextTick(function () {
        var v = document.getElementById('scan-video-' + mt);
        if (!v) return;
        window.BarcodeScan.start(v, function (code) {
          self.scanLive = false;
          self.lookupCode(code);
        }).then(function (err) {
          self.scanError = err || '';
          self.scanLive = !err;
        });
      });
    },
    stopScan() {
      this.scanLive = false;
      if (window.BarcodeScan) window.BarcodeScan.stop();
    },
    lookupCode(code) {
      var clean = String(code || '').replace(/[^0-9]/g, '');
      if (clean.length < 8) {
        this.scanError = 'Un code-barres fait 8 à 13 chiffres.';
        return;
      }
      var self = this;
      this.scanBusy = true;
      this.scanError = '';
      fetch('/nutrition/barcode/' + clean, { headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          self.scanBusy = false;
          if (!d || !d.ok) {
            self.scanError = (d && d.error) || 'Produit introuvable.';
            return;
          }
          // Le produit rejoint le panier « Aliments » : mêmes réglages de
          // portion, même bouton d'ajout, rien de nouveau à apprendre.
          self.stopScan();
          self.basket.push({ food: d.food, qty: 1, u: 0 });
          self.scanCode = '';
          self.mode = 'aliments';
        })
        .catch(function () {
          self.scanBusy = false;
          self.scanError = 'Pas de réseau — réessaie, ou passe en saisie rapide.';
        });
    },
    // ── Composition ──
    items: [],
    cur: { name: '', calories: 0, protein: 0, carbs: 0, fat: 0 },
    addItem() {
      if (!this.cur.name.trim() || this.cur.calories <= 0) return;
      this.items.push({
        name: this.cur.name.trim(),
        calories: this.cur.calories || 0,
        protein: this.cur.protein || 0,
        carbs: this.cur.carbs || 0,
        fat: this.cur.fat || 0,
      });
      this.cur = { name: '', calories: 0, protein: 0, carbs: 0, fat: 0 };
    },
    sumItems(key) {
      return this.items.reduce(function(s, i) { return s + (i[key] || 0); }, 0);
    },
  };
}
