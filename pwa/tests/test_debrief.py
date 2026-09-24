"""Debrief de fin de séance.

Le coach IA est une page qu'il faut penser à ouvrir — la plupart ne l'ouvrent
jamais. Le debrief va au-devant, sur l'écran qui suit la séance.
"""
import datetime as dt
import json
import sys
import types

from conftest import USER_ID, CSRF
from core import debrief
from core.dates import continuous_week

D_PREV = dt.date(2026, 9, 14)
D_NOW = dt.date(2026, 9, 21)


class _FakeAnthropic:
    text = ("Tu as posé 1 800 kg sur cette séance, 12 % de plus que la dernière "
            "fois. Ton RPE moyen de 9 montre que la charge est haute. "
            "La prochaine fois, garde la même charge et vise une répétition de plus.")
    calls: list = []

    def __init__(self, api_key=None):
        self.messages = self

    def create(self, **kwargs):
        _FakeAnthropic.calls.append(kwargs)
        return types.SimpleNamespace(content=[types.SimpleNamespace(text=self.text)])


def _install(monkeypatch, cls=_FakeAnthropic):
    cls.calls = []
    module = types.ModuleType("anthropic")
    module.Anthropic = cls
    monkeypatch.setitem(sys.modules, "anthropic", module)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    return cls


def _seed(fake, extra=None):
    data = {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": D_PREV.isoformat(),
    }
    data.update(extra or {})
    fake.table("programs").insert({"user_id": USER_ID, "data": data}).execute()
    fake.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()


def _series(fake, date, poids, reps=8, serie=1, rpe=None, exo="Développé couché"):
    fake.table("history").insert({
        "user_id": USER_ID, "semaine": continuous_week(date), "seance": "Push",
        "exercice": exo, "serie": serie, "reps": reps, "poids": poids,
        "remarque": "", "muscle": "Pecs", "date": date.isoformat(), "rpe": rpe,
    }).execute()


def _hist(fake):
    import core.db as core_db
    core_db._data_cache.clear()
    return core_db.get_hist(USER_ID)


# ── Collecte des faits (aucun appel IA) ──────────────────────────


def test_les_faits_resument_la_seance(fake_db):
    _seed(fake_db)
    for s in (1, 2, 3):
        _series(fake_db, D_NOW, 80.0, reps=8, serie=s, rpe=8.5)
    facts = debrief.collect_facts(_hist(fake_db), "Push", D_NOW.isoformat())
    assert facts["volume"] == 3 * 8 * 80
    assert facts["sets"] == 3 and facts["reps"] == 24
    assert facts["rpe_moyen"] == 8.5
    assert facts["exos"]["Développé couché"]["best"] == 80.0


def test_les_faits_comparent_a_la_seance_precedente(fake_db):
    _seed(fake_db)
    for s in (1, 2):
        _series(fake_db, D_PREV, 70.0, reps=8, serie=s)
    for s in (1, 2):
        _series(fake_db, D_NOW, 80.0, reps=8, serie=s)
    facts = debrief.collect_facts(_hist(fake_db), "Push", D_NOW.isoformat())
    assert facts["volume_prev"] == 2 * 8 * 70
    assert facts["volume_delta_pct"] == 14
    assert facts["prev_date"] == D_PREV.isoformat()


def test_les_faits_reperent_les_records(fake_db):
    _seed(fake_db)
    _series(fake_db, D_PREV, 70.0)
    _series(fake_db, D_NOW, 85.0)
    facts = debrief.collect_facts(_hist(fake_db), "Push", D_NOW.isoformat())
    assert [r["exo"] for r in facts["records"]] == ["Développé couché"]
    assert facts["records"][0]["poids"] == 85.0


def test_pas_de_record_si_moins_lourd_quavant(fake_db):
    _seed(fake_db)
    _series(fake_db, D_PREV, 90.0)
    _series(fake_db, D_NOW, 80.0)
    facts = debrief.collect_facts(_hist(fake_db), "Push", D_NOW.isoformat())
    assert facts["records"] == []


def test_aucun_fait_sans_serie_enregistree(fake_db):
    _seed(fake_db)
    assert debrief.collect_facts(_hist(fake_db), "Push", D_NOW.isoformat()) == {}


def test_le_prompt_ne_contient_que_des_chiffres_reels(fake_db):
    _seed(fake_db)
    _series(fake_db, D_NOW, 80.0, reps=10, rpe=9)
    facts = debrief.collect_facts(_hist(fake_db), "Push", D_NOW.isoformat())
    texte = debrief.format_facts(facts)
    assert "800 kg" in texte
    assert "RPE moyen : 9" in texte
    assert "Première séance de ce type" in texte


# ── Route ────────────────────────────────────────────────────────


def _call(client, date=D_NOW):
    return client.post("/seance/debrief",
                       json={"seance": "Push", "date": date.isoformat()},
                       headers={"X-CSRFToken": CSRF})


