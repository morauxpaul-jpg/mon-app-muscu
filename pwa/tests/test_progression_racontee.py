"""Progression racontée et charge de départ (audit du 03/10, profils 1 et 2)."""
from conftest import USER_ID
from core.muscu import conseil_depart
from core.progression import faits_marquants

W = 300


def _r(sem, exo, poids, reps=5):
    return {"Semaine": sem, "Exercice": exo, "Poids": poids, "Reps": reps, "Remarque": ""}


def test_gain_de_charge_raconte():
    hist = [_r(W - 4, "Squat", 60), _r(W - 4, "Squat", 62.5), _r(W - 1, "Squat", 70), _r(W, "Squat", 72.5)]
    (f,) = faits_marquants(hist, W)
    assert f["texte"] == "Squat : +10 kg en 4 semaines"


def test_poids_du_corps_en_reps_et_tri_par_gain_relatif():
    hist = ([_r(W - 5, "Tractions", 0, 5), _r(W, "Tractions", 0, 9)]
            + [_r(W - 5, "Squat", 100), _r(W, "Squat", 102.5)])
    faits = faits_marquants(hist, W)
    assert faits[0]["texte"] == "Tractions : +4 reps en 5 semaines"         # +80 % avant +2,5 %
    assert faits[1]["exo"] == "Squat"


def test_rien_a_raconter():
    assert faits_marquants([_r(W - 4, "Squat", 60), _r(W, "Squat", 61)], W) == []    # gain trop faible
    assert faits_marquants([_r(W, "Squat", 60)], W) == []                            # pas d'ancien
    assert faits_marquants([_r(W - 4, "Squat", 60), _r(W - 3, "Squat", 80)], W) == []  # pas récent


def test_conseil_de_depart():
    assert "barre vide" in conseil_depart("Squat", False)
    assert "RPE 6-7" in conseil_depart("Curl biceps", False)
    assert "réserve" in conseil_depart("Pompes", True)


def test_carte_premiere_fois_puis_disparait(fake_db, logged_in):
    from test_rpe_suggestion import SEMAINE_1, SEMAINE_2, _programme, _saisir
    _programme(fake_db)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={SEMAINE_1}").get_data(as_text=True)
    assert 'class="exo-conseil"' in html and "barre vide" in html      # développé couché
    _saisir(logged_in, [{"reps": 8, "poids": 60}], SEMAINE_1)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={SEMAINE_2}").get_data(as_text=True)
    assert 'class="exo-conseil"' not in html


def test_accueil_raconte_le_progres(fake_db, logged_in):
    import datetime as dt
    from core.dates import logical_today_paris, monday_of
    lundi = monday_of(logical_today_paris())
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {"_settings": {}}}).execute()
    for semaines, poids in ((4, 60), (0, 70)):
        fake_db.table("history").insert({
            "user_id": USER_ID, "semaine": 1, "seance": "A", "exercice": "Squat", "serie": 1,
            "reps": 5, "poids": poids, "remarque": "", "muscle": "Quadriceps",
            "date": (lundi - dt.timedelta(weeks=semaines)).isoformat()}).execute()
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert "Tes progrès" in html and "Squat : +10 kg en 4 semaines" in html
