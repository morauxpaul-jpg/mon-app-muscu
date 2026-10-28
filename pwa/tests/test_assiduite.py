"""Assiduité du calendrier de Progrès : elle ne juge que les jours passés.

Le 18/10, quatre séances faites sur sept prévues jusque-là s'affichaient
« Assiduité : 31 % » : les six séances encore à venir dans le mois
comptaient comme manquées (audit du 18/10, m1).
"""
import datetime as dt
import re

from conftest import USER_ID

from core.dates import logical_today_paris

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _compte(fake_db, faits):
    """Toutes les journées planifiées ; `faits` = jours passés du mois avec une série."""
    today = logical_today_paris()
    debut = today.replace(day=1)
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("onboarding").insert({"user_id": USER_ID, "completed_at": (debut - dt.timedelta(days=40)).isoformat()}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Full": [{"name": "Squat", "sets": 3, "muscle": "Quadriceps"}],
        "_planning": {j: "Full" for j in JOURS},
        "_started_at": (debut - dt.timedelta(days=40)).isoformat()}}).execute()
    for d in faits:
        fake_db.table("history").insert({"user_id": USER_ID, "date": d.isoformat(), "semaine": 1,
            "seance": "Full", "exercice": "Squat", "muscle": "Quadriceps",
            "serie": 1, "reps": 5, "poids": 60.0}).execute()
    return today, debut


def _taux(html):
    return int(re.search(r"Assiduité : (\d+) %", html).group(1))


def test_les_seances_a_venir_ne_comptent_pas_comme_manquees(fake_db, logged_in):
    today, debut = _compte(fake_db, [])
    passes = [debut + dt.timedelta(days=i) for i in range((today - debut).days + 1)]   # aujourd'hui compris : vrai aussi le 1er du mois
    fake_db.tables["history"] = []
    for d in passes:
        fake_db.table("history").insert({"user_id": USER_ID, "date": d.isoformat(), "semaine": 1,
            "seance": "Full", "exercice": "Squat", "muscle": "Quadriceps",
            "serie": 1, "reps": 5, "poids": 60.0}).execute()
    html = logged_in.get("/progres").get_data(as_text=True)
    # Tout ce qui était dû est fait : 100 %, quel que soit le jour du mois
    # (avant : jours passés / jours du mois, donc presque jamais 100 %).
    assert _taux(html) == 100


def test_aujourd_hui_ne_compte_qu_une_fois_la_seance_faite(fake_db, logged_in):
    today, debut = _compte(fake_db, [])
    html = logged_in.get("/progres").get_data(as_text=True)
    passes = (today - debut).days
    # Rien de fait : 0 % s'il y avait des jours dus ; le 1er, rien n'est dû.
    if passes:
        assert _taux(html) == 0
    else:
        assert "aucune séance due" in html
    fake_db.table("history").insert({"user_id": USER_ID, "date": today.isoformat(), "semaine": 1,
        "seance": "Full", "exercice": "Squat", "muscle": "Quadriceps",
        "serie": 1, "reps": 5, "poids": 60.0}).execute()
    import core.db as db
    db.vider_cache()
    html = logged_in.get("/progres").get_data(as_text=True)
    assert _taux(html) == round(100 / (passes + 1))


# ── Le 1er du mois (audit du 28/10, m1) ─────────────────────────


def _novembre_complet(fake_db):
    """Programme tous les jours depuis septembre, chaque jour de novembre 2026 fait."""
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("onboarding").insert({"user_id": USER_ID, "completed_at": "2026-09-01"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Full": [{"name": "Squat", "sets": 3, "muscle": "Quadriceps"}],
        "_planning": {j: "Full" for j in JOURS}, "_started_at": "2026-09-01"}}).execute()
    for i in range(30):
        fake_db.table("history").insert({"user_id": USER_ID, "date": (dt.date(2026, 11, 1) + dt.timedelta(days=i)).isoformat(),
            "semaine": 1, "seance": "Full", "exercice": "Squat", "muscle": "Quadriceps",
            "serie": 1, "reps": 5, "poids": 60.0}).execute()


def _heure_de_paris(monkeypatch, *quand):
    import core.dates as dates
    monkeypatch.setattr(dates, "now_paris", lambda: dt.datetime(*quand, tzinfo=dates.PARIS_TZ))


def test_le_1er_du_mois_rien_n_est_du_donc_pas_de_zero(fake_db, logged_in, monkeypatch):
    """Mardi 1er décembre, 10 h, la séance du jour pas encore faite, après
    un mois de novembre parfait : l'app affichait « Assiduité : 0 % »."""
    _novembre_complet(fake_db)
    _heure_de_paris(monkeypatch, 2026, 12, 1, 10, 0)
    html = logged_in.get("/progres").get_data(as_text=True)
    assert "Décembre 2026" in html
    assert "Assiduité : 0 %" not in html
    assert "aucune séance due" in html


def test_a_0_h_30_le_1er_le_calendrier_reste_sur_le_mois_d_avant(fake_db, logged_in, monkeypatch):
    """Jusqu'à 4 h, c'est encore la veille pour la séance : le calendrier
    suit le même jour. Il ouvrait décembre, vide, à 0 h 30 le 1er."""
    _novembre_complet(fake_db)
    _heure_de_paris(monkeypatch, 2026, 12, 1, 0, 30)
    html = logged_in.get("/progres").get_data(as_text=True)
    assert "Novembre 2026" in html
    assert _taux(html) == 100
