/**
 * Modale « fiche exercice » de l'écran de séance.
 *
 * Contenu : muscles ciblés sur une mini-carte du corps, exécution, conseils,
 * et la table des maxima (RM) calculée depuis le 1RM estimé de l'exercice.
 *
 * Les polygones du corps arrivent par <script type="application/json"
 * id="body-polygons"> (ils pèsent ~10 Ko et n'ont pas à être dans le HTML).
 */
(function () {
  "use strict";

  window.__BODY_POLYGONS__ = (function () {
    var el = document.getElementById("body-polygons");
    if (!el) return {};
    try { return JSON.parse(el.textContent || "{}"); } catch (e) { return {}; }
  })();

  

  // Les descriptions d'exos utilisent des libellés détaillés ("Pectoraux (haut)",
  // "Épaules antérieures", "Dos (grand dorsal)"…). On normalise vers les noms
  // canoniques de la carte du corps via la sous-chaîne présente dans le libellé.
  var MUSCLE_ALIASES = [
    { needle: "pector", canonical: "Pecs" },
    { needle: "pec ",   canonical: "Pecs" },
    { needle: "dos",    canonical: "Dos" },
    { needle: "dorsal", canonical: "Dos" },
    { needle: "rhombo", canonical: "Dos" },
    { needle: "trapèz", canonical: "Dos" },
    { needle: "lombai", canonical: "Dos" },
    { needle: "épaul",  canonical: "Épaules" },
    { needle: "deltoï", canonical: "Épaules" },
    { needle: "biceps", canonical: "Biceps" },
    { needle: "triceps", canonical: "Triceps" },
    { needle: "avant-bras", canonical: "Avant-bras" },
    { needle: "forearm", canonical: "Avant-bras" },
    { needle: "abdo",   canonical: "Abdos" },
    { needle: "oblique",canonical: "Abdos" },
    { needle: "quadri", canonical: "Quadriceps" },
    { needle: "ischio", canonical: "Ischio-jambiers" },
    { needle: "hamstring", canonical: "Ischio-jambiers" },
    { needle: "fessi",  canonical: "Fessiers" },
    { needle: "glute",  canonical: "Fessiers" },
    { needle: "mollet", canonical: "Mollets" },
    { needle: "soléai", canonical: "Mollets" },
    { needle: "adduct", canonical: "Adducteurs" },
    { needle: "abduct", canonical: "Abducteurs" },
  ];
  function normalizeMuscles(list) {
    var out = {};
    (list || []).forEach(function (raw) {
      var s = String(raw || "").toLowerCase();
      MUSCLE_ALIASES.forEach(function (a) {
        if (s.indexOf(a.needle) >= 0) out[a.canonical] = true;
      });
    });
    return Object.keys(out);
  }

  // Construit un <svg> mini montrant les muscles visés en accent, le reste grisé.
  // view = 'anterior' | 'posterior'. muscles = liste de noms FR canoniques.
  function buildMiniBodySvg(view, muscles) {
    var data = window.__BODY_POLYGONS__ || {};
    var side = (view === 'posterior') ? 'posterior' : 'anterior';
    var allMuscles = data[side] || {};
    var neutralPolys = data[side + '_neutral'] || [];
    var accent = '#FF9F0A';
    var dim = 'rgba(255,255,255,0.06)';
    var stroke = 'rgba(255,255,255,0.12)';

    var svg = '<svg viewBox="0 0 100 220" width="100" class="mini-body-svg" xmlns="http://www.w3.org/2000/svg">';
    // Silhouette neutre (tête, cou, etc.)
    neutralPolys.forEach(function (pts) {
      svg += '<polygon points="' + pts + '" fill="' + dim + '" stroke="' + stroke + '" stroke-width="0.3"/>';
    });
    // Muscles
    Object.keys(allMuscles).forEach(function (m) {
      var isTarget = muscles && muscles.indexOf(m) >= 0;
      var fill = isTarget ? accent : dim;
      var sw = isTarget ? 0.5 : 0.3;
      allMuscles[m].forEach(function (pts) {
        svg += '<polygon points="' + pts + '" fill="' + fill + '" stroke="' + stroke + '" stroke-width="' + sw + '"' + (isTarget ? ' opacity="0.92"' : ' opacity="0.7"') + '/>';
      });
    });
    svg += '</svg>';
    return svg;
  }

  // ── Exercise info modal (Feature 8) ────────────────────────────
  function showExoInfo(info) {
    document.getElementById('exo-info-title').textContent = info.name || '';
    // Image
    var imgEl = document.getElementById('exo-info-image');
    if (info.image) {
      imgEl.innerHTML = '<img src="/static/img/exercises/' + info.image + '" alt="" style="width:80px; height:80px; opacity:0.85;">';
    } else {
      imgEl.innerHTML = '';
    }
    // Muscles as colored tags
    var musclesEl = document.getElementById('exo-info-muscles');
    var muscleList = [];
    if (Array.isArray(info.muscles)) {
      muscleList = info.muscles.filter(Boolean);
      musclesEl.innerHTML = muscleList.map(function(m) {
        return '<span style="font-size:0.75rem; padding:2px 8px; border-radius:8px; background:rgba(255,159,10,0.12); border:1px solid rgba(255,159,10,0.4); color:#FF9F0A;">' + m + '</span>';
      }).join('');
    } else {
      musclesEl.innerHTML = '<span style="font-size:0.85rem; color:var(--text);">' + (info.muscles || '') + '</span>';
      muscleList = String(info.muscles || '').split(',').map(function(s){return s.trim();}).filter(Boolean);
    }

    // Mini-carte anatomique : on affiche les 2 vues (face + dos) avec
    // les muscles visés en orange.
    var bmEl = document.getElementById('exo-info-bodymap');
    if (bmEl) {
      var canonical = normalizeMuscles(muscleList);
      bmEl.innerHTML = buildMiniBodySvg('anterior', canonical) + buildMiniBodySvg('posterior', canonical);
    }
    // Description
    document.getElementById('exo-info-desc').textContent = info.description || '';
    // Tips as list
    var tipsEl = document.getElementById('exo-info-tips');
    var tipsSection = document.getElementById('exo-info-tips-section');
    if (Array.isArray(info.tips) && info.tips.length) {
      tipsEl.innerHTML = info.tips.map(function(t) { return '<li>' + t + '</li>'; }).join('');
      tipsSection.style.display = '';
    } else if (info.tips && typeof info.tips === 'string') {
      tipsEl.innerHTML = '<li>' + info.tips + '</li>';
      tipsSection.style.display = '';
    } else {
      tipsSection.style.display = 'none';
    }

    // Lien coach pré-rempli avec le nom de l'exercice
    var coachLink = document.getElementById('exo-info-coach-link');
    if (coachLink) {
      var exoName = info.name || '';
      var q = 'Comment progresser au ' + exoName + ' ?';
      coachLink.href = '/coach?q=' + encodeURIComponent(q);
    }

    // Table RM — remplit la 2e tab depuis info.one_rm
    var oneRM = parseFloat(info.one_rm || 0) || 0;
    var rmEmpty = document.getElementById('exo-rm-empty');
    var rmContent = document.getElementById('exo-rm-content');
    if (oneRM > 0) {
      rmEmpty.style.display = 'none';
      rmContent.style.display = '';
      document.getElementById('exo-rm-value').textContent = Math.round(oneRM * 10) / 10;
      var reps = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20];
      var tbody = document.getElementById('exo-rm-rows');
      tbody.innerHTML = reps.map(function (r) {
        var w = oneRM / (1 + r / 30);
        var pct = Math.round(w / oneRM * 100);
        var cls = r === 1 ? 'rm-row-max' : '';
        return '<tr class="' + cls + '"><td><strong>' + r + ' rep' + (r > 1 ? 's' : '') + '</strong></td><td>' + (Math.round(w * 10) / 10) + ' kg</td><td>' + pct + '%</td></tr>';
      }).join('');
    } else {
      rmEmpty.style.display = '';
      rmContent.style.display = 'none';
    }

    // Revient toujours sur la Fiche en ouvrant le modal
    switchExoTab('fiche');
    document.getElementById('exo-info-modal').style.display = 'flex';
  }

  function switchExoTab(tab) {
    var tabs = document.querySelectorAll('.exo-info-tab');
    tabs.forEach(function (t) {
      t.classList.toggle('active', t.getAttribute('data-tab') === tab);
    });
    document.getElementById('exo-tab-fiche').style.display = (tab === 'fiche') ? '' : 'none';
    document.getElementById('exo-tab-rm').style.display = (tab === 'rm') ? '' : 'none';
  }
  // Exposé pour les attributs onclick du gabarit de la modale.
  window.showExoInfo = showExoInfo;
  window.switchExoTab = switchExoTab;
})();
