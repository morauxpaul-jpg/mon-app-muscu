"""Fiche exercice et standards de force relatifs au gabarit."""
import datetime as dt

from conftest import USER_ID, CSRF
from core import exercise_stats, strength
from core.dates import continuous_week

D1 = dt.date(2026, 8, 3)


def _seed(fake, poids_kg=None, sexe=None):
    profile = {"id": USER_ID, "tier": "vip"}
    if poids_kg:
        profile["poids_kg"] = poids_kg
    fake.table("profiles").insert(profile).execute()
    if sexe:
        fake.table("onboarding").insert({"user_id": USER_ID, "sexe": sexe}).execute()
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": D1.isoformat(),
    }}).execute()


def _series(fake, date, poids, reps=8, exo="Développé couché", serie=1, rpe=None):
    fake.table("history").insert({
        "user_id": USER_ID, "semaine": continuous_week(date), "seance": "Push",
        "exercice": exo, "serie": serie, "reps": reps, "poids": poids,
        "remarque": "", "muscle": "Pecs", "date": date.isoformat(), "rpe": rpe,
    }).execute()


# ── Standards relatifs ───────────────────────────────────────────


def test_standard_depend_du_poids_de_corps():
    leger = strength.standard_for("Pecs", poids_kg=55, sexe="homme")
    lourd = strength.standard_for("Pecs", poids_kg=95, sexe="homme")
    assert leger < lourd
    assert leger == 55.0 and lourd == 95.0  # ratio 1.0 pour les pecs


def test_standard_depend_du_sexe():
    h = strength.standard_for("Quadriceps", poids_kg=70, sexe="homme")
    f = strength.standard_for("Quadriceps", poids_kg=70, sexe="femme")
    assert f < h


def test_sexe_non_precise_prend_la_moyenne():
    h = strength.standard_for("Pecs", poids_kg=70, sexe="homme")
    f = strength.standard_for("Pecs", poids_kg=70, sexe="femme")
    autre = strength.standard_for("Pecs", poids_kg=70, sexe="autre")
    assert f < autre < h


def test_sans_poids_on_retombe_sur_les_valeurs_absolues():
    assert strength.standard_for("Pecs") == 140.0
    assert strength.standard_for("Pecs", poids_kg=0) == 140.0
    assert not strength.is_relative(None)


def test_poids_aberrant_ignore():
    """Un poids en livres saisi par erreur ne doit pas fausser la carte."""
    assert strength.standard_for("Pecs", poids_kg=350) == 140.0
    assert strength.standard_for("Pecs", poids_kg=12) == 140.0


def test_niveau_lisible():
    assert strength.level_for(10) == "Débutant"
    assert strength.level_for(75) == "Intermédiaire"
    assert strength.level_for(140) == "Avancé"


def test_progres_annonce_la_base_des_standards(fake_db, logged_in):
    _seed(fake_db, poids_kg=72, sexe="homme")
    _series(fake_db, D1, 80.0)
    html = logged_in.get("/progres").get_data(as_text=True)
    assert "ton gabarit (72 kg)" in html


def test_progres_invite_a_saisir_son_poids(fake_db, logged_in):
    _seed(fake_db)
    _series(fake_db, D1, 80.0)
    html = logged_in.get("/progres").get_data(as_text=True)
    assert "Renseigne ton poids" in html


# ── Statistiques par exercice (fonctions pures) ──────────────────


def test_sessions_regroupe_par_seance():
    hist = [
        {"Exercice": "Squat", "Date": "2026-09-01", "Séance": "Legs", "Série": 1,
         "Reps": 8, "Poids": 100.0, "RPE": 8},
        {"Exercice": "Squat", "Date": "2026-09-01", "Séance": "Legs", "Série": 2,
         "Reps": 6, "Poids": 100.0, "RPE": 9},
        {"Exercice": "Squat", "Date": "2026-09-08", "Séance": "Legs", "Série": 1,
         "Reps": 8, "Poids": 105.0, "RPE": None},
    ]
    out = exercise_stats.sessions_for(hist, "Squat")
    assert len(out) == 2
    assert out[0]["date"] == "2026-09-08"          # la plus récente d'abord
    assert out[1]["volume"] == 8 * 100 + 6 * 100
    assert out[1]["sets"][0]["rpe"] == 8


