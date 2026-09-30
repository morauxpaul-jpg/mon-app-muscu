/**
 * Distance GPS (static/js/gps-track.js).
 *
 * Sommer les positions brutes donne un chiffre faux, et faux vers le HAUT :
 * à l'arrêt le point tremble de quelques mètres à chaque relevé, une position
 * imprécise invente des dizaines de mètres, un recalage en ajoute deux cents
 * d'un coup. Chaque test ci-dessous correspond à un de ces cas.
 *
 * Le dernier groupe compte ce qui a été perdu : un compteur qui sous-estime
 * en silence est pire qu'un compteur absent.
 */
'use strict';

const { createEnv } = require('./harness');

function suivi(options) {
  const env = createEnv({ scripts: ['gps-track.js'] });
  return env.window.GpsTrack.creerSuivi(options);
}

/** Un point à `m` mètres au nord de la référence, à l'instant `t` (s). */
const NORD_PAR_METRE = 1 / 111320;
const pt = (m, t, precision) => ({
  lat: 48.8566 + m * NORD_PAR_METRE, lon: 2.3522,
  precision: precision == null ? 5 : precision, t: t * 1000,
});

module.exports = ({ test, assert }) => {

  // ── Ce qui compte ─────────────────────────────────────────────

  test('deux points alignés donnent la distance entre eux', () => {
    const s = suivi();
    s.ajouter(pt(0, 0));
    s.ajouter(pt(100, 20));
    assert.equal(s.km(), 0.1);
  });

  test('la distance s’accumule le long du parcours', () => {
    const s = suivi();
    for (let i = 0; i <= 10; i++) s.ajouter(pt(i * 50, i * 10));
    // À un mètre près : `pt()` place ses points avec une approximation
    // plate du degré, la haversine calcule sur la sphère. C'est l'ACCUMULATION
    // qu'on vérifie ici, pas la constante géodésique.
    assert.ok(Math.abs(s.km() - 0.5) < 0.002, 's.km() = ' + s.km());
  });

  test('la première position ne crée pas de distance', () => {
    const s = suivi();
    s.ajouter(pt(0, 0));
    assert.equal(s.km(), 0);
  });

  // ── Les trois façons d’inventer des mètres ────────────────────

  test('une position imprécise est écartée', () => {
    // Un rayon de 60 m ne permet pas d’affirmer qu’on a bougé de 30.
    const s = suivi();
    s.ajouter(pt(0, 0));
    const r = s.ajouter(pt(30, 10, 60));
    assert.equal(r.raison, 'precision');
    assert.equal(s.km(), 0);
  });

  test('le tremblement à l’arrêt n’ajoute rien', () => {
    // Trente relevés de 2 m pendant qu’on reprend son souffle : sans filtre,
    // le compteur affiche 60 m parcourus sans avoir bougé.
    const s = suivi();
    s.ajouter(pt(0, 0));
    for (let i = 1; i <= 30; i++) s.ajouter(pt(i % 2 ? 2 : 0, i * 2));
    assert.equal(s.km(), 0);
    assert.ok(s.etat().rejets.immobile >= 20);
  });

  test('un recalage brutal est écarté', () => {
    // 300 m en 2 s, soit 540 km/h : c’est le GPS qui se reprend.
    const s = suivi();
    s.ajouter(pt(0, 0));
    const r = s.ajouter(pt(300, 2));
    assert.equal(r.raison, 'saut');
    assert.equal(s.km(), 0);
  });

  test('un rejet ne casse pas la suite du parcours', () => {
    const s = suivi();
    s.ajouter(pt(0, 0));
    s.ajouter(pt(50, 5, 80));     // écarté : imprécis
    s.ajouter(pt(100, 20));       // repris depuis le dernier point RETENU
    assert.equal(s.km(), 0.1);
  });

  // ── Ce qui est perdu doit se dire ─────────────────────────────

  test('une interruption est comptée', () => {
    const s = suivi();
    s.ajouter(pt(0, 0));
    s.ajouter(pt(200, 60));       // 60 s de silence
    assert.deepEqual(Array.from(s.etat().trous), [60]);
    assert.equal(s.etat().secondesPerdues, 60);
  });

  test('la ligne droite d’une interruption est quand même comptée', () => {
    // C’est un minimum : le vrai parcours ne peut pas être plus court.
    const s = suivi();
    s.ajouter(pt(0, 0));
    s.ajouter(pt(200, 60));
    assert.equal(s.km(), 0.2);
  });

  test('une interruption longue est annoncée à l’utilisateur', () => {
    const s = suivi();
    s.ajouter(pt(0, 0));
    s.ajouter(pt(200, 60));
    assert.match(s.avertissement(), /sous-estim/);
  });

  test('un parcours propre n’affiche aucun avertissement', () => {
    // Le silence vaut confiance : parler pour rien la dévalue.
    const s = suivi();
    for (let i = 0; i <= 10; i++) s.ajouter(pt(i * 50, i * 10));
    assert.equal(s.avertissement(), '');
  });

  test('des relevés simplement espacés n’alertent pas', () => {
    // Un téléphone en économie d'énergie donne une position toutes les 35 s.
    // Alerter sur la SOMME de ces silences allumerait l'avertissement pour
    // toute la course — et un avertissement permanent ne veut plus rien dire.
    const s = suivi();
    for (let i = 0; i <= 12; i++) s.ajouter(pt(i * 120, i * 35));
    assert.ok(s.etat().secondesPerdues > 300, 'les silences sont bien comptés');
    assert.equal(s.avertissement(), '', 'mais aucun n’est assez long pour alerter');
  });

  test('plusieurs silences moyens n’alertent pas, et c’est un choix', () => {
    // Trois trous de 50 s : la somme ne sait pas les distinguer d'un téléphone
    // simplement lent, alors qu'un seul trou de 60 s, si. On préfère se taire
    // que crier au mauvais moment — chaque trou de 50 s vaut ~150 m de
    // parcours inconnu, dont la ligne droite reste une bonne approximation.
    const s = suivi();
    let t = 0;
    for (let i = 0; i < 4; i++) { s.ajouter(pt(i * 400, t)); t += 50; }
    assert.equal(s.avertissement(), '');
    assert.ok(s.etat().secondesPerdues >= 150, 'les silences restent comptés');
  });

  test('un signal durablement imprécis le dit plutôt que d’afficher zéro', () => {
    const s = suivi();
    for (let i = 0; i < 15; i++) s.ajouter(pt(i * 30, i * 5, 90));
    assert.equal(s.km(), 0);
    assert.match(s.avertissement(), /imprécis/);
  });

  // ── Robustesse ────────────────────────────────────────────────

  test('une position absurde est ignorée sans tout casser', () => {
    const s = suivi();
    s.ajouter(pt(0, 0));
    assert.equal(s.ajouter({ lat: NaN, lon: 2, precision: 5, t: 1000 }).raison, 'invalide');
    assert.equal(s.ajouter({ lat: 48, lon: 2, precision: 5, t: NaN }).raison, 'invalide');
    s.ajouter(pt(100, 20));
    assert.equal(s.km(), 0.1);
  });

  test('un horodatage qui recule est ignoré', () => {
    const s = suivi();
    s.ajouter(pt(0, 10));
    assert.equal(s.ajouter(pt(100, 5)).raison, 'invalide');
    assert.equal(s.km(), 0);
  });

  test('réinitialiser remet tout à zéro', () => {
    const s = suivi();
    s.ajouter(pt(0, 0));
    s.ajouter(pt(200, 60));
    s.reinitialiser();
    assert.equal(s.km(), 0);
    assert.equal(s.avertissement(), '');
    assert.deepEqual(Array.from(s.etat().trous), []);
  });

  test('les seuils sont réglables, et les valeurs par défaut sont publiques', () => {
    const env = createEnv({ scripts: ['gps-track.js'] });
    assert.equal(env.window.GpsTrack.SEUILS.precisionMax, 25);
    const large = env.window.GpsTrack.creerSuivi({ precisionMax: 200 });
    large.ajouter(pt(0, 0));
    large.ajouter(pt(100, 20, 150));
    assert.equal(large.km(), 0.1);
  });
};
