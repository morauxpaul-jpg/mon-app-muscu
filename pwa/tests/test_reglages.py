"""Les réglages sortent de `programs.data` (v45).

Ils vivaient dans `programs.data['_settings']`, un sac de clés au milieu du
programme : non typés, sans valeur par défaut en base, et le cron des rappels
devait relire le blob entier de chaque abonné pour savoir à quelle heure
écrire. Ils ont maintenant leur table, `reglages`, une colonne typée par
réglage.

En les déplaçant, quatre réglages de la page Gestion se sont révélés sans
aucun effet : « Replier automatiquement », « Afficher l'estimation 1RM »,
« Animations du thème » (vendu comme avantage PRO) et « Nombre de semaines
précédentes affichées ». Rien ne les lisait. Ils sont retirés.
"""
from pathlib import Path

import pytest

from conftest import USER_ID, CSRF
from core.dates import DAYS_FR, logical_today_paris

import core.db as db
import core.db_reglages as dr

PWA = Path(__file__).resolve().parents[1]
SQL = PWA / "supabase_schema_v45_reglages.sql"
TODAY = logical_today_paris()
JOUR = DAYS_FR[TODAY.weekday()]
MORTS = ("auto_collapse", "show_1rm", "theme_animations", "show_previous_weeks")


def _prog(fake, settings=None, user_id=USER_ID):
    data = {"Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
            "_planning": {JOUR: "Push"}, "_started_at": TODAY.isoformat()}
    if settings is not None:
        data["_settings"] = settings
    fake.table("programs").insert({"user_id": user_id, "data": data}).execute()


def _envoyer(client, **champs):
    data = {"_csrf": CSRF, "auto_rest_timer": "on", "show_rpe": "on",
            "show_overload_hint": "on", "auto_prefill_weight": "on",
            "notifications": "on", "reminder_hour": "18", "recap_hebdo": "on"}
    data.update(champs)
    return client.post("/gestion/settings", data={k: v for k, v in data.items() if v is not None})


@pytest.fixture()
def table_absente(monkeypatch):
    """Base en retard : la table `reglages` n'existe pas encore."""
    from conftest import FakeQuery
    vraie = FakeQuery.execute

    def refuse(self):
        if self._table == "reglages":
            raise Exception("{'code': '42P01', 'message': 'relation \"public.reglages\" does not exist'}")
        return vraie(self)
    monkeypatch.setattr(FakeQuery, "execute", refuse)
    dr._oublier_absence()
    yield
    dr._oublier_absence()


# ── Les réglages sans effet ──────────────────────────────────────────────

def test_gestion_ne_propose_plus_de_reglage_sans_effet(fake_db, logged_in):
    _prog(fake_db)
    html = logged_in.get("/gestion").get_data(as_text=True)
    for nom in MORTS:
        assert f'name="{nom}"' not in html, nom
    assert "Animations du thème" not in html


def test_les_reglages_sans_effet_ne_sont_lus_nulle_part():
    """S'ils revenaient dans le code, il faudrait qu'ils servent à quelque
    chose — ce test oblige à le décider, pas à les oublier."""
    for p in list((PWA / "routes").glob("*.py")) + list((PWA / "core").glob("*.py")) \
            + list((PWA / "templates").glob("*.html")):
        texte = p.read_text(encoding="utf-8")
        for nom in MORTS:
            assert nom not in texte, f"{nom} dans {p.name}"


# ── Écriture ─────────────────────────────────────────────────────────────

def test_enregistrer_ecrit_dans_la_table_et_pas_dans_le_programme(fake_db, logged_in):
    _prog(fake_db)
    _envoyer(logged_in, reminder_hour="7", show_rpe=None, recap_hebdo=None)
    (ligne,) = fake_db.tables["reglages"]
    assert ligne["user_id"] == USER_ID
    assert (ligne["reminder_hour"], ligne["show_rpe"], ligne["recap_hebdo"]) == (7, False, False)
    assert ligne["notifications"] is True
    assert set(ligne) >= set(dr.DEFAUTS)
    assert not set(ligne) & set(MORTS)
    assert "_settings" not in fake_db.tables["programs"][0]["data"]


def test_un_second_enregistrement_remplace_le_premier(fake_db, logged_in):
    _prog(fake_db)
    _envoyer(logged_in, reminder_hour="7")
    _envoyer(logged_in, reminder_hour="20")
    assert [l["reminder_hour"] for l in fake_db.tables["reglages"]] == [20]


def test_lheure_reste_bornee(fake_db, logged_in):
    _prog(fake_db)
    _envoyer(logged_in, reminder_hour="3")
    assert fake_db.tables["reglages"][0]["reminder_hour"] == 6


def test_accepter_les_notifications_ecrit_dans_la_table(fake_db, logged_in):
    _prog(fake_db)
    logged_in.post("/gestion/notifications", json={"enabled": True},
                   headers={"X-CSRFToken": CSRF})
    assert fake_db.tables["reglages"][0]["notifications"] is True
    assert "_settings" not in fake_db.tables["programs"][0]["data"]


# ── Lecture ──────────────────────────────────────────────────────────────

