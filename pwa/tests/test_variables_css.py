"""Une variable CSS qui n'existe pas ne dessine rien, et ne dit rien.

`border: 0.5px solid var(--border-subtle)` avec un token non défini ne produit
pas une bordure par défaut : la déclaration entière devient invalide et il n'y
a **aucune** bordure. Le navigateur ne prévient pas, rien ne casse, la page
s'affiche simplement plus plate que ce que le code décrit.

C'est le cas de `--border-subtle` : écrit 18 fois dans six gabarits, défini
nulle part. Sur la seule page /programme, cela fait 244 bordures demandées et
jamais dessinées (mesuré dans le navigateur).

`var(--x, repli)` ne pose pas ce problème : le repli s'applique. Le test ne
signale donc que les références **sans repli**.

La liste fige l'existant au lieu d'exiger zéro : c'est un reste à payer, pas
un feu vert pour en ajouter.
"""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CSS = RACINE / "static" / "css"
GABARITS = RACINE / "templates"

# Tokens référencés sans définition ET sans repli : autant de règles mortes.
# À vider, pas à allonger.
MANQUANTS_CONNUS = {"--border-subtle"}

# Posés par du JavaScript à l'exécution : introuvables dans les sources.
POSES_EN_JS = {"--dx", "--ad-banner-h", "--vh"}


def _fichiers():
    return list(CSS.glob("*.css")) + list(GABARITS.glob("*.html"))


def _definis():
    """Les tokens déclarés — en feuille de style comme en `<style>` de gabarit."""
    tokens = set()
    for f in _fichiers():
        tokens |= set(re.findall(r"(--[\w-]+)\s*:", f.read_text(encoding="utf-8")))
    return tokens


def _sans_repli():
    """Chaque `var(--x)` écrit sans valeur de repli, et où il est."""
    trouves = {}
    for f in _fichiers():
        for nom in re.findall(r"var\(\s*(--[\w-]+)\s*\)", f.read_text(encoding="utf-8")):
            trouves.setdefault(nom, set()).add(f.name)
    return trouves


def _morts():
    definis = _definis()
    return {n: ou for n, ou in _sans_repli().items()
            if n not in definis and n not in POSES_EN_JS}


def test_aucun_nouveau_token_mort():
    """Un `var(--x)` sans définition ni repli est une règle qui ne s'applique pas."""
    morts = _morts()
    nouveaux = set(morts) - MANQUANTS_CONNUS
    assert nouveaux == set(), (
        "token CSS référencé sans être défini ni avoir de repli : "
        + "; ".join(f"{n} ({', '.join(sorted(morts[n]))})" for n in sorted(nouveaux)))


def test_la_liste_ne_se_desserre_pas():
    """Un token enfin défini doit sortir de la liste, sinon elle ne protège plus."""
    regles = MANQUANTS_CONNUS - set(_morts())
    assert regles == set(), (
        "ces tokens sont définis maintenant, retire-les de MANQUANTS_CONNUS : "
        + ", ".join(sorted(regles)))


def test_les_replis_restent_la_regle():
    """Un `var()` sur un token non garanti doit porter un repli.

    Quatre tokens (`--bg-input`, `--sp-2`, `--sp-3`, `--border-strong`) ne sont
    définis nulle part non plus, mais chacun de leurs usages porte une valeur
    de repli : ils s'affichent correctement. Ce test garde la trace de ce
    choix pour qu'on ne le défasse pas par inadvertance.
    """
    definis = _definis()
    avec_repli = set()
    for f in _fichiers():
        for nom in re.findall(r"var\(\s*(--[\w-]+)\s*,", f.read_text(encoding="utf-8")):
            if nom not in definis and nom not in POSES_EN_JS:
                avec_repli.add(nom)
    assert {"--bg-input", "--sp-2", "--sp-3", "--border-strong"} <= avec_repli
