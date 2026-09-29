/**
 * Saisie série par série (static/js/seance.js).
 *
 * Le tableau de six colonnes donnait, sur 375 px : Reps 67, Poids 70,
 * RPE 25, Remarque 87 — mesuré dans un navigateur. Une série remplie se
 * replie donc en une ligne et seule la courante reste ouverte.
 *
 * C'est de la MISE EN PAGE. Le test qui compte ici est celui qui vérifie
 * que rien de neuf ne part en base : `serializedSets()` doit rendre
 * exactement les mêmes quatre champs qu'avant.
 */
'use strict';

const { createEnv } = require('./harness');

/** Un bloc exercice prêt à exercer, sans Alpine ni DOM. */
function bloc(sets, extra) {
  const env = createEnv({ scripts: ['seance.js'] });
  const d = Object.assign({
    base: 'Développé couché',
    exo_index: 0,
    sets: sets,
    variant: 'Standard',
  }, extra || {});
  const b = env.window.exoBlock(0, d);
  b._majFaits();          // ce que fait `init()` après le brouillon
  return b;
}

const S = (reps, poids, rpe, remarque) => ({
  reps: reps === undefined ? '' : reps,
  poids: poids === undefined ? '' : poids,
  rpe: rpe || '',
  remarque: remarque || '',
});

module.exports = ({ test, assert }) => {

  // ── Ce qui part en base ne change pas ─────────────────────────

  test('les séries envoyées gardent exactement leurs quatre champs', () => {
    const b = bloc([S(8, 82.5, '8', 'facile'), S()]);
    b.serieFaite(0);
    const envoye = JSON.parse(b.serializedSets());
    assert.deepEqual(Object.keys(envoye[0]).sort(),
                     ['poids', 'remarque', 'reps', 'rpe']);
    assert.equal(envoye[0].reps, 8);
    assert.equal(envoye[0].poids, 82.5);
    assert.equal(envoye[0].rpe, '8');
    assert.equal(envoye[0].remarque, 'facile');
  });

  test("marquer une série faite n'ajoute rien à ce qui est envoyé", () => {
    const b = bloc([S(8, 80), S(8, 80)]);
    const avant = b.serializedSets();
    b.serieFaite(0);
    b.serieFaite(1);
    assert.equal(b.serializedSets(), avant,
                 'le repli est de l’affichage, pas de la donnée');
  });

  // ── Quelle série est ouverte ──────────────────────────────────

  test('une série déjà remplie s’ouvre repliée', () => {
    const b = bloc([S(8, 80), S(), S()]);
    assert.ok(b.estFait(0));
    assert.equal(b.indexCourant(), 1);
  });

  test('une série à zéro rep n’est pas faite', () => {
    const b = bloc([S(0, 80), S()]);
    assert.ok(!b.estFait(0));
    assert.equal(b.indexCourant(), 0);
  });

  test('valider une série ouvre la suivante', () => {
    const b = bloc([S(8, 80), S(), S()]);
    b.serieFaite(1);
    // `faits` vient du bac à sable : son Array.prototype n'est pas celui
    // de Node, donc deepEqual le refuserait tel quel.
    assert.deepEqual(Array.from(b.faits).sort(), [0, 1]);
    assert.equal(b.indexCourant(), 2);
  });

  test('tout validé, plus aucune série ouverte', () => {
    const b = bloc([S(8, 80), S(8, 80)]);
    assert.equal(b.indexCourant(), -1);
  });

  test('rouvrir une série la remet en cours', () => {
    const b = bloc([S(8, 80), S(8, 80)]);
    b.rouvrir(0);
    assert.ok(!b.estFait(0));
    assert.equal(b.indexCourant(), 0);
  });

  test('retirer une série ne rouvre pas les voisines', () => {
    // Les index glissent : sans recalcul, retirer la 1re ferait passer la 2e
    // (faite) pour la 1re (non faite), donc une série faite se rouvrirait.
    const b = bloc([S(8, 80), S(8, 80), S()]);
    b.removeSet(0);
    assert.equal(b.sets.length, 2);
    assert.ok(b.estFait(0), 'la série restante reste faite');
    assert.equal(b.indexCourant(), 1);
  });

  test('ajouter une série la met en attente, pas en faite', () => {
    const b = bloc([S(8, 80)]);
    b.addSet();
    assert.ok(!b.estFait(1));
    assert.equal(b.indexCourant(), 1);
  });

  // ── Le résumé d'une série repliée ─────────────────────────────

  test('le poids s’écrit avec une virgule', () => {
    const b = bloc([S(8, 82.5)]);
    assert.equal(b.resumeSerie(b.sets[0]), '8 reps · 82,5 kg');
  });

  test('le résumé porte le RPE et la remarque quand ils existent', () => {
    const b = bloc([S(8, 80, '8.5', 'dernière dure')]);
    assert.equal(b.resumeSerie(b.sets[0]),
                 '8 reps · 80 kg · RPE 8.5 · dernière dure');
  });

  test('au poids du corps, pas de kilos dans le résumé', () => {
    // Un poids traîne souvent dans la série — pré-rempli depuis une variante
    // « Lesté » passée. Il ne doit pas ressortir pour autant, sinon le test
    // ne distinguerait pas un champ vide d'un champ ignoré.
    const b = bloc([S(12, 80)], { is_bw_base: true });
    assert.ok(!b.showWeight, 'le décor du test doit bien être au poids du corps');
    assert.equal(b.resumeSerie(b.sets[0]), '12 reps');
  });

  test('une série vide ne prétend rien', () => {
    const b = bloc([S()]);
    assert.equal(b.resumeSerie(b.sets[0]), '—');
  });

  // ── L'objectif affiché ────────────────────────────────────────

  test('l’objectif reprend la suggestion, virgule comprise', () => {
    const b = bloc([S()]);
    b.suggestion = { reps: 8, poids: 82.5 };
    assert.equal(b.objectifTexte(), 'objectif 8 × 82,5 kg');
  });

  test('sans suggestion, pas d’objectif inventé', () => {
    const b = bloc([S()]);
    b.suggestion = null;
    assert.equal(b.objectifTexte(), '');
  });

  test('au poids du corps, l’objectif ne parle pas de kilos', () => {
    const b = bloc([S()], { is_bw_base: true });
    b.suggestion = { reps: 12, poids: 0 };
    assert.equal(b.objectifTexte(), 'objectif 12');
  });
};
