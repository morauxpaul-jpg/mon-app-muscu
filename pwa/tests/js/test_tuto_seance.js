/**
 * Bulles de la séance (static/js/tuto-seance.js, audit du 18/10, m9).
 *
 * Trois bulles au plus, dans l'ordre, une seule fois chacune. Les cas que le
 * test navigateur (tests/e2e/test_premier_jour.py) atteint mal : un exercice
 * d'une seule série (fini avant la bulle du repos), un stockage refusé, la
 * relance depuis Gestion.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', '..', 'static', 'js', 'tuto-seance.js'), 'utf8');

function charger(opts) {
  const o = opts || {};
  const store = new Map(Object.entries(o.stockage || {}));
  const ecouteurs = {};
  const minuteries = [];
  const montrees = [];            // titres des bulles ouvertes
  let ouverte = null;             // bulle en cours : { options }
  const element = (cache) => ({ hidden: !!cache, getClientRects: () => (cache ? [] : [{}]) });
  const localStorage = o.stockageRefuse ? {
    getItem() { throw new Error('refusé'); },
    setItem() { throw new Error('refusé'); },
  } : {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
  };
  const document = {
    addEventListener(type, fn) { (ecouteurs[type] = ecouteurs[type] || []).push(fn); },
    querySelectorAll: (sel) => (sel === '.serie-encours' ? [element(false)] : []),
    querySelector: (sel) => (sel === '#exo-anchor-0' ? element(false) : null),
    getElementById: (id) => (id === 'tuto-overlay' && ouverte ? {} : id === 'rest-timer' ? element(!o.chrono) : null),
  };
  const window = {
    TutoEngine: {
      run(etapes, options) {
        if (ouverte) return;
        ouverte = { options };
        montrees.push(etapes[0].title);
      },
    },
  };
  const ctx = { window, document, localStorage, setTimeout: (fn) => minuteries.push(fn), parseInt, String };
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx);
  return {
    store, montrees,
    init: (x) => window.initTutoSeance(x),
    relancer: () => window.replayTutoSeance(),
    temps() { while (minuteries.length) minuteries.shift()(); },
    geste(type) { (ecouteurs[type] || []).forEach((fn) => fn()); },
    fermer(comment) { const b = ouverte; ouverte = null; b.options.onFinish(comment || 'bouton'); },
  };
}

module.exports = ({ test, assert }) => {
  test('tuto-seance : trois bulles dans l\'ordre, une seule fois', () => {
    const t = charger({ chrono: true });
    t.init(); t.temps();
    assert.deepEqual(t.montrees, ['Une série à la fois']);
    assert.equal(t.store.get('tutoSeen'), 'true');   // la bulle d'accueil n'a plus lieu d'être
    t.fermer();
    t.geste('seance:serie-faite'); t.temps();
    assert.equal(t.montrees[1], 'Série enregistrée');
    t.fermer();
    t.geste('seance:serie-faite'); t.temps();        // 2e série : rien
    assert.equal(t.montrees.length, 2);
    t.geste('seance:exercice-fini');
    assert.equal(t.montrees[2], 'Premier exercice terminé');
    t.fermer();
    assert.equal(t.store.get('tutoSeanceSeen'), 'true');
    t.geste('seance:exercice-fini');
    assert.equal(t.montrees.length, 3);
  });

  test('tuto-seance : un exercice fini avant la bulle du repos attend le suivant', () => {
    const t = charger();
    t.init(); t.temps(); t.fermer();
    // Exercice d'une série : « fini » arrive dans le même geste que la série.
    t.geste('seance:serie-faite');
    t.geste('seance:exercice-fini');
    assert.equal(t.montrees.length, 1, 'pas de « Premier exercice terminé » avant le repos');
    t.temps(); t.fermer();
    t.geste('seance:exercice-fini');
    assert.equal(t.montrees[2], 'Premier exercice terminé');
  });

  test('tuto-seance : « Passer » coupe les bulles suivantes', () => {
    const t = charger();
    t.init(); t.temps(); t.fermer('passer');
    t.geste('seance:serie-faite'); t.temps();
    t.geste('seance:exercice-fini');
    assert.deepEqual(t.montrees, ['Une série à la fois']);
    assert.equal(t.store.get('tutoSeanceSeen'), 'true');
  });

  test('tuto-seance : reprise d\'une séance à l\'autre, sans rejouer ce qui est vu', () => {
    const t = charger({ stockage: { tutoSeanceSeen: '1' } });
    t.init(); t.temps();
    assert.equal(t.montrees.length, 0, 'l\'arrivée est déjà vue');
    t.geste('seance:serie-faite'); t.temps();
    assert.deepEqual(t.montrees, ['Série enregistrée']);
  });

  test('tuto-seance : déjà tout vu, ou stockage refusé : aucune bulle', () => {
    for (const o of [{ stockage: { tutoSeanceSeen: 'true' } }, { stockageRefuse: true }]) {
      const t = charger(o);
      t.init(); t.temps();
      t.geste('seance:serie-faite'); t.temps();
      t.geste('seance:exercice-fini');
      assert.equal(t.montrees.length, 0);
    }
  });

  test('tuto-seance : « Revoir l\'aide de la séance » repart de la première bulle', () => {
    const t = charger({ stockage: { tutoSeanceSeen: 'true' } });
    t.relancer(); t.temps();
    assert.deepEqual(t.montrees, ['Une série à la fois']);
  });
};
