// Push web — abonnement aux notifications (relance des inactifs).
// API publique : window.enablePush(btn) (demande permission + abonne).
// Au chargement : ré-abonne silencieusement si la permission est déjà accordée.
(function () {
  'use strict';

  function supported() {
    return ('serviceWorker' in navigator) && ('PushManager' in window) && ('Notification' in window);
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = atob(base64);
    var arr = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    return arr;
  }

  function csrfHeaders() {
    var m = document.querySelector('meta[name="csrf-token"]');
    var h = { 'Content-Type': 'application/json' };
    if (m && m.content) h['X-CSRFToken'] = m.content;
    return h;
  }

  function toast(msg) {
    var t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;left:50%;bottom:96px;transform:translateX(-50%);background:#1b1f27;color:#fff;border:1px solid rgba(255,255,255,0.12);padding:12px 18px;border-radius:12px;font-size:14px;z-index:99999;box-shadow:0 8px 32px rgba(0,0,0,0.5);max-width:88vw;text-align:center;';
    document.body.appendChild(t);
    setTimeout(function () { t.style.transition = 'opacity .4s'; t.style.opacity = '0'; }, 2400);
    setTimeout(function () { t.remove(); }, 2900);
  }

  async function getConfig() {
    try {
      var r = await fetch('/push/config', { credentials: 'same-origin' });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  }

  async function subscribeInternal(reg, publicKey) {
    var sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });
    }
    await fetch('/push/subscribe', {
      method: 'POST', headers: csrfHeaders(),
      body: JSON.stringify(sub), credentials: 'same-origin',
    });
    return sub;
  }

  // Garde l'abonnement frais côté serveur si la permission est déjà accordée.
  async function ensureSubscribed() {
    if (!supported() || Notification.permission !== 'granted') return;
    var cfg = await getConfig();
    if (!cfg || !cfg.enabled || !cfg.public_key) return;
    try {
      var reg = await navigator.serviceWorker.ready;
      await subscribeInternal(reg, cfg.public_key);
    } catch (e) {}
  }

  window.enablePush = async function (btn) {
    if (!supported()) { toast('Notifications non supportées sur cet appareil.'); return false; }
    if (btn) btn.disabled = true;
    try {
      var cfg = await getConfig();
      if (!cfg || !cfg.enabled || !cfg.public_key) { toast('Notifications indisponibles pour le moment.'); return false; }
      var perm = Notification.permission;
      if (perm === 'default') perm = await Notification.requestPermission();
      if (perm === 'denied') { toast('Notifications bloquées — autorise-les dans ton navigateur.'); return false; }
      if (perm !== 'granted') return false;
      var reg = await navigator.serviceWorker.ready;
      await subscribeInternal(reg, cfg.public_key);
      toast('Notifications activées ✅');
      document.querySelectorAll('[data-push-enable]').forEach(function (el) {
        el.textContent = 'Notifications activées ✓';
        el.disabled = true;
      });
      return true;
    } catch (e) {
      toast('Activation échouée.');
      return false;
    } finally {
      if (btn) btn.disabled = false;
    }
  };

  // Reflète l'état + ré-abonne au chargement.
  function init() {
    if (supported() && Notification.permission === 'granted') {
      document.querySelectorAll('[data-push-enable]').forEach(function (el) {
        el.textContent = 'Notifications activées ✓';
        el.disabled = true;
      });
      ensureSubscribed();
    }
  }
  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);
})();
