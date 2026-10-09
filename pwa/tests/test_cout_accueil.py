"""Ce que coûte un affichage de l'accueil.

C'est le premier écran, celui qu'on ouvre le plus, souvent en 4G dans une
salle. Son coût grandit avec l'historique : chaque séance faite alourdit
chaque ouverture, pour toujours.

Mesuré avec un an d'entraînement en base (1 872 séries), un seul affichage
faisait **8 requêtes Supabase** — dont le programme **trois fois**, parce que
la page pouvait le sauvegarder jusqu'à quatre fois : badges débloqués, record
de streak, bandeau PRO, défi gagné. Chacune relisait et réécrivait tout le
blob sous verrou optimiste, pour afficher une page.

Ces tests tiennent le compte : une seule sauvegarde, et ce qu'elle doit
contenir n'est pas perdu au passage.
"""
import datetime as dt

import pytest

from conftest import USER_ID, CSRF, prog_lu

LUNDI = dt.date(2026, 9, 14)
VISITE = {"Sec-Fetch-Mode": "navigate"}
PREFETCH = {"Sec-Fetch-Mode": "same-origin"}


@pytest.fixture()
def compte(fake_db, monkeypatch):
    """Assez d'historique pour débloquer des badges ET un record de streak.
    Vu le jour de la dernière séance : le streak part d'aujourd'hui."""
    import routes.accueil as accueil
    monkeypatch.setattr(accueil, "logical_today_paris", lambda: LUNDI)
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": (LUNDI - dt.timedelta(days=60)).isoformat(),
    }}).execute()
    for i in range(40):
        jour = (LUNDI - dt.timedelta(days=i)).isoformat()
        fake_db.table("history").insert({
            "user_id": USER_ID, "date": jour, "semaine": "2026-W38",
            "seance": "Push", "exercice": "Développé couché", "muscle": "Pecs",
            "serie": 1, "reps": 10, "poids": 60.0}).execute()
    return fake_db


@pytest.fixture()
def compter_sauvegardes(monkeypatch):
    """Compte les `save_prog` d'une requête, sans changer leur effet."""
    import core.data as data
    vrai = data.save_prog
    appels = []

    def espion(prog_dict):
        appels.append(dict(prog_dict))
        return vrai(prog_dict)

    monkeypatch.setattr(data, "save_prog", espion)
    return appels


def _prog(fake_db):
    return fake_db.table("programs").select("*").eq(
        "user_id", USER_ID).execute().data[0]["data"]


# ── Une seule écriture ───────────────────────────────────────────────────

def test_une_visite_ne_sauvegarde_le_programme_quune_fois(
        compte, logged_in, compter_sauvegardes):
    """Quatre raisons d'écrire, une seule écriture.

    Chaque `save_prog` relit le blob, le fusionne et le réécrit sous verrou
    optimiste, avec jusqu'à trois tentatives. En empiler quatre pour afficher
    une page, c'est quatre fois ce travail — et quatre occasions de conflit.
    """
    assert logged_in.get("/accueil", headers=VISITE).status_code == 200
    assert len(compter_sauvegardes) <= 1, (
        f"{len(compter_sauvegardes)} sauvegardes pour un affichage")


def test_un_prefetch_ne_sauvegarde_rien(compte, logged_in, compter_sauvegardes):
    """Le garde-fou de N4 tient toujours après le regroupement."""
    logged_in.get("/accueil", headers=PREFETCH)
    assert compter_sauvegardes == []


def test_une_deuxieme_visite_nechrit_plus_rien(
        compte, logged_in, compter_sauvegardes):
    """Rien de neuf à graver = rien à écrire. Sinon chaque ouverture de l'app
    écrirait en base sans raison."""
    logged_in.get("/accueil", headers=VISITE)
    compter_sauvegardes.clear()
    logged_in.get("/accueil", headers=VISITE)
    assert compter_sauvegardes == []


# ── Et ce qu'elle porte n'est pas perdu ──────────────────────────────────

def test_lunique_sauvegarde_porte_les_badges_et_le_streak(compte, logged_in):
    """Regrouper ne doit pas faire tomber l'une des quatre en route."""
    logged_in.get("/accueil", headers=VISITE)
    prog = prog_lu()
    assert prog.get("_badges"), "les badges ne sont plus gravés"
    assert prog.get("_streak_record"), "le record de streak n'est plus gravé"


def test_les_badges_affiches_sont_les_memes_quon_ecrive_ou_non(compte, logged_in):
    """Un prefetch doit RENDRE la même page : on coupe l'écriture, pas
    l'affichage. Sinon le cache servirait une version appauvrie au vrai clic."""
    prefetche = logged_in.get("/accueil", headers=PREFETCH).get_data(as_text=True)
    visite = logged_in.get("/accueil", headers=VISITE).get_data(as_text=True)
    assert prefetche.count("badge-item") == visite.count("badge-item")


def test_un_badge_obtenu_nest_jamais_perdu(compte, logged_in):
    """L'union avec l'existant doit survivre au regroupement : un badge gagné
    il y a six mois reste acquis même si ses conditions ne tiennent plus."""
    ligne = compte.table("programs").select("*").eq("user_id", USER_ID).execute().data[0]
    ligne["data"]["_badges"] = ["badge_fantome"]
    compte.table("programs").update({"data": ligne["data"]}).eq(
        "user_id", USER_ID).execute()

    logged_in.get("/accueil", headers=VISITE)
    assert "badge_fantome" in (prog_lu().get("_badges") or [])


def test_une_sauvegarde_qui_echoue_naffiche_pas_une_erreur(
        compte, logged_in, monkeypatch):
    """Un badge non gravé vaut mieux qu'un accueil cassé.

    Les quatre écritures étaient chacune dans un `try/except` ; celle qui les
    remplace doit l'être aussi.
    """
    import core.data as data

    def casse(_):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(data, "save_prog", casse)
    assert logged_in.get("/accueil", headers=VISITE).status_code == 200


# ── Le nombre de requêtes ────────────────────────────────────────────────

def test_un_affichage_ne_multiplie_pas_les_requetes(compte, logged_in, monkeypatch):
    """Plafond mesuré, pas choisi : il n'est là que pour signaler une hausse."""
    import core.db_base as db_base
    vraie = db_base._client.table
    tables = []

    def espion(nom):
        tables.append(nom)
        return vraie(nom)

    monkeypatch.setattr(db_base._client, "table", espion)
    db_base._data_cache.clear()
    logged_in.get("/accueil", headers=VISITE)
    assert tables.count("programs") <= 2, (
        f"le programme est touché {tables.count('programs')} fois "
        f"(1 lecture + 1 écriture attendues) : {tables}")