def test_sessions_regroupe_les_variantes_du_meme_mouvement():
    hist = [
        {"Exercice": "Squat (Barre)", "Date": "2026-09-01", "Séance": "Legs",
         "Série": 1, "Reps": 5, "Poids": 100.0},
        {"Exercice": "Squat", "Date": "2026-09-08", "Séance": "Legs",
         "Série": 1, "Reps": 5, "Poids": 102.5},
    ]
    assert len(exercise_stats.sessions_for(hist, "Squat", by_base=True)) == 2
    assert len(exercise_stats.sessions_for(hist, "Squat", by_base=False)) == 1


def test_summary_calcule_records_et_progression():
    hist = [
        {"Exercice": "Squat", "Date": "2026-08-01", "Séance": "L", "Série": 1,
         "Reps": 5, "Poids": 100.0},
        {"Exercice": "Squat", "Date": "2026-09-01", "Séance": "L", "Série": 1,
         "Reps": 5, "Poids": 120.0},
    ]
    s = exercise_stats.summary(exercise_stats.sessions_for(hist, "Squat"))
    assert s["sessions"] == 2
    assert s["best_weight"] == 120.0
    assert s["best_weight_date"] == "2026-09-01"
    assert s["volume_total"] == 500 + 600
    assert s["delta_pct"] == 20      # 1RM 116.7 → 140


def test_summary_vide_sans_seance():
    assert exercise_stats.summary([]) == {}


def test_series_ordonne_du_plus_ancien_au_plus_recent():
    hist = [
        {"Exercice": "Squat", "Date": "2026-08-01", "Séance": "L", "Série": 1,
         "Reps": 5, "Poids": 100.0},
        {"Exercice": "Squat", "Date": "2026-09-01", "Séance": "L", "Série": 1,
         "Reps": 5, "Poids": 120.0},
    ]
    pts = exercise_stats.series(exercise_stats.sessions_for(hist, "Squat"), "best_weight")
    assert [p["value"] for p in pts] == [100.0, 120.0]


def test_sparkline_produit_une_polyline_bornee():
    pts = [{"date": "2026-08-01", "value": 100}, {"date": "2026-09-01", "value": 120}]
    chart = exercise_stats.sparkline(pts, width=600, height=160)
    assert len(chart["points"]) == 2
    assert chart["points"][0]["y"] > chart["points"][1]["y"]   # valeur plus haute = y plus petit
    for c in chart["points"]:
        assert 0 <= c["x"] <= 600 and 0 <= c["y"] <= 160
    assert chart["last"]["value"] == 120


def test_sparkline_valeurs_identiques_ne_divise_pas_par_zero():
    pts = [{"date": "2026-08-01", "value": 80}, {"date": "2026-09-01", "value": 80}]
    chart = exercise_stats.sparkline(pts)
    assert len(chart["points"]) == 2


# ── Page ─────────────────────────────────────────────────────────


def test_fiche_exercice_affiche_records_et_historique(fake_db, logged_in):
    _seed(fake_db, poids_kg=75, sexe="homme")
    for i, p in enumerate([70.0, 75.0, 80.0]):
        _series(fake_db, D1 + dt.timedelta(days=7 * i), p, reps=8)
    html = logged_in.get("/progres/exercice?exo=D%C3%A9velopp%C3%A9+couch%C3%A9")\
        .get_data(as_text=True)
    assert "Développé couché" in html
    assert "3 séances" in html
    assert "Toutes tes séances" in html
    assert "Charges estimées" in html      # table RM, l'user est VIP


def test_fiche_exercice_sans_donnees(fake_db, logged_in):
    _seed(fake_db)
    html = logged_in.get("/progres/exercice?exo=Inconnu").get_data(as_text=True)
    assert "Aucune série enregistrée" in html


def test_fiche_exercice_sans_parametre_redirige(fake_db, logged_in):
    _seed(fake_db)
    assert logged_in.get("/progres/exercice").status_code == 302


def test_fiche_exercice_accessible_aux_gratuits(fake_db, client):
    """La fiche est la base offerte par les concurrents : elle reste gratuite."""
    import time
    _seed(fake_db)
    _series(fake_db, D1, 80.0)
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time(), _csrf=CSRF)
    html = client.get("/progres/exercice?exo=D%C3%A9velopp%C3%A9+couch%C3%A9")\
        .get_data(as_text=True)
    assert "Toutes tes séances" in html
    assert "Charges estimées par nombre de reps" not in html   # table RM = PRO


def test_progres_ne_charge_plus_plotly(fake_db, logged_in):
    """3,5 Mo de bibliothèque pour tracer une ligne de 8 points : remplacé
    par du SVG calculé côté serveur."""
    _seed(fake_db)
    _series(fake_db, D1, 80.0)
    html = logged_in.get("/progres").get_data(as_text=True)
    assert "plot.ly" not in html
    assert "Plotly" not in html


