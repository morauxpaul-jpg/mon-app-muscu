"""Semaine allégée proposée quand la fatigue s'accumule (audit du 03/10, idée 10)."""
import datetime as dt

from conftest import CSRF, USER_ID
from core.decharge import a_proposer, diagnostic, semaine_allegee
from core.seance_contexte import _build_exo_context

W = 200   # semaine « courante » (index continu)


def _s(sem, exo, poids, reps, rpe=None):
    return {"Semaine": sem, "Exercice": exo, "Poids": poids, "Reps": reps, "RPE": rpe,
            "Date": f"2026-01-{(sem % 28) + 1:02d}", "Séance": "A", "Remarque": "", "Muscle": "Pecs"}


def _carnet(recul=True, rpe_derniere=9.5, semaines=5, exos=("Squat", "Développé couché", "Rowing barre")):
    rows = []
    for k in range(semaines):
        sem = W - semaines + k            # la dernière = W - 1
        derniere = sem == W - 1
        for exo in exos:
            poids = 100 + 2.5 * k
            if derniere and recul:
                poids = 100 + 2.5 * (k - 2) - 2.5      # sous le meilleur récent de > 3 %
            rows += [_s(sem, exo, poids, 5, rpe_derniere if derniere else 8)] * 3
    return rows


def test_recul_et_rpe_haut_apres_cinq_semaines():
    d = diagnostic(_carnet(), W)
    assert d and d["semaines"] == 5 and len(d["exercices"]) == 3
    assert any("reculent" in r for r in d["raisons"]) and any("RPE moyen 9,5" in r for r in d["raisons"])


def test_un_seul_signe_ne_suffit_pas():
    assert diagnostic(_carnet(recul=False), W) is None                       # RPE seul
    assert diagnostic(_carnet(rpe_derniere=8, exos=("Squat", "Rowing barre")), W) is None   # recul sur 2 seulement


def test_recul_large_suffit_sans_rpe():
    assert diagnostic(_carnet(rpe_derniere=None), W)                         # 3 exercices en recul


def test_pas_avant_quatre_semaines_ni_apres_une_semaine_legere():
    assert diagnostic(_carnet(semaines=3), W) is None
    rows = [r for r in _carnet(semaines=6) if not (r["Semaine"] == W - 3 and r["Exercice"] != "Squat")]
    assert diagnostic(rows, W) is None                                       # W-3 déjà allégée


def test_ignoree_ou_appliquee_cette_semaine():
    hist = _carnet()
    assert a_proposer(hist, {"_decharge_ignoree": W}, W) is None
    assert a_proposer(hist, {"_decharge_semaine": W}, W) is None
    assert a_proposer(hist, {"_decharge_ignoree": W - 1}, W)
    assert semaine_allegee({"_decharge_semaine": W}, W) and not semaine_allegee({}, W)


def test_seance_allegee_moitie_des_series_et_moins_10_pourcent():
    hist = [{"Semaine": W - 1, "Séance": "A", "Exercice": "Squat", "Série": i, "Reps": 5,
             "Poids": 100.0, "Remarque": "", "Muscle": "Quadriceps", "Date": "2026-09-14", "RPE": None}
            for i in (1, 2, 3)]
    exo = {"name": "Squat", "sets": 5, "muscle": "Quadriceps", "reps": "5"}
    normal = _build_exo_context(hist, exo, "A", W, "2026-09-21")
    allege = _build_exo_context(hist, exo, "A", W, "2026-09-21", decharge=True)
    assert normal["p_sets"] == 5 and allege["p_sets"] == 3
    assert allege["suggestion"]["poids"] == 90.0 and allege["suggestion"]["why"] == "decharge"
    assert allege["sets"][0]["poids"] == 90.0                                # pré-rempli allégé
    assert normal["suggestion"]["why"] != "decharge"


def test_parcours_accueil(fake_db, logged_in):
    from core.dates import continuous_week, logical_today_paris
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {"_settings": {}}}).execute()
    semaine = continuous_week(logical_today_paris())
    for r in _carnet():
        decal = semaine - W
        lundi = dt.date(2024, 1, 1) + dt.timedelta(weeks=r["Semaine"] + decal - 1)
        fake_db.table("history").insert({
            "user_id": USER_ID, "semaine": 1, "seance": "A", "exercice": r["Exercice"],
            "serie": 1, "reps": r["Reps"], "poids": r["Poids"], "remarque": "",
            "muscle": "Pecs", "date": lundi.isoformat(), "rpe": r["RPE"]}).execute()
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert "Une semaine plus légère te ferait du bien" in html

    logged_in.post("/accueil/decharge", data={"_csrf": CSRF, "choix": "appliquer"})
    assert fake_db.tables["programs"][0]["data"]["_decharge_semaine"] == semaine
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert "Semaine allégée en cours" in html and "te ferait du bien" not in html

    logged_in.post("/accueil/decharge", data={"_csrf": CSRF, "choix": "annuler"})
    logged_in.post("/accueil/decharge", data={"_csrf": CSRF, "choix": "ignorer"})
    data = fake_db.tables["programs"][0]["data"]
    assert "_decharge_semaine" not in data and data["_decharge_ignoree"] == semaine
    assert "te ferait du bien" not in logged_in.get("/accueil").get_data(as_text=True)


def test_le_coach_sait_que_la_semaine_est_allegee():
    from core.dates import continuous_week, logical_today_paris
    from routes.coach import _programme_detail
    prog = {"A": [{"name": "Squat", "sets": 3}], "_planning": {"Lundi": "A"},
            "_decharge_semaine": continuous_week(logical_today_paris())}
    assert "Semaine allégée en cours" in _programme_detail(prog)
    prog.pop("_decharge_semaine")
    assert "Semaine allégée" not in _programme_detail(prog)
