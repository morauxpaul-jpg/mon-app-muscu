"""Le schéma que le code attend, et la base qui doit y correspondre.

Audit du 06/10 (C1) : la migration v29 n'avait jamais été appliquée. L'essai
PRO et le parrainage n'existaient pas en production, et 1 270 tests passaient
quand même : la fausse base acceptait n'importe quel nom de colonne. Trois
garde-fous, tenus ici :

* `core/schema.py:ATTENDU` contient chaque colonne et chaque table que créent
  les migrations du dépôt (une migration nouvelle doit l'y ajouter) ;
* la fausse base refuse une colonne absente de ce schéma, avec les codes de
  PostgREST ;
* le contrôle au démarrage signale en base ce qui manque (journal + /admin).
"""
import logging
import re
from pathlib import Path

import pytest

from conftest import USER_ID, FakeSupabase
from core import schema

PWA = Path(__file__).resolve().parent.parent
MIGRATIONS = sorted(PWA.glob("supabase_schema_v*.sql"))
_HORS_COLONNE = {"primary", "unique", "constraint", "check", "foreign", "exclude"}


def _sans_commentaires(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _morceaux_de_premier_niveau(corps: str):
    """Découpe `a int, b text check (x in (1, 2)), primary key (a)` aux virgules
    de premier niveau seulement."""
    profondeur, debut = 0, 0
    for i, ch in enumerate(corps):
        if ch == "(":
            profondeur += 1
        elif ch == ")":
            profondeur -= 1
        elif ch == "," and profondeur == 0:
            yield corps[debut:i]
            debut = i + 1
    yield corps[debut:]


def _colonnes_creees_par_les_migrations():
    vues = set()
    for f in MIGRATIONS:
        sql = _sans_commentaires(f.read_text(encoding="utf-8"))
        for m in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?(\w+)\s*\(",
                             sql, re.I):
            table, i, profondeur = m.group(1), m.end(), 1
            j = i
            while profondeur and j < len(sql):
                profondeur += {"(": 1, ")": -1}.get(sql[j], 0)
                j += 1
            for morceau in _morceaux_de_premier_niveau(sql[i:j - 1]):
                mots = morceau.split()
                if mots and mots[0].lower() not in _HORS_COLONNE:
                    vues.add((f.name, table, mots[0].strip('"')))
        for m in re.finditer(r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?(?:public\.)?(\w+)\s+([^;]*)",
                             sql, re.I):
            for c in re.finditer(r"add\s+column\s+(?:if\s+not\s+exists\s+)?(\w+)", m.group(2), re.I):
                vues.add((f.name, m.group(1), c.group(1)))
    return vues


# ── Le registre suit les migrations ──────────────────────────────


def test_les_migrations_sont_bien_lues():
    """Garde-fou du test lui-même : un analyseur qui ne trouverait rien
    validerait n'importe quel registre."""
    vues = _colonnes_creees_par_les_migrations()
    assert ("supabase_schema_v29_referral.sql", "profiles", "vip_until") in vues
    assert ("supabase_schema_v47_etat_compte.sql", "etat_compte", "plats_semaine") in vues
    assert ("supabase_schema_v45_reglages.sql", "reglages", "reminder_hour") in vues
    assert len(vues) > 80


def test_chaque_colonne_creee_par_une_migration_est_attendue():
    manquent = sorted(f"{fichier} : {table}.{col}"
                      for fichier, table, col in _colonnes_creees_par_les_migrations()
                      if col not in schema.ATTENDU.get(table, ()))
    assert not manquent, ("Ajoute ces colonnes à core/schema.py:ATTENDU (sinon la fausse base "
                          "des tests les refusera et le contrôle au démarrage ne les verra pas) :\n"
                          + "\n".join(manquent))


def test_aucun_doublon_dans_le_registre():
    for table, cols in schema.ATTENDU.items():
        assert len(cols) == len(set(cols)), table


# ── La fausse base refuse ce que la vraie refuserait ─────────────


def test_lire_une_colonne_absente_echoue_comme_postgrest():
    fake = FakeSupabase()
    with pytest.raises(Exception, match="42703"):
        fake.table("profiles").select("id,colonne_inventee").execute()


def test_filtrer_sur_une_colonne_absente_echoue():
    fake = FakeSupabase()
    with pytest.raises(Exception, match="42703"):
        fake.table("history").select("*").eq("series", 1).execute()


def test_ecrire_une_colonne_absente_echoue_avec_pgrst204():
    fake = FakeSupabase()
    with pytest.raises(Exception, match="PGRST204"):
        fake.table("history").insert({"user_id": USER_ID, "series": 1}).execute()


def test_les_colonnes_v29_sont_acceptees():
    fake = FakeSupabase()
    fake.table("profiles").insert({"id": USER_ID, "vip_until": "2026-10-10T00:00:00+00:00",
                                   "referral_code": "abc12345", "referred_by": None}).execute()
    r = fake.table("profiles").select("vip_until,referral_code").eq("id", USER_ID).execute()
    assert r.data == [{"vip_until": "2026-10-10T00:00:00+00:00", "referral_code": "abc12345"}]


# ── Le contrôle au démarrage ─────────────────────────────────────


class _BaseEnRetard:
    """Client minimal dont la table `profiles` n'a pas les colonnes v29 —
    l'état de la production du 14/06 au 09/10."""

    absentes = {"profiles": {"vip_until", "referral_code", "referred_by"}}
    tables_absentes = set()
    panne = False

    def table(self, nom):
        base = self

        class _Q:
            def select(self, cols):
                self.cols = [c.strip() for c in cols.split(",")]
                return self

            def limit(self, _n):
                return self

            def execute(self):
                if base.panne:
                    raise Exception("<ConnectionTerminated error_code:9>")
                if nom in base.tables_absentes:
                    raise Exception("{'code': 'PGRST205', 'message': \"Could not find the table "
                                    f"'public.{nom}' in the schema cache\"}}")
                for c in self.cols:
                    if c in base.absentes.get(nom, ()):
                        raise Exception("{'code': '42703', 'message': "
                                        f"'column {nom}.{c} does not exist'}}")
                return None
        return _Q()


@pytest.fixture(autouse=True)
def _etat_neuf():
    schema.reinitialiser()
    yield
    schema.reinitialiser()


def test_la_v29_manquante_est_reperee_colonne_par_colonne():
    r = schema.verifier(_BaseEnRetard())
    assert r == {"absentes": {"profiles": ["referral_code", "referred_by", "vip_until"]},
                 "inconnues": []}


def test_une_table_absente_est_signalee_en_entier():
    base = _BaseEnRetard()
    base.absentes = {}
    base.tables_absentes = {"etat_compte"}
    assert schema.verifier(base)["absentes"] == {"etat_compte": ["(table)"]}


def test_une_panne_reseau_nest_pas_une_migration_oubliee():
    base = _BaseEnRetard()
    base.panne = True
    r = schema.verifier(base)
    assert r["absentes"] == {} and set(r["inconnues"]) == set(schema.ATTENDU)


def test_une_base_complete_ne_declenche_aucune_alerte(caplog):
    caplog.set_level(logging.INFO, logger="core.schema")
    base = _BaseEnRetard()
    base.absentes = {}
    e = schema.enregistrer(schema.verifier(base))
    assert e["alerte"] == "" and e["verifie"] is True
    assert "rien ne manque" in caplog.text


def test_un_manque_est_journalise_en_erreur(caplog):
    e = schema.enregistrer(schema.verifier(_BaseEnRetard()))
    assert "profiles.vip_until" in e["alerte"]
    erreurs = [r for r in caplog.records if r.levelname == "ERROR"]
    assert erreurs and "profiles.vip_until" in erreurs[0].getMessage()


def test_sans_base_configuree_le_demarrage_ne_plante_pas():
    def _get_client():
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants")
    assert schema.verifier_et_enregistrer(_get_client)["verifie"] is False
    t = schema.verifier_au_demarrage(_get_client)
    t.join(5)
    assert not t.is_alive()


def test_admin_affiche_le_manque(fake_db, logged_in, monkeypatch):
    import types
    monkeypatch.setenv("ADMIN_EMAILS", "test@example.com")
    fake_db.auth.admin.list_users = lambda **k: [types.SimpleNamespace(
        id=USER_ID, email="test@example.com", created_at="2026-09-01")]
    import core.db as core_db
    monkeypatch.setattr(core_db, "get_client", lambda: _BaseEnRetard())
    monkeypatch.setattr(schema, "REVERIFIER_APRES", -1)   # le contrôle du démarrage a pu passer avant
    r = logged_in.get("/admin")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Colonnes absentes en base" in html and "profiles.vip_until" in html


def test_admin_sans_manque_naffiche_rien(fake_db, logged_in, monkeypatch):
    import types
    monkeypatch.setenv("ADMIN_EMAILS", "test@example.com")
    fake_db.auth.admin.list_users = lambda **k: [types.SimpleNamespace(
        id=USER_ID, email="test@example.com", created_at="2026-09-01")]
    html = logged_in.get("/admin").get_data(as_text=True)     # la fausse base est complète
    assert "Colonnes absentes en base" not in html


def test_admin_relance_le_controle_apres_une_migration(monkeypatch):
    """Une migration appliquée après le démarrage efface l'alerte au contrôle suivant."""
    base = _BaseEnRetard()
    schema.enregistrer(schema.verifier(base))
    assert schema.etat()["alerte"]
    base.absentes = {}
    monkeypatch.setattr(schema, "REVERIFIER_APRES", 0)
    assert schema.etat_a_jour(lambda: base)["alerte"] == ""


# ── Avec les colonnes v29, le parrainage crédite vraiment ────────


def test_le_parrainage_credite_filleul_et_parrain(fake_db):
    import core.db as core_db
    from routes.parrainage import apply_referral, REFEREE_VIP_DAYS, REFERRER_VIP_DAYS
    parrain, filleul = "u-parrain-0001", "u-filleul-0002"
    fake_db.table("profiles").insert({"id": parrain, "tier": "free"}).execute()
    fake_db.table("profiles").insert({"id": filleul, "tier": "free"}).execute()
    code = core_db.get_or_create_referral_code(parrain)
    assert core_db.get_user_by_referral_code(code) == parrain   # le code est bien en base
    assert apply_referral(filleul, code) is True
    profils = {p["id"]: p for p in fake_db.tables["profiles"]}
    assert core_db.vip_until_active(profils[filleul]["vip_until"])
    assert core_db.vip_until_active(profils[parrain]["vip_until"])
    assert profils[filleul]["referred_by"] == parrain
    assert apply_referral(filleul, code) is False                # une seule fois
    assert REFEREE_VIP_DAYS == 1 and REFERRER_VIP_DAYS == 3


# ── Un repli « base en retard » ne cache plus le manque (audit du 06/10, 4.3) ──

@pytest.mark.parametrize("message, attendu", [
    ("{'code': '42703', 'message': 'column profiles.referral_code does not exist'}",
     "profiles.referral_code"),
    ("{'code': 'PGRST204', 'message': \"Could not find the 'vip_until' column of 'profiles' in the schema cache\"}",
     "profiles.vip_until"),
    (str({"code": "42P01", "message": 'relation "public.reglages" does not exist'}), "table reglages"),
    ('{"code":"42P01","message":"relation \\"public.reglages\\" does not exist"}', "table reglages"),
    ("{'code': 'PGRST205', 'message': \"Could not find the table 'public.etat_compte' in the schema cache\"}",
     "table etat_compte"),
    ("column history.exercise_id does not exist".lower(), "history.exercise_id"),
])
def test_signaler_reconnait_les_quatre_formes(message, attendu):
    from core import schema
    assert schema.signaler(Exception(message), "x") is True
    assert attendu in schema.etat()["alerte"]


def test_une_panne_nest_pas_un_manque():
    from core import schema
    assert schema.signaler(TimeoutError("read timed out"), "profiles") is False
    assert schema.etat()["alerte"] == ""


def test_le_parrainage_en_repli_allume_ladmin_une_seule_fois(fake_db, monkeypatch, caplog):
    import logging
    import conftest
    import core.db as core_db
    from core import schema
    vraie = conftest.FakeQuery.execute

    def sans_v29(self):
        if self._table == "profiles" and "referral_code" in str(self._colonnes or "") + str(self._payload or ""):
            raise Exception("{'code': '42703', 'message': 'column profiles.referral_code does not exist'}")
        return vraie(self)
    monkeypatch.setattr(conftest.FakeQuery, "execute", sans_v29)
    caplog.set_level(logging.ERROR, logger="core.schema")
    core_db.get_or_create_referral_code(conftest.USER_ID)
    core_db.get_or_create_referral_code(conftest.USER_ID)
    assert "profiles.referral_code" in schema.etat()["alerte"]
    assert sum("profiles.referral_code" in r.getMessage() for r in caplog.records
               if r.name == "core.schema") == 1


def test_une_table_v45_absente_allume_ladmin():
    from core import db_reglages, schema
    db_reglages._marquer_absente()
    db_reglages._oublier_absence()
    assert "table reglages" in schema.etat()["alerte"]
