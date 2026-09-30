"""Une série saisie ne se perd plus (audit du 30/09 : C1, I5, I9).

Côté serveur, trois garanties :
- l'envoi partiel de « Série faite » n'écrit QUE les séries remplies — les
  autres ne deviennent pas des SKIP au milieu de l'exercice ;
- réécrire les séries d'un exercice insère avant d'effacer : un échec au
  milieu laisse l'ancien état, pas un exercice vide ;
- « Skip » n'efface pas des séries réelles sans confirmation explicite.

Le parcours complet, lui, est joué dans un navigateur :
tests/e2e/test_seance_navigateur.py.
"""
import json

import pytest

from conftest import USER_ID, CSRF
from test_seance_saisie import MONDAY, JSON_HEADERS, _seed, _hist

EXO = "Développé couché"


def _envoyer(client, sets, **extra):
    data = {
        "_csrf": CSRF, "seance_name": "Push", "exo_base": EXO,
        "variant": "Standard", "muscle": "Pecs", "date": MONDAY.isoformat(),
        "mode": "prefaite", "name": "Push", "sets_json": json.dumps(sets),
    }
    data.update(extra)
    return client.post("/seance/save-exo", data=data, headers=JSON_HEADERS)


def _lignes(fake):
    return sorted((r["serie"], r["reps"], r["poids"], r.get("remarque") or "")
                  for r in fake.tables.get("history", []) if r["exercice"] == EXO)


# ── Envoi partiel (« Série faite ») ──────────────────────────────


def test_lenvoi_partiel_necrit_que_les_series_remplies(fake_db, logged_in):
    _seed(fake_db)
    r = _envoyer(logged_in, [{"reps": 5, "poids": 100}, {"reps": "", "poids": 100},
                             {"reps": "", "poids": ""}], partiel="1")
    assert json.loads(r.data)["ok"] is True
    assert _lignes(fake_db) == [(1, 5, 100.0, "")], \
        "les séries pas encore faites ne sont pas des SKIP"


def test_lenvoi_complet_marque_toujours_les_vides_skip(fake_db, logged_in):
    """« Enregistrer » garde son sens : j'ai fini cet exercice."""
    _seed(fake_db)
    _envoyer(logged_in, [{"reps": 5, "poids": 100}, {"reps": "", "poids": 100}])
    assert _lignes(fake_db) == [(1, 5, 100.0, ""), (2, 0, 0.0, "SKIP")]


def test_un_envoi_partiel_vide_ne_touche_a_rien(fake_db, logged_in):
    """Un envoi sans aucune série remplie ne doit pas effacer ce qui est en base."""
    _seed(fake_db)
    _hist(fake_db, MONDAY, reps=5, poids=100.0)
    r = _envoyer(logged_in, [{"reps": "", "poids": 100}], partiel="1")
    assert r.status_code == 200
    assert _lignes(fake_db) == [(1, 5, 100.0, "")]


def test_les_envois_partiels_successifs_saccumulent(fake_db, logged_in):
    _seed(fake_db)
    _envoyer(logged_in, [{"reps": 5, "poids": 100}, {"reps": ""}], partiel="1")
    _envoyer(logged_in, [{"reps": 5, "poids": 100}, {"reps": 4, "poids": 100}], partiel="1")
    assert _lignes(fake_db) == [(1, 5, 100.0, ""), (2, 4, 100.0, "")]


# ── Réécriture sans trou ─────────────────────────────────────────


def test_un_echec_dinsertion_laisse_les_anciennes_series(fake_db, logged_in, monkeypatch):
    """DELETE puis INSERT sans transaction : une coupure entre les deux
    effaçait l'exercice. Maintenant on insère d'abord."""
    import core.db_historique as dh
    _seed(fake_db)
    _hist(fake_db, MONDAY, reps=5, poids=100.0)

    def panne(*a, **k):
        raise RuntimeError("coupure réseau")

    monkeypatch.setattr(dh, "_insert_history", panne)
    r = _envoyer(logged_in, [{"reps": 6, "poids": 100}], partiel="1")
    assert r.status_code == 503
    assert _lignes(fake_db) == [(1, 5, 100.0, "")], "l'ancien état est intact"


def test_la_reecriture_remplace_bien_lancien_etat(fake_db, logged_in):
    _seed(fake_db)
    _hist(fake_db, MONDAY, reps=5, poids=100.0)
    _envoyer(logged_in, [{"reps": 6, "poids": 102.5}], partiel="1")
    assert _lignes(fake_db) == [(1, 6, 102.5, "")]


# ── Skip ─────────────────────────────────────────────────────────


def _skip(client, **extra):
    data = {"_csrf": CSRF, "seance_name": "Push", "exo_base": EXO,
            "variant": "Standard", "muscle": "Pecs", "date": MONDAY.isoformat(),
            "mode": "prefaite", "name": "Push"}
    data.update(extra)
    return client.post("/seance/skip-exo", data=data, headers=JSON_HEADERS)


def test_skip_refuse_deffacer_des_series_sans_confirmation(fake_db, logged_in):
    _seed(fake_db)
    for n in (1, 2, 3):
        _hist(fake_db, MONDAY, reps=5, poids=100.0, serie=n)
    r = _skip(logged_in)
    assert r.status_code == 409
    d = json.loads(r.data)
    assert d["a_confirmer"] is True and d["series"] == 3
    assert len(_lignes(fake_db)) == 3


def test_skip_confirme_efface(fake_db, logged_in):
    _seed(fake_db)
    _hist(fake_db, MONDAY, reps=5, poids=100.0)
    r = _skip(logged_in, confirme="1")
    assert r.status_code == 200
    assert _lignes(fake_db) == [(1, 0, 0.0, "SKIP")]


def test_skip_sur_un_exercice_vide_passe_sans_question(fake_db, logged_in):
    _seed(fake_db)
    assert _skip(logged_in).status_code == 200
