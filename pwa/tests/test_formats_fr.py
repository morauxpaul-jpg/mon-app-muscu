"""Nombres au format français là où l'audit du 28/10 (m2) les a trouvés à
l'anglaise : « 3.9k / 6.2k / 7.1k » sous le volume par semaine de Progrès,
« 6616 / 13100 kg » en haut de la séance, « Record : 82.5 kg » au record."""
import datetime as dt
import pathlib
import re
import subprocess
import shutil

import pytest

from conftest import USER_ID
from core.dates import logical_today_paris

PWA = pathlib.Path(__file__).resolve().parents[1]


def _compte(fake_db, lignes):
    today = logical_today_paris()
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("onboarding").insert({"user_id": USER_ID, "completed_at": (today - dt.timedelta(days=60)).isoformat()}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_started_at": (today - dt.timedelta(days=60)).isoformat()}}).execute()
    for jours_avant, poids, reps in lignes:
        fake_db.table("history").insert({"user_id": USER_ID, "date": (today - dt.timedelta(days=jours_avant)).isoformat(),
            "semaine": 1, "seance": "Push", "exercice": "Développé couché", "muscle": "Pecs",
            "serie": 1, "reps": reps, "poids": poids}).execute()
    return today


def test_le_volume_par_semaine_est_en_tonnes_a_la_francaise(fake_db, logged_in):
    _compte(fake_db, [(0, 62, 100)])                     # 6 200 kg cette semaine
    html = logged_in.get("/progres").get_data(as_text=True)
    assert "6,2 t" in html
    assert not re.search(r"\d\.\dk<", html)


def test_le_volume_de_la_seance_garde_l_espace_des_milliers(fake_db, logged_in):
    _compte(fake_db, [(0, 66.16, 100), (7, 131, 100)])     # 6 616 cette semaine, 13 100 la précédente
    html = logged_in.get("/seance?mode=prefaite&name=Push").get_data(as_text=True)
    zone = re.search(r'id="prog-vol".*?</span>', html, re.S).group(0)
    assert "6 616 / 13 100 kg" in zone
    assert "6616" not in zone and "13100" not in zone


@pytest.mark.skipif(not shutil.which("node"), reason="Node absent")
def test_les_nombres_ecrits_par_seance_js_sont_a_la_francaise():
    """`fmt` de static/js/seance.js (record, volume après une série)."""
    source = (PWA / "static" / "js" / "seance.js").read_text(encoding="utf-8")
    fonction = re.search(r"  function fmt\(n\) \{.*?\n  \}", source, re.S).group(0)
    script = fonction + "\nconsole.log(JSON.stringify([fmt(82.5), fmt(6616), fmt(13100), fmt(80), fmt('')]));"
    sortie = subprocess.run(["node", "-e", script], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    assert sortie.strip() == '["82,5","6 616","13 100","80","0"]'
