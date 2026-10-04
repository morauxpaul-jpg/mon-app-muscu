"""Une série = une ligne (migration v41).

L'index unique (user, date, séance, exercice, série) protège la base, et
l'app écrit par clé : une écriture rejouée — requête abandonnée par le
téléphone puis renvoyée, import relancé après une coupure — réécrit les mêmes
lignes au lieu d'en ajouter (audit du 03/10, I7). La fausse base applique le
même index (`tests/conftest.py`, `FakeQuery.UNIQUE`).
"""
import pytest

from conftest import USER_ID
from core import db_historique as dh
from core import db_historique_lots as lots
from core import db_renommage as ren

D = "2026-10-01"


def _series(n, exo="Développé couché", seance="Push", date=D, poids=100.0):
    return [{"Séance": seance, "Exercice": exo, "Série": k, "Reps": 5, "Poids": poids, "Date": date}
            for k in range(1, n + 1)]


def _lignes(fake, exo=None):
    return sorted(((r["date"], r["seance"], r["exercice"], r["serie"], r["poids"])
                   for r in fake.tables.get("history", []) if exo is None or r["exercice"] == exo))


@pytest.fixture(autouse=True)
def index_present():
    dh._unicite = True
    yield
    dh._unicite = True


def test_la_base_refuse_une_serie_en_double(fake_db):
    row = {"user_id": USER_ID, "date": D, "seance": "Push", "exercice": "Dips", "serie": 1}
    fake_db.table("history").insert(row).execute()
    with pytest.raises(Exception, match="23505"):
        fake_db.table("history").insert(dict(row)).execute()


def test_un_remplacement_rejoue_ne_double_rien_et_garde_les_ids(fake_db):
    dh.replace_exo_rows(USER_ID, D, "Push", "Développé couché", _series(3))
    ids = sorted(r["id"] for r in fake_db.tables["history"])
    dh.replace_exo_rows(USER_ID, D, "Push", "Développé couché", _series(3, poids=102.5))
    assert len(fake_db.tables["history"]) == 3
    assert sorted(r["id"] for r in fake_db.tables["history"]) == ids   # mis à jour sur place
    assert {r["poids"] for r in fake_db.tables["history"]} == {102.5}


def test_un_remplacement_plus_court_retire_les_series_en_trop(fake_db):
    dh.replace_exo_rows(USER_ID, D, "Push", "Développé couché", _series(4))
    dh.replace_exo_rows(USER_ID, D, "Push", "Développé couché", _series(2))
    assert [l[3] for l in _lignes(fake_db)] == [1, 2]


def test_sans_lindex_v41_lancienne_ecriture_prend_le_relais(fake_db, monkeypatch):
    import conftest
    vrai = conftest.FakeQuery.execute

    def execute(self):
        if self._op == "upsert" and self._table == "history":
            raise Exception("{'code': '42P10', 'message': 'there is no unique or exclusion "
                            "constraint matching the ON CONFLICT specification'}")
        return vrai(self)
    monkeypatch.setattr(conftest.FakeQuery, "execute", execute)
    monkeypatch.setattr(conftest.FakeQuery, "UNIQUE", {})
    dh.replace_exo_rows(USER_ID, D, "Push", "Développé couché", _series(3))
    dh.replace_exo_rows(USER_ID, D, "Push", "Développé couché", _series(3))
    assert dh._unicite is False
    assert len(fake_db.tables["history"]) == 3


def test_restaurer_deux_fois_la_meme_sauvegarde_ne_double_rien(fake_db):
    lignes = _series(3) + _series(2, exo="Dips")
    lots.save_hist(USER_ID, lignes)
    lots.save_hist(USER_ID, lignes)
    assert len(fake_db.tables["history"]) == 5


def test_une_sauvegarde_qui_numerote_deux_fois_la_serie_1_ne_perd_rien(fake_db):
    doublee = _series(1) + _series(1, poids=90.0)
    lots.save_hist(USER_ID, doublee)
    assert [(l[3], l[4]) for l in _lignes(fake_db)] == [(1, 100.0), (2, 90.0)]


def test_un_import_relance_ne_double_rien_et_respecte_lexistant(fake_db):
    dh.replace_exo_rows(USER_ID, D, "Push", "Développé couché", _series(1, poids=120.0))
    lots.ajouter_lignes(USER_ID, _series(3))
    lots.ajouter_lignes(USER_ID, _series(3))
    lignes = _lignes(fake_db)
    assert len(lignes) == 3
    assert lignes[0][4] == 120.0     # la série déjà saisie n'est pas écrasée par l'import


