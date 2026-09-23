"""Hors-ligne et rappels planifiés.

Deux ruptures du parcours réel sont couvertes ici :
  - la séance du jour n'était jamais en cache tant qu'on ne l'avait pas
    ouverte, donc inaccessible en salle sans réseau ;
  - les rappels ne partaient que si l'app était ouverte, c'est-à-dire jamais
    au moment utile.
"""
import datetime as dt

from conftest import USER_ID, CSRF
from core import reminders
from core.dates import DAYS_FR, logical_today_paris, continuous_week

TODAY = logical_today_paris()
DAY_NAME = DAYS_FR[TODAY.weekday()]
TOMORROW = TODAY + dt.timedelta(days=1)
TOMORROW_NAME = DAYS_FR[TOMORROW.weekday()]


def _seed(fake, planning=None, settings=None, user_id=USER_ID):
    fake.table("programs").insert({"user_id": user_id, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "Pull": [{"name": "Rowing", "sets": 3, "muscle": "Dos"}],
        "_planning": planning if planning is not None else {DAY_NAME: "Push"},
        "_settings": settings if settings is not None else {"notifications": True},
        "_started_at": TODAY.isoformat(),
    }}).execute()


def _sub(fake, user_id=USER_ID, endpoint="https://push.example/abc"):
    fake.table("push_subscriptions").insert({
        "user_id": user_id, "endpoint": endpoint,
        "p256dh": "k", "auth": "a", "reactivation_count": 0,
    }).execute()


# ── Pré-cache de la séance du jour ───────────────────────────────


def test_accueil_expose_les_urls_de_seance_a_precacher(fake_db, logged_in):
    _seed(fake_db, planning={DAY_NAME: "Push", TOMORROW_NAME: "Pull"})
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert 'id="precache-urls"' in html
    assert "mode=prefaite" in html
    assert "Push" in html and "Pull" in html


def test_precache_ignore_les_jours_de_repos(fake_db, logged_in):
    import json
    import re
    _seed(fake_db, planning={})          # aucun jour planifié
    html = logged_in.get("/accueil").get_data(as_text=True)
    raw = re.search(r'id="precache-urls">(.*?)</script>', html, re.S).group(1)
    urls = json.loads(raw)
    assert urls == ["/seance"]           # seul le point d'entrée générique


def test_service_worker_gere_le_message_precache(client):
    sw = client.get("/service-worker.js").get_data(as_text=True)
    assert 'data.type === "PRECACHE"' in sw
    assert "async function precache" in sw


def test_service_worker_sert_les_assets_depuis_le_cache_dabord(client):
    """Stale-while-revalidate : les CSS/JS ne se re-téléchargent plus à
    chaque navigation (ils ne changent qu'au déploiement)."""
    sw = client.get("/service-worker.js").get_data(as_text=True)
    assert "isVersionedAsset" in sw
    assert "OFFLINE_PAGE" in sw          # repli explicite, pas un retour muet


# ── Heure de rappel ──────────────────────────────────────────────


def test_clean_hour_borne_les_valeurs():
    assert reminders.clean_hour(18) == 18
    assert reminders.clean_hour(3) == 6        # pas de notif à 3 h du matin
    assert reminders.clean_hour(23) == 22
    assert reminders.clean_hour(0) == 0        # 0 = désactivé
    assert reminders.clean_hour("bof") == reminders.DEFAULT_HOUR


def test_reglage_heure_enregistre(fake_db, logged_in):
    _seed(fake_db)
    logged_in.post("/gestion/settings", data={
        "_csrf": CSRF, "notifications": "on", "reminder_hour": "7",
        "show_previous_weeks": "2",
    })
    prog = fake_db.tables["programs"][0]["data"]
    assert prog["_settings"]["reminder_hour"] == 7


def test_reglage_heure_visible_dans_gestion(fake_db, logged_in):
    _seed(fake_db, settings={"notifications": True, "reminder_hour": 7})
    html = logged_in.get("/gestion").get_data(as_text=True)
    assert 'name="reminder_hour"' in html
    assert '<option value="7" selected>07 h 00</option>' in html


# ── Ciblage des rappels ──────────────────────────────────────────


def test_rappel_cible_qui_sentraine_aujourdhui(fake_db):
    _seed(fake_db, settings={"notifications": True, "reminder_hour": 18})
    targets = reminders.targets_for_hour(18)
    assert [t["user_id"] for t in targets] == [USER_ID]
    assert targets[0]["seance"] == "Push"


def test_pas_de_rappel_a_une_autre_heure(fake_db):
    _seed(fake_db, settings={"notifications": True, "reminder_hour": 18})
    assert reminders.targets_for_hour(9) == []


