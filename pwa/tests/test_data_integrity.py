"""Non-régression des trois pertes de données silencieuses de l'audit.

R1 — la même séance faite deux fois dans la semaine : la première était
     effacée par la seconde (ciblage par plage de semaine au lieu de la date).
R2 — l'autosave de l'éditeur de programme reconstruisait le blob à partir
     d'une liste blanche et jetait bilans / exos perso / badges / record.
R3 — tout ce qui compte une séance « faite » sur l'accueil exigeait un poids
     > 0, donc les séances au poids du corps ne comptaient jamais.

Ces trois scénarios sont ceux qui touchent le plus d'utilisateurs (9 des 20
programmes du catalogue planifient une même séance deux fois par semaine).
"""
import datetime as dt
import json
import re

from conftest import USER_ID, CSRF
from core.dates import continuous_week, logical_today_paris, DAYS_FR

MONDAY = dt.date(2026, 9, 14)
FRIDAY = MONDAY + dt.timedelta(days=4)


def _seed_full_body(fake, extra=None):
    data = {
        "Full Body A": [{"name": "Squat", "sets": 3, "muscle": "Quadriceps"}],
        "Full Body B": [{"name": "Rowing", "sets": 3, "muscle": "Dos"}],
        "_planning": {"Lundi": "Full Body A", "Mercredi": "Full Body B",
                      "Vendredi": "Full Body A"},
        "_settings": {},
        "_started_at": MONDAY.isoformat(),
    }
    data.update(extra or {})
    fake.table("programs").insert({"user_id": USER_ID, "data": data}).execute()


def _save_squat(client, day, poids):
    return client.post("/seance/save-exo", data={
        "_csrf": CSRF,
        "semaine": str(continuous_week(day)),
        "seance_name": "Full Body A",
        "exo_base": "Squat",
        "variant": "Standard",
        "muscle": "Quadriceps",
        "date": day.isoformat(),
        "mode": "prefaite",
        "name": "Full Body A",
        "sets_json": json.dumps([{"reps": 8, "poids": poids},
                                 {"reps": 8, "poids": poids}]),
    })


# ── R1 : deux séances du même nom dans la semaine ────────────────


def test_meme_seance_deux_fois_dans_la_semaine_coexiste(fake_db, logged_in):
    _seed_full_body(fake_db)
    assert _save_squat(logged_in, MONDAY, 60.0).status_code == 302
    assert _save_squat(logged_in, FRIDAY, 62.5).status_code == 302

    rows = [r for r in fake_db.tables["history"] if r["exercice"] == "Squat"]
    assert sorted({r["date"] for r in rows}) == [MONDAY.isoformat(), FRIDAY.isoformat()]
    assert len(rows) == 4  # 2 séries × 2 jours
    par_jour = {}
    for r in rows:
        par_jour.setdefault(r["date"], set()).add(r["poids"])
    assert par_jour[MONDAY.isoformat()] == {60.0}
    assert par_jour[FRIDAY.isoformat()] == {62.5}


def test_reenregistrer_le_meme_jour_remplace_sans_doublon(fake_db, logged_in):
    _seed_full_body(fake_db)
    _save_squat(logged_in, MONDAY, 60.0)
    _save_squat(logged_in, MONDAY, 65.0)  # correction de la même séance
    rows = [r for r in fake_db.tables["history"] if r["exercice"] == "Squat"]
    assert len(rows) == 2
    assert {r["poids"] for r in rows} == {65.0}


def test_cardio_deux_fois_dans_la_semaine_coexiste(fake_db, logged_in):
    _seed_full_body(fake_db)
    for day, km in ((MONDAY, 5.0), (FRIDAY, 8.0)):
        r = logged_in.post("/cardio/save", data={
            "_csrf": CSRF, "date": day.isoformat(), "activite": "Course",
            "duree_min": "30", "distance_km": str(km), "poids_kg": "75",
        })
        assert r.status_code == 302
    rows = [r for r in fake_db.tables["history"] if r["exercice"] == "CARDIO:Course"]
    assert sorted(r["date"] for r in rows) == [MONDAY.isoformat(), FRIDAY.isoformat()]
    assert sorted(r["poids"] for r in rows) == [5.0, 8.0]


def test_session_id_partage_par_les_series_dune_meme_seance(fake_db, logged_in):
    _seed_full_body(fake_db)
    _save_squat(logged_in, MONDAY, 60.0)
    _save_squat(logged_in, FRIDAY, 62.5)
    rows = [r for r in fake_db.tables["history"] if r["exercice"] == "Squat"]
    par_jour = {}
    for r in rows:
        par_jour.setdefault(r["date"], set()).add(r.get("session_id"))
    # Un id par séance, partagé par ses séries, différent d'un jour à l'autre.
    assert all(len(v) == 1 for v in par_jour.values())
    assert len({next(iter(v)) for v in par_jour.values()}) == 2


# ── R2 : les données personnelles survivent aux écritures programme ──