def test_la_page_gestion_lit_la_table(fake_db, logged_in):
    _prog(fake_db, settings={"notifications": True, "reminder_hour": 9})
    fake_db.table("reglages").insert({"user_id": USER_ID, **dr.DEFAUTS,
                                      "notifications": True, "reminder_hour": 7}).execute()
    html = logged_in.get("/gestion").get_data(as_text=True)
    assert '<option value="7" selected>07 h 00</option>' in html


def test_la_seance_applique_les_reglages_de_la_table(fake_db, logged_in):
    _prog(fake_db)
    fake_db.table("reglages").insert({"user_id": USER_ID, **dr.DEFAUTS,
                                      "show_rpe": False, "auto_rest_timer": False}).execute()
    html = logged_in.get("/seance?mode=prefaite&name=Push").get_data(as_text=True)
    assert '"autoRestTimer": false' in html and '"showRpe": false' in html


def test_sans_ligne_les_valeurs_par_defaut(fake_db):
    assert db.lire_reglages(USER_ID) == dr.DEFAUTS


def test_un_ancien_reglage_du_programme_sert_tant_quil_ny_a_pas_de_ligne(fake_db):
    """Entre le déploiement et la migration, rien ne doit revenir aux valeurs
    par défaut : l'heure choisie hier tient toujours."""
    assert db.lire_reglages(USER_ID, {"_settings": {"reminder_hour": 7, "show_1rm": False}}) \
        == {**dr.DEFAUTS, "reminder_hour": 7}


# ── Base en retard ───────────────────────────────────────────────────────

def test_sans_la_table_tout_marche_comme_avant(fake_db, logged_in, table_absente):
    _prog(fake_db, settings={"notifications": True, "reminder_hour": 9})
    html = logged_in.get("/gestion").get_data(as_text=True)
    assert '<option value="9" selected>09 h 00</option>' in html
    _envoyer(logged_in, reminder_hour="7")
    assert fake_db.tables["programs"][0]["data"]["_settings"]["reminder_hour"] == 7
    assert "reglages" not in fake_db.tables


def test_la_table_est_reessayee_apres_une_absence(fake_db, monkeypatch):
    """Un processus qui a vu la table absente la redemande une minute plus
    tard : la migration appliquée, il s'en sert sans redémarrage."""
    dr._marquer_absente()
    assert dr._disponible() is False
    monkeypatch.setattr(dr, "_absente_depuis", dr._absente_depuis - dr.REESSAI - 1)
    assert dr._disponible() is True


# ── Crons ────────────────────────────────────────────────────────────────

def _abonne(fake, user_id=USER_ID):
    fake.table("push_subscriptions").insert({
        "user_id": user_id, "endpoint": f"https://push.example/{user_id}",
        "p256dh": "k", "auth": "a", "reactivation_count": 0}).execute()


def test_le_rappel_suit_la_table(fake_db):
    from core import reminders
    _prog(fake_db)
    _abonne(fake_db)
    fake_db.table("reglages").insert({"user_id": USER_ID, **dr.DEFAUTS,
                                      "notifications": True, "reminder_hour": 18}).execute()
    assert [t["user_id"] for t in reminders.targets_for_hour(18)] == [USER_ID]
    assert reminders.targets_for_hour(9) == []


def test_la_table_prime_sur_un_reste_du_programme(fake_db):
    from core import reminders
    _prog(fake_db, settings={"notifications": True, "reminder_hour": 18})
    _abonne(fake_db)
    fake_db.table("reglages").insert({"user_id": USER_ID, **dr.DEFAUTS,
                                      "notifications": False}).execute()
    assert reminders.targets_for_hour(18) == []


def test_le_recap_suit_la_table(fake_db):
    from core import recap
    progs = [{"user_id": "a", "data": {}}, {"user_id": "b", "data": {}}]
    fake_db.table("reglages").insert({"user_id": "a", **dr.DEFAUTS, "notifications": True}).execute()
    fake_db.table("reglages").insert({"user_id": "b", **dr.DEFAUTS, "notifications": True,
                                      "recap_hebdo": False}).execute()
    assert set(recap.cibles(progs)) == {"a"}


# ── Suppression du compte ────────────────────────────────────────────────

def test_supprimer_le_compte_efface_ses_reglages(fake_db):
    fake_db.table("reglages").insert({"user_id": USER_ID, **dr.DEFAUTS}).execute()
    db.delete_user_account(USER_ID)
    assert fake_db.tables["reglages"] == []


# ── La migration ─────────────────────────────────────────────────────────

def test_la_migration_cree_la_table_fermee_et_la_remplit():
    import re
    sql = re.sub(r"--[^\n]*", "", SQL.read_text(encoding="utf-8").lower())   # code seul
    assert "create table if not exists public.reglages" in sql
    assert "references auth.users(id) on delete cascade" in sql
    for col in dr.DEFAUTS:
        assert col in sql
    for mort in MORTS:
        assert mort not in sql
    assert "enable row level security" in sql
    assert "revoke all on public.reglages from anon, authenticated" in sql
    assert "on conflict (user_id) do nothing" in sql
    assert "data - '_settings'" in sql
    assert "version = version + 1" in sql
