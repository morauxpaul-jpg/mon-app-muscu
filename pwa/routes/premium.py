"""Blueprint premium — page de présentation des tiers."""
from flask import Blueprint, render_template, g

bp = Blueprint("premium", __name__)


@bp.route("/premium")
def index():
    # Pour un VIP abonné : détecte le plan courant (mensuel/annuel) afin de
    # proposer les upgrades (annuel, à vie). None = lifetime ou VIP manuel.
    current_plan = None
    if getattr(g, "is_vip", False):
        from routes.billing import detect_current_plan
        current_plan = detect_current_plan()
    return render_template("premium.html", active="plus", current_plan=current_plan)
