/* Scan de code-barres — Nutrition.
 *
 * Utilise BarcodeDetector, l'API de décodage intégrée au navigateur
 * (Chrome/Android, donc l'app native et la PWA sur Android). Aucun
 * décodeur JavaScript n'est embarqué : une bibliothèque comme ZXing pèse
 * ~250 ko et ralentirait le chargement de tout le monde pour une
 * fonctionnalité utilisée par une minorité.
 *
 * Là où l'API n'existe pas (iOS, Firefox, desktop), la page propose la
 * saisie des chiffres sous le code-barres : plus lent, mais jamais bloqué.
 *
 * window.BarcodeScan :
 *   supported()            → true si le décodage automatique est possible
 *   start(video, onCode)   → ouvre la caméra ; onCode(code) au premier code lu
 *   stop()                 → coupe la caméra (à appeler systématiquement)
 */
(function () {
  'use strict';

  // EAN-13 et UPC couvrent les produits alimentaires européens et américains ;
  // EAN-8 les petits emballages. Les autres formats (QR, Code 128) ne sont pas
  // demandés : les détecter ralentirait l'analyse pour rien.
  var FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e'];
  var SCAN_INTERVAL_MS = 220;

  var detector = null;
  var stream = null;
  var timer = null;
  var videoEl = null;

  function supported() {
    return typeof window.BarcodeDetector === 'function' &&
      !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  }

  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
    if (stream) {
      stream.getTracks().forEach(function (t) { try { t.stop(); } catch (e) {} });
      stream = null;
    }
    if (videoEl) {
      try { videoEl.pause(); videoEl.srcObject = null; } catch (e) {}
      videoEl = null;
    }
  }

  /* Résout avec un message d'erreur lisible, ou null si la caméra démarre. */
  function start(video, onCode) {
    if (!supported()) return Promise.resolve('Ce navigateur ne sait pas lire les codes-barres.');
    stop();
    videoEl = video;

    if (!detector) {
      try {
        detector = new window.BarcodeDetector({ formats: FORMATS });
      } catch (e) {
        detector = null;
        return Promise.resolve('Les codes-barres ne sont pas lisibles ici.');
      }
    }

    // facingMode 'environment' = caméra arrière. Sur un téléphone sans caméra
    // arrière déclarée, la contrainte n'est pas stricte : on retombe sur celle
    // qui existe plutôt que d'échouer.
    return navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } }, audio: false
    }).then(function (s) {
      stream = s;
      video.srcObject = s;
      video.setAttribute('playsinline', '');
      video.muted = true;
      return video.play();
    }).then(function () {
      var busy = false;
      timer = setInterval(function () {
        if (busy || !videoEl || videoEl.readyState < 2) return;
        busy = true;
        detector.detect(videoEl).then(function (codes) {
          busy = false;
          if (!codes || !codes.length) return;
          var value = (codes[0].rawValue || '').replace(/[^0-9]/g, '');
          if (value.length < 8) return;
          stop();
          onCode(value);
        }).catch(function () { busy = false; });
      }, SCAN_INTERVAL_MS);
      return null;
    }).catch(function (err) {
      stop();
      var name = err && err.name;
      if (name === 'NotAllowedError' || name === 'SecurityError') {
        return 'Accès à la caméra refusé. Autorise-le dans les réglages, ou saisis les chiffres du code.';
      }
      if (name === 'NotFoundError' || name === 'OverconstrainedError') {
        return 'Aucune caméra disponible sur cet appareil.';
      }
      return 'La caméra n’a pas pu démarrer.';
    });
  }

  // Filet de sécurité : sans ça, quitter la page pendant un scan peut laisser
  // le voyant de la caméra allumé tant que la page reste en cache mémoire.
  window.addEventListener('pagehide', stop);

  window.BarcodeScan = { supported: supported, start: start, stop: stop };
})();
