"""Blueprint partage — endpoint léger de tracking des partages de progression.

La carte (image) est générée côté client (canvas) puis partagée via l'API Web
Share. Ce endpoint ne sert qu'à compter les partages côté serveur (analytics /
croissance), en best-effort.
"""
import logging

from flask import Blueprint, jsonify, request

from core.analytics import track
from core.limiter import limiter

logger = logging.getLogger(__name__)

bp = Blueprint("share", __name__)


@bp.route("/share/track", methods=["POST"])
@limiter.limit("30 per minute")
def share_track():
    data = request.get_json(silent=True) or {}
    kind = str(data.get("kind") or "progress")[:40]
    method = str(data.get("method") or "")[:20]  # 'share' | 'download'
    track("progress_shared", {"kind": kind, "method": method})
    return ("", 204)
