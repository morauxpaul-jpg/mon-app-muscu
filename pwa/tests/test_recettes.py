"""Mes recettes et aliments (v49) : saisis une fois, ajoutés ensuite comme
n'importe quel aliment.

Relevé du 12/10 : « Pâtes carbonara » notées trois fois en septembre, à
1 150, 897 puis 880 kcal — la même assiette, ressaisie de mémoire.
"""
import json

import pytest

from conftest import CSRF, USER_ID
from core import nutrition_aliments as na
from core import nutrition_recettes as nr
from core.foods_data import FOODS

PROFIL = {"poids_kg": 91.4, "taille_cm": 186.0, "age": 30, "sexe": "H",
          "activite": "actif", "objectif_nutrition": "seche"}


def _aliment(nom):
    return next(dict(f) for f in FOODS if f["n"] == nom)


def _carbonara(grams=(500, 200, 200, 60, 100)):
    noms = ("Pâtes crues", "Lardons cuits", "Œuf entier", "Parmesan", "Crème fraîche 30 %")
    return [{**_aliment(n), "grams": g} for n, g in zip(noms, grams)]


@pytest.fixture()
def compte(fake_db, logged_in):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip", **PROFIL}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {}, "_upsell_seen": True}}).execute()
    return fake_db


def _post(client, url, **data):
    return client.post(url, data={"_csrf": CSRF, **data})


def _lignes(fake):
    return [r for r in fake.tables.get("aliments_perso", []) if r["user_id"] == USER_ID]


# ── Calculs ──────────────────────────────────────────────────────

def test_une_part_vaut_la_recette_divisee_par_le_nombre_de_parts():
    ing = _carbonara()
    total = sum(i["k"] * i["grams"] / 100 for i in ing)
    food, detail, err = nr.recette("Pâtes carbonara", ing, 4)
    assert err == ""
    part = nr.par_part(food)
    assert part["libelle"] == "1 part" and part["grams"] == 265          # 1 060 g crus / 4
    assert abs(part["kcal"] - total / 4) <= total / 4 * 0.01
    assert detail["parts"] == 4 and detail["poids_cru"] == 1060 and detail["poids_cuit"] is None
    assert [u[0] for u in food["u"]] == ["1 part"]                        # pas de « 100 g » sans poids cuit


def test_le_poids_cuit_change_les_100_g_pas_la_part():
    ing = _carbonara()
    cru, _, _ = nr.recette("Pâtes carbonara", ing, 4)
    cuit, detail, err = nr.recette("Pâtes carbonara", ing, 4, "1650")
    assert err == "" and detail["poids_cuit"] == 1650
    assert cuit["k"] < cru["k"]                                            # l'eau de cuisson dilue
    assert abs(nr.par_part(cuit)["kcal"] - nr.par_part(cru)["kcal"]) <= 3
    assert cuit["u"] == [["1 part", 413], ["100 g", 100]]          # 412,5 g, arrondi comme l'écran


def test_le_navigateur_ne_fixe_pas_les_valeurs():
    """Les totaux sont recalculés à partir des ingrédients : un total envoyé
    à côté est ignoré, une valeur hors bornes écarte l'ingrédient."""
    ing = _carbonara() + [{"n": "Triche", "k": 99999, "p": 1, "c": 1, "f": 1, "grams": 100}]
    food, detail, _ = nr.recette("Pâtes carbonara", ing, 4)
    assert [i["n"] for i in detail["ingredients"]][-1] == "Crème fraîche 30 %"
    assert food == nr.recette("Pâtes carbonara", _carbonara(), 4)[0]


@pytest.mark.parametrize("parts, cuit, attendu", [
    ("0", "", "Nombre de parts"),
    ("2.5", "", "Nombre de parts"),
    ("51", "", "Nombre de parts"),
    ("4", "300", "poids cuit"),            # 3 300 kcal dans 300 g : impossible
    ("4", "abc", "Poids cuit"),
])
def test_une_recette_invraisemblable_est_refusee_avec_une_raison(parts, cuit, attendu):
    food, _, err = nr.recette("Pâtes carbonara", _carbonara(), parts, cuit)
    assert food is None and attendu.lower() in err.lower()


