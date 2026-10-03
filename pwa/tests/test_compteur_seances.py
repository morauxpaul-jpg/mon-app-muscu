"""Le compteur « Séances x/y » de l'accueil (audit du 03/10, I8, reproduit R5).

Il comptait les NOMS de séance distincts faits cette semaine, sur le nombre
de séances du programme : Full Body A, B, A faits lundi-mercredi-vendredi
donnait « 2/2 », et un membre à trois dossiers lisait « 3/9 ».
"""
import datetime as dt
import re

from conftest import USER_ID
from core.dates import DAYS_FR, logical_today_paris, monday_of


def _prog(fake, planning, seances=("Full Body A", "Full Body B")):
    data = {s: [{"name": "Squat", "sets": 3, "muscle": "Quadriceps"}] for s in seances}
    data.update({"_planning": planning, "_settings": {}, "_badges": [], "_upsell_seen": True})
    fake.table("programs").insert({"user_id": USER_ID, "data": data}).execute()


def _fait(fake, d, seance):
    fake.table("history").insert({
        "user_id": USER_ID, "date": d.isoformat(), "semaine": 1, "seance": seance,
        "exercice": "Squat", "serie": 1, "reps": 8, "poids": 60.0, "remarque": "",
        "muscle": "Quadriceps"}).execute()


def _compteur(client):
    html = client.get("/accueil").get_data(as_text=True)
    m = re.search(r'SÉANCES</div>\s*<div class="stat-value">(\d+)/(\d+)', html)
    return int(m.group(1)), int(m.group(2))


def test_full_body_a_b_a_compte_chaque_seance(fake_db, logged_in):
    lundi = monday_of(logical_today_paris())
    _prog(fake_db, {"Lundi": "Full Body A", "Mercredi": "Full Body B", "Vendredi": "Full Body A"})
    # Trois séances cette semaine, dont deux du même nom, aux jours passés.
    jours = [lundi + dt.timedelta(days=k) for k in (0, 2, 4)
             if lundi + dt.timedelta(days=k) <= logical_today_paris()]
    for d, s in zip(jours, ("Full Body A", "Full Body B", "Full Body A")):
        _fait(fake_db, d, s)
    assert _compteur(logged_in) == (len(jours), 3)


def test_plusieurs_dossiers_le_total_est_le_planning(fake_db, logged_in):
    _prog(fake_db, {"Lundi": "Push", "Mercredi": "Pull", "Vendredi": "Legs"},
          seances=("Push", "Pull", "Legs", "Maison A", "Maison B", "Haut", "Bas", "Bras", "Abdos"))
    assert _compteur(logged_in) == (0, 3)


def test_sans_planning_on_retombe_sur_les_seances_du_programme(fake_db, logged_in):
    _prog(fake_db, {j: "" for j in DAYS_FR})
    assert _compteur(logged_in) == (0, 2)
