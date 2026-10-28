"""Limiteur de débit face à un Redis en panne (constat du 23/10).

Le limiteur (`core/limiter.py`) tentait Redis à chaque requête : avec un Redis
injoignable, chaque page attendait le délai de connexion (2 s), et face à un
Redis qui accepte la connexion sans répondre, elle pendait sans fin (aucun
`socket_timeout`). Les limites, elles, sautaient : `swallow_errors` laissait
tout passer.

Depuis, il bascule sur la mémoire du processus à la première erreur, garde les
mêmes limites, puis revient sur Redis quand il répond de nouveau.

Les pannes sont de vrais serveurs TCP : un port fermé (refus immédiat), un
serveur dont la file d'attente est pleine (la connexion n'aboutit jamais) et un
serveur qui accepte sans jamais répondre. Le retour passe par un relais qu'on
coupe puis rouvre devant un vrai Redis : `REDIS_TEST_URL=redis://…` s'il est
donné, sinon un `redis-server` lancé pour l'occasion ; sans l'un ni l'autre, ce
test-là s'ignore (le faux Redis TCP de fakeredis ne répond pas aux scripts de
`limits`).
"""
import os
import shutil
import socket
import subprocess
import sys
import threading
import time

import pytest
import redis
from flask import Flask

from core.limiter import DELAI_REDIS, creer_limiteur

# La requête qui découvre la panne paie au plus deux fois le délai du client
# Redis (aucune nouvelle tentative) : l'échec, puis parfois une sonde dans la
# foulée. Plus une marge pour une machine de CI chargée.
PREMIERE_MAX = 2 * DELAI_REDIS + 0.4
RAPIDE = 0.3            # une page servie sans attendre Redis
ATTENTE_MAX = 10        # au-delà, la requête est déclarée bloquée


# ── Pannes simulées ──────────────────────────────────────────────

def _port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Muet:
    """Accepte les connexions et ne répond jamais."""

    def __init__(self):
        self.ecoute = socket.socket()
        self.ecoute.bind(("127.0.0.1", 0))
        self.ecoute.listen(16)
        self.port = self.ecoute.getsockname()[1]
        self.clients = []
        threading.Thread(target=self._accepter, daemon=True).start()

    def _accepter(self):
        while True:
            try:
                c, _ = self.ecoute.accept()
            except OSError:
                return
            self.clients.append(c)

    def fermer(self):
        self.ecoute.close()
        for c in self.clients:
            c.close()


class _Sourd:
    """File d'attente pleine : les connexions suivantes n'aboutissent jamais."""

    def __init__(self):
        self.ecoute = socket.socket()
        self.ecoute.bind(("127.0.0.1", 0))
        self.ecoute.listen(0)
        self.port = self.ecoute.getsockname()[1]
        self.remplissage = []
        for _ in range(4):
            c = socket.socket()
            c.setblocking(False)
            try:
                c.connect(("127.0.0.1", self.port))
            except BlockingIOError:
                pass
            self.remplissage.append(c)
        # La file est bien pleine : sinon le test ne prouverait rien.
        sonde = socket.socket()
        sonde.settimeout(0.3)
        try:
            sonde.connect(("127.0.0.1", self.port))
            pytest.skip("impossible de remplir la file d'attente TCP ici")
        except (TimeoutError, socket.timeout):
            pass
        finally:
            sonde.close()

    def fermer(self):
        for c in self.remplissage:
            c.close()
        self.ecoute.close()


class _Relais:
    """Relais TCP vers un Redis, qu'on coupe et rouvre à volonté."""

    def __init__(self, hote, port):
        self.cible = (hote, port)
        self.ouvert = True
        self.ecoute = socket.socket()
        self.ecoute.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ecoute.bind(("127.0.0.1", 0))
        self.ecoute.listen(16)
        self.port = self.ecoute.getsockname()[1]
        self.paires = []
        threading.Thread(target=self._accepter, daemon=True).start()

    def _accepter(self):
        while True:
            try:
                c, _ = self.ecoute.accept()
            except OSError:
                return
            if not self.ouvert:
                c.close()
                continue
            r = socket.create_connection(self.cible)
            self.paires.append((c, r))
            for a, b in ((c, r), (r, c)):
                threading.Thread(target=self._pomper, args=(a, b), daemon=True).start()

    @staticmethod
    def _pomper(a, b):
        try:
            while True:
                d = a.recv(65536)
                if not d:
                    break
                b.sendall(d)
        except OSError:
            pass
        for s in (a, b):
            try:
                s.close()
            except OSError:
                pass

    def couper(self):
        self.ouvert = False
        for c, r in self.paires:
            for s in (c, r):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                    s.close()
                except OSError:
                    pass
        self.paires.clear()

    def rouvrir(self):
        self.ouvert = True

    def fermer(self):
        self.couper()
        self.ecoute.close()


# ── App de test : le limiteur de production, sur un stockage choisi ───

def _app(storage_uri):
    app = Flask(__name__)
    limiteur = creer_limiteur(storage_uri)

    @app.route("/page")
    def page():
        return "ok"

    @app.route("/bridee")
    @limiteur.limit("3 per minute")
    def bridee():
        return "ok"

    limiteur.init_app(app)
    return app.test_client()


