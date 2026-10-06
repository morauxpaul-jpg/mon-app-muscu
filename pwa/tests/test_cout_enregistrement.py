"""Ce que coûte un « Série faite ».

Depuis l'audit du 30/09 (C1), chaque série validée est enregistrée : c'est
la requête la plus fréquente de l'app, faite entre deux séries, souvent en
4G faible. L'audit (I15, mesure Q1) comptait 11 requêtes Supabase par
enregistrement, dont 8 pages d'historique : l'historique entier était relu
AVANT l'écriture (détection de record), puis relu APRÈS, le cache ayant été
vidé entre les deux. Le coût grandissait avec l'ancienneté du compte.

Mesuré avec un an d'entraînement en base (3 744 séries).
"""
import datetime as dt
import json

import pytest

from conftest import USER_ID, CSRF

JSON_HEADERS = {"Accept": "application/json", "X-CSRFToken": CSRF}
AUJOURDHUI = dt.date(2026, 9, 28)


@pytest.fixture()
def un_an(fake_db):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Full": [{"name": f"Exo {i}", "sets": 4, "muscle": "Pecs", "reps": "8-12"}
                 for i in range(6)],
        "_planning": {"Lundi": "Full", "Mercredi": "Full", "Vendredi": "Full"},
        "_settings": {},
    }}).execute()
    lignes = []
    for s in range(52 * 3):
        jour = (AUJOURDHUI - dt.timedelta(days=2 + s * 7 // 3)).isoformat()
        for i in range(6):
            for n in range(1, 5):
                lignes.append({"user_id": USER_ID, "date": jour, "semaine": 1,
                               "seance": "Full", "exercice": f"Exo {i}", "serie": n,
                               "reps": 10, "poids": 60.0, "remarque": "", "muscle": "Pecs"})
    fake_db.tables["history"] = lignes
    for k, r in enumerate(lignes):
        r["id"] = k + 1
    fake_db._id = len(lignes) + 1
    return fake_db


@pytest.fixture()
def compteur(monkeypatch):
    """Compte les requêtes Supabase exécutées, par table et par opération."""
    import conftest
    vraie = conftest.FakeQuery.execute
    faites = []

    def espion(self):
        faites.append((self._table, self._op or "select"))
        return vraie(self)

    monkeypatch.setattr(conftest.FakeQuery, "execute", espion)
    return faites


def _serie_faite(client, n):
    return client.post("/seance/save-exo", data={
        "_csrf": CSRF, "seance_name": "Full", "exo_base": "Exo 0",
        "variant": "Standard", "muscle": "Pecs", "date": AUJOURDHUI.isoformat(),
        "mode": "prefaite", "name": "Full", "partiel": "1",
        "sets_json": json.dumps([{"reps": 10, "poids": 62.5}] * n),
    }, headers=JSON_HEADERS)


def test_une_serie_faite_ne_relit_pas_lhistorique_apres_lecriture(un_an, logged_in, compteur):
    """Plafonds mesurés, pas choisis : 11 puis 8 requêtes avant, 7 puis 3
    maintenant. Les 4 lectures restantes au premier envoi sont la lecture
    de l'historique quand le cache est froid (détection de record)."""
    import core.db_base as db_base
    db_base._data_cache.clear()
    assert _serie_faite(logged_in, 1).status_code == 200
    # +1 depuis la v47 : l'état du compte (`etat_compte`) se lit avec le
    # programme, une fois par cache froid.
    assert len(compteur) <= 8, compteur
    assert compteur.count(("history", "select")) <= 5, compteur
    compteur.clear()
    assert _serie_faite(logged_in, 2).status_code == 200
    assert len(compteur) <= 3, f"cache chaud : écrire, pas relire — {compteur}"


def test_le_cache_corrige_est_identique_a_une_vraie_relecture(un_an, logged_in):
    """Corriger le cache au lieu de le jeter n'a de sens que s'il dit
    exactement ce que dirait la base."""
    import core.db as db
    import core.db_base as db_base
    db_base._data_cache.clear()
    _serie_faite(logged_in, 1)
    _serie_faite(logged_in, 3)
    en_cache = db.get_hist(USER_ID)
    db_base._data_cache.clear()
    relu = db.get_hist(USER_ID)
    cle = lambda r: (r["Date"], r["Séance"], r["Exercice"], r["Série"])
    assert sorted(en_cache, key=cle) == sorted(relu, key=cle)


def test_la_reponse_reste_juste(un_an, logged_in):
    """Volume et séries de la séance : comptés avec ce qu'on vient d'écrire."""
    import core.db_base as db_base
    db_base._data_cache.clear()
    _serie_faite(logged_in, 1)
    d = json.loads(_serie_faite(logged_in, 3).data)
    assert d["ok"] and d["sets_done"] == 3
    assert d["volume"] == 3 * 10 * 62.5


def test_un_echec_decriture_vide_le_cache(un_an, logged_in, monkeypatch):
    """Si l'écriture échoue à mi-chemin, le cache ne doit pas prétendre
    qu'elle a réussi."""
    import core.db as db
    import core.db_base as db_base
    import core.db_historique as dh
    db_base._data_cache.clear()
    db.get_hist(USER_ID)

    def panne(*a, **k):
        raise RuntimeError("coupure")

    monkeypatch.setattr(dh, "_insert_history", panne)
    assert _serie_faite(logged_in, 1).status_code == 503
    assert f"hist:{USER_ID}" not in db_base._data_cache
