"""Saisie de séance : réponse JSON, records, durée, cibles du programme.

L'enregistrement d'un exercice ne recharge plus la page : il répond en JSON
et la carte se met à jour sur place. Ces tests couvrent le contrat de cette
réponse (c'est elle qui pilote le bandeau « Record », la barre de progression
et le volume) ainsi que le repli sans JavaScript.
"""
import datetime as dt
import json

from conftest import USER_ID, CSRF
from core.dates import continuous_week
from routes.seance import _pr_check

MONDAY = dt.date(2026, 9, 14)
FRIDAY = MONDAY + dt.timedelta(days=4)
JSON_HEADERS = {"Accept": "application/json", "X-CSRFToken": CSRF}


def _seed(fake, exos=None):
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": exos or [{"name": "Développé couché", "sets": 3, "muscle": "Pecs",
                          "reps": "8-12", "rest_seconds": 120}],
        "_planning": {"Lundi": "Push"},
        "_settings": {},
        "_started_at": MONDAY.isoformat(),
    }}).execute()


def _hist(fake, date, exercice="Développé couché", reps=8, poids=80.0, serie=1):
    fake.table("history").insert({
        "user_id": USER_ID, "semaine": continuous_week(date), "seance": "Push",
        "exercice": exercice, "serie": serie, "reps": reps, "poids": poids,
        "remarque": "", "muscle": "Pecs", "date": date.isoformat(),
    }).execute()


def _save(client, sets, date=MONDAY, headers=None, exo="Développé couché"):
    return client.post("/seance/save-exo", data={
        "_csrf": CSRF, "seance_name": "Push", "exo_base": exo,
        "variant": "Standard", "muscle": "Pecs", "date": date.isoformat(),
        "mode": "prefaite", "name": "Push", "sets_json": json.dumps(sets),
    }, headers=headers if headers is not None else JSON_HEADERS)


# ── Contrat de la réponse JSON ───────────────────────────────────


def test_save_exo_repond_en_json_sans_redirection(fake_db, logged_in):
    _seed(fake_db)
    r = _save(logged_in, [{"reps": 8, "poids": 80}])
    assert r.status_code == 200
    d = json.loads(r.data)
    assert d["ok"] is True
    assert d["completed"] is True
    assert d["volume"] == 640
    assert d["sets_done"] == 1
    assert d["last_summary"] == "80kg × 8"


def test_save_exo_sans_json_redirige_comme_avant(fake_db, logged_in):
    """Repli sans JavaScript : le formulaire classique doit continuer à marcher."""
    _seed(fake_db)
    r = _save(logged_in, [{"reps": 8, "poids": 80}], headers={"X-CSRFToken": CSRF})
    assert r.status_code == 302
    assert "/seance" in r.headers["Location"]


def test_save_exo_cumule_le_volume_de_la_seance(fake_db, logged_in):
    _seed(fake_db, [{"name": "Développé couché", "sets": 2, "muscle": "Pecs"},
                    {"name": "Dips", "sets": 2, "muscle": "Pecs"}])
    _save(logged_in, [{"reps": 10, "poids": 60}])
    r = _save(logged_in, [{"reps": 10, "poids": 40}], exo="Dips")
    d = json.loads(r.data)
    assert d["volume"] == 600 + 400
    assert d["sets_done"] == 2


def test_save_exo_renvoie_le_rpe_dans_la_ligne(fake_db, logged_in):
    _seed(fake_db)
    _save(logged_in, [{"reps": 8, "poids": 80, "rpe": "8.5"}])
    row = [r for r in fake_db.tables["history"] if r["exercice"] == "Développé couché"][0]
    assert row["rpe"] == 8.5


def test_skip_exo_repond_en_json(fake_db, logged_in):
    _seed(fake_db)
    r = logged_in.post("/seance/skip-exo", data={
        "_csrf": CSRF, "seance_name": "Push", "exo_base": "Développé couché",
        "variant": "Standard", "muscle": "Pecs", "date": MONDAY.isoformat(),
        "mode": "prefaite", "name": "Push",
    }, headers=JSON_HEADERS)
    assert r.status_code == 200
    d = json.loads(r.data)
    assert d["completed"] is True and d["skipped"] is True


# ── Détection de record (fonction pure) ──────────────────────────


def _rows(*pairs):
    return [{"Reps": reps, "Poids": poids} for reps, poids in pairs]


