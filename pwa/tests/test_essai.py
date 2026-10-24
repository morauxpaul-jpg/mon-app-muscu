"""Essai PRO de 3 jours ouvert à la fin de la première séance (core/essai.py).

Audit du 18/10 (I-4) : l'essai ne s'ouvrait que par parrainage, et personne
n'avait jamais été parrainé : 0 essai, 0 paiement. Personne n'avait vu le
coach ni le debrief complets.
"""
import datetime as dt
import time

import pytest

from conftest import USER_ID, CSRF
from core import db
from core.dates import continuous_week, logical_today_paris
from core.essai import ESSAI_JOURS

AUJ = logical_today_paris()


@pytest.fixture()
def gratuit(client):
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", fournisseurs=["google"], onboarded=True,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time(), _csrf=CSRF)
    return client


def _decor(fake, profil=None, series=1):
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {}}}).execute()
    fake.table("profiles").insert({"id": USER_ID, "tier": "free", **(profil or {})}).execute()
    for n in range(1, series + 1):
        fake.table("history").insert({
            "user_id": USER_ID, "semaine": continuous_week(AUJ), "seance": "Push",
            "exercice": "Développé couché", "serie": n, "reps": 8, "poids": 60.0,
            "remarque": "", "muscle": "Pecs", "date": AUJ.isoformat()}).execute()


def _terminer(client):
    return client.post("/seance/finish", data={
        "_csrf": CSRF, "mode": "prefaite", "seance_name": "Push",
        "date": AUJ.isoformat(), "rating": "", "comment": ""})


def _profil(fake):
    return next(p for p in fake.tables["profiles"] if p["id"] == USER_ID)


def _essais(fake):
    return [e for e in fake.tables.get("events", []) if e["event"] == "trial_started"]


def test_la_premiere_seance_ouvre_l_essai_tout_de_suite(fake_db, gratuit):
    _decor(fake_db)
    assert _terminer(gratuit).status_code == 302
    fin = dt.datetime.fromisoformat(_profil(fake_db)["vip_until"])
    reste = fin - dt.datetime.now(dt.timezone.utc)
    assert dt.timedelta(days=ESSAI_JOURS) - dt.timedelta(minutes=1) < reste <= dt.timedelta(days=ESSAI_JOURS)
    assert len(_essais(fake_db)) == 1
    with gratuit.session_transaction() as s:   # effet immédiat : le debrief suivant est le complet
        assert s["is_vip"] is True and s["is_vip_full"] is False

    html = gratuit.get("/accueil").get_data(as_text=True)
    assert "ESSAI PRO OFFERT" in html and f"pendant {ESSAI_JOURS} jours" in html
    # Annoncé une fois.
    assert "ESSAI PRO OFFERT" not in gratuit.get("/accueil").get_data(as_text=True)


def test_l_essai_ne_s_ouvre_qu_une_fois(fake_db, gratuit):
    _decor(fake_db)
    _terminer(gratuit)
    premiere_fin = _profil(fake_db)["vip_until"]
    db.vider_cache()
    _terminer(gratuit)
    assert _profil(fake_db)["vip_until"] == premiere_fin
    assert len(_essais(fake_db)) == 1


@pytest.mark.parametrize("profil", [
    {"vip_until": "2026-06-01T10:00:00+00:00"},      # essai déjà eu (parrainage), fini
    {"tier": "vip"},                                  # déjà abonné
])
def test_pas_de_second_essai_ni_d_essai_pour_un_abonne(fake_db, gratuit, profil):
    _decor(fake_db, profil)
    _terminer(gratuit)
    assert _profil(fake_db).get("vip_until") == profil.get("vip_until")
    assert _essais(fake_db) == []
    assert "ESSAI PRO OFFERT" not in gratuit.get("/accueil").get_data(as_text=True)


def test_une_seance_sans_serie_n_ouvre_rien(fake_db, gratuit):
    _decor(fake_db, series=0)
    _terminer(gratuit)
    assert _profil(fake_db).get("vip_until") is None
    assert _essais(fake_db) == []
