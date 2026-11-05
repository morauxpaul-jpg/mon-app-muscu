"""Rappels et relances push : qui reçoit quoi, et combien (audit du 04/11, I-1, m10).

Trois comptes arrêtent de s'entraîner le même jour, avec une séance prévue
chaque jour. On fait tourner 21 jours de crons et on compte les push :
  - A : notifications cochées, rappel à 18 h (même heure que la relance) ;
  - B : notifications DÉCOCHÉES (l'abonnement push est resté) ;
  - C : notifications cochées, rappel à 20 h.
"""
import datetime as dt
import types

import pytest

import core.db_push as db_push
import core.push as push
import core.reminders as reminders
from conftest import USER_ID
from core.dates import DAYS_FR

A, B, C = USER_ID, "u-b-decoche", "u-c-soir"
DERNIERE_SEANCE = dt.date(2026, 10, 1)
HEURE_RELANCE = 18


def _reglages(notifications, heure):
    return {"notifications": notifications, "reminder_hour": heure}


@pytest.fixture()
def trois_comptes(fake_db):
    for uid, notifs, heure in ((A, True, 18), (B, False, 18), (C, True, 20)):
        fake_db.table("programs").insert({"user_id": uid, "data": {
            "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
            "_planning": {j: "Push" for j in DAYS_FR},
            "_settings": _reglages(notifs, heure),
            "_started_at": (DERNIERE_SEANCE - dt.timedelta(days=60)).isoformat(),
        }}).execute()
        fake_db.table("push_subscriptions").insert({
            "user_id": uid, "endpoint": f"https://push.example/{uid}",
            "p256dh": "k", "auth": "a", "reactivation_count": 0}).execute()
        fake_db.table("history").insert({
            "user_id": uid, "semaine": 1, "seance": "Push", "serie": 1,
            "exercice": "Développé couché", "reps": 8, "poids": 80.0,
            "remarque": "", "muscle": "Pecs", "date": DERNIERE_SEANCE.isoformat()}).execute()
    return fake_db


def _simuler(monkeypatch, jour: dt.date, heure: int):
    """Fige « aujourd'hui » dans tous les modules qui lisent l'horloge."""
    class Date(dt.date):
        @classmethod
        def today(cls):
            return jour

    class DateHeure(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(jour.year, jour.month, jour.day, heure, 0, tzinfo=tz or dt.timezone.utc)

    faux = types.SimpleNamespace(date=Date, datetime=DateHeure,
                                 timedelta=dt.timedelta, timezone=dt.timezone)
    monkeypatch.setattr(db_push, "_dt", faux)
    monkeypatch.setattr(push, "_dt", faux)
    monkeypatch.setattr(reminders, "logical_today_paris", lambda: jour)


def test_21_jours_de_crons_trois_comptes(trois_comptes, monkeypatch):
    envois = []   # (compte, jour, heure, type)
    contexte = {}
    monkeypatch.setattr(push, "is_configured", lambda: True)
    monkeypatch.setattr(db_push, "_PAUSE_MARQUAGE", 0)

    def faux_envoi(sub, payload, **k):
        uid = sub["endpoint"].rsplit("/", 1)[-1] if sub.get("endpoint") else None
        envois.append((uid, contexte["jour"], contexte["heure"],
                       "rappel" if payload.get("tag") == "seance-reminder" else "relance"))
        return "ok"
    monkeypatch.setattr(push, "send_push", faux_envoi)

    for k in range(21):
        jour = DERNIERE_SEANCE + dt.timedelta(days=3 + k)   # 3 → 23 jours sans séance
        for heure in (18, 20):
            contexte.update(jour=jour, heure=heure)
            _simuler(monkeypatch, jour, heure)
            reminders.run_reminders(hour=heure)
            if heure == HEURE_RELANCE:
                push.run_reactivation_push(min_days=3, max_days=30, heure=heure)

    def de(uid, genre=None):
        return [e for e in envois if e[0] == uid and (genre is None or e[3] == genre)]

    ids = {a: f"{a}" for a in (A, B, C)}
    assert de(ids[B]) == [], "notifications décochées : aucun push, ni rappel ni relance"
    # Un seul push par compte et par heure.
    par_heure = [(e[0], e[1], e[2]) for e in envois]
    assert len(par_heure) == len(set(par_heure)), "deux push dans la même heure"
    # Rappels coupés après 14 jours sans séance (jours 3 → 14 : 12 rappels).
    assert len(de(ids[A], "rappel")) == 12
    assert len(de(ids[C], "rappel")) == 12
    assert max(e[1] for e in envois if e[3] == "rappel") == DERNIERE_SEANCE + dt.timedelta(days=14)
    # Relances : 3 au plus par compte. A les reçoit après la fin des rappels
    # (à 18 h le rappel est prioritaire), C dès le premier jour (rappel à 20 h).
    assert len(de(ids[A], "relance")) == 3
    assert min(e[1] for e in de(ids[A], "relance")) > DERNIERE_SEANCE + dt.timedelta(days=14)
    assert len(de(ids[C], "relance")) == 3
    assert len(envois) == 30


def test_la_relance_respecte_le_reglage_notifications(trois_comptes, monkeypatch):
    envoyes = []
    monkeypatch.setattr(push, "is_configured", lambda: True)
    monkeypatch.setattr(push, "send_push", lambda sub, body, **k: envoyes.append(sub["endpoint"]) or "ok")
    _simuler(monkeypatch, DERNIERE_SEANCE + dt.timedelta(days=20), 10)
    r = push.run_reactivation_push(heure=10)
    assert r["sent"] == 2 and not any(B in e for e in envoyes)


# ── m10 : l'enregistrement de la relance est retenté ─────────────

def test_mark_reactivation_sent_retente_puis_reussit(fake_db, monkeypatch):
    monkeypatch.setattr(db_push, "_PAUSE_MARQUAGE", 0)
    appels = []
    vrai = db_push.get_client

    class Client:
        def table(self, nom):
            appels.append(nom)
            if len(appels) < 3:
                raise ConnectionError("coupé")
            return vrai().table(nom)
    monkeypatch.setattr(db_push, "get_client", lambda: Client())
    fake_db.table("push_subscriptions").insert({
        "user_id": A, "endpoint": "e1", "p256dh": "k", "auth": "a"}).execute()
    db_push.mark_reactivation_sent("e1", 1)
    assert len(appels) == 3
    assert fake_db.tables["push_subscriptions"][0]["reactivation_count"] == 1


def test_mark_reactivation_sent_leve_apres_les_essais_sans_accuser_la_migration(monkeypatch):
    monkeypatch.setattr(db_push, "_PAUSE_MARQUAGE", 0)

    class Client:
        def table(self, nom):
            raise ConnectionError("coupé")
    monkeypatch.setattr(db_push, "get_client", lambda: Client())
    with pytest.raises(RuntimeError) as e:
        db_push.mark_reactivation_sent("e1", 1)
    assert "migration" not in str(e.value).lower()
    assert "3 essais" in str(e.value)
