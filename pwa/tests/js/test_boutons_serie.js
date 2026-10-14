/**
 * Boutons − / + de la série en cours (style « Instrument », 14/10/2026).
 * Ils partent de la valeur montrée (tapée, sinon grisée) et, pour la
 * charge, passent à la charge d'à côté déjà soulevée : les plaques d'une
 * machine ne vont pas de 2,5 en 2,5 kg.
 */
'use strict';

const { createEnv } = require('./harness');

function bloc(extra) {
  const env = createEnv({ scripts: ['seance.js'] });
  const b = env.window.exoBlock(0, Object.assign({
    base: 'Machine adducteurs', exo_index: 0, variant: 'Standard',
    sets: [{ reps: '', poids: '' }],
  }, extra || {}));
  return b;
}

module.exports = ({ test, assert }) => {

test('boutons : les reps partent de la valeur grisée (objectif)', () => {
  const b = bloc({ suggestion: { reps: 8, poids: 60 } });
  const s = b.sets[0];
  b.ajuster(s, 'reps', 1);
  assert.equal(s.reps, 9);
  b.ajuster(s, 'reps', -1);
  b.ajuster(s, 'reps', -1);
  assert.equal(s.reps, 7);
});

test('boutons : jamais sous zéro', () => {
  const b = bloc({ sets: [{ reps: 0, poids: 0 }] });
  b.ajuster(b.sets[0], 'reps', -1);
  b.ajuster(b.sets[0], 'poids', -1);
  assert.equal(b.sets[0].reps, 0);
  assert.equal(b.sets[0].poids, 0);
});

test('boutons : la charge passe à la plaque suivante de la machine', () => {
  // Adducteurs du vrai compte : 52, 59, 66, 73, 79, 86, 93, 100 (écart 7).
  const b = bloc({ sets: [{ reps: '', poids: 73 }],
                   echelle: { charges: [52, 59, 66, 73, 79, 86, 93, 100], pas: 7 } });
  const s = b.sets[0];
  b.ajuster(s, 'poids', 1);
  assert.equal(s.poids, 79);
  b.ajuster(s, 'poids', -1);
  b.ajuster(s, 'poids', -1);
  assert.equal(s.poids, 66);
});

test('boutons : au-delà de ce qui a été soulevé, un écart habituel de plus', () => {
  const b = bloc({ sets: [{ reps: '', poids: 100 }],
                   echelle: { charges: [52, 59, 66, 73, 79, 86, 93, 100], pas: 7 } });
  b.ajuster(b.sets[0], 'poids', 1);
  assert.equal(b.sets[0].poids, 107);
});

test('boutons : poulie de 2,2 à 2,3 kg, sans virgule flottante', () => {
  const b = bloc({ sets: [{ reps: '', poids: 24.8 }],
                   echelle: { charges: [22.5, 24.8, 27, 29.3], pas: 2.3 } });
  const s = b.sets[0];
  b.ajuster(s, 'poids', 1);
  assert.equal(s.poids, 27);
  b.ajuster(s, 'poids', 1);
  b.ajuster(s, 'poids', 1);
  assert.equal(s.poids, 31.6);
});

test('boutons : un trou dans les charges ne fait pas sauter deux crans', () => {
  // Presse : 100, 120, puis 160 une fois. De 120, « + » mène à 140.
  const b = bloc({ sets: [{ reps: '', poids: 120 }],
                   echelle: { charges: [100, 120, 160], pas: 20 } });
  b.ajuster(b.sets[0], 'poids', 1);
  assert.equal(b.sets[0].poids, 140);
});

test('boutons : sans charge tapée, on part de la charge proposée', () => {
  const b = bloc({ suggestion: { reps: 8, poids: 60 } });
  b.ajuster(b.sets[0], 'poids', 1);
  assert.equal(b.sets[0].poids, 62.5);   // pas par défaut, sans historique
});

};