def test_le_debrief_est_genere_pour_un_membre_pro(fake_db, logged_in, monkeypatch):
    _install(monkeypatch)
    _seed(fake_db)
    for s in (1, 2, 3):
        _series(fake_db, D_NOW, 80.0, serie=s)
    d = json.loads(_call(logged_in).data)
    assert d["ok"] is True
    assert "1 800 kg" in d["text"]
    assert d["trial"] is False


def test_le_debrief_est_refuse_sans_serie(fake_db, logged_in, monkeypatch):
    _install(monkeypatch)
    _seed(fake_db)
    d = json.loads(_call(logged_in).data)
    assert d["ok"] is False


def test_un_gratuit_a_un_apercu_par_semaine(fake_db, client, monkeypatch):
    import time
    _install(monkeypatch)
    _seed(fake_db)
    _series(fake_db, D_NOW, 80.0)
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True, is_vip=False,
                 is_vip_full=False, is_vip_ts=time.time(), _csrf=CSRF)

    first = json.loads(_call(client).data)
    assert first["ok"] is True and first["trial"] is True

    second = json.loads(_call(client).data)
    assert second.get("locked") is True


def test_lapercu_nest_consomme_que_si_la_generation_aboutit(fake_db, client, monkeypatch):
    """Une panne de l'IA ne doit pas brûler l'aperçu gratuit de la semaine."""
    import time

    class _Boom(_FakeAnthropic):
        def create(self, **kwargs):
            raise RuntimeError("overloaded")

    _install(monkeypatch, _Boom)
    _seed(fake_db)
    _series(fake_db, D_NOW, 80.0)
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True, is_vip=False,
                 is_vip_full=False, is_vip_ts=time.time(), _csrf=CSRF)

    assert json.loads(_call(client).data)["ok"] is False
    prog = fake_db.tables["programs"][0]["data"]
    assert not prog.get("_debrief_free")


def test_laccueil_propose_le_debrief_apres_une_seance(fake_db, logged_in, monkeypatch):
    _install(monkeypatch)
    _seed(fake_db)
    _series(fake_db, D_NOW, 80.0)
    logged_in.post("/seance/finish", data={
        "_csrf": CSRF, "mode": "prefaite", "seance_name": "Push",
        "date": D_NOW.isoformat(), "rating": "", "comment": "",
    })
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert 'class="card debrief-card"' in html
    assert "TON COACH A REGARDÉ TA SÉANCE" in html


def test_la_seance_est_passee_au_script_en_javascript_valide(fake_db, logged_in, monkeypatch):
    """|tojson produit des guillemets doubles : dans un attribut lui-même
    délimité par des guillemets, l'expression Alpine est coupée en deux et la
    carte ne charge jamais rien."""
    import re
    _install(monkeypatch)
    _seed(fake_db)
    _series(fake_db, D_NOW, 80.0)
    logged_in.post("/seance/finish", data={
        "_csrf": CSRF, "mode": "prefaite", "seance_name": "Push",
        "date": D_NOW.isoformat(), "rating": "", "comment": "",
    })
    html = logged_in.get("/accueil").get_data(as_text=True)
    m = re.search(r"x-data='debriefCard\((.*?)\)'", html)
    assert m, "x-data doit être délimité par des apostrophes"
    assert json.loads(m.group(1)) == {"seance": "Push", "date": D_NOW.isoformat()}


def test_laccueil_ne_propose_rien_sans_seance_terminee(fake_db, logged_in):
    _seed(fake_db)
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert 'class="card debrief-card"' not in html


def test_le_debrief_ne_safficher_quune_fois(fake_db, logged_in, monkeypatch):
    """La proposition est consommée : recharger l'accueil ne la rejoue pas."""
    _install(monkeypatch)
    _seed(fake_db)
    _series(fake_db, D_NOW, 80.0)
    logged_in.post("/seance/finish", data={
        "_csrf": CSRF, "mode": "prefaite", "seance_name": "Push",
        "date": D_NOW.isoformat(), "rating": "", "comment": "",
    })
    marker = 'class="card debrief-card"'
    assert marker in logged_in.get("/accueil").get_data(as_text=True)
    assert marker not in logged_in.get("/accueil").get_data(as_text=True)


def test_le_debrief_nest_pas_brule_par_un_prefetch(fake_db, logged_in, monkeypatch):
    """prefetch.js charge l'accueil au survol du lien : ce chargement de fond
    ne doit pas consommer la proposition avant que l'utilisateur la voie."""
    _install(monkeypatch)
    _seed(fake_db)
    _series(fake_db, D_NOW, 80.0)
    logged_in.post("/seance/finish", data={
        "_csrf": CSRF, "mode": "prefaite", "seance_name": "Push",
        "date": D_NOW.isoformat(), "rating": "", "comment": "",
    })
    marker = 'class="card debrief-card"'

    # Prefetch (Sec-Fetch-Mode: same-origin) : rien n'est consommé.
    prefetched = logged_in.get("/accueil", headers={"Sec-Fetch-Mode": "same-origin"})
    assert marker not in prefetched.get_data(as_text=True)

    # La vraie navigation la trouve toujours.
    assert marker in logged_in.get("/accueil").get_data(as_text=True)
