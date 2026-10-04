"""Identité stable des exercices (audit du 03/10, modèle de données).

Un exercice était retrouvé par son NOM : le renommer coupait son passé, sauf à
réécrire toutes ses séries. Il porte maintenant un identifiant qui survit aux
renommages (core/exercice_ids.py), et chaque série enregistrée le porte aussi
(`history.exercise_id`, migration v42).
"""
import datetime as dt
import json

import core.db_historique as dh
from conftest import CSRF, USER_ID
from core import db
from core import exercice_ids as ei

LUNDI = dt.date(2026, 9, 14)
JSON = {"Accept": "application/json", "X-CSRFToken": CSRF}


def _prog(fake, exos=None, autres=None):
    data = {"Push": exos or [{"name": "Curl", "sets": 3, "muscle": "Biceps"}],
            "_planning": {"Lundi": "Push"}, "_started_at": LUNDI.isoformat()}
    data.update(autres or {})
    fake.table("programs").insert({"user_id": USER_ID, "data": data}).execute()


def _blob(fake):
    return next(p for p in fake.tables["programs"] if p["user_id"] == USER_ID)["data"]


def _lignes(fake):
    return sorted((r["date"], r["exercice"], r["serie"], r.get("exercise_id"))
                  for r in fake.tables.get("history", []))


def _save(client, exo, sets, exo_id="", variant="Standard", date=LUNDI):
    return client.post("/seance/save-exo", data={
        "_csrf": CSRF, "seance_name": "Push", "exo_base": exo, "exo_id": exo_id,
        "variant": variant, "muscle": "Biceps", "date": date.isoformat(),
        "mode": "prefaite", "name": "Push", "sets_json": json.dumps(sets)}, headers=JSON)


def _historique(client, **corps):
    return client.post("/programme/exo/historique", data=json.dumps(corps),
                       content_type="application/json", headers={"X-CSRFToken": CSRF})


# ── Règles d'identité ────────────────────────────────────────────

def test_lidentifiant_est_stable_et_partage_par_un_meme_nom():
    prog = {"A": [{"name": "Développé couché"}, {"name": "Dips"}],
            "B": [{"name": "developpe  COUCHE"}], "_planning": {}}
    ei.assurer_ids(prog)
    a, dips, b = prog["A"][0]["id"], prog["A"][1]["id"], prog["B"][0]["id"]
    assert ei.valide(a) and a == b and a != dips          # casse et accents mis à part
    assert ei.assurer_ids(json.loads(json.dumps(prog))) == prog   # relire ne change rien
    assert "id" not in prog["_planning"]


def test_un_identifiant_illisible_est_remplace():
    prog = {"A": [{"name": "Dips", "id": "<script>"}]}
    ei.assurer_ids(prog)
    assert ei.valide(prog["A"][0]["id"])


def test_un_nouveau_nom_nherite_pas_du_passe_dun_exercice_renomme():
    """« Curl » renommé « Curl marteau » (même exercice) garde l'identifiant
    calculé sur « Curl ». Un nouveau « Curl » en reçoit un autre."""
    id_curl = ei.assurer_ids({"A": [{"name": "Curl"}]})["A"][0]["id"]
    prog = {"A": [{"name": "Curl marteau", "id": id_curl}], "B": [{"name": "Curl"}]}
    ei.assurer_ids(prog)
    assert prog["B"][0]["id"] != id_curl and prog["B"][0]["id"].startswith(id_curl + "-")


def test_valeur_de_serie_avec_variante():
    assert ei.pour_serie("e_0123abcd", "Standard") == "e_0123abcd"
    assert ei.pour_serie("e_0123abcd", "Haltères") == "e_0123abcd~Haltères"
    assert ei.pour_serie("pas-un-id", "Haltères") is None
    assert ei.separer("e_0123abcd~Haltères") == ("e_0123abcd", "Haltères")
    assert ei.separer(None) == (None, "")


def test_les_series_identifiees_safffichent_sous_le_nom_actuel():
    prog = {"A": [{"name": "Curl marteau", "id": "e_0123abcd"}]}
    hist = [{"Exercice": "Curl", "ExoId": "e_0123abcd"},
            {"Exercice": "Curl (Haltères)", "ExoId": "e_0123abcd~Haltères"},
            {"Exercice": "Curl"},                                     # avant la v42 : son nom
            {"Exercice": "Squat", "ExoId": "e_99999999"},             # exercice retiré du programme
            {"Exercice": "CARDIO:Rameur", "ExoId": "e_0123abcd"}]
    noms = [r["Exercice"] for r in ei.afficher_selon_programme(hist, prog)]
    assert noms == ["Curl marteau", "Curl marteau (Haltères)", "Curl", "Squat", "CARDIO:Rameur"]