def test_une_recette_sans_nom_ou_sans_ingredient_est_refusee():
    assert nr.recette("  ", _carbonara(), 4)[2].startswith("Donne un nom")
    assert nr.recette("Vide", [], 4)[2].startswith("Ajoute au moins")
    assert nr.recette("Vide", [{**_aliment("Parmesan"), "grams": 0}], 4)[2].startswith("Ajoute")


def test_un_aliment_se_saisit_comme_sur_l_etiquette():
    barre, err = nr.aliment_saisi("Barre choco", "45", "190", "15", "18", "6", "1 barre")
    assert err == ""
    assert barre["k"] == pytest.approx(422.2) and barre["p"] == pytest.approx(33.3)
    assert barre["u"] == [["1 barre", 45], ["100 g", 100]]
    assert nr.par_part(barre)["kcal"] == 190


def test_sans_calories_elles_se_deduisent_des_macros():
    huile, err = nr.aliment_saisi("Huile d'olive", "", "", "0", "0", "100")
    assert err == "" and huile["k"] == 900 and huile["u"] == [["100 g", 100]]
    virgule, _ = nr.aliment_saisi("Skyr", "100", "", "10,5", "4", "0,2")
    assert virgule["p"] == 10.5 and virgule["k"] == pytest.approx(59.8)


@pytest.mark.parametrize("args, attendu", [
    (("Faux", "10", "200", "5", "5", "5"), "950 kcal"),
    (("Faux", "100", "300", "60", "50", "0"), "plus de 100 g"),
    (("Faux", "0", "100", "1", "1", "1"), "combien de grammes"),
    (("Faux", "100", "-5", "1", "1", "1"), "Calories"),
    (("", "100", "100", "1", "1", "1"), "Donne un nom"),
])
def test_une_etiquette_impossible_est_refusee(args, attendu):
    food, err = nr.aliment_saisi(*args)
    assert food is None and attendu in err


def test_le_recent_d_une_recette_prend_ses_valeurs_actuelles():
    """Corrigée après coup, la recette ne doit pas revenir avec ses anciennes
    valeurs via « Tes aliments habituels » ; la quantité de la dernière fois
    reste proposée."""
    ancien, _, _ = nr.recette("Pâtes carbonara", _carbonara(), 4)
    nouveau, _, _ = nr.recette("Pâtes carbonara", _carbonara((400, 150, 200, 40, 50)), 4)
    recents = na.recents([{"food": ancien, "grams": 265}])
    perso = nr.pour_la_recherche([{"id": 7, "nom": "Pâtes carbonara", "food": nouveau,
                                   "recette": {"parts": 4}}])
    frais = nr.rafraichir_recents(recents, perso)[0]
    assert frais["k"] == nouveau["k"] and frais["perso"] == 7 and frais["g"] == "Ma recette"
    assert frais["u"][0] == ["comme la dernière fois", 265]


# ── Page et routes ───────────────────────────────────────────────

def test_creer_une_recette_puis_la_retrouver_dans_la_recherche_du_repas(compte, client):
    r = _post(client, "/nutrition/aliments/enregistrer", type="recette", nom="Pâtes carbonara",
              parts="4", poids_cuit="1650", ingredients=json.dumps(_carbonara()))
    assert r.status_code == 302 and "enregistre=" in r.headers["Location"]
    [ligne] = _lignes(compte)
    assert ligne["nom"] == "Pâtes carbonara" and ligne["recette"]["parts"] == 4
    assert len(ligne["recette"]["ingredients"]) == 5

    page = client.get(r.headers["Location"]).get_data(as_text=True)
    assert "C&#39;est enregistré" in page and "Pâtes carbonara" in page and "4 parts" in page

    nutrition = client.get("/nutrition").get_data(as_text=True)
    perso = json.loads(nutrition.split("var PERSO = ", 1)[1].split(";\n", 1)[0])
    assert perso[0]["n"] == "Pâtes carbonara" and perso[0]["g"] == "Ma recette"
    assert perso[0]["u"][0] == ["1 part", 413]


