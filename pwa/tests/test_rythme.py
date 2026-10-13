"""La cible qui suit le poids réel (core/nutrition_rythme.py).

La cible calculée est une estimation ; la balance dit ce qui se passe. Sur
six semaines, le rythme des pesées est comparé à la fourchette de
l'objectif, et une nouvelle cible est proposée — jamais appliquée seule.
"""
from datetime import date, timedelta

import pytest

from conftest import CSRF, USER_ID, prog_lu
from core import nutrition_rythme as nr

AUJ = date(2026, 10, 12)
# Les pesées réelles du compte de l'auteur, 31/08 → 12/10 (relevé du 12/10).
REELLES = [("2026-09-08", 92.6), ("2026-09-16", 93.0), ("2026-09-22", 92.4),
           ("2026-09-26", 92.5), ("2026-09-27", 91.8), ("2026-10-07", 91.4)]


def _pesees(liste):
    return [{"date": d, "poids_kg": kg} for d, kg in liste]


def _reguliere(kg_semaine, debut=95.0, semaines=6):
    """Une pesée par semaine, sur une droite."""
    return [{"date": (AUJ - timedelta(days=7 * i)).isoformat(),
             "poids_kg": debut + kg_semaine * (semaines - i)} for i in range(semaines, -1, -1)]


def test_sur_les_vraies_pesees_la_seche_est_un_peu_lente():
    r = nr.rythme(_pesees(REELLES), "seche", AUJ, 2400, 1932)
    assert r["etat"] == "au_dessus" and r["kg_semaine"] == pytest.approx(-0.33, abs=0.01)
    assert r["fourchette_kg"] == (pytest.approx(-0.92, abs=0.01), pytest.approx(-0.46, abs=0.01))
    # Le plus petit pas qui ramène dans la fourchette : 0,13 kg/sem ≈ 140 kcal/j.
    assert r["proposition"] == {"cible": 2250, "ecart": -150}
    ph = nr.phrases(r, "seche")
    assert ph["constat"] == "tu perds 0,33 kg par semaine"
    assert ph["vise"] == "En sèche, le conseil : perdre 0,46 à 0,92 kg par semaine"
    assert ph["verdict"] == "Tu perds moins vite que conseillé."


def test_une_pente_ne_se_lit_pas_sur_une_seule_pesee_aberrante():
    """La droite passe au milieu : une pesée isolée (repas salé, déshydratation)
    ne fait pas le rythme."""
    stable = _reguliere(0.0)
    bruit = [dict(p) for p in stable]
    bruit[3]["poids_kg"] += 2.0
    assert abs(nr.rythme(bruit, "maintien", AUJ, 2500)["kg_semaine"]) < 0.1


@pytest.mark.parametrize("objectif, kg_semaine, etat", [
    ("seche", -0.6, "dans_la_cible"),
    ("seche", -1.2, "en_dessous"),      # trop vite
    ("seche", 0.2, "au_dessus"),        # ne perd pas
    ("masse", 0.3, "dans_la_cible"),
    ("masse", 0.0, "en_dessous"),
    ("masse", 0.8, "au_dessus"),
    ("maintien", 0.1, "dans_la_cible"),
    ("maintien", -0.5, "en_dessous"),
])
def test_le_verdict_suit_l_objectif(objectif, kg_semaine, etat):
    r = nr.rythme(_reguliere(kg_semaine), objectif, AUJ, 2500, 1800)
    assert r["etat"] == etat
    if etat == "dans_la_cible":
        assert r["proposition"] is None
    else:
        # Manger moins si l'on est au-dessus de la fourchette, plus en dessous.
        assert (r["proposition"]["ecart"] < 0) == (etat == "au_dessus")


def test_un_pas_a_la_fois():
    r = nr.rythme(_reguliere(0.5), "seche", AUJ, 2500, 1800)     # prend 0,5 kg/sem en sèche
    assert r["proposition"] == {"cible": 2200, "ecart": -300}


