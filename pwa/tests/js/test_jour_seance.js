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

const { createEnv } = require('./harness');

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
