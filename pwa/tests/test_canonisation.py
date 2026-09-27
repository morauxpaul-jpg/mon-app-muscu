"""Ramener les noms de l'historique sur ceux du catalogue.

Un programme écrit à la main accumule « TRICEPS EXTENSION », « Triceps
extension barre », « developpe couche ». Tant que ces noms diffèrent, chaque
orthographe a son propre historique : records éclatés, « dernière fois »
vide, progression illisible.

Renommer l'historique n'est PAS réversible. D'où deux exigences : le matcher
dit à quel point il est sûr, et rien ne bouge sans validation.
"""
import pytest

from core.exercises_data import (EXERCISES_INFO, NIVEAUX_SURS, canoniser,
                                 resoudre)


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


def test_les_niveaux_surs_excluent_les_rattrapages_larges():
    """« mots » et « sous_ensemble » peuvent se tromper : « développé couché
    prise serrée » n'est pas un développé couché. Assez bon pour proposer une
    fiche, pas pour renommer tout seul."""
    assert "mots" not in NIVEAUX_SURS
    assert "sous_ensemble" not in NIVEAUX_SURS
    assert "anglais" not in NIVEAUX_SURS
    assert set(NIVEAUX_SURS) <= {"exact", "orthographe", "parenthese", "materiel"}


def test_un_nom_inconnu_ne_resout_vers_rien():
    assert resoudre("Zumba intergalactique") == (None, "")
    assert resoudre("") == (None, "")
    assert resoudre(None) == (None, "")


# ── La variante est une donnée, pas une faute ────────────────────


def test_le_materiel_traverse_la_migration_intact():
    """« (Poulie) » dit avec quoi la série a été faite. Le perdre effacerait
    la distinction entre trois façons de faire le même mouvement."""
    assert canoniser("TRICEPS EXTENSION (Poulie)")[0] == "Extensions triceps (Poulie)"
    assert canoniser("developpe couche (Barre)")[0] == "Développé couché (Barre)"


def test_une_parenthese_qui_nest_pas_du_materiel_reste_dans_le_nom():
    """« Hip thrust (sol) » est un nom d'exercice, pas un hip thrust fait au
    sol. Le découper le casserait."""
    assert canoniser("Hip thrust (sol)") == (None, "")
    assert canoniser("Squat (poids du corps ou lesté)") == (None, "")


# ── Ce qui ne doit pas bouger ────────────────────────────────────


def test_un_nom_deja_canonique_ne_propose_aucun_changement():
    """Sinon la migration afficherait 87 renommages qui ne font rien."""
    for nom in EXERCISES_INFO:
        assert canoniser(nom) == (None, ""), nom


def test_un_exercice_absent_du_catalogue_est_laisse_tranquille():
    """Les exercices maison doivent survivre à la migration."""
    assert canoniser("Mon exercice à moi") == (None, "")


def test_la_canonisation_est_stable():
    """Rejouer la migration ne doit plus rien changer. Sans ça, deux passages
    feraient dériver les noms — et un historique ne se rattrape pas."""
    for depart in ("TRICEPS EXTENSION", "developpe couche", "PEC FLY",
                   "ÉCARTÉ POULIE VIS À VIS HAUTE (Machine)", "Leg press"):
        une_fois = canoniser(depart)[0]
        assert une_fois, depart
        assert canoniser(une_fois) == (None, ""), f"{depart} -> {une_fois} -> encore"


def test_aucun_exercice_du_catalogue_nen_absorbe_un_autre():
    """Si « Squat » canonisait vers « Squat bulgare », la migration
    fusionnerait deux exercices que l'utilisateur distingue — et l'historique
    de l'un se retrouverait sous l'autre, sans retour possible."""
    fusions = []
    for nom in EXERCISES_INFO:
        vers, _ = canoniser(nom)
        if vers and vers != nom:
            fusions.append((nom, vers))
    assert not fusions, fusions


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


def test_deux_prises_ne_sont_jamais_proposees_a_la_fusion():
    """Elles ne se chargent pas pareil : prise neutre et prise large mènent
    chacune sa progression. Les renommer vers le même nom fusionnerait deux
    passés en un, sans retour possible — et le seul indice serait une
    courbe qui devient incohérente."""
    for saisi in ("Tirage horizontal prise neutre",
                  "Tirage horizontal prise large",
                  "Développé couché prise inversée"):
        assert canoniser(saisi) == (None, ""), f"{saisi} -> {canoniser(saisi)}"


def test_une_prise_que_le_catalogue_distingue_garde_sa_propre_fiche():
    """« Tirage vertical prise serrée » est une entrée à part entière : elle
    ne doit pas retomber sur « Tirage vertical »."""
    assert resoudre("Tirage vertical prise serrée") == (
        "Tirage vertical prise serrée", "exact")
