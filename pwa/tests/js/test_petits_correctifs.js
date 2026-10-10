/**
 * Petits correctifs de l'audit du 06/10/2026 (profil 1, le débutant).
 *
 * - « Série faite » recopie la charge dans la série suivante encore vide :
 *   on retapait son poids à chaque série.
 * - « Terminer » sur une séance où rien n'est saisi ne dit plus
 *   « Séance terminée 💪 » : `seanceVide()` le détecte.
 */
'use strict';

const { createEnv } = require('./harness');

const S = (reps, poids, type) => ({
  reps: reps === undefined ? '' : reps,
  poids: poids === undefined ? '' : poids,
  rpe: '',
  remarque: '',
  type: type || '',
});

/** Un bloc exercice prêt à exercer, sans Alpine ni DOM. */
function bloc(sets, env) {
  env = env || createEnv({ scripts: ['seance.js'] });
  const b = env.window.exoBlock(0, {
    base: 'Développé couché', exo_index: 0, sets, variant: 'Standard',
  });
  b._majFaits();
  return { env, b };
}

/** Un bloc enregistré comme le fait `init()` (sans brouillon ni Alpine). */
function blocInscrit(env, sets) {
  const { b } = bloc(sets, env);
  b.$watch = () => {};
  b.init();
  return b;
}

module.exports = ({ test, assert }) => {

  // ── La charge passe à la série suivante ──────────────────────

  test('« Série faite » recopie la charge dans la série suivante vide', () => {
    const { b } = bloc([S(8, 40), S(), S()]);
    b.serieFaite(0);
    assert.equal(b.sets[1].poids, 40);
    assert.equal(b.sets[1].reps, '', 'les répétitions restent à taper');
    assert.equal(b.sets[2].poids, '', 'une seule série à la fois');
  });

  test('une charge déjà tapée dans la série suivante ne bouge pas', () => {
    const { b } = bloc([S(8, 40), S('', 45)]);
    b.serieFaite(0);
    assert.equal(b.sets[1].poids, 45);
  });

  test("rien ne passe depuis ni vers un échauffement", () => {
    const depuis = bloc([S(10, 20, 'echauffement'), S()]).b;
    depuis.serieFaite(0);
    assert.equal(depuis.sets[1].poids, '');

    const vers = bloc([S(8, 60), S('', '', 'echauffement')]).b;
    vers.serieFaite(0);
    assert.equal(vers.sets[1].poids, '');
  });

  test('la dernière série ne recopie rien (et ne plante pas)', () => {
    const { b } = bloc([S(8, 40)]);
    b.serieFaite(0);
    assert.equal(b.sets.length, 1);
    assert.ok(b.estFait(0));
  });

  // ── Terminer une séance vide ─────────────────────────────────

  test('sans aucune série saisie, la séance est vide', () => {
    const env = createEnv({ scripts: ['seance.js'] });
    blocInscrit(env, [S(), S()]);
    blocInscrit(env, [S()]);
    assert.equal(env.window.seanceVide(), true);
  });

  test('une seule série remplie suffit : la séance compte', () => {
    const env = createEnv({ scripts: ['seance.js'] });
    blocInscrit(env, [S(), S()]);
    blocInscrit(env, [S(8, 40)]);
    assert.equal(env.window.seanceVide(), false);
  });

  test('une charge sans répétitions ne compte pas comme une série', () => {
    const env = createEnv({ scripts: ['seance.js'] });
    blocInscrit(env, [S('', 40)]);
    assert.equal(env.window.seanceVide(), true);
  });

  test('un cardio déjà enregistré suffit aussi', () => {
    const env = createEnv({ scripts: ['seance.js'] });
    blocInscrit(env, [S()]);
    env.document.querySelector = (sel) => (sel === '[data-cardio-fait]' ? {} : null);
    assert.equal(env.window.seanceVide(), false);
  });
};
