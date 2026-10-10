"""État partagé entre instances : verrous, compteurs, générations de cache, valeurs.

Le cache, les verrous, les réservations de quota et les tâches IA vivaient dans
la mémoire du processus. Ils n'étaient justes qu'avec UNE instance (un worker
gunicorn, une réplique Railway) : avec deux, chacune avait son cache — l'une
servait l'ancien historique 60 s après une écriture sur l'autre —, ses verrous —
deux écritures croisées n'étaient plus mises en file —, et la page qui suivait
une génération IA tombait une fois sur deux sur l'instance qui ne la
connaissait pas (audit du 03/10, I11).

Ce module donne un seul endroit pour cet état :

* **Redis** si `REDIS_URL` est une vraie URL Redis (la variable sert déjà au
  limiteur de débit, `core/limiter.py`) : l'état est commun à toutes les
  instances ;
* **mémoire du processus** sinon : le comportement d'avant, correct tant qu'il
  n'y a qu'une instance. `verifier_au_demarrage()` crie si on en lance plusieurs.

Redis en panne ne casse pas l'app : chaque opération retombe sur la mémoire
pendant `PAUSE_PANNE` secondes, et le cache se coupe (`generations()` rend
None) plutôt que de servir une donnée qu'une autre instance a peut-être
changée. Les écritures, elles, restent garanties par la base (index unique v41,
verrou optimiste du programme).
"""
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager

logger = logging.getLogger(__name__)

PREFIXE = "mt:"
PAUSE_PANNE = 10.0          # secondes sans retenter Redis après une erreur
VERROU_TTL = 15.0           # un verrou abandonné (instance tuée) tombe seul
VERROU_ATTENTE = 20.0       # > VERROU_TTL : un verrou orphelin expire avant qu'on abandonne
GENERATION_TTL = 3600       # bien plus long que le cache (10 min) : voir generations()

# Libère le verrou seulement s'il porte encore notre jeton : un verrou expiré
# puis repris par une autre instance ne doit pas être effacé par l'ancienne.
_LIBERER = ("if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end")


def url_redis(env=None) -> str:
    """L'URL Redis si la variable en est vraiment une, sinon ''.

    Même règle que le limiteur : une valeur vide, un exemple laissé tel quel ou
    une faute de frappe retombe sur la mémoire au lieu d'empêcher le démarrage."""
    env = os.environ if env is None else env
    brut = (env.get("REDIS_URL") or "").strip().strip('"').strip("'")
    return brut if brut.startswith(("redis://", "rediss://")) else ""


# ── Mémoire du processus ─────────────────────────────────────────

class _Memoire:
    nom = "memoire"

    def __init__(self):
        self._valeurs = {}            # clé → (valeur, expire_a | None)
        self._etat = threading.Lock()
        self._verrous = [threading.Lock() for _ in range(64)]
        self._fenetres = {}           # clé → horodatages récents

    def _vivante(self, cle, maintenant):
        v = self._valeurs.get(cle)
        if v is not None and v[1] is not None and v[1] <= maintenant:
            self._valeurs.pop(cle, None)
            return None
        return v

    def verrou_local(self, cle):
        return self._verrous[hash(cle) % len(self._verrous)]

    def ajouter(self, cle, delta, ttl):
        with self._etat:
            v = self._vivante(cle, time.time())
            n = max(0, int(v[0] if v else 0) + delta)
            self._valeurs[cle] = (n, time.time() + ttl if ttl else None)
            return n

    def entiers(self, cles):
        with self._etat:
            maintenant = time.time()
            return [int((self._vivante(c, maintenant) or (0,))[0]) for c in cles]

    def ecrire(self, cle, valeur, ttl):
        with self._etat:
            self._valeurs[cle] = (json.dumps(valeur), time.time() + ttl if ttl else None)

    def lire(self, cle):
        with self._etat:
            v = self._vivante(cle, time.time())
        return json.loads(v[0]) if v else None

    def supprimer(self, cle):
        with self._etat:
            self._valeurs.pop(cle, None)

    def fenetre(self, cle, limite, secondes):
        """Fenêtre glissante : au plus `limite` passages sur `secondes`."""
        with self._etat:
            maintenant = time.time()
            recents = [t for t in self._fenetres.get(cle, []) if maintenant - t < secondes]
            if len(recents) >= limite:
                self._fenetres[cle] = recents
                return False
            self._fenetres[cle] = recents + [maintenant]
            return True


# ── Redis ────────────────────────────────────────────────────────

