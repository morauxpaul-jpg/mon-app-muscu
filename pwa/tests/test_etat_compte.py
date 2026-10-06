"""L'état du compte sort de `programs.data` (v47).

Badges, record de série, défis gagnés, « upsell vu », quota de debrief
gratuit, semaine allégée, plats de la semaine, cibles nutrition perso : rien
de tout ça n'est le programme. Tout vivait pourtant dans son blob, et
l'accueil réécrivait le programme entier quand un badge tombait.

Une table, `etat_compte` : une ligne par compte, une colonne typée par
donnée. La conversion se fait à un seul endroit, à la frontière avec la base
(`core/db_etat.py`, appelé par `get_prog` et `save_prog`) : les dizaines de
lecteurs voient toujours `prog["_badges"]`, et une écriture qui passerait par
le programme atterrit quand même dans la table.

Au passage, le « reset soft » est supprimé (archive de l'historique dans le
blob, réinjectée dans Progrès) : aucun compte ne s'en servait, et l'audit du
03/10 le classait parmi les choses à supprimer.
"""
import datetime as dt
from pathlib import Path

import pytest

from conftest import USER_ID, CSRF

import core.db as db
import core.db_etat as de

PWA = Path(__file__).resolve().parents[1]
SQL = PWA / "supabase_schema_v47_etat_compte.sql"
from core.dates import logical_today_paris, monday_of  # noqa: E402
# Relatif à aujourd'hui : la série en cours se compte depuis la semaine du jour.
LUNDI = monday_of(logical_today_paris()) - dt.timedelta(days=7)
VISITE = {"Sec-Fetch-Mode": "navigate"}


@pytest.fixture()
def compte(fake_db):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "version": 1, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_started_at": LUNDI.isoformat(),
    }}).execute()
    for i in range(12):
        fake_db.table("history").insert({
            "user_id": USER_ID, "date": (logical_today_paris() - dt.timedelta(days=i)).isoformat(),
            "semaine": 38, "seance": "Push", "exercice": "Développé couché",
            "muscle": "Pecs", "serie": 1, "reps": 10, "poids": 60.0}).execute()
    return fake_db


@pytest.fixture()
def table_absente(monkeypatch):
    from conftest import FakeQuery
    vraie = FakeQuery.execute

    def refuse(self):
        if self._table == "etat_compte":
            raise Exception("{'code': '42P01', 'message': 'relation \"public.etat_compte\" does not exist'}")
        return vraie(self)
    monkeypatch.setattr(FakeQuery, "execute", refuse)
    de._oublier_absence()
    yield
    de._oublier_absence()


def _blob(fake):
    return fake.tables["programs"][0]["data"]


def _ligne(fake):
    lignes = fake.tables.get("etat_compte", [])
    assert len(lignes) <= 1
    return lignes[0] if lignes else None


# ── Les écritures vont dans la table ─────────────────────────────────────

def test_un_badge_obtenu_va_dans_la_table(compte, logged_in):
    assert logged_in.get("/accueil", headers=VISITE).status_code == 200
    ligne = _ligne(compte)
    assert ligne and "first_session" in ligne["badges"]
    assert "_badges" not in _blob(compte)


def test_le_record_de_serie_va_dans_la_table(compte, logged_in):
    logged_in.get("/accueil", headers=VISITE)
    assert _ligne(compte)["record_serie"] >= 1
    assert "_streak_record" not in _blob(compte)


def test_la_semaine_allegee_va_dans_la_table(compte, logged_in):
    logged_in.post("/accueil/decharge", data={"_csrf": CSRF, "choix": "appliquer"},
                   headers={"X-CSRFToken": CSRF})
    assert _ligne(compte)["decharge_semaine"]
    assert "_decharge_semaine" not in _blob(compte)
    assert db.get_prog(USER_ID)["_decharge_semaine"] == _ligne(compte)["decharge_semaine"]
    logged_in.post("/accueil/decharge", data={"_csrf": CSRF, "choix": "annuler"},
                   headers={"X-CSRFToken": CSRF})
    assert _ligne(compte)["decharge_semaine"] is None
    assert "_decharge_semaine" not in db.get_prog(USER_ID)


def test_une_cible_nutrition_perso_va_dans_la_table(compte):
    prog = db.get_prog(USER_ID)
    prog["_nutrition"] = {"calories_custom": 2400, "cycle": False}
    db.save_prog(USER_ID, prog)
    assert _ligne(compte)["nutrition_perso"] == {"calories_custom": 2400, "cycle": False}
    assert "_nutrition" not in _blob(compte)
    assert db.get_prog(USER_ID)["_nutrition"]["calories_custom"] == 2400


def test_les_plats_de_la_semaine_vont_dans_la_table(compte):
    prog = db.get_prog(USER_ID)
    prog["_meal_plan"] = {"Lundi": [{"nom": "Riz poulet"}]}
    db.save_prog(USER_ID, prog)
    assert _ligne(compte)["plats_semaine"] == {"Lundi": [{"nom": "Riz poulet"}]}
    prog = db.get_prog(USER_ID)
    prog.pop("_meal_plan")
    db.save_prog(USER_ID, prog)
    assert _ligne(compte)["plats_semaine"] is None


