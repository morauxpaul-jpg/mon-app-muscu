// Partage de progression — génère une carte (canvas → PNG) et la partage via
// l'API Web Share (image si supportée, sinon texte+lien, sinon téléchargement +
// copie du lien). Aucune dépendance. API publique : window.shareProgress().
(function () {
  'use strict';

  var ACCENT = '#78c8ff';
  var GOLD = '#FFD700';
  var TEXT = '#ffffff';
  var DIM = '#8b93a1';

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  var FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif';

  function tile(ctx, x, y, w, h, label, value, color) {
    ctx.fillStyle = 'rgba(255,255,255,0.05)';
    roundRect(ctx, x, y, w, h, 24); ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.08)'; ctx.lineWidth = 1.5;
    roundRect(ctx, x, y, w, h, 24); ctx.stroke();

    ctx.textAlign = 'center';
    ctx.fillStyle = DIM;
    ctx.font = '600 26px ' + FONT;
    ctx.fillText(label, x + w / 2, y + 56);
    ctx.fillStyle = color || TEXT;
    ctx.font = '800 64px ' + FONT;
    ctx.fillText(value, x + w / 2, y + h - 44);
  }

  function buildCard(d) {
    var S = 1080;
    var c = document.createElement('canvas');
    c.width = S; c.height = S;
    var ctx = c.getContext('2d');

    // Fond dégradé sombre + halo accent en haut.
    var g = ctx.createLinearGradient(0, 0, 0, S);
    g.addColorStop(0, '#14181f'); g.addColorStop(1, '#0c0e12');
    ctx.fillStyle = g; ctx.fillRect(0, 0, S, S);
    var glow = ctx.createRadialGradient(S / 2, 120, 40, S / 2, 120, 620);
    glow.addColorStop(0, 'rgba(120,200,255,0.16)');
    glow.addColorStop(1, 'rgba(120,200,255,0)');
    ctx.fillStyle = glow; ctx.fillRect(0, 0, S, S);

    var P = 90;

    // En-tête : marque
    ctx.textAlign = 'left';
    ctx.fillStyle = ACCENT;
    ctx.font = '800 34px ' + FONT;
    ctx.fillText('MUSCU TRACKER', P, 110);
    ctx.textAlign = 'right';
    ctx.fillStyle = DIM;
    ctx.font = '600 30px ' + FONT;
    ctx.fillText('Semaine ' + d.week, S - P, 110);

    // Sous-titre prénom
    if (d.prenom) {
      ctx.textAlign = 'left';
      ctx.fillStyle = TEXT;
      ctx.font = '600 40px ' + FONT;
      ctx.fillText('La semaine de ' + d.prenom, P, 200);
    }

    // Héros : streak (ou volume si pas de streak)
    ctx.textAlign = 'center';
    if (d.streak >= 1) {
      ctx.font = '800 220px ' + FONT;
      ctx.fillStyle = GOLD;
      ctx.fillText('🔥 ' + d.streak, S / 2, 520);
      ctx.fillStyle = TEXT;
      ctx.font = '700 46px ' + FONT;
      ctx.fillText(d.streak > 1 ? 'semaines d’affilée' : 'semaine d’affilée', S / 2, 600);
    } else {
      ctx.font = '800 150px ' + FONT;
      ctx.fillStyle = ACCENT;
      ctx.fillText(d.tonnage, S / 2, 480);
      ctx.fillStyle = TEXT;
      ctx.font = '700 46px ' + FONT;
      ctx.fillText('kg soulevés cette semaine', S / 2, 560);
    }

    // Tuiles stats
    var ty = 660, th = 200, gap = 30;
    var tw = (S - 2 * P - 2 * gap) / 3;
    tile(ctx, P, ty, tw, th, 'SÉANCES', d.sessions + '/' + d.total, ACCENT);
    tile(ctx, P + tw + gap, ty, tw, th, 'VOLUME', d.tonnage, '#34c759');
    tile(ctx, P + 2 * (tw + gap), ty, tw, th, 'EXOS', String(d.exos), GOLD);

    // Pied : tagline + lien
    ctx.textAlign = 'center';
    ctx.fillStyle = TEXT;
    ctx.font = '700 38px ' + FONT;
    ctx.fillText('Suis ta muscu. Progresse.', S / 2, 960);
    ctx.fillStyle = DIM;
    ctx.font = '600 30px ' + FONT;
    ctx.fillText(d.host, S / 2, 1010);

    return new Promise(function (resolve) {
      c.toBlob(function (b) { resolve(b); }, 'image/png', 0.92);
    });
  }

  function toast(msg) {
    var t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;left:50%;bottom:96px;transform:translateX(-50%);' +
      'background:#1b1f27;color:#fff;border:1px solid rgba(255,255,255,0.12);' +
      'padding:12px 18px;border-radius:12px;font-size:14px;z-index:99999;' +
      'box-shadow:0 8px 32px rgba(0,0,0,0.5);max-width:88vw;text-align:center;';
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
    try { blob = await buildCard(d); } catch (e) { blob = null; }

    var summary = 'Ma semaine sur Muscu Tracker 💪 ' + d.sessions + '/' + d.total +
      ' séances, ' + d.tonnage + ' kg soulevés' + (d.streak > 1 ? ', streak ' + d.streak + ' 🔥' : '') + '.';

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
        toast(blob ? 'Image téléchargée · lien copié 📋' : 'Lien copié 📋');
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
})();
