"""Fiche exercice et standards de force relatifs au gabarit."""
import datetime as dt

from conftest import USER_ID, CSRF
from core import exercise_stats, strength
from core.dates import continuous_week

D1 = dt.date(2026, 8, 3)


def _seed(fake, poids_kg=None, sexe=None):
    profile = {"id": USER_ID, "tier": "vip"}
    if poids_kg:
        profile["poids_kg"] = poids_kg
    fake.table("profiles").insert(profile).execute()
    if sexe:
        fake.table("onboarding").insert({"user_id": USER_ID, "sexe": sexe}).execute()
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": D1.isoformat(),
    }}).execute()


def _series(fake, date, poids, reps=8, exo="Développé couché", serie=1, rpe=None):
    fake.table("history").insert({
        "user_id": USER_ID, "semaine": continuous_week(date), "seance": "Push",
        "exercice": exo, "serie": serie, "reps": reps, "poids": poids,
        "remarque": "", "muscle": "Pecs", "date": date.isoformat(), "rpe": rpe,
    }).execute()


# ── Standards relatifs ───────────────────────────────────────────


def test_standard_depend_du_poids_de_corps():
    leger = strength.standard_for("Pecs", poids_kg=55, sexe="homme")
    lourd = strength.standard_for("Pecs", poids_kg=95, sexe="homme")
    assert leger < lourd
    assert leger == 55.0 and lourd == 95.0  # ratio 1.0 pour les pecs


def test_standard_depend_du_sexe():
    h = strength.standard_for("Quadriceps", poids_kg=70, sexe="homme")
    f = strength.standard_for("Quadriceps", poids_kg=70, sexe="femme")
    assert f < h


def test_sexe_non_precise_prend_la_moyenne():
    h = strength.standard_for("Pecs", poids_kg=70, sexe="homme")
    f = strength.standard_for("Pecs", poids_kg=70, sexe="femme")
    autre = strength.standard_for("Pecs", poids_kg=70, sexe="autre")
    assert f < autre < h


def test_sans_poids_on_retombe_sur_les_valeurs_absolues():
    assert strength.standard_for("Pecs") == 140.0
    assert strength.standard_for("Pecs", poids_kg=0) == 140.0
    assert not strength.is_relative(None)


def test_poids_aberrant_ignore():
    """Un poids en livres saisi par erreur ne doit pas fausser la carte."""
    assert strength.standard_for("Pecs", poids_kg=350) == 140.0
    assert strength.standard_for("Pecs", poids_kg=12) == 140.0


def test_niveau_lisible():
    assert strength.level_for(10) == "Débutant"
    assert strength.level_for(75) == "Intermédiaire"
    assert strength.level_for(140) == "Avancé"


def test_progres_annonce_la_base_des_standards(fake_db, logged_in):
    _seed(fake_db, poids_kg=72, sexe="homme")
    _series(fake_db, D1, 80.0)
    html = logged_in.get("/progres").get_data(as_text=True)
    assert "ton gabarit (72 kg)" in html


def test_progres_invite_a_saisir_son_poids(fake_db, logged_in):
    _seed(fake_db)
    _series(fake_db, D1, 80.0)
    html = logged_in.get("/progres").get_data(as_text=True)
    assert "Renseigne ton poids" in html


# ── Statistiques par exercice (fonctions pures) ──────────────────


def test_sessions_regroupe_par_seance():
    hist = [
        {"Exercice": "Squat", "Date": "2026-09-01", "Séance": "Legs", "Série": 1,
         "Reps": 8, "Poids": 100.0, "RPE": 8},
        {"Exercice": "Squat", "Date": "2026-09-01", "Séance": "Legs", "Série": 2,
         "Reps": 6, "Poids": 100.0, "RPE": 9},
        {"Exercice": "Squat", "Date": "2026-09-08", "Séance": "Legs", "Série": 1,
         "Reps": 8, "Poids": 105.0, "RPE": None},
    ]
    out = exercise_stats.sessions_for(hist, "Squat")
    assert len(out) == 2
    assert out[0]["date"] == "2026-09-08"          # la plus récente d'abord
    assert out[1]["volume"] == 8 * 100 + 6 * 100
    assert out[1]["sets"][0]["rpe"] == 8


def test_sessions_regroupe_les_variantes_du_meme_mouvement():
    hist = [
        {"Exercice": "Squat (Barre)", "Date": "2026-09-01", "Séance": "Legs",
         "Série": 1, "Reps": 5, "Poids": 100.0},
        {"Exercice": "Squat", "Date": "2026-09-08", "Séance": "Legs",
         "Série": 1, "Reps": 5, "Poids": 102.5},
    ]
    assert len(exercise_stats.sessions_for(hist, "Squat", by_base=True)) == 2
    assert len(exercise_stats.sessions_for(hist, "Squat", by_base=False)) == 1


