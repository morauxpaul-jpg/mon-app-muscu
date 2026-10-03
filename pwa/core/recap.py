"""Récap de la semaine, poussé le dimanche soir.

Hevy et Strong résument la semaine ; ici, rien ne revenait vers l'utilisateur
une fois la séance finie, sauf la relance des inactifs (audit du 03/10). Le
dimanche à 19 h, une notification dit ce qui a été fait — séances, volume,
écart avec la semaine d'avant — et ce qui vient : la première séance prévue
de la semaine suivante, rotation comprise.

Envoyé seulement à qui s'est entraîné dans la semaine : un récap à zéro
n'informe pas, il culpabilise (la relance des inactifs existe pour ça).
Désactivable (`_settings.recap_hebdo`), et suspendu avec les notifications.

Le cron horaire des rappels (core/reminders.py) l'appelle à chaque passage ;
hors du dimanche 19 h, ça ne coûte rien.
"""
import logging
from datetime import timedelta

from core.dates import DAYS_FR, monday_of, now_paris

logger = logging.getLogger(__name__)

JOUR_RECAP = 6      # dimanche
HEURE_RECAP = 19


def _vol(rows) -> int:
    return int(sum(float(r.get("poids") or 0) * int(r.get("reps") or 0) for r in rows
                   if not str(r.get("exercice") or "").startswith("CARDIO:")))


def _faites(rows) -> int:
    return len({(r.get("date"), r.get("seance")) for r in rows
                if int(r.get("reps") or 0) > 0 or float(r.get("poids") or 0) > 0})


def _milliers(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def recap_utilisateur(semaine: list, precedente: list, prog: dict, lundi_prochain) -> dict | None:
    """Notification du récap, ou None s'il n'y a rien à dire.

    semaine / precedente : lignes `history` (clés en base : date, seance,
    exercice, reps, poids) de la semaine écoulée et de celle d'avant."""
    from core.rotation import seance_prevue

    n = _faites(semaine)
    if not n:
        return None
    vol, vol_prec = _vol(semaine), _vol(precedente)
    titre = f"Ta semaine : {n} séance{'s' if n > 1 else ''}"
    morceaux = []
    if vol:
        morceaux.append(f"{_milliers(vol)} kg soulevés")
        if vol_prec:
            ecart = round((vol - vol_prec) / vol_prec * 100)
            if ecart:
                morceaux.append(f"{'+' if ecart > 0 else ''}{ecart} % vs la semaine d'avant")
    for i in range(7):
        d = lundi_prochain + timedelta(days=i)
        prevue = seance_prevue(prog or {}, d)
        if prevue:
            jour = "demain" if i == 0 else DAYS_FR[d.weekday()].lower()
            morceaux.append(f"Prochaine : {prevue} {jour}")
            break
    return {
        "title": titre,
        "body": " · ".join(morceaux) or "Bien joué. On remet ça la semaine prochaine ?",
        "url": "/progres",
        "tag": "recap-hebdo",
    }


def cibles(progs: list) -> dict:
    """{user_id: prog} : abonnés aux notifications qui n'ont pas coupé le récap."""
    out = {}
    for row in progs or []:
        uid, data = row.get("user_id"), row.get("data") or {}
        settings = data.get("_settings") or {}
        if uid and settings.get("notifications") and settings.get("recap_hebdo", True):
            out[uid] = data
    return out


def run_recap_hebdo(maintenant=None) -> dict:
    """Envoie le récap si c'est le moment, sinon ne fait rien.
    {"ok", "sent", "targets", ...} ou {"ok": True, "skipped": True}."""
    maintenant = maintenant or now_paris()
    aujourd_hui = maintenant.date()
    if aujourd_hui.weekday() != JOUR_RECAP or maintenant.hour != HEURE_RECAP:
        return {"ok": True, "skipped": True}

    from core import db as core_db
    from core import push as core_push
    if not core_push.is_configured():
        return {"ok": False, "error": "unconfigured"}

    lundi = monday_of(aujourd_hui)
    try:
        par_user = cibles(core_db.list_all_programs())
        rows = core_db.history_between_for_users(
            set(par_user), (lundi - timedelta(days=7)).isoformat(), aujourd_hui.isoformat())
        subs = core_db.list_push_subscriptions_for_users(set(par_user))
    except Exception as e:
        logger.error("run_recap_hebdo lecture FAILED: %s", e)
        return {"ok": False, "error": "gather_failed"}

    semaine, precedente = {}, {}
    for r in rows:
        cible = semaine if str(r.get("date") or "") >= lundi.isoformat() else precedente
        cible.setdefault(r.get("user_id"), []).append(r)

    payloads = {}
    for uid, prog in par_user.items():
        p = recap_utilisateur(semaine.get(uid, []), precedente.get(uid, []), prog,
                              lundi + timedelta(days=7))
        if p:
            payloads[uid] = p

    sent = expired = errors = 0
    for sub in subs:
        payload = payloads.get(sub.get("user_id"))
        if not payload:
            continue
        status = core_push.send_push(sub["sub"], payload)
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
    logger.info("récap hebdo : sent=%s targets=%s errors=%s", sent, len(payloads), errors)
    return {"ok": True, "sent": sent, "expired": expired, "errors": errors,
            "targets": len(payloads)}
