/**
 * Une séance d'un jour à venir s'enregistre aujourd'hui (static/js/jour-seance.js).
 *
 * Audit du 06/10 (I-1) : la carte « Prochaine séance · Demain » ouvrait la page
 * datée du lendemain et les séries s'y enregistraient à cette date (constaté
 * en production le 04/10). En ligne, la page est rouverte pour aujourd'hui ;
 * hors ligne, sa date est réécrite sur place. Une page datée d'aujourd'hui ou
 * d'un jour passé (rattrapage) n'est jamais touchée.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert').strict;
const { createEnv } = require('./harness');

/**
 * Exécute fn avec l'horloge du téléphone réglée sur Paris. Node relit TZ quand
 * on la change en cours de route ; on remet l'ancienne valeur ensuite pour ne
 * pas déranger les autres tests.
 */
function aParis(fn) {
  const avant = process.env.TZ;
  process.env.TZ = 'Europe/Paris';
  try { return fn(); } finally {
    if (avant === undefined) delete process.env.TZ; else process.env.TZ = avant;
  }
}

/** Les scripts en ligne d'un gabarit qui lisent la séance en cours. */
function scriptsDuGabarit(nom) {
  const html = fs.readFileSync(path.join(__dirname, '..', '..', 'templates', nom), 'utf8');
  return [...html.matchAll(/<script nonce="[^"]*">([\s\S]*?)<\/script>/g)]
    .map((m) => m[1]).filter((js) => js.includes('active_session'));
}

/**
 * Lance ces scripts avec une horloge figée à `instant` et une séance en cours
 * datée `dateSeance`. Rend ce qui reste de la séance et l'adresse rouverte.
 */
function lancerGabarit(nom, instant, dateSeance) {
  const scripts = scriptsDuGabarit(nom);
  assert.ok(scripts.length, nom + ' : aucun script ne lit la séance en cours');
  const stockage = new Map([['active_session', JSON.stringify({
    active_session: true, session_id: 'Push', session_mode: 'prefaite', session_date: dateSeance,
  })]]);
  const local = {
    getItem: (k) => (stockage.has(k) ? stockage.get(k) : null),
    setItem: (k, v) => { stockage.set(k, String(v)); },
    removeItem: (k) => { stockage.delete(k); },
  };
  const session = { getItem: () => null, setItem() {} };
  let rouverte = null;
  const location = { pathname: '/', search: '', replace: (u) => { rouverte = u; } };
  class DateFigee extends Date {
    constructor(...a) { if (a.length) super(...a); else super(instant); }
    static now() { return instant; }
  }
  const element = () => ({ style: {}, dataset: {}, addEventListener() {} });
  const bac = {
    Date: DateFigee, JSON, String, URLSearchParams, encodeURIComponent,
    localStorage: local, sessionStorage: session,
    document: { getElementById: element },
  };
  bac.window = { location };
  aParis(() => {
    for (const js of scripts) vm.runInNewContext(js, bac, { filename: nom });
  });
  return { gardee: stockage.has('active_session'), rouverte };
}

function charger() {
  const env = createEnv({ scripts: ['jour-seance.js'] });
  return env.window.JourSeance;
}

/** Document factice qui GARDE ce qu'on y écrit (le harnais renvoie un objet neuf à chaque appel). */
function fauxDocument(datePage, autresChamps) {
  const cfg = { textContent: JSON.stringify({ mode: 'prefaite', seance: 'Push', date: datePage }) };
  const champs = [{ value: datePage }, { value: datePage }].concat(autresChamps || []);
  let xdata = 'seanceReorder("prefaite", "Push", ' + JSON.stringify(datePage) + ')';
  const liste = { getAttribute: () => xdata, setAttribute: (_n, v) => { xdata = v; } };
  const bandeau = { hidden: true };
  return {
    cfg, champs, bandeau, xdata: () => xdata,
    getElementById: (id) => (id === 'seance-config' ? cfg : id === 'seance-en-avance' ? bandeau : null),
    querySelectorAll: () => champs,
    querySelector: () => liste,
  };
}

function fausseAdresse(date) {
  const loc = { href: 'https://app.test/seance?mode=prefaite&name=Push&date=' + date, remplacee: null };
  loc.replace = (u) => { loc.remplacee = u; };
  return loc;
}

// Midi, heure locale : loin de la bascule de 4 h, quel que soit le fuseau de la machine.
const MARDI_MIDI = new Date(2026, 9, 6, 12, 0).getTime();

module.exports = ({ test, assert }) => {
  test('jour-seance : avant 4 h, c\'est encore la veille', () => {
    const J = charger();
    assert.equal(J.jourLogique(new Date(2026, 9, 7, 3, 30).getTime()), '2026-10-06');
    assert.equal(J.jourLogique(new Date(2026, 9, 7, 4, 30).getTime()), '2026-10-07');
  });

  // Nuit du passage à l'heure d'hiver : à 03 h heure d'été, on revient à 02 h.
  // Le 25/10/2026 à 02 h 13 UTC (03 h 13 heure d'hiver), « maintenant moins
  // 4 h » retombait à 23 h 13 heure d'été... du 25 : la page se datait du
  // lendemain, alors que le serveur dit le 24.
  test('jour-seance : nuit du passage à l\'heure d\'hiver, même jour que le serveur', () => {
    const J = charger();
    aParis(() => {
      assert.equal(J.jourLogique(Date.parse('2026-10-25T00:30:00Z')), '2026-10-24'); // 02 h 30 été
      assert.equal(J.jourLogique(Date.parse('2026-10-25T01:30:00Z')), '2026-10-24'); // 02 h 30 hiver
      assert.equal(J.jourLogique(Date.parse('2026-10-25T02:13:00Z')), '2026-10-24'); // 03 h 13 hiver
      assert.equal(J.jourLogique(Date.parse('2026-10-25T03:00:00Z')), '2026-10-25'); // 04 h 00 hiver
    });
  });

  // Passage à l'heure d'été : à 02 h heure d'hiver, on saute à 03 h. Ici,
  // « moins 4 h » rendait la veille de 04 h à 05 h, une heure de trop.
  test('jour-seance : nuit du passage à l\'heure d\'été, même jour que le serveur', () => {
    const J = charger();
    aParis(() => {
      assert.equal(J.jourLogique(Date.parse('2026-03-29T00:30:00Z')), '2026-03-28'); // 01 h 30 hiver
      assert.equal(J.jourLogique(Date.parse('2026-03-29T01:30:00Z')), '2026-03-28'); // 03 h 30 été
      assert.equal(J.jourLogique(Date.parse('2026-03-29T02:00:00Z')), '2026-03-29'); // 04 h 00 été
      assert.equal(J.jourLogique(Date.parse('2026-03-29T02:30:00Z')), '2026-03-29'); // 04 h 30 été
      // Lendemain à 02 h 30 : reculer d'un jour tombe dans l'heure sautée du
      // 29, que le navigateur décale à 03 h 30. La date reste le 29.
      assert.equal(J.jourLogique(Date.parse('2026-03-30T00:30:00Z')), '2026-03-29');
    });
  });

  // base.html (reprise au lancement) et seance_choix.html (onglet Séance)
  // comparent la date de la séance en cours à « aujourd'hui ». Un jour faux et
  // la séance en cours est oubliée : base.html avait le même « moins 4 h »,
  // seance_choix.html prenait la date UTC.
  for (const gabarit of ['base.html', 'seance_choix.html']) {
    test('jour-seance : ' + gabarit + ' reprend la séance en cours la nuit du passage à l\'heure d\'hiver', () => {
      const r = lancerGabarit(gabarit, Date.parse('2026-10-25T02:13:00Z'), '2026-10-24');
      assert.equal(r.gardee, true, 'la séance en cours du 24 a été effacée');
      assert.ok(r.rouverte && r.rouverte.includes('date=2026-10-24'), 'séance non rouverte : ' + r.rouverte);
    });

    test('jour-seance : ' + gabarit + ' reprend la séance en cours à 03 h 30 en été', () => {
      const r = lancerGabarit(gabarit, Date.parse('2026-07-15T01:30:00Z'), '2026-07-14');
      assert.equal(r.gardee, true, 'la séance en cours du 14 a été effacée');
      assert.ok(r.rouverte && r.rouverte.includes('date=2026-07-14'), 'séance non rouverte : ' + r.rouverte);
    });

    test('jour-seance : ' + gabarit + ' oublie la séance de la veille passé 4 h', () => {
      const r = lancerGabarit(gabarit, Date.parse('2026-10-25T03:00:00Z'), '2026-10-24');
      assert.equal(r.gardee, false);
      assert.equal(r.rouverte, null);
    });
  }

  test('jour-seance : seule une date postérieure à aujourd\'hui est « à venir »', () => {
    const J = charger();
    assert.equal(J.estAVenir('2026-10-07', '2026-10-06'), true);
    assert.equal(J.estAVenir('2026-10-06', '2026-10-06'), false);
    assert.equal(J.estAVenir('2026-10-01', '2026-10-06'), false);   // rattrapage
    assert.equal(J.estAVenir('pas-une-date', '2026-10-06'), false);
  });

  test('jour-seance : en ligne, la séance de demain est rouverte pour aujourd\'hui', () => {
    const J = charger();
    const doc = fauxDocument('2026-10-07');
    const loc = fausseAdresse('2026-10-07');
    assert.equal(J.appliquer(doc, loc, { onLine: true }, MARDI_MIDI), 'rouverte');
    const u = new URL(loc.remplacee);
    assert.equal(u.searchParams.get('date'), '2026-10-06');
    assert.equal(u.searchParams.get('prevue'), '2026-10-07');
    assert.equal(u.searchParams.get('name'), 'Push');
  });

  test('jour-seance : hors ligne, la date est réécrite partout sur la page', () => {
    const J = charger();
    const autre = { value: '2026-09-30' };
    const doc = fauxDocument('2026-10-08', [autre]);
    const loc = fausseAdresse('2026-10-08');
    assert.equal(J.appliquer(doc, loc, { onLine: false }, MARDI_MIDI), 'reecrite');
    assert.equal(loc.remplacee, null, 'pas de navigation sans réseau');
    assert.equal(JSON.parse(doc.cfg.textContent).date, '2026-10-06');
    assert.deepEqual(doc.champs.slice(0, 2).map((c) => c.value), ['2026-10-06', '2026-10-06']);
    assert.equal(autre.value, '2026-09-30', 'un champ portant une autre date ne bouge pas');
    assert.ok(doc.xdata().includes('"2026-10-06"') && !doc.xdata().includes('2026-10-08'));
    assert.equal(doc.bandeau.hidden, false, 'le bandeau « En avance » le dit');
  });

  test('jour-seance : la séance du jour et un rattrapage ne sont jamais touchés', () => {
    const J = charger();
    for (const date of ['2026-10-06', '2026-10-02']) {
      const doc = fauxDocument(date);
      const loc = fausseAdresse(date);
      assert.equal(J.appliquer(doc, loc, { onLine: true }, MARDI_MIDI), 'rien');
      assert.equal(loc.remplacee, null);
      assert.equal(JSON.parse(doc.cfg.textContent).date, date);
    }
  });

  test('jour-seance : la page du jeudi gardée mardi garde sa date ouverte le jeudi', () => {
    const J = charger();
    const jeudiMatin = new Date(2026, 9, 8, 9, 0).getTime();
    const doc = fauxDocument('2026-10-08');
    assert.equal(J.appliquer(doc, fausseAdresse('2026-10-08'), { onLine: false }, jeudiMatin), 'rien');
    assert.equal(JSON.parse(doc.cfg.textContent).date, '2026-10-08');
  });
};