PERSO = {
    "_custom_exercises": [{"name": "Mon exo", "muscle": "Pecs", "profil": "Salle"}],
    "_badges": ["first_session", "tonnage_10k"],
    "_streak_record": 7,
    "_challenges_won": 3,
    "_challenges_done": [900],
    "_upsell_seen": True,
    "_meal_plan": {"label": "S38", "plats": [{"name": "Poulet riz"}]},
    "_equipment_details": ["halteres"],
    "_equipement": "maison",
    "_seance_order": {"Full Body A|2026-09-14": ["Squat"]},
    "_archive": [{"Exercice": "Squat", "Semaine": 1, "Poids": 80, "Reps": 5}],
    "_settings": {"auto_rest_timer": False},
}


def _perso_survivant(fake):
    data = fake.tables["programs"][0]["data"]
    return {k: data.get(k) for k in PERSO}


def test_autosave_programme_preserve_les_donnees_perso(fake_db, logged_in):
    _seed_full_body(fake_db, PERSO)
    logged_in.get("/programme")
    r = logged_in.post("/programme/state", data=json.dumps({
        "name": "Mon prog",
        "seances": {"Full Body A": [{"name": "Squat", "sets": 4, "muscle": "Quadriceps"}]},
        "planning": {"Lundi": "Full Body A"},
        "seance_order": ["Full Body A"],
    }), content_type="application/json", headers={"X-CSRFToken": CSRF})
    assert r.status_code == 200
    assert _perso_survivant(fake_db) == PERSO
    # et le corps a bien été remplacé
    data = fake_db.tables["programs"][0]["data"]
    assert "Full Body B" not in data
    assert data["Full Body A"][0]["sets"] == 4


def test_adoption_programme_ia_preserve_les_donnees_perso(fake_db, logged_in):
    _seed_full_body(fake_db, PERSO)
    program = {
        "name": "Programme IA",
        "seances": {"Haut": [{"name": "Développé couché", "sets": 4,
                              "reps": "8-12", "rest_seconds": 120, "muscle": "Pecs"}]},
        "planning": {"Lundi": "Haut"},
    }
    r = logged_in.post("/generator/apply",
                       data={"_csrf": CSRF, "program": json.dumps(program)})
    assert r.status_code == 302
    assert _perso_survivant(fake_db) == PERSO


def test_changement_de_programme_preserve_les_donnees_perso(fake_db, logged_in):
    _seed_full_body(fake_db, PERSO)
    r = logged_in.post("/programme/change-program", data={
        "_csrf": CSRF, "programme_id": "fb_deb_3j", "mode": "replace", "confirm": "yes",
    })
    assert r.status_code == 302
    assert _perso_survivant(fake_db) == PERSO


def test_programme_ia_conserve_les_reps_et_le_repos(fake_db, logged_in):
    _seed_full_body(fake_db)
    program = {
        "name": "Programme IA",
        "seances": {"Haut": [{"name": "Développé couché", "sets": 4,
                              "reps": "8-12", "rest_seconds": 120, "muscle": "Pecs"}]},
        "planning": {"Lundi": "Haut"},
    }
    logged_in.post("/generator/apply", data={"_csrf": CSRF, "program": json.dumps(program)})
    exo = fake_db.tables["programs"][0]["data"]["Haut"][0]
    assert exo["reps"] == "8-12"
    assert exo["rest_seconds"] == 120


def test_get_programme_n_ecrit_pas_a_chaque_affichage(fake_db, logged_in):
    _seed_full_body(fake_db, PERSO)
    logged_in.get("/programme")          # 1er appel : migration de schéma
    import core.db as core_db
    core_db._data_cache.clear()
    snapshot = json.dumps(fake_db.tables["programs"][0]["data"], sort_keys=True, default=str)
    logged_in.get("/programme")          # 2e appel : doit être en lecture pure
    assert json.dumps(fake_db.tables["programs"][0]["data"], sort_keys=True,
                      default=str) == snapshot


# ── R3 : les séances au poids du corps comptent ──────────────────


def _seed_bodyweight_session(fake):
    today = logical_today_paris()
    day = DAYS_FR[today.weekday()]
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "PDC A": [{"name": "Pompes", "sets": 3, "muscle": "Pecs"}],
        "_planning": {day: "PDC A"},
        "_settings": {},
        "_started_at": today.isoformat(),
    }}).execute()
    for s in (1, 2, 3):
        fake.table("history").insert({
            "user_id": USER_ID, "semaine": continuous_week(today), "seance": "PDC A",
            "exercice": "Pompes", "serie": s, "reps": 15, "poids": 0.0,
            "remarque": "", "muscle": "Pecs", "date": today.isoformat(),
        }).execute()
    return today


def test_seance_poids_du_corps_compte_dans_le_streak(fake_db, logged_in):
    _seed_bodyweight_session(fake_db)
    html = logged_in.get("/accueil").get_data(as_text=True)
    streak = re.search(r"(\d+) SEMAINE", html)
    assert streak and streak.group(1) != "0"


def test_seance_poids_du_corps_compte_dans_les_stats_semaine(fake_db, logged_in):
    _seed_bodyweight_session(fake_db)
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert re.search(r'stat-value">\s*1/1', html)


def test_seance_poids_du_corps_pas_de_streak_en_danger(fake_db, logged_in):
    _seed_bodyweight_session(fake_db)
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert "En danger" not in html


def test_seance_poids_du_corps_debloque_le_badge_premiere_seance(fake_db, logged_in):
    _seed_bodyweight_session(fake_db)
    logged_in.get("/accueil")
    assert "first_session" in (fake_db.tables["programs"][0]["data"].get("_badges") or [])
