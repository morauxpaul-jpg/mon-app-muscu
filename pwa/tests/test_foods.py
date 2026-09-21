"""Base d'aliments (core/foods_data.py) : intégrité + exposition dans la page Nutrition."""
import json
from core.foods_data import FOODS, FOODS_RAW


def test_table_coherente():
    names = [f["n"] for f in FOODS]
    assert len(names) == len(set(names)), "noms en double"
    assert len(FOODS) >= 250
    for f in FOODS:
        assert f["g"], f["n"]                       # catégorie posée
        assert f["k"] >= 0 and f["p"] >= 0 and f["c"] >= 0 and f["f"] >= 0
        assert f["u"] and all(g > 0 for _, g in f["u"]), f["n"]
        assert any(g == 100 for _, g in f["u"]), f["n"]   # portion 100 g toujours dispo
        # Macros × kcal/g ≈ kcal (hors alcool, 7 kcal/g non modélisé)
        est = f["p"] * 4 + f["c"] * 4 + f["f"] * 9
        if f["g"] != "Boissons":
            assert abs(est - f["k"]) <= max(60, f["k"] * 0.35), (f["n"], est, f["k"])


def test_categories_plats_en_second():
    assert next(f for f in FOODS if f["n"] == "Banane")["r"] == 0
    assert next(f for f in FOODS if f["n"] == "Pizza margherita")["r"] == 1


def test_page_nutrition_embarque_la_base(fake_db, logged_in):
    r = logged_in.get("/nutrition")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "var FOODS = " in html
    assert json.dumps("Banane") in html
    assert 'mode === \'aliments\'' in html
