"""Muscu Tracker PRO — version PWA (Flask).

Phase 3 : multi-user via Supabase. L'authentification est gérée par
routes/auth.py (Google OAuth + bridge), et un `before_request` global
bloque l'accès aux pages protégées tant que la session Flask n'a pas de
`user_id`. Les routes lisent leurs données via `core.data` qui reprend
ce `user_id` dans `flask.g`.
"""
import os
from datetime import timedelta

from flask import Flask, render_template, send_from_directory, session, g, redirect, url_for, request

from routes.accueil import bp as accueil_bp
from routes.seance import bp as seance_bp
from routes.programme import bp as programme_bp
from routes.progres import bp as progres_bp
from routes.gestion import bp as gestion_bp
from routes.auth import bp as auth_bp

app = Flask(__name__, static_folder="static", template_folder="templates")

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


# ────────────────────────────────────────────────────────────────
# Auth gate — toutes les routes sauf celles listées nécessitent user_id
# ────────────────────────────────────────────────────────────────
_PUBLIC_PATHS = {"/login", "/auth/bridge", "/auth/session", "/manifest.json", "/service-worker.js"}


@app.before_request
def _require_login():
    path = request.path or "/"
    if path.startswith("/static/"):
        return None
    if path in _PUBLIC_PATHS:
        return None
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))
    g.user_id = user_id
    g.email = session.get("email", "")
    return None


@app.context_processor
def _inject_user():
    return {
        "current_user_email": session.get("email", ""),
        "is_authenticated": bool(session.get("user_id")),
    }


# ────────────────────────────────────────────────────────────────
# Routes pages — les pages non encore migrées restent des stubs
# ────────────────────────────────────────────────────────────────


@app.route("/arcade")
def arcade():
    return render_template("arcade.html", active="arcade")


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


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
