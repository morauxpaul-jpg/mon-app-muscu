"""Retour à l'écran de séance après une action de formulaire (PRG).

Partagé par les blueprints de la séance (routes/seance.py, seance_fin.py,
seance_cardio.py), qui ne s'importent pas entre eux.
"""
from flask import redirect, url_for


def _back_to_editor(form):
    return redirect(url_for(
        "seance.seance",
        date=form["date"], mode=form["mode"], name=form["name"]
    ))
