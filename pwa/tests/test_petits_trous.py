"""Point 4 du rapport d'audit (04/10) : trois petits trous visibles.

* « Créer mon propre programme » promettait l'éditeur et renvoyait à
  l'accueil ;
* l'éditeur acceptait n'importe quel nombre de séries, d'exercices et de
  séances (M11) ;
* vider l'historique ne demandait aucune confirmation au serveur (M10).
"""
import os
import json
import time

from conftest import CSRF, USER_ID
from routes import programme as rp


def _prog(fake, data=None):
    base = {"Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
            "_planning": {}, "_settings": {}}
    base.update(data or {})
    fake.table("programs").insert({"user_id": USER_ID, "data": base}).execute()


def _data(fake):
    return next(p for p in fake.tables["programs"] if p["user_id"] == USER_ID)["data"]


def _onboarding(client, programme_id):
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=False, is_vip=False,
                 is_vip_full=False, is_vip_ts=time.time(), _csrf=CSRF)
    return client.post("/onboarding/submit", data={
        "_csrf": CSRF, "prenom": "Alex", "age": "25", "sexe": "homme", "niveau": "debutant",
        "frequence": "3", "objectif": "prise de masse", "equipement": "salle",
        "programme_id": programme_id})


# ── « Créer mon propre programme » ───────────────────────────────

def test_creer_mon_programme_ouvre_lediteur_avec_le_mode_demploi(fake_db, client):
    r = _onboarding(client, "custom")
    assert r.headers["Location"].endswith("/programme?nouveau=1")
    html = client.get("/programme?nouveau=1").get_data(as_text=True)
    assert "Construis ton programme" in html
    assert 'id="mes-programmes"' in html and "Nouvelle séance" in html


def test_un_programme_du_catalogue_mene_toujours_a_laccueil(fake_db, client):
    r = _onboarding(client, "fullbody_debutant_3j")
    assert r.headers["Location"].endswith("/accueil")


def test_le_mode_demploi_napparait_pas_en_temps_normal(fake_db, logged_in):
    _prog(fake_db)
    assert "Construis ton programme" not in logged_in.get("/programme").get_data(as_text=True)


# ── Bornes de l'éditeur (M11) ────────────────────────────────────

def _state(client, seances, planning=None):
    return client.post("/programme/state", data=json.dumps(
        {"seances": seances, "planning": planning or {}, "seance_order": list(seances)}),
        content_type="application/json", headers={"X-CSRF-Token": CSRF})


def test_lediteur_borne_les_series(fake_db, logged_in):
    _prog(fake_db)
    r = _state(logged_in, {"Push": [{"name": "Développé couché", "sets": 10000, "muscle": "Pecs"},
                                    {"name": "Dips", "sets": -4, "muscle": "Pecs"}]})
    assert r.status_code == 200
    exos = _data(fake_db)["Push"]
    assert [e["sets"] for e in exos] == [rp.MAX_SERIES, 1]


def test_lediteur_borne_exercices_et_seances(fake_db, logged_in):
    _prog(fake_db)
    exos = [{"name": f"Exo {i}", "sets": 3, "muscle": "Pecs"} for i in range(100)]
    seances = {f"S{i}": [] for i in range(100)}
    seances["Push"] = exos
    _state(logged_in, seances)
    data = _data(fake_db)
    noms = [k for k in data if not k.startswith("_")]
    assert len(noms) <= rp.MAX_SEANCES
    assert len(data.get("Push", [])) <= rp.MAX_EXOS_PAR_SEANCE


def test_un_nom_dexercice_demesure_est_coupe(fake_db, logged_in):
    _prog(fake_db)
    _state(logged_in, {"Push": [{"name": "X" * 5000, "sets": 3, "muscle": "M" * 500}]})
    ex = _data(fake_db)["Push"][0]
    assert len(ex["name"]) == rp.NOM_EXO_MAX and len(ex["muscle"]) <= rp.NOM_EXO_MAX


