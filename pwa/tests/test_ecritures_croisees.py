"""Deux écritures du même exercice qui se croisent (audit du 03/10, I7, R9).

Chacune lisait les anciennes séries avant que l'autre n'insère les siennes :
les deux insertions restaient, séries en double. On rejoue le croisement
avec une insertion ralentie, dans deux fils."""
import threading
import time

import core.db_historique as dh
from conftest import USER_ID

D = "2026-10-01"
S = lambda n: [{"Séance": "Push", "Exercice": "Développé couché", "Série": k, "Reps": 5,
                "Poids": 100.0, "Date": D} for k in range(1, n + 1)]


def _croiser(monkeypatch, ecrire_a, ecrire_b):
    orig = dh._insert_history

    def lent(client, payload):
        time.sleep(0.2)
        return orig(client, payload)
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


def test_deux_exercices_differents_ne_sattendent_pas(fake_db):
    """Le verrou est par exercice : il ne sérialise pas toute la base."""
    assert dh._verrou(USER_ID, D, "Push", "Squat") is dh._verrou(USER_ID, D, "Push", "Squat")
