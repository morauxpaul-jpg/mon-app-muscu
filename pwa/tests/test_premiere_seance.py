"""Petits correctifs du premier jour (audit du 06/10/2026, profil 1).

- Première fois sur un mouvement à la barre : le poids est pré-rempli à
  20 kg (la barre vide que la carte conseille), sinon « Série faite » était
  refusée au premier tap.
- La fenêtre de fin porte de quoi prévenir quand rien n'est saisi
  (le comportement est joué dans tests/js/test_petits_correctifs.js).
"""
from core.muscu import POIDS_BARRE
from core.seance_contexte import _build_exo_context

W = 200
DATE = "2026-09-21"


def _exo(nom, series=3, muscle="Quadriceps"):
    return {"name": nom, "sets": series, "muscle": muscle, "reps": "8-12"}


def _poids(ctx):
    return [s["poids"] for s in ctx["sets"]]


def test_premiere_fois_a_la_barre_le_poids_part_de_la_barre_vide():
    ctx = _build_exo_context([], _exo("Squat"), "A", W, DATE)
    assert POIDS_BARRE == 20.0
    assert _poids(ctx) == [20.0, 20.0, 20.0]
    assert all(s["reps"] is None for s in ctx["sets"])          # les reps restent à taper
    assert "barre vide" in ctx["conseil_depart"]


def test_barre_reconnue_par_le_nom_aussi():
    ctx = _build_exo_context([], _exo("Développé couché", 2, "Pecs"), "A", W, DATE)
    assert _poids(ctx) == [20.0, 20.0]


def test_pas_de_barre_pas_de_charge_inventee():
    for nom, muscle in (("Élévations latérales", "Épaules"), ("Curl biceps", "Biceps"),
                        ("Pompes", "Pecs"), ("Gainage", "Abdos")):
        ctx = _build_exo_context([], _exo(nom, 2, muscle), "A", W, DATE)
        assert _poids(ctx) == [None, None], nom


def test_avec_un_historique_la_derniere_charge_passe_avant():
    hist = [{"Semaine": W - 1, "Séance": "A", "Exercice": "Squat", "Série": i, "Reps": 5,
             "Poids": 60.0, "Remarque": "", "Muscle": "Quadriceps", "Date": "2026-09-14",
             "RPE": None} for i in (1, 2)]
    ctx = _build_exo_context(hist, _exo("Squat"), "A", W, DATE)
    assert _poids(ctx)[:2] == [60.0, 60.0]
    assert _poids(ctx)[2] is None          # pas de 3e série la dernière fois : rien d'inventé


def test_sans_pre_remplissage_rien_n_est_mis():
    ctx = _build_exo_context([], _exo("Squat"), "A", W, DATE, prefill_weight=False)
    assert _poids(ctx) == [None, None, None]


def test_la_fenetre_de_fin_sait_prevenir_d_une_seance_vide(fake_db, logged_in):
    from test_rpe_suggestion import SEMAINE_1, _programme
    _programme(fake_db)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={SEMAINE_1}").get_data(as_text=True)
    assert 'id="finish-titre"' in html
    assert 'id="finish-vide" hidden' in html
    assert "cette séance ne comptera pas" in html
