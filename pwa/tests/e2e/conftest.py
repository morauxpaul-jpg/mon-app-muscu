"""Décor des tests navigateur : le serveur de démonstration (fausse base)
sur un port libre, et Chromium. Sans Playwright ni Chromium, tout s'ignore."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PWA = Path(__file__).resolve().parents[2]


def _port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def serveur():
    port = _port_libre()
    # ADMIN_EMAILS : /admin s'ouvre avec /test-login?admin=1 (connexion Google simulée).
    env = dict(os.environ, PORT=str(port), FLASK_SECRET_KEY="e2e", PYTHONUTF8="1", FAUX_IA="lent",
               SANS_LIMITE="1", ADMIN_EMAILS="test@example.com")
    proc = subprocess.Popen([sys.executable, "run_local_fake.py"], cwd=PWA, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/test-historique", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("le serveur de test n'a pas démarré")
    yield base
    proc.kill()


@pytest.fixture(scope="module")
def navigateur():
    with sync_api.sync_playwright() as p:
        try:
            # À l'heure de Paris, comme le téléphone d'un utilisateur et comme
            # le serveur. Le jour de la séance vient du téléphone
            # (jour-seance.js) : un Chromium à l'heure UTC, celle de la CI,
            # n'était pas d'accord avec le serveur entre 4 h et 6 h à Paris,
            # et la page de demain s'ouvrait en « RATTRAPAGE » (main rouge le
            # 18/10 à 04:02, déploiement sauté).
            b = p.chromium.launch(env={**os.environ, "TZ": "Europe/Paris"})
        except Exception as e:  # navigateur non installé
            pytest.skip(f"Chromium indisponible : {e}")
        yield b
        b.close()