def test_un_ajout_concurrent_reprend_le_numero_suivant(fake_db, monkeypatch):
    dh.append_exo_rows(USER_ID, D, "Push", "CARDIO:Rameur", _series(1, exo="CARDIO:Rameur"))
    vrai = dh._append_une_fois
    appels = []

    def course(*a, **k):
        appels.append(1)
        if len(appels) == 1:   # une autre instance vient de prendre la série 2
            fake_db.table("history").insert({"user_id": USER_ID, "date": D, "seance": "Push",
                                             "exercice": "CARDIO:Rameur", "serie": 2}).execute()
            raise Exception("{'code': '23505', 'message': 'duplicate key'}")
        return vrai(*a, **k)
    monkeypatch.setattr(dh, "_append_une_fois", course)
    depart = dh.append_exo_rows(USER_ID, D, "Push", "CARDIO:Rameur", _series(1, exo="CARDIO:Rameur"))
    assert depart == 3 and len(appels) == 2


def test_fusionner_deux_exercices_le_meme_jour_ne_perd_aucune_serie(fake_db):
    dh.replace_exo_rows(USER_ID, D, "Push", "Squat", _series(2, exo="Squat"))
    dh.replace_exo_rows(USER_ID, D, "Push", "Squat barre", _series(2, exo="Squat barre", poids=80.0))
    n = ren.rename_exercise_rows(USER_ID, ["Squat"], "Squat barre")
    assert n == 2
    lignes = _lignes(fake_db)
    assert {l[2] for l in lignes} == {"Squat barre"}
    assert [l[3] for l in lignes] == [1, 2, 3, 4]


def test_renommer_une_seance_en_collision_ne_perd_rien(fake_db):
    dh.replace_exo_rows(USER_ID, D, "Push A", "Dips", _series(1, exo="Dips", seance="Push A"))
    dh.replace_exo_rows(USER_ID, D, "Push", "Dips", _series(1, exo="Dips"))
    ren.rename_seance_rows(USER_ID, "Push A", "Push")
    assert [(l[1], l[3]) for l in _lignes(fake_db)] == [("Push", 1), ("Push", 2)]


def test_un_renommage_sans_collision_reste_un_seul_update(fake_db, monkeypatch):
    dh.replace_exo_rows(USER_ID, D, "Push", "Squat", _series(3, exo="Squat"))
    appels = []
    monkeypatch.setattr(ren, "_deplacer_ligne_a_ligne", lambda *a: appels.append(a) or 0)
    assert ren.rename_exercise_rows(USER_ID, ["Squat"], "Squat arrière") == 3
    assert appels == []


# ── Renommer dans l'éditeur : l'historique suit si on le demande (I12) ──

def _post(client, **corps):
    import json
    from conftest import CSRF
    return client.post("/programme/exo/historique", data=json.dumps(corps),
                       content_type="application/json", headers={"X-CSRFToken": CSRF})


def test_lediteur_compte_les_series_a_emmener(fake_db, logged_in):
    dh.replace_exo_rows(USER_ID, D, "Push", "Tirage horizontal", _series(3, exo="Tirage horizontal"))
    d = _post(logged_in, ancien="Tirage horizontal", nouveau="Tirage horizontal prise neutre").get_json()
    assert d == {"ok": True, "series": 3}
    assert {l[2] for l in _lignes(fake_db)} == {"Tirage horizontal"}   # compter ne déplace rien


def test_oui_emmene_les_series_sous_le_nouveau_nom(fake_db, logged_in):
    dh.replace_exo_rows(USER_ID, D, "Push", "Devlopé couché", _series(2, exo="Devlopé couché"))
    d = _post(logged_in, ancien="Devlopé couché", nouveau="Développé couché", suivre=True).get_json()
    assert d == {"ok": True, "deplacees": 2}
    assert {l[2] for l in _lignes(fake_db)} == {"Développé couché"}


def test_noms_invalides_refuses(fake_db, logged_in):
    assert _post(logged_in, ancien="Dips", nouveau="Dips").status_code == 400
    assert _post(logged_in, ancien="", nouveau="Dips").status_code == 400