def test_pr_premiere_fois():
    pr = _pr_check([], _rows((8, 60.0)), "Squat", False)
    assert pr == {"kind": "first", "value": 60.0, "previous": 0}


def test_pr_charge_battue():
    pr = _pr_check(_rows((8, 80.0)) and [{"Exercice": "Squat", "Reps": 8, "Poids": 80.0}],
                   _rows((6, 85.0)), "Squat", False)
    assert pr["kind"] == "weight" and pr["value"] == 85.0 and pr["previous"] == 80.0


def test_pr_plus_de_reps_a_la_meme_charge():
    before = [{"Exercice": "Squat", "Reps": 8, "Poids": 80.0}]
    pr = _pr_check(before, _rows((10, 80.0)), "Squat", False)
    assert pr["kind"] == "reps_at_weight"
    assert pr["value"] == 10 and pr["previous"] == 8 and pr["weight"] == 80.0


def test_pr_aucun_record_si_moins_bien():
    before = [{"Exercice": "Squat", "Reps": 10, "Poids": 80.0}]
    assert _pr_check(before, _rows((6, 70.0)), "Squat", False) is None


def test_pr_poids_du_corps_compte_les_reps():
    before = [{"Exercice": "Tractions", "Reps": 8, "Poids": 0.0}]
    pr = _pr_check(before, _rows((11, 0.0)), "Tractions", True)
    assert pr == {"kind": "reps", "value": 11, "previous": 8}


def test_pr_ignore_les_autres_exercices():
    before = [{"Exercice": "Squat", "Reps": 5, "Poids": 150.0}]
    pr = _pr_check(before, _rows((8, 60.0)), "Développé couché", False)
    assert pr["kind"] == "first"


def test_save_exo_signale_le_record_dans_la_reponse(fake_db, logged_in):
    _seed(fake_db)
    _hist(fake_db, MONDAY - dt.timedelta(days=7), reps=8, poids=80.0)
    r = _save(logged_in, [{"reps": 6, "poids": 85}])
    pr = json.loads(r.data)["pr"]
    assert pr["kind"] == "weight" and pr["value"] == 85.0


def test_save_exo_pas_de_record_sur_une_seance_moins_bonne(fake_db, logged_in):
    _seed(fake_db)
    _hist(fake_db, MONDAY - dt.timedelta(days=7), reps=10, poids=90.0)
    r = _save(logged_in, [{"reps": 8, "poids": 70}])
    assert json.loads(r.data)["pr"] is None


# ── Cibles du programme et durée ─────────────────────────────────


def test_la_cible_de_reps_du_programme_est_affichee(fake_db, logged_in):
    _seed(fake_db)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={MONDAY.isoformat()}")\
        .get_data(as_text=True)
    assert "3 séries × 8-12 reps · repos 120 s" in html


def test_la_duree_de_seance_est_enregistree(fake_db, logged_in):
    _seed(fake_db)
    r = logged_in.post("/seance/finish", data={
        "_csrf": CSRF, "mode": "prefaite", "seance_name": "Push",
        "date": MONDAY.isoformat(), "rating": "4", "comment": "",
        "duration_min": "47",
    })
    assert r.status_code == 302
    note = fake_db.tables["session_notes"][0]
    assert note["duration_min"] == 47 and note["rating"] == 4


def test_duree_aberrante_ignoree(fake_db, logged_in):
    _seed(fake_db)
    logged_in.post("/seance/finish", data={
        "_csrf": CSRF, "mode": "prefaite", "seance_name": "Push",
        "date": MONDAY.isoformat(), "rating": "", "comment": "RAS",
        "duration_min": "99999",
    })
    note = fake_db.tables["session_notes"][0]
    assert note["duration_min"] == 480  # borné à 8 h


def test_la_duree_seule_cree_un_bilan(fake_db, logged_in):
    """« Passer » sans note ni commentaire : on garde quand même la durée."""
    _seed(fake_db)
    logged_in.post("/seance/finish", data={
        "_csrf": CSRF, "mode": "prefaite", "seance_name": "Push",
        "date": MONDAY.isoformat(), "rating": "", "comment": "", "duration_min": "35",
    })
    assert fake_db.tables["session_notes"][0]["duration_min"] == 35


