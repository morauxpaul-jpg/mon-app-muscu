"""Scan de code-barres — Nutrition.

Ce qui compte ici : les macros affichées à l'utilisateur doivent être celles
de l'étiquette. Une erreur d'unité (kJ pris pour des kcal) fausse la journée
d'un facteur 4, sans que rien ne le signale à l'écran.
"""
import json

from conftest import USER_ID
from core import openfoodfacts as off


def _reset_cache():
    off._cache.clear()


def _payload(**nutriments):
    base = {"energy-kcal_100g": 57, "proteins_100g": 10,
            "carbohydrates_100g": 4, "fat_100g": 0.2}
    base.update(nutriments)
    return {"product": {"product_name_fr": "Skyr nature", "brands": "Danone",
                        "serving_size": "150 g", "nutriments": base}}


# ── Validation du code ───────────────────────────────────────────


def test_le_code_est_nettoye_des_espaces_et_tirets():
    assert off.clean_code(" 3 033 710-065967 ") == "3033710065967"


def test_un_code_trop_court_est_refuse():
    assert off.clean_code("1234567") == ""
    assert off.clean_code("") == ""
    assert off.clean_code(None) == ""


def test_un_code_trop_long_est_refuse():
    assert off.clean_code("1" * 15) == ""


def test_un_code_alphabetique_est_refuse():
    """Le code sert à construire une URL : pas de chemin traversant."""
    assert off.clean_code("../../etc/passwd") == ""


# ── Lecture des valeurs nutritionnelles ──────────────────────────


def test_les_macros_sont_reprises_pour_100_g():
    food = off.normalize(_payload()["product"], "3033710065967")
    assert food["n"] == "Skyr nature"
    assert (food["k"], food["p"], food["c"], food["f"]) == (57, 10, 4, 0.2)


def test_les_kilojoules_sont_convertis_en_calories():
    """L'étiquette européenne affiche les deux ; certaines fiches n'ont que les kJ."""
    p = _payload()["product"]
    p["nutriments"] = {"energy-kj_100g": 1000, "proteins_100g": 0,
                       "carbohydrates_100g": 0, "fat_100g": 0}
    assert off.normalize(p, "1")["k"] == 239.0


def test_une_energie_sans_unite_au_dela_du_plausible_est_lue_en_kilojoules():
    """900 kcal/100 g est le plafond physique (huile pure) : au-delà, c'est des kJ."""
    p = _payload()["product"]
    p["nutriments"] = {"energy_100g": 2000}
    assert off.normalize(p, "1")["k"] == 478.0

    p["nutriments"] = {"energy_100g": 250}
    assert off.normalize(p, "1")["k"] == 250


def test_un_produit_sans_energie_est_rejete():
    """Mieux vaut « produit inconnu » qu'un aliment à 0 kcal ajouté en silence."""
    p = _payload()["product"]
    p["nutriments"] = {"proteins_100g": 10}
    assert off.normalize(p, "1") is None


def test_un_produit_sans_nom_est_rejete():
    p = _payload()["product"]
    p["product_name_fr"] = ""
    p["product_name"] = ""
    assert off.normalize(p, "1") is None


def test_les_macros_manquantes_valent_zero():
    p = _payload()["product"]
    p["nutriments"] = {"energy-kcal_100g": 120}
    food = off.normalize(p, "1")
    assert (food["p"], food["c"], food["f"]) == (0, 0, 0)


# ── Portions ─────────────────────────────────────────────────────


def test_la_portion_declaree_devient_une_unite_proposee():
    food = off.normalize(_payload()["product"], "1")
    assert food["u"][0] == ["1 portion", 150]
    assert ["100 g", 100] in food["u"]


def test_sans_portion_declaree_seul_le_100_g_est_propose():
    p = _payload()["product"]
    p.pop("serving_size")
    assert off.normalize(p, "1")["u"] == [["100 g", 100]]


def test_la_portion_est_lue_dans_un_texte_libre():
    assert off.serving_grams({"serving_size": "2 tranches (50g)"}) == 50
    assert off.serving_grams({"serving_size": "1 verre 25 cl"}) == 250
    assert off.serving_grams({"serving_size": "330 ml"}) == 330


