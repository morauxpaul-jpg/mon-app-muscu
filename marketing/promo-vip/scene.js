// Animation de la vidéo promo PRO. Tout est fonction du temps : seek(t)
// place chaque élément et dessine la 3D pour l'instant t, sans horloge.
// Deux rendus du même t donnent la même image — c'est ce qui permet à
// rendre.py de photographier la vidéo image par image, sans à-coups.
import * as THREE from './node_modules/three/build/three.module.js';

const W = 720, H = 1280;
export const DUREE = 24.5;

// ── Temps ────────────────────────────────────────────────────────
const borne = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lin = (t, a, b) => borne((t - a) / (b - a));
const E = {
  out: x => 1 - Math.pow(1 - x, 3),
  inOut: x => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  expo: x => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),
  back: x => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); },
};
const p = (t, a, b, e = E.out) => e(lin(t, a, b));
const mix = (a, b, k) => a + (b - a) * k;
const fr = (n, d = 0) => n.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d }).replace(/[  ]/g, ' ');
const $ = s => document.querySelector(s);

// Les scènes, dans l'ordre. a et b en secondes.
const SCENES = [
  { id: 's1', a: 0.0, b: 2.5 },   // accroche
  { id: 's2', a: 2.5, b: 4.7 },   // marque, haltère 3D
  { id: 's3', a: 4.7, b: 7.8 },   // coach IA
  { id: 's4', a: 7.8, b: 10.0 },  // debrief
  { id: 's5', a: 10.0, b: 12.6 }, // force estimée
  { id: 's6', a: 12.6, b: 14.8 }, // carte musculaire
  { id: 's7', a: 14.8, b: 17.2 }, // nutrition
  { id: 's8', a: 17.2, b: 19.9 }, // programmes + générateur
  { id: 's9', a: 19.9, b: 21.7 }, // et aussi
  { id: 's10', a: 21.7, b: DUREE }, // appel à l'action
];
for (const s of SCENES) s.el = document.getElementById(s.id);

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
for (const [x, y, l, h, r] of HALTERE) {
  const barre = r === 0;
  const prof = barre ? 26 : (h > 200 ? 64 : 50);
  const forme = rectArrondi(x - 256, -(y + h) + 256, l, h, r);
  const g = new THREE.ExtrudeGeometry(forme, { depth: prof, bevelEnabled: true, bevelThickness: 3, bevelSize: 2.5, bevelSegments: 3, curveSegments: 8 });
  g.translate(0, 0, -prof / 2);
  haltere.add(new THREE.Mesh(g, matiere));
}
const pivot = new THREE.Group();
pivot.add(haltere);
scene3d.add(pivot);
const LARGEUR_HALTERE = 340;  // en unités de la grille de 512

// Sol en perspective, qui défile doucement : la profondeur du décor.
const sol = new THREE.GridHelper(80, 64, 0x1c1c1c, 0x141414);
sol.position.set(0, -6.2, -10);
scene3d.add(sol);

function placerHaltere(px, py, largeurPx, rx, ry, rz = 0) {
  const [x, y] = versMonde(px, py);
  pivot.position.set(x, y, 0);
  const k = (largeurPx / PX) / LARGEUR_HALTERE;
  pivot.scale.setScalar(k);
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
const zones = [];   // [{poly[], muscle, ordre}]
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
  const dessiner = (svg, muscles, neutres) => {
    for (const pts of neutres) el('polygon', { points: pts, fill: '#1a1a1a', stroke: '#262626', 'stroke-width': 0.3 }, svg);
    for (const [m, polys] of Object.entries(muscles)) {
      const ps = polys.map(pts => el('polygon', { points: pts, fill: '#1a1a1a', stroke: '#262626', 'stroke-width': 0.3 }, svg));
      zones.push({ muscle: m, polys: ps });
    }
  };
  dessiner($('#corps-face'), corps.anterior, corps.anterior_neutral);
  dessiner($('#corps-dos'), corps.posterior, corps.posterior_neutral);
  musclesConnus = [...new Set(zones.map(z => z.muscle))];
}

