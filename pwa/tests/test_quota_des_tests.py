"""Le limiteur de débit ne doit pas faire tomber des tests voisins.

`core/limiter.py` est **process-wide** et compte par route : les 60 requêtes
par minute de `/accueil` étaient partagées par TOUS les tests d'une exécution.
Ajouter huit tests sur cette page a suffi à dépasser le seuil — et ce sont
trois tests voisins, écrits des mois plus tôt et parfaitement corrects, qui
ont reçu un 429 et sont tombés.

Un échec qui désigne le mauvais coupable coûte plus cher qu'un échec : on
cherche la régression là où elle n'est pas.

`conftest.quota_neuf` remet donc le compteur à zéro avant chaque test. Ces
deux tests le prouvent : chacun consomme une bonne part du quota, et le
second doit passer malgré le premier.
"""
import pytest

from conftest import USER_ID

RAFALE = 35          # par test : deux tests dépassent les 60/minute de la route
LIMITE_PAR_MINUTE = 60


@pytest.fixture()
def compte(fake_db):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {}}}).execute()
    return fake_db


def _rafale(client):
    return [client.get("/accueil").status_code for _ in range(RAFALE)]


def test_le_quota_suffit_a_un_test(compte, logged_in):
    assert 2 * RAFALE > LIMITE_PAR_MINUTE, (
        "la rafale doit être assez grosse pour que DEUX tests dépassent le "
        "seuil, sinon ce fichier ne prouve rien")
    assert set(_rafale(logged_in)) == {200}


def test_le_test_suivant_repart_avec_son_quota(compte, logged_in):
    """C'est celui-ci qui tombait en 429 avant la remise à zéro."""
    codes = _rafale(logged_in)
    assert 429 not in codes, (
        "le quota d'un test précédent a débordé sur celui-ci")
    assert set(codes) == {200}
