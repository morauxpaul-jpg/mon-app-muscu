"""Les calques du jour sortent de `programs.data` (v46).

Les quatre calques d'une séance — exercices ajoutés à la volée, brouillon de
séance libre, échanges du jour, ordre des cartes — vivaient dans le blob du
programme, indexés par « séance|date ». Ajouter un exercice, en échanger un,
glisser une carte : chaque geste relisait et réécrivait le programme entier,
passait par son verrou optimiste, et pouvait entrer en conflit avec une
modification du programme faite dans un autre onglet.

Ils ont maintenant leur table, `calques_seance` : une ligne par séance et par
date, une colonne par calque. Le programme n'est plus touché.
"""
import datetime as dt
from pathlib import Path

import pytest

from conftest import USER_ID, CSRF
from core.dates import logical_today_paris

import core.db as db
import core.db_calques as dc

PWA = Path(__file__).resolve().parents[1]
SQL = PWA / "supabase_schema_v46_calques_seance.sql"
JOUR = logical_today_paris().isoformat()


@pytest.fixture()
def compte(fake_db):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"},
                 {"name": "Écarté poulie", "sets": 3, "muscle": "Pecs"}],
        "_planning": {}, "_started_at": JOUR,
    }}).execute()
    return fake_db


@pytest.fixture()
def table_absente(monkeypatch):
    from conftest import FakeQuery
    vraie = FakeQuery.execute

    def refuse(self):
        if self._table == "calques_seance":
            raise Exception("{'code': '42P01', 'message': 'relation \"public.calques_seance\" does not exist'}")
        return vraie(self)
    monkeypatch.setattr(FakeQuery, "execute", refuse)
    dc._oublier_absence()
    yield
    dc._oublier_absence()


def _blob(fake):
    return fake.tables["programs"][0]["data"]


def _version(fake):
    return fake.tables["programs"][0].get("version")


def _lignes(fake):
    return fake.tables.get("calques_seance", [])


def _post(client, url, **data):
    return client.post(url, data={"_csrf": CSRF, **data}, headers={"X-CSRFToken": CSRF})


def _ajouter(client, nom, mode="prefaite", seance="Push"):
    return _post(client, "/seance/add-extra", mode=mode, name=seance, seance_name=seance,
                 date=JOUR, exo_name=nom, muscle="Biceps", sets_count="3")


# ── Chaque geste écrit sa ligne, pas le programme ────────────────────────

def test_ajouter_un_exercice_ecrit_dans_la_table(compte, logged_in):
    v = _version(compte)
    _ajouter(logged_in, "Curl")
    (ligne,) = _lignes(compte)
    assert (ligne["seance"], ligne["date"]) == ("Push", JOUR)
    assert [e["name"] for e in ligne["extras"]] == ["Curl"]
    assert "_extras" not in _blob(compte)
    assert _version(compte) == v, "le programme ne doit pas être réécrit"


def test_deux_ajouts_sappendent(compte, logged_in):
    _ajouter(logged_in, "Curl")
    _ajouter(logged_in, "Dips")
    assert [e["name"] for e in _lignes(compte)[0]["extras"]] == ["Curl", "Dips"]


def test_retirer_un_exercice_ajoute(compte, logged_in):
    _ajouter(logged_in, "Curl")
    _ajouter(logged_in, "Dips")
    _post(logged_in, "/seance/remove-extra", mode="prefaite", name="Push", seance_name="Push",
          date=JOUR, exo_name="Curl")
    assert [e["name"] for e in _lignes(compte)[0]["extras"]] == ["Dips"]


def test_le_brouillon_libre_va_dans_sa_colonne(compte, logged_in):
    _ajouter(logged_in, "Squat", mode="libre", seance="Séance Libre")
    (ligne,) = _lignes(compte)
    assert [e["name"] for e in ligne["brouillon"]] == ["Squat"]
    assert ligne["extras"] == []
    assert "_libre_draft" not in _blob(compte)


def test_echanger_un_exercice(compte, logged_in):
    _post(logged_in, "/seance/substitute", seance_name="Push", date=JOUR,
          exo_name="Écarté poulie", vers="Pec deck", mode="prefaite", name="Push")
    (ligne,) = _lignes(compte)
    assert list(ligne["substituts"].values()) == ["Pec deck"]
    assert "_substituts" not in _blob(compte)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={JOUR}").get_data(as_text=True)
    assert "Pec deck" in html


def test_revenir_a_loriginal_efface_la_ligne_vide(compte, logged_in):
    _post(logged_in, "/seance/substitute", seance_name="Push", date=JOUR,
          exo_name="Écarté poulie", vers="Pec deck", mode="prefaite", name="Push")
    _post(logged_in, "/seance/substitute", seance_name="Push", date=JOUR,
          exo_name="Écarté poulie", vers="", mode="prefaite", name="Push")
    assert _lignes(compte) == []


