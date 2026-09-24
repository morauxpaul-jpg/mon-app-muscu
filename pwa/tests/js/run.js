/**
 * Lanceur de tests JavaScript — sans dépendance, sans npm install.
 *
 * Les scripts de `static/js` portent de la logique que pytest ne voit pas :
 * la file hors-ligne notamment, seul endroit où des données utilisateur
 * vivent en dehors de la base. Node suffit pour les exercer.
 *
 *   cd pwa && node tests/js/run.js
 *
 * Intégré à la suite Python par tests/test_js.py (ignoré si Node manque).
 */
'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert').strict;

const files = fs.readdirSync(__dirname)
  .filter((f) => f.startsWith('test_') && f.endsWith('.js'))
  .sort();

const cases = [];
const register = (nom, fn) => cases.push({ nom, fn });

for (const f of files) {
  require(path.join(__dirname, f))({ test: register, assert });
}

(async () => {
  let echecs = 0;
  for (const c of cases) {
    try {
      await c.fn();
      process.stdout.write('.');
    } catch (e) {
      echecs++;
      process.stdout.write('\nÉCHEC : ' + c.nom + '\n  ' + (e && e.message || e) + '\n');
    }
  }
  const total = cases.length;
  process.stdout.write('\n' + (echecs
    ? `${echecs} échec(s) sur ${total}\n`
    : `${total} tests JS passés\n`));
  process.exit(echecs ? 1 : 0);
})();
