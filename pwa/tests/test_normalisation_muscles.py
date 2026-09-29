"""Corriger le muscle de chaque ligne d'historique, une fois par exercice.

`_normalize_hist` tourne sur l'accueil et sur chaque écran de séance, sur
**tout** l'historique. `fix_muscle` peut passer une soixantaine de règles de
mots-clés sur le nom de l'exercice ; le refaire à chaque ligne, c'est des
dizaines de milliers de comparaisons pour une vingtaine de réponses.

Mesuré : **68 ms pour 1 872 lignes, 196 ms pour 5 000**. Et ce coût grandit
avec l'historique — chaque séance faite alourdit chaque affichage, pour
toujours. Avec la mémoïsation : 1,2 ms et 2,3 ms.

Elle existait aussi **en double** : `routes/accueil.py` en avait sa propre
copie, qui avait divergé sur le traitement d'un muscle vide.
"""
import re
from pathlib import Path

import pytest

from core.seance_semaine import _normalize_hist

RACINE = Path(__file__).resolve().parent.parent
PROG = {"Push": [{"name": "Développé couché", "muscle": "Pecs"}], "_settings": {}}


def _lignes(n, exos=20):
    return [{"Exercice": f"Exercice {i % exos}", "Muscle": "" if i % 3 else "Dos"}
            for i in range(n)]


# ── Le résultat ne change pas ────────────────────────────────────────────

def test_le_muscle_du_programme_gagne_sur_celui_de_la_ligne():
    rows = [{"Exercice": "Développé couché", "Muscle": "Autre"}]
    _normalize_hist(rows, PROG)
    assert rows[0]["Muscle"] == "Pecs"


def test_un_muscle_vide_dans_le_programme_neffface_pas_celui_de_la_ligne():
    """La divergence entre les deux copies portait exactement là-dessus.

    Un exercice du programme sans muscle renseigné ne doit pas écraser ce que
    l'historique avait noté : c'est une information, pas du bruit.
    """
    prog = {"Push": [{"name": "Curl biceps", "muscle": ""}], "_settings": {}}
    rows = [{"Exercice": "Curl biceps", "Muscle": "Avant-bras"}]
    _normalize_hist(rows, prog)
    # « Avant-bras » est ce que la ligne portait. La déduction par le nom
    # donnerait « Biceps » : les deux chemins se distinguent donc vraiment.
    assert rows[0]["Muscle"] == "Avant-bras"


def test_une_ligne_sans_muscle_se_deduit_du_nom():
    rows = [{"Exercice": "Curl biceps", "Muscle": ""}]
    _normalize_hist(rows, {"_settings": {}})
    assert "Biceps" in rows[0]["Muscle"]


def test_deux_lignes_du_meme_exo_avec_des_muscles_differents():
    """La mémoire porte sur (exercice, muscle noté), pas sur l'exercice seul.

    `fix_muscle` ne recalcule que si la valeur existante est vide ou héritée :
    deux lignes du même exercice peuvent donc donner deux résultats, et une
    mémoire trop large les confondrait.
    """
    # « Avant-bras » est gardé tel quel ; le vide se déduit en « Biceps ».
    # Deux réponses différentes pour le même exercice : une mémoire qui ne
    # retiendrait que le nom donnerait deux fois la première.
    rows = [{"Exercice": "Curl biceps", "Muscle": "Avant-bras"},
            {"Exercice": "Curl biceps", "Muscle": ""}]
    _normalize_hist(rows, {"_settings": {}})
    assert rows[0]["Muscle"] == "Avant-bras"
    assert rows[1]["Muscle"] == "Biceps"


def test_les_seances_du_programme_sont_bien_rendues():
    rows = []
    _, seances = _normalize_hist(rows, PROG)
    assert list(seances) == ["Push"]  # `_settings` est exclu


# ── Le coût ne grandit plus avec l'historique ────────────────────────────

def test_le_muscle_nest_deduit_quune_fois_par_exercice(monkeypatch):
    """La garantie, énoncée en nombre d'appels plutôt qu'en millisecondes.

    Un test chronométré serait à la merci de la machine ; celui-ci mesure
    exactement ce qui coûte, et il tombe si la mémoïsation saute.
    """
    import core.seance_semaine as mod
    appels = []
    vrai = mod.fix_muscle

    def compte(exercice, muscle):
        appels.append((exercice, muscle))
        return vrai(exercice, muscle)

    monkeypatch.setattr(mod, "fix_muscle", compte)
    rows = _lignes(2000, exos=20)
    _normalize_hist(rows, PROG)
    assert len(appels) == len(set(appels)), "une combinaison a été recalculée"
    assert len(appels) <= 40, (
        f"{len(appels)} déductions pour 20 exercices × 2 muscles : "
        "la mémoïsation ne prend pas")


def test_le_cout_ne_suit_pas_le_nombre_de_lignes(monkeypatch):
    """Dix fois plus d'historique ne doit pas coûter dix fois plus."""
    import core.seance_semaine as mod
    vrai = mod.fix_muscle

    def mesurer(n):
        appels = []
        monkeypatch.setattr(mod, "fix_muscle",
                            lambda e, m: (appels.append(1), vrai(e, m))[1])
        _normalize_hist(_lignes(n, exos=15), PROG)
        return len(appels)

    assert mesurer(5000) == mesurer(500), (
        "le nombre de déductions doit dépendre des exercices distincts, "
        "pas du nombre de lignes")


# ── Une seule copie ──────────────────────────────────────────────────────

def test_personne_ne_redefinit_la_normalisation():
    """`routes/accueil.py` en avait une deuxième, qui avait divergé."""
    coupables = []
    for dossier in ("routes", "core"):
        for f in (RACINE / dossier).glob("*.py"):
            if f.name == "seance_semaine.py":
                continue
            if re.search(r"^def _normalize_hist", f.read_text(encoding="utf-8"), re.M):
                coupables.append(f"{dossier}/{f.name}")
    assert coupables == [], "normalisation redéfinie dans " + ", ".join(coupables)
