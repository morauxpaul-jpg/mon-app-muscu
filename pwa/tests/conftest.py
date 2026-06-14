"""Fixtures de test — fake Supabase en mémoire.

Permet de tester les routes Flask (logique semaine, sauvegarde, suppression
de compte…) sans base réelle : on stubbe le module `supabase` AVANT l'import
de l'app, puis on injecte un faux client requêtable dans core.db._client.

Lancer : cd pwa && python -m pytest tests -q
"""
import sys
import types
from pathlib import Path

# pwa/ doit être importable (core, routes, app)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Stub du paquet supabase avant tout import de core.db
_supabase_stub = types.ModuleType("supabase")


class _StubClient:  # pragma: no cover - jamais instancié
    pass


def _stub_create_client(url, key):
    raise RuntimeError("create_client ne doit pas être appelé dans les tests")


_supabase_stub.Client = _StubClient
_supabase_stub.create_client = _stub_create_client
sys.modules.setdefault("supabase", _supabase_stub)

import pytest  # noqa: E402


# ── Fake Supabase ────────────────────────────────────────────────


class FakeResponse:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class FakeQuery:
    def __init__(self, db, table):
        self._db = db
        self._table = table
        self._filters = []
        self._op = "select"
        self._payload = None
        self._order_col = None
        self._order_desc = False
        self._limit = None
        self._maybe_single = False

    # builders
    def select(self, *_args, **_kwargs):
        self._op = "select"
        return self

    def delete(self):
        self._op = "delete"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def upsert(self, payload):
        self._op = "upsert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def gte(self, col, val):
        self._filters.append(("gte", col, val))
        return self

    def lte(self, col, val):
        self._filters.append(("lte", col, val))
        return self

    def order(self, col, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    # exec
    def _match(self, row):
        for op, col, val in self._filters:
            cur = row.get(col)
            if op == "eq" and cur != val:
                return False
            if op == "gte" and not (cur is not None and str(cur) >= str(val)):
                return False
            if op == "lte" and not (cur is not None and str(cur) <= str(val)):
                return False
        return True

    def execute(self):
        rows = self._db.tables.setdefault(self._table, [])
        if self._op == "insert":
            payload = self._payload if isinstance(self._payload, list) else [self._payload]
            for p in payload:
                p = dict(p)
                p.setdefault("id", self._db.next_id())
                rows.append(p)
            return FakeResponse(payload)
        if self._op == "upsert":
            payload = self._payload if isinstance(self._payload, list) else [self._payload]
            key = "id" if self._table == "profiles" else "user_id"
            for p in payload:
                p = dict(p)
                existing = next((r for r in rows if r.get(key) == p.get(key)), None)
                if existing:
                    existing.update(p)
                else:
                    p.setdefault("id", p.get("id") or self._db.next_id())
                    rows.append(p)
            return FakeResponse(payload)
        matched = [r for r in rows if self._match(r)]
        if self._op == "delete":
            self._db.tables[self._table] = [r for r in rows if not self._match(r)]
            return FakeResponse(matched)
        if self._op == "update":
            for r in matched:
                r.update(self._payload or {})
            return FakeResponse(matched)
        # select
        if self._order_col:
            matched = sorted(matched, key=lambda r: r.get(self._order_col) or 0,
                             reverse=self._order_desc)
        if self._limit is not None:
            matched = matched[: self._limit]
        if self._maybe_single:
            return FakeResponse(matched[0] if matched else None)
        return FakeResponse(matched)


class FakeAdmin:
    def __init__(self):
        self.deleted_users = []

    def delete_user(self, uid):
        self.deleted_users.append(uid)

    def get_user_by_id(self, uid):
        if uid in self.deleted_users:
            raise Exception("User not found")
        return types.SimpleNamespace(user=types.SimpleNamespace(id=uid))

    def list_users(self):
        return []


class FakeAuth:
    def __init__(self):
        self.admin = FakeAdmin()


class FakeSupabase:
    def __init__(self):
        self.tables = {}
        self.auth = FakeAuth()
        self._id = 0

    def next_id(self):
        self._id += 1
        return self._id

    def table(self, name):
        return FakeQuery(self, name)


# ── Fixtures ─────────────────────────────────────────────────────

USER_ID = "u-test-0001"
CSRF = "test-csrf-token"


@pytest.fixture()
def fake_db():
    import core.db as core_db
    fake = FakeSupabase()
    core_db._client = fake
    core_db._data_cache.clear()
    yield fake
    core_db._client = None
    core_db._data_cache.clear()


@pytest.fixture()
def client(fake_db):
    import app as appmod
    appmod.app.config["TESTING"] = True
    return appmod.app.test_client()


@pytest.fixture()
def logged_in(client):
    """Session authentifiée + onboardée + VIP PAYANT (is_vip_full) — cache frais
    → pas de hit DB."""
    import time
    with client.session_transaction() as s:
        s["user_id"] = USER_ID
        s["email"] = "test@example.com"
        s["onboarded"] = True
        s["is_vip"] = True
        s["is_vip_full"] = True
        s["is_vip_ts"] = time.time()
        s["_csrf"] = CSRF
    return client
