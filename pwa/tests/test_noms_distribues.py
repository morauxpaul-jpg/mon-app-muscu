"""Les trois endroits où l'app DONNE un nom d'exercice.

Le catalogue (`EXERCISES_INFO`) dit ce qu'un exercice est. Mais trois autres
listes en distribuent les noms : la bibliothèque du créateur de programme,
les programmes tout faits de l'inscription, et le générateur IA. Quand elles
dérivent du catalogue, chaque programme construit porte des noms qu'il
faudra rapprocher à vie.

C'est arrivé : le matériel est devenu une variante dans le catalogue, mais
la bibliothèque proposait encore « Élévation latérale haltères » et les
programmes tout faits le citaient 47 fois. Ces tests ferment la porte.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

from core.exercises_data import _ABSORBES, EXERCISES_INFO, resoudre

RACINE = Path(__file__).resolve().parent.parent


def _bibliotheque():
    """Les entrées du fichier JS, lues par Node — une seule source."""
    sortie = subprocess.run(
        ["node", "-e",
         "const l=require('./static/js/exercise-library.js');"
         "console.log(JSON.stringify(Object.entries(l.EXERCISE_LIBRARY)"
         ".flatMap(([g,v])=>v.map(e=>[g,e.name]))))"],
        capture_output=True, text=True, encoding="utf-8", cwd=RACINE)
    if sortie.returncode != 0:
        pytest.skip("node indisponible")
    return json.loads(sortie.stdout)


def _programmes_tout_faits():
    src = (RACINE / "core" / "catalog.py").read_text(encoding="utf-8")
    return sorted(set(re.findall(r'_ex\("([^"]+)"', src)))


# ── Aucune liste ne distribue un nom absorbé ─────────────────────


def test_la_bibliotheque_ne_propose_aucun_nom_absorbe():
    """« Élévation latérale haltères » ne doit plus être proposable : le
    matériel se choisit à côté du nom, pas en choisissant un autre
    exercice."""
    absorbes = {n.casefold() for n in _ABSORBES}
    fautifs = [f"{g} / {n}" for g, n in _bibliotheque() if n.casefold() in absorbes]
    assert not fautifs, fautifs


def test_les_programmes_tout_faits_ne_citent_aucun_nom_absorbe():
    """Un compte créé aujourd'hui doit repartir avec des noms que l'app
    reconnaît — sinon le problème renaît à chaque inscription."""
    absorbes = {n.casefold() for n in _ABSORBES}
    fautifs = [n for n in _programmes_tout_faits() if n.casefold() in absorbes]
    assert not fautifs, fautifs


# ── Tout ce qui est distribué se résout ──────────────────────────


# Trois exercices cités par les programmes tout faits n'ont pas de fiche au
# catalogue, et ce n'en sont pas des variantes : il faudrait les écrire.
# Ils sont nommés ici plutôt que tolérés en silence — le test bloque toute
# NOUVELLE dérive sans prétendre que celle-là est réglée.
SANS_FICHE_CONNUS = {"Dragon flag négatifs", "Good morning", "L-sit progression"}


def test_aucun_nouvel_exercice_sans_fiche_dans_les_programmes_tout_faits():
    """Un programme d'inscription qui cite un exercice inconnu donne des
    cartes sans illustration ni conseils dès la première séance."""
    perdus = {n for n in _programmes_tout_faits()
              if not n.startswith("CARDIO") and not resoudre(n)[0]}
    nouveaux = perdus - SANS_FICHE_CONNUS
    assert not nouveaux, f"sans fiche et pas encore recensés : {sorted(nouveaux)}"


def test_la_liste_des_exercices_sans_fiche_ne_ment_pas():
    """Si l'un d'eux reçoit enfin sa fiche, il doit sortir de la liste —
    sinon elle se fossilise et on ne sait plus ce qui reste à faire."""
    perdus = {n for n in _programmes_tout_faits()
              if not n.startswith("CARDIO") and not resoudre(n)[0]}
    regles = SANS_FICHE_CONNUS - perdus
    assert not regles, f"ont une fiche désormais, à retirer de la liste : {sorted(regles)}"


def test_la_bibliotheque_ne_propose_pas_deux_fois_le_meme_exercice():
    """Deux entrées qui mènent à la même fiche font hésiter pour rien."""
    par_groupe = {}
    for groupe, nom in _bibliotheque():
        par_groupe.setdefault(groupe, []).append(nom)
    doublons = {g: n for g, n in par_groupe.items() if len(set(n)) != len(n)}
    assert not doublons, doublons


def test_une_abduction_de_hanche_nest_pas_une_elevation_laterale():
    """« Élévation latérale jambe » se résolvait vers les élévations
    latérales d'ÉPAULES : les mots se ressemblent, pas les exercices.
    C'est le genre de rapprochement que le flou rend possible."""
    noms = [n for _, n in _bibliotheque()]
    assert "Élévation latérale jambe" not in noms
    for nom in noms:
        if "abduction" in nom.casefold() or "hanche" in nom.casefold():
            cle = resoudre(nom)[0]
            assert cle != "Élévations latérales", f"{nom} -> {cle}"


def test_les_noms_absorbes_ne_sont_plus_au_catalogue():
    """Ils restent dans le fichier source pour documenter la fusion, mais
    ne doivent plus être servis : sinon le sélecteur les reproposerait."""
    presents = [n for n in _ABSORBES if n in EXERCISES_INFO]
    assert not presents, presents