def test_une_part_de_recette_se_note_comme_un_aliment(compte, client):
    food, _, _ = nr.recette("Pâtes carbonara", _carbonara(), 4, "1650")
    r = _post(client, "/nutrition/add-meal", date="2026-10-12", meal_type="dejeuner",
              items=json.dumps([{**food, "grams": 413}]))
    assert r.status_code == 302
    [repas] = compte.tables["nutrition"]
    assert repas["note"] == "Pâtes carbonara" and repas["grams"] == 413
    assert abs(repas["calories"] - nr.par_part(food)["kcal"]) <= 1


def test_modifier_une_recette_garde_le_meme_identifiant(compte, client):
    _post(client, "/nutrition/aliments/enregistrer", type="recette", nom="Pâtes carbonara",
          parts="4", ingredients=json.dumps(_carbonara()))
    [ligne] = _lignes(compte)
    page = client.get(f"/nutrition/aliments?modifier={ligne['id']}").get_data(as_text=True)
    assert "Modifier la recette" in page and "RECETTE_DONNEES" in page
    donnees = json.loads(page.split("var RECETTE_DONNEES = ", 1)[1].split(";\n", 1)[0])
    assert donnees["edition"]["parts"] == 4 and len(donnees["edition"]["ingredients"]) == 5
    assert all(p["perso"] != ligne["id"] for p in donnees["perso"])   # pas dans ses propres ingrédients

    _post(client, "/nutrition/aliments/enregistrer", type="recette", id=str(ligne["id"]),
          nom="Pâtes carbonara", parts="5", ingredients=json.dumps(_carbonara()))
    [apres] = _lignes(compte)
    assert apres["id"] == ligne["id"] and apres["recette"]["parts"] == 5


def test_une_saisie_refusee_rouvre_l_editeur_sans_rien_perdre(compte, client):
    r = _post(client, "/nutrition/aliments/enregistrer", type="recette", nom="Pâtes carbonara",
              parts="4", poids_cuit="300", ingredients=json.dumps(_carbonara()))
    assert r.status_code == 400
    page = r.get_data(as_text=True)
    assert "pèse le plat entier" in page
    donnees = json.loads(page.split("var RECETTE_DONNEES = ", 1)[1].split(";\n", 1)[0])
    assert donnees["edition"]["nom"] == "Pâtes carbonara"
    assert len(donnees["edition"]["ingredients"]) == 5 and donnees["edition"]["poids_cuit"] == "300"
    assert _lignes(compte) == []


def test_deux_aliments_ne_portent_pas_le_meme_nom(compte, client):
    _post(client, "/nutrition/aliments/enregistrer", type="aliment", nom="Barre choco",
          pour_g="45", kcal="190", p="15", c="18", f="6", portion="1 barre")
    r = _post(client, "/nutrition/aliments/enregistrer", type="aliment", nom="barre  CHOCO",
              pour_g="100", kcal="400", p="30", c="40", f="12")
    assert r.status_code == 400 and "Tu as déjà" in r.get_data(as_text=True)
    assert len(_lignes(compte)) == 1


def test_modifier_un_aliment_reprend_ses_valeurs_de_portion(compte, client):
    _post(client, "/nutrition/aliments/enregistrer", type="aliment", nom="Barre choco",
          pour_g="45", kcal="190", p="15", c="18", f="6", portion="1 barre")
    [ligne] = _lignes(compte)
    page = client.get(f"/nutrition/aliments?modifier={ligne['id']}").get_data(as_text=True)
    assert 'name="pour_g" class="field" min="1" max="3000" step="any" value="45"' in page
    assert 'value="190"' in page and 'value="1 barre"' in page
    assert "RECETTE_DONNEES" not in page                     # un aliment n'a pas besoin de la base


