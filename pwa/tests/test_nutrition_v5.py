"""Nutrition (audit du 03/10, axe resté à 5) : cibles reliées au corps et à
l'entraînement, repas détaillés aliment par aliment, recherche élargie."""
import json
import time
from datetime import date, timedelta

import pytest

from conftest import CSRF, USER_ID, prog_lu
from core import nutrition_cibles as nc
from core import nutrition_aliments as na
from core import openfoodfacts as off
from core import partage
from core.dates import DAYS_FR, today_paris

PROFIL = {"poids_kg": 80.0, "taille_cm": 180.0, "age": 30, "sexe": "H",
          "activite": "actif", "objectif_nutrition": "seche"}
BANANE = {"n": "Banane", "k": 89, "p": 1.1, "c": 20, "f": 0.3, "u": [["1 banane", 120], ["100 g", 100]]}
RIZ = {"n": "Riz blanc cuit", "k": 130, "p": 2.7, "c": 28, "f": 0.3, "u": [["1 portion", 200]]}


def _profil(fake, **extra):
    fake.table("profiles").insert({"id": USER_ID, "tier": "vip", **PROFIL,
                                   "calories_cible": 2400, **extra}).execute()


def _prog(fake, planning=None, nutrition=None):
    data = {"Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
            "_planning": planning or {}, "_settings": {}, "_upsell_seen": True}
    if nutrition is not None:
        data["_nutrition"] = nutrition
    fake.table("programs").insert({"user_id": USER_ID, "data": data}).execute()


def _repas(fake):
    return [r for r in fake.tables.get("nutrition", []) if r["user_id"] == USER_ID]


# ── Cibles ───────────────────────────────────────────────────────

def test_les_proteines_suivent_le_poids_et_non_les_calories():
    t = nc.compute_targets(PROFIL)
    assert t["macros_g"]["protein"] == round(2.2 * 80)          # sèche : 2,2 g/kg
    maintien = nc.compute_targets({**PROFIL, "objectif_nutrition": "maintien"})
    assert maintien["macros_g"]["protein"] == round(1.8 * 80)
    # Les trois macros refont la cible (à l'arrondi près).
    m = t["macros_g"]
    assert abs(m["protein"] * 4 + m["carbs"] * 4 + m["fat"] * 9 - t["calories_cible"]) < 15
    assert m["fat"] >= 0.7 * 80 - 1


def test_un_gros_gabarit_ne_recoit_pas_une_dose_de_proteines_absurde():
    t = nc.compute_targets({**PROFIL, "poids_kg": 150.0}, 1800)
    assert t["macros_g"]["protein"] <= 0.40 * 1800 / 4 + 1
    assert t["macros_g"]["carbs"] >= 0


def test_la_cible_manuelle_prime_toujours():
    t = nc.compute_targets(PROFIL, 2400)
    assert t["calories_cible"] == 2400 and t["is_custom"]
    assert t["calories_auto"] != 2400


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
def test_la_moyenne_de_la_semaine_ne_change_pas(n):
    t = nc.compute_targets(PROFIL)
    seance = nc.cible_du_jour(t, n, True)
    repos = nc.cible_du_jour(t, n, False)
    assert seance["calories"] > t["calories_cible"] > repos["calories"]
    moyenne = (n * seance["calories"] + (7 - n) * repos["calories"]) / 7
    assert abs(moyenne - t["calories_cible"]) <= 15
    # Seuls les glucides bougent.
    assert seance["macros_g"]["protein"] == repos["macros_g"]["protein"] == t["macros_g"]["protein"]
    assert seance["macros_g"]["fat"] == repos["macros_g"]["fat"] == t["macros_g"]["fat"]


def test_sans_modulation_la_cible_est_la_meme_tous_les_jours():
    t = nc.compute_targets(PROFIL)
    for args in ((4, True, False), (0, True, True), (7, False, True)):
        jour = nc.cible_du_jour(t, *args)
        assert jour["calories"] == t["calories_cible"] and jour["jour"] == ""


def test_seances_par_semaine_planning_puis_carnet():
    lundi = date(2026, 9, 28)
    assert nc.seances_par_semaine({"_planning": {"Lundi": "A", "Jeudi": "B", "Mardi": ""}}, set(), lundi) == 2
    # Sans planning : moyenne des quatre semaines complètes précédentes.
    faits = {(lundi - timedelta(days=d)).isoformat() for d in (1, 3, 5, 8, 10, 12, 15, 17, 19, 22, 24, 26)}
    assert nc.seances_par_semaine({}, faits, lundi) == 3