def _get(client, chemin):
    """(statut, durée) ; échoue si la requête ne revient pas."""
    res = {}

    def faire():
        t = time.monotonic()
        res["statut"] = client.get(chemin).status_code
        res["duree"] = time.monotonic() - t

    fil = threading.Thread(target=faire, daemon=True)
    fil.start()
    fil.join(ATTENTE_MAX)
    assert not fil.is_alive(), f"{chemin} bloquée plus de {ATTENTE_MAX} s : Redis attendu sans fin"
    return res["statut"], res["duree"]


@pytest.fixture()
def muet():
    s = _Muet()
    yield s
    s.fermer()


@pytest.fixture()
def sourd():
    s = _Sourd()
    yield s
    s.fermer()


@pytest.fixture()
def redis_cible():
    """Un vrai Redis : REDIS_TEST_URL, sinon un redis-server local et jetable."""
    url = os.getenv("REDIS_TEST_URL", "")
    if url:
        client = redis.Redis.from_url(url)
        kw = client.connection_pool.connection_kwargs
        client.flushdb()
        yield kw.get("host", "localhost"), kw.get("port", 6379), kw.get("db", 0), client
        client.flushdb()
        return
    binaire = shutil.which("redis-server")
    if not binaire:
        pytest.skip("ni REDIS_TEST_URL ni redis-server")
    port = _port_libre()
    proc = subprocess.Popen([binaire, "--port", str(port), "--save", "", "--appendonly", "no"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = redis.Redis(host="127.0.0.1", port=port)
    fin = time.monotonic() + 5
    while True:
        try:
            client.ping()
            break
        except redis.ConnectionError:
            if time.monotonic() > fin:
                proc.kill()
                pytest.skip("redis-server n'a pas démarré")
            time.sleep(0.05)
    yield "127.0.0.1", port, 0, client
    proc.kill()
    proc.wait()


@pytest.fixture()
def relais(redis_cible):
    hote, port, db, client = redis_cible
    r = _Relais(hote, port)
    yield r, f"redis://127.0.0.1:{r.port}/{db}", client
    r.fermer()


def _cles(client):
    return client.keys("LIMITS*")


# ── Une panne ne ralentit plus les pages ─────────────────────────

@pytest.mark.parametrize("panne", ["muet", "sourd"])
def test_redis_en_panne_une_page_repond_vite(panne, request):
    serveur = request.getfixturevalue(panne)
    client = _app(f"redis://127.0.0.1:{serveur.port}/0")

    statut, duree = _get(client, "/page")
    assert statut == 200
    assert duree < PREMIERE_MAX, (
        f"première page en {duree:.2f} s : le délai du client Redis n'est pas borné")

    for _ in range(5):
        statut, duree = _get(client, "/page")
        assert statut == 200
        assert duree < RAPIDE, (
            f"page en {duree:.2f} s alors que la panne est connue : "
            "chaque requête retente Redis")


@pytest.mark.skipif(sys.platform == "win32", reason=(
    "sous Windows, un port fermé ne refuse la connexion qu'au bout de 2 s (mesuré) : "
    "le client expire à 0,5 s ; ce test décrit le refus immédiat de Linux, celui de la production"))
def test_redis_arrete_une_page_repond_vite():
    client = _app(f"redis://127.0.0.1:{_port_libre()}/0")
    for _ in range(5):
        statut, duree = _get(client, "/page")
        assert statut == 200
        assert duree < RAPIDE


# ── Les limites tiennent pendant la panne ────────────────────────

def test_redis_arrete_les_limites_s_appliquent_en_memoire():
    client = _app(f"redis://127.0.0.1:{_port_libre()}/0")
    codes = [_get(client, "/bridee")[0] for _ in range(4)]
    assert codes == [200, 200, 200, 429], (
        "Redis en panne, la sur-limite d'une route ne doit pas sauter")


def test_redis_arrete_la_limite_par_defaut_s_applique_en_memoire():
    client = _app(f"redis://127.0.0.1:{_port_libre()}/0")
    codes = [client.get("/page").status_code for _ in range(61)]
    assert codes[:60] == [200] * 60
    assert codes[60] == 429


def test_redis_muet_les_limites_s_appliquent_en_memoire(muet):
    client = _app(f"redis://127.0.0.1:{muet.port}/0")
    codes = [_get(client, "/bridee")[0] for _ in range(4)]
    assert codes == [200, 200, 200, 429]


# ── Redis revenu : retour au stockage partagé ────────────────────

def test_redis_revenu_le_compteur_redevient_partage(relais):
    r, url, redis_client = relais
    client = _app(url)

    assert _get(client, "/page")[0] == 200
    assert _cles(redis_client), "Redis joignable : le compteur doit y être"

    r.couper()
    redis_client.flushdb()
    for _ in range(3):
        statut, duree = _get(client, "/page")
        assert statut == 200
        assert duree < PREMIERE_MAX
    assert not _cles(redis_client), "relais coupé : rien n'a pu atteindre Redis"

    # flask-limiter sonde Redis après 1, 2, 4… s : il revient en quelques secondes.
    r.rouvrir()
    fin = time.monotonic() + 8
    while not _cles(redis_client):
        assert time.monotonic() < fin, "Redis revenu, le limiteur ne l'a pas repris"
        assert _get(client, "/page")[0] == 200
        time.sleep(0.2)

    # Partagé de nouveau : deux instances, un seul compteur pour la sur-limite.
    autre = _app(url)
    codes = [_get(client, "/bridee")[0], _get(autre, "/bridee")[0],
             _get(client, "/bridee")[0], _get(autre, "/bridee")[0]]
    assert codes == [200, 200, 200, 429], (
        "après le retour de Redis, les instances doivent partager le compteur")