// ── Outils d'animation ───────────────────────────────────────────
function reveler(spans, t0, loc, pas = 0.08, duree = 0.55) {
  spans.forEach((s, i) => {
    const k = p(loc, t0 + i * pas, t0 + i * pas + duree, E.expo);
    s.style.transform = `translateY(${(1 - k) * 112}%)`;
  });
}
function poser(e, { x = 0, y = 0, s = 1, o = 1, rx = 0, ry = 0, z = 0 } = {}) {
  e.style.transform = `translate3d(${x}px, ${y}px, ${z}px) rotateX(${rx}deg) rotateY(${ry}deg) scale(${s})`;
  e.style.opacity = o;
}
const vert = new THREE.Color('#c8f031'), fond = new THREE.Color('#1a1a1a');
const teinte = k => '#' + fond.clone().lerp(vert, k).getHexString();

// ── Une image ────────────────────────────────────────────────────
function seek(t) {
  for (const s of SCENES) {
    const actif = t >= s.a && t < s.b;
    s.el.style.display = actif ? 'block' : 'none';
    if (!actif) continue;
    const loc = t - s.a, dur = s.b - s.a;
    // Sortie commune (sauf scènes fermées par le volet vert) : la scène
    // remonte et s'efface sur ses 0,35 dernières secondes.
    if (!['s1', 's9', 's10'].includes(s.id)) {
      const k = p(loc, dur - 0.35, dur, E.inOut);
      s.el.style.transform = `translateY(${-90 * k}px)`;
      s.el.style.opacity = 1 - k;
    }
    const titre = s.el.querySelectorAll('.titre .masque > span');
    if (titre.length) reveler([...titre], 0.05, loc);
    MAJ[s.id](loc, dur);
  }

  // Volet vert entre l'accroche et la marque, et avant l'appel à l'action.
  const volet = $('#volet');
  const passages = [2.27, 21.47];
  const v = passages.find(a => t >= a && t < a + 0.46);
  volet.style.display = v === undefined ? 'none' : 'block';
  if (v !== undefined) volet.style.transform = `translateY(${mix(100, -100, E.inOut(lin(t, v, v + 0.46)))}%)`;

  // 3D : le sol défile toujours ; l'haltère n'apparaît que sur 2 et 10.
  sol.position.z = -10 + ((t * 1.3) % (80 / 64));
  const s2 = SCENES[1], s10 = SCENES[9];
  if (t >= s2.a && t < s2.b) {
    const loc = t - s2.a;
    const k = p(loc, 0, 1.15, E.expo);
    const flotte = Math.sin(loc * 2.2) * 0.18 * lin(loc, 0.9, 1.4);
    const sortie = p(loc, 1.85, 2.2, E.inOut);
    placerHaltere(360, mix(1500, 560, k) + mix(0, -900, sortie), 540,
      mix(0.9, 0.18, k) + sortie * 0.8, mix(-4 * Math.PI, 0.2, k) + flotte, mix(-0.3, 0, k));
    pivot.visible = true;
  } else if (t >= s10.a) {
    const loc = t - s10.a;
    const k = p(loc, 0.1, 1.0, E.expo);
    placerHaltere(360, mix(1600, 390, k), 380, mix(1.2, 0.16, k), mix(3 * Math.PI, 0, k) + Math.sin(loc * 1.7) * 0.32 * lin(loc, 0.8, 1.3));
    pivot.visible = true;
  } else {
    pivot.visible = false;
  }
  renderer.render(scene3d, camera);
}