def test_jour_entrainement_planifie_ou_fait():
    d = date(2026, 9, 30)  # mercredi
    assert nc.est_jour_entrainement({"_planning": {"Mercredi": "Push"}, "Push": []}, set(), d)
    assert nc.est_jour_entrainement({}, {"2026-09-30"}, d)
    assert not nc.est_jour_entrainement({"_planning": {"Lundi": "Push"}}, set(), d)
    hist = [{"Date": "2026-09-30", "Exercice": "Squat", "Reps": 8},
            {"Date": "2026-09-29", "Exercice": "SESSION", "Reps": 0},
            {"Date": "2026-09-28", "Exercice": "CARDIO:Course", "Reps": 30}]
    assert nc.jours_seances(hist) == {"2026-09-30", "2026-09-28"}


# ── Page et profil ───────────────────────────────────────────────

def test_un_jour_de_seance_relève_la_cible_de_la_page(fake_db, logged_in):
    jour = DAYS_FR[today_paris().weekday()]
    _profil(fake_db)
    _prog(fake_db, {jour: "Push"})
    html = logged_in.get("/nutrition").get_data(as_text=True)
    t = nc.compute_targets(PROFIL)
    attendu = nc.cible_du_jour(t, 1, True)
    assert "Jour d'entraînement : +" in html
    assert f"/ {attendu['calories']} kcal" in html
    assert "week-day-seance" in html
    assert "par kilo de poids de corps" in html


def test_la_case_desactive_la_modulation(fake_db, logged_in):
    jour = DAYS_FR[today_paris().weekday()]
    _profil(fake_db)
    _prog(fake_db, {jour: "Push"})
    r = logged_in.post("/nutrition/profile", data={
        "_csrf": CSRF, **{k: str(v) for k, v in PROFIL.items()}, "cycle_form": "1"})
    assert r.status_code == 302
    prog = prog_lu()
    assert prog["_nutrition"]["cycle"] is False
    html = logged_in.get("/nutrition").get_data(as_text=True)
    assert "Jour d'entraînement : +" not in html
    # Recochée : la clé disparaît (comportement par défaut).
    logged_in.post("/nutrition/profile", data={
        "_csrf": CSRF, **{k: str(v) for k, v in PROFIL.items()}, "cycle_form": "1", "cycle": "1"})
    prog = prog_lu()
    assert "cycle" not in prog["_nutrition"]


def test_un_formulaire_sans_la_case_ne_touche_pas_au_reglage(fake_db, logged_in):
    _profil(fake_db)
    _prog(fake_db, nutrition={"cycle": False})
    logged_in.post("/nutrition/profile", data={"_csrf": CSRF, **{k: str(v) for k, v in PROFIL.items()}})
    prog = prog_lu()
    assert prog["_nutrition"]["cycle"] is False


def test_laccueil_montre_la_cible_du_jour_et_les_proteines(fake_db, logged_in):
    jour = DAYS_FR[today_paris().weekday()]
    _profil(fake_db)
    _prog(fake_db, {jour: "Push"})
    fake_db.table("nutrition").insert({"user_id": USER_ID, "date": today_paris().isoformat(),
                                       "meal_type": "dejeuner", "calories": 600, "protein": 45,
                                       "carbs": 60, "fat": 15}).execute()
    html = logged_in.get("/accueil").get_data(as_text=True)
    attendu = nc.cible_du_jour(nc.compute_targets(PROFIL), 1, True)
    assert "CALORIES DU JOUR · SÉANCE" in html
    assert f"/ {attendu['calories']} kcal" in html
    assert f"Protéines : 45 / {attendu['macros_g']['protein']} g" in html


# ── Repas détaillés ──────────────────────────────────────────────

def _ajouter(client, items, **extra):
    data = {"_csrf": CSRF, "date": "2026-10-01", "meal_type": "dejeuner",
            "items": json.dumps(items), **extra}
    return client.post("/nutrition/add-meal", data=data)


def test_le_panier_devient_une_ligne_par_aliment(fake_db, logged_in):
    r = _ajouter(logged_in, [{**BANANE, "grams": 120}, {**RIZ, "grams": 250}],
                 calories="9999")  # un total envoyé par le navigateur est ignoré
    assert r.status_code == 302
    rows = sorted(_repas(fake_db), key=lambda x: x["note"])
    assert [x["note"] for x in rows] == ["Banane", "Riz blanc cuit"]
    banane, riz = rows
    assert banane["grams"] == 120 and banane["calories"] == round(89 * 1.2)
    assert riz["calories"] == round(130 * 2.5) and riz["carbs"] == 70
    assert riz["food"]["k"] == 130 and riz["meal_type"] == "dejeuner"


def test_un_panier_invalide_ne_note_rien(fake_db, logged_in):
    for items in ([{"n": "", "k": 10, "p": 1, "c": 1, "f": 1, "grams": 100}],
                  [{**BANANE, "grams": 0}], [{**BANANE, "k": 5000, "grams": 100}], "pas une liste"):
        r = _ajouter(logged_in, items)
        assert r.status_code == 400
    r = logged_in.post("/nutrition/add-meal", data={"_csrf": CSRF, "items": "{cassé"})
    assert r.status_code == 400
    assert _repas(fake_db) == []


