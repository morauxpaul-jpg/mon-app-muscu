"""Routes du programme encore peu testées (I14, 64 % au 04/10).

Le programme décide de ce que l'utilisateur fait à la salle : une séance
fantôme dans le planning, un export qui fuit d'un compte gratuit, un import
qui accepte n'importe quoi se voient à l'accueil du lendemain. Deux défauts
trouvés en écrivant ces tests sont corrigés avec eux :

* supprimer une séance laissait le planning (et la rotation) pointer vers elle ;
* enregistrer le planning acceptait un nom de séance inexistant.
"""
import io
import json
import time

import pytest

from conftest import CSRF, USER_ID
from core.dates import DAYS_FR
from routes import programme as rp


def _prog(fake, data=None):
    base = {"Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"},
                     {"name": "Dips", "sets": 3, "muscle": "Pecs"}],
            "Pull": [{"name": "Rowing", "sets": 3, "muscle": "Dos"}],
            "Legs": [{"name": "Squat", "sets": 4, "muscle": "Quadriceps"}],
            "_planning": {"Lundi": "Push", "Mercredi": "Pull", "Vendredi": "Legs"},
            "_settings": {}}
    base.update(data or {})
    fake.table("programs").insert({"user_id": USER_ID, "data": base}).execute()


def _data(fake):
    return next(p for p in fake.tables["programs"] if p["user_id"] == USER_ID)["data"]


def _post(client, chemin, **form):
    return client.post(chemin, data={"_csrf": CSRF, **form})


# ── Planning ─────────────────────────────────────────────────────

def test_le_planning_naccepte_que_des_seances_qui_existent(fake_db, logged_in):
    _prog(fake_db)
    form = {f"plan_{j}": "" for j in DAYS_FR}
    form.update(plan_Lundi="Pull", plan_Mardi="__rest__", plan_Jeudi="Séance fantôme")
    _post(logged_in, "/programme/planning", **form)
    planning = _data(fake_db)["_planning"]
    assert planning["Lundi"] == "Pull" and planning["Mardi"] == "" and planning["Jeudi"] == ""


# ── Séances ──────────────────────────────────────────────────────

def test_supprimer_une_seance_la_retire_du_planning_et_de_la_rotation(fake_db, logged_in):
    _prog(fake_db, {"_rotation": ["Push", "Pull", "Legs"], "_seance_prog": {"Legs": "p_1"}})
    _post(logged_in, "/programme/seance/delete", name="Legs")
    data = _data(fake_db)
    assert "Legs" not in data
    assert data["_planning"]["Vendredi"] == ""
    assert data["_rotation"] == ["Push", "Pull"]
    assert "Legs" not in data["_seance_prog"]


def test_une_rotation_reduite_a_une_seance_disparait(fake_db, logged_in):
    _prog(fake_db, {"_rotation": ["Push", "Legs"]})
    _post(logged_in, "/programme/seance/delete", name="Legs")
    assert "_rotation" not in _data(fake_db)


def test_on_ne_supprime_pas_une_cle_technique(fake_db, logged_in):
    _prog(fake_db)
    _post(logged_in, "/programme/seance/delete", name="_planning")
    assert "_planning" in _data(fake_db)


def test_disponibilite_dun_nom_de_seance(fake_db, logged_in):
    _prog(fake_db, {"_programmes": [{"id": "p_1", "name": "Mon PPL"}], "_seance_prog": {"Push": "p_1"}})
    dispo = lambda nom: logged_in.post("/programme/seance/disponible", json={"name": nom},
                                       headers={"X-CSRFToken": CSRF}).get_json()
    assert dispo("Haut du corps") == {"libre": True}
    assert dispo("Push") == {"libre": False, "programme": "Mon PPL"}
    assert dispo("_secret")["libre"] is False


@pytest.mark.parametrize("nom,direction,ordre", [
    ("Pull", "up", ["Pull", "Push", "Legs"]),
    ("Pull", "down", ["Push", "Legs", "Pull"]),
    ("Push", "up", ["Push", "Pull", "Legs"]),      # déjà en tête : rien ne bouge
    ("Inconnue", "up", ["Push", "Pull", "Legs"]),
])
def test_deplacer_une_seance(fake_db, logged_in, nom, direction, ordre):
    _prog(fake_db)
    _post(logged_in, "/programme/seance/move", name=nom, direction=direction)
    data = _data(fake_db)
    assert [k for k in data if not k.startswith("_")] == ordre
    assert data["_planning"]["Lundi"] == "Push"          # les clés techniques restent


def test_reinitialiser_une_seance_depuis_le_catalogue(fake_db, logged_in):
    _prog(fake_db, {"_origin": "fb_deb_3j", "Full Body A": [{"name": "Truc", "sets": 1, "muscle": "Autre"}]})
    _post(logged_in, "/programme/seance/reset", name="Full Body A")
    exos = _data(fake_db)["Full Body A"]
    assert len(exos) > 1 and exos[0]["name"] != "Truc"
    _post(logged_in, "/programme/seance/reset", name="Push")     # pas dans le catalogue : rien
    assert _data(fake_db)["Push"][0]["name"] == "Développé couché"


def test_sans_origine_catalogue_la_reinitialisation_ne_fait_rien(fake_db, logged_in):
    _prog(fake_db)
    _post(logged_in, "/programme/seance/reset", name="Push")
    assert len(_data(fake_db)["Push"]) == 2


