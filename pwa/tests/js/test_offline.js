/**
 * File d'attente hors-ligne (static/js/offline.js).
 *
 * C'est le seul endroit de l'app où des données utilisateur vivent hors de
 * la base : entre le moment où la série est saisie en sous-sol et celui où
 * le réseau revient. Une régression ici ne se voit pas — la série disparaît
 * simplement, et l'utilisateur croit avoir mal appuyé.
 *
 * Lancer : node tests/js/run.js  (ou via pytest, cf. test_js.py)
 */
'use strict';

const { createEnv, makeForm, makeFormData, submitEvent } = require('./harness');

const SAVE_URL = 'https://app.test/seance/save-exo';

function envHorsLigne(opts) {
  return createEnv(Object.assign({ scripts: ['offline.js'], online: false }, opts || {}));
}

module.exports = ({ test, assert }) => {

  test('une série mise en file est retrouvée telle quelle', () => {
    const env = envHorsLigne();
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ exo_base: 'Squat', reps: '8' }));
    const q = env.queue();
    assert.equal(q.length, 1);
    assert.equal(q[0].url, SAVE_URL);
    assert.equal(q[0].data.exo_base, 'Squat');
    assert.equal(env.window.OfflineQueue.pending(), 1);
  });

  test('un localStorage corrompu donne une file vide, pas une exception', () => {
    const env = envHorsLigne({ corruptQueue: true });
    assert.equal(env.window.OfflineQueue.pending(), 0);
  });

  test('la synchronisation envoie dans l\'ordre de saisie', async () => {
    const env = envHorsLigne();
    for (const poids of ['60', '70', '80']) {
      env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ poids }));
    }
    env.navigator.onLine = true;
    const n = await env.window.OfflineQueue.sync();
    assert.equal(n, 3);
    assert.equal(env.queue().length, 0);
    const poids = env.calls.map((c) => new URLSearchParams(c.body).get('poids'));
    assert.deepEqual(poids, ['60', '70', '80']);
  });

  test('un envoi qui échoue garde TOUTE la suite en file', async () => {
    const env = envHorsLigne();
    for (const poids of ['60', '70', '80']) {
      env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ poids }));
    }
    env.navigator.onLine = true;
    env.setResponder((url, init, i) =>
      i === 1 ? { ok: false, status: 500, redirected: false, url: SAVE_URL }
              : { ok: true, status: 200, redirected: false, url: SAVE_URL });

    const n = await env.window.OfflineQueue.sync();
    assert.equal(n, 1, 'seule la première est partie');
    const restant = env.queue().map((it) => it.data.poids);
    assert.deepEqual(restant, ['70', '80'], 'les suivantes restent, dans l\'ordre');
  });

  test('une redirection vers le login ne consomme pas la série', async () => {
    // Session expirée : le serveur répond 200 sur la page de login, donc
    // `resp.ok` est vrai — sans le contrôle d'URL, la série serait jetée
    // alors qu'elle n'a jamais été enregistrée.
    const env = envHorsLigne();
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ poids: '60' }));
    env.navigator.onLine = true;
    env.setResponder(() => ({ ok: true, status: 200, redirected: true, url: 'https://app.test/login' }));

    const n = await env.window.OfflineQueue.sync();
    assert.equal(n, 0);
    assert.equal(env.queue().length, 1);
  });

  test('deux synchronisations simultanées n\'envoient pas deux fois', async () => {
    const env = envHorsLigne();
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ poids: '60' }));
    env.navigator.onLine = true;
    let liberer;
    env.setResponder(() => new Promise((res) => { liberer = () => res({ ok: true, status: 200, redirected: false, url: SAVE_URL }); }));

    const a = env.window.OfflineQueue.sync();
    const b = env.window.OfflineQueue.sync();   // pendant que la première tourne
    liberer();
    const [na, nb] = await Promise.all([a, b]);
    assert.equal(na + nb, 1, 'une seule requête aboutie');
    assert.equal(env.calls.length, 1);
  });

  test('un envoi réussi vide la file même après une redirection normale', async () => {
    // /seance/save-exo répond par un 302 vers la séance : c'est un succès.
    const env = envHorsLigne();
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ poids: '60' }));
    env.navigator.onLine = true;
    env.setResponder(() => ({ ok: true, status: 200, redirected: true, url: 'https://app.test/seance' }));
    assert.equal(await env.window.OfflineQueue.sync(), 1);
    assert.equal(env.queue().length, 0);
  });

  test('un formulaire de séance soumis hors ligne part en file', () => {
    const env = envHorsLigne();
    const form = makeForm(SAVE_URL, { exo_base: 'Squat', poids: '60' });
    env.emit('document', 'submit', submitEvent(form));
    assert.equal(env.queue().length, 1);
    assert.equal(form.defaultPrevented, true, 'le POST ne doit pas partir hors ligne');
  });

  test("l'interception écoute en phase de BULLE, jamais en capture", () => {
    // En capture, cet écouteur passe AVANT le gestionnaire du formulaire :
    // seance.js et lui mettaient chacun la série en file, et le badge
    // affichait « 2 à envoyer » pour un seul enregistrement.
    const env = envHorsLigne();
    const phases = env.phases('document', 'submit');
    assert.ok(phases.length >= 1, 'aucun écouteur submit enregistré');
    assert.equal(phases[0], false, 'le premier écouteur submit doit être en bulle');
  });

  test('une soumission déjà prise en charge n\'est pas remise en file', () => {
    const env = envHorsLigne();
    const form = makeForm(SAVE_URL, { poids: '60' });
    form.preventDefault();                       // seance.js l'a déjà traitée
    env.emit('document', 'submit', submitEvent(form));
    assert.equal(env.queue().length, 0);
  });

  test('un formulaire hors séance n\'est jamais mis en file', () => {
    const env = envHorsLigne();
    const form = makeForm('https://app.test/nutrition/add-meal', { calories: '500' });
    env.emit('document', 'submit', submitEvent(form));
    assert.equal(env.queue().length, 0);
  });

  test('en ligne, la soumission part normalement au serveur', () => {
    const env = createEnv({ scripts: ['offline.js'], online: true });
    const form = makeForm(SAVE_URL, { poids: '60' });
    env.emit('document', 'submit', submitEvent(form));
    assert.equal(env.queue().length, 0);
    assert.equal(form.defaultPrevented, false, 'le navigateur doit poster lui-même');
  });

  test('la déconnexion efface la file et les clés locales', () => {
    const env = envHorsLigne();
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ poids: '60' }));
    env.localStorage.setItem('active_session', '{"x":1}');
    env.emit('document', 'submit', submitEvent(makeForm('/logout', {})));
    assert.equal(env.window.OfflineQueue.pending(), 0);
    assert.equal(env.localStorage.getItem('active_session'), null);
  });
};
