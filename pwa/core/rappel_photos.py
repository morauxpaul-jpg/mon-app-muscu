"""Rappel des photos de progression : toutes les 4 semaines (PRO).

Choix du propriétaire (18/10/2026) : une notification propose de reprendre
ses photos, pour garder des intervalles réguliers. Appelé par le cron
horaire des rappels (/tasks/reminders, cron_reminders.py).

Qui le reçoit : un compte PRO aujourd'hui, notifications activées, dont la
dernière photo date de 28, 56 ou 84 jours (core/photos_corps.rappel_du_jour).
À son heure de rappel de séance, 18 h s'il n'en a pas choisi. Aucun état à
tenir : une nouvelle photo remet le compte à zéro.
"""
import logging

from core.dates import now_paris, today_paris
from core.photos_corps import jours_sans_photo, payload_rappel, rappel_du_jour
from core.reminders import DEFAULT_HOUR, clean_hour

logger = logging.getLogger(__name__)


def cibles(derniere_par_compte: dict, reglages: dict, pro: set, heure: int, aujourdhui) -> dict:
    """{user_id: jours sans photo} : qui reçoit le rappel à cette heure-ci."""
    out = {}
    for uid, derniere in (derniere_par_compte or {}).items():
        if uid not in pro or not rappel_du_jour(derniere, aujourdhui):
            continue
        r = reglages.get(uid) or {}
        if not r.get("notifications"):
            continue
        if (clean_hour(r.get("reminder_hour"), DEFAULT_HOUR) or DEFAULT_HOUR) != heure:
            continue
        out[uid] = jours_sans_photo(derniere, aujourdhui)
    return out


def run_rappel_photos(heure: int | None = None) -> dict:
    from core import db as core_db
    from core import push as core_push

    if not core_push.is_configured():
        return {"ok": False, "error": "unconfigured"}
    heure = now_paris().hour if heure is None else int(heure)
    aujourdhui = today_paris()
    dernieres = core_db.dernieres_photos_par_compte()
    a_rappeler = {u: d for u, d in dernieres.items() if rappel_du_jour(d, aujourdhui)}
    if not a_rappeler:
        return {"ok": True, "sent": 0, "targets": 0}
    try:
        progs = [p for p in core_db.list_all_programs() if p.get("user_id") in a_rappeler]
        par_uid = cibles(a_rappeler, core_db.reglages_pour(progs),
                         core_db.comptes_pro(set(a_rappeler)), heure, aujourdhui)
        subs = core_db.list_push_subscriptions_for_users(set(par_uid)) if par_uid else []
    except Exception as e:
        logger.error("rappel photos lecture FAILED: %s", e)
        return {"ok": False, "error": "gather_failed"}

    sent = expired = errors = 0
    for sub in subs:
        jours = par_uid.get(sub.get("user_id"))
        if jours is None:
            continue
        status = core_push.send_push(sub["sub"], payload_rappel(jours))
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
    logger.info("rappel photos h=%s : sent=%s targets=%s errors=%s", heure, sent, len(par_uid), errors)
    return {"ok": True, "sent": sent, "expired": expired, "errors": errors, "targets": len(par_uid)}