def test_la_quantite_numerique_prime_sur_le_texte():
    assert off.serving_grams({"serving_quantity": 30, "serving_size": "1 barre"}) == 30


def test_une_portion_absurde_est_ignoree():
    assert off.serving_grams({"serving_size": "1 portion"}) is None
    assert off.serving_grams({"serving_quantity": 99999}) is None


# ── Cache ────────────────────────────────────────────────────────


def test_le_meme_code_nappelle_le_reseau_quune_fois(monkeypatch):
    _reset_cache()
    calls = []
    monkeypatch.setattr(off, "_http_get", lambda url: calls.append(url) or _payload())
    assert off.lookup("3033710065967")["n"] == "Skyr nature"
    assert off.lookup("3033710065967")["n"] == "Skyr nature"
    assert len(calls) == 1


def test_un_code_inconnu_est_aussi_mis_en_cache(monkeypatch):
    """Rescanner trois fois le même paquet non référencé = un seul appel."""
    _reset_cache()
    calls = []
    monkeypatch.setattr(off, "_http_get",
                        lambda url: calls.append(url) or {"status": 0})
    assert off.lookup("3033710065967") is None
    assert off.lookup("3033710065967") is None
    assert len(calls) == 1


def test_une_panne_reseau_nest_pas_mise_en_cache(monkeypatch):
    """Sinon un code scanné pendant une coupure resterait introuvable 12 h."""
    _reset_cache()
    calls = []

    def _down(url):
        calls.append(url)
        return None

    monkeypatch.setattr(off, "_http_get", _down)
    assert off.lookup("3033710065967") is None
    assert off.lookup("3033710065967") is None
    assert len(calls) == 2


def test_lappel_reseau_demande_les_champs_utiles(monkeypatch):
    _reset_cache()
    seen = []
    monkeypatch.setattr(off, "_http_get", lambda url: seen.append(url) or _payload())
    off.lookup("3033710065967")
    assert seen[0].startswith("https://world.openfoodfacts.org/api/v2/product/3033710065967.json")
    assert "nutriments" in seen[0]


# ── Route ────────────────────────────────────────────────────────


def test_la_route_renvoie_laliment_pret_a_ajouter(fake_db, logged_in, monkeypatch):
    _reset_cache()
    monkeypatch.setattr(off, "_http_get", lambda url: _payload())
    d = json.loads(logged_in.get("/nutrition/barcode/3033710065967").data)
    assert d["ok"] is True
    # Même forme qu'un aliment de core/foods_data.py : le panier ne fait pas
    # de cas particulier pour un produit scanné.
    assert set(("n", "k", "p", "c", "f", "u")) <= set(d["food"])
    assert d["food"]["brand"] == "Danone"


def test_la_route_refuse_un_code_invalide(fake_db, logged_in):
    r = logged_in.get("/nutrition/barcode/abc")
    assert r.status_code == 400
    assert json.loads(r.data)["ok"] is False


def test_la_route_repond_proprement_sur_un_produit_inconnu(fake_db, logged_in, monkeypatch):
    _reset_cache()
    monkeypatch.setattr(off, "_http_get", lambda url: {"status": 0})
    r = logged_in.get("/nutrition/barcode/3033710065967")
    assert r.status_code == 200
    d = json.loads(r.data)
    assert d["ok"] is False and "Open Food Facts" in d["error"]


def test_la_route_est_reservee_aux_membres_pro(fake_db, client, monkeypatch):
    import time
    _reset_cache()
    monkeypatch.setattr(off, "_http_get", lambda url: _payload())
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time())
    r = client.get("/nutrition/barcode/3033710065967")
    assert r.status_code == 403


def test_la_page_nutrition_charge_le_scanner(fake_db, logged_in):
    html = logged_in.get("/nutrition").get_data(as_text=True)
    assert "/static/js/barcode.js" in html
    assert ">Scanner</button>" in html


def test_la_camera_est_autorisee_pour_notre_propre_page(fake_db, logged_in):
    """Permissions-Policy camera=() bloquerait getUserMedia avant tout code JS."""
    policy = logged_in.get("/nutrition").headers.get("Permissions-Policy", "")
    assert "camera=(self)" in policy
    assert "microphone=()" in policy