# ── Exercices ────────────────────────────────────────────────────

def test_deplacer_et_supprimer_un_exercice(fake_db, logged_in):
    _prog(fake_db)
    _post(logged_in, "/programme/exo/move", seance="Push", index="1", direction="up")
    assert [e["name"] for e in _data(fake_db)["Push"]] == ["Dips", "Développé couché"]
    _post(logged_in, "/programme/exo/move", seance="Push", index="0", direction="up")   # bord : rien
    _post(logged_in, "/programme/exo/move", seance="Push", index="x")                  # index illisible
    assert [e["name"] for e in _data(fake_db)["Push"]] == ["Dips", "Développé couché"]
    _post(logged_in, "/programme/exo/delete", seance="Push", index="0")
    _post(logged_in, "/programme/exo/delete", seance="Push", index="9")                # hors liste : rien
    assert [e["name"] for e in _data(fake_db)["Push"]] == ["Développé couché"]


def test_modifier_un_exercice(fake_db, logged_in):
    _prog(fake_db)
    _post(logged_in, "/programme/exo/update", seance="Push", index="0", sets="5",
          reps="6-8", rest_seconds="9999", muscles=["Pecs", "Triceps"])
    ex = _data(fake_db)["Push"][0]
    assert (ex["sets"], ex["reps"], ex["rest_seconds"], ex["muscle"]) == (5, "6-8", 300, "Pecs,Triceps")
    _post(logged_in, "/programme/exo/update", seance="Push", index="0", reps="")
    assert "reps" not in _data(fake_db)["Push"][0]


# ── Export / import ──────────────────────────────────────────────

def test_lexport_est_reserve_au_pro_et_contient_le_programme(fake_db, logged_in, client):
    _prog(fake_db, {"_rotation": ["Push", "Pull"]})
    r = logged_in.get("/programme/export")
    assert r.status_code == 200 and r.mimetype == "application/json"
    data = json.loads(r.data)
    assert data["_format"] == rp.EXPORT_FORMAT and set(data["seances"]) == {"Push", "Pull", "Legs"}
    assert data["_rotation"] == ["Push", "Pull"]
    with client.session_transaction() as s:
        s.update(is_vip=False, is_vip_full=False, is_vip_ts=time.time())
    assert client.get("/programme/export").status_code == 403


def _importer(client, contenu, **form):
    return client.post("/programme/import", data={
        "_csrf": CSRF, "confirm": "yes", **form,
        "file": (io.BytesIO(contenu if isinstance(contenu, bytes) else json.dumps(contenu).encode()),
                 "prog.json")}, content_type="multipart/form-data")


@pytest.mark.parametrize("contenu,erreur", [
    (b"{pas du json", "parse"),
    ({"_format": "autre-app", "seances": {}}, "format"),
    ({"_format": rp.EXPORT_FORMAT, "seances": ["liste"]}, "format"),
])
def test_un_fichier_illisible_ou_etranger_est_refuse(fake_db, logged_in, contenu, erreur):
    _prog(fake_db)
    r = _importer(logged_in, contenu)
    assert f"import_err={erreur}" in r.headers["Location"]
    assert "Push" in _data(fake_db)


def test_import_sans_confirmation_ne_fait_rien(fake_db, logged_in):
    _prog(fake_db)
    r = logged_in.post("/programme/import", data={"_csrf": CSRF}, content_type="multipart/form-data")
    assert r.status_code == 302 and "Push" in _data(fake_db)


def test_un_import_ne_planifie_que_ses_propres_seances(fake_db, logged_in):
    _prog(fake_db)
    _importer(logged_in, {"_format": rp.EXPORT_FORMAT, "name": "Importé",
                          "seances": {"Haut": [{"name": "Dips", "sets": 3, "muscle": "Pecs"}]},
                          "_planning": {"Lundi": "Haut", "Mardi": "Séance fantôme"}})
    planning = _data(fake_db)["_planning"]
    assert planning["Lundi"] == "Haut" and planning["Mardi"] == ""


def test_changer_de_programme_demande_confirmation_et_respecte_le_pro(fake_db, logged_in, client):
    _prog(fake_db)
    _post(logged_in, "/programme/change-program", programme_id="fb_deb_3j")       # sans confirm
    assert "Full Body A" not in _data(fake_db)
    _post(logged_in, "/programme/change-program", programme_id="fb_deb_3j", confirm="yes")
    assert "Full Body A" in _data(fake_db)
    _post(logged_in, "/programme/change-program", programme_id="inconnu", confirm="yes")
    with client.session_transaction() as s:
        s.update(is_vip=False, is_vip_full=False, is_vip_ts=time.time())
    r = _post(client, "/programme/change-program", programme_id="ppl_4j", confirm="yes")
    assert r.status_code == 403 and "Push" not in _data(fake_db)


def test_fusionner_un_programme_garde_les_seances_existantes(fake_db, logged_in):
    _prog(fake_db)
    _post(logged_in, "/programme/change-program", programme_id="fb_deb_3j", confirm="yes", mode="merge")
    data = _data(fake_db)
    assert "Push" in data and "Full Body A" in data


def test_repartir_de_zero(fake_db, logged_in):
    _prog(fake_db)
    _post(logged_in, "/programme/change-program", programme_id="custom", confirm="yes")
    data = _data(fake_db)
    assert "Push" not in data or data["_planning"]["Lundi"] == ""
