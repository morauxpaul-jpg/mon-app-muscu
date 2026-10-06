"""La couche données reste découpée, et sa façade reste complète.

`core/db.py` faisait 1 705 lignes et mélangeait dix sujets : l'historique des
séries, le blob du programme, le profil, les repas, Stripe, le parrainage, les
notifications, le coach, la console admin et les bilans. Elle est maintenant
répartie en modules `core/db_*.py` et `core/db.py` n'est plus qu'une carte.

Ces tests protègent les trois propriétés qui rendent le découpage utile :

1. la façade expose tout ce que les modules définissent — sinon une fonction
   ajoutée dans un module resterait invisible pour les routes ;
2. les dépendances restent un arbre — un cycle rendrait l'ordre d'import
   fragile et ramènerait tout le monde dans un seul fichier ;
3. le client Supabase reste unique et substituable — c'est ce qui permet aux
   tests de brancher une fausse base sur les dix modules d'un coup.
"""
import ast
import importlib
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "core"
PLAFOND = 400  # lignes : au-delà, un module porte plus d'un sujet

# Le seul nom volontairement absent de la façade. Le réexporter créerait un
# piège : `core.db._client` serait une copie du lien, figée à None, et une
# affectation dessus n'aurait aucun effet sur `get_client()`. `use_client()`
# et `current_client()` sont le chemin, et une lecture directe doit échouer.
# `_absente_depuis` : un horodatage que le module réaffecte ; réexporté, la
# façade en garderait une copie figée qui mentirait.
HORS_FACADE = {"db_base._client", "db_reglages._absente_depuis", "db_calques._absente_depuis"}


def _modules():
    return sorted(p.stem for p in DOSSIER.glob("db_*.py"))


def _noms_publics(chemin: Path) -> set:
    """Les noms définis au premier niveau, privés compris (la façade les
    réexporte aussi : des tests s'appuient dessus)."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    noms = set()
    for n in arbre.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            noms.add(n.name)
        elif isinstance(n, ast.Assign):
            noms |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            noms.add(n.target.id)
    return {n for n in noms if n != "logger"}


def test_la_facade_reexporte_tout():
    """Rien de ce que définit un module ne manque à `core.db`.

    C'est le test qui compte : sans lui, découper revient à cacher du code.
    """
    db = importlib.import_module("core.db")
    oublis = []
    for mod in _modules():
        for nom in _noms_publics(DOSSIER / f"{mod}.py"):
            if not hasattr(db, nom) and f"{mod}.{nom}" not in HORS_FACADE:
                oublis.append(f"{mod}.{nom}")
    assert oublis == [], "absents de core.db : " + ", ".join(sorted(oublis))
    # L'exception doit rester une exception : si `_client` réapparaissait dans
    # la façade, la ligne ci-dessus cesserait de le voir sans rien dire.
    for nom in HORS_FACADE:
        assert not hasattr(db, nom.split(".", 1)[1]), f"{nom} ne doit pas être réexporté"


def test_la_facade_ne_contient_pas_de_code():
    """`core/db.py` est une carte : docstring, commentaires et imports.

    Une fonction posée là recommencerait le fichier de 1 700 lignes.
    """
    arbre = ast.parse((DOSSIER / "db.py").read_text(encoding="utf-8"))
    intrus = [type(n).__name__ for n in arbre.body
              if not isinstance(n, (ast.Import, ast.ImportFrom, ast.Expr))]
    assert intrus == [], f"core/db.py contient du code : {intrus}"


def test_aucun_module_ne_depasse_le_plafond():
    """Un module qui grossit trop a recommencé à porter plusieurs sujets."""
    gros = {m: len((DOSSIER / f"{m}.py").read_text(encoding="utf-8").splitlines())
            for m in _modules()}
    depassent = {m: n for m, n in gros.items() if n > PLAFOND}
    assert depassent == {}, f"au-delà de {PLAFOND} lignes : {depassent}"


def test_les_dependances_forment_un_arbre():
    """Aucun cycle entre les modules de la couche données."""
    voisins = {}
    for m in _modules():
        src = (DOSSIER / f"{m}.py").read_text(encoding="utf-8")
        voisins[m] = {c for c in re.findall(r"from core\.(db_\w+) import", src)} | \
                     {c for c in re.findall(r"^from core import (db_\w+)$", src, re.M)}

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
    assert voisins["db_base"] == set(), "db_base est le socle : il ne dépend de personne"


def test_personne_ne_construit_son_client():
    """`get_client()` de `db_base` est le seul chemin vers Supabase.

    Un module qui appellerait `create_client` lui-même échapperait à la fausse
    base des tests — et à la substitution par `use_client()`.
    """
    coupables = [m for m in _modules() if m != "db_base"
                 and "create_client" in (DOSSIER / f"{m}.py").read_text(encoding="utf-8")]
    assert coupables == []


def test_le_faux_client_atteint_tous_les_modules(fake_db):
    """La fausse base branchée par `use_client()` est vue partout.

    Si un module capturait le client au moment de l'import, il parlerait à la
    vraie base pendant les tests. Ce test l'attrape.
    """
    for m in _modules():
        mod = importlib.import_module(f"core.{m}")
        obtenir = getattr(mod, "get_client", None)
        if obtenir is not None:
            assert obtenir() is fake_db, f"{m} ne voit pas la fausse base"


def test_chaque_module_est_cite_dans_la_carte():
    """La carte en tête de `core/db.py` nomme les dix modules.

    Une carte incomplète est pire que pas de carte : elle fait croire au
    lecteur qu'il a tout vu.
    """
    doc = ast.get_docstring(ast.parse((DOSSIER / "db.py").read_text(encoding="utf-8"))) or ""
    absents = [m for m in _modules() if m not in doc]
    assert absents == [], f"pas dans la carte de core/db.py : {absents}"
