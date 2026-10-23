"""Le vrai paquet `anthropic`, contre un faux serveur Anthropic local.

Les autres tests remplacent le module `anthropic` par un faux : ils ne voient
rien de ce que change une nouvelle version du SDK (forme des requêtes, lecture
du flux, texte des erreurs que `_user_error` reconnaît). Ici, coach, bilan de
séance, mémoire et générateur passent par le SDK installé, jusqu'au HTTP.
Écrit pour le passage de 0.39 à 1.x (23/10) ; vert sur les deux.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anthropic
import pytest

from conftest import USER_ID, CSRF

MORCEAUX = ["Pour progresser ", "au développé couché, ", "ajoute 2,5 kg."]

# Réponses d'erreur de l'API, telles qu'elle les envoie.
ERREURS = {
    "auth": (401, "authentication_error", "invalid x-api-key"),
    "credit": (400, "invalid_request_error",
               "Your credit balance is too low to access the Anthropic API."),
    "surcharge": (529, "overloaded_error", "Overloaded"),
}


class _Serveur(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requetes: list = []
    erreur = None

    def log_message(self, *a):
        pass

    def _envoyer(self, code, corps, ctype="application/json", extra=None):
        data = corps if isinstance(corps, bytes) else json.dumps(corps).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Serveur.requetes.append({"chemin": self.path, "corps": corps,
                                  "version": self.headers.get("anthropic-version"),
                                  "cle": self.headers.get("x-api-key")})
        if _Serveur.erreur:
            code, type_, msg = ERREURS[_Serveur.erreur]
            # Sans `x-should-retry: false`, le SDK réessaierait 2 fois avec attente.
            return self._envoyer(code, {"type": "error", "error": {"type": type_, "message": msg}},
                                 extra={"x-should-retry": "false", "request-id": "req_test"})
        message = {"id": "msg_test", "type": "message", "role": "assistant",
                   "model": corps["model"], "stop_reason": "end_turn", "stop_sequence": None,
                   "usage": {"input_tokens": 10, "output_tokens": 12}}
        if not corps.get("stream"):
            return self._envoyer(200, {**message, "content": [{"type": "text", "text": "".join(MORCEAUX)}]})
        evenements = [("message_start", {"type": "message_start", "message": {
                          **message, "content": [], "stop_reason": None,
                          "usage": {"input_tokens": 10, "output_tokens": 1}}}),
                      ("content_block_start", {"type": "content_block_start", "index": 0,
                                               "content_block": {"type": "text", "text": ""}})]
        evenements += [("content_block_delta", {"type": "content_block_delta", "index": 0,
                                                "delta": {"type": "text_delta", "text": m}})
                       for m in MORCEAUX]
        evenements += [("content_block_stop", {"type": "content_block_stop", "index": 0}),
                       ("message_delta", {"type": "message_delta",
                                          "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                                          "usage": {"output_tokens": 12}}),
                       ("message_stop", {"type": "message_stop"})]
        sse = "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in evenements)
        self._envoyer(200, sse.encode(), "text/event-stream")


@pytest.fixture()
def api(monkeypatch):
    serveur = ThreadingHTTPServer(("127.0.0.1", 0), _Serveur)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    _Serveur.requetes, _Serveur.erreur = [], None
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{serveur.server_port}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    yield _Serveur
    serveur.shutdown()


def _seed(fake):
    fake.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
    }}).execute()


def _demander(client, stream=True):
    entetes = {"X-CSRFToken": CSRF}
    if stream:
        entetes["Accept"] = "text/event-stream"
    return client.post("/coach/ask", json={"message": "Comment progresser ?"}, headers=entetes)


def _evenements(resp):
    out = []
    for bloc in resp.get_data(as_text=True).split("\n\n"):
        lignes = dict(l.split(":", 1) for l in bloc.split("\n") if ":" in l)
        if "data" in lignes:
            out.append((lignes.get("event", "message").strip(), json.loads(lignes["data"])))
    return out


def test_le_coach_en_flux_passe_par_le_vrai_sdk(api, fake_db, logged_in):
    _seed(fake_db)
    evenements = _evenements(_demander(logged_in))
    assert [d["text"] for e, d in evenements if e == "delta"] == MORCEAUX
    assert evenements[-1][0] == "done"
    corps = api.requetes[0]["corps"]
    assert corps["stream"] is True and corps["max_tokens"] >= 1000
    assert "Développé couché" in corps["system"]
    assert corps["messages"][-1] == {"role": "user", "content": "Comment progresser ?"}
    assert not {"temperature", "top_p", "top_k"} & set(corps)
    assert api.requetes[0]["cle"] == "sk-test"
    assert api.requetes[0]["version"] == "2023-06-01"


def test_le_coach_sans_flux_passe_par_le_vrai_sdk(api, fake_db, logged_in):
    _seed(fake_db)
    r = _demander(logged_in, stream=False)
    assert r.status_code == 200
    assert r.get_json()["reply"] == "".join(MORCEAUX)
    assert "stream" not in api.requetes[0]["corps"]


@pytest.mark.parametrize("erreur, attendu", [
    ("auth", "momentanément indisponible"),
    ("credit", "momentanément indisponible"),
    ("surcharge", "très sollicité"),
])
def test_les_erreurs_de_l_api_sont_reconnues(api, fake_db, logged_in, erreur, attendu):
    """`_user_error` lit le texte de l'exception : il dépend du SDK."""
    _seed(fake_db)
    api.erreur = erreur
    evenements = _evenements(_demander(logged_in))
    assert [e for e, _ in evenements] == ["error"]
    assert attendu in evenements[0][1]["error"]
    assert len(api.requetes) == 1                     # pas de nouvelle tentative


def test_le_bilan_et_la_memoire_passent_par_le_vrai_sdk(api):
    from core import coach_memory, debrief
    faits = {"seance": "Push", "date": "2026-10-23", "volume": 2400, "sets": 9, "reps": 72,
             "exos": {"Développé couché": {"sets": 3, "reps": 24, "best": 80, "rpe": [8]}}}
    texte = debrief.generate("sk-test", faits)
    assert texte == "".join(MORCEAUX)
    assert api.requetes[0]["corps"]["max_tokens"] == debrief.MAX_TOKENS

    note = coach_memory.build_summary(
        anthropic.Anthropic(api_key="sk-test"), debrief.MODEL, "",
        [{"role": "user", "content": "J'ai mal au genou."},
         {"role": "assistant", "content": "Évite les squats lourds."}])
    assert note == "".join(MORCEAUX)
    assert api.requetes[1]["corps"]["max_tokens"] == 250


def test_le_generateur_passe_par_le_vrai_sdk(api):
    from routes.generator import _appeler_ia
    assert _appeler_ia("Un programme push/pull/legs.") == ("".join(MORCEAUX), None)
    api.erreur = "surcharge"
    texte, (corps, code) = _appeler_ia("Un programme push/pull/legs.")
    assert texte is None and code == 502 and "très sollicité" in corps["error"]
