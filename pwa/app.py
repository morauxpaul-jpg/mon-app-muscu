"""Muscu Tracker PRO — version PWA (Flask).

Tourne en parallèle du Streamlit d'origine sur le même Google Sheet.
Commit 1 : squelette + layout de base. Les pages sont des stubs.
"""
import os
from flask import Flask, render_template, send_from_directory

from routes.accueil import bp as accueil_bp
from routes.seance import bp as seance_bp
from routes.programme import bp as programme_bp
from routes.progres import bp as progres_bp
from routes.gestion import bp as gestion_bp

app = Flask(__name__, static_folder="static", template_folder="templates")
app.register_blueprint(accueil_bp)
app.register_blueprint(seance_bp)
app.register_blueprint(programme_bp)
app.register_blueprint(progres_bp)
app.register_blueprint(gestion_bp)


# ────────────────────────────────────────────────────────────────
# Routes pages — les pages non encore migrées restent des stubs
# ────────────────────────────────────────────────────────────────


@app.route("/arcade")
def arcade():
    return render_template("arcade.html", active="arcade")


# ────────────────────────────────────────────────────────────────
# Manifest et service worker servis depuis la racine pour scope /
# ────────────────────────────────────────────────────────────────
@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory("static", "manifest.webmanifest", mimetype="application/manifest+json")


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory("static", "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    return response


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
