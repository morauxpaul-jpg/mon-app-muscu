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


# ── Retour du 26/10 : « pec deck 39 kg, contre 15,8 kg le 12/10 » ─────


def _ligne(d, exo, serie, reps, poids, seance="Push 1"):
    return {"Date": d, "Séance": seance, "Exercice": exo, "Série": serie, "Reps": reps, "Poids": poids}


# Les vraies séances de l'ami (26/10) : le 12/10, le pushdown était à 15,8 kg,
# le pec deck à 39 kg ; le pec deck n'était à 15,8 kg que le 4/10.
HIST_AMI = [
    _ligne("2026-10-04", "Développé incliné haltères", 1, 9, 18.0),
    _ligne("2026-10-04", "Pec deck (machine)", 1, 12, 15.8),
    _ligne("2026-10-04", "Pec deck (machine)", 2, 11, 15.8),
    _ligne("2026-10-12", "Pec deck (machine)", 1, 10, 39.0),
    _ligne("2026-10-12", "Pec deck (machine)", 2, 8, 39.0),
    _ligne("2026-10-12", "Pushdown poulie corde", 1, 11, 15.8),
    _ligne("2026-10-12", "Dips (triceps)", 1, 0, 0.0),
    _ligne("2026-10-20", "Pec deck (machine)", 1, 9, 39.0),
    _ligne("2026-10-20", "Dips (triceps)", 1, 14, 0.0),
    {"Date": "2026-10-20", "Séance": "Push 1", "Exercice": "CARDIO:Course", "Reps": 20, "Poids": 3.0},
]


def test_chaque_exercice_a_sa_ligne_de_progression_datee():
    from core.coach_progression import progression_par_exercice
    txt = progression_par_exercice(HIST_AMI)
    pec = next(l for l in txt.splitlines() if l.startswith("- Pec deck"))
    assert pec == ("- Pec deck (machine) → 2026-10-20 : 39 kg × 9 | "
                   "2026-10-12 : 39 kg × 10, 39 kg × 8 | 2026-10-04 : 15.8 kg × 12, 15.8 kg × 11")
    assert "- Dips (triceps) → 2026-10-20 : poids du corps × 14" in txt   # série à 0 rep ignorée
    assert "CARDIO" not in txt and "Course" not in txt
    assert txt.splitlines()[0].startswith(("- Pec deck", "- Dips"))      # le plus récent d'abord


def test_au_plus_4_seances_par_exercice():
    from core.coach_progression import progression_par_exercice
    h = [_ligne(f"2026-10-{j:02d}", "Squat", 1, 5, 100.0 + j) for j in range(1, 8)]
    ligne = progression_par_exercice(h)
    assert ligne.count("|") == 3 and "2026-10-07" in ligne and "2026-10-03" not in ligne


def test_le_prompt_porte_la_progression_et_la_regle_des_chiffres():
    assert "{progression}" in SYSTEM_PROMPT_TMPL
    assert "ne cite une charge, des reps ou une date que s'ils figurent" in SYSTEM_PROMPT_TMPL


def test_le_septieme_exercice_dune_seance_arrive_au_coach():
    exos = ["A", "B", "C", "D", "E", "F", "Septième"]
    h = [_ligne(D, e, 1, 8, 20.0) for e in exos]
    assert "Septième 1s @20kg" in _dernieres_seances(h)
