"""Relances et messages de retour justes (audit du 30/09, I14).

- Le bandeau « Content de te revoir » s'affichait dès 3 jours sans séance,
  quel que soit le planning : chaque lundi chez un pratiquant Lun/Mer/Ven
  régulier (R7).
- Le plafond de 3 relances push n'était jamais remis à zéro : après un
  premier décrochage, plus jamais de relance.
- 2 défis sur 5 se comptaient en kilos, impossibles au poids du corps.
- Les rappels locaux ne se déclenchaient jamais (R4) : retirés.
"""
import datetime as dt
from pathlib import Path

import pytest

from conftest import USER_ID
from core.challenges import weekly_challenge, CHALLENGES
from core.dates import continuous_week
from core.push import relances_de_cet_arret, _should_relaunch, MAX_REACTIVATIONS
from routes.accueil import seances_manquees

LMV = {"Lundi": "Full A", "Mardi": "", "Mercredi": "Full B", "Jeudi": "",
       "Vendredi": "Full A", "Samedi": "", "Dimanche": ""}


# ── Bandeau de retour ────────────────────────────────────────────


def test_un_regulier_na_rien_manque_le_lundi():
    vendredi, lundi = dt.date(2026, 9, 25), dt.date(2026, 9, 28)
    assert seances_manquees(LMV, vendredi, lundi) == 0


def test_une_seance_prevue_et_ratee_compte():
    vendredi, jeudi = dt.date(2026, 9, 25), dt.date(2026, 10, 1)
    assert seances_manquees(LMV, vendredi, jeudi) == 2   # lundi + mercredi


def test_sans_planning_pas_de_calcul():
    assert seances_manquees({}, dt.date(2026, 9, 1), dt.date(2026, 9, 30)) is None


@pytest.fixture()
def regulier(fake_db, monkeypatch):
    import routes.accueil as accueil
    lundi = dt.date(2026, 9, 28)
    monkeypatch.setattr(accueil, "logical_today_paris", lambda: lundi)
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Full A": [{"name": "Squat", "sets": 3, "muscle": "Jambes"}],
        "Full B": [{"name": "Rowing", "sets": 3, "muscle": "Dos"}],
        "_planning": LMV, "_settings": {}, "_started_at": "2026-08-01",
    }}).execute()

    def seance(jour):
        fake_db.table("history").insert({
            "user_id": USER_ID, "date": jour.isoformat(), "semaine": 1,
            "seance": "Full A", "exercice": "Squat", "serie": 1, "reps": 8,
            "poids": 60.0, "remarque": "", "muscle": "Jambes"}).execute()
    return lundi, seance


def test_le_bandeau_ne_sermonne_pas_un_regulier(regulier, logged_in):
    lundi, seance = regulier
    seance(lundi - dt.timedelta(days=3))   # vendredi
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert "Content de te revoir" not in html


def test_le_bandeau_saffiche_apres_des_seances_ratees(regulier, logged_in):
    lundi, seance = regulier
    seance(lundi - dt.timedelta(days=10))  # vendredi d'avant : lun + mer ratés
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert "Content de te revoir" in html


# ── Plafond de relances ──────────────────────────────────────────


def test_les_relances_dun_arret_termine_ne_comptent_plus():
    sub = {"reactivation_count": MAX_REACTIVATIONS, "last_reactivation_at": "2026-06-10T09:00:00+00:00"}
    # Il a repris le 20/06, puis décroché de nouveau.
    assert relances_de_cet_arret(sub, "2026-06-20") == 0
    assert _should_relaunch(sub, derniere_seance="2026-06-20")


def test_pendant_le_meme_arret_le_plafond_tient():
    sub = {"reactivation_count": MAX_REACTIVATIONS, "last_reactivation_at": "2026-06-25T09:00:00+00:00"}
    assert relances_de_cet_arret(sub, "2026-06-20") == MAX_REACTIVATIONS
    assert not _should_relaunch(sub, derniere_seance="2026-06-20")


def test_le_cron_relance_quelquun_qui_a_decroche_une_deuxieme_fois(fake_db, monkeypatch):
    import core.push as push
    import core.db as db
    derniere = (dt.date.today() - dt.timedelta(days=5)).isoformat()
    monkeypatch.setattr(push, "is_configured", lambda: True)
    monkeypatch.setattr(db, "get_inactive_users", lambda **k: {USER_ID: derniere})
    monkeypatch.setattr(db, "list_push_subscriptions_for_users", lambda ids: [{
        "user_id": USER_ID, "endpoint": "e1", "sub": {},
        "reactivation_count": 3, "last_reactivation_at": "2026-01-10T09:00:00+00:00"}])
    envoyes, marques = [], []
    monkeypatch.setattr(push, "send_push", lambda sub, body: envoyes.append(body) or "ok")
    monkeypatch.setattr(db, "mark_reactivation_sent", lambda ep, n: marques.append(n))
    r = push.run_reactivation_push()
    assert r["sent"] == 1
    assert envoyes[0] == push.REACTIVATION_MESSAGES[0], "on repart du premier message"
    assert marques == [1]


# ── Défis au poids du corps ──────────────────────────────────────


def _semaine_du_defi(cid):
    """Un lundi dont la semaine tombe sur le défi `cid`."""
    d = dt.date(2026, 9, 28)
    ids = [c for c, _ in CHALLENGES]
    while ids[continuous_week(d) % len(ids)] != cid:
        d += dt.timedelta(days=7)
    return d


def _pompes(jour, n_series=3, reps=15):
    return [{"Date": jour.isoformat(), "Semaine": continuous_week(jour), "Séance": "PDC",
             "Exercice": "Pompes", "Série": i, "Reps": reps, "Poids": 0.0,
             "Remarque": "", "Muscle": "Pecs"} for i in range(1, n_series + 1)]


@pytest.mark.parametrize("cid", ["tonnage10k", "beat_volume"])
def test_au_poids_du_corps_les_defis_se_comptent_en_reps(cid):
    lundi = _semaine_du_defi(cid)
    hist = _pompes(lundi - dt.timedelta(days=7)) + _pompes(lundi)
    ch = weekly_challenge(hist, lundi)
    assert ch["id"] == cid and ch["unit"] == "reps"
    assert ch["current"] == 45


def test_un_defi_en_reps_peut_etre_reussi():
    lundi = _semaine_du_defi("tonnage10k")
    hist = []
    for k in range(4):
        hist += _pompes(lundi + dt.timedelta(days=k), n_series=5, reps=20)
    assert weekly_challenge(hist, lundi)["done"]


def test_avec_des_charges_on_reste_en_kilos():
    lundi = _semaine_du_defi("tonnage10k")
    hist = [dict(r, Poids=60.0) for r in _pompes(lundi)]
    assert weekly_challenge(hist, lundi)["unit"] == "kg"


# ── Rappels locaux retirés ───────────────────────────────────────


def test_les_rappels_locaux_morts_sont_retires():
    pwa = Path(__file__).resolve().parents[1]
    assert not (pwa / "static/js/notifications.js").exists()
    assert "checkDailyNotifications" not in (pwa / "templates/accueil.html").read_text(encoding="utf-8")
    assert "notifications.js" not in (pwa / "templates/base.html").read_text(encoding="utf-8")