def test_summary_calcule_records_et_progression():
    hist = [
        {"Exercice": "Squat", "Date": "2026-08-01", "Séance": "L", "Série": 1,
         "Reps": 5, "Poids": 100.0},
        {"Exercice": "Squat", "Date": "2026-09-01", "Séance": "L", "Série": 1,
         "Reps": 5, "Poids": 120.0},
    ]
    s = exercise_stats.summary(exercise_stats.sessions_for(hist, "Squat"))
    assert s["sessions"] == 2
    assert s["best_weight"] == 120.0
    assert s["best_weight_date"] == "2026-09-01"
    assert s["volume_total"] == 500 + 600
    assert s["delta_pct"] == 20      # 1RM 116.7 → 140


def test_summary_vide_sans_seance():
    assert exercise_stats.summary([]) == {}


def test_series_ordonne_du_plus_ancien_au_plus_recent():
    hist = [
        {"Exercice": "Squat", "Date": "2026-08-01", "Séance": "L", "Série": 1,
         "Reps": 5, "Poids": 100.0},
        {"Exercice": "Squat", "Date": "2026-09-01", "Séance": "L", "Série": 1,
         "Reps": 5, "Poids": 120.0},
    ]
    pts = exercise_stats.series(exercise_stats.sessions_for(hist, "Squat"), "best_weight")
    assert [p["value"] for p in pts] == [100.0, 120.0]


def test_sparkline_produit_une_polyline_bornee():
    pts = [{"date": "2026-08-01", "value": 100}, {"date": "2026-09-01", "value": 120}]
    chart = exercise_stats.sparkline(pts, width=600, height=160)
    assert len(chart["points"]) == 2
    assert chart["points"][0]["y"] > chart["points"][1]["y"]   # valeur plus haute = y plus petit
    for c in chart["points"]:
        assert 0 <= c["x"] <= 600 and 0 <= c["y"] <= 160
    assert chart["last"]["value"] == 120


def test_sparkline_valeurs_identiques_ne_divise_pas_par_zero():
    pts = [{"date": "2026-08-01", "value": 80}, {"date": "2026-09-01", "value": 80}]
    chart = exercise_stats.sparkline(pts)
    assert len(chart["points"]) == 2


# ── Page ─────────────────────────────────────────────────────────


def test_fiche_exercice_affiche_records_et_historique(fake_db, logged_in):
    _seed(fake_db, poids_kg=75, sexe="homme")
    for i, p in enumerate([70.0, 75.0, 80.0]):
        _series(fake_db, D1 + dt.timedelta(days=7 * i), p, reps=8)
    html = logged_in.get("/progres/exercice?exo=D%C3%A9velopp%C3%A9+couch%C3%A9")\
        .get_data(as_text=True)
    assert "Développé couché" in html
    assert "3 séances" in html
    assert "Toutes tes séances" in html
    assert "Charges estimées" in html      # table RM, l'user est VIP


def test_fiche_exercice_sans_donnees(fake_db, logged_in):
    _seed(fake_db)
    html = logged_in.get("/progres/exercice?exo=Inconnu").get_data(as_text=True)
    assert "Aucune série enregistrée" in html


def test_fiche_exercice_sans_parametre_redirige(fake_db, logged_in):
    _seed(fake_db)
    assert logged_in.get("/progres/exercice").status_code == 302


def test_fiche_exercice_accessible_aux_gratuits(fake_db, client):
    """La fiche est la base offerte par les concurrents : elle reste gratuite."""
    import time
    _seed(fake_db)
    _series(fake_db, D1, 80.0)
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time(), _csrf=CSRF)
    html = client.get("/progres/exercice?exo=D%C3%A9velopp%C3%A9+couch%C3%A9")\
        .get_data(as_text=True)
    assert "Toutes tes séances" in html
    assert "Charges estimées par nombre de reps" not in html   # table RM = PRO


def test_progres_ne_charge_plus_plotly(fake_db, logged_in):
    """3,5 Mo de bibliothèque pour tracer une ligne de 8 points : remplacé
    par du SVG calculé côté serveur."""
    _seed(fake_db)
    _series(fake_db, D1, 80.0)
    html = logged_in.get("/progres").get_data(as_text=True)
    assert "plot.ly" not in html
    assert "Plotly" not in html
