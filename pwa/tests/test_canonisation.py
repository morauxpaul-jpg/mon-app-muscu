"""Ramener les noms de l'historique sur ceux du catalogue.

Un programme écrit à la main accumule « TRICEPS EXTENSION », « Triceps
extension barre », « developpe couche ». Tant que ces noms diffèrent, chaque
orthographe a son propre historique : records éclatés, « dernière fois »
vide, progression illisible.

Renommer l'historique n'est PAS réversible. D'où deux exigences : le matcher
dit à quel point il est sûr (ici), et rien ne bouge sans validation
(Gestion → « Ranger mes exercices », tests/test_ranger_exercices.py).
"""
import pytest

from core.exercises_data import resoudre


# ── Le niveau de certitude ───────────────────────────────────────


@pytest.mark.parametrize("nom,niveau", [
    ("Développé couché", "exact"),
    ("developpe couche", "orthographe"),
    ("DÉVELOPPÉ COUCHÉ", "orthographe"),
    ("Curl biceps haltères", "materiel"),
    ("Leg press", "surnom"),
    ("PEC FLY", "anglais"),
    ("TRICEPS EXTENSION", "mots"),
    ("ÉCARTÉ POULIE VIS À VIS HAUTE", "sous_ensemble"),
])
def test_le_matcher_dit_comment_il_a_reconnu(nom, niveau):
    """Afficher une fiche se corrige d'un rechargement ; renommer un
    historique, non. Le niveau décide de ce qu'on propose coché."""
    assert resoudre(nom)[1] == niveau


def test_un_nom_inconnu_ne_resout_vers_rien():
    assert resoudre("Zumba intergalactique") == (None, "")
    assert resoudre("") == (None, "")
    assert resoudre(None) == (None, "")


# Ce qui se renomme, et ce qui ne se renomme jamais : tests/test_ranger_exercices.py.


# ── La prise : même fiche, historiques séparés ───────────────────


@pytest.mark.parametrize("saisi", [
    "Tirage horizontal prise neutre",
    "Tirage horizontal prise large",
])
def test_une_prise_partage_la_fiche_de_lexercice(saisi):
    """Le geste, les conseils et l'illustration sont les mêmes quelle que
    soit la prise : inutile d'écrire deux fiches."""
    from core.exercises_data import get_exercise_info
    info = get_exercise_info(saisi)
    assert info is not None, saisi
    assert info["name"].startswith("Tirage horizontal")


def test_une_prise_que_le_catalogue_distingue_garde_sa_propre_fiche():
    """« Tirage vertical prise serrée » est une entrée à part entière : elle
    ne doit pas retomber sur « Tirage vertical »."""
    assert resoudre("Tirage vertical prise serrée") == (
        "Tirage vertical prise serrée", "exact")
