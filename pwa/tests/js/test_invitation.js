/**
 * Lien d'invitation (static/js/invitation.js), commun aux pages Parrainage
 * et Amis : le lien suit le domaine de la page, « Partager » passe par Web
 * Share (WhatsApp sur téléphone), et retombe sur la copie sans lui.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', '..', 'static', 'js', 'invitation.js'), 'utf8');

function bloc(attrs) {
  const parties = {};
  const el = {
    getAttribute: (k) => (k in attrs ? attrs[k] : null),
    querySelector: (sel) => parties[sel] || (parties[sel] = {
      value: '', ecouteurs: {}, select() {},
      addEventListener(type, fn) { this.ecouteurs[type] = fn; },
    }),
  };
  return { el, parties };
}

function charger(options) {
  const o = options || {};
  const envois = [];
  const toasts = [];
  const partages = [];
  const copies = [];
  const ctx = {
    location: { origin: 'https://muscu.example' },
    navigator: {
      clipboard: { writeText: (t) => { copies.push(t); return Promise.resolve(); } },
      share: o.share ? (d) => { partages.push(d); return o.share(d); } : undefined,
    },
    document: {
      body: { appendChild: (t) => toasts.push(t.textContent) },
      createElement: () => ({ style: {}, remove() {} }),
      execCommand() {},
      querySelectorAll: () => [],
    },
    fetch: (url, init) => { envois.push({ url, corps: JSON.parse(init.body) }); return Promise.resolve({}); },
    setTimeout: () => 0,
    Promise,
    JSON,
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx);
  return { ctx, envois, toasts, partages, copies };
}

const AMI = { 'data-chemin': '/?ref=abcd2345&ami=1', 'data-texte': 'Ajoute-moi', 'data-suivi': 'ami' };

module.exports = ({ test, assert }) => {
  test('invitation.js : le lien suit le domaine de la page', () => {
    const { ctx } = charger();
    const { el, parties } = bloc(AMI);
    const inv = ctx.Invitation.brancher(el, ctx);
    assert.equal(inv.lien, 'https://muscu.example/?ref=abcd2345&ami=1');
    assert.equal(parties['.inv-lien'].value, inv.lien);
  });

  test('invitation.js : Partager passe par Web Share avec le texte', async () => {
    const env = charger({ share: () => Promise.resolve() });
    const { el } = bloc(AMI);
    await env.ctx.Invitation.brancher(el, env.ctx).partager();
    assert.equal(env.partages.length, 1);
    assert.equal(env.partages[0].url, 'https://muscu.example/?ref=abcd2345&ami=1');
    assert.equal(env.partages[0].text, 'Ajoute-moi');
    assert.deepEqual(env.envois.map((e) => e.corps.method), ['ami_share']);
    assert.deepEqual(env.copies, []);
  });

  test('invitation.js : sans Web Share, le lien est copié', async () => {
    const env = charger();
    const { el, parties } = bloc(AMI);
    env.ctx.Invitation.brancher(el, env.ctx);
    await parties['.inv-partager'].ecouteurs.click();
    assert.deepEqual(env.copies, ['https://muscu.example/?ref=abcd2345&ami=1']);
    assert.deepEqual(env.toasts, ['Lien copié']);
    assert.deepEqual(env.envois.map((e) => e.corps.method), ['ami_copy']);
  });

  test('invitation.js : partage annulé, rien n\'est copié', async () => {
    const env = charger({ share: () => Promise.reject({ name: 'AbortError' }) });
    const { el } = bloc(AMI);
    await env.ctx.Invitation.brancher(el, env.ctx).partager();
    assert.deepEqual(env.copies, []);
    assert.deepEqual(env.envois, []);
  });

  test('invitation.js : la page Parrainage garde sa mesure d\'avant', async () => {
    const env = charger();
    const { el } = bloc({ 'data-chemin': '/?ref=abcd2345', 'data-texte': 'Rejoins-moi' });
    await env.ctx.Invitation.brancher(el, env.ctx).copier();
    assert.deepEqual(env.envois.map((e) => e.corps.method), ['copy']);
    assert.deepEqual(env.copies, ['https://muscu.example/?ref=abcd2345']);
  });
};
