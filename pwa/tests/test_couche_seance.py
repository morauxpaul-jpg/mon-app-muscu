"""Le calcul de la séance est sorti des routes, et doit y rester.

`routes/seance.py` faisait 1 685 lignes. Les deux tiers ne touchaient ni à
Flask ni à la base : ils prenaient l'historique et le programme, et rendaient
des dictionnaires. C'était du calcul rangé dans la couche HTTP — impossible à
exercer sans monter une requête, et invisible depuis le reste de l'app, au
point que `routes/accueil.py` importait `_display_week` depuis `routes/`.

Ces 36 fonctions vivent maintenant dans six modules `core/seance_*.py`. Les
tests ci-dessous tiennent la frontière :

1. ces modules restent purs — ni Flask, ni `core.data`, ni `core.db` ;
2. leurs dépendances restent un arbre ;
3. la couche HTTP ne regrossit pas jusqu'à réabsorber le calcul.

Le dernier test est un cliquet et non une correction : les routes qui
s'importent entre elles sont une dette mesurée, pas encore payée.
"""
import ast
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
CORE = RACINE / "core"
ROUTES = RACINE / "routes"
PLAFOND_MODULE = 250   # lignes par module de calcul
PLAFOND_ROUTES = 1000  # lignes pour la couche HTTP de la séance

# Ce qu'un module de calcul n'a pas le droit de connaître.
INTERDITS = (
    (r"\bfrom flask\b|\bimport flask\b", "flask"),
    (r"\bfrom core\.data\b", "core.data"),
    (r"\bfrom core\.db\b|\bfrom core import db\b", "core.db"),
    (r"\bfrom core\.limiter\b", "core.limiter"),
)


def _modules():
    return sorted(p.stem for p in CORE.glob("seance_*.py"))


def test_les_six_modules_existent():
    assert _modules() == ["seance_calques", "seance_cardio", "seance_contexte",
                          "seance_historique", "seance_saisie", "seance_semaine"]


@pytest.mark.parametrize("module", _modules())
def test_un_module_de_calcul_ne_connait_ni_flask_ni_la_base(module):
    """Ce sont des fonctions, pas des bouts de requête.

    Un `from flask import g` suffirait à les rendre inexerçables hors d'une
    requête — et c'est exactement ce qui les avait retenues dans `routes/`.
    """
    src = (CORE / f"{module}.py").read_text(encoding="utf-8")
    fautes = [nom for motif, nom in INTERDITS if re.search(motif, src)]
    assert fautes == [], f"core/{module}.py importe {', '.join(fautes)}"


def test_les_dependances_forment_un_arbre():
    """Aucun cycle entre les six modules."""
    voisins = {m: set(re.findall(r"from core\.(seance_\w+) import",
                                 (CORE / f"{m}.py").read_text(encoding="utf-8")))
               for m in _modules()}
    chemin, vus = [], set()

    def descendre(n):
        if n in chemin:
            pytest.fail("cycle : " + " → ".join(chemin[chemin.index(n):] + [n]))
        if n in vus:
            return
        chemin.append(n)
        for v in sorted(voisins.get(n, ())):
            descendre(v)
        chemin.pop()
        vus.add(n)

    for m in _modules():
        descendre(m)


def test_aucun_module_de_calcul_ne_depasse_le_plafond():
    gros = {m: len((CORE / f"{m}.py").read_text(encoding="utf-8").splitlines())
            for m in _modules()}
    depassent = {m: n for m, n in gros.items() if n > PLAFOND_MODULE}
    assert depassent == {}, f"au-delà de {PLAFOND_MODULE} lignes : {depassent}"


def test_la_couche_http_ne_regrossit_pas():
    n = len((ROUTES / "seance.py").read_text(encoding="utf-8").splitlines())
    assert n <= PLAFOND_ROUTES, (
        f"routes/seance.py est remonté à {n} lignes : du calcul y est "
        f"probablement revenu, il a sa place dans core/seance_*.py")


def test_la_couche_http_ne_garde_que_des_routes():
    """Les fonctions restantes servent une requête, ou en préparent une.

    Une fonction sans décorateur qui ne touche ni à `request`, ni à `g`, ni à
    la base, ni au rendu est du calcul : elle appartient à `core/`.
    """
    src = (ROUTES / "seance.py").read_text(encoding="utf-8")
    lignes = src.split("\n")
    http = re.compile(r"\brequest\b|getattr\(\s*g\s*,|\bg\.\w+|\bsession\b|"
                      r"render_template|redirect|url_for|jsonify|abort|"
                      r"get_hist\(\)|get_prog\(\)|save_prog\(|from core\.data import")
    intrus = []
    for n in ast.parse(src).body:
        if not isinstance(n, ast.FunctionDef) or n.decorator_list:
            continue
        corps = "\n".join(lignes[n.lineno - 1:n.end_lineno])
        if not http.search(corps):
            intrus.append(n.name)
    assert intrus == [], f"calcul resté dans routes/seance.py : {intrus}"


# ── Cliquet : les routes qui s'importent entre elles ─────────────────────

# Mesuré, pas choisi. `routes/cardio.py` est cité par quatre autres routes :
# c'est un module de calcul qui porte un chapeau de blueprint. Tant qu'il n'a
# pas déménagé dans `core/`, cette liste empêche au moins la dette de grossir.
IMPORTS_ENTRE_ROUTES = {
    ("accueil", "cardio"),
    ("generator", "cardio"),
    ("gestion", "programme"),
    ("onboarding", "parrainage"),
    ("premium", "billing"),
    ("programme", "generator"),
    ("progres", "cardio"),
    ("progres", "nutrition"),
    ("seance", "cardio"),
}


def test_les_routes_ne_simportent_pas_davantage_entre_elles():
    """Un blueprint qui en importe un autre est un module de calcul déguisé.

    Le test ne corrige rien : il fige l'existant pour qu'une dixième
    dépendance ne passe pas inaperçue.
    """
    trouves = set()
    for chemin in ROUTES.glob("*.py"):
        src = chemin.read_text(encoding="utf-8")
        for cible in re.findall(r"from routes\.(\w+) import|import routes\.(\w+)", src):
            nom = cible[0] or cible[1]
            if nom != chemin.stem:
                trouves.add((chemin.stem, nom))
    nouveaux = trouves - IMPORTS_ENTRE_ROUTES
    assert nouveaux == set(), (
        "nouvelle dépendance entre blueprints : " + ", ".join(
            f"{a} → {b}" for a, b in sorted(nouveaux))
        + " — le code partagé a sa place dans core/")


def test_le_cliquet_reste_serre():
    """Une dépendance supprimée doit sortir de la liste, sinon le cliquet
    se desserre tout seul et cesse de protéger."""
    trouves = set()
    for chemin in ROUTES.glob("*.py"):
        src = chemin.read_text(encoding="utf-8")
        for cible in re.findall(r"from routes\.(\w+) import|import routes\.(\w+)", src):
            nom = cible[0] or cible[1]
            if nom != chemin.stem:
                trouves.add((chemin.stem, nom))
    disparus = IMPORTS_ENTRE_ROUTES - trouves
    assert disparus == set(), (
        "ces dépendances n'existent plus, retire-les de IMPORTS_ENTRE_ROUTES : "
        + ", ".join(f"{a} → {b}" for a, b in sorted(disparus)))
