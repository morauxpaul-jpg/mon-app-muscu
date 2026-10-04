/**
 * Recherche d'aliments de la page Nutrition (static/js/nutrition.js).
 *
 * Le classement décide de ce qui est noté : « riz » qui propose d'abord le
 * riz CRU (360 kcal / 100 g) fausse la journée si l'on ne lit pas la ligne.
 * Et le panier envoyé au serveur doit porter l'aliment et la quantité, pas
 * des totaux calculés par le navigateur.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { createEnv } = require('./harness');

const FOODS = [
  { n: 'Riz blanc cru', k: 360, p: 7, c: 79, f: 0.6, g: 'Féculents', r: 0, u: [['1 portion', 70], ['100 g', 100]] },
  { n: 'Riz blanc cuit', k: 130, p: 2.7, c: 28, f: 0.3, g: 'Féculents', r: 0, u: [['1 portion', 200], ['100 g', 100]] },
  { n: 'Blanc de poulet cuit', k: 165, p: 31, c: 0, f: 3.6, g: 'Viandes', r: 0, u: [['1 filet', 150], ['100 g', 100]] },
  { n: 'Poulet curry coco', k: 150, p: 12, c: 6, f: 9, g: 'Plats', r: 1, u: [['1 assiette', 350], ['100 g', 100]] },
  { n: 'Banane', k: 89, p: 1.1, c: 20, f: 0.3, g: 'Fruits', r: 0, u: [['1 banane', 120], ['100 g', 100]] },
];

function form(recents) {
  const env = createEnv({ scripts: [] });
  vm.runInContext(
    'var FOODS = ' + JSON.stringify(FOODS) + '; var MEAL_LABELS = {dejeuner: "Déjeuner"};' +
    'var RECENTS = ' + JSON.stringify(recents || []) + ';', env.sandbox);
  const src = fs.readFileSync(path.join(__dirname, '..', '..', 'static', 'js', 'nutrition.js'), 'utf8');
  vm.runInContext(src, env.sandbox, { filename: 'nutrition.js' });
  return { env, f: vm.runInContext('mealForm()', env.sandbox) };
}

function chercher(f, q) {
  f.q = q;
  f.search();
  return Array.from(f.results, (r) => r.n);   // tableau du contexte de test (pas celui du bac à sable)
}

module.exports = ({ test, assert }) => {
  test('« riz » propose le riz cuit avant le riz cru', () => {
    const { f } = form();
    assert.deepEqual(chercher(f, 'riz').slice(0, 2), ['Riz blanc cuit', 'Riz blanc cru']);
    assert.equal(chercher(f, 'riz cru')[0], 'Riz blanc cru');
  });

  test('un aliment simple passe avant un plat', () => {
    const { f } = form();
    assert.deepEqual(chercher(f, 'poulet'), ['Blanc de poulet cuit', 'Poulet curry coco']);
  });

  test('un aliment déjà mangé passe en tête, sans doublon', () => {
    const recent = { ...FOODS[2], g: 'Récent', r: -1, recent: true,
                     u: [['comme la dernière fois', 180], ['1 filet', 150], ['100 g', 100]] };
    const { f } = form([{ ...FOODS[3], g: 'Récent', r: -1, u: [['comme la dernière fois', 300]] }, recent]);
    const res = chercher(f, 'poulet');
    assert.equal(res.length, 2);
    assert.equal(f.results[0].recent || f.results[1].recent, true);
  });

  test('le panier envoie aliment et quantité, sans « comme la dernière fois »', () => {
    const recent = { ...FOODS[1], g: 'Récent', r: -1, u: [['comme la dernière fois', 180], ['100 g', 100]] };
    const { f } = form([recent]);
    f.pickFood(recent);
    f.basket[0].qty = 1.5;
    const items = JSON.parse(f.basketItems());
    assert.equal(items.length, 1);
    assert.equal(items[0].n, 'Riz blanc cuit');
    assert.equal(items[0].grams, 270);
    assert.deepEqual(items[0].u, [['100 g', 100]]);
    assert.equal('calories' in items[0], false);
  });

  test('la recherche Open Food Facts affiche ses résultats ou dit pourquoi', async () => {
    const { env, f } = form();
    env.setResponder(() => ({ json: () => Promise.resolve({ ok: true, foods: [{ n: 'Skyr', k: 60, p: 10, c: 4, f: 0.2, u: [['100 g', 100]] }] }) }));
    f.q = 'skyr';
    f.offSearch();
    await new Promise((r) => setImmediate(r));
    await new Promise((r) => setImmediate(r));
    assert.equal(env.calls[0].url, '/nutrition/recherche?q=skyr');
    assert.equal(f.offResults.length, 1);
    env.setResponder(() => ({ json: () => Promise.resolve({ ok: false, error: 'Recherche indisponible' }) }));
    f.q = 'pain de mie';
    f.offSearch();
    await new Promise((r) => setImmediate(r));
    await new Promise((r) => setImmediate(r));
    assert.equal(f.offError, 'Recherche indisponible');
  });
};
