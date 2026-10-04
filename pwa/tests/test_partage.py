"""État partagé entre instances (audit du 03/10, I11).

Le cache, les verrous, les réservations de quota et les tâches IA vivaient dans
la mémoire du processus : justes avec une instance, faux avec deux. Ils passent
maintenant par `core/partage.py` (Redis si `REDIS_URL`, mémoire sinon).

Les « deux instances » sont simulées par deux copies indépendantes d'un même
module (chacune son cache local, ses fils), branchées sur le même Redis : c'est
exactement ce que voient deux processus gunicorn ou deux répliques Railway.
`REDIS_TEST_URL=redis://…` rejoue aussi ces tests contre un vrai serveur.
"""
import importlib.util
import os
import threading
import time
import uuid
from pathlib import Path

import fakeredis
import pytest

from conftest import CSRF, USER_ID
from core import partage

CORE = Path(__file__).resolve().parent.parent / "core"


def _clients():
    yield pytest.param(None, id="memoire")
    yield pytest.param("fake", id="fakeredis")
    url = os.getenv("REDIS_TEST_URL", "")
    if url:
        yield pytest.param(url, id="redis")


def _brancher(choix):
    if choix is None:
        partage.utiliser(None)
        return None
    if choix == "fake":
        client = fakeredis.FakeRedis(decode_responses=True)
    else:
        import redis
        client = redis.Redis.from_url(choix, decode_responses=True)
        client.flushdb()
    partage.utiliser(client)
    return client


@pytest.fixture(params=list(_clients()))
def stockage(request):
    client = _brancher(request.param)
    partage.reinitialiser()
    yield client
    partage.utiliser(None)


@pytest.fixture()
def redis_commun():
    client = fakeredis.FakeRedis(decode_responses=True)
    partage.utiliser(client)
    yield client
    partage.utiliser(None)


