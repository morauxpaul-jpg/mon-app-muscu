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

  test('se déconnecter avec des envois en attente prévient d’abord', () => {
    // Avant, la file partait à la poubelle sans un mot.
    const env = envHorsLigne();
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ poids: '60' }));
    const form = makeForm('/logout', {});
    env.emit('document', 'submit', submitEvent(form));
    assert.ok(form.defaultPrevented, 'le premier appui ne déconnecte pas');
    assert.equal(env.window.OfflineQueue.pending(), 1, 'rien n’est effacé');
  });

  test('le second appui déconnecte et efface la file et les clés locales', () => {
    const env = envHorsLigne();
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ poids: '60' }));
    env.localStorage.setItem('active_session', '{"x":1}');
    env.emit('document', 'submit', submitEvent(makeForm('/logout', {})));
    const second = makeForm('/logout', {});
    env.emit('document', 'submit', submitEvent(second));
    assert.ok(!second.defaultPrevented);
    assert.equal(env.window.OfflineQueue.pending(), 0);
    assert.equal(env.localStorage.getItem('active_session'), null);
  });

  test('file vide : la déconnexion part tout de suite', () => {
    const env = envHorsLigne();
    env.localStorage.setItem('active_session', '{"x":1}');
    const form = makeForm('/logout', {});
    env.emit('document', 'submit', submitEvent(form));
    assert.ok(!form.defaultPrevented);
    assert.equal(env.localStorage.getItem('active_session'), null);
  });

  // ── Un exercice, un seul envoi en attente ─────────────────────

  test('un envoi plus récent du même exercice remplace l’ancien', () => {
    // L'enregistrement d'un exercice réécrit toutes ses séries : rejouer
    // l'état à 1 série APRÈS celui à 3 séries en effacerait deux.
    const env = envHorsLigne();
    const Q = env.window.OfflineQueue;
    Q.enqueue(SAVE_URL, makeFormData({ series: '1' }), 'Squat');
    Q.enqueue(SAVE_URL, makeFormData({ series: '1' }), 'Rowing');
    Q.enqueue(SAVE_URL, makeFormData({ series: '3' }), 'Squat');
    const q = env.queue();
    assert.equal(q.length, 2);
    assert.deepEqual(q.map((it) => it.cle), ['Rowing', 'Squat']);
    assert.equal(q[1].data.series, '3');
  });

  test('sans clé, rien n’est dédoublonné', () => {
    const env = envHorsLigne();
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ a: '1' }));
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ a: '1' }));
    assert.equal(env.queue().length, 2);
  });

  test('un envoi direct réussi retire ce qui attendait pour le même exercice', () => {
    const env = envHorsLigne();
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ series: '1' }), 'Squat');
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ series: '1' }), 'Rowing');
    env.window.OfflineQueue.drop('Squat');
    assert.deepEqual(env.queue().map((it) => it.cle), ['Rowing']);
  });

  // ── Rejeu ─────────────────────────────────────────────────────

  test('le rejeu utilise le jeton CSRF de la page, pas celui gardé', async () => {
    // Après une reconnexion, l'ancien jeton valait 400 et bloquait la file
    // pour toujours.
    const env = envHorsLigne();
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ _csrf: 'ancien', poids: '60' }));
    env.document.querySelector = (sel) => (sel === 'meta[name="csrf-token"]'
      ? { getAttribute: () => 'nouveau' } : null);
    env.navigator.onLine = true;
    await env.window.OfflineQueue.sync();
    assert.equal(new URLSearchParams(env.calls[0].body).get('_csrf'), 'nouveau');
    assert.equal(env.queue().length, 0);
  });

  test('un envoi refusé pour de bon est mis de côté et ne bloque plus la suite', async () => {
    const env = envHorsLigne();
    for (const poids of ['60', '70']) {
      env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ poids }));
    }
    env.navigator.onLine = true;
    env.setResponder((url, init, i) =>
      i === 0 ? { ok: false, status: 400, redirected: false, url: SAVE_URL }
              : { ok: true, status: 200, redirected: false, url: SAVE_URL });
    const n = await env.window.OfflineQueue.sync();
    assert.equal(n, 1, 'le second est passé');
    assert.equal(env.queue().length, 0);
    const rejets = JSON.parse(env.localStorage.getItem('muscu_offline_rejets'));
    assert.equal(rejets.length, 1, 'le refusé est gardé, pas jeté');
    assert.equal(rejets[0].data.poids, '60');
  });

  test('une erreur serveur (5xx) garde la file telle quelle', async () => {
    const env = envHorsLigne();
    env.window.OfflineQueue.enqueue(SAVE_URL, makeFormData({ poids: '60' }));
    env.navigator.onLine = true;
    env.setResponder(() => ({ ok: false, status: 503, redirected: false, url: SAVE_URL }));
    await env.window.OfflineQueue.sync();
    assert.equal(env.queue().length, 1);
  });
};
