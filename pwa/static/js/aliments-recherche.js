// Recherche d'aliments, partagée par le repas (nutrition.js) et les recettes
// (recettes.js) : accents et casse ignorés, début de mot avant milieu de mot,
// aliment simple avant plat, cuit avant cru — sauf si l'on tape « cru ».
// Hors des composants Alpine : pas besoin de réactivité sur 400 entrées.
// « œ » et « æ » ne se décomposent pas : « oeuf » doit trouver « Œuf entier ».
function foodNorm(s) {
  return (s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/\u0153/g, 'oe').replace(/\u00e6/g, 'ae');
}

// Réunit des listes d'aliments. Un nom déjà donné par une liste précédente
// n'est pas repris : un récent garde la quantité de la dernière fois, une
// recette ses valeurs actuelles, avant l'aliment moyen du même nom.
function poolAliments(listes) {
  var vus = {}, out = [];
  listes.forEach(function (liste) {
    var noms = {};
    (liste || []).forEach(function (f) {
      f._n = foodNorm(f.n);
      if (vus[f._n]) return;
      noms[f._n] = true;
      out.push(f);
    });
    Object.keys(noms).forEach(function (n) { vus[n] = true; });
  });
  return out;
}

function chercherAliments(pool, q, n) {
  var words = foodNorm(q).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  var cru = /\bcru/.test(foodNorm(q));
  var scored = [];
  for (var i = 0; i < pool.length; i++) {
    var f = pool[i], ok = true, score = 0;
    for (var w = 0; w < words.length; w++) {
      var pos = f._n.indexOf(words[w]);
      if (pos < 0) { ok = false; break; }
      // Début de mot (nom ou mot interne) = 0, milieu de mot = 3.
      score += (pos === 0 || f._n[pos - 1] === ' ' ? 0 : 3) + pos / 100;
    }
    // « riz » → le riz cuit avant le riz cru (pesé cru, c'est l'exception).
    if (ok && / crue?s?\b/.test(f._n) && !cru) score += 0.5;
    if (ok) scored.push([score, f]);
  }
  // Début de mot > milieu de mot ; mes aliments (r=−2), récents (−1), simples
  // (0) puis plats et snacks (1) ; puis nom court.
  scored.sort(function (a, b) {
    return Math.floor(a[0]) - Math.floor(b[0]) || a[1].r - b[1].r || a[0] - b[0]
      || a[1].n.length - b[1].n.length || a[1].n.localeCompare(b[1].n);
  });
  return scored.slice(0, n || 8).map(function (x) { return x[1]; });
}