def test_jamais_sous_le_metabolisme_de_base():
    r = nr.rythme(_reguliere(0.3), "seche", AUJ, 2000, 1932)
    assert r["proposition"] == {"cible": 1950, "ecart": -50}
    r = nr.rythme(_reguliere(0.3), "seche", AUJ, 1950, 1932)
    assert r["proposition"] is None and r["plancher"]


def test_apres_un_ajustement_on_laisse_deux_semaines_au_poids():
    r = nr.rythme(_pesees(REELLES), "seche", AUJ, 2250, 1932, ajuste_le="2026-10-05")
    assert r["proposition"] is None and r["attente_jusquau"] == "2026-10-19"
    r = nr.rythme(_pesees(REELLES), "seche", AUJ, 2250, 1932, ajuste_le="2026-09-20")
    assert r["proposition"] is not None


@pytest.mark.parametrize("liste", [
    [],
    [("2026-10-01", 92.0), ("2026-10-07", 91.4)],                      # 2 pesées
    [("2026-10-01", 92.0), ("2026-10-04", 91.8), ("2026-10-07", 91.4)],  # 6 jours
    [("2026-06-01", 95.0), ("2026-07-01", 94.0), ("2026-10-07", 91.4)],  # hors fenêtre
])
def test_pas_assez_de_pesees_on_le_dit_au_lieu_d_inventer(liste):
    r = nr.rythme(_pesees(liste), "seche", AUJ, 2400, 1932)
    assert r["etat"] == "manque" and "proposition" not in r
    assert nr.phrases(r, "seche") == {}


# ── Page et bouton ───────────────────────────────────────────────

PROFIL = {"poids_kg": 91.4, "taille_cm": 186.0, "age": 30, "sexe": "H",
          "activite": "actif", "objectif_nutrition": "seche"}


@pytest.fixture()
def compte(fake_db, logged_in, monkeypatch):
    from routes import nutrition
    monkeypatch.setattr(nutrition, "today_paris", lambda: AUJ)
    monkeypatch.setattr(nutrition, "today_paris_str", lambda: AUJ.isoformat())
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip", **PROFIL,
                                      "calories_cible": 2400}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {}, "_upsell_seen": True,
        "_nutrition": {"calories_custom": 2400}}}).execute()
    for d, kg in REELLES:
        fake_db.table("body_weight").insert({"user_id": USER_ID, "date": d, "poids_kg": kg}).execute()
    return fake_db


def test_la_carte_propose_et_le_bouton_applique(compte, client):
    page = client.get("/nutrition").get_data(as_text=True)
    assert "TON RYTHME RÉEL" in page and "tu perds 0,33 kg par semaine" in page
    assert "Passer à 2250 kcal par jour (−150)" in page

    r = client.post("/nutrition/cible/ajuster", data={"_csrf": CSRF, "cible": "2250"})
    assert r.status_code == 302 and "cible=ajustee" in r.headers["Location"]
    nutri = prog_lu()["_nutrition"]
    assert nutri == {"calories_custom": 2250, "ajuste_le": "2026-10-12", "ajuste_de": 2400}
    assert compte.tables["profiles"][0]["calories_cible"] == 2250

    apres = client.get("/nutrition?cible=ajustee").get_data(as_text=True)
    assert "ta cible est à 2250 kcal" in apres
    assert "Passer à 2" not in apres and "jusqu'au 26/10 pour répondre" in apres


def test_une_proposition_perimee_n_est_pas_appliquee(compte, client):
    r = client.post("/nutrition/cible/ajuster", data={"_csrf": CSRF, "cible": "1500"})
    assert "cible=change" in r.headers["Location"]
    assert prog_lu()["_nutrition"] == {"calories_custom": 2400}


def test_un_jour_passe_n_affiche_pas_le_rythme(compte, client):
    page = client.get("/nutrition?date=2026-10-01").get_data(as_text=True)
    assert "TON RYTHME RÉEL" not in page


def test_sans_pesees_la_carte_dit_ce_qui_manque(compte, client):
    compte.tables["body_weight"] = []
    page = client.get("/nutrition").get_data(as_text=True)
    assert "il faut au moins 3 pesées sur 2 semaines" in page and "tu en as 0" in page
