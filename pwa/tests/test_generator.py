"""Tests du parseur du générateur IA (fonction pure, sans appel API)."""
import json

import pytest

from routes.generator import parse_and_validate, _clean_muscle


def _valid_payload():
    return {
        "name": "Hypertrophie 3j",
        "notes": "Programme orienté volume.",
        "seances": {
            "Push": [
                {"name": "Développé couché", "sets": 4, "reps": "8-10", "muscle": "Pecs,Triceps"},
                {"name": "Élévations latérales", "sets": 3, "reps": "12-15", "muscle": "Épaules"},
            ],
            "Pull": [
                {"name": "Tractions", "sets": 4, "reps": "6-10", "muscle": "Dos,Biceps"},
            ],
            "Legs": [
                {"name": "Squat", "sets": 5, "reps": "5-8", "muscle": "Quadriceps,Fessiers"},
            ],
        },
        "planning": {"Lundi": "Push", "Mercredi": "Pull", "Vendredi": "Legs"},
    }


def test_parse_dict_ok():
    prog = parse_and_validate(_valid_payload())
    assert prog["name"] == "Hypertrophie 3j"
    assert set(prog["seances"].keys()) == {"Push", "Pull", "Legs"}
    assert prog["seances"]["Push"][0]["name"] == "Développé couché"
    assert prog["planning"]["Lundi"] == "Push"
    # reps conservées pour la preview
    assert prog["seances"]["Push"][0]["reps"] == "8-10"


def test_parse_json_string_with_code_fence():
    raw = "```json\n" + json.dumps(_valid_payload()) + "\n```"
    prog = parse_and_validate(raw)
    assert len(prog["seances"]) == 3


def test_muscle_normalization():
    assert _clean_muscle("pecs, triceps") == "Pecs,Triceps"
    assert _clean_muscle("Épaules") == "Épaules"
    assert _clean_muscle("inconnu") == "Autre"
    assert _clean_muscle("") == "Autre"
    # séparateur slash toléré
    assert _clean_muscle("Dos / Biceps") == "Dos,Biceps"


def test_sets_clamped_and_defaulted():
    payload = {
        "name": "X",
        "seances": {"A": [
            {"name": "Squat", "sets": 99, "muscle": "Quadriceps"},
            {"name": "Curl", "sets": "abc", "muscle": "Biceps"},
        ]},
        "planning": {},
    }
    prog = parse_and_validate(payload)
    assert prog["seances"]["A"][0]["sets"] == 8     # clampé à 8 max
    assert prog["seances"]["A"][1]["sets"] == 3     # défaut si invalide


def test_planning_fallback_when_missing():
    payload = _valid_payload()
    payload["planning"] = {}
    prog = parse_and_validate(payload)
    # Réparti automatiquement → au moins un jour pointe vers une séance.
    assert any(v in prog["seances"] for v in prog["planning"].values())


def test_planning_drops_unknown_seance():
    payload = _valid_payload()
    payload["planning"] = {"Lundi": "Push", "Mardi": "Inexistante"}
    prog = parse_and_validate(payload)
    assert prog["planning"]["Lundi"] == "Push"
    assert prog["planning"]["Mardi"] == ""


def test_empty_raises():
    with pytest.raises(ValueError):
        parse_and_validate("")


def test_no_seances_raises():
    with pytest.raises(ValueError):
        parse_and_validate({"name": "X", "seances": {}})


def test_all_exos_invalid_raises():
    with pytest.raises(ValueError):
        parse_and_validate({"seances": {"A": [{"sets": 3}], "B": ["pas un dict"]}})


def test_invalid_json_string_raises():
    with pytest.raises(ValueError):
        parse_and_validate("{ceci n'est pas du json")


def test_max_six_seances_and_twelve_exos():
    big = {"name": "Big", "seances": {}, "planning": {}}
    for i in range(9):
        big["seances"][f"S{i}"] = [{"name": f"Ex{j}", "sets": 3, "muscle": "Autre"} for j in range(20)]
    prog = parse_and_validate(big)
    assert len(prog["seances"]) <= 6
    for exos in prog["seances"].values():
        assert len(exos) <= 12