def test_le_template_ne_contient_plus_de_gros_script_inline(fake_db, logged_in):
    """Le JS de la séance vit dans /static (testable, mis en cache, CSP-friendly)."""
    _seed(fake_db)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={MONDAY.isoformat()}")\
        .get_data(as_text=True)
    assert '/static/js/seance.js' in html
    assert 'id="seance-config"' in html
    assert "function exoBlock" not in html


# ── Séries non faites : marquées passées, pas inventées ──────────
# Enregistrer un exercice après n'avoir rempli qu'une série sur trois
# stockait les deux autres avec leur charge PRÉ-REMPLIE et zéro répétition.
# « 82,5 kg × 0 » n'est pas une performance : c'est une série qui n'a pas eu
# lieu. Elle polluait « Dernière fois » et comptait comme un entraînement.


def _lignes(fake, exo="Développé couché"):
    return sorted(
        (r for r in fake.tables["history"] if r.get("exercice") == exo),
        key=lambda r: r.get("serie") or 0,
    )


def test_une_serie_sans_repetition_est_marquee_passee(fake_db, logged_in):
    _seed(fake_db)
    _save(logged_in, [{"reps": 10, "poids": 75},
                      {"reps": "", "poids": 82.5},
                      {"reps": "", "poids": 82.5}])
    faite, passee1, passee2 = _lignes(fake_db)
    assert (faite["reps"], faite["poids"]) == (10, 75.0)
    for r in (passee1, passee2):
        assert "SKIP" in r["remarque"], "la série non faite doit être marquée passée"
        assert r["poids"] == 0, "la charge pré-remplie ne doit pas être conservée"
        assert r["reps"] == 0


def test_une_serie_passee_ne_compte_pas_comme_entrainement(fake_db, logged_in):
    from core.hist import is_muscu_perf, tonnage
    _seed(fake_db)
    _save(logged_in, [{"reps": 10, "poids": 75}, {"reps": "", "poids": 82.5}])
    import core.db as core_db
    core_db._data_cache.clear()
    hist = core_db.get_hist(USER_ID)
    assert sum(1 for r in hist if is_muscu_perf(r)) == 1
    assert tonnage(hist) == 750


def test_lexercice_reste_marque_traite(fake_db, logged_in):
    """La trace doit rester : on a ouvert l'exercice et on l'a enregistré."""
    d = json.loads(_save(logged_in, [{"reps": "", "poids": 82.5}]).data)
    assert d["completed"] is True


def test_le_commentaire_de_la_serie_survit_au_marquage(fake_db, logged_in):
    _seed(fake_db)
    _save(logged_in, [{"reps": "", "poids": 80, "remarque": "épaule douloureuse"}])
    ligne = _lignes(fake_db)[0]
    assert "SKIP" in ligne["remarque"]
    assert "épaule douloureuse" in ligne["remarque"]


def test_derniere_fois_ignore_les_series_a_zero_repetition(fake_db, logged_in):
    """Vaut aussi pour les lignes déjà en base avant ce correctif : le filtre
    est à la lecture, donc pas de migration à passer."""
    from routes.seance import _last_session_sets
    import core.db as core_db
    _seed(fake_db)
    _hist(fake_db, MONDAY, reps=10, poids=75.0, serie=1)
    _hist(fake_db, MONDAY, reps=0, poids=82.5, serie=2)   # ancienne ligne fantôme
    core_db._data_cache.clear()
    hist, _ = __import__("routes.seance", fromlist=["_normalize_hist"])._normalize_hist(
        core_db.get_hist(USER_ID), core_db.get_prog(USER_ID))
    series = _last_session_sets(hist, "Développé couché", "Push", FRIDAY.isoformat())
    assert [(s["reps"], s["poids"]) for s in series] == [(10, 75.0)]


def test_une_seance_au_poids_du_corps_a_enfin_une_derniere_fois(fake_db, logged_in):
    """Effet de bord du correctif : le filtre était `Poids > 0`, donc les
    exercices au poids du corps n'avaient jamais de « Dernière fois »."""
    from routes.seance import _last_session_sets, _normalize_hist
    import core.db as core_db
    _seed(fake_db)
    _hist(fake_db, MONDAY, exercice="Pompes", reps=20, poids=0.0)
    core_db._data_cache.clear()
    hist, _ = _normalize_hist(core_db.get_hist(USER_ID), core_db.get_prog(USER_ID))
    series = _last_session_sets(hist, "Pompes", "Push", FRIDAY.isoformat())
    assert [s["reps"] for s in series] == [20]
