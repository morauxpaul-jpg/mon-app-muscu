"""Fixtures de test — fake Supabase en mémoire.

Permet de tester les routes Flask (logique semaine, sauvegarde, suppression
de compte…) sans base réelle : on stubbe le module `supabase` AVANT l'import
de l'app, puis on injecte un faux client requêtable via core.db.use_client().

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
        self._on_conflict = None
        self._range = None
        self._colonnes = None

    # builders
    def select(self, *args, **_kwargs):
        """PostgREST ne renvoie QUE les colonnes demandées.

        Une fausse base qui ignore la liste laisse passer un code qui lit une
        colonne qu'il n'a pas demandée — et ça ne se voit qu'en production.
        On projette donc, comme le vrai.

        Ce que ça n'attrape PAS : un nom de colonne qui n'existe pas en base.
        Ici les lignes sont des dicts, donc une clé absente d'une ligne est
        indiscernable d'une colonne absente de la table ; elle ressort à
        `None`, comme le ferait PostgREST pour une colonne non renseignée.
        """
        self._op = "select"
        spec = str(args[0]) if args and args[0] else "*"
        # Les formes imbriquées (`table(col)`) ou renommées (`alias:col`)
        # dépassent ce que cette fausse base sait faire : on ne projette pas.
        if spec != "*" and not any(c in spec for c in "(:*"):
            self._colonnes = [c.strip() for c in spec.split(",") if c.strip()]
        return self

    def delete(self):
        self._op = "delete"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def upsert(self, payload, **kwargs):
        self._op = "upsert"
        self._payload = payload
        self._on_conflict = kwargs.get("on_conflict")
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

    def range(self, start, end):
        """Pagination PostgREST (bornes incluses)."""
        self._range = (int(start), int(end))
        return self

    # exec
    # Tables dont la clé primaire est un uuid en production. La fausse base
    # doit produire le même TYPE, sinon un code correct échoue ici (ou pire,
    # un code cassé passe) à cause d'une comparaison int/str.
    _UUID_PK = {"coach_conversations"}

    # Valeur par défaut de `max-rows` côté PostgREST/Supabase.
    MAX_ROWS = 1000

    def _apply_defaults(self, row):
        """Valeurs par défaut du schéma SQL (migration v32 : programs.version)."""
        if self._table == "programs":
            row.setdefault("version", 1)

    def _next_pk(self):
        if self._table in self._UUID_PK:
            import uuid as _uuid
            return str(_uuid.uuid4())
        return self._db.next_id()

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
            # PostgREST renvoie les lignes INSÉRÉES (avec leur id généré) :
            # plusieurs appels s'en servent (création de conversation, save_hist).
            inserted = []
            for p in payload:
                p = dict(p)
                p.setdefault("id", self._next_pk())
                self._apply_defaults(p)
                rows.append(p)
                inserted.append(dict(p))
            return FakeResponse(inserted)
        if self._op == "upsert":
            payload = self._payload if isinstance(self._payload, list) else [self._payload]
            key = self._on_conflict or ("id" if self._table == "profiles" else "user_id")
            keys = [k.strip() for k in key.split(",")]
            written = []
            for p in payload:
                p = dict(p)
                existing = next((r for r in rows
                                 if all(r.get(k) == p.get(k) for k in keys)), None)
                if existing:
                    existing.update(p)
                    written.append(dict(existing))
                else:
                    p.setdefault("id", p.get("id") or self._next_pk())
                    self._apply_defaults(p)
                    rows.append(p)
                    written.append(dict(p))
            return FakeResponse(written)
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
        # PostgREST plafonne les réponses à `max-rows` SANS le signaler : au-delà,
        # la liste est simplement tronquée. Le reproduire ici est le seul moyen
        # qu'un test remarque une lecture non paginée (sinon la fausse base
        # renvoie tout, et le bug n'apparaît qu'en production, une fois
        # l'historique assez long).
        if self._range is not None:
            start, end = self._range
            matched = matched[start:end + 1][:self.MAX_ROWS]
        else:
            matched = matched[:self.MAX_ROWS]
        if self._colonnes is not None:
            matched = [{c: r.get(c) for c in self._colonnes} for r in matched]
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


@pytest.fixture(autouse=True)
def quota_neuf():
    """Chaque test repart avec son quota de requêtes complet.

    Le limiteur est **process-wide** et compte par route : les 60 requêtes par
    minute de `/accueil` étaient partagées par TOUS les tests d'une exécution.
    Ajouter huit tests sur cette page suffisait à dépasser le seuil — et ce
    sont des tests voisins, écrits des mois plus tôt, qui recevaient un 429 et
    tombaient. Un échec qui désigne le mauvais coupable est pire qu'un échec.

    On remet le compteur à zéro plutôt que de désactiver le limiteur : un test
    qui voudrait vérifier qu'une route se bride peut toujours le faire, en
    envoyant lui-même sa rafale.
    """
    from core.limiter import limiter
    try:
        limiter.reset()
    except Exception:
        pass
    yield


@pytest.fixture()
def fake_db():
    import core.db as core_db
    fake = FakeSupabase()
    core_db.use_client(fake)
    core_db._data_cache.clear()
    core_db._prog_base.clear()
    yield fake
    core_db.use_client(None)
    core_db._data_cache.clear()
    core_db._prog_base.clear()


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
