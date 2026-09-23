"""Rappels de séance planifiés — poussés par le serveur, à l'heure choisie.

Les rappels existants (static/js/notifications.js) ne se déclenchent que si
l'application est OUVERTE au bon moment : un rappel qui vous prévient pendant
que vous regardez déjà l'app ne sert à rien. C'est la raison pour laquelle la
seule notification réellement envoyée était la relance des inactifs — donc
toujours après le décrochage, jamais avant.

Ici, un cron horaire envoie un push aux personnes qui :
  - ont une séance planifiée aujourd'hui,
  - ne l'ont pas encore faite,
  - ont choisi cette heure de rappel,
  - et sont abonnées au push.

Le rappel arrive donc avant la séance, pas trois jours après l'avoir ratée.
"""
import logging

from core.dates import DAYS_FR, logical_today_paris, now_paris

logger = logging.getLogger(__name__)

# Heure de rappel par défaut (18 h) si l'utilisateur n'a rien choisi.
DEFAULT_HOUR = 18
# Bornes raisonnables : pas de notification au milieu de la nuit.
MIN_HOUR, MAX_HOUR = 6, 22


def clean_hour(value, default=DEFAULT_HOUR) -> int:
    """Heure valide dans [MIN_HOUR, MAX_HOUR], ou 0 pour « désactivé »."""
    try:
        h = int(value)
    except (TypeError, ValueError):
        return default
    if h == 0:
        return 0
    return max(MIN_HOUR, min(MAX_HOUR, h))


def _planned_today(prog: dict, day_name: str) -> str:
    planning = (prog or {}).get("_planning") or {}
    return planning.get(day_name) or ""


def targets_for_hour(hour: int) -> list[dict]:
    """[{user_id, seance, hour}] : qui doit recevoir un rappel maintenant.

    Une seule lecture groupée des programmes et de l'historique du jour —
    le cron tourne toutes les heures, il ne doit pas coûter une requête par
    utilisateur.
    """
    from core import db as core_db

    today = logical_today_paris()
    day_name = DAYS_FR[today.weekday()]
    today_iso = today.isoformat()

    try:
        progs = core_db.list_all_programs()
        done = core_db.users_trained_on(today_iso)
    except Exception as e:
        logger.error("targets_for_hour lecture FAILED: %s", e)
        return []

    out = []
    for row in progs:
        uid = row.get("user_id")
        data = row.get("data") or {}
        if not uid or uid in done:
            continue
        seance = _planned_today(data, day_name)
        if not seance:
            continue
        settings = data.get("_settings") or {}
        if not settings.get("notifications"):
            continue
        user_hour = clean_hour(settings.get("reminder_hour"), DEFAULT_HOUR)
        if user_hour == 0 or user_hour != hour:
            continue
        out.append({"user_id": uid, "seance": seance, "hour": user_hour})
    return out


def payload_for(seance: str) -> dict:
    """Notification de rappel. Elle nomme la séance : « C'est jour de Push »
    donne une information, « N'oublie pas ta séance » n'en donne aucune."""
    return {
        "title": f"C'est jour de {seance}",
        "body": "Ta séance t'attend — lance-la quand tu veux.",
        "url": "/seance",
        "tag": "seance-reminder",
    }


def run_reminders(hour: int | None = None) -> dict:
    """Envoie les rappels de l'heure courante. Retour identique à la relance :
    {"ok", "sent", "expired", "errors", "targets"}."""
    from core import db as core_db
    from core import push as core_push
    from core import analytics

    if not core_push.is_configured():
        return {"ok": False, "error": "unconfigured"}

    hour = now_paris().hour if hour is None else int(hour)
    targets = targets_for_hour(hour)
    if not targets:
        return {"ok": True, "sent": 0, "expired": 0, "errors": 0, "targets": 0, "hour": hour}

    by_user = {t["user_id"]: t for t in targets}
    try:
        subs = core_db.list_push_subscriptions_for_users(set(by_user))
    except Exception as e:
        logger.error("run_reminders subscriptions FAILED: %s", e)
        return {"ok": False, "error": "gather_failed"}

    sent, expired, errors = 0, 0, 0
    for sub in subs:
        target = by_user.get(sub.get("user_id"))
        if not target:
            continue
        status = core_push.send_push(sub["sub"], payload_for(target["seance"]))
        if status == "ok":
            sent += 1
        elif status == "expired":
            expired += 1
            try:
                core_db.delete_push_subscription(sub.get("endpoint"))
            except Exception:
                pass
        else:
            errors += 1

    try:
        analytics.track("seance_reminder_sent",
                        {"sent": sent, "errors": errors, "hour": hour,
                         "targets": len(targets)},
                        user_id=None, tier="system")
    except Exception:
        pass
    logger.info("rappels séance h=%s: sent=%s targets=%s errors=%s",
                hour, sent, len(targets), errors)
    return {"ok": True, "sent": sent, "expired": expired, "errors": errors,
            "targets": len(targets), "hour": hour}
