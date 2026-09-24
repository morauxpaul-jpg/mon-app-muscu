/**
 * Chrono de repos (static/js/rest-timer.js) — continuité hors de l'app.
 *
 * Deux mécaniques selon le support, et il ne faut surtout pas les cumuler :
 *   • app native  → compte à rebours dans la barre de notification, donc on
 *     pose son téléphone. Forcer l'écran allumé irait contre l'usage.
 *   • web / PWA   → aucune API pour faire défiler une notification. On garde
 *     l'écran allumé, sans quoi le navigateur gèle la page et le bip de fin
 *     arrive en retard, voire jamais.
 */
'use strict';

const { createEnv } = require('./harness');

const attendre = () => new Promise((r) => setImmediate(r));

module.exports = ({ test, assert }) => {

  // ── Web : verrou d'écran ───────────────────────────────────────

  test("le repos garde l'écran allumé sur le web", async () => {
    const env = createEnv({ scripts: ['rest-timer.js'] });
    env.window.RestTimer.start(90);
    await attendre();
    assert.deepEqual(env.wakeLog, ['request:screen']);
  });

  test("passer le repos rend l'écran", async () => {
    const env = createEnv({ scripts: ['rest-timer.js'] });
    env.window.RestTimer.start(90);
    await attendre();
    env.window.RestTimer.skip();
    await attendre();
    assert.deepEqual(env.wakeLog, ['request:screen', 'release']);
  });

  test("terminer la séance rend l'écran", async () => {
    const env = createEnv({ scripts: ['rest-timer.js'] });
    env.window.RestTimer.start(90);
    await attendre();
    env.window.RestTimer.finishSession();
    await attendre();
    assert.ok(env.wakeLog.includes('release'), env.wakeLog.join(','));
  });

  test("un navigateur sans verrou d'écran ne casse rien", async () => {
    const env = createEnv({ scripts: ['rest-timer.js'], wakeLock: false });
    env.window.RestTimer.start(90);
    await attendre();
    assert.equal(env.window.RestTimer.isRunning(), true);
    assert.deepEqual(env.wakeLog, []);
  });

  // ── App native : compte à rebours dans la barre ────────────────

  test("l'app native affiche le compte à rebours au lieu de forcer l'écran", async () => {
    const env = createEnv({ scripts: ['rest-timer.js'], nativeTimer: true });
    env.window.RestTimer.start(90);
    await attendre();
    assert.deepEqual(env.wakeLog, [], "l'écran ne doit pas être forcé en natif");
    const depart = env.nativeLog.find((a) => a[0] === 'start');
    assert.ok(depart, 'le compte à rebours natif n’a pas été posé');
  });

  test("l'échéance envoyée au natif est absolue, pas une durée", async () => {
    // C'est ce qui rend le compteur juste après une mise en veille ou la mort
    // du processus : il n'y a pas d'état à reconstruire, juste une heure.
    const env = createEnv({ scripts: ['rest-timer.js'], nativeTimer: true });
    const avant = Date.now();
    env.window.RestTimer.start(90);
    await attendre();
    const [, echeance] = env.nativeLog.find((a) => a[0] === 'start');
    assert.ok(echeance >= avant + 89000 && echeance <= Date.now() + 91000,
      'échéance attendue ~90 s dans le futur, reçu ' + (echeance - avant) + ' ms');
  });

  test("passer le repos retire la notification native", async () => {
    const env = createEnv({ scripts: ['rest-timer.js'], nativeTimer: true });
    env.window.RestTimer.start(90);
    await attendre();
    env.window.RestTimer.skip();
    await attendre();
    assert.ok(env.nativeLog.some((a) => a[0] === 'stop'));
  });

  test('revenir dans l’app repose la notification si elle a été balayée', async () => {
    const env = createEnv({ scripts: ['rest-timer.js'], nativeTimer: true });
    env.window.RestTimer.start(90);
    await attendre();
    const avant = env.nativeLog.filter((a) => a[0] === 'start').length;
    env.emit('document', 'visibilitychange', {});
    await attendre();
    const apres = env.nativeLog.filter((a) => a[0] === 'start').length;
    assert.ok(apres > avant, 'la notification doit être reposée au retour');
  });

  // ── État partagé ───────────────────────────────────────────────

  test("l'échéance survit à un changement de page", async () => {
    // L'état vit dans localStorage, pas dans la page : naviguer entre deux
    // onglets ne doit pas couper le repos en cours.
    const env = createEnv({ scripts: ['rest-timer.js'] });
    env.window.RestTimer.start(90);
    await attendre();
    const etat = JSON.parse(env.localStorage.getItem('rest_timer_state'));
    assert.ok(etat.end > Date.now() + 88000);
    assert.equal(etat.total, 90);
  });
};
