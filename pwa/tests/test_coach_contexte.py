"""Ce que le coach voit de l'utilisateur (audit du 03/10, I9, reproduit R7)."""
from routes.coach import SYSTEM_PROMPT_TMPL, _dernieres_seances, _programme_detail

D = "2026-10-01"


def test_le_programme_porte_la_prescription():
    txt = _programme_detail({"Force": [{"name": "Squat", "sets": 5, "reps": "5", "rest_seconds": 180}],
                             "_planning": {"Lundi": "Force"}})
    assert "Squat (5 × 5, repos 180 s)" in txt


def test_le_cardio_nest_plus_compte_comme_de_la_charge():
    h = [{"Date": D, "Séance": "Push", "Exercice": "CARDIO:Course", "Reps": 30, "Poids": 5.0},
         {"Date": D, "Séance": "Push", "Exercice": "Développé couché", "Reps": 8, "Poids": 80.0}]
    txt = _dernieres_seances(h)
    assert "(vol 640kg)" in txt, txt
    assert "cardio Course 30 min, 5 km" in txt
    assert "CARDIO:" not in txt


def test_le_rpe_et_le_bilan_arrivent_au_coach():
    h = [{"Date": D, "Séance": "Push", "Exercice": "Développé couché", "Reps": 8, "Poids": 80.0, "RPE": 9.0},
         {"Date": D, "Séance": "Push", "Exercice": "Développé couché", "Reps": 7, "Poids": 80.0, "RPE": 10.0}]
    txt = _dernieres_seances(h, {(D, "Push"): {"rating": 2, "comment": "épaule qui tire"}})
    assert "RPE 9.5" in txt
    assert "bilan 2/5 « épaule qui tire »" in txt


def test_le_prompt_ne_decrit_plus_de_fonction_supprimee():
    assert "profils d'entraînement" not in SYSTEM_PROMPT_TMPL
