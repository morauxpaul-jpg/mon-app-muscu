/**
 * Messages d'échec de la connexion Google native (templates/login.html).
 *
 * Le plugin renvoie le message brut de Credential Manager : « Google Sign-In
 * failed: 16 ». Personne ne sait quoi en faire — et les causes se corrigent à
 * des endroits différents : le téléphone, la console Google, ou Supabase.
 * Ce test vérifie que chacune tombe dans la bonne explication.
 *
 * La fonction est lue dans le gabarit puis évaluée : elle est pure, donc pas
 * besoin de charger la page ni Supabase.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const TEMPLATE = path.join(__dirname, '..', '..', 'templates', 'login.html');

function chargerExpliquer() {
  const src = fs.readFileSync(TEMPLATE, 'utf8');
  const m = src.match(/function expliquer\(brut\) \{[\s\S]*?\n {4}\}/);
  if (!m) throw new Error("fonction `expliquer` introuvable dans login.html");
  return new Function('return ' + m[0])();
}

module.exports = ({ test, assert }) => {
  const expliquer = chargerExpliquer();

  const CAS = [
    ['Google Sign-In failed: No credentials available', 'compte Google',
      'aucun compte sur le téléphone'],
    ['Google Sign-In failed: 10: ', 'console Google Cloud',
      'app non déclarée (SHA-1 / package)'],
    ['Google Sign-In failed: 16: Cannot find a matching credential', 'console Google Cloud',
      'même cause, autre code'],
    ['activity is cancelled by the user', 'annulée',
      "l'utilisateur a fermé la fenêtre"],
    ['Unacceptable audience in id_token', 'Authorized Client IDs',
      'côté Supabase, pas côté Google'],
    ['Google Sign-In dependencies are not available', 'Réinstalle',
      'build incomplet'],
    ['network error while fetching', 'réseau',
      'connexion absente'],
  ];

  for (const [brut, attendu, pourquoi] of CAS) {
    test('« ' + brut.slice(0, 46) + ' » → ' + pourquoi, () => {
      const clair = expliquer(brut);
      assert.ok(clair.includes(attendu),
        'attendu une mention de « ' + attendu + ' », reçu : ' + clair);
      assert.notEqual(clair, brut, 'le message brut ne doit pas être renvoyé tel quel');
    });
  }

  test('un message inconnu est rendu tel quel plutôt que masqué', () => {
    // Inventer une explication pour un cas non prévu induirait en erreur ;
    // le texte d'origine reste ce qui permet de chercher.
    const brut = 'UnknownProviderException: quelque chose de nouveau';
    assert.equal(expliquer(brut), brut);
  });

  test('une erreur vide ne laisse pas la page muette', () => {
    assert.ok(expliquer('').length > 0);
    assert.ok(expliquer(null).length > 0);
    assert.ok(expliquer(undefined).length > 0);
  });
};