def test_sans_la_migration_v40_le_repas_est_quand_meme_note(fake_db, logged_in, monkeypatch):
    """Base sans `grams` / `food` : PostgREST refuse l'écriture (PGRST204).
    Elle est retentée sans ces colonnes — le repas est noté."""
    import conftest

    vrai = conftest.FakeQuery.execute

    def execute(self):
        if self._table == "nutrition" and self._op == "insert":
            rows = self._payload if isinstance(self._payload, list) else [self._payload]
            if any("grams" in r for r in rows):
                raise RuntimeError("{'code': 'PGRST204', 'message': \"Could not find the 'food' "
                                   "column of 'nutrition' in the schema cache\"}")
        return vrai(self)
    monkeypatch.setattr(conftest.FakeQuery, "execute", execute)
    r = _ajouter(logged_in, [{**BANANE, "grams": 120}])
    assert r.status_code == 302
    rows = _repas(fake_db)
    assert len(rows) == 1 and rows[0]["calories"] == 107 and "grams" not in rows[0]


def test_une_autre_panne_decriture_reste_une_erreur(fake_db, logged_in, monkeypatch):
    import conftest

    def execute(self):
        raise RuntimeError("connection reset")
    monkeypatch.setattr(conftest.FakeQuery, "execute", execute)
    r = _ajouter(logged_in, [{**BANANE, "grams": 120}])
    assert r.status_code == 503


def test_correction_de_quantite_recalcule_les_macros(fake_db, logged_in):
    _ajouter(logged_in, [{**RIZ, "grams": 250}])
    row = _repas(fake_db)[0]
    r = logged_in.post("/nutrition/edit-meal", data={"_csrf": CSRF, "id": row["id"],
                                                     "grams": "150", "date": "2026-10-01"})
    assert r.status_code == 302
    row = _repas(fake_db)[0]
    assert row["grams"] == 150 and row["calories"] == 195 and row["carbs"] == 42


def test_un_repas_en_bloc_ne_se_corrige_pas_en_grammes(fake_db, logged_in):
    logged_in.post("/nutrition/add-meal", data={"_csrf": CSRF, "date": "2026-10-01",
                                                "meal_type": "diner", "calories": "700"})
    row = _repas(fake_db)[0]
    r = logged_in.post("/nutrition/edit-meal", data={"_csrf": CSRF, "id": row["id"], "grams": "100"})
    assert r.status_code == 400
    assert _repas(fake_db)[0]["calories"] == 700


def test_on_ne_corrige_pas_le_repas_dun_autre(fake_db, logged_in):
    fake_db.table("nutrition").insert({"user_id": "autre", "date": "2026-10-01", "meal_type": "diner",
                                       "calories": 100, "protein": 0, "carbs": 0, "fat": 0,
                                       "grams": 100, "food": RIZ}).execute()
    autre = fake_db.tables["nutrition"][0]
    r = logged_in.post("/nutrition/edit-meal", data={"_csrf": CSRF, "id": autre["id"], "grams": "300"})
    assert r.status_code == 400
    assert autre["grams"] == 100


def test_ancienne_ligne_avec_quantite_mais_sans_valeurs_pour_100_g():
    champs = na.recalculer({"calories": 300, "protein": 10, "carbs": 40, "fat": 10, "grams": 200}, 100)
    assert champs == {"calories": 150, "protein": 5, "carbs": 20, "fat": 5, "grams": 100}


def test_reprendre_hier_recopie_le_seul_creneau_demande(fake_db, logged_in):
    _ajouter(logged_in, [{**BANANE, "grams": 120}], date="2026-09-30", meal_type="petit_dej")
    _ajouter(logged_in, [{**RIZ, "grams": 200}], date="2026-09-30", meal_type="diner")
    html = logged_in.get("/nutrition?date=2026-10-01").get_data(as_text=True)
    assert "Reprendre le petit-déj de la veille" in html
    assert "Reprendre le dîner de la veille" in html
    r = logged_in.post("/nutrition/copier", data={"_csrf": CSRF, "date": "2026-10-01",
                                                  "source": "2026-09-30", "meal_type": "petit_dej"})
    assert r.status_code == 302
    copies = [x for x in _repas(fake_db) if x["date"] == "2026-10-01"]
    assert len(copies) == 1 and copies[0]["note"] == "Banane" and copies[0]["grams"] == 120
    html = logged_in.get("/nutrition?date=2026-10-01").get_data(as_text=True)
    assert "Reprendre le petit-déj de la veille" not in html