def test_on_ne_modifie_ni_ne_supprime_l_aliment_d_un_autre(compte, client):
    compte.table("aliments_perso").insert({"user_id": "autre", "nom": "Secret", "food": {
        "n": "Secret", "k": 100, "p": 1, "c": 1, "f": 1, "u": [["100 g", 100]]}}).execute()
    autre = compte.tables["aliments_perso"][0]["id"]
    _post(client, "/nutrition/aliments/enregistrer", type="aliment", id=str(autre),
          nom="Volé", pour_g="100", kcal="1", p="0", c="0", f="0")
    _post(client, "/nutrition/aliments/supprimer", id=str(autre))
    assert [r["nom"] for r in compte.tables["aliments_perso"]] == ["Secret"]
    assert "Secret" not in client.get(f"/nutrition/aliments?modifier={autre}").get_data(as_text=True)


def test_supprimer_ne_touche_pas_aux_repas_deja_notes(compte, client):
    _post(client, "/nutrition/aliments/enregistrer", type="aliment", nom="Barre choco",
          pour_g="45", kcal="190", p="15", c="18", f="6", portion="1 barre")
    [ligne] = _lignes(compte)
    _post(client, "/nutrition/add-meal", date="2026-10-12", meal_type="collation",
          items=json.dumps([{**ligne["food"], "grams": 45}]))
    r = _post(client, "/nutrition/aliments/supprimer", id=str(ligne["id"]))
    assert r.status_code == 302 and _lignes(compte) == []
    assert compte.tables["nutrition"][0]["calories"] == 190
    assert "les repas déjà notés gardent" in client.get(r.headers["Location"]).get_data(as_text=True).lower()


def test_un_compte_gratuit_voit_le_mur_pro(fake_db, client):
    with client.session_transaction() as s:
        s.update({"user_id": USER_ID, "onboarded": True, "is_vip": False, "_csrf": CSRF})
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    assert "Mes recettes et aliments" not in client.get("/nutrition/aliments").get_data(as_text=True)
    _post(client, "/nutrition/aliments/enregistrer", type="aliment", nom="X", pour_g="100",
          kcal="10", p="1", c="1", f="0")
    assert fake_db.tables.get("aliments_perso", []) == []


@pytest.fixture()
def sans_table(monkeypatch):
    from conftest import FakeQuery
    vraie = FakeQuery.execute

    def refuse(self):
        if self._table == "aliments_perso":
            raise Exception("{'code': 'PGRST205', 'message': \"Could not find the table "
                            "'public.aliments_perso' in the schema cache\"}")
        return vraie(self)
    monkeypatch.setattr(FakeQuery, "execute", refuse)


def test_sans_la_migration_la_nutrition_marche_et_l_admin_le_sait(compte, client, sans_table):
    from core import schema
    assert client.get("/nutrition").status_code == 200
    page = client.get("/nutrition/aliments")
    assert page.status_code == 200 and "arrivent bientôt" in page.get_data(as_text=True)
    r = _post(client, "/nutrition/aliments/enregistrer", type="aliment", nom="Barre",
              pour_g="100", kcal="400", p="30", c="40", f="12")
    assert r.status_code == 503
    assert "aliments_perso" in schema.etat()["absentes"]


def test_l_export_et_la_suppression_du_compte_couvrent_mes_aliments(compte, client):
    _post(client, "/nutrition/aliments/enregistrer", type="aliment", nom="Barre choco",
          pour_g="45", kcal="190", p="15", c="18", f="6")
    export = json.loads(client.get("/gestion/export").get_data(as_text=True))
    assert [a["nom"] for a in export["aliments_perso"]] == ["Barre choco"]
    from core import db
    db.delete_user_account(USER_ID)
    assert _lignes(compte) == []
