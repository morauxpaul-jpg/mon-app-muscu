"""Deux écritures du même exercice qui se croisent (audit du 03/10, I7, R9).

Chacune lisait les anciennes séries avant que l'autre n'insère les siennes :
les deux insertions restaient, séries en double. On rejoue le croisement
avec une insertion ralentie, dans deux fils."""
import threading
import time

import pytest

import core.db_historique as dh
from core import partage
from conftest import USER_ID

D = "2026-10-01"
S = lambda n: [{"Séance": "Push", "Exercice": "Développé couché", "Série": k, "Reps": 5,
                "Poids": 100.0, "Date": D} for k in range(1, n + 1)]


def _croiser(monkeypatch, ecrire_a, ecrire_b):
    orig = dh._insert_history

    def lent(client, payload, **kw):
        time.sleep(0.2)
        return orig(client, payload, **kw)
    monkeypatch.setattr(dh, "_insert_history", lent)
    a = threading.Thread(target=ecrire_a)
    b = threading.Thread(target=ecrire_b)
    a.start(); time.sleep(0.05); b.start()
    a.join(); b.join()


def test_deux_remplacements_croises_ne_dupliquent_rien(fake_db, monkeypatch):
    _croiser(monkeypatch,
             lambda: dh.replace_exo_rows(USER_ID, D, "Push", "Développé couché", S(2)),
             lambda: dh.replace_exo_rows(USER_ID, D, "Push", "Développé couché", S(3)))
    series = sorted(r["serie"] for r in fake_db.tables["history"])
    assert series == [1, 2, 3], "le dernier état gagne, sans doublon"


def test_deux_ajouts_de_cardio_croises_gardent_des_numeros_distincts(fake_db, monkeypatch):
    bloc = [{"Séance": "Push", "Exercice": "CARDIO:Rameur", "Série": 1, "Reps": 10, "Poids": 2.0}]
    _croiser(monkeypatch,
             lambda: dh.append_exo_rows(USER_ID, D, "Push", "CARDIO:Rameur", bloc),
             lambda: dh.append_exo_rows(USER_ID, D, "Push", "CARDIO:Rameur", bloc))
    assert sorted(r["serie"] for r in fake_db.tables["history"]) == [1, 2]


def test_le_meme_exercice_attend_son_tour(fake_db):
    """Le verrou porte sur (compte, date, séance, exercice) — partagé entre
    instances quand Redis est là (tests/test_partage.py)."""
    with dh._verrou(USER_ID, D, "Push", "Squat"):
        with pytest.raises(TimeoutError):
            with partage.verrou("exo", USER_ID, D, "Push", "Squat", attente=0.05):
                pass
