// Page « Mes recettes et aliments » — l'éditeur de recette (composant Alpine
// `recetteForm`). Les données (RECETTE_DONNEES : foods, recents, perso,
// edition) sont posées par le gabarit juste avant ce script ; la recherche
// vient de aliments-recherche.js. Le serveur recalcule tout à partir des
// ingrédients (core/nutrition_recettes.py) : les totaux affichés ici ne
// servent qu'à voir ce qu'on compose.
var RECETTE = (typeof RECETTE_DONNEES !== 'undefined' && RECETTE_DONNEES) || {};
var POOL_INGREDIENTS = poolAliments([RECETTE.recents, RECETTE.perso, RECETTE.foods]);
var DERNIERE_FOIS = 'comme la dernière fois';

// Une recette se pèse : la première unité proposée est le gramme, les
// portions de l'aliment (« 1 œuf ») restent au choix.
function ingredient(f, grammes) {
  var portions = (f.u || []).filter(function (u) { return u[0] !== DERNIERE_FOIS; });
  return { food: f, unites: [['g', 1]].concat(portions), qty: grammes, u: 0 };
}

function recetteForm() {
  var ed = RECETTE.edition || {};
  return {
    nom: ed.nom || '',
    parts: String(ed.parts || 4),
    poidsCuit: ed.poids_cuit ? String(ed.poids_cuit) : '',
    items: (ed.ingredients || []).map(function (i) { return ingredient(i, i.grams); }),
    q: '',
    results: [],
    offResults: [],
    offBusy: false,
    offError: '',
    offFor: '',
    // Un nom tapé avant qu'Alpine démarre (réseau lent) n'est pas effacé.
    init() {
      var champ = this.$refs.nom;
      if (champ && champ.value && !this.nom) this.nom = champ.value;
    },
    search() {
      this.offResults = []; this.offError = ''; this.offFor = '';
      this.results = chercherAliments(POOL_INGREDIENTS, this.q, 8);
    },
    pickFood(f) {
      var portion = (f.u && f.u.length) ? f.u[0][1] : 100;
      this.items.push(ingredient(f, portion));
      this.q = ''; this.results = []; this.offResults = []; this.offError = ''; this.offFor = '';
    },
    retirer(idx) { this.items.splice(idx, 1); },
    libelleUnite(u) { return u[0] === 'g' ? 'g' : u[0] + ' (' + u[1] + ' g)'; },
    kcalFor(f, grams) { return Math.round(f.k * grams / 100); },
    arrondi(x) { return Math.round(x); },
    grams(b) { return (parseFloat(b.qty) || 0) * b.unites[b.u][1]; },
    macro(b, key) { return b.food[key] * this.grams(b) / 100; },
    total(key) {
      var self = this;
      return Math.round(this.items.reduce(function (s, b) { return s + self.macro(b, key); }, 0));
    },
    nbParts() {
      var n = parseInt(this.parts, 10);
      return n >= 1 && n <= 50 ? n : 0;
    },
    parPart(key) { return this.nbParts() ? Math.round(this.total(key) / this.nbParts()) : 0; },
    // Poids d'une part : sur le plat cuit s'il est pesé, sinon sur la somme
    // des ingrédients (comme le serveur).
    poidsPart() {
      var base = parseFloat(this.poidsCuit) || this.items.reduce(function (s, b) {
        return s + (parseFloat(b.qty) || 0) * b.unites[b.u][1];
      }, 0);
      return this.nbParts() ? Math.round(base / this.nbParts()) : 0;
    },
    peutEnregistrer() {
      return this.nom.trim().length > 0 && this.items.length > 0 && this.nbParts() > 0;
    },
    ingredientsJson() {
      var self = this;
      return JSON.stringify(this.items.map(function (b) {
        var f = b.food;
        return { n: f.n, k: f.k, p: f.p, c: f.c, f: f.f, brand: f.brand || '', code: f.code || '',
                 u: b.unites.slice(1), grams: Math.round(self.grams(b) * 10) / 10 };
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
          self.offError = 'Pas de réseau — réessaie dans un instant.';
        });
    },
  };
}