class _Redis:
    nom = "redis"

    def __init__(self, client):
        self.r = client

    def acquerir(self, cle, jeton, ttl):
        return bool(self.r.set(cle, jeton, nx=True, px=int(ttl * 1000)))

    def relacher(self, cle, jeton):
        self.r.eval(_LIBERER, 1, cle, jeton)

    def ajouter(self, cle, delta, ttl):
        p = self.r.pipeline()
        p.incrby(cle, delta)
        if ttl:
            p.expire(cle, int(ttl))
        n = int(p.execute()[0])
        if n < 0:                     # libération sans réservation (après une panne)
            self.r.set(cle, 0, ex=int(ttl) if ttl else None)
            n = 0
        return n

    def entiers(self, cles):
        return [int(v or 0) for v in self.r.mget(cles)]

    def ecrire(self, cle, valeur, ttl):
        self.r.set(cle, json.dumps(valeur), ex=int(ttl) if ttl else None)

    def lire(self, cle):
        v = self.r.get(cle)
        return json.loads(v) if v else None

    def supprimer(self, cle):
        self.r.delete(cle)

    def fenetre(self, cle, limite, secondes):
        """Fenêtre fixe (une clé par tranche) : simple et atomique."""
        tranche = f"{cle}:{int(time.time() // secondes)}"
        p = self.r.pipeline()
        p.incr(tranche)
        p.expire(tranche, int(secondes) * 2)
        return int(p.execute()[0]) <= limite


def _chronometre(methode):
    """Temps passé à attendre Redis, compté pour la requête en cours
    (core/chrono.py). Tout accès à Redis passe par une méthode de _Redis."""
    def mesuree(self, *args, **kwargs):
        t0 = time.perf_counter()
        try:
            return methode(self, *args, **kwargs)
        finally:
            from core import chrono
            chrono.ajouter("redis", time.perf_counter() - t0)
    mesuree.__name__ = methode.__name__
    mesuree.__doc__ = methode.__doc__
    return mesuree


for _nom in ("acquerir", "relacher", "ajouter", "entiers", "ecrire", "lire", "supprimer", "fenetre"):
    setattr(_Redis, _nom, _chronometre(getattr(_Redis, _nom)))


# ── Choix du stockage et repli en cas de panne ───────────────────

_memoire = _Memoire()
_redis = None                 # _Redis, construit au premier usage
_redis_essaye = False
_panne_jusqua = 0.0
_dernier_journal = 0.0
_choix = threading.Lock()


def _construire():
    global _redis, _redis_essaye
    with _choix:
        if _redis_essaye:
            return _redis
        _redis_essaye = True
        url = url_redis()
        if url:
            import redis
            _redis = _Redis(redis.Redis.from_url(
                url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True))
        return _redis


def _actif():
    """Le stockage Redis s'il est configuré et pas en pause, sinon None."""
    r = _redis if _redis_essaye else _construire()
    if r is None or time.time() < _panne_jusqua:
        return None
    return r


def _panne(e):
    global _panne_jusqua, _dernier_journal
    _panne_jusqua = time.time() + PAUSE_PANNE
    if time.time() - _dernier_journal > 60:
        _dernier_journal = time.time()
        logger.error("partage: Redis indisponible (%s), repli sur la mémoire %ss",
                     type(e).__name__, PAUSE_PANNE)


def _appeler(methode, *args):
    """Exécute sur Redis, ou sur la mémoire si Redis est absent ou en panne."""
    r = _actif()
    if r is not None:
        try:
            return getattr(r, methode)(*args)
        except Exception as e:
            _panne(e)
    return getattr(_memoire, methode)(*args)


def stockage() -> str:
    """'redis' (partagé), 'redis-en-panne' ou 'memoire' (une instance)."""
    if _construire() is None:
        return "memoire"
    return "redis" if _actif() is not None else "redis-en-panne"


def utiliser(client) -> None:
    """Tests : impose un client Redis (fakeredis), ou None pour la mémoire."""
    global _redis, _redis_essaye, _panne_jusqua
    with _choix:
        _redis = _Redis(client) if client is not None else None
        _redis_essaye = True
        _panne_jusqua = 0.0


def reinitialiser() -> None:
    """Tests : repart d'une mémoire vide (le client Redis imposé reste)."""
    global _memoire
    _memoire = _Memoire()


def _cle(*parties) -> str:
    brut = "|".join(str(p) for p in parties)
    if len(brut) > 120:            # noms de séance ou d'exercice longs : clé bornée
        brut = brut[:60] + "#" + hashlib.sha1(brut.encode()).hexdigest()
    return PREFIXE + brut


# ── API ──────────────────────────────────────────────────────────

@contextmanager
def verrou(*cle, ttl: float = VERROU_TTL, attente: float = VERROU_ATTENTE):
    """Section critique commune à toutes les instances.

    Mémoire : un verrou du processus (bloquant, comme avant). Redis : SET NX
    avec expiration — une instance tuée en pleine section ne bloque personne
    plus de `ttl` secondes. Lève TimeoutError au-delà de `attente`."""
    nom = _cle("verrou", *cle)
    r = _actif()
    if r is not None:
        jeton = uuid.uuid4().hex
        fin, pause = time.monotonic() + attente, 0.01
        try:
            while not r.acquerir(nom, jeton, ttl):
                if time.monotonic() > fin:
                    raise TimeoutError(f"verrou occupé : {cle[0]}")
                time.sleep(pause)
                pause = min(pause * 2, 0.1)
        except TimeoutError:
            raise
        except Exception as e:
            _panne(e)
        else:
            try:
                yield
            finally:
                try:
                    r.relacher(nom, jeton)
                except Exception as e:  # il expirera seul
                    _panne(e)
            return
    lk = _memoire.verrou_local(nom)
    if not lk.acquire(timeout=attente):
        raise TimeoutError(f"verrou occupé : {cle[0]}")
    try:
        yield
    finally:
        lk.release()


