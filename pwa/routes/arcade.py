"""Blueprint arcade — mini-jeux intégrés."""
from flask import Blueprint, render_template

bp = Blueprint("arcade", __name__)


@bp.route("/arcade")
def index():
    return render_template("arcade.html", active="plus")
