// Animation de la vidéo promo PRO. Tout est fonction du temps : seek(t)
// place chaque élément et dessine la 3D pour l'instant t, sans horloge.
// Deux rendus du même t donnent la même image — c'est ce qui permet à
// rendre.py de photographier la vidéo image par image, sans à-coups.
import * as THREE from './node_modules/three/build/three.module.js';

const W = 720, H = 1280;

// ── Temps ────────────────────────────────────────────────────────
const borne = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lin = (t, a, b) => borne((t - a) / (b - a));
const E = {
  out: x => 1 - Math.pow(1 - x, 3),
  in: x => x * x * x,
  inOut: x => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  inOut5: x => (x < 0.5 ? 16 * Math.pow(x, 5) : 1 - Math.pow(-2 * x + 2, 5) / 2),
  expo: x => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),
  back: x => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); },
};
const p = (t, a, b, e = E.out) => e(lin(t, a, b));
const mix = (a, b, k) => a + (b - a) * k;
const mixLog = (a, b, k) => Math.exp(mix(Math.log(a), Math.log(b), k));  // zoom régulier à l'œil
const fr = (n, d = 0) => n.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d }).replace(/[  ]/g, ' ');
const $ = s => document.querySelector(s);

// ── Montage ──────────────────────────────────────────────────────
// [plan, durée avant la transition suivante, durée de cette transition].
// Pendant une transition, les deux plans sont à l'écran. Chaque passage est
// différent et vient du contenu, pour ne pas faire défiler des diapos.
const PLANS = [
  ['s1', 3.0, 1.0],   // accroche → plongée dans le point du « ? », dont le vert devient la barre de l'haltère
  ['s2', 3.0, 0.9],   // marque → l'haltère passe au-dessus de la caméra, le téléphone sort de la profondeur
  ['s3', 5.0, 0.9],   // coach IA → la bulle du coach grandit et devient la carte du debrief
  ['s4', 3.9, 0.8],   // debrief → panoramique filé vers la gauche
  ['s5', 3.9, 0.9],   // force → rotation de cube
  ['s6', 3.8, 0.9],   // carte musculaire → la nutrition s'ouvre en cercle depuis les pectoraux
  ['s7', 3.8, 0.9],   // nutrition → la carte tombe, les programmes arrivent d'en haut
  ['s8', 3.6, 0.9],   // programmes → le bloc vert « Générateur IA » envahit l'écran
  ['s9', 3.0, 1.0],   // et aussi, sur fond vert → on ressort de la lettre P de « PRO »
  ['s10', 4.4, 0],    // appel à l'action
];
const SCENES = [];
let debut = 0;
for (const [id, L, T] of PLANS) {
  SCENES.push({ id, el: document.getElementById(id), debut, L, fin: debut + L + T, centre: [W / 2, H / 2] });
  debut += L;
}
export const DUREE = debut;
const S = Object.fromEntries(SCENES.map(s => [s.id, s]));
const K = {};   // avancement (0 → 1) de la transition qui suit chaque plan

// ── 3D ───────────────────────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ canvas: $('#gl'), antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene3d = new THREE.Scene();
scene3d.background = new THREE.Color('#000000');
const camera = new THREE.PerspectiveCamera(35, W / H, 0.1, 200);
camera.position.set(0, 0, 12);
const HAUTEUR_VUE = 2 * 12 * Math.tan(THREE.MathUtils.degToRad(17.5));
const PX = H / HAUTEUR_VUE;                     // pixels par unité, plan z = 0
const versMonde = (px, py) => [(px - W / 2) / PX, (H / 2 - py) / PX];

scene3d.add(new THREE.HemisphereLight(0xffffff, 0x0a0a0a, 0.9));
const cle = new THREE.DirectionalLight(0xffffff, 2.4);
cle.position.set(4, 6, 9);
scene3d.add(cle);
const contre = new THREE.DirectionalLight(0xffffff, 1.4);
contre.position.set(-7, -3, -5);
scene3d.add(contre);