def _copie(module: str):
    """Une seconde instance du module : même code, état local séparé."""
    spec = importlib.util.spec_from_file_location(f"instance_{module}_{uuid.uuid4().hex[:6]}",
                                                  CORE / f"{module}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Briques ──────────────────────────────────────────────────────

def test_le_verrou_met_les_fils_en_file(stockage):
    compteur, vus = [0], []

    def section():
        with partage.verrou("test", "u1"):
            lu = compteur[0]
            time.sleep(0.01)
            compteur[0] = lu + 1
            vus.append(lu)

    fils = [threading.Thread(target=section) for _ in range(8)]
    [f.start() for f in fils]
    [f.join() for f in fils]
    assert compteur[0] == 8 and sorted(vus) == list(range(8))


def test_un_verrou_tenu_fait_attendre_puis_abandonner(stockage):
    with partage.verrou("test", "u1"):
        with pytest.raises(TimeoutError):
            with partage.verrou("test", "u1", attente=0.05):
                pass
    with partage.verrou("test", "u1", attente=0.05):     # libéré : on passe
        pass


def test_avec_redis_deux_cles_differentes_ne_sattendent_pas(redis_commun):
    with partage.verrou("exo", USER_ID, "2026-10-01", "Push", "Squat"):
        with partage.verrou("exo", USER_ID, "2026-10-01", "Push", "Dips", attente=0.05):
            pass


def test_un_verrou_abandonne_par_une_instance_morte_expire(redis_commun):
    """Une instance tuée en pleine section ne bloque personne au-delà du TTL."""
    cle = partage._cle("verrou", "test", "u1")
    redis_commun.set(cle, "jeton-dune-instance-morte", px=150)
    debut = time.monotonic()
    with partage.verrou("test", "u1", attente=2):
        pass
    assert 0.1 < time.monotonic() - debut < 1.5


def test_un_verrou_expire_puis_repris_nest_pas_efface_par_lancien(redis_commun):
    with partage.verrou("test", "u1", ttl=0.1):
        time.sleep(0.2)                                  # expiré pendant la section
        cle = partage._cle("verrou", "test", "u1")
        redis_commun.set(cle, "autre-instance", px=5000)  # repris ailleurs
    assert redis_commun.get(cle) == "autre-instance"


def test_compteurs_valeurs_et_fenetre(stockage):
    assert partage.ajouter("c", 2, 60) == 2
    assert partage.ajouter("c", -5, 60) == 0             # jamais négatif
    assert partage.valeur("c") == 0 and partage.valeur("absent") == 0
    partage.ecrire("v", {"a": [1, "é"]}, 60)
    assert partage.lire("v") == {"a": [1, "é"]}
    partage.supprimer("v")
    assert partage.lire("v") is None
    assert [partage.fenetre("f", 3, 60) for _ in range(4)] == [True, True, True, False]


def test_les_valeurs_expirent(stockage):
    partage.ecrire("v", {"x": 1}, 1)
    assert partage.lire("v") == {"x": 1}
    time.sleep(1.1)
    assert partage.lire("v") is None


def test_les_generations_avancent_et_marquent_le_stockage(stockage):
    avant = partage.generations(["cache:a", "cache:*"])
    assert avant[0] == ("m" if stockage is None else "r") and avant[1:] == (0, 0)
    assert partage.nouvelle_generation("cache:a") == 1
    assert partage.generations(["cache:a", "cache:*"])[1:] == (1, 0)


def test_une_cle_longue_reste_bornee():
    cle = partage._cle("verrou", "exo", "u", "2026-10-01", "x" * 300)
    assert len(cle) < 120 and cle != partage._cle("verrou", "exo", "u", "2026-10-01", "y" * 300)


# ── Deux instances ───────────────────────────────────────────────

def test_une_ecriture_sur_une_instance_invalide_le_cache_de_lautre(redis_commun):
    a, b = _copie("db_base"), _copie("db_base")
    cle = "hist:u-deux"
    assert a._cache_get(cle) is None
    a._cache_set(cle, ["ancienne séance"])
    assert a._cache_get(cle) == ["ancienne séance"]
    b._cache_invalidate(cle)                             # écriture servie par B
    assert a._cache_get(cle) is None, "A servait l'ancien historique pendant 60 s"


def test_une_lecture_lente_croisee_par_une_autre_instance_nest_pas_gardee(redis_commun):
    a, b = _copie("db_base"), _copie("db_base")
    cle = "prog:u-course"
    assert a._cache_get(cle) is None                     # A commence sa lecture
    b._cache_invalidate(cle)                             # B écrit entre-temps
    a._cache_set(cle, {"ancien": True})
    assert a._cache_get(cle) is None


def test_corriger_le_cache_local_invalide_les_autres(redis_commun):
    a, b = _copie("db_base"), _copie("db_base")
    cle = "hist:u-corr"
    for inst in (a, b):
        assert inst._cache_get(cle) is None
        inst._cache_set(cle, [1])
    a._cache_modifier(cle, lambda v: v + [2])            # « Série faite » servie par A
    assert a._cache_get(cle) == [1, 2]                   # A garde sa copie corrigée
    assert b._cache_get(cle) is None                     # B relira la base


def test_une_correction_croisee_par_une_autre_ecriture_est_jetee(redis_commun, monkeypatch):
    a, b = _copie("db_base"), _copie("db_base")
    cle = "hist:u-croise"
    assert a._cache_get(cle) is None
    a._cache_set(cle, [1])
    vrai = partage.nouvelle_generation

    def ecriture_de_b_juste_avant(c):
        vrai(c)                                          # B écrit pendant la correction
        return vrai(c)
    monkeypatch.setattr(partage, "nouvelle_generation", ecriture_de_b_juste_avant)
    a._cache_modifier(cle, lambda v: v + [2])
    monkeypatch.setattr(partage, "nouvelle_generation", vrai)
    assert a._cache_get(cle) is None


def test_une_tache_ia_se_suit_depuis_une_autre_instance(redis_commun):
    a, b = _copie("taches_ia"), _copie("taches_ia")
    feu = threading.Event()

    def travail():
        feu.wait(5)
        return {"ok": True, "programme": "Force"}, 200

    tid = a.lancer(USER_ID, "programme", travail)
    corps, code = b.lire(tid, USER_ID)
    assert code == 202 and corps["statut"] == "encours"
    assert b.en_cours(USER_ID, "programme") == tid       # un second tap rejoint la tâche
    assert b.lire(tid, "u-autre") is None                # jamais lisible par un autre compte
    feu.set()
    debut = time.monotonic()
    b.attendre(tid, 3)                                   # B sonde le stockage partagé
    assert time.monotonic() - debut < 2
    assert b.lire(tid, USER_ID) == ({"ok": True, "programme": "Force"}, 200)
    assert b.en_cours(USER_ID, "programme") is None


def test_les_reservations_de_quota_sont_communes(redis_commun):
    from core import quota
    a = _copie("quota")
    assert a.reserver("generateur", "u-q", lambda: 0, 1)
    assert not quota.reserver("generateur", "u-q", lambda: 0, 1)   # l'autre instance voit la réservation
    a.liberer("generateur", "u-q")
    assert quota.reserver("generateur", "u-q", lambda: 0, 1)


# ── Redis en panne ───────────────────────────────────────────────

class _Panne:
    """Client Redis dont chaque appel échoue (serveur arrêté)."""

    def __getattr__(self, nom):
        def echoue(*a, **k):
            raise ConnectionError("Redis injoignable")
        return echoue


def test_redis_en_panne_lapp_continue_sans_cache(fake_db, monkeypatch):
    import core.db_base as base
    partage.utiliser(_Panne())
    try:
        with partage.verrou("test", "u1"):                # repli sur un verrou local
            pass
        assert partage.ajouter("c", 1, 60) == 1
        partage.ecrire("v", {"x": 1}, 60)
        assert partage.lire("v") == {"x": 1}             # visible par cette instance
        assert partage.stockage() == "redis-en-panne"
        assert base._cache_get("hist:u-panne") is None
        base._cache_set("hist:u-panne", ["valeur"])
        assert base._cache_get("hist:u-panne") is None   # cache coupé : rien de périmé servi
        assert partage.etat()["alerte"].startswith("REDIS_URL est défini")
    finally:
        partage.utiliser(None)


def test_redis_revient_apres_la_pause(monkeypatch):
    client = fakeredis.FakeRedis(decode_responses=True)
    partage.utiliser(_Panne())
    try:
        assert partage.generations(["cache:a"]) is None
        partage.utiliser(client)
        monkeypatch.setattr(partage, "_panne_jusqua", time.time() + 60)
        assert partage.generations(["cache:a"]) is None  # encore en pause
        monkeypatch.setattr(partage, "_panne_jusqua", 0.0)
        assert partage.generations(["cache:a"]) == ("r", 0)
    finally:
        partage.utiliser(None)


# ── Configuration ────────────────────────────────────────────────

@pytest.mark.parametrize("brut,attendu", [
    ("redis://default:mdp@redis.railway.internal:6379", "redis://default:mdp@redis.railway.internal:6379"),
    ('"rediss://h:6380"', "rediss://h:6380"),
    ("", ""), ("localhost:6379", ""), ("${{Redis.REDIS_URL}}", ""),
])
def test_seule_une_vraie_url_active_redis(brut, attendu):
    assert partage.url_redis({"REDIS_URL": brut}) == attendu


def test_sans_redis_plusieurs_processus_demandes_declenchent_une_alerte():
    partage.utiliser(None)
    e = partage.etat({"WEB_CONCURRENCY": "3"})
    assert e["stockage"] == "memoire" and e["processus"] == 1
    assert "WEB_CONCURRENCY=3 ignoré" in e["alerte"]
    assert partage.etat({"WEB_CONCURRENCY": "1"})["alerte"] == ""


def test_avec_redis_les_processus_demandes_sont_appliques(redis_commun):
    e = partage.verifier_au_demarrage({"WEB_CONCURRENCY": "3"})
    assert e == {"stockage": "redis", "processus": 3, "alerte": ""}


def test_la_console_admin_affiche_lalerte(fake_db, monkeypatch):
    from flask import render_template
    import app as appmod
    partage.utiliser(None)                               # sans Redis, quel que soit PARTAGE_TEST
    alerte = partage.etat({"WEB_CONCURRENCY": "2"})
    with appmod.app.test_request_context("/admin"):
        html = render_template("admin.html", users=[], vip_count=0, total_count=0,
                               current_email="a@b.c", admob="reel", partage=alerte,
                               stats={"total_rows": 0, "total_tonnage": 0, "total_seances": 0,
                                      "active_7d": 0, "active_30d": 0})
    assert "WEB_CONCURRENCY=2 ignoré" in html


# ── Flux du coach ────────────────────────────────────────────────

def test_trop_de_flux_coach_ouverts_la_question_est_refusee_et_rendue(fake_db, logged_in, monkeypatch):
    """Une réponse en flux tient un fil. Au-delà de COACH_FLUX_MAX par
    instance, la question reçoit « réessaie » et son quota est rendu."""
    import routes.coach as coach
    from test_coach_stream import _install_fake_anthropic
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    _install_fake_anthropic(monkeypatch)
    plein = threading.BoundedSemaphore(1)
    plein.acquire()                                      # le seul flux est pris
    monkeypatch.setattr(coach, "_FLUX", plein)
    r = logged_in.post("/coach/ask", json={"message": "Combien de séries ?"},
                       headers={"X-CSRFToken": CSRF, "Accept": "text/event-stream"})
    corps = r.get_data(as_text=True)
    assert "event: error" in corps and "beaucoup de monde" in corps
    from core import db
    assert int(db.get_profile(USER_ID).get("coach_quota_count") or 0) == 0
    plein.release()
    r = logged_in.post("/coach/ask", json={"message": "Combien de séries ?"},
                       headers={"X-CSRFToken": CSRF, "Accept": "text/event-stream"})
    assert "event: done" in r.get_data(as_text=True)
    assert plein.acquire(blocking=False), "le flux terminé rend sa place"
