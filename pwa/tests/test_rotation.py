"""Rotation des séances : un A/B sur 3 jours alterne vraiment, un PPL sur
2 jours garde Legs (audit du 03/10)."""
import datetime as dt
import json

from conftest import CSRF, USER_ID
from core import catalog
from core.dates import DAYS_FR, logical_today_paris, monday_of
from core.rotation import planning_semaine, rotation_de, rotation_nettoyee, seance_prevue

LUNDI = dt.date(2026, 9, 7)
LMV = {d: "" for d in DAYS_FR}


def _prog(rotation, planning, started="2026-09-07"):
    p = {"A": [{"name": "Squat", "sets": 3}], "B": [{"name": "Rowing", "sets": 3}],
         "C": [{"name": "Curl", "sets": 3}],
         "_planning": {**LMV, **planning}, "_started_at": started}
    if rotation is not None:
        p["_rotation"] = rotation
    return p


def _semaine(prog, lundi):
    return [seance_prevue(prog, lundi + dt.timedelta(days=i)) for i in range(7)]


def test_ab_sur_trois_jours_alterne_d_une_semaine_a_l_autre():
    prog = _prog(["A", "B"], {"Lundi": "A", "Mercredi": "B", "Vendredi": "A"})
    assert _semaine(prog, LUNDI) == ["A", "", "B", "", "A", "", ""]
    assert _semaine(prog, LUNDI + dt.timedelta(days=7)) == ["B", "", "A", "", "B", "", ""]
    assert _semaine(prog, LUNDI + dt.timedelta(days=14)) == ["A", "", "B", "", "A", "", ""]


def test_trois_seances_sur_deux_jours_n_en_perd_aucune():
    prog = _prog(["A", "B", "C"], {"Lundi": "A", "Jeudi": "B"})
    vues = [s for k in range(3) for s in _semaine(prog, LUNDI + dt.timedelta(days=7 * k)) if s]
    assert vues == ["A", "B", "C", "A", "B", "C"]


def test_programme_commence_en_milieu_de_semaine_ouvre_sur_a():
    prog = _prog(["A", "B"], {"Lundi": "A", "Mercredi": "B", "Vendredi": "A"},
                 started="2026-09-09")                       # un mercredi
    assert seance_prevue(prog, dt.date(2026, 9, 9)) == "A"
    assert seance_prevue(prog, dt.date(2026, 9, 11)) == "B"
    assert seance_prevue(prog, dt.date(2026, 9, 14)) == "A"  # lundi suivant


def test_sans_rotation_rien_ne_change():
    planning = {"Lundi": "A", "Mercredi": "B", "Vendredi": "A"}
    prog = _prog(None, planning)
    for k in range(3):
        assert _semaine(prog, LUNDI + dt.timedelta(days=7 * k)) == ["A", "", "B", "", "A", "", ""]


def test_rotation_invalide_ignoree():
    planning = {"Lundi": "A", "Mercredi": "B"}
    assert rotation_de(_prog(["A"], planning)) == []
    assert rotation_de(_prog(["A", "Disparue"], planning)) == []
    assert rotation_de(_prog("A,B", planning)) == []
    assert _semaine(_prog(["A", "Disparue"], planning), LUNDI)[:3] == ["A", "", "B"]
    assert rotation_nettoyee(["A", "X", "B"], {"A", "B"}) == ["A", "B"]
    assert rotation_nettoyee(["A", "X"], {"A", "B"}) == []


def test_planning_semaine_suit_la_rotation():
    prog = _prog(["A", "B"], {"Lundi": "A", "Mercredi": "B", "Vendredi": "A"})
    sem2 = planning_semaine(prog, LUNDI + dt.timedelta(days=9))
    assert (sem2["Lundi"], sem2["Mercredi"], sem2["Vendredi"], sem2["Mardi"]) == ("B", "A", "B", "")


# ── Construction depuis le catalogue ─────────────────────────────


def _catalogue_a(n):
    return next(pid for pid, p in catalog.CATALOG.items() if len(p["seances"]) == n)


def test_catalogue_ne_tronque_plus():
    pid = _catalogue_a(3)
    built = catalog.build_program(pid, 2)
    noms = [k for k in built if not k.startswith("_")]
    assert len(noms) == 3                               # Legs n'est plus perdu
    assert built["_rotation"] == noms
    assert sum(1 for v in built["_planning"].values() if v) == 2


def test_catalogue_sans_rotation_quand_les_jours_tombent_juste():
    pid = _catalogue_a(2)
    assert "_rotation" not in catalog.build_program(pid, 2)
    assert "_rotation" not in catalog.build_program(pid, 4)
    assert catalog.build_program(pid, 3)["_rotation"] == list(catalog.CATALOG[pid]["seances"])


# ── Parcours ─────────────────────────────────────────────────────


def _seed(fake_db, **extra):
    today = logical_today_paris()
    data = _prog(["A", "B"], {d: ("A" if d in ("Lundi", "Mercredi", "Vendredi") else "")
                              for d in DAYS_FR},
                 started=monday_of(today).isoformat())
    data.update(extra)
    fake_db.table("programs").insert({"user_id": USER_ID, "data": data}).execute()
    return today


def _blob(fake_db):
    return fake_db.tables["programs"][0]["data"]


def test_editeur_garde_la_rotation(fake_db, logged_in):
    _seed(fake_db)
    blob = _blob(fake_db)
    state = {"name": "P", "planning": blob["_planning"],
             "seances": {k: v for k, v in blob.items() if not k.startswith("_")},
             "seance_order": ["A", "B", "C"]}
    r = logged_in.post("/programme/state", data=json.dumps(state),
                       headers={"X-CSRFToken": CSRF, "Content-Type": "application/json"})
    assert r.status_code == 200
    assert _blob(fake_db)["_rotation"] == ["A", "B"]

    state["rotation"] = []                              # case décochée
    logged_in.post("/programme/state", data=json.dumps(state),
                   headers={"X-CSRFToken": CSRF, "Content-Type": "application/json"})
    assert "_rotation" not in _blob(fake_db)


def test_renommer_une_seance_renomme_la_rotation(fake_db, logged_in):
    _seed(fake_db)
    r = logged_in.post("/programme/seance/rename", json={"name": "B", "new_name": "Haut"},
                       headers={"X-CSRFToken": CSRF})
    assert r.status_code == 200
    assert _blob(fake_db)["_rotation"] == ["A", "Haut"]


def test_accueil_precache_la_seance_de_la_rotation(fake_db, logged_in):
    import re
    # A planifiée tous les jours, rotation A/B : aujourd'hui et demain sont
    # deux séances différentes. Sans rotation, seul A serait annoncé.
    _seed(fake_db, _planning={d: "A" for d in DAYS_FR})
    html = logged_in.get("/accueil").get_data(as_text=True)
    urls = json.loads(re.search(r'id="precache-urls">(.*?)</script>', html, re.S).group(1))
    noms = {u.split("name=")[1].split("&")[0] for u in urls if "name=" in u}
    assert noms == {"A", "B"}
