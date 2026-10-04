"""Séries d'échauffement enregistrées à part (retour du 04/10).

Une série d'échauffement compte dans ce qu'on a soulevé, mais pas dans le
travail : la noter comme une série normale fausserait la suggestion de charge,
les séries par muscle et les records en répétitions. Elle porte
`history.type_serie = 'echauffement'` (migration v43) ; `db.get_hist()` ne la
renvoie que sur demande, si bien que tous les calculs l'ignorent d'office.
"""
import datetime as dt
import json

from conftest import CSRF, USER_ID
from core import db
from core.hist import TYPE_ECHAUFFEMENT
from core.seance_saisie import _rows_from_sets
import core.db_historique as dh

LUNDI = dt.date(2026, 9, 14)
JSON = {"Accept": "application/json", "X-CSRFToken": CSRF}


def _prog(fake):
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_started_at": LUNDI.isoformat()}}).execute()


def _save(client, sets, date=LUNDI):
    return client.post("/seance/save-exo", data={
        "_csrf": CSRF, "seance_name": "Push", "exo_base": "Développé couché",
        "variant": "Standard", "muscle": "Pecs", "date": date.isoformat(),
        "mode": "prefaite", "name": "Push", "sets_json": json.dumps(sets)}, headers=JSON)


ECH = {"reps": 10, "poids": 20, "type": TYPE_ECHAUFFEMENT}


def test_la_saisie_marque_lechauffement_mais_pas_une_serie_passee():
    rows = _rows_from_sets([ECH, {"reps": 8, "poids": 60}, {"reps": 0, "type": TYPE_ECHAUFFEMENT}],
                           semaine=1, seance="Push", exo_final="DC", muscle="Pecs",
                           date_str="2026-09-14", is_bw=False)
    assert [r.get("Type") for r in rows] == [TYPE_ECHAUFFEMENT, None, None]


def test_lhistorique_ne_renvoie_lechauffement_que_sur_demande(fake_db):
    dh.replace_exo_rows(USER_ID, LUNDI.isoformat(), "Push", "Développé couché", [
        {"Séance": "Push", "Exercice": "Développé couché", "Série": 1, "Reps": 10, "Poids": 20,
         "Type": TYPE_ECHAUFFEMENT},
        {"Séance": "Push", "Exercice": "Développé couché", "Série": 2, "Reps": 8, "Poids": 60}])
    assert [r["type_serie"] for r in sorted(fake_db.tables["history"], key=lambda r: r["serie"])] \
        == [TYPE_ECHAUFFEMENT, None]
    assert [r["Poids"] for r in db.get_hist(USER_ID)] == [60]
    assert sorted(r["Poids"] for r in db.get_hist(USER_ID, echauffement=True)) == [20, 60]


def test_enregistrer_avec_un_echauffement(fake_db, logged_in):
    """Record, résumé et « exercice fait » ne voient que le travail ; le
    volume d'échauffement revient à part."""
    _prog(fake_db)
    d = _save(logged_in, [ECH]).get_json()
    assert d["ok"] and d["completed"] is False          # que de l'échauffement : pas fait
    assert d["volume"] == 0 and d["volume_echauffement"] == 200
    d = _save(logged_in, [ECH, {"reps": 8, "poids": 60}]).get_json()
    assert d["completed"] is True
    assert d["last_summary"] == "60kg × 8"
    assert d["pr"] and d["pr"]["value"] == 60
    assert d["volume"] == 480 and d["volume_echauffement"] == 200


def test_la_carte_garde_lechauffement_et_le_reenregistrer_ne_lefface_pas(fake_db, logged_in):
    _prog(fake_db)
    _save(logged_in, [ECH, {"reps": 8, "poids": 60}])
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={LUNDI.isoformat()}").get_data(as_text=True)
    assert '"type": "echauffement"' in html and "+200 échauff." in html
    assert '"echauffements": true' in html
    _save(logged_in, [ECH, {"reps": 9, "poids": 60}])     # correction de la série de travail
    assert sorted((r["serie"], r["type_serie"]) for r in fake_db.tables["history"]) \
        == [(1, TYPE_ECHAUFFEMENT), (2, None)]


def test_la_suggestion_et_le_record_ignorent_lechauffement(fake_db, logged_in):
    """Un échauffement à 20 kg × 15 ne devient ni « record de reps » ni la
    base de la prochaine suggestion."""
    _prog(fake_db)
    _save(logged_in, [{"reps": 15, "poids": 20, "type": TYPE_ECHAUFFEMENT}, {"reps": 8, "poids": 60}])
    from core.seance_historique import _best_record, _last_session_sets
    hist = db.get_hist(USER_ID)
    assert _best_record(hist, "Développé couché", False)["weight"] == 60
    assert [s["poids"] for s in _last_session_sets(hist, "Développé couché", "Push", "2026-09-21")] == [60]


def test_lexport_emporte_les_echauffements(fake_db, logged_in):
    _prog(fake_db)
    _save(logged_in, [ECH, {"reps": 8, "poids": 60}])
    data = json.loads(logged_in.get("/gestion/export").data)
    assert sorted(r.get("Type") or "" for r in data["historique"]) == ["", TYPE_ECHAUFFEMENT]


def test_sans_la_v43_un_echauffement_ne_devient_jamais_du_travail(fake_db, logged_in, monkeypatch):
    """Base en retard : la colonne est refusée. La case n'est pas proposée et
    un échauffement envoyé quand même n'est pas écrit comme une série normale."""
    from conftest import FakeQuery
    vraie = FakeQuery.execute

    def refuse(self):
        charge = self._payload if isinstance(self._payload, list) else [self._payload] if self._payload else []
        if "type_serie" in str(self._colonnes or "") or any("type_serie" in (l or {}) for l in charge):
            raise Exception("column history.type_serie does not exist")
        return vraie(self)
    monkeypatch.setattr(FakeQuery, "execute", refuse)
    monkeypatch.setitem(dh._COLONNES, "type_serie", True)
    _prog(fake_db)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={LUNDI.isoformat()}").get_data(as_text=True)
    assert '"echauffements": false' in html
    _save(logged_in, [ECH, {"reps": 8, "poids": 60}])
    assert [(r["serie"], r["poids"]) for r in fake_db.tables["history"]] == [(2, 60.0)]
