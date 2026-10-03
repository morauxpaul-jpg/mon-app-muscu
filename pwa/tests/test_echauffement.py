"""Séries d'échauffement : rampe affichée avant une charge lourde, jamais
enregistrée (audit du 03/10)."""
from core.muscu import est_a_la_barre, series_echauffement


def test_rampe_squat_a_100_kg():
    assert series_echauffement(100, barre=True) == [
        {"poids": 20.0, "reps": 10}, {"poids": 40.0, "reps": 8},
        {"poids": 60.0, "reps": 5}, {"poids": 80.0, "reps": 3},
        {"poids": 90.0, "reps": 1}]


def test_rampe_haltere_sans_barre_vide():
    assert series_echauffement(40) == [
        {"poids": 15.0, "reps": 8}, {"poids": 25.0, "reps": 5}, {"poids": 32.5, "reps": 3}]


def test_charge_legere_pas_d_echauffement():
    assert series_echauffement(25, barre=True) == []
    assert series_echauffement(None) == []
    assert series_echauffement("abc") == []


def test_a_la_barre_les_paliers_ne_descendent_pas_sous_la_barre():
    rampe = series_echauffement(35, barre=True)
    poids = [s["poids"] for s in rampe]
    assert poids == sorted(set(poids)) and all(p >= 20 for p in poids) and max(poids) < 35


def test_detection_barre():
    assert est_a_la_barre("Squat") and est_a_la_barre("Rowing barre")
    assert not est_a_la_barre("Curl haltères") and not est_a_la_barre("Tractions")


def test_la_carte_propose_l_echauffement_sans_rien_enregistrer(fake_db, logged_in):
    from test_rpe_suggestion import SEMAINE_1, SEMAINE_2, _programme, _saisir
    _programme(fake_db, reps="5")
    _saisir(logged_in, [{"reps": 5, "poids": 100}] * 3, SEMAINE_1)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={SEMAINE_2.isoformat()}"
                         ).get_data(as_text=True)
    assert "Échauffement · 5 séries" in html
    # Charge suggérée : 102,5 kg (3 × 5 au haut de la cible) — la rampe y mène.
    assert "20 kg × 10" in html and "82.5 kg × 3" in html and "92.5 kg × 1" in html
    assert len(fake_db.tables["history"]) == 3        # rien d'écrit en plus


def test_premiere_fois_pas_d_echauffement(fake_db, logged_in):
    from test_rpe_suggestion import SEMAINE_2, _programme
    _programme(fake_db)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={SEMAINE_2.isoformat()}"
                         ).get_data(as_text=True)
    assert "exo-echauffement" not in html
