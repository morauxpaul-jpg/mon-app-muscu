/**
 * Recherche dans la bibliothèque d'exercices.
 *
 * L'ancienne version faisait un `indexOf` brut sur le nom. Taper « ecarte »
 * sans accent ne trouvait rien, et on en concluait que l'exercice n'existait
 * pas — c'est ce qui a bloqué une création de programme. Au clavier d'un
 * téléphone, personne ne met les accents.
 */
'use strict';

const path = require('path');
const lib = require(path.join(__dirname, '..', '..', 'static', 'js',
                              'exercise-library.js'));

function cherche(q) {
  const out = [];
  for (const groupe of Object.keys(lib.EXERCISE_LIBRARY)) {
    for (const ex of lib.EXERCISE_LIBRARY[groupe]) {
      if (lib.exerciseMatches(ex, q)) out.push(ex.name);
    }
  }
  return out;
}

module.exports = ({ test, assert }) => {
  test('la recherche sans accents trouve quand meme', () => {
    assert.ok(cherche('ecarte').includes('Écarté poulie vis-à-vis'));
    assert.ok(cherche('developpe couche').length >= 2);
  });

  test('la casse ne change rien', () => {
    assert.deepStrictEqual(cherche('ECARTE POULIE'), cherche('ecarte poulie'));
  });

  test("l'ordre des mots ne change rien", () => {
    assert.ok(cherche('adducteur machine').includes('Machine adducteurs'));
    assert.ok(cherche('machine adducteur').includes('Machine adducteurs'));
  });

  test('le surnom anglais trouve l exercice', () => {
    assert.ok(cherche('pec fly').includes('Pec deck (machine)'));
    assert.ok(cherche('bench press').includes('Développé couché barre'));
  });

  test('une recherche vide ne filtre rien', () => {
    assert.ok(cherche('').length > 50, 'attendu toute la bibliotheque');
  });

  test('un mot inconnu ne ramene rien', () => {
    assert.deepStrictEqual(cherche('zumba intergalactique'), []);
  });

  test('un mot en plus restreint, il n elargit pas', () => {
    const deux = cherche('ecarte poulie');
    assert.ok(!deux.includes('Écarté couché haltères'), deux.join(', '));
  });
};