# ── Courbe de force : période, tendance, comparaison, records ────
# Audit du 06/10 (axe 4) : « pas de courbe d'e1RM avec tendance ni de
# comparaison entre périodes comme chez Strong ».

from core.dates import today_paris  # noqa: E402

AUJ = dt.date(2026, 10, 11)


def _seance(date, *series, exo="Squat"):
    """series : (poids, reps), …"""
    return [{"Exercice": exo, "Date": date, "Séance": "L", "Série": i + 1,
             "Reps": r, "Poids": float(p)} for i, (p, r) in enumerate(series)]


def _points(valeurs, debut=dt.date(2026, 6, 1), pas=7):
    return [{"date": (debut + dt.timedelta(days=pas * i)).isoformat(), "value": v}
            for i, v in enumerate(valeurs)]


def test_series_marque_les_records_et_ignore_le_poids_du_corps():
    hist = (_seance("2026-08-01", (100, 5)) + _seance("2026-08-08", (0, 12))
            + _seance("2026-08-15", (95, 5)) + _seance("2026-08-22", (105, 5)))
    sess = exercise_stats.sessions_for(hist, "Squat")
    pts = exercise_stats.series(sess, "best_weight")
    assert [(p["value"], p["record"]) for p in pts] == [(100, False), (95, False), (105, True)]
    # En répétitions, la séance sans charge compte.
    assert len(exercise_stats.series(sess, "best_reps")) == 4
    assert exercise_stats.series(sess, "best_reps")[1]["value"] == 12


def test_periode_garde_les_derniers_jours():
    pts = _points([1, 2, 3], debut=dt.date(2026, 7, 1), pas=30)   # 01/07, 31/07, 30/08
    debut = exercise_stats.debut_periode("1m", AUJ)
    assert debut == "2026-09-12"
    assert exercise_stats.dans_periode(pts, debut) == []
    assert len(exercise_stats.dans_periode(pts, exercise_stats.debut_periode("3m", AUJ))) == 2
    assert len(exercise_stats.dans_periode(pts, exercise_stats.debut_periode("tout", AUJ))) == 3


def test_tendance_donne_la_pente_par_mois():
    t = exercise_stats.tendance(_points([40, 40.5, 41, 41.5, 42, 42.5]))   # +0,5 kg / semaine
    assert t["sens"] == "hausse"
    assert t["par_mois"] == round(0.5 / 7 * 30.44, 1) == 2.2
    assert t["debut"]["value"] == 40 and t["fin"]["value"] == 42.5


def test_tendance_stable_et_baisse():
    assert exercise_stats.tendance(_points([50, 50.4, 49.8, 50.2, 50]))["sens"] == "stable"
    assert exercise_stats.tendance(_points([60, 58, 57, 55, 54]))["sens"] == "baisse"


def test_pas_de_tendance_sans_assez_de_seances_ni_de_recul():
    assert exercise_stats.tendance(_points([40, 41, 42])) is None              # 3 séances
    assert exercise_stats.tendance(_points([40, 41, 42, 43], pas=5)) is None   # 15 jours
    assert exercise_stats.tendance(_points([0, 0, 0, 0])) is None


def test_tendance_ne_tombe_pas_a_zero_quand_les_valeurs_se_repetent():
    """Vrai historique, 11/10 : des dips à 10 reps séance après séance, puis
    20 à 24. La médiane des pentes (Theil-Sen) disait « stable, 0 par mois »."""
    t = exercise_stats.tendance(_points([10] * 12 + [20, 10, 20, 24, 20, 14]))
    assert t["sens"] == "hausse" and t["par_mois"] > 0.5


def test_une_faute_de_frappe_ne_fait_pas_basculer_la_tendance():
    juste = exercise_stats.tendance(_points([45, 46, 45, 47, 46, 47, 46, 48, 47, 48]))
    faute = exercise_stats.tendance(_points([45, 46, 45, 47, 460, 47, 46, 48, 47, 48]))
    assert faute["sens"] == juste["sens"] == "hausse"
    assert abs(faute["par_mois"] - juste["par_mois"]) <= 0.3


def test_une_faute_sur_la_derniere_seance_est_mise_de_cote():
    """La faute la plus probable : la séance qu'on vient de saisir. Jugée
    par son écart à une première droite, elle passait : la droite allait la
    chercher (+195 kg par mois, essayé le 11/10)."""
    pts = _points([40, 40, 41, 40, 41, 41, 42, 41, 42, 420])
    t = exercise_stats.tendance(pts)
    assert t["sens"] == "hausse" and 0 < t["par_mois"] < 3
    assert t["fin"]["date"] == pts[-2]["date"]           # la droite s'arrête avant elle