def test_une_sauvegarde_sans_changement_nest_pas_une_ecriture(compte):
    db.save_prog(USER_ID, db.get_prog(USER_ID))
    assert _ligne(compte) is None


def test_le_programme_garde_ses_propres_cles(compte):
    prog = db.get_prog(USER_ID)
    prog["_badges"] = ["first_session"]
    db.save_prog(USER_ID, prog)
    blob = _blob(compte)
    assert blob["_planning"] == {"Lundi": "Push"} and blob["Push"]
    assert "_badges" not in blob


def test_une_valeur_bancale_est_ramenee_comme_dans_la_migration():
    """Mêmes règles que la v47 : la table refuserait un compteur négatif."""
    lu = de._depuis_prog({"_streak_record": -3, "_decharge_ignoree": 139.0,
                          "_badges": "pas une liste", "_upsell_seen": True})
    assert (lu["record_serie"], lu["decharge_ignoree"], lu["badges"], lu["upsell_vu"]) == (0, 139, [], True)


# ── Restes d'avant la migration, et base en retard ───────────────────────

def test_un_reste_du_programme_se_lit_et_part_a_la_premiere_sauvegarde(compte):
    _blob(compte)["_badges"] = ["first_session"]
    _blob(compte)["_streak_record"] = 4
    prog = db.get_prog(USER_ID)
    assert prog["_badges"] == ["first_session"] and prog["_streak_record"] == 4
    db.save_prog(USER_ID, prog)
    assert _ligne(compte)["badges"] == ["first_session"]
    assert _ligne(compte)["record_serie"] == 4
    assert "_badges" not in _blob(compte) and "_streak_record" not in _blob(compte)


def test_la_ligne_prime_sur_un_reste_du_programme(compte):
    _blob(compte)["_streak_record"] = 2
    compte.table("etat_compte").insert({"user_id": USER_ID, **de._vide(), "record_serie": 9}).execute()
    db.vider_cache()
    assert db.get_prog(USER_ID)["_streak_record"] == 9


def test_sans_la_table_le_programme_sert_comme_avant(compte, logged_in, table_absente):
    logged_in.get("/accueil", headers=VISITE)
    assert "first_session" in _blob(compte)["_badges"]
    assert "etat_compte" not in compte.tables


def test_la_table_est_reessayee_apres_une_absence(fake_db, monkeypatch):
    de._marquer_absente()
    assert de._disponible() is False
    monkeypatch.setattr(de, "_absente_depuis", de._absente_depuis - de.REESSAI - 1)
    assert de._disponible() is True


def test_supprimer_le_compte_efface_son_etat(compte):
    prog = db.get_prog(USER_ID)
    prog["_streak_record"] = 3
    db.save_prog(USER_ID, prog)
    db.delete_user_account(USER_ID)
    assert compte.tables["etat_compte"] == []


# ── Le reset soft n'existe plus ──────────────────────────────────────────

def test_le_reset_soft_est_retire(compte, logged_in):
    r = logged_in.post("/gestion/reset-soft", data={"_csrf": CSRF, "confirm": "yes"},
                       headers={"X-CSRFToken": CSRF})
    assert r.status_code in (404, 405)
    assert len(compte.tables["history"]) == 12
    html = logged_in.get("/gestion").get_data(as_text=True)
    assert "reset-soft" not in html


def test_plus_rien_ne_lit_larchive_heritee():
    for p in list((PWA / "routes").glob("*.py")) + list((PWA / "templates").glob("*.html")):
        texte = p.read_text(encoding="utf-8")
        assert "_archive" not in texte and "_legacy_volume" not in texte, p.name


# ── La migration ─────────────────────────────────────────────────────────

def test_la_migration_cree_la_table_fermee_et_vide_le_programme():
    import re
    sql = re.sub(r"--[^\n]*", "", SQL.read_text(encoding="utf-8").lower())
    assert "create table if not exists public.etat_compte" in sql
    assert "references auth.users(id) on delete cascade" in sql
    for col in de.COLONNES:
        assert col in sql
    assert "enable row level security" in sql
    assert "revoke all on public.etat_compte from anon, authenticated" in sql
    for cle in de.CLES_BLOB:
        assert f"'{cle}'" in sql
    assert "'_archive'" in sql and "'_legacy_volume'" in sql
    assert "version = version + 1" in sql


def test_deux_requetes_ne_secrasent_pas_leur_etat(compte):
    """A lit, B lit, A grave un badge, B change ses plats avec son état lu
    avant : le badge de A reste. Sans ça, la table aurait réintroduit la
    perte d'écriture que le verrou du programme empêche (audit du 30/09, I7)."""
    import app as appmod
    a, b = appmod.app.app_context(), appmod.app.app_context()
    a.push(); prog_a = db.get_prog(USER_ID); a.pop()
    b.push(); prog_b = db.get_prog(USER_ID); b.pop()
    a.push(); prog_a["_badges"] = ["first_session"]; db.save_prog(USER_ID, prog_a); a.pop()
    b.push(); prog_b["_meal_plan"] = {"Lundi": []}; db.save_prog(USER_ID, prog_b); b.pop()
    ligne = _ligne(compte)
    assert ligne["badges"] == ["first_session"]
    assert ligne["plats_semaine"] == {"Lundi": []}
