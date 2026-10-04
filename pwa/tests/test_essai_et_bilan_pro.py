"""Essai qui montre le coach et le debrief ; bilan PRO du mois (audit du 03/10, profils 6 et 7)."""
import datetime as dt

from conftest import CSRF, USER_ID
from core.bilan_pro import records_du_mois


def _essai(client):
    with client.session_transaction() as s:
        s["is_vip"], s["is_vip_full"] = True, False
        s["vip_until"] = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=20)).isoformat()


def test_essai_ouvre_le_coach_avec_quota_reduit(fake_db, logged_in):
    import routes.coach as coach
    fin = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=20)).isoformat()
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free", "vip_until": fin}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {"_settings": {}}}).execute()
    _essai(logged_in)
    r = logged_in.get("/coach")
    assert r.status_code == 200 and "<title>Coach IA · Muscu Tracker</title>" in r.get_data(as_text=True)
    with logged_in.application.test_request_context():
        from flask import g
        g.is_vip, g.is_vip_full = True, False
        assert coach._limite() == coach.ESSAI_QUOTA < coach.DAILY_QUOTA
        g.is_vip_full = True
        assert coach._limite() == coach.DAILY_QUOTA


def test_essai_debrief_autorise(fake_db, logged_in):
    from flask import g
    from routes.seance_fin import _debrief_allowed
    with logged_in.application.test_request_context():
        g.is_vip, g.is_vip_full = True, False
        assert _debrief_allowed({}) == (True, "vip")
        g.is_vip = False
        assert _debrief_allowed({})[1] == "free_trial"


def test_gratuit_reste_au_mur(fake_db, logged_in):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    with logged_in.session_transaction() as s:
        s["is_vip"] = s["is_vip_full"] = False
    r = logged_in.post("/coach/ask", json={"message": "salut"}, headers={"X-CSRFToken": CSRF})
    assert r.status_code == 403


def test_records_du_mois():
    auj = dt.date(2026, 10, 3)
    hist = [{"Exercice": "Squat", "Date": "2026-08-01", "Reps": 5, "Poids": 100},
            {"Exercice": "Squat", "Date": "2026-09-20", "Reps": 5, "Poids": 105},     # record
            {"Exercice": "Rowing", "Date": "2026-08-01", "Reps": 8, "Poids": 60},
            {"Exercice": "Rowing", "Date": "2026-09-20", "Reps": 8, "Poids": 60},     # égalé, pas battu
            {"Exercice": "Curl", "Date": "2026-09-25", "Reps": 10, "Poids": 15}]      # première fois
    assert records_du_mois(hist, auj) == 1


def test_plus_affiche_le_bilan_du_mois(fake_db, logged_in):
    from core.dates import logical_today_paris
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    maintenant = dt.datetime.now(dt.timezone.utc).isoformat()
    for ev in ["debrief_generated"] * 3 + ["coach_message"] * 12 + ["program_generated"]:
        fake_db.table("events").insert({"user_id": USER_ID, "event": ev, "created_at": maintenant}).execute()
    html = logged_in.get("/plus").get_data(as_text=True)
    assert "Ce mois-ci avec PRO" in html
    assert "<b>3</b><span>debriefs</span>" in html
    assert "<b>12</b><span>messages au coach</span>" in html
    assert "<b>1</b><span>programme généré</span>" in html
    assert "séance refaite" not in html                                    # zéro : masqué
