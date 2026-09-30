/**
 * Cardio : durée, distance, vitesse — deux valeurs sur trois suffisent.
 *
 * Le formulaire calculait la vitesse à partir de la durée et de la distance.
 * Dans ce sens seulement, et seulement pour l'AFFICHER : elle n'arrivait
 * jamais en base. Or on connaît souvent l'inverse — le tapis affiche 10 km/h
 * pendant 30 minutes, et c'est la distance qu'on ignore.
 *
 * La règle de conversion se devinait à partir du LIBELLÉ de l'unité
 * (`indexOf("km/h")`, `indexOf("/min")`). « Allure (min/500m) » ne tombait
 * dans aucun cas : l'allure du rameur ne se calculait jamais, en silence.
 * Elle est maintenant nommée, et la table vient du serveur.
 */
'use strict';

const { createEnv } = require('./harness');

// La table telle que le serveur la sert (core/seance_cardio.py).
const UNITES = {
  "Course":   { dist: "Distance (km)",       vit: "Vitesse (km/h)",    regle: "par_heure", pas: "0.01" },
  "Natation": { dist: "Distance (km)",       vit: "Vitesse (m/min)",   regle: "m_par_min", pas: "0.01" },
  "Corde":    { dist: "Nombre de sauts",     vit: "Sauts/min",         regle: "par_min",   pas: "1" },
  "Rameur":   { dist: "Distance (km)",       vit: "Allure (min/500m)", regle: "",          pas: "0.01" },
  "HIIT":     { dist: "Rounds",              vit: "",                  regle: "",          pas: "1" },
  "Autre":    { dist: "Distance (km)",       vit: "Vitesse (km/h)",    regle: "par_heure", pas: "0.01" },
};

function cardio(etat) {
  const env = createEnv({
    scripts: ['seance.js'],
    json: { 'seance-config': { cardioUnits: UNITES } },
  });
  return Object.assign(env.window.cardioBlock(), etat || {});
}

module.exports = ({ test, assert }) => {

  test('la distance se déduit de la vitesse', () => {
    const c = cardio({ activite: 'Course', duree: '30', vitesse: '10', distance: '' });
    assert.equal(c.autoDistance(), '5.00');
  });

  test('la vitesse se déduit de la distance', () => {
    const c = cardio({ activite: 'Course', duree: '30', distance: '5', vitesse: '' });
    assert.equal(c.autoVitesse(), '10.00');
  });

  test('la natation compte en mètres par minute', () => {
    const c = cardio({ activite: 'Natation', duree: '20', distance: '1', vitesse: '' });
    assert.equal(c.autoVitesse(), '50.00');
  });

  test('les sauts à la corde ne prennent pas de décimale', () => {
    const c = cardio({ activite: 'Corde', duree: '5', distance: '300', vitesse: '' });
    assert.equal(c.autoVitesse(), '60');
  });

  test("l'allure du rameur ne s'invente pas", () => {
    // min/500 m n'est pas une division : deviner d'après le libellé donnait
    // silencieusement une suggestion vide, ce qui était juste par accident.
    const c = cardio({ activite: 'Rameur', duree: '20', distance: '5', vitesse: '' });
    assert.equal(c.autoVitesse(), '');
    assert.equal(c.autoDistance(), '');
  });

  test('le HIIT ne parle pas de vitesse', () => {
    const c = cardio({ activite: 'HIIT', duree: '20', distance: '3', vitesse: '' });
    assert.equal(c.autoVitesse(), '');
  });

  test('sans durée, rien ne se déduit', () => {
    const c = cardio({ activite: 'Course', duree: '', vitesse: '10', distance: '' });
    assert.equal(c.autoDistance(), '');
  });

  test('la virgule décimale est acceptée', () => {
    const c = cardio({ activite: 'Course', duree: '30', vitesse: '10,5', distance: '' });
    assert.equal(c.autoDistance(), '5.25');
  });

  test('une activité inconnue retombe sur « Autre »', () => {
    const c = cardio({ activite: 'Zumba', duree: '30', vitesse: '10', distance: '' });
    assert.equal(c.autoDistance(), '5.00');
  });

  test('sans table servie, rien ne casse', () => {
    // La config peut manquer (page servie depuis le cache hors ligne).
    const env = createEnv({ scripts: ['seance.js'] });
    const c = Object.assign(env.window.cardioBlock(),
                            { activite: 'Course', duree: '30', vitesse: '10' });
    assert.equal(c.autoDistance(), '');
    assert.equal(c.autoVitesse(), '');
  });
};