// L'haltère de l'icône de l'app, en volume. Même géométrie que
// pwa/tools/dessiner_icone.py (grille de 512) : disques épais, barre fine.
const HALTERE = [
  [86, 234, 20, 44, 4], [112, 178, 38, 156, 6], [158, 142, 42, 228, 6],
  [200, 243, 112, 26, 0],
  [312, 142, 42, 228, 6], [362, 178, 38, 156, 6], [406, 234, 20, 44, 4],
];
function rectArrondi(x, y, l, h, r) {
  const s = new THREE.Shape();
  r = Math.max(r, 0.01);
  s.moveTo(x + r, y);
  s.lineTo(x + l - r, y); s.quadraticCurveTo(x + l, y, x + l, y + r);
  s.lineTo(x + l, y + h - r); s.quadraticCurveTo(x + l, y + h, x + l - r, y + h);
  s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
  return s;
}
const matiere = new THREE.MeshStandardMaterial({ color: new THREE.Color('#c8f031'), roughness: 0.38, metalness: 0.12 });
const haltere = new THREE.Group();
// Chaque pièce est centrée sur elle-même, pour pouvoir la faire grandir.
const pieces = HALTERE.map(([x, y, l, h, r]) => {
  const barre = r === 0;
  const prof = barre ? 26 : (h > 200 ? 64 : 50);
  const g = new THREE.ExtrudeGeometry(rectArrondi(-l / 2, -h / 2, l, h, r), { depth: prof, bevelEnabled: true, bevelThickness: 3, bevelSize: 2.5, bevelSegments: 3, curveSegments: 8 });
  g.translate(0, 0, -prof / 2);
  const m = new THREE.Mesh(g, matiere);
  m.position.set(x + l / 2 - 256, 256 - (y + h / 2), 0);
  haltere.add(m);
  return m;
});
const pivot = new THREE.Group();
pivot.add(haltere);
scene3d.add(pivot);
const LARGEUR_HALTERE = 340;  // en unités de la grille de 512

// Sol en perspective, qui défile doucement : la profondeur du décor.
// Il suit aussi les mouvements de caméra des transitions (filé, cube).
const sol = new THREE.GridHelper(80, 64, 0x1c1c1c, 0x141414);
sol.position.set(0, -6.2, -10);
scene3d.add(sol);

function placerHaltere(px, py, largeurPx, rx, ry, rz = 0, dy = 0, dz = 0) {
  const [x, y] = versMonde(px, py);
  pivot.position.set(x, y + dy, dz);
  pivot.scale.setScalar((largeurPx / PX) / LARGEUR_HALTERE);
  pivot.rotation.set(rx, ry, rz);
}

// ── Contenus construits une fois ─────────────────────────────────
const NS = 'http://www.w3.org/2000/svg';
const el = (nom, attrs, parent) => {
  const e = document.createElementNS(NS, nom);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
};

// 1 — la courbe plate de la stagnation
const plat = $('#plat');
for (let i = 0; i < 4; i++) el('line', { x1: 0, x2: 624, y1: 20 + i * 45, y2: 20 + i * 45, stroke: '#1a1a1a', 'stroke-width': 1 }, plat);
const PLAT_X = [20, 136, 252, 368, 484, 600];
const platChemin = el('path', { d: 'M' + PLAT_X.map(x => `${x} 95`).join(' L'), fill: 'none', stroke: '#858585', 'stroke-width': 4 }, plat);
const platPoints = PLAT_X.map(x => el('circle', { cx: x, cy: 95, r: 8, fill: '#858585' }, plat));
const platLabels = PLAT_X.map((x, i) => { const t = el('text', { x, y: 180, fill: '#585858', 'font-size': 20, 'text-anchor': 'middle', 'font-family': 'Barlow Condensed', 'font-weight': 600 }, plat); t.textContent = 'S' + (i + 1); return t; });

// 3 — conversation avec le coach
const MOI = 'Je stagne au développé couché. Je fais quoi ?';
const COACH = [['Tu', 0], ['es', 0], ['à', 0], ['80 kg × 8', 1], ['depuis', 0], ['3', 0], ['séances.', 0], ['Passe', 0], ['à', 0], ['4 × 6', 1], ['à', 0], ['82,5 kg,', 1], ['puis', 0], ['ajoute', 0], ['une', 0], ['rep', 0], ['par', 0], ['séance.', 0]];
// Les groupes en gras ne se coupent pas en fin de ligne (« 82,5 | kg »).
const texteCoach = n => COACH.slice(0, n).map(([w, b]) => (b ? `<b>${w.replace(/ /g, ' ')}</b>` : w)).join(' ');

