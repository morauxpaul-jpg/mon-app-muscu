// Micro-animations + haptic feedback (Muscu PRO, v22).
// Haptic sur [data-haptic], flash succès .row-flash, confetti fin séance.
(function () {
  'use strict';

  function vibrate(ms) {
    if (navigator.vibrate) { try { navigator.vibrate(ms); } catch (e) {} }
  }

  // Haptic 10ms sur click de tout élément [data-haptic="1"]
  document.addEventListener('click', function (e) {
    var el = e.target.closest('[data-haptic]');
    if (el) vibrate(10);
  }, { passive: true });

  // API publique : flash d'une ligne (.row-flash se re-déclenche)
  window.flashRow = function (el) {
    if (!el) return;
    el.classList.remove('row-flash');
    void el.offsetWidth;
    el.classList.add('row-flash');
    vibrate(15);
    setTimeout(function () { el.classList.remove('row-flash'); }, 320);
  };

  // API publique : confetti CSS-only (fin séance)
  window.fireConfetti = function (count) {
    count = count || 60;
    var colors = ['#58CCFF', '#00FF7F', '#FFD700', '#FF9F0A', '#FF453A'];
    var wrap = document.createElement('div');
    wrap.className = 'confetti-wrap';
    for (var i = 0; i < count; i++) {
      var p = document.createElement('div');
      p.className = 'confetti-piece';
      p.style.left = Math.random() * 100 + 'vw';
      p.style.background = colors[i % colors.length];
      p.style.setProperty('--dx', (Math.random() * 200 - 100) + 'px');
      p.style.animationDelay = (Math.random() * 0.3) + 's';
      p.style.animationDuration = (1.8 + Math.random() * 1.2) + 's';
      wrap.appendChild(p);
    }
    document.body.appendChild(wrap);
    vibrate([20, 40, 20]);
    setTimeout(function () { wrap.remove(); }, 3200);
  };
})();
