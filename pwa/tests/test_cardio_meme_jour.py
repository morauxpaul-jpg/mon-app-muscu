"""Deux cardios identiques le même jour sont deux séances.

La sauvegarde passait par `replace_exo_rows`, qui efface les lignes
existantes de (date, séance, exercice) avant d'insérer. Un second footing
le lundi effaçait donc le premier : le volume, les kilomètres et le
calendrier n'en comptaient qu'un, sans erreur nulle part.

Le ciblage était déjà passé de la semaine à la date, ce qui avait réduit le
défaut sans le supprimer — deux footings la même SEMAINE cohabitent, deux le
même JOUR non.
"""
import datetime as dt

import pytest

from conftest import USER_ID, CSRF

JOUR = "2026-09-14"


def _enregistrer(client, minutes, km, note=""):
    return client.post("/cardio/save", data={
        "activite": "Course", "date": JOUR, "duree_min": str(minutes),
        "distance_km": str(km), "note": note,
    }, headers={"X-CSRFToken": CSRF}, follow_redirects=True)


def _lignes(fake_db):
    return [r for r in fake_db.table("history").select("*").eq(
        "user_id", USER_ID).execute().data
        if str(r.get("exercice") or "").startswith("CARDIO:")]


@pytest.fixture()
def compte(fake_db):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "_planning": {}, "_settings": {}}}).execute()
    return fake_db


def test_deux_footings_le_meme_jour_sont_tous_les_deux_gardes(compte, logged_in):
    _enregistrer(logged_in, 30, 5.0, "matin")
    _enregistrer(logged_in, 45, 8.0, "soir")
    assert len(_lignes(compte)) == 2, _lignes(compte)


def test_le_premier_nest_pas_ecrase(compte, logged_in):
    """Le vrai défaut : la séance du matin disparaissait en enregistrant
    celle du soir."""
    _enregistrer(logged_in, 30, 5.0, "matin")
    _enregistrer(logged_in, 45, 8.0, "soir")
    minutes = sorted(int(r["reps"]) for r in _lignes(compte))
    assert minutes == [30, 45]


def test_les_kilometres_sadditionnent(compte, logged_in):
    """Ce qui se voyait à l'écran : 8 km au lieu de 13."""
    _enregistrer(logged_in, 30, 5.0)
    _enregistrer(logged_in, 45, 8.0)
    assert sum(float(r["poids"]) for r in _lignes(compte)) == pytest.approx(13.0)


def test_les_series_se_suivent(compte, logged_in):
    """Sans numéro distinct, les deux lignes seraient indiscernables à la
    lecture de l'historique."""
    _enregistrer(logged_in, 30, 5.0)
    _enregistrer(logged_in, 45, 8.0)
    assert sorted(int(r["serie"]) for r in _lignes(compte)) == [1, 2]


def test_deux_activites_differentes_restent_separees(compte, logged_in):
    _enregistrer(logged_in, 30, 5.0)
    logged_in.post("/cardio/save", data={
        "activite": "Vélo", "date": JOUR, "duree_min": "60", "distance_km": "20",
    }, headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    activites = {r["exercice"] for r in _lignes(compte)}
    assert activites == {"CARDIO:Course", "CARDIO:Vélo"}


def test_un_autre_jour_repart_de_la_serie_un(compte, logged_in):
    """Le numéro suit la journée, pas le compteur global."""
    _enregistrer(logged_in, 30, 5.0)
    logged_in.post("/cardio/save", data={
        "activite": "Course", "date": "2026-09-15", "duree_min": "30",
        "distance_km": "5",
    }, headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    demain = [r for r in _lignes(compte) if r["date"] == "2026-09-15"]
    assert [int(r["serie"]) for r in demain] == [1]
