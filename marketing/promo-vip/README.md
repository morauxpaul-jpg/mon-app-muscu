# Vidéo promo PRO

Source de `pwa/static/promo-vip-motion.mp4` (720 × 1280, 37 s, muette),
lue en boucle sur la page PRO, et de son image d'aperçu
`promo-vip-motion-poster.jpg`.

- `index.html` : les 10 plans, en HTML et CSS, au style « Instrument » de l'app.
- `scene.js` : le minutage de chaque plan, et l'haltère 3D (Three.js), même
  géométrie que l'icône (`pwa/tools/dessiner_icone.py`).
- `rendre.py` : photographie la page 30 fois par seconde dans Chromium,
  puis assemble les images en MP4 avec ffmpeg. Le rendu ne dépend d'aucune
  horloge : deux rendus donnent la même vidéo.

La carte musculaire vient de l'app (`pwa/core/body_map.py`), les noms de
programmes du vrai catalogue PRO. Pas de prix dans la vidéo : ils sont
affichés juste en dessous, sur la page.

```
cd marketing/promo-vip
npm ci                                  # Three.js, une fois
python rendre.py --images 3.5,9,23.2    # quelques images fixes dans planche/
python rendre.py                        # vidéo + aperçu dans pwa/static/
```

Prérequis : Playwright (`requirements-dev.txt`) et ffmpeg.
