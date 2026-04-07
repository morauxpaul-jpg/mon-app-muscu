"""Muscu Tracker PRO — version PWA (Flask).

Tourne en parallèle du Streamlit d'origine sur le même Google Sheet.
Commit 1 : squelette + layout de base. Les pages sont des stubs.
"""
import os
from flask import Flask, render_template, send_from_directory

from routes.accueil import bp as accueil_bp

app = Flask(__name__, static_folder="static", template_folder="templates")
app.register_blueprint(accueil_bp)


# ────────────────────────────────────────────────────────────────
# Routes pages — les pages non encore migrées restent des stubs
# ────────────────────────────────────────────────────────────────


@app.route("/seance")
def seance():
    return render_template("seance.html", active="seance")


@app.route("/programme")
def programme():
    return render_template("programme.html", active="programme")


@app.route("/progres")
def progres():
    return render_template("progres.html", active="progres")


@app.route("/gestion")
def gestion():
    return render_template("gestion.html", active="gestion")


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
