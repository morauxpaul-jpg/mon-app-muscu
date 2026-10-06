"""Adopter un programme ne supprime plus les autres (audit du 30/09, I16).

Un membre PRO avec « Salle », « Maison » et « Vacances » qui adoptait un
programme généré — ou « Changeait de programme » — perdait les trois :
tout le corps du blob était remplacé, alors que l'avertissement parlait de
« tes séances actuelles ». Désormais seul le programme EN COURS (celui dont
le planning utilise les séances) est remplacé.
"""
import json

import pytest

from conftest import USER_ID, CSRF, prog_lu
from core.programmes_dossiers import (fusionner_dans_le_programme_en_cours,
                                      remplacer_programme_en_cours)

SEMAINE = ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")


def _trois_programmes():
    return {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "Pull": [{"name": "Tractions", "sets": 3, "muscle": "Dos"}],
        "Maison A": [{"name": "Pompes", "sets": 3, "muscle": "Pecs"}],
        "Hôtel": [{"name": "Burpees", "sets": 3, "muscle": "Cardio"}],
        "_programmes": [{"id": "p_salle", "name": "Salle"},
                        {"id": "p_maison", "name": "Maison"},
                        {"id": "p_vac", "name": "Vacances"}],
        "_seance_prog": {"Push": "p_salle", "Pull": "p_salle",
                         "Maison A": "p_maison", "Hôtel": "p_vac"},
        "_planning": {"Lundi": "Push", "Jeudi": "Pull"},
        "_badges": ["first_session"],
        "_settings": {"auto_rest_timer": False},
    }


# ── La règle ─────────────────────────────────────────────────────


def test_remplacer_ne_touche_quau_programme_en_cours():
    body = remplacer_programme_en_cours(
        _trois_programmes(), {"Haut": [], "Bas": []},
        {"Lundi": "Haut", "Mercredi": "Bas"}, "Programme IA", "2026-09-30")
    assert "Push" not in body and "Pull" not in body, "le programme en cours est remplacé"
    assert "Maison A" in body and "Hôtel" in body, "les autres programmes restent"
    noms = [p["name"] for p in body["_programmes"]]
    assert noms[:2] == ["Maison", "Vacances"] and noms[2] == "Programme IA"
    nouvel_id = body["_programmes"][2]["id"]
    assert body["_seance_prog"] == {"Maison A": "p_maison", "Hôtel": "p_vac",
                                    "Haut": nouvel_id, "Bas": nouvel_id}
    assert body["_planning"] == {"Lundi": "Haut", "Mercredi": "Bas"}
    assert body["_name"] == "Programme IA" and body["_started_at"] == "2026-09-30"


def test_un_nom_deja_pris_par_un_autre_programme_est_suffixe():
    """Les noms de séance identifient l'historique : pas de collision."""
    body = remplacer_programme_en_cours(
        _trois_programmes(), {"Maison A": [{"name": "Squat"}]},
        {"Lundi": "Maison A"}, "Nouveau", "2026-09-30")
    assert body["Maison A"] == [{"name": "Pompes", "sets": 3, "muscle": "Pecs"}]
    assert body["Maison A 2"] == [{"name": "Squat"}]
    assert body["_planning"] == {"Lundi": "Maison A 2"}


def test_un_seul_programme_se_remplace_comme_avant():
    old = {"Full A": [], "Full B": [], "_planning": {"Lundi": "Full A"}}
    body = remplacer_programme_en_cours(old, {"PPL Push": []}, {"Lundi": "PPL Push"},
                                        "PPL", "2026-09-30")
    assert [k for k in body if not k.startswith("_")] == ["PPL Push"]
    assert [p["name"] for p in body["_programmes"]] == ["PPL"]


def test_fusionner_garde_tous_les_dossiers():
    body = fusionner_dans_le_programme_en_cours(
        _trois_programmes(), {"Legs": [], "Push": [{"name": "autre"}]})
    assert body["Push"] == [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}]
    assert body["_seance_prog"]["Legs"] == "p_salle"
    assert len(body["_programmes"]) == 3
    assert body["_planning"] == {"Lundi": "Push", "Jeudi": "Pull"}


# ── Par les routes ───────────────────────────────────────────────


@pytest.fixture()
def membre(fake_db):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": _trois_programmes()}).execute()
    return fake_db


def _data(fake):
    return fake.tables["programs"][0]["data"]


def test_adopter_un_programme_genere_garde_les_autres(membre, logged_in):
    program = {
        "name": "Programme IA",
        "seances": {"Haut": [{"name": "Développé couché", "sets": 4,
                              "reps": "8-12", "rest_seconds": 120, "muscle": "Pecs"}]},
        "planning": {"Lundi": "Haut"},
    }
    r = logged_in.post("/generator/apply", data={"_csrf": CSRF, "program": json.dumps(program)})
    assert r.status_code == 302
    d = _data(membre)
    assert {"Maison A", "Hôtel", "Haut"} <= set(d)
    assert {p["name"] for p in d["_programmes"]} == {"Maison", "Vacances", "Programme IA"}
    assert prog_lu()["_badges"] == ["first_session"], "les données perso restent"


def test_changer_de_programme_garde_les_autres(membre, logged_in):
    r = logged_in.post("/programme/change-program", data={
        "_csrf": CSRF, "programme_id": "fb_deb_3j", "mode": "replace", "confirm": "yes"})
    assert r.status_code == 302
    d = _data(membre)
    assert "Maison A" in d and "Hôtel" in d
    assert "Push" not in d
    assert len(d["_programmes"]) == 3


def test_fusionner_un_programme_garde_les_dossiers(membre, logged_in):
    logged_in.post("/programme/change-program", data={
        "_csrf": CSRF, "programme_id": "fb_deb_3j", "mode": "merge", "confirm": "yes"})
    d = _data(membre)
    assert {"Push", "Pull", "Maison A", "Hôtel"} <= set(d)
    assert {p["id"] for p in d["_programmes"]} == {"p_salle", "p_maison", "p_vac"}


def test_repartir_de_zero_garde_les_autres(membre, logged_in):
    logged_in.post("/programme/change-program", data={
        "_csrf": CSRF, "programme_id": "custom", "confirm": "yes"})
    d = _data(membre)
    assert "Maison A" in d and "Hôtel" in d and "Push" not in d
    assert all(v == "" for v in d["_planning"].values())


def test_la_page_programme_montre_les_trois_apres_adoption(membre, logged_in):
    program = {"name": "Programme IA", "planning": {"Lundi": "Haut"},
               "seances": {"Haut": [{"name": "Développé couché", "sets": 4, "muscle": "Pecs"}]}}
    logged_in.post("/generator/apply", data={"_csrf": CSRF, "program": json.dumps(program)})
    html = logged_in.get("/programme").get_data(as_text=True)
    for nom in ("Maison", "Vacances", "Programme IA"):
        assert nom in html
