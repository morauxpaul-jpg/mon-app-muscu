/**
 * Remontée des erreurs JavaScript (static/js/erreurs.js, audit du 18/10, I-2).
 *
 * Le coach est resté vide sept jours sans une ligne au journal. Ce test
 * vérifie que l'erreur part bien au serveur, une seule fois, et jamais pour
 * un visiteur non connecté.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', '..', 'static', 'js', 'erreurs.js'), 'utf8');

function charger(jeton) {
  const ecouteurs = {};
  const envois = [];
  const window = {
    addEventListener(type, fn) { ecouteurs[type] = fn; },
    fetch(url, init) { envois.push({ url, init, corps: JSON.parse(init.body) }); return Promise.resolve({}); },
  };
  const ctx = {
    window,
    location: { pathname: '/coach' },
    document: { querySelector: () => (jeton === null ? null : { content: jeton }) },
    console: { error() {}, warn() {} },
  };
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx);
  return { ecouteurs, envois };
}

module.exports = ({ test, assert }) => {
  test('erreurs.js : une erreur de code part au serveur', () => {
    const { ecouteurs, envois } = charger('jeton');
    ecouteurs.error({ message: 'x is not defined', filename: 'https://a/static/js/coach.js', lineno: 12 });
    assert.equal(envois.length, 1);
    assert.equal(envois[0].url, '/erreurs/js');
    assert.equal(envois[0].init.method, 'POST');
    assert.equal(envois[0].corps.genre, 'erreur');
    assert.equal(envois[0].corps.message, 'x is not defined');
    assert.equal(envois[0].corps.ligne, 12);
    assert.equal(envois[0].corps.page, '/coach');
  });

  test('erreurs.js : la même erreur ne part qu\'une fois, cinq au plus par page', () => {
    const { ecouteurs, envois } = charger('jeton');
    for (let i = 0; i < 3; i++) ecouteurs.error({ message: 'boucle', filename: 'a.js', lineno: 1 });
    assert.equal(envois.length, 1);
    for (let i = 0; i < 10; i++) ecouteurs.error({ message: 'e' + i, filename: 'a.js', lineno: 1 });
    assert.equal(envois.length, 5);
  });

  test('erreurs.js : promesse rejetée remontée, image manquante ignorée', () => {
    const { ecouteurs, envois } = charger('jeton');
    ecouteurs.error({});   // ressource non chargée : pas de message
    ecouteurs.unhandledrejection({ reason: new Error('réseau') });
    assert.equal(envois.length, 1);
    assert.equal(envois[0].corps.genre, 'promesse');
    assert.equal(envois[0].corps.message, 'réseau');
  });

  test('erreurs.js : une transition de page interrompue n\'est pas une erreur', () => {
    const { ecouteurs, envois } = charger('jeton');
    const rejet = (name, message) => Object.assign(new Error(message), { name });
    ecouteurs.unhandledrejection({ reason: rejet('InvalidStateError',
      'Transition was aborted because of invalid state. Viewport size changed') });
    ecouteurs.unhandledrejection({ reason: rejet('AbortError', 'Transition was skipped') });
    assert.equal(envois.length, 0);
    // Une autre InvalidStateError, elle, part toujours.
    ecouteurs.unhandledrejection({ reason: rejet('InvalidStateError', 'The object is in an invalid state.') });
    assert.equal(envois.length, 1);
  });

  test('erreurs.js : rien ne part sans compte connecté', () => {
    for (const jeton of [null, '']) {
      const { ecouteurs, envois } = charger(jeton);
      ecouteurs.error({ message: 'boom', filename: 'a.js', lineno: 1 });
      assert.equal(envois.length, 0);
    }
  });
};
