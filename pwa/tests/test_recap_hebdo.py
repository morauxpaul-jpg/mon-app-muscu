"""Récap de la semaine, le dimanche à 19 h (audit du 03/10)."""
import datetime as dt

from conftest import CSRF, USER_ID
from core import recap
from core.dates import DAYS_FR

DIMANCHE = dt.date(2026, 9, 27)
LUNDI = dt.date(2026, 9, 21)
LUNDI_PROCHAIN = dt.date(2026, 9, 28)
PROG = {"Push": [{"name": "Développé couché", "sets": 3}],
        "Pull": [{"name": "Rowing barre", "sets": 3}],
        "_planning": {**{d: "" for d in DAYS_FR}, "Mardi": "Push", "Jeudi": "Pull"}}


def _l(date, seance, poids, reps=10, exercice="Développé couché"):
    return {"user_id": USER_ID, "date": date.isoformat(), "seance": seance,
            "exercice": exercice, "reps": reps, "poids": poids}


def test_message_dit_semaine_volume_ecart_et_suite():
    semaine = [_l(LUNDI, "Push", 100), _l(LUNDI, "Push", 100),
               _l(LUNDI + dt.timedelta(days=3), "Pull", 50),
               _l(LUNDI, "Cardio", 5, 30, "CARDIO:Course")]
    precedente = [_l(LUNDI - dt.timedelta(days=7), "Push", 100)]
    p = recap.recap_utilisateur(semaine, precedente, PROG, LUNDI_PROCHAIN)
    assert p["title"] == "Ta semaine : 3 séances"           # cardio compris
    assert p["body"] == "2 500 kg soulevés · +150 % vs la semaine d'avant · Prochaine : Push mardi"
    assert p["url"] == "/progres"


def test_rien_fait_rien_envoye():
    assert recap.recap_utilisateur([], [_l(LUNDI, "Push", 100)], PROG, LUNDI_PROCHAIN) is None


def test_prochaine_seance_suit_la_rotation():
    prog = {**PROG, "_planning": {**PROG["_planning"], "Mardi": "Push", "Jeudi": "Push"},
            "_rotation": ["Push", "Pull"], "_started_at": "2026-09-24"}
    p = recap.recap_utilisateur([_l(LUNDI, "Push", 100)], [], prog, LUNDI_PROCHAIN)
    # Cycle ouvert le jeudi 24 (Push) : le mardi suivant, c'est Pull.
    assert p["body"].endswith("Prochaine : Pull mardi")


def test_cibles_respecte_les_reglages(fake_db):
    """Sans ligne dans `reglages` (v45), un reste du programme fait foi."""
    progs = [{"user_id": "a", "data": {"_settings": {"notifications": True}}},
             {"user_id": "b", "data": {"_settings": {"notifications": True, "recap_hebdo": False}}},
             {"user_id": "c", "data": {"_settings": {"notifications": False}}}]
    assert set(recap.cibles(progs)) == {"a"}


def test_hors_du_dimanche_19h_rien(monkeypatch):
    for quand in (dt.datetime(2026, 9, 27, 18), dt.datetime(2026, 9, 26, 19)):
        assert recap.run_recap_hebdo(quand) == {"ok": True, "skipped": True}


def test_run_envoie_a_qui_s_est_entraine(fake_db, monkeypatch):
    import core.push as core_push
    monkeypatch.setattr(core_push, "is_configured", lambda: True)
    envoyes = []
    monkeypatch.setattr(core_push, "send_push", lambda sub, p: envoyes.append(p) or "ok")
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        **PROG, "_settings": {"notifications": True}}}).execute()
    fake_db.table("programs").insert({"user_id": "u-oisif", "data": {
        **PROG, "_settings": {"notifications": True}}}).execute()
    for uid in (USER_ID, "u-oisif"):
        fake_db.table("push_subscriptions").insert({
            "user_id": uid, "endpoint": f"https://push.example/{uid}",
            "p256dh": "k", "auth": "a", "reactivation_count": 0}).execute()
    fake_db.table("history").insert({**_l(LUNDI, "Push", 80), "semaine": 1, "serie": 1,
                                     "remarque": "", "muscle": "Pecs"}).execute()

    res = recap.run_recap_hebdo(dt.datetime(2026, 9, 27, 19, 0))
    assert res["ok"] and res["sent"] == 1 and res["targets"] == 1
    assert envoyes[0]["title"] == "Ta semaine : 1 séance"


def test_reglage_recap_enregistre_et_affiche(fake_db, logged_in):
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        **PROG, "_settings": {"notifications": True}}}).execute()
    assert 'name="recap_hebdo" checked' in logged_in.get("/gestion").get_data(as_text=True)
    logged_in.post("/gestion/settings", data={"_csrf": CSRF, "notifications": "on",
                                              "reminder_hour": "18"})
    assert fake_db.tables["reglages"][0]["recap_hebdo"] is False
