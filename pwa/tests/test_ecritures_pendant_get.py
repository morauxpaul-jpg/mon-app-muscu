"""Un affleurement de doigt ne doit rien écrire en base.

`prefetch.js` charge la page visée au `touchstart` ET au survol, pour
remplir le cache avant le clic. Effleurer le lien Accueil — sans même
appuyer — déclenchait donc les écritures de `/accueil` : badges débloqués
et record de streak.

Le garde-fou `is_navigation` existait pour l'upsell et le défi, mais il
était calculé APRÈS ces deux écritures-là. Elles passaient à travers.

Une vraie navigation envoie `Sec-Fetch-Mode: navigate` ; le fetch du
prefetch envoie `same-origin`.
"""
import datetime as dt

import pytest

from conftest import USER_ID, CSRF

LUNDI = dt.date(2026, 9, 14)
PREFETCH = {"Sec-Fetch-Mode": "same-origin"}
VISITE = {"Sec-Fetch-Mode": "navigate"}


@pytest.fixture()
def compte(fake_db):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": LUNDI.isoformat(),
    }}).execute()
    # Assez de séries pour débloquer au moins un badge.
    for i in range(12):
        jour = (LUNDI + dt.timedelta(days=i)).isoformat()
        fake_db.table("history").insert({
            "user_id": USER_ID, "date": jour, "semaine": "2026-W38",
            "seance": "Push", "exercice": "Développé couché", "muscle": "Pecs",
            "series": 1, "reps": 10, "poids": 60.0}).execute()
    return fake_db


def _prog(fake_db):
    return fake_db.table("programs").select("*").eq(
        "user_id", USER_ID).execute().data[0]["data"]


def test_un_prefetch_necrit_aucun_badge(compte, logged_in):
    avant = _prog(compte).get("_badges")
    assert logged_in.get("/accueil", headers=PREFETCH).status_code == 200
    assert _prog(compte).get("_badges") == avant


def test_un_prefetch_necrit_aucun_record_de_streak(compte, logged_in):
    avant = _prog(compte).get("_streak_record")
    logged_in.get("/accueil", headers=PREFETCH)
    assert _prog(compte).get("_streak_record") == avant


def test_une_vraie_visite_enregistre_bien(compte, logged_in):
    """Le garde-fou ne doit pas empêcher ce pour quoi le code existe."""
    logged_in.get("/accueil", headers=VISITE)
    prog = _prog(compte)
    assert prog.get("_badges") or prog.get("_streak_record"), \
        "une visite réelle doit graver quelque chose"


def test_un_prefetch_affiche_quand_meme_la_page(compte, logged_in):
    """On ne coupe que l'écriture : la page rendue doit rester identique,
    sinon le cache servirait une version appauvrie au vrai clic."""
    prefetche = logged_in.get("/accueil", headers=PREFETCH).get_data(as_text=True)
    visite = logged_in.get("/accueil", headers=VISITE).get_data(as_text=True)
    assert len(prefetche) > 500
    # Même nombre de badges affichés de part et d'autre.
    assert prefetche.count("badge-item") == visite.count("badge-item")


def test_sans_en_tete_on_considere_que_cest_une_visite(compte, logged_in):
    """Un vieux navigateur n'envoie pas `Sec-Fetch-Mode`. Mieux vaut écrire
    une fois de trop que perdre un badge pour toujours."""
    logged_in.get("/accueil")
    prog = _prog(compte)
    assert prog.get("_badges") or prog.get("_streak_record")
