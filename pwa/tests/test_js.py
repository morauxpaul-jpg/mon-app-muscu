"""Branche les tests JavaScript sur la suite Python.

`static/js` porte de la logique que pytest ne voit pas — au premier rang la
file d'attente hors-ligne, seul endroit où des données utilisateur vivent en
dehors de la base. Le lanceur (`tests/js/run.js`) tourne sous Node nu, sans
npm install ni jsdom : une seule commande couvre donc les deux langages.

    cd pwa && python -m pytest tests -q
    cd pwa && node tests/js/run.js      # pour le détail des cas
"""
import shutil
import subprocess
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parent / "js" / "run.js"


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="Node absent — les tests JS sont ignorés")
def test_les_tests_javascript_passent():
    proc = subprocess.run(
        ["node", str(RUNNER)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(RUNNER.parent.parent.parent),
    )
    sortie = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, "\n" + sortie
    assert "tests JS pass" in sortie, sortie
