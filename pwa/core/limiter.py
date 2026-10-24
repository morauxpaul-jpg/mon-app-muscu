"""Instance Flask-Limiter partagée — importable depuis les blueprints
sans créer de cycle d'import via app.py. Initialisée dans app.py via
`limiter.init_app(app)`.

Stockage : `memory://` par défaut (par worker, remis à zéro au redéploiement).
Si la variable d'env `REDIS_URL` est définie (instance Redis Railway), le
rate-limiting devient **partagé entre les workers gunicorn** automatiquement,
sans changement de code — l'anti-abus réel (et la protection du coût API du
coach) s'active alors.

Redis en panne : `in_memory_fallback_enabled` bascule le compteur sur la
mémoire du processus dès la première erreur. Les mêmes limites s'appliquent,
par processus, jusqu'au retour de Redis : flask-limiter le sonde (un `PING`)
après 1, 2, 4, 8, 16 puis 32 s, et recommence ; Redis revenu, il est repris
en 32 s au plus. Avant, chaque requête tentait Redis et payait le délai de
connexion (2 s par page, constaté le 23/10), ou pendait sans fin face à un
Redis qui accepte la connexion sans répondre (aucun `socket_timeout`).
`swallow_errors=True` reste le dernier filet : une erreur du stockage ne donne
jamais de 500.
"""
import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from redis.backoff import NoBackoff
from redis.retry import Retry

# On n'active Redis que si la valeur ressemble à une vraie URL Redis. Toute
# autre valeur (vide, placeholder, typo) retombe sur memory:// → impossible de
# casser le démarrage avec une variable mal renseignée.
_raw_redis = (os.getenv("REDIS_URL") or "").strip().strip('"').strip("'")
_storage_uri = _raw_redis if _raw_redis.startswith(("redis://", "rediss://")) else "memory://"

# Délais du client Redis du limiteur. Sur le réseau privé de Railway, Redis
# répond en quelques millisecondes : 0,5 s ne coupe qu'un Redis en panne. Le
# délai se paie à la première erreur, puis à chaque sonde de retour (une
# requête par sonde, pas toutes).
DELAI_REDIS = 0.5
# Aucune nouvelle tentative. Celles de redis-py par défaut (3, avec des
# attentes jusqu'à 2, 4 et 8 s) multiplient le délai, et elles s'imbriquent :
# la connexion retente, la commande aussi (une seule nouvelle tentative
# donnait déjà 4 × 0,5 s). Une erreur isolée (connexion du pool fermée par un
# redémarrage de Redis) coûte seulement quelques secondes de compteur en
# mémoire, jusqu'à la sonde suivante.
_OPTIONS_REDIS = {
    "socket_connect_timeout": DELAI_REDIS,
    "socket_timeout": DELAI_REDIS,
    "retry": Retry(NoBackoff(), 0),
}


def creer_limiteur(storage_uri: str) -> Limiter:
    """Le limiteur de l'app, sur ce stockage. Les tests s'en servent pour
    éprouver la configuration de production contre un Redis en panne."""
    return Limiter(
        key_func=get_remote_address,
        default_limits=["60 per minute"],
        storage_uri=storage_uri,
        storage_options=_OPTIONS_REDIS if storage_uri.startswith("redis") else {},
        in_memory_fallback_enabled=True,
        swallow_errors=True,
    )


limiter = creer_limiteur(_storage_uri)