def ajouter(cle: str, delta: int, ttl: float) -> int:
    """Compteur entier, jamais négatif ; `ttl` efface un compteur oublié."""
    return _appeler("ajouter", _cle(cle), int(delta), ttl)


def valeur(cle: str) -> int:
    return _appeler("entiers", [_cle(cle)])[0]


def ecrire(cle: str, donnee, ttl: float) -> None:
    _appeler("ecrire", _cle(cle), donnee, ttl)


def lire(cle: str):
    """La valeur écrite (JSON), ou None. En repli, la mémoire est lue aussi :
    une valeur écrite pendant une panne reste visible par cette instance."""
    k = _cle(cle)
    r = _actif()
    if r is not None:
        try:
            v = r.lire(k)
            if v is not None:
                return v
        except Exception as e:
            _panne(e)
    return _memoire.lire(k)


def supprimer(cle: str) -> None:
    _appeler("supprimer", _cle(cle))


def fenetre(cle: str, limite: int, secondes: float) -> bool:
    """True si un passage de plus tient dans `limite` par `secondes`."""
    return _appeler("fenetre", _cle(cle), int(limite), secondes)


def generations(cles: list):
    """Numéros de version des clés de cache, ou None si Redis est en panne.

    Une entrée de cache retient les numéros lus avant sa lecture en base ; elle
    n'est servie que s'ils n'ont pas bougé. Le stockage fait partie du résultat :
    des numéros de la mémoire ne valident jamais une entrée Redis, ni l'inverse.

    Une clé jamais incrémentée, ou expirée, vaut 0. L'expiration est sûre : elle
    survient au moins `GENERATION_TTL` après la dernière écriture, quand toute
    entrée lue avant celle-ci a dépassé depuis longtemps les 10 min du cache."""
    noms = [_cle("gen", c) for c in cles]
    r = _actif()
    if r is not None:
        try:
            return ("r", *r.entiers(noms))
        except Exception as e:
            _panne(e)
            return None
    if _construire() is not None:
        return None                  # Redis configuré mais en pause : pas de cache
    return ("m", *_memoire.entiers(noms))


def nouvelle_generation(cle: str):
    """Invalide `cle` sur toutes les instances. Rend le nouveau numéro, ou
    None si Redis est en panne (les autres instances ne sont pas prévenues :
    leur cache expirera au bout de son TTL)."""
    nom = _cle("gen", cle)
    r = _actif()
    if r is not None:
        try:
            return r.ajouter(nom, 1, GENERATION_TTL)
        except Exception as e:
            _panne(e)
            return None
    if _construire() is not None:
        return None
    return _memoire.ajouter(nom, 1, None)


def processus_annonces(env=None) -> int:
    """Nombre de workers gunicorn demandés (WEB_CONCURRENCY, lu par gunicorn)."""
    env = os.environ if env is None else env
    try:
        return max(1, int(env.get("WEB_CONCURRENCY") or 1))
    except ValueError:
        return 1


def etat(env=None, sonder: bool = False) -> dict:
    """{"stockage", "processus", "alerte"} — affiché sur /admin.

    `processus` est ce que gunicorn applique (gunicorn.conf.py) : WEB_CONCURRENCY
    n'est suivi qu'avec Redis. Le nombre de répliques Railway, lui, ne se voit
    pas d'ici : sans Redis, il doit rester à 1."""
    stock = stockage()
    if stock == "redis" and sonder:
        try:
            _redis.r.ping()
        except Exception as e:
            _panne(e)
            stock = "redis-en-panne"
    demandes = processus_annonces(env)
    n = demandes if stock != "memoire" else 1
    alerte = ""
    if stock == "memoire" and demandes > 1:
        alerte = (f"WEB_CONCURRENCY={demandes} ignoré : sans REDIS_URL, l'app reste à 1 processus "
                  "(cache, verrous et tâches IA en mémoire). Ajoute Redis pour en lancer plusieurs.")
    elif stock == "redis-en-panne":
        alerte = ("REDIS_URL est défini mais Redis ne répond pas : cache coupé, verrous et "
                  "tâches IA limités à chaque instance.")
    return {"stockage": stock, "processus": n, "alerte": alerte}


def verifier_au_demarrage(env=None) -> dict:
    """Journalise le stockage choisi ; ERREUR si la configuration est bancale."""
    e = etat(env, sonder=True)
    if e["alerte"]:
        logger.error("partage: %s", e["alerte"])
    else:
        logger.info("partage: stockage %s, %d processus", e["stockage"], e["processus"])
    return e
