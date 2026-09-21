"""Verrou optimiste sur programs.data, cache borné, purge des bilans."""
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
    monkeypatch.setattr(db, "_CACHE_MAX", 3)
    for i in range(10):
        db._cache_set(f"k{i}", i)
    assert list(db._data_cache) == ["k7", "k8", "k9"]
    assert db._cache_get("k8") == 8
    assert list(db._data_cache)[-1] == "k8"       # touché → devient le plus récent


def test_purge_old_session_notes():
    from datetime import date
    from routes.seance import _purge_old_session_notes
    prog = {"_session_notes": {
        "Push|2026-09-20": {"rating": 5},   # hier
        "Pull|2026-06-01": {"rating": 3},   # > 12 semaines
        "garbage": {"rating": 1},           # clé sans date → retirée
    }}
    assert _purge_old_session_notes(prog, today=date(2026, 9, 21)) is True
    assert list(prog["_session_notes"]) == ["Push|2026-09-20"]
    assert _purge_old_session_notes(prog, today=date(2026, 9, 21)) is False
    assert _purge_old_session_notes({}) is False