def test_ajout_et_modification_dexercice_bornes(fake_db, logged_in):
    _prog(fake_db)
    logged_in.post("/programme/exo/add", data={"_csrf": CSRF, "seance": "Push",
                                               "name": "Dips", "sets": "999"})
    assert _data(fake_db)["Push"][-1]["sets"] == rp.MAX_SERIES
    logged_in.post("/programme/exo/update", data={"_csrf": CSRF, "seance": "Push",
                                                  "index": "0", "sets": "500"})
    assert _data(fake_db)["Push"][0]["sets"] == rp.MAX_SERIES


def test_une_seance_pleine_refuse_un_exercice_de_plus(fake_db, logged_in):
    _prog(fake_db, {"Push": [{"name": f"Exo {i}", "sets": 3, "muscle": "Pecs"}
                             for i in range(rp.MAX_EXOS_PAR_SEANCE)]})
    r = logged_in.post("/programme/exo/add", data={"_csrf": CSRF, "seance": "Push", "name": "De trop"})
    assert "exo=trop" in r.headers["Location"]
    assert len(_data(fake_db)["Push"]) == rp.MAX_EXOS_PAR_SEANCE


def test_trop_de_seances_refuse_une_seance_de_plus(fake_db, logged_in):
    _prog(fake_db, {f"S{i}": [] for i in range(rp.MAX_SEANCES)})
    r = logged_in.post("/programme/seance/new", data={"_csrf": CSRF, "name": "Encore une"})
    assert "seance=trop" in r.headers["Location"]
    assert "Encore une" not in _data(fake_db)


def test_import_de_programme_borne(fake_db, logged_in):
    import io
    _prog(fake_db)
    fichier = {"_format": rp.EXPORT_FORMAT,
               "seances": {"Push": [{"name": f"Dips {i}", "sets": 77, "muscle": "Pecs"} for i in range(60)]}}
    r = logged_in.post("/programme/import", data={
        "_csrf": CSRF, "confirm": "yes",
        "file": (io.BytesIO(json.dumps(fichier).encode()), "prog.json")},
        content_type="multipart/form-data")
    assert r.status_code == 302 and "import_err" not in r.headers["Location"]
    push = _data(fake_db)["Push"]
    assert len(push) == rp.MAX_EXOS_PAR_SEANCE and all(e["sets"] == rp.MAX_SERIES for e in push)


def test_la_page_donne_ses_bornes_a_lediteur(fake_db, logged_in):
    _prog(fake_db)
    html = logged_in.get("/programme").get_data(as_text=True)
    assert f'"series": {rp.MAX_SERIES}' in html
    assert ':max="BORNES.series"' in html and 'bornerEtSauver(ex)' in html
    # Le geste borne puis sauvegarde (static/js/programme.js, version CSP).
    js = open(os.path.join(os.path.dirname(__file__), "..", "static", "js", "programme.js"),
              encoding="utf-8").read()
    assert "ex.sets = this.bornerSeries(ex.sets);" in js


# ── Vider l'historique (M10) ─────────────────────────────────────

def _serie(fake):
    fake.table("history").insert({"user_id": USER_ID, "date": "2026-10-01", "semaine": 1,
                                  "seance": "Push", "exercice": "Développé couché", "serie": 1,
                                  "reps": 8, "poids": 60.0, "remarque": "", "muscle": "Pecs"}).execute()


def test_tout_effacer_sans_confirmation_nefface_rien(fake_db, logged_in):
    """Le « reset soft » a disparu en v47 ; le reset total garde la même
    règle : un POST nu (formulaire rejoué, double tap) n'efface rien."""
    _prog(fake_db)
    _serie(fake_db)
    r = logged_in.post("/gestion/reset-total", data={"_csrf": CSRF})
    assert r.headers["Location"].endswith("?reset=confirm")
    assert len(fake_db.tables["history"]) == 1
    html = logged_in.get("/gestion?reset=confirm").get_data(as_text=True)
    assert "Rien n'a été effacé" in html


def test_le_formulaire_envoie_la_confirmation(fake_db, logged_in):
    _prog(fake_db)
    html = logged_in.get("/gestion").get_data(as_text=True)
    form = html.split('action="/gestion/reset-total"', 1)[1].split("</form>", 1)[0]
    assert 'name="confirm" value="yes"' in form
