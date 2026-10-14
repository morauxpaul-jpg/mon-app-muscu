// Partage de progression — génère une carte (canvas → PNG) et la partage via
// l'API Web Share (image si supportée, sinon texte+lien, sinon téléchargement +
// copie du lien). Aucune dépendance. API publique : window.shareProgress().
(function () {
  'use strict';

  // Style « Instrument » (13/10) : fond noir, blocs #111, une seule couleur
  // vive, chiffres en Barlow Condensed. Plus de dégradé, de halo, d'or ni
  // d'emoji.
  var ACCENT = '#c8f031';
  var TEXT = '#f2f2f2';
  var DIM = '#9a9a9a';

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  var FONT = '"Barlow", -apple-system, "Segoe UI", Roboto, system-ui, sans-serif';
  var ETROIT = '"Barlow Condensed", "Barlow", -apple-system, "Segoe UI", Roboto, sans-serif';

  function tile(ctx, x, y, w, h, label, value, color) {
    ctx.fillStyle = '#111111';
    roundRect(ctx, x, y, w, h, 10); ctx.fill();

    ctx.textAlign = 'left';
    ctx.fillStyle = DIM;
    ctx.font = '600 30px ' + ETROIT;
    ctx.fillText(label, x + 32, y + 60);
    ctx.fillStyle = color || TEXT;
    ctx.font = '700 84px ' + ETROIT;
    ctx.fillText(value, x + 32, y + h - 40);
  }

  function buildCard(d) {
    var S = 1080;
    var c = document.createElement('canvas');
    c.width = S; c.height = S;
    var ctx = c.getContext('2d');

    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, S, S);

    var P = 90;

    // En-tête : marque
    ctx.textAlign = 'left';
    ctx.fillStyle = TEXT;
    ctx.font = '700 40px ' + ETROIT;
    ctx.fillText('MUSCU TRACKER', P, 110);
    ctx.textAlign = 'right';
    ctx.fillStyle = DIM;
    ctx.font = '600 36px ' + ETROIT;
    ctx.fillText('SEMAINE ' + d.week, S - P, 110);

    // Sous-titre prénom
    if (d.prenom) {
      ctx.textAlign = 'left';
      ctx.fillStyle = TEXT;
      ctx.font = '500 40px ' + FONT;
      ctx.fillText('La semaine de ' + d.prenom, P, 200);
    }

    // Héros : semaines d'affilée (ou volume sans série en cours), en très
    // grand, aligné à gauche comme les écrans de l'app.
    ctx.textAlign = 'left';
    if (d.streak >= 1) {
      ctx.font = '700 300px ' + ETROIT;
      ctx.fillStyle = ACCENT;
      ctx.fillText(String(d.streak), P - 8, 530);
      ctx.fillStyle = TEXT;
      ctx.font = '700 56px ' + ETROIT;
      ctx.fillText(d.streak > 1 ? 'SEMAINES D’AFFILÉE' : 'SEMAINE D’AFFILÉE', P, 600);
    } else {
      ctx.font = '700 220px ' + ETROIT;
      ctx.fillStyle = ACCENT;
      ctx.fillText(d.tonnage, P - 6, 500);
      ctx.fillStyle = TEXT;
      ctx.font = '700 56px ' + ETROIT;
      ctx.fillText('KG SOULEVÉS CETTE SEMAINE', P, 580);
    }

    // Tuiles stats
    var ty = 660, th = 200, gap = 12;
    var tw = (S - 2 * P - 2 * gap) / 3;
    tile(ctx, P, ty, tw, th, 'SÉANCES', d.sessions + '/' + d.total, TEXT);
    tile(ctx, P + tw + gap, ty, tw, th, 'VOLUME', d.tonnage, TEXT);
    tile(ctx, P + 2 * (tw + gap), ty, tw, th, 'EXOS', String(d.exos), TEXT);

    // Pied : tagline + lien
    ctx.textAlign = 'left';
    ctx.fillStyle = TEXT;
    ctx.font = '700 44px ' + ETROIT;
    ctx.fillText('SUIS TA MUSCU. PROGRESSE.', P, 960);
    ctx.fillStyle = DIM;
    ctx.font = '500 30px ' + FONT;
    ctx.fillText(d.host, P, 1010);

    return new Promise(function (resolve) {
      c.toBlob(function (b) { resolve(b); }, 'image/png', 0.92);
    });
  }

  function toast(msg) {
    var t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;left:50%;bottom:96px;transform:translateX(-50%);' +
      'background:#111111;color:#f2f2f2;border:1px solid #262626;' +
      'padding:12px 18px;border-radius:4px;font-size:14px;z-index:99999;' +
      'max-width:88vw;text-align:center;';
    document.body.appendChild(t);
    setTimeout(function () { t.style.transition = 'opacity .4s'; t.style.opacity = '0'; }, 2400);
    setTimeout(function () { t.remove(); }, 2900);
  }

  function trackShare(method) {
    try {
      fetch('/share/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: 'progress', method: method }),
        keepalive: true,
      }).catch(function () {});
    } catch (e) {}
  }

  function download(blob, name) {
    var u = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = u; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(u); }, 2000);
  }

  window.shareProgress = async function (btn) {
    var el = document.getElementById('share-data');
    if (!el) return;
    var d;
    try { d = JSON.parse(el.textContent); } catch (e) { return; }
    d.host = location.host;
    var url = location.origin;

    if (btn) btn.disabled = true;

    var blob;
    try {
      if (document.fonts && document.fonts.load) {
        await Promise.all([document.fonts.load('700 100px "Barlow Condensed"'),
                           document.fonts.load('500 40px "Barlow"')]);
      }
    } catch (e) {}
    try { blob = await buildCard(d); } catch (e) { blob = null; }

    var summary = 'Ma semaine sur Muscu Tracker : ' + d.sessions + '/' + d.total +
      ' séances, ' + d.tonnage + ' kg soulevés' + (d.streak > 1 ? ', ' + d.streak + ' semaines d’affilée' : '') + '.';

    var file = blob ? new File([blob], 'ma-progression.png', { type: 'image/png' }) : null;

    try {
      // 1) Partage avec image (mobile moderne)
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], text: summary + ' ' + url, title: 'Ma progression' });
        trackShare('share');
      // 2) Partage texte + lien
      } else if (navigator.share) {
        await navigator.share({ title: 'Muscu Tracker', text: summary, url: url });
        trackShare('share');
      // 3) Fallback : téléchargement image + copie du lien
      } else {
        if (blob) download(blob, 'ma-progression.png');
        try { await navigator.clipboard.writeText(url); } catch (e) {}
        toast(blob ? 'Image téléchargée · lien copié' : 'Lien copié');
        trackShare('download');
      }
    } catch (e) {
      // AbortError = l'utilisateur a annulé la feuille de partage : silencieux.
      if (e && e.name !== 'AbortError') {
        if (blob) download(blob, 'ma-progression.png');
        toast('Image téléchargée');
        trackShare('download');
      }
    } finally {
      if (btn) btn.disabled = false;
    }
  };

  // Le bouton de l'accueil (data-partage-progres) : branché ici, la CSP
  // refuse les onclick écrits dans le HTML. Script en `defer` : la page est lue.
  document.querySelectorAll('[data-partage-progres]').forEach(function (btn) {
    btn.addEventListener('click', function () { window.shareProgress(btn); });
  });
})();
