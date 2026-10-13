/**
 * Page Programme (style « Instrument », 13/10/2026) : la ligne sous le nom
 * d'une séance résume son contenu, « 3 exercices · 10 séries · pecs, épaules ».
 */
'use strict';

const { createEnv } = require('./harness');

function app(prog) {
  const env = createEnv({ scripts: ['programme.js'] });
  const a = env.sandbox.programmeApp();
  a.prog = prog;
  return a;
}

module.exports = ({ test, assert }) => {

test('programme : résumé d\'une séance (exercices, séries, muscles)', () => {
  const a = app({
    Push: [
      { name: 'Développé couché', sets: 4, muscle: 'Pecs' },
      { name: 'Développé militaire', sets: '3', muscle: 'Épaules, Triceps' },
      { name: 'Dips', sets: 3, muscle: 'Triceps' },
    ],
  });
  assert.equal(a.resumeSeance('Push'), '3 exercices · 10 séries · pecs, épaules, triceps');
});

test('programme : résumé sans muscle choisi, au singulier, et séance vide', () => {
  const a = app({
    Gainage: [{ name: 'Planche', sets: 1, muscle: 'Autre' }],
    Vide: [],
    Large: [{ name: 'A', sets: 2, muscle: 'Pecs,Dos,Biceps,Triceps' }],
  });
  assert.equal(a.resumeSeance('Gainage'), '1 exercice · 1 série');
  assert.equal(a.resumeSeance('Vide'), '0 exercice');
  assert.equal(a.resumeSeance('Inconnue'), '0 exercice');
  assert.equal(a.resumeSeance('Large'), '1 exercice · 2 séries · pecs, dos, biceps…');
});

};