def test_un_historique_qui_triple_n_est_pas_une_faute():
    """Plus d'une séance sur dix « hors norme » : c'est la progression d'un
    débutant, pas une faute de frappe. Rien n'est écarté."""
    t = exercise_stats.tendance(_points([10, 12, 15, 20, 25, 30, 35, 40, 45, 50]))
    assert t["debut"]["date"] == "2026-06-01" and t["par_mois"] > 15


def test_comparaison_avec_la_periode_d_avant():
    hist = (_seance("2026-06-10", (100, 5))                            # hors des deux fenêtres
            + _seance("2026-08-20", (100, 5), (100, 5))                # 1 mois d'avant
            + _seance("2026-09-20", (110, 5)) + _seance("2026-10-05", (100, 5)))
    c = exercise_stats.comparaison(exercise_stats.sessions_for(hist, "Squat"), "1m", AUJ)
    assert (c["titre"], c["titre_avant"]) == ("30 derniers jours", "30 jours d'avant")
    seances, force, volume = c["lignes"]
    assert (seances["actuel"], seances["avant"], seances["delta_pct"]) == (2, 1, 100)
    assert force["actuel"] == round(110 * (1 + 5 / 30), 1) and force["delta_pct"] == 10
    assert (volume["actuel"], volume["avant"], volume["delta_pct"]) == (1050, 1000, 5)
    assert exercise_stats.comparaison(exercise_stats.sessions_for(hist, "Squat"), "tout", AUJ) is None


def test_comparaison_sans_periode_d_avant():
    hist = _seance("2026-10-05", (100, 5))
    c = exercise_stats.comparaison(exercise_stats.sessions_for(hist, "Squat"), "3m", AUJ)
    assert c["avant_vide"] and c["lignes"][0]["avant"] is None and c["lignes"][0]["delta_pct"] is None


def test_comparaison_au_poids_du_corps_parle_en_repetitions():
    hist = _seance("2026-10-05", (0, 20), exo="Dips") + _seance("2026-09-01", (0, 10), (0, 10), exo="Dips")
    c = exercise_stats.comparaison(exercise_stats.sessions_for(hist, "Dips"), "1m", AUJ,
                                   poids_du_corps=True)
    assert [l["libelle"] for l in c["lignes"]] == ["Séances", "Meilleure série", "Répétitions"]
    assert (c["lignes"][1]["actuel"], c["lignes"][1]["avant"], c["lignes"][1]["delta_pct"]) == (20, 10, 100)


def test_records_par_reps_au_moins_et_premiere_fois():
    hist = (_seance("2026-08-01", (100, 6), (80, 12))
            + _seance("2026-09-01", (100, 5), (102.5, 3))
            + _seance("2026-09-10", (0, 30)))
    recs = exercise_stats.records_par_reps(exercise_stats.sessions_for(hist, "Squat"))
    lignes = [(r["de"], r["a"], r["poids"], r["reps_faites"], r["date"]) for r in recs]
    assert lignes == [
        (1, 3, 102.5, 3, "2026-09-01"),
        (5, 5, 100.0, 6, "2026-08-01"),          # 100 × 6 le 01/08, avant 100 × 5 le 01/09
        (8, 12, 80.0, 12, "2026-08-01"),         # une seule ligne pour 8, 10 et 12
    ]


def test_poids_du_corps_a_la_majorite_des_seances():
    """Vrai historique, 11/10 : 21 séances de tractions sans charge, une à
    +10 kg. « Jamais chargé » ne suffisait pas : la courbe n'avait qu'un point."""
    hist = []
    for i in range(5):
        hist += _seance(f"2026-09-{10 + i:02d}", (0, 8 + i), exo="Tractions")
    hist += _seance("2026-09-20", (10, 5), exo="Tractions")
    s = exercise_stats.summary(exercise_stats.sessions_for(hist, "Tractions"))
    assert s["poids_du_corps"] and s["best_reps"] == 12 and s["best_reps_date"] == "2026-09-14"
    hist += _seance("2026-09-21", (10, 5), exo="Tractions")
    for j in range(5):
        hist += _seance(f"2026-09-{22 + j}", (10, 6), exo="Tractions")
    assert not exercise_stats.summary(exercise_stats.sessions_for(hist, "Tractions"))["poids_du_corps"]


