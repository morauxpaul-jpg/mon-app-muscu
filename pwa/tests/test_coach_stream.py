"""Coach : réponse en flux, mémoire persistante, messages d'erreur.

Le coach mettait 3 à 8 secondes avant d'afficher quoi que ce soit, coupait
ses réponses à 500 tokens, et repartait de zéro à chaque conversation.
"""
import json
import sys
import types

from conftest import USER_ID, CSRF
from core import coach_memory


# ── Faux client Anthropic ────────────────────────────────────────


class _FakeStream:
    def __init__(self, parts):
        self.text_stream = iter(parts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeMessages:
    def __init__(self, parts, calls):
        self._parts = parts
        self._calls = calls

    def stream(self, **kwargs):
        self._calls.append(kwargs)
        return _FakeStream(self._parts)

    def create(self, **kwargs):
        self._calls.append(kwargs)
        text = "".join(self._parts)
        return types.SimpleNamespace(
            content=[types.SimpleNamespace(text=text)])


class _FakeAnthropic:
    parts = ["Pour progresser ", "au développé couché, ", "ajoute 2,5 kg."]
    calls: list = []

    def __init__(self, api_key=None):
        self.messages = _FakeMessages(self.parts, self.calls)


def _install_fake_anthropic(monkeypatch, parts=None):
    _FakeAnthropic.calls = []
    if parts is not None:
        _FakeAnthropic.parts = parts
    module = types.ModuleType("anthropic")
    module.Anthropic = _FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", module)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    return _FakeAnthropic


def _seed(fake, memory=None):
    profile = {"id": USER_ID, "tier": "vip"}
    if memory:
        profile["coach_memory"] = memory
    fake.table("profiles").insert(profile).execute()
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
    }}).execute()


def _ask(client, message="Comment progresser ?", stream=True, conv=None):
    headers = {"X-CSRFToken": CSRF}
    if stream:
        headers["Accept"] = "text/event-stream"
    return client.post("/coach/ask", json={"message": message,
                                           "conversation_id": conv},
                       headers=headers)


def _events(resp):
    """[(event, data)] depuis un corps SSE."""
    out = []
    for block in resp.get_data(as_text=True).split("\n\n"):
        if not block.strip():
            continue
        event, payload = "message", ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                payload += line[5:].strip()
        if payload:
            out.append((event, json.loads(payload)))
    return out


# ── Streaming ────────────────────────────────────────────────────


def test_la_reponse_arrive_en_flux(fake_db, logged_in, monkeypatch):
    _install_fake_anthropic(monkeypatch)
    _seed(fake_db)
    r = _ask(logged_in)
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["Content-Type"]
    events = _events(r)
    deltas = [d["text"] for e, d in events if e == "delta"]
    assert deltas == ["Pour progresser ", "au développé couché, ", "ajoute 2,5 kg."]
    assert [e for e, _ in events][-1] == "done"


def test_le_flux_nest_pas_mis_en_tampon_par_le_proxy(fake_db, logged_in, monkeypatch):
    """Sans ces en-têtes, le proxy accumule tout et le flux perd son intérêt."""
    _install_fake_anthropic(monkeypatch)
    _seed(fake_db)
    r = _ask(logged_in)
    assert r.headers["X-Accel-Buffering"] == "no"
    assert "no-cache" in r.headers["Cache-Control"]


def test_la_conversation_est_creee_a_la_fin_du_flux(fake_db, logged_in, monkeypatch):
    _install_fake_anthropic(monkeypatch)
    _seed(fake_db)
    done = [d for e, d in _events(_ask(logged_in)) if e == "done"][0]
    assert done["new_conversation"] is True
    assert done["conversation_id"]
    assert done["quota_remaining"] == 14
    # Les deux messages du tour sont enregistrés.
    roles = [m["role"] for m in fake_db.tables["coach_messages"]]
    assert roles == ["user", "assistant"]


def test_sans_flux_la_reponse_json_fonctionne_toujours(fake_db, logged_in, monkeypatch):
    """Repli pour un client qui ne sait pas lire le flux."""
    _install_fake_anthropic(monkeypatch)
    _seed(fake_db)
    r = _ask(logged_in, stream=False)
    assert r.status_code == 200
    data = json.loads(r.data)
    assert "développé couché" in data["reply"]
    assert data["conversation_id"]


