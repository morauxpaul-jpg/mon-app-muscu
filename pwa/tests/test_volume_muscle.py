"""Séries par muscle et par semaine (audit du 03/10, axe 4)."""
import datetime as dt

from conftest import USER_ID
from core.volume_muscle import repere, series_par_muscle, tableau_semaine

LUNDI = dt.date(2026, 9, 14)


def _r(jour, muscle, reps=8, exo="Développé couché", remarque=""):
    return {"Date": (LUNDI + dt.timedelta(days=jour)).isoformat(), "Exercice": exo,
            "Muscle": muscle, "Reps": reps, "Poids": 60, "Remarque": remarque}


def test_principal_compte_1_secondaires_un_demi():
    hist = [_r(0, "Pecs,Triceps,Épaules")] * 4 + [_r(2, "Triceps", exo="Extensions")] * 3
    assert series_par_muscle(hist, LUNDI) == {"Pecs": 4, "Triceps": 5.0, "Épaules": 2.0}


def test_ce_qui_ne_compte_pas():
    hist = [_r(0, "Pecs", reps=0),                                   # pas faite
            _r(0, "Pecs", remarque="SKIP"),                          # passée
            _r(0, "Cardio", exo="CARDIO:Course"),
            _r(0, "", exo="SESSION"),
            _r(7, "Pecs"),                                           # semaine suivante
            _r(-1, "Pecs")]                                          # semaine d'avant
    assert series_par_muscle(hist, LUNDI) == {}


def test_tableau_statuts_et_semaine_passee():
    hist = ([_r(1, "Pecs")] * 12 + [_r(1, "Biceps")] * 3 + [_r(1, "Mollets")] * 18
            + [_r(-3, "Dos")] * 10)
    lignes = {l["muscle"]: l for l in tableau_semaine(hist, LUNDI + dt.timedelta(days=4))}
    assert lignes["Pecs"]["statut"] == "zone" and lignes["Pecs"]["series"] == 12
    assert lignes["Biceps"]["statut"] == "sous"
    assert lignes["Mollets"]["statut"] == "au-dela" and repere("Mollets") == (6, 16)
    assert lignes["Dos"]["series"] == 0 and lignes["Dos"]["precedente"] == 10
    assert list(lignes)[0] == "Mollets"                              # le plus travaillé d'abord


def test_page_progres_affiche_le_tableau_pour_tous(fake_db, logged_in):
    from core.dates import continuous_week, today_paris
    today = today_paris()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {"_settings": {}}}).execute()
    for i in range(3):
        fake_db.table("history").insert({
            "user_id": USER_ID, "semaine": continuous_week(today), "seance": "Push",
            "exercice": "Développé couché", "serie": i + 1, "reps": 8, "poids": 60.0,
            "remarque": "", "muscle": "Pecs,Triceps", "date": today.isoformat()}).execute()
    html = logged_in.get("/progres").get_data(as_text=True)          # compte gratuit
    assert "Séries par muscle cette semaine" in html
    assert "<b>3</b><small> / 10-20</small>" in html                 # pecs
    assert "<b>1,5</b>" in html                                       # triceps, secondaire
