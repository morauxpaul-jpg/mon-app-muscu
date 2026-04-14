"""Blueprint premium — page de présentation des tiers (pré-paywall)."""
from flask import Blueprint, render_template

bp = Blueprint("premium", __name__)


@bp.route("/premium")
def index():
    return render_template("premium.html", active="plus")
