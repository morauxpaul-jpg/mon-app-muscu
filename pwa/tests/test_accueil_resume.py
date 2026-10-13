"""Accueil du style « Instrument » : séance du jour, poids, dernier record
(core/accueil_resume.py) et leur place dans la page."""
import datetime as dt
import re

from conftest import USER_ID
from core.accueil_resume import contenu_seance, date_courte, dernier_record, poids_resume

AUJ = dt.date(2026, 10, 13)


def _ligne(date, exo, poids, reps, serie=1):
    return {"Date": date, "Exercice": exo, "Poids": poids, "Reps": reps, "Série": serie,
            "Séance": "Push", "Remarque": ""}


def test_contenu_dune_seance_du_programme():
    prog = {"Push": [{"name": "Développé couché", "sets": 4}, {"name": "Dips", "sets": "3"},
                     {"name": "Élévations latérales"}]}
    assert contenu_seance(prog, "Push") == {"exercices": 3, "series": 7, "premier": "Développé couché"}
    assert contenu_seance(prog, "Absente") == {"exercices": 0, "series": 0, "premier": ""}


def test_le_poids_donne_la_pente_par_semaine_sur_six_semaines():
    pesees = [{"date": (AUJ - dt.timedelta(days=j)).isoformat(), "poids_kg": round(92.0 - (21 - j) * 0.1, 1)}
              for j in (21, 14, 7, 0)]
    p = poids_resume(pesees, AUJ)
    assert p["kg"] == "89,9"
    assert p["kg_semaine"] == -0.7
    assert p["texte"] == "\u22120,7\u00a0kg / semaine"


def test_trop_peu_de_pesees_on_donne_la_date_pas_une_tendance_inventee():
    p = poids_resume([{"date": "2026-10-08", "poids_kg": 91.4}, {"date": "2026-10-11", "poids_kg": 91.2}], AUJ)
    assert p["kg"] == "91,2" and p["kg_semaine"] is None
    assert p["texte"] == "Pesée du 11/10"
    assert poids_resume([], AUJ) is None
    # Une pesée « dans le futur » (fuseau, saisie) n'est pas la dernière.
    assert poids_resume([{"date": "2026-10-20", "poids_kg": 80}], AUJ) is None


def test_le_dernier_record_est_la_derniere_serie_qui_bat_la_force_estimee():
    # Force estimée (Epley) : poids × (1 + reps / 30).
    hist = [
        _ligne("2026-06-01", "Développé couché", 80, 8),         # 101,3
        _ligne("2026-06-01", "Développé couché", 82.5, 6, 2),   # 99 : même jour, rien à battre
        _ligne("2026-06-04", "Squat", 100, 5),                   # 116,7 : première séance
        _ligne("2026-06-08", "Développé couché", 82.5, 9),       # 107,3 : bat 101,3
        _ligne("2026-06-08", "Développé couché", 85, 5, 2),      # 99,2 : non
        _ligne("2026-06-10", "Squat", 90, 5),                    # 105 : ne bat pas 116,7
    ]
    r = dernier_record(hist)
    assert (r["exo"], r["date"], r["texte"], r["jour"]) == ("Développé couché", "2026-06-08", "82,5 × 9", "8 juin")


def test_au_poids_du_corps_le_record_se_compte_en_repetitions():
    hist = [_ligne("2026-06-01", "Tractions", 0, 8), _ligne("2026-06-05", "Tractions", 0, 10)]
    assert dernier_record(hist)["texte"] == "10 reps"


def test_pas_de_record_sans_rien_a_battre():
    assert dernier_record([_ligne("2026-06-01", "Squat", 100, 5)]) is None
    assert dernier_record([]) is None
    # Le cardio et les séries sautées ne battent rien.
    assert dernier_record([_ligne("2026-06-01", "CARDIO:Course", 0, 30),
                           _ligne("2026-06-02", "CARDIO:Course", 0, 40)]) is None


def test_date_courte():
    assert date_courte(AUJ) == "mar. 13 oct."


def test_laccueil_met_la_seance_la_semaine_et_le_record_en_tete(fake_db, logged_in):
    from core.dates import DAYS_FR, logical_today_paris
    auj = logical_today_paris()
    prog = {"Push": [{"name": "Développé couché", "sets": 4, "muscle": "Pecs"},
                     {"name": "Dips", "sets": 3, "muscle": "Triceps"}],
            "_planning": {DAYS_FR[auj.weekday()]: "Push"}}
    fake_db.table("programs").insert({"user_id": USER_ID, "data": prog}).execute()
    html = logged_in.get("/accueil").get_data(as_text=True)
    seance = re.search(r'<section class="acc-seance"[^>]*>(.*?)</section>', html, re.S).group(1)
    assert "PROCHAINE SÉANCE · AUJOURD&#39;HUI" in seance or "PROCHAINE SÉANCE · AUJOURD'HUI" in seance
    assert '<div class="acc-seance-nom">Push</div>' in seance
    assert "<b>2</b> exercices" in seance and "<b>7</b> séries" in seance
    assert "Développé couché en premier" in seance and "Commencer" in seance
    # Sept barres, celle d'aujourd'hui encadrée.
    assert html.count('class="acc-jour ') == 7
    assert html.count("acc-jour--auj") == 1
