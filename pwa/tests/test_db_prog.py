"""Verrou optimiste sur programs.data, cache borné, purge des bilans."""
import pytest

import core.db as db
from tests.conftest import USER_ID


def _db_row(fake):
    return next(r for r in fake.tables["programs"] if r["user_id"] == USER_ID)


def test_save_prog_bumps_version(fake_db):
    db.save_prog(USER_ID, {"Push": []})          # 1re écriture : upsert (pas de base)
    assert _db_row(fake_db)["version"] == 1
    prog = db.get_prog(USER_ID)
    prog["Pull"] = []
    db.save_prog(USER_ID, prog)
    row = _db_row(fake_db)
    assert row["version"] == 2
    assert set(row["data"]) == {"Push", "Pull"}


def test_save_prog_conflict_merges_other_workers_write(fake_db):
    """Worker A lit le blob (cache), worker B écrit le défi hebdo entre-temps,
    A termine sa séance : l'écriture de B doit survivre."""
    db.save_prog(USER_ID, {"Push": [], "_session_notes": {}})
    prog_a = db.get_prog(USER_ID)                 # A lit v1

    # B (autre process) écrit directement en DB et bump la version
    row = _db_row(fake_db)
    row["data"] = {"Push": [], "_session_notes": {}, "_challenges_done": ["w38"]}
    row["version"] = 2

    prog_a["_session_notes"]["Push|2026-09-21"] = {"rating": 4}
    db.save_prog(USER_ID, prog_a)

    row = _db_row(fake_db)
    assert row["version"] == 3
    assert row["data"]["_challenges_done"] == ["w38"]          # écriture de B conservée
    assert row["data"]["_session_notes"] == {"Push|2026-09-21": {"rating": 4}}


def test_save_prog_conflict_merges_nested_dicts(fake_db):
    db.save_prog(USER_ID, {"_session_notes": {"a": 1}})
    prog_a = db.get_prog(USER_ID)
    row = _db_row(fake_db)
    row["data"] = {"_session_notes": {"a": 1, "b": 2}}
    row["version"] = 2
    prog_a["_session_notes"]["c"] = 3
    db.save_prog(USER_ID, prog_a)
    assert _db_row(fake_db)["data"]["_session_notes"] == {"a": 1, "b": 2, "c": 3}


def test_save_prog_conflict_our_deletion_wins(fake_db):
    db.save_prog(USER_ID, {"Push": [], "Legs": []})
    prog_a = db.get_prog(USER_ID)
    row = _db_row(fake_db)
    row["data"] = {"Push": [], "Legs": [], "_badges": ["x"]}
    row["version"] = 2
    prog_a.pop("Legs")
    db.save_prog(USER_ID, prog_a)
    assert _db_row(fake_db)["data"] == {"Push": [], "_badges": ["x"]}


def test_save_prog_without_version_column_falls_back_to_upsert(fake_db):
    """Migration v32 pas encore appliquée → comportement historique."""
    fake_db.tables["programs"] = [{"id": 1, "user_id": USER_ID, "data": {"Push": []}}]
    prog = db.get_prog(USER_ID)
    prog["Pull"] = []
    db.save_prog(USER_ID, prog)
    assert _db_row(fake_db)["data"] == {"Push": [], "Pull": []}


def test_cache_is_bounded(fake_db, monkeypatch):
    # Le plafond est lu par `_cache_set`, qui vit dans core.db_base : c'est
    # donc ce module qu'il faut borner, pas la façade qui le réexporte.
    import core.db_base as db_base
    monkeypatch.setattr(db_base, "_CACHE_MAX", 3)
    for i in range(10):
        db._cache_set(f"k{i}", i)
    assert list(db._data_cache) == ["k7", "k8", "k9"]
    assert db._cache_get("k8") == 8
    assert list(db._data_cache)[-1] == "k8"       # touché → devient le plus récent