const MAJ = {
  s1(loc) {
    reveler([...$('#hook').querySelectorAll('.masque > span')], 0.1, loc, 0.22, 0.5);
    const k = p(loc, 0.85, 1.6, E.inOut);
    const L = 580;
    platChemin.style.strokeDasharray = L;
    platChemin.style.strokeDashoffset = L * (1 - k);
    platPoints.forEach((c, i) => { const a = lin(k, i / 5 - 0.02, i / 5 + 0.08); c.setAttribute('r', 8 * a); });
    platLabels.forEach((l, i) => l.setAttribute('opacity', lin(k, i / 5 - 0.05, i / 5 + 0.1)));
    poser($('#s1-sous'), { y: 20 * (1 - p(loc, 1.35, 1.8)), o: p(loc, 1.35, 1.8) });
  },
  s2(loc) {
    reveler([...$('#s2-nom').querySelectorAll('.masque > span')], 0.75, loc);
    const k = p(loc, 1.0, 1.45, E.back);
    $('#s2-pro').style.transform = `translateX(-50%) scale(${mix(0.4, 1, k)})`;
    $('#s2-pro').style.opacity = lin(loc, 1.0, 1.15);
  },
  s3(loc) {
    const tel = $('#s3-tel');
    const k = p(loc, 0.15, 1.05, E.out);
    const sortie = p(loc, 2.75, 3.1, E.inOut);
    poser(tel, { y: mix(380, 0, k), rx: mix(24, 7, k), ry: mix(48, -12, k) + 6 * lin(loc, 1.05, 2.7) - 30 * sortie, x: -640 * sortie, z: mix(-200, 0, k) });
    const n = Math.round(MOI.length * lin(loc, 0.7, 1.35));
    $('#s3-moi').textContent = MOI.slice(0, n);
    $('#s3-moi').style.visibility = n ? 'visible' : 'hidden';
    const attente = loc >= 1.4 && loc < 1.75;
    $('#s3-points').style.display = attente ? 'block' : 'none';
    if (attente) [...$('#s3-points').children].forEach((d, i) => { d.style.opacity = 0.35 + 0.65 * Math.max(0, Math.sin((loc - 1.4) * 14 - i * 0.9)); });
    const m = Math.round(COACH.length * lin(loc, 1.75, 2.65));
    $('#s3-coach').style.display = m ? 'block' : 'none';
    // Les groupes en gras ne se coupent pas en fin de ligne (« 82,5 | kg »).
    $('#s3-coach').innerHTML = COACH.slice(0, m).map(([w, b]) => (b ? `<b>${w.replace(/ /g, '\u00a0')}</b>` : w)).join(' ');
  },
  s4(loc) {
    const k = p(loc, 0.15, 0.6);
    poser($('#s4-carte'), { y: 80 * (1 - k), o: k });
    const c = p(loc, 0.4, 1.25);
    $('#s4-series').textContent = Math.round(18 * c);
    $('#s4-volume').textContent = fr(Math.round(7420 * c / 10) * 10);
    $('#s4-gain').textContent = '+' + Math.round(6 * c) + ' %';
    ['#s4-l1', '#s4-l2', '#s4-l3'].forEach((id, i) => {
      const a = p(loc, 0.85 + i * 0.25, 1.25 + i * 0.25, E.out);
      poser($(id), { x: 70 * (1 - a), o: a });
    });
  },
  s5(loc) {
    const k = p(loc, 0.3, 1.9, E.out);
    $('#s5-val').textContent = fr(mix(87, 102.5, k), 1);
    const L = forceChemin.getTotalLength();
    forceChemin.style.strokeDasharray = L;
    forceChemin.style.strokeDashoffset = L * (1 - k);
    forcePoints.forEach((c, i) => {
      const a = E.back(lin(k, i / (FORCE.length - 1) - 0.03, i / (FORCE.length - 1) + 0.06));
      c.setAttribute('transform', `translate(${CX(i)} ${CY(FORCE[i])}) scale(${a}) translate(${-CX(i)} ${-CY(FORCE[i])})`);
    });
    poser($('#s5-gain'), { x: 30 * (1 - p(loc, 1.6, 2.0)), o: p(loc, 1.6, 2.0) });
    poser($('#s5-carte'), { y: 60 * (1 - p(loc, 0.1, 0.5)), o: p(loc, 0.1, 0.5) });
  },
  s6(loc) {
    const ordre = musclesConnus;
    let allumes = 0;
    zones.forEach(z => {
      const i = ordre.indexOf(z.muscle);
      const a = p(loc, 0.35 + i * 0.09, 0.65 + i * 0.09);
      if (a > 0.5) allumes = Math.max(allumes, i + 1);
      const c = teinte(a * (INTENSITE[z.muscle] ?? 0.5));
      z.polys.forEach(pl => pl.setAttribute('fill', c));
    });
    $('#s6-compte').textContent = `${allumes} groupes travaillés`;
    const k = p(loc, 0.1, 0.5);
    poser($('#s6-corps'), { y: 50 * (1 - k), o: k });
  },
  s7(loc) {
    poser($('#s7-carte'), { y: 60 * (1 - p(loc, 0.1, 0.5)), o: p(loc, 0.1, 0.5) });
    const k = p(loc, 0.3, 1.45);
    const kcal = Math.round(1840 * k / 10) * 10;
    $('#s7-val').textContent = fr(kcal);
    $('#s7-reste').textContent = fr(2250 - kcal);
    $('#s7-barre').style.width = (kcal / 2250 * 100) + '%';
    [['p', 132, 160], ['g', 205, 260], ['l', 54, 70]].forEach(([m, v, max], i) => {
      const a = p(loc, 0.55 + i * 0.15, 1.45 + i * 0.15);
      $('#s7-' + m).textContent = Math.round(v * a);
      $('#s7-b' + m).style.width = (v * a / max * 100) + '%';
    });
    poser($('#s7-note'), { y: 24 * (1 - p(loc, 1.35, 1.75)), o: p(loc, 1.35, 1.75) });
  },
  s8(loc) {
    cartesProg.forEach((c, i) => {
      const a = p(loc, 0.25 + i * 0.11, 0.85 + i * 0.11, E.out);
      poser(c, { y: mix(-260, 0, a), z: mix(-700, 0, a), rx: mix(-80, 0, a), o: lin(a, 0, 0.25) });
    });
    const a = p(loc, 1.35, 1.85, E.back);
    poser($('#s8-ia'), { y: 70 * (1 - lin(loc, 1.35, 1.75)), s: mix(0.86, 1, a), o: lin(loc, 1.35, 1.55) });
  },
  s9(loc) {
    ['#s9-a', '#s9-b', '#s9-c'].forEach((id, i) => {
      const a = p(loc, 0.3 + i * 0.28, 0.75 + i * 0.28);
      const ligne = $(id);
      poser(ligne.querySelector('.cond'), { x: 50 * (1 - a), o: a });
      const b = p(loc, 0.3 + i * 0.28, 0.75 + i * 0.28, E.back);
      poser(ligne.querySelector('.case'), { s: b, o: lin(a, 0, 0.3) });
    });
  },
  s10(loc) {
    reveler([...$('#s10-passe').querySelectorAll('.masque > span')], 0.3, loc);
    const k = p(loc, 0.5, 1.0, E.back);
    poser($('#s10-pro'), { s: mix(0.6, 1, k), o: lin(loc, 0.5, 0.65) });
    const b = p(loc, 1.05, 1.45);
    const pouls = 1 + 0.03 * Math.max(0, Math.sin((loc - 1.6) * 5)) * lin(loc, 1.6, 1.7);
    poser($('#s10-bouton'), { y: 60 * (1 - b), o: b, s: pouls });
  },
};

window.DUREE = DUREE;
window.seek = seek;
window.pret = (async () => {
  await chargerCorps();
  await document.fonts.ready;
  await Promise.all([...document.fonts].map(f => f.load()));
  seek(0);
  return true;
})();
