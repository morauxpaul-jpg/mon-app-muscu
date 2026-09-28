"""L'outil de mesure du blob : il mesure, et il ne fait que ça.

`tools/analyse_blob.py` tourne sur les vraies données de l'utilisateur. Deux
promesses tiennent ce droit d'accès, et deux tests les vérifient :

1. il n'écrit rien — aucun `insert`, `update`, `upsert`, `delete` ;
2. il n'imprime aucun contenu — que des noms de clés, des tailles et des
   comptages, pour que le rapport puisse se coller n'importe où.

Le reste vérifie que les chiffres sont justes, sur des blobs construits ici.
"""
import ast
import datetime as dt
import json
from pathlib import Path

import pytest

from tools.analyse_blob import _dates_du_calque, _octets, analyser, rapport

SOURCE = Path(__file__).resolve().parent.parent / "tools" / "analyse_blob.py"


# ── Les deux promesses ───────────────────────────────────────────────────

def _verbes_postgrest(source: str) -> set:
    """Les méthodes enchaînées après un `.table(…)`, et elles seules.

    On remonte la chaîne d'appels : `sys.path.insert(…)` n'est pas une
    écriture en base, et un test qui les confondrait ne prouverait rien.
    """
    verbes = set()

    def sur_une_table(noeud):
        while isinstance(noeud, (ast.Call, ast.Attribute)):
            if isinstance(noeud, ast.Call):
                noeud = noeud.func
                continue
            if noeud.attr == "table":
                return True
            noeud = noeud.value
        return False

    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if sur_une_table(n.func.value):
                verbes.add(n.func.attr)
    return verbes


def test_loutil_nappelle_aucune_ecriture():
    """Seuls `select` et `execute` sont permis sur une table.

    C'est ce qui rend l'outil sûr à lancer sur des données réelles sans
    sauvegarde préalable. La liste est blanche, pas noire : un verbe
    d'écriture qu'on n'aurait pas pensé à interdire tombe quand même.
    """
    verbes = _verbes_postgrest(SOURCE.read_text(encoding="utf-8"))
    assert verbes <= {"select", "execute", "eq", "order", "limit", "range"}, (
        f"verbe PostgREST inattendu : {sorted(verbes - {chr(115)})}")


def test_la_detection_decriture_fonctionne():
    """Le test ci-dessus doit voir une écriture s'il y en avait une.

    Sans cette vérification, une chaîne d'appels un peu différente le rendrait
    aveugle sans que rien ne le dise.
    """
    assert "insert" in _verbes_postgrest(
        "client.table('programs').insert({'a': 1}).execute()")
    assert "update" in _verbes_postgrest(
        "get_client().table('programs').update(x).eq('id', u).execute()")
    # Et il ne confond pas avec une liste Python.
    assert _verbes_postgrest("import sys" + chr(10) + "sys.path.insert(0, '.')") == set()


def test_le_rapport_nimprime_aucun_contenu():
    """Un rapport doit être collable dans une conversation sans y penser."""
    # Des valeurs ET des clés : un nom de séance ou d'exercice est du contenu,
    # qu'il soit rangé à gauche ou à droite des deux-points.
    secrets = ["Développé couché", "moraux.paul@gmail.com", "u-secret-0001",
               "j'ai mal au dos", "Curl marteau", "Ma séance secrète", "curl biceps"]
    blob = {
        "Push": [{"name": secrets[0], "sets": 3, "muscle": "Pecs"}],
        secrets[5]: [{"name": secrets[0], "sets": 3}],
        "_session_notes": {f"{secrets[5]}|2026-09-14": {"rating": 5,
                                                        "comment": secrets[3]}},
        "_substituts": {"Push|2026-09-14": {secrets[6]: secrets[4]}},
        "_email": secrets[1], "_uid": secrets[2],
    }
    texte = rapport(analyser([blob]))
    fuites = [s for s in secrets if s in texte]
    assert fuites == [], f"le rapport contient du contenu : {fuites}"
    # Et il nomme bien les clés, sinon il ne servirait à rien.
    assert "_session_notes" in texte and "_substituts" in texte


# ── Les chiffres ─────────────────────────────────────────────────────────

def test_le_poids_est_celui_qui_part_en_base():
    """Mesuré en octets UTF-8 du JSON compact, pas en caractères.

    « é » compte pour deux octets : un rapport en caractères sous-estimerait
    un blob français d'environ 5 %.
    """
    assert _octets({"a": "é"}) == len(json.dumps({"a": "é"}, ensure_ascii=False,
                                                 separators=(",", ":")).encode("utf-8"))
    assert _octets({"a": "é"}) > len(str({"a": "é"})) - 6


def test_les_seances_ne_comptent_pas_comme_des_calques():
    """Le programme lui-même est rangé à part : ce n'est pas de la dette."""
    m = analyser([{"Push": [{"name": "Squat"}], "_settings": {"x": 1}}])
    assert "Push" not in m["par_cle"]
    assert "_settings" in m["par_cle"]
    assert m["seances"] > 0


def test_les_entrees_de_calque_sont_comptees_et_datees():
    blob = {"_seance_order": {
        "Push|2026-09-14": ["A"], "Pull|2026-01-02": ["B"], "sans-date": ["C"]}}
    m = analyser([blob])
    assert m["entrees_calque"]["_seance_order"] == 3
    assert m["plus_vieille"]["_seance_order"] == "2026-01-02"


def test_plusieurs_programmes_sadditionnent_et_le_max_est_le_pire():
    petit = {"_archive": {"a": 1}}
    gros = {"_archive": {str(i): "x" * 50 for i in range(20)}}
    m = analyser([petit, gros])
    assert m["programmes"] == 2
    assert m["par_cle"]["_archive"]["comptes"] == 2
    assert m["par_cle"]["_archive"]["max"] == _octets(gros["_archive"])
    assert m["par_cle"]["_archive"]["total"] == (
        _octets(petit["_archive"]) + _octets(gros["_archive"]))


def test_une_cle_absente_chez_un_utilisateur_ne_le_penalise_pas():
    m = analyser([{"_badges": ["a"]}, {}])
    assert m["par_cle"]["_badges"]["comptes"] == 1


@pytest.mark.parametrize("entree", [None, [], "texte", 42])
def test_un_blob_inattendu_ne_fait_pas_tomber_loutil(entree):
    """La base peut contenir un `data` null ou malformé : on l'ignore."""
    m = analyser([entree, {"_settings": {}}])
    assert m["programmes"] == 2
    assert "_settings" in m["par_cle"]


def test_les_dates_malformees_sont_ecartees():
    assert _dates_du_calque({"a|2026-09-14": 1, "b|hier": 1, "c": 1}) == ["2026-09-14"]
    assert _dates_du_calque("pas un dict") == []


def test_le_rapport_tient_sans_aucun_calque():
    texte = rapport(analyser([{"_settings": {"a": 1}}]))
    assert "_settings" in texte
    assert "1 programme(s)" in texte
