/**
 * Retours du 23/11 sur la séance.
 *
 * - Une carte rechargée en cours d'exercice revenait FERMÉE, comme finie :
 *   le serveur la dit « terminée » dès une série (la séance compte). Elle
 *   reste ouverte tant qu'il manque des séries de travail prévues.
 */
'use strict';

const { createEnv } = require('./harness');

const S = (reps, poids, type, remarque) => ({
  reps: reps === undefined ? '' : reps,
  poids: poids === undefined ? '' : poids,
  rpe: '', remarque: remarque || '', type: type || '',
});

function carte(sets, extra) {
  const env = createEnv({ scripts: ['seance.js'] });
  return env.window.exoBlock(0, Object.assign({
    base: 'Tirage horizontal', exo_index: 0, sets, variant: 'Standard',
    p_sets: 3, completed: true,
  }, extra || {}));
}

module.exports = ({ test, assert }) => {
  test('échauffement + 1 série sur 3, rechargée : la carte reste ouverte', () => {
    const b = carte([S(12, 25, 'echauffement'), S(12, 59), S(), S()]);
    assert.strictEqual(b.open, true);
  });

  test('1 série de travail sur 3, rechargée : ouverte aussi', () => {
    assert.strictEqual(carte([S(12, 59), S(), S()]).open, true);
  });

  test('les 3 séries de travail faites (+ échauffement) : fermée', () => {
    const b = carte([S(12, 25, 'echauffement'), S(12, 59), S(12, 59), S(12, 59)]);
    assert.strictEqual(b.open, false);
  });

  test('un échauffement ne compte pas comme série de travail', () => {
    const b = carte([S(12, 25, 'echauffement'), S(12, 25, 'echauffement'), S(12, 59), S(12, 59)]);
    assert.strictEqual(b.open, true);
  });

  test('exercice passé (« Skip ») : fermé', () => {
    assert.strictEqual(carte([S(0, 0, '', 'SKIP')]).open, false);
  });

  test('pas encore commencé : ouvert, comme avant', () => {
    assert.strictEqual(carte([S(), S(), S()], { completed: false }).open, true);
  });
};