def test_les_reponses_ne_sont_plus_coupees_a_500_tokens(fake_db, logged_in, monkeypatch):
    fake_anthropic = _install_fake_anthropic(monkeypatch)
    _seed(fake_db)
    _ask(logged_in)
    assert fake_anthropic.calls[0]["max_tokens"] >= 1000


# ── Mémoire ──────────────────────────────────────────────────────


def test_la_memoire_est_injectee_dans_le_prompt(fake_db, logged_in, monkeypatch):
    fake_anthropic = _install_fake_anthropic(monkeypatch)
    _seed(fake_db, memory="Douleur épaule droite depuis mars.\nS'entraîne le matin.")
    _ask(logged_in)
    system = fake_anthropic.calls[0]["system"]
    assert "Douleur épaule droite" in system
    assert "CE QUE TU SAIS DÉJÀ DE LUI" in system


def test_sans_memoire_le_prompt_reste_propre(fake_db, logged_in, monkeypatch):
    fake_anthropic = _install_fake_anthropic(monkeypatch)
    _seed(fake_db)
    _ask(logged_in)
    assert "CE QUE TU SAIS DÉJÀ" not in fake_anthropic.calls[0]["system"]


def test_la_memoire_se_met_a_jour_apres_plusieurs_echanges(fake_db, logged_in, monkeypatch):
    _install_fake_anthropic(monkeypatch, parts=["Note mise à jour."])
    _seed(fake_db)
    conv = None
    for i in range(4):
        events = _events(_ask(logged_in, f"Question {i}", conv=conv))
        conv = [d for e, d in events if e == "done"][0]["conversation_id"]
    profile = next(p for p in fake_db.tables["profiles"] if p["id"] == USER_ID)
    assert profile.get("coach_memory")


def test_pas_de_resume_des_le_premier_message(fake_db, logged_in, monkeypatch):
    """Condenser un « bonjour » coûte un appel API pour rien."""
    _install_fake_anthropic(monkeypatch)
    _seed(fake_db)
    _ask(logged_in)
    profile = next(p for p in fake_db.tables["profiles"] if p["id"] == USER_ID)
    assert not profile.get("coach_memory")


def test_should_update_attend_assez_dechanges():
    peu = [{"role": "user", "content": "salut"}]
    assert not coach_memory.should_update(peu)
    assez = [{"role": "user", "content": f"q{i}"} for i in range(4)]
    assert coach_memory.should_update(assez)


def test_la_note_est_bornee_en_longueur():
    class _C:
        class messages:
            @staticmethod
            def create(**k):
                return types.SimpleNamespace(
                    content=[types.SimpleNamespace(text="x" * 5000)])
    note = coach_memory.build_summary(
        _C(), "m", "", [{"role": "user", "content": "bonjour"}])
    assert len(note) <= coach_memory.MAX_CHARS


# ── Erreurs ──────────────────────────────────────────────────────


def test_les_erreurs_ne_parlent_plus_de_linfra(fake_db, logged_in, monkeypatch):
    """« Vérifie ANTHROPIC_API_KEY dans Railway » n'apprend rien à
    l'utilisateur et fait amateur au moment où il paye."""
    from routes.coach import _user_error
    msg = _user_error("authentication_error: invalid x-api-key")
    assert "Railway" not in msg and "ANTHROPIC" not in msg
    assert "indisponible" in msg.lower()

    msg = _user_error("Your credit balance is too low")
    assert "console.anthropic.com" not in msg


def test_le_quota_est_rendu_si_le_flux_echoue(fake_db, logged_in, monkeypatch):
    class _Boom:
        def __init__(self, api_key=None):
            self.messages = self

        def stream(self, **k):
            raise RuntimeError("overloaded_error")

    module = types.ModuleType("anthropic")
    module.Anthropic = _Boom
    monkeypatch.setitem(sys.modules, "anthropic", module)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    _seed(fake_db)

    events = _events(_ask(logged_in))
    assert [e for e, _ in events] == ["error"]
    profile = next(p for p in fake_db.tables["profiles"] if p["id"] == USER_ID)
    assert int(profile.get("coach_quota_count") or 0) == 0   # quota rendu


def test_le_coach_reste_reserve_aux_membres_pro(fake_db, client):
    import time
    _seed(fake_db)
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time(), _csrf=CSRF)
    assert _ask(client).status_code == 403
