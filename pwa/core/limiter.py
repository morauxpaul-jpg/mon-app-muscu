"""Instance Flask-Limiter partagée — importable depuis les blueprints
sans créer de cycle d'import via app.py. Initialisée dans app.py via
`limiter.init_app(app)`."""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60 per minute"],
    storage_uri="memory://",
)
