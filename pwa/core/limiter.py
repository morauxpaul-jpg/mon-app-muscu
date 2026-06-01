"""Instance Flask-Limiter partagée — importable depuis les blueprints
sans créer de cycle d'import via app.py. Initialisée dans app.py via
`limiter.init_app(app)`.

Stockage : `memory://` par défaut (par worker, remis à zéro au redéploiement).
Si la variable d'env `REDIS_URL` est définie (instance Redis Railway), le
rate-limiting devient **partagé entre les workers gunicorn** automatiquement,
sans changement de code — l'anti-abus réel (et la protection du coût API du
coach) s'active alors. `swallow_errors=True` : si Redis est momentanément
indisponible, on dégrade gracieusement (pas de 500) au lieu de bloquer.
"""
import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# On n'active Redis que si la valeur ressemble à une vraie URL Redis. Toute
# autre valeur (vide, placeholder, typo) retombe sur memory:// → impossible de
# casser le démarrage avec une variable mal renseignée.
_raw_redis = (os.getenv("REDIS_URL") or "").strip().strip('"').strip("'")
_storage_uri = _raw_redis if _raw_redis.startswith(("redis://", "rediss://")) else "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60 per minute"],
    storage_uri=_storage_uri,
    storage_options={"socket_connect_timeout": 2} if _storage_uri.startswith("redis") else {},
    swallow_errors=True,
)