def test_reordonner_les_cartes(compte, logged_in):
    logged_in.post("/seance/reorder", json={"seance_name": "Push", "date": JOUR,
                                            "order": ["Écarté poulie", "Développé couché"]},
                   headers={"X-CSRFToken": CSRF})
    (ligne,) = _lignes(compte)
    assert ligne["ordre"] == ["Écarté poulie", "Développé couché"]
    assert "_seance_order" not in _blob(compte)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={JOUR}").get_data(as_text=True)
    assert html.index("Écarté poulie") < html.index("Développé couché")


def test_la_page_de_seance_montre_lexercice_ajoute(compte, logged_in):
    _ajouter(logged_in, "Curl marteau")
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={JOUR}").get_data(as_text=True)
    assert "Curl marteau" in html


# ── Fin de séance, purge, renommage, reset, suppression ──────────────────

def test_terminer_efface_les_calques_du_jour(compte, logged_in):
    _ajouter(logged_in, "Curl")
    _post(logged_in, "/seance/finish", mode="prefaite", seance_name="Push", date=JOUR)
    assert _lignes(compte) == []


def test_une_seance_abandonnee_est_purgee_apres_84_jours(compte, logged_in):
    vieux = (logical_today_paris() - dt.timedelta(days=100)).isoformat()
    recent = (logical_today_paris() - dt.timedelta(days=10)).isoformat()
    for d in (vieux, recent):
        compte.table("calques_seance").insert({"user_id": USER_ID, "seance": "Pull", "date": d,
                                               **dc._vide(), "ordre": ["Rowing"]}).execute()
    _post(logged_in, "/seance/finish", mode="prefaite", seance_name="Push", date=JOUR)
    assert [l["date"] for l in _lignes(compte)] == [recent]


def test_renommer_la_seance_suit_les_calques(compte, logged_in):
    _ajouter(logged_in, "Curl")
    logged_in.post("/programme/seance/rename", json={"name": "Push", "new_name": "Poussée"},
                   headers={"X-CSRFToken": CSRF})
    assert [l["seance"] for l in _lignes(compte)] == ["Poussée"]


def test_le_reset_total_efface_les_calques(compte, logged_in):
    _ajouter(logged_in, "Curl")
    _post(logged_in, "/gestion/reset-total", confirm="yes")
    assert _lignes(compte) == []


def test_supprimer_le_compte_efface_les_calques(compte):
    db.ecrire_calque(USER_ID, "Push", JOUR, "ordre", ["A"])
    db.delete_user_account(USER_ID)
    assert _lignes(compte) == []


# ── Base en retard : le programme, comme avant ───────────────────────────

def test_sans_la_table_le_programme_sert_comme_avant(compte, logged_in, table_absente):
    _ajouter(logged_in, "Curl")
    assert [e["name"] for e in _blob(compte)["_extras"][f"Push|{JOUR}"]] == ["Curl"]
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={JOUR}").get_data(as_text=True)
    assert "Curl" in html
    _post(logged_in, "/seance/finish", mode="prefaite", seance_name="Push", date=JOUR)
    assert f"Push|{JOUR}" not in (_blob(compte).get("_extras") or {})


def test_un_reste_du_programme_se_lit_tant_quil_ny_a_pas_de_ligne(compte, logged_in):
    """Entre le déploiement et la migration, l'exercice ajouté ce matin
    reste à l'écran."""
    compte.tables["programs"][0]["data"]["_extras"] = {
        f"Push|{JOUR}": [{"name": "Curl ancien", "muscle": "Biceps", "sets": 3}]}
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={JOUR}").get_data(as_text=True)
    assert "Curl ancien" in html


def test_la_table_est_reessayee_apres_une_absence(fake_db, monkeypatch):
    dc._marquer_absente()
    assert dc._disponible() is False
    monkeypatch.setattr(dc, "_absente_depuis", dc._absente_depuis - dc.REESSAI - 1)
    assert dc._disponible() is True


# ── La migration ─────────────────────────────────────────────────────────

def test_la_migration_cree_la_table_fermee_et_vide_le_programme():
    import re
    sql = re.sub(r"--[^\n]*", "", SQL.read_text(encoding="utf-8").lower())
    assert "create table if not exists public.calques_seance" in sql
    assert "references auth.users(id) on delete cascade" in sql
    assert "primary key (user_id, seance, date)" in sql
    for col in ("extras", "brouillon", "substituts", "ordre"):
        assert col in sql
    assert "enable row level security" in sql
    assert "revoke all on public.calques_seance from anon, authenticated" in sql
    for cle in ("_extras", "_libre_draft", "_substituts", "_seance_order", "_session_notes"):
        assert f"'{cle}'" in sql
    assert "insert into public.session_notes" in sql
    assert "version = version + 1" in sql


def test_une_date_illisible_dans_ladresse_ne_casse_pas_la_page(compte, logged_in):
    r = logged_in.get("/seance?mode=prefaite&name=Push&date=bof")
    assert r.status_code == 200