# ── Programme ────────────────────────────────────────────────────

def test_les_identifiants_existent_des_la_lecture_sans_ecrire(fake_db, monkeypatch):
    from conftest import FakeQuery
    _prog(fake_db)
    ecritures, vraie = [], FakeQuery.execute

    def espion(self):
        if self._table == "programs" and self._op != "select":
            ecritures.append(self._op)
        return vraie(self)
    monkeypatch.setattr(FakeQuery, "execute", espion)
    eid = db.get_prog(USER_ID)["Push"][0]["id"]
    assert ei.valide(eid)
    assert ecritures == []                                       # rien d'écrit
    assert db.get_prog(USER_ID)["Push"][0]["id"] == eid           # même valeur à la relecture
    db.save_prog(USER_ID, db.get_prog(USER_ID))
    assert _blob(fake_db)["Push"][0]["id"] == eid                 # gravé à la sauvegarde


def test_lire_le_programme_pour_lhistorique_ne_change_pas_la_base_de_fusion(fake_db, logged_in):
    from flask import g
    from core import data
    _prog(fake_db)
    with logged_in.application.test_request_context():
        g.user_id = USER_ID
        data.get_prog()
        base = dict(db._bases()[USER_ID])
        fake_db.tables["programs"][0]["version"] = 7               # écriture concurrente
        db.vider_cache()
        data.get_hist()
        assert db._bases()[USER_ID] == base


def test_lediteur_garde_lidentifiant(fake_db, logged_in):
    _prog(fake_db)
    eid = db.get_prog(USER_ID)["Push"][0]["id"]
    seances = {"Push": [{"name": "Curl marteau", "sets": 3, "muscle": "Biceps", "id": eid},
                        {"name": "Dips", "sets": 3, "muscle": "Triceps", "id": "faux"}]}
    r = logged_in.post("/programme/state", data=json.dumps({"seances": seances, "planning": {}}),
                       content_type="application/json", headers={"X-CSRFToken": CSRF})
    assert r.status_code == 200
    push = _blob(fake_db)["Push"]
    assert push[0]["id"] == eid and ei.valide(push[1]["id"]) and push[1]["id"] != "faux"


# ── Séance ───────────────────────────────────────────────────────

def test_une_serie_enregistree_porte_lidentifiant_et_la_variante(fake_db, logged_in):
    _prog(fake_db)
    eid = db.get_prog(USER_ID)["Push"][0]["id"]
    _save(logged_in, "Curl", [{"reps": 10, "poids": 14}], exo_id=eid, variant="Haltères")
    assert _lignes(fake_db) == [(LUNDI.isoformat(), "Curl (Haltères)", 1, f"{eid}~Haltères")]


def test_la_page_de_seance_transmet_lidentifiant(fake_db, logged_in):
    _prog(fake_db)
    eid = db.get_prog(USER_ID)["Push"][0]["id"]
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={LUNDI.isoformat()}").get_data(as_text=True)
    assert f'name="exo_id" value="{eid}"' in html


def test_reecrire_une_seance_passee_apres_renommage_ne_double_rien(fake_db, logged_in):
    """Lundi : 2 séries de « Curl ». L'exercice devient « Curl marteau » (même
    identifiant), puis on corrige la séance de lundi : les séries de lundi
    sont remplacées, pas ajoutées à côté de l'ancien nom."""
    _prog(fake_db)
    eid = db.get_prog(USER_ID)["Push"][0]["id"]
    _save(logged_in, "Curl", [{"reps": 10, "poids": 12}, {"reps": 9, "poids": 12}], exo_id=eid)
    prog = db.get_prog(USER_ID)
    prog["Push"][0]["name"] = "Curl marteau"
    db.save_prog(USER_ID, prog)
    _save(logged_in, "Curl marteau", [{"reps": 11, "poids": 12}], exo_id=eid)
    assert _lignes(fake_db) == [(LUNDI.isoformat(), "Curl marteau", 1, eid)]


def test_le_reset_dun_exercice_vise_aussi_lancien_nom(fake_db, logged_in):
    _prog(fake_db)
    eid = db.get_prog(USER_ID)["Push"][0]["id"]
    _save(logged_in, "Curl", [{"reps": 10, "poids": 12}], exo_id=eid)
    logged_in.post("/seance/reset-exo", data={
        "_csrf": CSRF, "seance_name": "Push", "exo_base": "Curl marteau", "exo_id": eid,
        "variant": "Standard", "date": LUNDI.isoformat(), "mode": "prefaite", "name": "Push"})
    assert _lignes(fake_db) == []


