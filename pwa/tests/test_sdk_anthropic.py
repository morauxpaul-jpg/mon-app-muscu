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


# Haiku 5.5 réfléchit par défaut : sa réponse commence par un bloc `thinking`,
# dont le texte est vide (seule la signature revient). Le faux serveur fait de
# même, pour que chaque test vérifie que ce bloc n'entre pas dans la réponse.
REFLEXION = {"type": "thinking", "thinking": "", "signature": "sig_test"}
REFUS = {"type": "refusal", "category": "general_harms", "explanation": None}


class _Serveur(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requetes: list = []
    erreur = None
    refus = False        # refus de sécurité, après le début du texte

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
        fin = {"stop_reason": "refusal" if _Serveur.refus else "end_turn", "stop_sequence": None,
               "stop_details": REFUS if _Serveur.refus else None}
        morceaux = MORCEAUX[:1] if _Serveur.refus else MORCEAUX
        message = {"id": "msg_test", "type": "message", "role": "assistant",
                   "model": corps["model"], **fin,
                   "usage": {"input_tokens": 10, "output_tokens": 12}}
        if not corps.get("stream"):
            return self._envoyer(200, {**message, "content": [
                REFLEXION, {"type": "text", "text": "".join(morceaux)}]})
        evenements = [("message_start", {"type": "message_start", "message": {
                          **message, "content": [], "stop_reason": None, "stop_details": None,
                          "usage": {"input_tokens": 10, "output_tokens": 1}}}),
                      ("content_block_start", {"type": "content_block_start", "index": 0,
                                               "content_block": {**REFLEXION, "signature": ""}}),
                      ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                               "delta": {"type": "signature_delta",
                                                         "signature": "sig_test"}}),
                      ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                      ("content_block_start", {"type": "content_block_start", "index": 1,
                                               "content_block": {"type": "text", "text": ""}})]
        evenements += [("content_block_delta", {"type": "content_block_delta", "index": 1,
                                                "delta": {"type": "text_delta", "text": m}})
                       for m in morceaux]
        evenements += [("content_block_stop", {"type": "content_block_stop", "index": 1}),
                       ("message_delta", {"type": "message_delta", "delta": fin,
                                          "usage": {"output_tokens": 12}}),
                       ("message_stop", {"type": "message_stop"})]
        sse = "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in evenements)
        self._envoyer(200, sse.encode(), "text/event-stream")


@pytest.fixture()
def api(monkeypatch):
    serveur = ThreadingHTTPServer(("127.0.0.1", 0), _Serveur)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    _Serveur.requetes, _Serveur.erreur, _Serveur.refus = [], None, False
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
    assert api.requetes[1]["corps"]["max_tokens"] == coach_memory.MAX_TOKENS


def test_le_generateur_passe_par_le_vrai_sdk(api):
    from routes.generator import _appeler_ia
    assert _appeler_ia("Un programme push/pull/legs.") == ("".join(MORCEAUX), None)
    api.erreur = "surcharge"
    texte, (corps, code) = _appeler_ia("Un programme push/pull/legs.")
    assert texte is None and code == 502 and "très sollicité" in corps["error"]


# ── Passage à Haiku 5.5 (25/10) ──────────────────────────────────


def test_chaque_appel_part_avec_les_reglages_de_haiku_5_5(api, fake_db, logged_in):
    """Modèle, effort, plafonds : ce qui part réellement dans la requête."""
    from core import coach_memory, debrief, ia
    from routes import coach, generator
    _seed(fake_db)
    _evenements(_demander(logged_in))
    _demander(logged_in, stream=False)
    debrief.generate("sk-test", {"seance": "Push", "date": "2026-10-25", "volume": 1, "sets": 1,
                                 "reps": 1, "exos": {}})
    coach_memory.build_summary(anthropic.Anthropic(api_key="sk-test"), coach.MODEL, "",
                               [{"role": "user", "content": "J'ai mal au genou."}])
    generator._appeler_ia("Un programme.")
    corps = [r["corps"] for r in api.requetes]
    assert [c["model"] for c in corps] == ["claude-haiku-5-5"] * 5
    assert [c["output_config"] for c in corps] == [{"effort": "low"}] * 4 + [{"effort": "medium"}]
    assert [c["max_tokens"] for c in corps] == [coach.MAX_TOKENS, coach.MAX_TOKENS,
                                                debrief.MAX_TOKENS, coach_memory.MAX_TOKENS,
                                                generator.MAX_TOKENS]
    for c in corps:
        # Refusés par Haiku 5.5 : budget de réflexion, échantillonnage, réponse amorcée.
        assert "thinking" not in c and not {"temperature", "top_p", "top_k"} & set(c)
        assert c["messages"][-1]["role"] == "user"
    assert ia.MODEL == coach.MODEL == debrief.MODEL == generator.MODEL


def test_les_tokens_de_chaque_appel_sont_journalises(api, fake_db, logged_in, caplog):
    _seed(fake_db)
    with caplog.at_level("INFO", logger="core.ia"):
        _evenements(_demander(logged_in))
        _demander(logged_in, stream=False)
    lignes = [r.getMessage() for r in caplog.records if r.name == "core.ia"]
    assert lignes == ["ia coach : 10 tokens en entrée, 12 en sortie, fin=end_turn"] * 2


def _quota(fake_db):
    profil = next(p for p in fake_db.tables["profiles"] if p["id"] == USER_ID)
    return int(profil.get("coach_quota_count") or 0)


def test_un_refus_en_cours_de_flux_efface_le_debut_et_rend_la_question(api, fake_db, logged_in):
    from routes.coach import REFUS
    _seed(fake_db)
    api.refus = True
    evenements = _evenements(_demander(logged_in))
    assert [e for e, _ in evenements] == ["delta", "error"]
    assert evenements[-1][1] == {"error": REFUS, "retirer": True}
    assert _quota(fake_db) == 0
    assert not fake_db.tables.get("coach_messages")       # rien n'est gardé


def test_un_refus_sans_flux_rend_la_question(api, fake_db, logged_in):
    from routes.coach import REFUS
    _seed(fake_db)
    api.refus = True
    r = _demander(logged_in, stream=False)
    assert r.status_code == 422 and r.get_json() == {"error": REFUS}
    assert _quota(fake_db) == 0
    assert not fake_db.tables.get("coach_messages")


def test_un_refus_ne_donne_ni_bilan_ni_memoire_ni_programme(api):
    from core import coach_memory, debrief
    from routes.generator import _appeler_ia
    api.refus = True
    assert debrief.generate("sk-test", {"seance": "Push", "date": "2026-10-25", "volume": 1,
                                        "sets": 1, "reps": 1, "exos": {}}) is None
    assert coach_memory.build_summary(anthropic.Anthropic(api_key="sk-test"), debrief.MODEL,
                                      "note", [{"role": "user", "content": "Bonjour"}]) is None
    texte, (corps, code) = _appeler_ia("Un programme.")
    assert texte is None and code == 422 and "Reformule" in corps["error"]
