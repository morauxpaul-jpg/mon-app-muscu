"""Préciser le nom d'un exercice dans le programme.

Le seated row se fait en prise neutre ou en prise large : deux façons qui
ne se chargent pas pareil, donc deux progressions. Mais la bibliothèque
n'offre qu'une entrée, et une fois l'exercice ajouté son nom n'était plus
modifiable — il fallait le supprimer et le resaisir.

Pire : le bouton de la bibliothèque s'appelait « + Ajouter » alors qu'il
ne fait que REMPLIR le champ. On validait donc sans voir qu'on pouvait
encore changer le nom.
"""
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
CARTE = (RACINE / "templates" / "_programme_seance_card.html").read_text(
    encoding="utf-8")
PAGE = (RACINE / "templates" / "programme.html").read_text(encoding="utf-8")


def test_le_nom_dun_exercice_est_modifiable():
    """Avant : `x-text`, donc lecture seule. Changer un nom imposait de
    supprimer la ligne et de tout resaisir."""
    bloc = CARTE[CARTE.index('class="prog-exo-name"'):][:900]
    assert "prog-exo-rename" in bloc, "le nom n'est pas un champ"
    assert "renommerExo(" in bloc, "le champ ne déclenche aucun renommage"


def test_le_bouton_de_la_bibliotheque_ne_ment_plus():
    """Il remplit le champ, il n'ajoute pas. « + Ajouter » faisait valider
    sans regarder le nom."""
    assert ">+ Ajouter</button>" not in CARTE
    assert ">Choisir</button>" in CARTE


def test_le_renommage_previent_pour_lhistorique():
    """Renommer ici ne peut pas deviner si on SCINDE un exercice en deux
    (les séries passées appartiennent alors à l'un des deux) ou si on
    CORRIGE une faute (elles doivent suivre). On le dit plutôt que de
    choisir à la place de l'utilisateur."""
    bloc = PAGE[PAGE.index("renommerExo("):][:1400]
    assert "ancien nom" in bloc
    assert "Gestion" in bloc


def test_le_champ_de_saisie_dit_quon_peut_preciser():
    """Sans un mot, personne ne devine que « prise neutre » et « prise
    large » sont deux exercices à suivre séparément."""
    assert "prise neutre" in CARTE and "prise large" in CARTE


def test_aucune_apostrophe_echappee_dans_les_expressions_alpine():
    """Une apostrophe échappée dans un attribut Alpine casse l'expression
    en silence — c'est ce qui avait rendu « Montée d'escaliers »
    inutilisable pendant des semaines."""
    for expression in re.findall(r'[:@][\w.-]+="([^"]*)"', CARTE):
        assert chr(92) + chr(39) not in expression, expression