// 5 — courbe de force
const FORCE = [87, 87.5, 89, 88, 91, 90.5, 93, 95, 94, 97.5, 100, 102.5];
const courbe = $('#courbe');
const CX = i => 16 + i * (540 / (FORCE.length - 1));
const CY = v => 270 - (v - 84) / (104 - 84) * 240;
for (let i = 0; i < 4; i++) el('line', { x1: 0, x2: 572, y1: 30 + i * 80, y2: 30 + i * 80, stroke: '#262626', 'stroke-width': 1 }, courbe);
const forceChemin = el('path', { d: 'M' + FORCE.map((v, i) => `${CX(i)} ${CY(v)}`).join(' L'), fill: 'none', stroke: '#f2f2f2', 'stroke-width': 4, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, courbe);
let maxi = 0;
const records = [];
FORCE.forEach((v, i) => { if (v > maxi) { maxi = v; if (i > 0) records.push(i); } });
const forcePoints = FORCE.map((v, i) => el('circle', { cx: CX(i), cy: CY(v), r: records.includes(i) ? 9 : 5, fill: records.includes(i) ? '#c8f031' : '#f2f2f2' }, courbe));

// 6 — carte musculaire (polygones de l'app : pwa/core/body_map.py)
const INTENSITE = { 'Pecs': 1, 'Épaules': 0.85, 'Triceps': 0.7, 'Biceps': 0.6, 'Abdos': 0.45, 'Quadriceps': 0.9,
  'Dos': 0.95, 'Trapèzes': 0.6, 'Ischio-jambiers': 0.55, 'Fessiers': 0.7, 'Mollets': 0.35, 'Avant-bras': 0.3, 'Lombaires': 0.4 };
const zones = [];   // [{muscle, polys[], cote}]
let musclesConnus = [];

// 8 — programmes PRO (noms réels du catalogue, pwa/core/catalog.py)
const PROGRAMMES = [
  ['PPL avancé · 6 jours', 'Force et hypertrophie en alternance'],
  ['5 × 5 force', 'Squat, couché, soulevé de terre'],
  ['Force athlétique · 4 jours', 'Un jour par mouvement principal'],
  ['Spécialisation bras', 'Biceps et triceps en priorité'],
  ['Spécial fessiers · 4 jours', 'Deux séances fessiers par semaine'],
  ['Sèche musculation · 5 jours', 'Volume élevé et finishers cardio'],
];
const pile = $('#s8-pile');
const cartesProg = PROGRAMMES.map(([n, s], i) => {
  const d = document.createElement('div');
  d.className = 'prog';
  d.style.top = (i * 100) + 'px';
  d.innerHTML = `<div class="cond">${n}</div><div class="s">${s}</div><span class="pro">PRO</span>`;
  pile.appendChild(d);
  return d;
});

async function chargerCorps() {
  const corps = await (await fetch('body.json')).json();
  const dessiner = (svg, muscles, neutres, cote) => {
    for (const pts of neutres) el('polygon', { points: pts, fill: '#1a1a1a', stroke: '#262626', 'stroke-width': 0.3 }, svg);
    for (const [m, polys] of Object.entries(muscles)) {
      const ps = polys.map(pts => el('polygon', { points: pts, fill: '#1a1a1a', stroke: '#262626', 'stroke-width': 0.3 }, svg));
      zones.push({ muscle: m, polys: ps, cote });
    }
  };
  dessiner($('#corps-face'), corps.anterior, corps.anterior_neutral, 'face');
  dessiner($('#corps-dos'), corps.posterior, corps.posterior_neutral, 'dos');
  musclesConnus = [...new Set(zones.map(z => z.muscle))];
}

// Repères mesurés une fois la page en place (voir mesurer).
let BULLE, CARTE, PECS, BARRE, POINT_Q, TIGE_P;

// ── Outils d'animation ───────────────────────────────────────────
function reveler(spans, t0, loc, pas = 0.08, duree = 0.55) {
  spans.forEach((s, i) => {
    const k = p(loc, t0 + i * pas, t0 + i * pas + duree, E.expo);
    s.style.transform = `translateY(${(1 - k) * 112}%)`;
  });
}
// Titre d'un plan : entre ligne par ligne, et peut ressortir par le haut.
function titre(s, loc, entree, sortie = null, dureeSortie = 0.4) {
  s.el.querySelectorAll('.titre .masque > span').forEach((e, i) => {
    const a = p(loc, entree + i * 0.1, entree + i * 0.1 + 0.7, E.expo);
    const b = sortie === null ? 0 : p(loc, sortie + i * 0.05, sortie + i * 0.05 + dureeSortie, E.in);
    e.style.transform = `translateY(${(1 - a) * 112 - b * 112}%)`;
  });
}
function poser(e, { x = 0, y = 0, s = 1, o = 1, rx = 0, ry = 0, rz = 0, z = 0 } = {}) {
  e.style.transform = `translate3d(${x}px, ${y}px, ${z}px) rotateX(${rx}deg) rotateY(${ry}deg) rotateZ(${rz}deg) scale(${s})`;
  e.style.opacity = o;
}
// Une transformation appliquée autour d'un point de l'écran.
const autour = ([x, y], f) => `translate(${x}px, ${y}px) ${f} translate(${-x}px, ${-y}px)`;
// Le plan vu comme la face d'un cube de 720 px de côté, tourné de a degrés.
const cube = a => autour([W / 2, 0], `translateZ(${-W / 2}px) rotateY(${a}deg) translateZ(${W / 2}px)`);
// Flou de bougé horizontal du panoramique filé, maximal à mi-course.
const FLOU = $('#flou-h');
function flouFile(s, k) {
  const b = 30 * Math.pow(Math.sin(Math.PI * k), 2);
  if (b < 0.3) return;
  FLOU.setAttribute('stdDeviation', `${b.toFixed(2)} 0`);
  s.el.style.filter = 'url(#flou)';
}
function rect(e, { x, y, w, h }) {
  Object.assign(e.style, { left: x + 'px', top: y + 'px', width: w + 'px', height: h + 'px' });
}
const mixRect = (a, b, k) => ({ x: mix(a.x, b.x, k), y: mix(a.y, b.y, k), w: mix(a.w, b.w, k), h: mix(a.h, b.h, k) });
const vert = new THREE.Color('#c8f031'), fond = new THREE.Color('#1a1a1a');
const teinte = k => '#' + fond.clone().lerp(vert, k).getHexString();
const teinteEntre = (a, b, k) => '#' + new THREE.Color(a).lerp(new THREE.Color(b), k).getHexString();

// ── Une image ────────────────────────────────────────────────────
function seek(t) {
  for (const s of SCENES) {
    K[s.id] = lin(t, s.debut + s.L, s.fin);
    s.actif = t >= s.debut && t < s.fin;
    s.el.style.display = s.actif ? 'block' : 'none';
    Object.assign(s.el.style, { opacity: 1, visibility: 'visible', clipPath: 'none', filter: 'none', background: '' });
    s.xf = '';
  }
  for (const id of ['#plein', '#morph', '#anneau']) $(id).style.display = 'none';
  for (const s of SCENES) {
    if (!s.actif) continue;
    const loc = t - s.debut;
    MAJ[s.id](loc, s.L, s);
    // Léger travelling avant pendant tout le plan : rien n'est jamais figé.
    const d = s.derive === false ? '' : autour(s.centre, `scale(${1 + 0.03 * lin(loc, 0, s.fin - s.debut)})`);
    s.el.style.transform = `${s.xf} ${d}`.trim() || 'none';
  }

  sol.position.z = -10 + ((t * 1.3) % (80 / 64));
  sol.position.x = -5 * E.inOut5(K.s4);                // la caméra file avec le panoramique
  sol.rotation.y = -Math.PI / 2 * E.inOut(K.s5);       // et tourne avec le cube (grille identique à 90°)
  haltere3D(t);
  renderer.render(scene3d, camera);
}

function haltere3D(t) {
  const l2 = t - S.s2.debut, l10 = t - S.s10.debut;
  pieces.forEach(m => { m.scale.setScalar(1); m.visible = true; });
  if (l2 >= 0.9 && t < S.s2.fin) {
    // Les disques poussent autour de la barre verte, du centre vers les bouts.
    const ordre = [2, 1, 0, null, 0, 1, 2];
    pieces.forEach((m, i) => {
      if (ordre[i] === null) return;
      const a = E.back(lin(l2, 0.92 + ordre[i] * 0.09, 1.3 + ordre[i] * 0.09));
      m.scale.setScalar(Math.max(a, 0.001));
      m.visible = a > 0.001;
    });
    const tour = E.inOut(lin(l2, 1.15, 2.55));
    const flotte = Math.sin((l2 - 2.55) * 2.2) * 0.16 * lin(l2, 2.55, 3.0);
    const f = E.in(K.s2);   // sortie : passe au-dessus de la caméra
    placerHaltere(360, 560, 540,
      0.2 * p(l2, 1.15, 2.2) + 1.3 * f,
      2 * Math.PI * tour + 0.22 * p(l2, 1.9, 2.6) + flotte + 0.9 * f,
      0, 3.6 * f, 8 * f);
    pivot.visible = true;
  } else if (l10 >= 0.9) {
    const k = p(l10, 0.9, 1.8, E.expo);
    placerHaltere(360, mix(1600, 390, k), 380, mix(1.2, 0.16, k), mix(3 * Math.PI, 0, k) + Math.sin(l10 * 1.7) * 0.32 * lin(l10, 1.7, 2.2));
    pivot.visible = true;
  } else {
    pivot.visible = false;
  }
}

const MAJ = {
  s1(loc, L, s) {
    s.centre = POINT_Q;
    reveler([...$('#hook').querySelectorAll('.masque > span')], 0.15, loc, 0.3, 0.7);
    const k = p(loc, 1.2, 2.2, E.inOut);
    const longueur = 580;
    platChemin.style.strokeDasharray = longueur;
    platChemin.style.strokeDashoffset = longueur * (1 - k);
    platPoints.forEach((c, i) => { const a = lin(k, i / 5 - 0.02, i / 5 + 0.08); c.setAttribute('r', 8 * a); });
    platLabels.forEach((l, i) => l.setAttribute('opacity', lin(k, i / 5 - 0.05, i / 5 + 0.1)));
    poser($('#s1-sous'), { y: 20 * (1 - p(loc, 2.0, 2.5)), o: p(loc, 2.0, 2.5) });
    // Sortie : la caméra plonge dans le point du « ? » jusqu'à ce que son
    // vert remplisse l'écran.
    const z = lin(K.s1, 0, 0.5);
    if (z > 0) s.xf = autour(POINT_Q, `scale(${mixLog(1, 110, z * z)})`);
    if (K.s1 >= 0.5) s.el.style.visibility = 'hidden';
  },
  s2(loc, L, s) {
    s.derive = false;
    // Entrée : l'écran vert se resserre jusqu'à la barre de l'haltère ;
    // les disques 3D poussent ensuite autour (haltere3D).
    const plein = $('#plein');
    if (loc >= 0.48 && loc < 0.97) {
      plein.style.display = 'block';
      rect(plein, mixRect({ x: 0, y: 0, w: W, h: H }, BARRE, p(loc, 0.5, 0.95, E.inOut)));
    }
    reveler([...$('#s2-nom').querySelectorAll('.masque > span')], 1.7, loc, 0.08, 0.7);
    const k = p(loc, 2.1, 2.55, E.back);
    $('#s2-pro').style.transform = `translateX(-50%) scale(${mix(0.4, 1, k)})`;
    $('#s2-pro').style.opacity = lin(loc, 2.1, 2.25);
    // Sortie : poussée de caméra, le texte grossit et s'efface.
    const f = E.in(K.s2);
    if (f > 0) {
      s.xf = autour([W / 2, 880], `scale(${1 + 0.9 * f})`);
      s.el.style.opacity = 1 - lin(K.s2, 0, 0.6);
    }
  },
  s3(loc, L, s) {
    // Entrée : le téléphone sort de la profondeur pendant que l'haltère passe.
    if (loc < 1.1) {
      s.xf = autour([W / 2, 800], `scale(${mix(0.55, 1, p(loc, 0.3, 1.1, E.out))})`);
      s.el.style.opacity = lin(loc, 0.3, 0.6);
    }
    titre(s, loc, 0.6, L);
    const k = p(loc, 0.3, 1.2, E.out);
    const aplat = p(loc, L - 0.5, L, E.inOut);   // se remet à plat avant que la bulle s'envole
    const chute = p(loc, L, L + 0.6, E.in);       // puis bascule en arrière
    poser($('#s3-tel'), {
      y: mix(260, 0, k) + 320 * chute, z: mix(-300, 0, k),
      rx: mix(28, 7, k) * (1 - aplat) + 55 * chute,
      ry: (mix(-34, -12, k) + 8 * lin(loc, 1.2, 4.5)) * (1 - aplat),
      s: 1 - 0.2 * chute, o: 1 - chute,
    });
    const n = Math.round(MOI.length * lin(loc, 1.3, 2.3));
    $('#s3-moi').textContent = MOI.slice(0, n);
    $('#s3-moi').style.visibility = n ? 'visible' : 'hidden';
    const attente = loc >= 2.4 && loc < 2.9;
    $('#s3-points').style.display = attente ? 'block' : 'none';
    if (attente) [...$('#s3-points').children].forEach((d, i) => { d.style.opacity = 0.35 + 0.65 * Math.max(0, Math.sin((loc - 2.4) * 12 - i * 0.9)); });
    const m = Math.round(COACH.length * lin(loc, 2.9, 4.1));
    $('#s3-coach').style.display = m ? 'block' : 'none';
    $('#s3-coach').style.visibility = loc >= L ? 'hidden' : 'visible';   // #morph prend le relais
    $('#s3-coach').innerHTML = texteCoach(m);
  },
  s4(loc, L, s) {
    // Entrée : la bulle du coach grandit et devient la carte du debrief.
    const morph = $('#morph');
    if (loc < 0.8) {
      const m = p(loc, 0, 0.75, E.inOut);
      morph.style.display = 'block';
      rect(morph, mixRect(BULLE, CARTE, m));
      morph.style.background = teinteEntre('#1a1a1a', '#111111', m);
      morph.firstChild.style.opacity = 1 - lin(loc, 0, 0.22);
    }
    $('#s4-carte').style.opacity = loc >= 0.75 ? 1 : 0;
    $('#s4-entete').style.opacity = lin(loc, 0.75, 1.0);
    $('#s4-chiffres').style.opacity = lin(loc, 0.8, 1.05);
    titre(s, loc, 0.45);
    const c = p(loc, 0.9, 1.9);
    $('#s4-series').textContent = Math.round(18 * c);
    $('#s4-volume').textContent = fr(Math.round(7420 * c / 10) * 10);
    $('#s4-gain').textContent = '+' + Math.round(6 * c) + ' %';
    ['#s4-l1', '#s4-l2', '#s4-l3'].forEach((id, i) => {
      const a = p(loc, 1.5 + i * 0.35, 1.95 + i * 0.35, E.out);
      poser($(id), { x: 70 * (1 - a), o: a });
    });
    // Sortie : panoramique filé vers la gauche.
    const w = E.inOut5(K.s4);
    if (w > 0) { s.xf = `translateX(${-W * w}px)`; flouFile(s, w); }
  },
  s5(loc, L, s) {
    const w = E.inOut5(K.s4);
    if (w < 1) { s.xf = `translateX(${W * (1 - w)}px)`; flouFile(s, w); }
    titre(s, loc, -1);
    const k = p(loc, 0.8, 2.4, E.out);
    $('#s5-val').textContent = fr(mix(87, 102.5, k), 1);
    const longueur = forceChemin.getTotalLength();
    forceChemin.style.strokeDasharray = longueur;
    forceChemin.style.strokeDashoffset = longueur * (1 - k);
    forcePoints.forEach((c, i) => {
      const a = E.back(lin(k, i / (FORCE.length - 1) - 0.03, i / (FORCE.length - 1) + 0.06));
      c.setAttribute('transform', `translate(${CX(i)} ${CY(FORCE[i])}) scale(${a}) translate(${-CX(i)} ${-CY(FORCE[i])})`);
    });
    poser($('#s5-gain'), { x: 30 * (1 - p(loc, 2.3, 2.7)), o: p(loc, 2.3, 2.7) });
    // Sortie : le plan tourne comme la face d'un cube.
    const c = E.inOut(K.s5);
    if (c > 0) { s.xf = cube(-90 * c); s.el.style.opacity = 1 - 0.7 * c; }
  },
  s6(loc, L, s) {
    s.centre = PECS;
    const c = E.inOut(K.s5);
    if (c < 1) { s.xf = cube(90 * (1 - c)); s.el.style.opacity = 0.3 + 0.7 * c; }
    titre(s, loc, -1);
    let allumes = 0;
    zones.forEach(z => {
      const i = musclesConnus.indexOf(z.muscle);
      const a = p(loc, 1.0 + i * 0.12, 1.35 + i * 0.12);
      if (a > 0.5) allumes = Math.max(allumes, i + 1);
      const couleur = teinte(a * (INTENSITE[z.muscle] ?? 0.5));
      z.polys.forEach(pl => pl.setAttribute('fill', couleur));
    });
    $('#s6-compte').textContent = `${allumes} groupes travaillés`;
    // Sortie : la caméra avance vers les pectoraux, d'où s'ouvre le plan suivant.
    const z = E.inOut(K.s6);
    if (z > 0) { s.xf = autour(PECS, `scale(${1 + 0.45 * z})`); s.el.style.opacity = 1 - 0.6 * z; }
  },
  s7(loc, L, s) {
    // Entrée : ouverture en cercle, cerclée de vert, depuis les pectoraux.
    const o = E.inOut(K.s6);
    if (o < 1) {
      const r = 1500 * o;
      s.el.style.clipPath = `circle(${r}px at ${PECS[0]}px ${PECS[1]}px)`;
      s.el.style.background = '#000';   // cache le corps à l'intérieur du cercle
      const anneau = $('#anneau');
      anneau.style.display = o > 0 ? 'block' : 'none';
      rect(anneau, { x: PECS[0] - r, y: PECS[1] - r, w: 2 * r, h: 2 * r });
      anneau.style.opacity = 1 - lin(o, 0.6, 1);
    }
    titre(s, loc, -1, L);
    const k = p(loc, 0.9, 2.1);
    const kcal = Math.round(1840 * k / 10) * 10;
    $('#s7-val').textContent = fr(kcal);
    $('#s7-reste').textContent = fr(2250 - kcal);
    $('#s7-barre').style.width = (kcal / 2250 * 100) + '%';
    [['p', 132, 160], ['g', 205, 260], ['l', 54, 70]].forEach(([m, v, max], i) => {
      const a = p(loc, 1.05 + i * 0.15, 2.1 + i * 0.15);
      $('#s7-' + m).textContent = Math.round(v * a);
      $('#s7-b' + m).style.width = (v * a / max * 100) + '%';
    });
    // Sortie : la carte et la note tombent, chacune de son côté.
    const g = E.in(lin(loc, L + 0.05, L + 0.75)), g2 = E.in(lin(loc, L, L + 0.65));
    poser($('#s7-carte'), { y: 1500 * g, rz: 9 * g });
    const a = p(loc, 2.3, 2.7);
    poser($('#s7-note'), { y: 24 * (1 - a) + 900 * g2, rz: -14 * g2, o: a });
  },
  s8(loc, L, s) {
    titre(s, loc, 0.45, L);
    cartesProg.forEach((c, i) => {
      const a = p(loc, 0.25 + i * 0.12, 0.95 + i * 0.12, E.out);
      poser(c, { y: mix(-260, 0, a), z: mix(-700, 0, a), rx: mix(-80, 0, a), o: lin(a, 0, 0.25) });
    });
    const ia = $('#s8-ia');
    const a = p(loc, 1.9, 2.4, E.back);
    poser(ia, { y: 70 * (1 - lin(loc, 1.9, 2.3)), s: mix(0.86, 1, a), o: lin(loc, 1.9, 2.1) });
    // Sortie : le bloc vert grandit jusqu'à remplir l'écran ; le plan
    // suivant est posé sur ce vert.
    const g = p(loc, L, L + 0.55, E.inOut);
    rect(ia, mixRect({ x: 48, y: 1050, w: 624, h: 150 }, { x: 0, y: 0, w: W, h: H }, g));
    ia.style.borderRadius = mix(4, 0, g) + 'px';
    ia.querySelectorAll('div').forEach(d => { d.style.opacity = 1 - lin(g, 0, 0.3); });
    const recul = lin(loc, L, L + 0.45);
    pile.style.opacity = 1 - recul;
    pile.style.transform = `scale(${1 - 0.06 * recul})`;
  },
  s9(loc, L, s) {
    s.el.style.visibility = loc >= 0.55 && loc < L + 0.35 ? 'visible' : 'hidden';
    titre(s, loc, 0.6, L, 0.25);
    ['#s9-a', '#s9-b', '#s9-c'].forEach((id, i) => {
      const a = p(loc, 1.0 + i * 0.3, 1.5 + i * 0.3);
      const part = E.in(lin(loc, L + i * 0.04, L + i * 0.04 + 0.2));   // sortie vers la gauche
      const ligne = $(id);
      poser(ligne, { x: -W * part });
      poser(ligne.querySelector('.cond'), { x: 50 * (1 - a), o: a });
      poser(ligne.querySelector('.case'), { s: E.back(lin(loc, 1.0 + i * 0.3, 1.5 + i * 0.3)), o: lin(a, 0, 0.3) });
    });
  },
  s10(loc, L, s) {
    s.derive = false;
    // Entrée : on ressort de la lettre P. À ce grossissement, son vert
    // couvre tout l'écran, comme le fond du plan précédent.
    s.el.style.visibility = loc >= 0.35 ? 'visible' : 'hidden';
    const pro = $('#s10-pro');
    pro.style.transformOrigin = `${TIGE_P[0]}px ${TIGE_P[1]}px`;
    pro.style.transform = `scale(${mixLog(40, 1, p(loc, 0.35, 1.1, E.out))})`;
    reveler([...$('#s10-passe').querySelectorAll('.masque > span')], 1.1, loc, 0.08, 0.6);
    const b = p(loc, 1.5, 1.9);
    const pouls = 1 + 0.03 * Math.max(0, Math.sin((loc - 2.2) * 5)) * lin(loc, 2.2, 2.3);
    poser($('#s10-bouton'), { y: 60 * (1 - b), o: b, s: pouls });
  },
};

// Les repères dont les transitions ont besoin, pris sur la page elle-même
// plutôt que recopiés à la main : si la mise en page bouge, ils suivent.
function mesurer() {
  const voir = id => Object.assign(S[id].el.style, { display: 'block', transform: 'none' });
  // La bulle du coach, téléphone à plat, réponse complète.
  voir('s3');
  $('#s3-tel').style.transform = 'none';
  $('#s3-moi').textContent = MOI;
  $('#s3-moi').style.visibility = 'visible';
  $('#s3-points').style.display = 'none';
  Object.assign($('#s3-coach').style, { display: 'block', visibility: 'visible' });
  $('#s3-coach').innerHTML = texteCoach(COACH.length);
  const b = $('#s3-coach').getBoundingClientRect();
  BULLE = { x: b.left, y: b.top, w: b.width, h: b.height };
  $('#morph').innerHTML = `<span>${texteCoach(COACH.length)}</span>`;
  // La carte du debrief, où la bulle atterrit.
  voir('s4');
  const c = $('#s4-carte');
  CARTE = { x: c.offsetLeft, y: c.offsetTop, w: c.offsetWidth, h: c.offsetHeight };
  // Le centre des pectoraux, d'où s'ouvre la nutrition.
  voir('s6');
  const pecs = zones.filter(z => z.muscle === 'Pecs' && z.cote === 'face').flatMap(z => z.polys).map(pl => pl.getBoundingClientRect());
  PECS = [(Math.min(...pecs.map(r => r.left)) + Math.max(...pecs.map(r => r.right))) / 2,
    (Math.min(...pecs.map(r => r.top)) + Math.max(...pecs.map(r => r.bottom))) / 2];
  // La barre de l'haltère, scène 2 : centré en (360, 560), large de 540 px.
  const e = 540 / LARGEUR_HALTERE;
  BARRE = { x: 360 - 56 * e, y: 560 - 13 * e, w: 112 * e, h: 26 * e };
  // Le point du « ? » et la tige du P de « PRO », repérés à l'encre.
  voir('s1');
  POINT_Q = encre($('#hook .vert'), 'point');
  voir('s10');
  const pro = $('#s10-pro');
  pro.style.transform = 'none';
  const r = pro.getBoundingClientRect();
  const [x, y] = encre(pro, 'tige');
  TIGE_P = [x - r.left, y - r.top];
  for (const s of SCENES) s.el.style.display = 'none';
}

// Trouve un point plein dans un glyphe : le centre du point du « ? », ou le
// milieu de la tige du P. On redessine le texte de l'élément dans un canvas,
// à sa place exacte, puis on lit les pixels.
function encre(e, quoi) {
  const r = e.getBoundingClientRect();
  const st = getComputedStyle(e);
  const marge = 200;   // l'encre peut dépasser la boîte (interligne serré)
  const cv = document.createElement('canvas');
  cv.width = Math.ceil(r.width); cv.height = Math.ceil(r.height) + 2 * marge;
  const g = cv.getContext('2d');
  g.font = `${st.fontWeight} ${st.fontSize} ${st.fontFamily}`;
  // Ligne de base : celle d'un repère vide posé en ligne dans l'élément.
  const rep = document.createElement('span');
  rep.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline';
  e.appendChild(rep);
  const base = rep.getBoundingClientRect().top - r.top;
  rep.remove();
  g.fillText(e.textContent, 0, base + marge);
  const d = g.getImageData(0, 0, cv.width, cv.height).data;
  const plein = (x, y) => d[(y * cv.width + x) * 4 + 3] > 200;
  const lignes = [];
  for (let y = 0; y < cv.height; y++) { let n = 0; for (let x = 0; x < cv.width; x++) if (plein(x, y)) n++; lignes.push(n); }
  let haut = 0; while (!lignes[haut]) haut++;
  let bas = lignes.length - 1; while (!lignes[bas]) bas--;
  let y;
  if (quoi === 'point') {
    // Le point est la dernière bande de lignes pleines, sous un vide.
    let h = bas;
    while (h > 0 && lignes[h - 1]) h--;
    y = Math.round((h + bas) / 2);
  } else {
    // La tige du P, aux trois quarts de la hauteur de l'encre.
    y = Math.round(haut + (bas - haut) * 0.75);
  }
  let x0 = 0; while (!plein(x0, y)) x0++;
  let x1 = x0; while (plein(x1 + 1, y)) x1++;
  return [r.left + (x0 + x1) / 2, r.top + y - marge];
}

window.DUREE = DUREE;
window.reperes = () => ({ BULLE, CARTE, PECS, BARRE, POINT_Q, TIGE_P });   // pour vérifier les mesures
window.seek = seek;
window.pret = (async () => {
  await chargerCorps();
  await document.fonts.ready;
  await Promise.all([...document.fonts].map(f => f.load()));
  mesurer();
  seek(0);
  return true;
})();