# ── Renommage dans l'éditeur ─────────────────────────────────────

def test_oui_rattache_les_series_anciennes_sans_les_reecrire(fake_db, logged_in):
    from flask import g
    from core import data
    _prog(fake_db)
    dh.replace_exo_rows(USER_ID, LUNDI.isoformat(), "Push", "Curl",
                        [{"Séance": "Push", "Exercice": "Curl", "Série": 1, "Reps": 10, "Poids": 12}])
    dh.replace_exo_rows(USER_ID, LUNDI.isoformat(), "Push", "Curl (Haltères)",
                        [{"Séance": "Push", "Exercice": "Curl (Haltères)", "Série": 1, "Reps": 8, "Poids": 14}])
    prog = db.get_prog(USER_ID)
    eid = prog["Push"][0]["id"]
    prog["Push"][0]["name"] = "Curl marteau"                      # l'éditeur renomme
    db.save_prog(USER_ID, prog)
    d = _historique(logged_in, ancien="Curl", nouveau="Curl marteau", suivre=True, id=eid).get_json()
    assert d == {"ok": True, "deplacees": 2}
    assert _lignes(fake_db) == [(LUNDI.isoformat(), "Curl", 1, eid),
                                (LUNDI.isoformat(), "Curl (Haltères)", 1, f"{eid}~Haltères")]
    with logged_in.application.test_request_context():
        g.user_id = USER_ID
        assert sorted(r["Exercice"] for r in data.get_hist()) == ["Curl marteau", "Curl marteau (Haltères)"]


def test_non_laisse_le_passe_a_lancien_nom(fake_db, logged_in):
    from flask import g
    from core import data
    _prog(fake_db)
    eid = db.get_prog(USER_ID)["Push"][0]["id"]
    _save(logged_in, "Curl", [{"reps": 10, "poids": 12}], exo_id=eid)
    seances = {"Push": [{"name": "Curl incliné", "sets": 3, "muscle": "Biceps"}]}   # l'éditeur retire l'id
    logged_in.post("/programme/state", data=json.dumps({"seances": seances, "planning": {}}),
                   content_type="application/json", headers={"X-CSRFToken": CSRF})
    assert _blob(fake_db)["Push"][0]["id"] != eid
    with logged_in.application.test_request_context():
        g.user_id = USER_ID
        assert [r["Exercice"] for r in data.get_hist()] == ["Curl"]


def test_sans_la_colonne_v42_lapp_fonctionne_comme_avant(fake_db, logged_in, monkeypatch):
    """Base en retard : la colonne est refusée. Lecture et écriture se font
    sans elle, et « oui » renomme les séries comme avant."""
    from conftest import FakeQuery
    vraie_exec = FakeQuery.execute

    def refuse(self):
        sel = getattr(self, "_colonnes", "") or ""
        charge = getattr(self, "_payload", None)
        lignes = charge if isinstance(charge, list) else [charge] if isinstance(charge, dict) else []
        if "exercise_id" in str(sel) or any("exercise_id" in (l or {}) for l in lignes) \
                or any(f[1] == "exercise_id" for f in getattr(self, "_filters", [])):
            raise Exception('column history.exercise_id does not exist')
        return vraie_exec(self)
    monkeypatch.setattr(FakeQuery, "execute", refuse)
    monkeypatch.setitem(dh._COLONNES, "exercise_id", True)
    _prog(fake_db)
    eid = db.get_prog(USER_ID)["Push"][0]["id"]
    assert _save(logged_in, "Curl", [{"reps": 10, "poids": 12}], exo_id=eid).get_json()["ok"]
    assert dh._COLONNES["exercise_id"] is False
    assert _lignes(fake_db) == [(LUNDI.isoformat(), "Curl", 1, None)]
    d = _historique(logged_in, ancien="Curl", nouveau="Curl marteau", suivre=True, id=eid).get_json()
    assert d == {"ok": True, "deplacees": 1}
    assert _lignes(fake_db)[0][1] == "Curl marteau"


def test_lediteur_recoit_lidentifiant_de_chaque_exercice(fake_db, logged_in):
    """Sans lui, chaque sauvegarde de l'éditeur recalculait l'identifiant depuis
    le nom, et un renommage le perdait (trouvé par le test navigateur)."""
    import re
    _prog(fake_db)
    eid = db.get_prog(USER_ID)["Push"][0]["id"]
    html = logged_in.get("/programme").get_data(as_text=True)
    etat = json.loads(re.search(r'<script id="prog-initial" type="application/json">(.*?)</script>',
                                html, re.S).group(1))
    assert etat["seances"]["Push"][0]["id"] == eid