def test_sparkline_place_les_points_a_leur_date_et_coupe_la_tendance():
    pts = [{"date": "2026-09-01", "value": 40}, {"date": "2026-09-02", "value": 42},
           {"date": "2026-09-21", "value": 41}]
    tend = {"debut": {"date": "2026-09-01", "value": 38}, "fin": {"date": "2026-09-21", "value": 44}}
    c = exercise_stats.sparkline(pts, tendance=tend)
    xs = [p["x"] for p in c["points"]]
    assert xs[1] - xs[0] < (xs[2] - xs[1]) / 10          # 1 jour contre 19 jours
    assert c["etiquettes"] == {"haut": 42, "bas": 40}     # les vraies valeurs, pas la droite
    t = c["tendance"]
    assert 14 <= t["y1"] <= 140 and 14 <= t["y2"] <= 140   # dans la zone tracée
    assert t["x1"] > xs[0] and t["x2"] < xs[2]            # coupée aux bords
    plat = exercise_stats.sparkline([{"date": "2026-09-01", "value": 0, "record": False}] * 2)
    assert plat["etiquettes"] is None


def test_nombre_fr():
    f = exercise_stats.nombre_fr
    assert (f(1234.5), f(80.0), f(2.25), f(None)) == ("1 234,5", "80", "2,2", "—")
    assert (f(1.4, True), f(-0.8, True), f(0.02, True)) == ("+1,4", "−0,8", "0")


# ── Page : courbe de force ───────────────────────────────────────

EXO_URL = "/progres/exercice?exo=D%C3%A9velopp%C3%A9+couch%C3%A9"


def _historique_regulier(fake, semaines=10, exo="Développé couché", poids0=60.0, pas=1.0, reps=8):
    aujourdhui = today_paris()
    for i in range(semaines):
        d = aujourdhui - dt.timedelta(days=7 * (semaines - 1 - i) + 1)
        p = poids0 + pas * i if poids0 else 0.0
        _series(fake, d, p, reps=reps, exo=exo)
        _series(fake, d, p, reps=reps, exo=exo, serie=2)


def test_fiche_trace_la_tendance_et_compare_les_periodes(fake_db, logged_in):
    _seed(fake_db)
    _historique_regulier(fake_db)
    html = logged_in.get(EXO_URL).get_data(as_text=True)
    assert 'class="periode-chip on"' in html and ">3 mois</a>" in html   # période par défaut
    assert 'class="exo-trend"' in html
    assert "En hausse" in html and "kg par mois" in html
    assert "3 derniers mois contre les 3 mois d&#39;avant" in html or \
           "3 derniers mois contre les 3 mois d'avant" in html
    assert "Tes records par répétitions" in html
    # Les onglets de mesure gardent la période, et l'inverse.
    assert "&m=volume&p=3m" in html and "&m=e1rm&p=6m" in html


def test_fiche_record_battu_marque_sur_la_courbe(fake_db, logged_in):
    _seed(fake_db)
    _historique_regulier(fake_db, semaines=5)
    html = logged_in.get(EXO_URL + "&p=tout").get_data(as_text=True)
    assert html.count('class="exo-pt rec') == 4          # chaque séance bat la précédente
    assert "Record battu (4)" in html


def test_fiche_periode_vide_propose_tout_l_historique(fake_db, logged_in):
    _seed(fake_db)
    _series(fake_db, today_paris() - dt.timedelta(days=200), 60.0)
    _series(fake_db, today_paris() - dt.timedelta(days=190), 62.5)
    # Sans choix : on montre l'histoire plutôt qu'un graphique vide.
    html = logged_in.get(EXO_URL).get_data(as_text=True)
    assert 'class="exo-chart"' in html
    assert 'class="periode-chip on"' in html
    assert html.split('class="periode-chip on"')[1].split("</a>")[0].endswith(">Tout")
    # Choix explicite d'une période vide : le dire, et proposer tout.
    html = logged_in.get(EXO_URL + "&p=1m").get_data(as_text=True)
    assert "Pas assez de séances sur 1 mois" in html and "&m=e1rm&p=tout" in html


def test_fiche_poids_du_corps_en_repetitions(fake_db, logged_in):
    _seed(fake_db)
    _historique_regulier(fake_db, exo="Dips", poids0=0, reps=10)
    html = logged_in.get("/progres/exercice?exo=Dips").get_data(as_text=True)
    assert ">Meilleure série</a>" in html and ">Force estimée</a>" not in html
    assert "Tes records par répétitions" not in html
    assert "1RM <strong>0" not in html and "0 kg" not in html.split("Toutes tes séances")[1]
    # Le grand chiffre d'en-tête est la meilleure série, en répétitions.
    assert "Meilleure série" in html.split('class="exo-hero"')[1][:400]