def test_la_page_affiche_la_quantite_et_le_bouton_de_correction(fake_db, logged_in):
    _ajouter(logged_in, [{**RIZ, "grams": 250}])
    html = logged_in.get("/nutrition?date=2026-10-01").get_data(as_text=True)
    assert "· 250 g" in html and 'action="/nutrition/edit-meal"' in html


def test_une_date_invalide_retombe_sur_aujourdhui(fake_db, logged_in):
    r = logged_in.get("/nutrition?date=n'importe-quoi")
    assert r.status_code == 200


# ── Aliments récents ─────────────────────────────────────────────

def test_les_aliments_habituels_arrivent_en_tete(fake_db, logged_in):
    hier = (today_paris() - timedelta(days=1)).isoformat()
    for _ in range(3):
        _ajouter(logged_in, [{**RIZ, "grams": 180}], date=hier)
    _ajouter(logged_in, [{**BANANE, "grams": 120}], date=hier)
    html = logged_in.get("/nutrition").get_data(as_text=True)
    recents = json.loads(html.split("var RECENTS = ", 1)[1].split(";\n", 1)[0])
    assert [f["n"] for f in recents] == ["Riz blanc cuit", "Banane"]
    assert recents[0]["u"][0] == ["comme la dernière fois", 180]
    assert "Tes aliments habituels" in html


def test_recents_sans_colonnes_v40_la_page_marche(fake_db, logged_in, monkeypatch):
    import routes.nutrition as rn

    def boom(*a, **k):
        raise RuntimeError("column nutrition.food does not exist")
    monkeypatch.setattr(rn, "list_nutrition_recents", boom)
    html = logged_in.get("/nutrition").get_data(as_text=True)
    assert "var RECENTS = []" in html


# ── Recherche Open Food Facts ────────────────────────────────────

def _produits(*noms):
    return {"products": [{"code": f"30000000{i:05d}", "product_name_fr": n, "brands": "Marque",
                          "nutriments": {"energy-kcal_100g": 60, "proteins_100g": 10,
                                         "carbohydrates_100g": 4, "fat_100g": 0.2}}
                         for i, n in enumerate(noms)]}


@pytest.fixture()
def off_neuf():
    off._cache.clear()
    partage.reinitialiser()
    yield
    off._cache.clear()
    partage.reinitialiser()


def test_la_recherche_renvoie_des_aliments_prets_a_ajouter(fake_db, logged_in, monkeypatch, off_neuf):
    urls = []
    monkeypatch.setattr(off, "_http_get", lambda url: urls.append(url) or _produits("Skyr nature", "Skyr nature", "Skyr vanille"))
    d = json.loads(logged_in.get("/nutrition/recherche?q=Skyr").data)
    assert d["ok"] and [f["n"] for f in d["foods"]] == ["Skyr nature", "Skyr vanille"]   # doublon retiré
    assert d["foods"][0]["g"] == "Marque" and d["foods"][0]["code"]
    assert "search_terms=skyr" in urls[0]
    # Même recherche : servie par le cache.
    logged_in.get("/nutrition/recherche?q=skyr ")
    assert len(urls) == 1


def test_la_recherche_reste_sous_la_limite_open_food_facts(fake_db, logged_in, monkeypatch, off_neuf):
    monkeypatch.setattr(off, "_http_get", lambda url: _produits("X"))
    codes = [logged_in.get(f"/nutrition/recherche?q=produit{i}").status_code
             for i in range(off.SEARCH_MAX_PAR_MINUTE + 1)]
    assert codes[:-1] == [200] * off.SEARCH_MAX_PAR_MINUTE and codes[-1] == 503


def test_la_recherche_sans_reseau_le_dit(fake_db, logged_in, monkeypatch, off_neuf):
    monkeypatch.setattr(off, "_http_get", lambda url: None)
    r = logged_in.get("/nutrition/recherche?q=skyr")
    assert r.status_code == 503 and "Réessaie" in json.loads(r.data)["error"]


def test_la_recherche_demande_trois_lettres_et_un_compte_pro(fake_db, client, logged_in, off_neuf):
    assert logged_in.get("/nutrition/recherche?q=sk").status_code == 400
    with client.session_transaction() as s:
        s.update(is_vip=False, is_vip_full=False, is_vip_ts=time.time())
    assert client.get("/nutrition/recherche?q=skyr").status_code == 403


def test_la_page_propose_la_recherche_et_envoie_le_panier_detaille(fake_db, logged_in):
    html = logged_in.get("/nutrition").get_data(as_text=True)
    assert "/static/js/nutrition.js" in html
    assert 'name="items"' in html
    js = open("static/js/nutrition.js", encoding="utf-8").read()
    assert "/nutrition/recherche?q=" in js and "basketItems" in js


def test_la_base_compte_plus_de_400_aliments():
    from core.foods_data import FOODS
    assert len(FOODS) >= 400
