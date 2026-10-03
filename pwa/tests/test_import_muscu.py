"""Import de l'historique Hevy / Strong (audit du 03/10).

Les échantillons reprennent la forme réelle des deux exports : en-têtes,
séparateurs, dates locales, échauffements, livres."""
import io

from conftest import CSRF, USER_ID
from core.import_muscu import lire_export, lignes_historique, compacter, nom_exercice

HEVY = '''"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"
"Push Day","28 Sep 2026, 18:05","28 Sep 2026, 19:10","","Bench Press (Barbell)",,"",0,"warmup",40,10,,,
"Push Day","28 Sep 2026, 18:05","28 Sep 2026, 19:10","","Bench Press (Barbell)",,"",1,"normal",80,8,,,8
"Push Day","28 Sep 2026, 18:05","28 Sep 2026, 19:10","","Bench Press (Barbell)",,"",2,"failure",80,7,,,10
"Push Day","28 Sep 2026, 18:05","28 Sep 2026, 19:10","","Lateral Raise (Dumbbell)",,"",0,"normal",10,15,,,
"Push Day","28 Sep 2026, 18:05","28 Sep 2026, 19:10","","Treadmill",,"",0,"normal",,,2.5,900,
"Leg Day","30 Sep 2026, 07:30","30 Sep 2026, 08:30","","Squat (Barbell)",,"",0,"normal",100,5,,,
'''

STRONG = '''Date;Workout Name;Duration;Exercise Name;Set Order;Weight;Reps;Distance;Seconds;Notes;Workout Notes;RPE;Weight Unit
2026-09-21 10:00:00;Full Body A;1h;Deadlift (Barbell);W;135;5;0;0;;;;lbs
2026-09-21 10:00:00;Full Body A;1h;Deadlift (Barbell);1;225;5;0;0;;;;lbs
2026-09-21 10:00:00;Full Body A;1h;Lat Pulldown (Cable);1;50;10;0;0;;;;kg
'''


def test_hevy_lu_echauffements_et_cardio_ecartes():
    seances, rapport = lire_export(HEVY.encode())
    assert rapport["source"] == "Hevy"
    assert rapport["echauffements"] == 1 and rapport["sans_reps"] == 1
    assert [(s["date"], s["seance"]) for s in seances] == [
        ("2026-09-28", "Push Day"), ("2026-09-30", "Leg Day")]
    push = seances[0]["exercices"]
    assert push[0]["nom"] == "Développé couché"
    assert push[0]["series"] == [{"reps": 8, "poids": 80.0, "rpe": 8.0},
                                 {"reps": 7, "poids": 80.0, "rpe": 10.0}]
    assert push[1]["nom"] == "Élévations latérales"
    assert push[0]["muscle"] == "Pecs"


def test_strong_point_virgule_et_livres_converties():
    seances, rapport = lire_export(STRONG.encode("utf-8-sig"))
    assert rapport["source"] == "Strong" and rapport["echauffements"] == 1
    (s,) = seances
    sdt, tirage = s["exercices"]
    assert sdt["nom"] == "Soulevé de terre"
    assert sdt["series"][0]["poids"] == 102.0          # 225 lbs, au quart de kg
    assert tirage["nom"] == "Tirage vertical" and tirage["series"][0]["poids"] == 50.0


def test_fichier_etranger_ne_produit_rien():
    seances, rapport = lire_export(b"name,age\nAlex,30\n")
    assert seances == [] and rapport["lignes"] == 0


def test_inconnu_garde_son_nom():
    assert nom_exercice("Zottman Curl") == "Zottman Curl"
    assert nom_exercice("Bench Press (Dumbbell)") == "Développé couché (Haltères)"


def test_charge_trafiquee_revalidee():
    lignes = lignes_historique([
        ["2026-09-28", "Push", [["Développé couché", "Pecs", [[8, 80, 8], [-3, 80, None],
                                                            ["x", 1, None], [5, 99999, 42]]]]],
        ["pas une date", "Push", [["Squat", "Quadriceps", [[5, 100, None]]]]],
        ["2026-09-28", "_planning", [["Squat", "Quadriceps", [[5, 100, None]]]]],
        ["2026-09-28", "Push", [["CARDIO:Course", "Cardio", [[30, 5, None]]]]],
    ], "Hevy")
    assert [(l["Reps"], l["Poids"], l["RPE"]) for l in lignes] == [(8, 80.0, 8.0), (5, 1000.0, None)]
    assert lignes[0]["Remarque"] == "Import Hevy"


# ── Parcours ─────────────────────────────────────────────────────


def _deposer(client, texte):
    return client.post("/gestion/import-muscu", data={
        "_csrf": CSRF, "fichier": (io.BytesIO(texte.encode()), "workouts.csv")},
        content_type="multipart/form-data", headers={"X-CSRFToken": CSRF})


def _confirmer(client, html):
    import html as _h
    import re
    charge = _h.unescape(re.search(r'name="charge" value="([^"]*)"', html).group(1))
    source = re.search(r'name="source" value="([^"]*)"', html).group(1)
    return client.post("/gestion/import-muscu/confirmer",
                       data={"_csrf": CSRF, "charge": charge, "source": source},
                       headers={"X-CSRFToken": CSRF})


def test_apercu_n_ecrit_rien_puis_confirmation_ecrit(fake_db, logged_in):
    r = _deposer(logged_in, HEVY)
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "Importer ces 2 séances" in html
    assert "Bench Press (Barbell)" in html and "Développé couché" in html
    assert not fake_db.tables.get("history")

    fin = _confirmer(logged_in, html).get_data(as_text=True)
    assert "2 séances importées (4 séries)" in fin
    rows = fake_db.tables["history"]
    assert {(r["user_id"], r["exercice"], r["poids"], r["reps"]) for r in rows} == {
        (USER_ID, "Développé couché", 80.0, 8), (USER_ID, "Développé couché", 80.0, 7),
        (USER_ID, "Élévations latérales", 10.0, 15), (USER_ID, "Squat", 100.0, 5)}
    assert {r["rpe"] for r in rows if r["reps"] == 7} == {10.0}


def test_reimport_ne_double_rien(fake_db, logged_in):
    html = _deposer(logged_in, HEVY).get_data(as_text=True)
    _confirmer(logged_in, html)
    n = len(fake_db.tables["history"])
    html2 = _deposer(logged_in, HEVY).get_data(as_text=True)
    assert "Rien de nouveau à importer" in html2
    _confirmer(logged_in, html)                  # double envoi du 1er formulaire
    assert len(fake_db.tables["history"]) == n


def test_compte_gratuit_peut_importer_et_page_accessible(fake_db, logged_in):
    assert logged_in.get("/gestion/import-muscu").status_code == 200
    assert "/gestion/import-muscu" in logged_in.get("/gestion").get_data(as_text=True)


def test_compacter_aller_retour():
    seances, _ = lire_export(HEVY.encode())
    lignes = lignes_historique(compacter(seances), "Hevy")
    assert len(lignes) == 4 and {l["Série"] for l in lignes if l["Exercice"] == "Développé couché"} == {1, 2}
