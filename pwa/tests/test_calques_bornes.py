"""Les calques du jour ne doivent pas s'accumuler à vie.

Le blob `programs.data` est relu ET réécrit à chaque interaction — chaque
série validée, chaque case cochée. Tout ce qu'on y laisse est donc relu et
réécrit pour toujours.

Quatre calques y rangent une entrée par séance ET par date : `_extras` (les
exercices ajoutés à la volée), `_libre_draft` (le brouillon de séance libre),
`_substituts` (les échanges du jour) et `_seance_order` (l'ordre des cartes).
`/seance/finish` en nettoyait **trois**. Le quatrième, `_seance_order`, était
écrit et jamais effacé : une entrée par séance réordonnée, à vie.

Ces tests tiennent la règle pour les quatre, et vérifient le rattrapage de ce
qui s'est déjà accumulé.
"""
import datetime as dt

import pytest

from conftest import USER_ID, CSRF

LUNDI = dt.date(2026, 9, 14)
CALQUES = ("_extras", "_libre_draft", "_substituts", "_seance_order")


@pytest.fixture()
def compte(fake_db):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": LUNDI.isoformat(),
    }}).execute()
    return fake_db


def _prog(fake_db):
    return fake_db.table("programs").select("*").eq(
        "user_id", USER_ID).execute().data[0]["data"]


def _ecrire(fake_db, calques):
    ligne = fake_db.table("programs").select("*").eq("user_id", USER_ID).execute().data[0]
    ligne["data"].update(calques)
    fake_db.table("programs").update({"data": ligne["data"]}).eq(
        "user_id", USER_ID).execute()


def _finir(client, date_str, seance="Push", mode="prefaite"):
    return client.post("/seance/finish", data={
        "mode": mode, "seance_name": seance, "date": date_str, "_csrf": CSRF})


# ── La règle, pour les quatre calques ────────────────────────────────────

@pytest.mark.parametrize("calque", CALQUES)
def test_le_calque_du_jour_disparait_a_la_fin_de_la_seance(calque, compte, logged_in):
    """Terminer une séance efface ce qui ne concernait que ce jour-là."""
    jour = LUNDI.isoformat()
    contenu = ["Squat"] if calque == "_seance_order" else (
        {"curl biceps": "Curl marteau"} if calque == "_substituts"
        else [{"name": "Squat", "sets": 3, "muscle": "Quadriceps"}])
    mode = "libre" if calque == "_libre_draft" else "prefaite"
    _ecrire(compte, {calque: {f"Push|{jour}": contenu}})

    _finir(logged_in, jour, mode=mode)

    reste = _prog(compte).get(calque) or {}
    assert f"Push|{jour}" not in reste, (
        f"{calque} garde l'entrée du jour après la fin de la séance")


def test_lordre_des_cartes_ne_survit_pas_a_la_seance(compte, logged_in):
    """Le cas qui manquait : nommé à part pour qu'on sache lequel a cassé."""
    jour = LUNDI.isoformat()
    _ecrire(compte, {"_seance_order": {f"Push|{jour}": ["Squat", "Dips"]}})
    _finir(logged_in, jour)
    assert not (_prog(compte).get("_seance_order") or {})


# ── Le rattrapage de l'existant ──────────────────────────────────────────

def test_les_vieilles_entrees_accumulees_sont_purgees(compte, logged_in):
    """Effacer en fin de séance ne concerne que les séances à venir.

    Un compte qui a déjà des mois d'ordres enregistrés doit voir le passé
    nettoyé, pas seulement la séance du jour.
    """
    jour = LUNDI.isoformat()
    vieux = (LUNDI - dt.timedelta(days=200)).isoformat()
    moyen = (LUNDI - dt.timedelta(days=90)).isoformat()
    recent = (LUNDI - dt.timedelta(days=10)).isoformat()
    _ecrire(compte, {"_seance_order": {
        f"Push|{jour}": ["Squat"],
        f"Pull|{vieux}": ["Traction"],
        f"Pull|{moyen}": ["Rowing"],
        f"Pull|{recent}": ["Curl"],
        "sans-date": ["Bruit"],
    }})

    _finir(logged_in, jour)

    reste = _prog(compte).get("_seance_order") or {}
    assert f"Pull|{vieux}" not in reste
    assert f"Pull|{moyen}" not in reste
    assert "sans-date" not in reste
    assert f"Pull|{recent}" in reste, "12 semaines de marge, pas moins"


def test_une_seance_recente_garde_son_ordre(compte, logged_in):
    """La purge ne doit pas manger ce qui sert encore.

    Rouvrir la séance d'avant-hier doit retrouver l'ordre qu'on lui a donné.
    """
    jour = LUNDI.isoformat()
    avant_hier = (LUNDI - dt.timedelta(days=2)).isoformat()
    _ecrire(compte, {"_seance_order": {
        f"Push|{jour}": ["Squat"], f"Push|{avant_hier}": ["Dips", "Squat"]}})
    _finir(logged_in, jour)
    assert f"Push|{avant_hier}" in (_prog(compte).get("_seance_order") or {})


# ── La purge elle-même, hors requête ─────────────────────────────────────

def test_purger_un_calque_absent_ne_fait_rien():
    from core.seance_calques import _purger_calque
    assert _purger_calque({}, "_seance_order") is False
    assert _purger_calque({"_seance_order": {}}, "_seance_order") is False


def test_purger_signale_ce_quil_a_retire():
    from core.seance_calques import _purger_calque
    prog = {"_seance_order": {
        f"Push|{(LUNDI - dt.timedelta(days=300)).isoformat()}": ["A"],
        f"Push|{LUNDI.isoformat()}": ["B"],
    }}
    assert _purger_calque(prog, "_seance_order", today=LUNDI) is True
    assert list(prog["_seance_order"]) == [f"Push|{LUNDI.isoformat()}"]
    assert _purger_calque(prog, "_seance_order", today=LUNDI) is False


def test_les_deux_purges_partagent_la_meme_fenetre():
    """Bilans et ordre des cartes suivent la même règle : une seule à retenir."""
    from core.seance_calques import (SESSION_NOTES_KEEP_DAYS,
                                     _purge_old_seance_order,
                                     _purge_old_session_notes)
    vieux = (LUNDI - dt.timedelta(days=SESSION_NOTES_KEEP_DAYS + 1)).isoformat()
    prog = {"_session_notes": {f"Push|{vieux}": {"rating": 5}},
            "_seance_order": {f"Push|{vieux}": ["A"]}}
    assert _purge_old_session_notes(prog, today=LUNDI) is True
    assert _purge_old_seance_order(prog, today=LUNDI) is True
    assert prog["_session_notes"] == {} and prog["_seance_order"] == {}
