/**
 * Bac à sable minimal pour tester les scripts de `static/js` sous Node,
 * sans jsdom, sans npm install.
 *
 * On ne simule que ce que le script touche vraiment : assez pour exercer la
 * logique (file d'attente, ordre d'envoi, reprise après échec), pas assez
 * pour prétendre être un navigateur. Tout ce qui relève du rendu est un
 * mannequin inerte.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

/** Élément DOM factice : accepte tout, ne rend rien. */
function makeElement(tag) {
  const el = {
    tagName: (tag || 'div').toUpperCase(),
    id: '',
    textContent: '',
    innerHTML: '',
    title: '',
    hidden: false,
    value: '',
    style: { cssText: '', setProperty() {} },
    children: [],
    attributes: {},
    setAttribute(k, v) { this.attributes[k] = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attributes, k) ? this.attributes[k] : null; },
    appendChild(c) { this.children.push(c); return c; },
    insertBefore(c) { this.children.push(c); return c; },
    remove() {},
    addEventListener() {},
    removeEventListener() {},
    // Un élément factice rend d'autres éléments factices : le code testé peut
    // chercher ses sous-parties sans qu'on décrive le gabarit.
    querySelector() { return makeElement('div'); },
    querySelectorAll() { return []; },
    getBoundingClientRect() { return { top: 0, left: 0, width: 0, height: 0 }; },
    focus() {},
    click() {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    dataset: {},
  };
  return el;
}

/**
 * Construit un environnement, y charge les scripts demandés et rend de quoi
 * piloter le test : horloge, réseau, stockage, événements.
 */
function createEnv(options) {
  const opts = options || {};
  const store = new Map();
  const listeners = { document: {}, window: {} };
  const captures = { document: {}, window: {} };   // phase déclarée par écouteur
  const timers = [];
  const intervals = [];
  const calls = [];              // requêtes fetch observées
  const nativeLog = [];          // appels au pont natif (MTTimer)

  const localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => { store.set(k, String(v)); },
    removeItem: (k) => { store.delete(k); },
    clear: () => store.clear(),
  };
  if (opts.corruptQueue) store.set('muscu_offline_queue', '{pas du json');

  // Verrou d'écran : on note les prises et les relâches plutôt que de simuler
  // l'API complète — c'est la séquence qui compte, pas l'objet.
  const wakeLog = [];
  const wakeLock = {
    request(type) {
      wakeLog.push('request:' + type);
      return Promise.resolve({
        type,
        release() { wakeLog.push('release'); return Promise.resolve(); },
        addEventListener() {},
      });
    },
  };

  const document = {
    readyState: 'complete',
    hidden: false,
    visibilityState: 'visible',
    title: '',
    body: makeElement('body'),
    createElement: makeElement,
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener(type, fn, capture) {
      (listeners.document[type] ||= []).push(fn);
      (captures.document[type] ||= []).push(capture === true || (capture && capture.capture === true));
    },
  };

  // Réponse de fetch pilotée par le test : par défaut, tout passe.
  let responder = () => ({ ok: true, status: 200, redirected: false, url: '/seance/save-exo' });

  const window = {
    location: { origin: 'https://app.test', pathname: '/seance' },
    addEventListener(type, fn, capture) {
      (listeners.window[type] ||= []).push(fn);
      (captures.window[type] ||= []).push(capture === true || (capture && capture.capture === true));
    },
    localStorage,
    document,
  };

  const navigator = { onLine: opts.online !== false };
  if (opts.wakeLock !== false) navigator.wakeLock = wakeLock;
  if (opts.nativeTimer) {
    window.MTTimer = { start(...a) { nativeLog.push(['start', ...a]); }, stop() { nativeLog.push(['stop']); } };
  }

  const sandbox = {
    window, document, navigator, localStorage,
    URL, URLSearchParams, FormData: FakeFormData, Promise, Date, Error, JSON, console,
    setTimeout: (fn) => { timers.push(fn); return timers.length; },
    clearTimeout() {},
    setInterval: (fn) => { intervals.push(fn); return intervals.length; },
    clearInterval() {},
    requestAnimationFrame: (fn) => { timers.push(fn); return timers.length; },
    fetch(url, init) {
      calls.push({ url, body: init && init.body ? String(init.body) : '' });
      const r = responder(url, init, calls.length - 1);
      return r instanceof Promise ? r : Promise.resolve(r);
    },
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);

  for (const name of opts.scripts || []) {
    const file = path.join(__dirname, '..', '..', 'static', 'js', name);
    vm.runInContext(fs.readFileSync(file, 'utf8'), sandbox, { filename: name });
  }

  return {
    window, document, navigator, localStorage, calls, sandbox,
    /** Décide de la réponse HTTP suivante. */
    setResponder(fn) { responder = fn; },
    /** Vide les minuteries en attente (toasts, rAF). */
    flushTimers() { while (timers.length) timers.shift()(); },
    /** Déclenche un événement DOM/window enregistré par le script. */
    emit(target, type, event) {
      for (const fn of (listeners[target][type] || [])) fn(event);
    },
    /** Phases déclarées pour un type d'événement (true = capture). */
    phases(target, type) { return (captures[target][type] || []).slice(); },
    /** Historique des prises/relâches du verrou d'écran. */
    wakeLog,
    /** Historique des appels au pont natif du chrono. */
    nativeLog,
    /** Laisse tourner les promesses en attente. */
    settle() { return new Promise((r) => setImmediate(r)); },
    queue() {
      try { return JSON.parse(localStorage.getItem('muscu_offline_queue') || '[]'); }
      catch (e) { return null; }
    },
  };
}

/**
 * FormData minimal : `new FormData(form)` lit les champs du faux formulaire,
 * et `enqueue` n'utilise que `forEach(valeur, clé)`.
 */
class FakeFormData {
  constructor(form) { this._entries = (form && form._fields) || []; }
  forEach(cb) { for (const [k, v] of this._entries) cb(v, k); }
}

/** Formulaire factice, tel que le voit l'écouteur `submit`. */
function makeForm(action, fields) {
  let prevented = false;
  const data = Object.entries(fields || {});
  return {
    action,
    method: 'post',
    get defaultPrevented() { return prevented; },
    preventDefault() { prevented = true; },
    getAttribute(k) { return k === 'action' ? action : null; },
    _fields: data,
  };
}

function makeFormData(fields) {
  return new FakeFormData({ _fields: Object.entries(fields || {}) });
}

/** Événement `submit` tel que le navigateur le passe aux écouteurs. */
function submitEvent(form) {
  return {
    target: form,
    get defaultPrevented() { return form.defaultPrevented; },
    preventDefault() { form.preventDefault(); },
  };
}

module.exports = { createEnv, makeForm, makeFormData, makeElement, submitEvent, FakeFormData };