def test_purge_old_session_notes():
    from datetime import date
    from core.seance_calques import _purge_old_session_notes
    prog = {"_session_notes": {
        "Push|2026-09-20": {"rating": 5},   # hier
        "Pull|2026-06-01": {"rating": 3},   # > 12 semaines
        "garbage": {"rating": 1},           # clé sans date → retirée
    }}
    assert _purge_old_session_notes(prog, today=date(2026, 9, 21)) is True
    assert list(prog["_session_notes"]) == ["Push|2026-09-20"]
    assert _purge_old_session_notes(prog, today=date(2026, 9, 21)) is False
    assert _purge_old_session_notes({}) is False


def test_deux_requetes_du_meme_worker_ne_se_volent_pas_leur_base(fake_db):
    """Audit du 30/09, I7 (reproduit R11). Deux requêtes du même
    utilisateur, servies par deux threads du même worker : A lit, B lit, A
    grave un badge, B enregistre un réglage. La base du verrou était partagée
    par le process : B écrivait « depuis » la version de A, l'update passait,
    et le badge disparaissait. Chaque requête a désormais sa propre base."""
    import app as appmod
    db.save_prog(USER_ID, {"Push": [], "_settings": {}})
    db.clear_user_cache(USER_ID)

    req_a = appmod.app.app_context()
    req_b = appmod.app.app_context()

    req_a.push()
    prog_a = db.get_prog(USER_ID)                  # A lit v1
    req_a.pop()

    req_b.push()
    prog_b = db.get_prog(USER_ID)                  # B lit v1
    req_b.pop()

    req_a.push()
    prog_a["_badges"] = ["first_session"]
    db.save_prog(USER_ID, prog_a)                  # A écrit v2
    req_a.pop()

    req_b.push()
    prog_b["_settings"] = {"auto_rest_timer": False}
    db.save_prog(USER_ID, prog_b)                  # B écrit « depuis v1 » → conflit → fusion
    req_b.pop()

    data = _db_row(fake_db)["data"]
    assert data.get("_badges") == ["first_session"], "le badge de A a survécu"
    assert data["_settings"] == {"auto_rest_timer": False}


@pytest.mark.parametrize("redis,demandes,attendus", [
    ("", "4", 1),                          # sans Redis : un seul processus, quoi qu'on demande
    ("pas-une-url", "4", 1),
    ("redis://cache.railway.internal:6379", "", 1),
    ("redis://cache.railway.internal:6379", "3", 3),
])
def test_plusieurs_processus_seulement_avec_redis(monkeypatch, redis, demandes, attendus):
    """Audit du 30/09, I8 : avec plusieurs processus et un cache par processus,
    chacun servait sa version de l'historique jusqu'à 60 s après une écriture
    faite ailleurs. Le cache est maintenant cohérent via Redis
    (`core/partage.py`) ; sans Redis, gunicorn.conf.py garde UN processus, et
    une variable d'environnement seule ne peut pas changer ça."""
    import json
    import runpy
    from pathlib import Path
    racine = Path(__file__).resolve().parents[2]
    cmd = json.loads((racine / "railway.json").read_text(encoding="utf-8"))["deploy"]["startCommand"]
    assert "--workers" not in cmd, "la ligne de commande écraserait gunicorn.conf.py"
    assert "WEB_CONCURRENCY" not in cmd
    monkeypatch.setenv("REDIS_URL", redis)
    monkeypatch.setenv("WEB_CONCURRENCY", demandes)
    assert runpy.run_path(str(racine / "pwa" / "gunicorn.conf.py"))["workers"] == attendus


def test_le_cache_supporte_des_threads_concurrents():
    import threading
    import core.db_base as b
    erreurs = []

    def travail(n):
        try:
            for i in range(300):
                k = f"hist:u{(n * 7 + i) % 250}"
                b._cache_set(k, [i])
                b._cache_get(k)
                if i % 5 == 0:
                    b._cache_invalidate(k)
        except Exception as e:  # pragma: no cover - c'est ce qu'on guette
            erreurs.append(e)

    fils = [threading.Thread(target=travail, args=(n,)) for n in range(16)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    assert not erreurs, erreurs
    assert len(b._data_cache) <= b._CACHE_MAX
