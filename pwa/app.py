"""Muscu Tracker PRO — version PWA (Flask).

Phase 3 : multi-user via Supabase. L'authentification est gérée par
routes/auth.py (Google OAuth + bridge), et un `before_request` global
bloque l'accès aux pages protégées tant que la session Flask n'a pas de
`user_id`. Les routes lisent leurs données via `core.data` qui reprend
ce `user_id` dans `flask.g`.
"""
import logging
import os
from datetime import timedelta

from flask import Flask, render_template, send_from_directory, session, g, redirect, url_for, request

from core.limiter import limiter

from routes.accueil import bp as accueil_bp
from routes.seance import bp as seance_bp
from routes.programme import bp as programme_bp
from routes.progres import bp as progres_bp
from routes.gestion import bp as gestion_bp
from routes.auth import bp as auth_bp
from routes.onboarding import bp as onboarding_bp
from routes.arcade import bp as arcade_bp
from routes.cardio import bp as cardio_bp
from routes.nutrition import bp as nutrition_bp
from routes.coach import bp as coach_bp

from core import db as core_db

# Logging structuré — remplace print() un peu partout dans le code.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", template_folder="templates")

# Rate limiter global — protège les routes POST contre les clics compulsifs.
# default_limits s'applique à toutes les routes ; sur-limite ajoutée avec
# @limiter.limit(...) pour les actions sensibles dans les blueprints.
limiter.init_app(app)

# Secret_key : obligatoire pour signer le cookie de session Flask. Doit être
# défini en prod via la variable d'env FLASK_SECRET_KEY sur Railway.
app.secret_key = os.getenv("FLASK_SECRET_KEY") or "dev-insecure-change-me"
app.permanent_session_lifetime = timedelta(days=30)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.getenv("FLASK_SECRET_KEY")),  # HTTPS-only en prod
)

app.register_blueprint(auth_bp)
app.register_blueprint(accueil_bp)
app.register_blueprint(seance_bp)
app.register_blueprint(programme_bp)
app.register_blueprint(progres_bp)
app.register_blueprint(gestion_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(arcade_bp)
app.register_blueprint(cardio_bp)
app.register_blueprint(nutrition_bp)
app.register_blueprint(coach_bp)


# ────────────────────────────────────────────────────────────────
# Auth gate — toutes les routes sauf celles listées nécessitent user_id
# ────────────────────────────────────────────────────────────────
_PUBLIC_PATHS = {"/", "/login", "/auth/bridge", "/auth/session", "/auth/debug", "/manifest.json", "/service-worker.js"}


@app.before_request
def _require_login():
    path = request.path or "/"
    if path.startswith("/static/"):
        return None
    if path in _PUBLIC_PATHS:
        return None
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("landing"))
    g.user_id = user_id
    g.email = session.get("email", "")

    # Phase 4 : gate onboarding. Les routes /onboarding/* et /logout sont
    # exemptées pour éviter la boucle de redirection.
    if path.startswith("/onboarding") or path == "/logout":
        return None
    # Cache le flag en session pour éviter un hit DB à chaque requête
    if not session.get("onboarded"):
        try:
            onboarding = core_db.get_onboarding(user_id)
        except Exception:
            onboarding = {}
        if not onboarding:
            # Fix bug Phase 4 : un user pré-Phase 4 (qui a déjà un programme
            # ou de l'historique) ne doit JAMAIS voir l'onboarding — sinon
            # il risque d'écraser ses données. On crée une row minimale et
            # on le laisse passer.
            try:
                has_prog = bool(core_db.get_prog(user_id))
                has_hist = bool(core_db.get_hist(user_id))
            except Exception:
                has_prog = has_hist = False
            if has_prog or has_hist:
                try:
                    core_db.save_onboarding(user_id, {"prenom": ""})
                except Exception:
                    pass
                session["onboarded"] = True
                return None
            return redirect(url_for("onboarding.index"))
        session["onboarded"] = True
    return None


@app.context_processor
def _inject_user():
    # is_premium : exposé à tous les templates pour gater des features (Coach
    # IA, export, stats avancées…). Pour l'instant tout le monde est free,
    # donc is_premium = False — mais l'infra est prête.
    premium = False
    uid = session.get("user_id")
    if uid:
        try:
            profile = core_db.get_profile(uid) or {}
            premium = (profile.get("tier") or "free").strip().lower() == "vip"
        except Exception:
            premium = False
    return {
        "current_user_email": session.get("email", ""),
        "is_authenticated": bool(uid),
        "is_premium": premium,
    }


# ────────────────────────────────────────────────────────────────
# Landing page publique + page "Plus"
# ────────────────────────────────────────────────────────────────


@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("accueil.index"))
    return render_template("landing.html")


@app.route("/plus")
def plus():
    return render_template("plus.html", active="plus")


# ────────────────────────────────────────────────────────────────
# Manifest et service worker servis depuis la racine pour scope /
# ────────────────────────────────────────────────────────────────
@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory("static", "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    return response


# ────────────────────────────────────────────────────────────────
# Error handlers globaux — jamais de trace Flask blanche pour l'user.
# ────────────────────────────────────────────────────────────────
@app.errorhandler(404)
def handle_404(e):
    return render_template(
        "error.html",
        code=404,
        message="Page introuvable.",
    ), 404


@app.errorhandler(500)
def handle_500(e):
    logger.error("500 on %s: %s", request.path, e)
    return render_template(
        "error.html",
        code=500,
        message="Erreur serveur. Réessaie dans quelques secondes.",
    ), 500


@app.errorhandler(429)
def handle_429(e):
    return render_template(
        "error.html",
        code=429,
        message="Tu cliques un peu trop vite — attends quelques secondes et réessaie.",
    ), 429


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
