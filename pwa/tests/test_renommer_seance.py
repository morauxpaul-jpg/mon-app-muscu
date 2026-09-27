"""Renommer une séance — et emmener son passé avec elle.

Les noms de séance sont uniques TOUS PROGRAMMES CONFONDUS : l'historique les
retrouve par leur nom (`r["Séance"]`), pas par un identifiant. Impossible
d'avoir « Push 1 » dans deux programmes — c'est une contrainte du modèle, pas
un oubli.

Deux défauts corrigés ici :
  — créer ou renommer vers un nom pris échouait EN SILENCE, et on concluait
    à un bug de l'app ;
  — le renommage se faisait côté navigateur, donc l'historique restait sous
    l'ancien nom : la séance repartait à zéro sans que rien ne le signale.
"""
import datetime as dt

import pytest

from conftest import USER_ID, CSRF

MONDAY = dt.date(2026, 9, 14)


@pytest.fixture()
def deux_programmes(fake_db):
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push 1": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "Leg": [{"name": "Squat", "sets": 4, "muscle": "Quadriceps"}],
        "_programmes": [{"id": "p1", "name": "PPL numéro 1"},
                        {"id": "p2", "name": "PPL numéro 2"}],
        "_seance_prog": {"Push 1": "p1", "Leg": "p1"},
        "_planning": {"Lundi": "Push 1", "Mercredi": "Leg"},
        "_settings": {},
        "_extras": {"Push 1|2026-09-14": [{"name": "Dips", "sets": 2}]},
        "_seance_order": {"Push 1|2026-09-14": ["Développé couché"]},
        "_session_notes": {"Push 1|2026-09-14": {"duration_min": 62}},
    }}).execute()
    for i in range(3):
        fake_db.table("history").insert({
            "user_id": USER_ID, "date": MONDAY.isoformat(), "semaine": "2026-W38",
            "seance": "Push 1", "exercice": "Développé couché", "muscle": "Pecs",
            "series": 1, "reps": 8, "poids": 80.0}).execute()
    return fake_db


def _prog(fake_db):
    return fake_db.table("programs").select("*").eq(
        "user_id", USER_ID).execute().data[0]["data"]


def _renommer(client, ancien, nouveau):
    return client.post("/programme/seance/rename",
                       json={"name": ancien, "new_name": nouveau},
                       headers={"X-CSRFToken": CSRF})


# ── Le nom déjà pris ─────────────────────────────────────────────


def test_un_nom_deja_pris_est_refuse_en_le_disant(deux_programmes, logged_in):
    """Le vrai défaut : ça ne faisait rien, sans un mot."""
    r = _renommer(logged_in, "Leg", "Push 1")
    assert r.status_code == 409
    assert r.get_json()["error"] == "pris"


def test_le_refus_nomme_le_programme_qui_detient_le_nom(deux_programmes, logged_in):
    """Sans ça on cherche dans le mauvais programme — surtout quand on est
    en train d'en construire un deuxième à côté du premier."""
    assert _renommer(logged_in, "Leg", "Push 1").get_json()["programme"] \
        == "PPL numéro 1"


def test_un_refus_ne_touche_a_rien(deux_programmes, logged_in):
    _renommer(logged_in, "Leg", "Push 1")
    prog = _prog(deux_programmes)
    assert "Leg" in prog and "Push 1" in prog


def test_un_nom_technique_est_refuse(deux_programmes, logged_in):
    """Une séance appelée « _planning » écraserait le planning."""
    assert _renommer(logged_in, "Leg", "_planning").status_code == 400
    assert isinstance(_prog(deux_programmes)["_planning"], dict)


# ── Le renommage emmène tout ─────────────────────────────────────


def test_la_seance_change_de_nom(deux_programmes, logged_in):
    assert _renommer(logged_in, "Push 1", "Push A").status_code == 200
    prog = _prog(deux_programmes)
    assert "Push A" in prog and "Push 1" not in prog


def test_lhistorique_suit(deux_programmes, logged_in):
    """Le défaut invisible : renommer côté navigateur laissait les séries
    sous l'ancien nom. Volume, records et progression repartaient de zéro."""
    r = _renommer(logged_in, "Push 1", "Push A")
    assert r.get_json()["series"] == 3
    lignes = deux_programmes.table("history").select("*").eq(
        "user_id", USER_ID).execute().data
    assert {l["seance"] for l in lignes} == {"Push A"}


def test_le_planning_suit(deux_programmes, logged_in):
    _renommer(logged_in, "Push 1", "Push A")
    assert _prog(deux_programmes)["_planning"]["Lundi"] == "Push A"


def test_le_rattachement_au_programme_suit(deux_programmes, logged_in):
    """Sans ça la séance sort de son programme et atterrit dans « Non
    classé » — on croit l'avoir perdue."""
    _renommer(logged_in, "Push 1", "Push A")
    assert _prog(deux_programmes)["_seance_prog"]["Push A"] == "p1"


@pytest.mark.parametrize("calque", ["_extras", "_seance_order", "_session_notes"])
def test_les_calques_ranges_par_seance_et_date_suivent(deux_programmes,
                                                       logged_in, calque):
    """Exos ajoutés à la volée, ordre des cartes, bilan de fin : rangés par
    « séance|date ». En oublier un ne casse rien visiblement — ça laisse des
    données orphelines que personne ne reverra."""
    _renommer(logged_in, "Push 1", "Push A")
    store = _prog(deux_programmes)[calque]
    assert "Push A|2026-09-14" in store, store
    assert "Push 1|2026-09-14" not in store


def test_lordre_des_seances_est_conserve(deux_programmes, logged_in):
    """Renommer ne doit pas faire sauter la séance en fin de liste."""
    _renommer(logged_in, "Push 1", "Push A")
    noms = [k for k in _prog(deux_programmes) if not k.startswith("_")]
    assert noms == ["Push A", "Leg"]


def test_une_seance_inconnue_ne_cree_rien(deux_programmes, logged_in):
    assert _renommer(logged_in, "Seance fantome", "Push B").status_code == 404
    assert "Push B" not in _prog(deux_programmes)