def test_pas_de_rappel_un_jour_de_repos(fake_db):
    _seed(fake_db, planning={TOMORROW_NAME: "Pull"},
          settings={"notifications": True, "reminder_hour": 18})
    assert reminders.targets_for_hour(18) == []


def test_pas_de_rappel_si_la_seance_est_deja_faite(fake_db):
    _seed(fake_db, settings={"notifications": True, "reminder_hour": 18})
    fake_db.table("history").insert({
        "user_id": USER_ID, "semaine": continuous_week(TODAY), "seance": "Push",
        "exercice": "Développé couché", "serie": 1, "reps": 8, "poids": 80.0,
        "remarque": "", "muscle": "Pecs", "date": TODAY.isoformat(),
    }).execute()
    assert reminders.targets_for_hour(18) == []


def test_pas_de_rappel_si_notifications_desactivees(fake_db):
    _seed(fake_db, settings={"notifications": False, "reminder_hour": 18})
    assert reminders.targets_for_hour(18) == []


def test_pas_de_rappel_si_heure_a_zero(fake_db):
    _seed(fake_db, settings={"notifications": True, "reminder_hour": 0})
    assert reminders.targets_for_hour(18) == []


def test_le_message_nomme_la_seance():
    p = reminders.payload_for("Push")
    assert "Push" in p["title"]
    assert p["url"] == "/seance"


# ── Endpoint cron ────────────────────────────────────────────────


def test_cron_rappels_exige_le_secret(client, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    assert client.post("/tasks/reminders").status_code == 401
    assert client.post("/tasks/reminders",
                       headers={"X-Cron-Secret": "faux"}).status_code == 401


def test_cron_rappels_envoie_les_push(client, fake_db, monkeypatch):
    import json
    import core.push as core_push
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    monkeypatch.setattr(core_push, "is_configured", lambda: True)
    envoyes = []
    monkeypatch.setattr(core_push, "send_push",
                        lambda sub, payload: envoyes.append(payload) or "ok")
    _seed(fake_db, settings={"notifications": True, "reminder_hour": 18})
    _sub(fake_db)

    # L'endpoint envoie pour l'heure COURANTE ; le ciblage par heure est
    # couvert par test_run_reminders_envoie_a_lheure_donnee.
    r = client.post("/tasks/reminders", headers={"X-Cron-Secret": "s3cret"})
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["ok"] is True
    assert "hour" in data


def test_run_reminders_envoie_a_lheure_donnee(fake_db, monkeypatch):
    import core.push as core_push
    monkeypatch.setattr(core_push, "is_configured", lambda: True)
    envoyes = []
    monkeypatch.setattr(core_push, "send_push",
                        lambda sub, payload: envoyes.append(payload) or "ok")
    _seed(fake_db, settings={"notifications": True, "reminder_hour": 20})
    _sub(fake_db)

    res = reminders.run_reminders(hour=20)
    assert res["ok"] and res["sent"] == 1
    assert "Push" in envoyes[0]["title"]


def test_run_reminders_sans_cible_ne_fait_rien(fake_db, monkeypatch):
    import core.push as core_push
    monkeypatch.setattr(core_push, "is_configured", lambda: True)
    _seed(fake_db, settings={"notifications": True, "reminder_hour": 20})
    res = reminders.run_reminders(hour=8)
    assert res["ok"] and res["sent"] == 0 and res["targets"] == 0


# ── Relances : plafond et espacement ─────────────────────────────


def test_relance_plafonnee_a_trois_envois():
    from core.push import _should_relaunch, MAX_REACTIVATIONS
    assert _should_relaunch({"reactivation_count": 0, "last_reactivation_at": None})
    assert not _should_relaunch({"reactivation_count": MAX_REACTIVATIONS,
                                 "last_reactivation_at": None})


def test_relance_respecte_un_delai_minimum():
    import datetime as _dt
    from core.push import _should_relaunch, MIN_DAYS_BETWEEN
    now = _dt.datetime.now(_dt.timezone.utc)
    hier = (now - _dt.timedelta(days=1)).isoformat()
    vieux = (now - _dt.timedelta(days=MIN_DAYS_BETWEEN + 1)).isoformat()
    assert not _should_relaunch({"reactivation_count": 1, "last_reactivation_at": hier})
    assert _should_relaunch({"reactivation_count": 1, "last_reactivation_at": vieux})


def test_relance_change_de_message_a_chaque_envoi():
    from core.push import REACTIVATION_MESSAGES
    titres = {m["title"] for m in REACTIVATION_MESSAGES}
    assert len(titres) == len(REACTIVATION_MESSAGES)   # aucun doublon
