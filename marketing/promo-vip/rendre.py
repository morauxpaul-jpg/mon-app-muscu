# -*- coding: utf-8 -*-
"""Fabrique la vidéo promo PRO à partir de l'animation (index.html + scene.js).

La page calcule chaque image à partir du temps (window.seek). Ce script la
photographie 30 fois par seconde dans Chromium, puis ffmpeg assemble les
images en MP4. Aucune horloge : deux rendus donnent la même vidéo.

    cd marketing/promo-vip && npm ci          # Three.js, une fois
    python rendre.py                          # vidéo + image d'aperçu dans pwa/static/
    python rendre.py --images 1.2,3.6,6.5     # quelques images fixes (planche)

Prérequis : Playwright (requirements-dev.txt) et ffmpeg. Le Chromium de
Playwright convient ; CHROMIUM=/chemin/vers/chrome en force un autre.
"""
import argparse
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.abspath(os.path.join(ICI, "..", ".."))
STATIC = os.path.join(RACINE, "pwa", "static")
FPS = 30
APERCU_T = 36.6   # l'image d'aperçu : l'appel à l'action, haltère posé


def ecrire_corps():
    """Les polygones de la carte musculaire, pris dans l'app elle-même."""
    sys.path.insert(0, os.path.join(RACINE, "pwa"))
    from core.body_map import get_body_polygons
    with open(os.path.join(ICI, "body.json"), "w", encoding="utf-8") as f:
        json.dump(get_body_polygons(), f, ensure_ascii=False)


class _Muet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serveur():
    gestion = functools.partial(_Muet, directory=RACINE)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), gestion)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/marketing/promo-vip/index.html"


def ouvrir(p):
    options = {}
    chrome = os.environ.get("CHROMIUM") or ("/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
    if chrome:
        options["executable_path"] = chrome
    nav = p.chromium.launch(**options)
    page = nav.new_page(viewport={"width": 720, "height": 1280}, device_scale_factor=1)
    erreurs = []
    page.on("pageerror", lambda e: erreurs.append(str(e)))
    return nav, page, erreurs


def rendre(images=None, sortie=None, apercu=None, fps=FPS):
    from playwright.sync_api import sync_playwright
    ecrire_corps()
    srv, url = serveur()
    try:
        with sync_playwright() as p:
            nav, page, erreurs = ouvrir(p)
            page.goto(url, wait_until="networkidle")
            page.evaluate("window.pret")
            if erreurs:
                raise SystemExit("erreur dans l'animation : " + erreurs[0])
            duree = page.evaluate("window.DUREE")
            if images:
                os.makedirs(sortie, exist_ok=True)
                for t in images:
                    page.evaluate(f"window.seek({t})")
                    chemin = os.path.join(sortie, f"t{t:05.2f}.png")
                    page.screenshot(path=chemin)
                    print(chemin)
                return
            dossier = tempfile.mkdtemp(prefix="promo-")
            n = int(round(duree * fps))
            for i in range(n):
                page.evaluate(f"window.seek({i / fps})")
                page.screenshot(path=os.path.join(dossier, f"{i:05d}.png"))
                if i % fps == 0:
                    print(f"  {i // fps:2d} s / {duree:.1f} s", flush=True)
            page.evaluate(f"window.seek({APERCU_T})")
            page.screenshot(path=apercu, type="jpeg", quality=82)
            if erreurs:
                raise SystemExit("erreur dans l'animation : " + erreurs[0])
            nav.close()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps),
                        "-i", os.path.join(dossier, "%05d.png"),
                        "-c:v", "libx264", "-preset", "slow", "-crf", "24",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", sortie],
                       check=True)
        shutil.rmtree(dossier, ignore_errors=True)
        print(f"{sortie} : {os.path.getsize(sortie) // 1024} ko, {n} images")
        print(f"{apercu} : {os.path.getsize(apercu) // 1024} ko")
    finally:
        srv.shutdown()


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--images", help="instants à photographier, en secondes, séparés par des virgules")
    a.add_argument("--dossier", default=os.path.join(ICI, "planche"), help="où ranger les images fixes")
    a.add_argument("--sortie", default=os.path.join(STATIC, "promo-vip-motion.mp4"))
    a.add_argument("--apercu", default=os.path.join(STATIC, "promo-vip-motion-poster.jpg"))
    a.add_argument("--fps", type=int, default=FPS)
    o = a.parse_args()
    if o.images:
        rendre(images=[float(x) for x in o.images.split(",")], sortie=o.dossier)
    else:
        rendre(sortie=o.sortie, apercu=o.apercu, fps=o.fps)
