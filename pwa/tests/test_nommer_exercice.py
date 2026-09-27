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


# ── Les prises sont proposables, pas seulement saisissables ──────


def _bibliotheque():
    import json
    import subprocess
    sortie = subprocess.run(
        ["node", "-e",
         "const l=require('./static/js/exercise-library.js');"
         "console.log(JSON.stringify(Object.values(l.EXERCISE_LIBRARY)"
         ".flat().map(e=>e.name)))"],
        capture_output=True, text=True, encoding="utf-8", cwd=RACINE)
    if sortie.returncode != 0:
        pytest.skip("node indisponible")
    return json.loads(sortie.stdout)


@pytest.mark.parametrize("entree", [
    "Tirage horizontal prise neutre",
    "Tirage horizontal prise large",
    "Tirage vertical prise large",
    "Tirage vertical prise serrée",
])
def test_les_prises_courantes_se_choisissent_dans_la_liste(entree):
    """Pouvoir renommer apres coup ne suffit pas : encore faut-il savoir
    que les deux existent. La bibliotheque distingue deja les prises pour
    les tractions (pronation / supination) — le dos suit le meme
    precedent."""
    assert entree in _bibliotheque()


@pytest.mark.parametrize("prise", [
    "Tirage horizontal prise neutre",
    "Tirage horizontal prise large",
])
def test_une_prise_proposee_trouve_sa_fiche(prise):
    """Une entrée de bibliothèque sans fiche donne une carte muette dès la
    première séance."""
    from core.exercises_data import get_exercise_info
    info = get_exercise_info(prise)
    assert info is not None, prise
    assert info.get("illustration") is True, prise


def test_les_deux_prises_restent_deux_exercices():
    """Même fiche, mais pas le même historique : les charges n'ont rien à
    voir. Les confondre rendrait la progression illisible."""
    from core.exercises_data import canoniser
    assert canoniser("Tirage horizontal prise neutre") == (None, "")
    assert canoniser("Tirage horizontal prise large") == (None, "")
