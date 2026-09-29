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

from conftest import USER_ID
from core.blob_stats import (_dates_du_calque, _octets, analyser,
                             analyser_historique, rapport)

RACINE = Path(__file__).resolve().parent.parent

# Le chemin de mesure, de bout en bout. Deux entrées (la ligne de commande et
# la page admin), une seule lecture, et le calcul qui ne touche pas à la base.
SANS_BASE = (RACINE / "tools" / "analyse_blob.py",
             RACINE / "core" / "blob_stats.py")
# (fichier, fonction) : les deux seuls endroits où la mesure parle à Supabase.
QUI_LIT = ((RACINE / "core" / "db_programme.py", "list_all_program_blobs"),
           (RACINE / "core" / "db_historique.py", "list_history_shape"),
           (RACINE / "routes" / "admin.py", "blob"))


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


PERMIS = {"select", "execute", "eq", "order", "limit", "range"}


def _source_de(chemin: Path, nom: str) -> str:
    """Le texte d'UNE fonction. `core/db_programme.py` contient des écritures
    légitimes ailleurs : scanner le fichier entier ne prouverait rien."""
    texte = chemin.read_text(encoding="utf-8")
    lignes = texte.split(chr(10))
    for n in ast.walk(ast.parse(texte)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom:
            return chr(10).join(lignes[n.lineno - 1:n.end_lineno])
    raise AssertionError(f"{nom} introuvable dans {chemin.name}")


def test_la_mesure_nappelle_aucune_ecriture():
    """Seule la lecture est permise sur le chemin de mesure.

    C'est ce qui rend l'outil sûr à lancer sur des données réelles sans
    sauvegarde préalable. La liste est BLANCHE, pas noire : un verbe
    d'écriture qu'on n'aurait pas pensé à interdire tombe quand même.
    """
    for chemin, nom in QUI_LIT:
        verbes = _verbes_postgrest(_source_de(chemin, nom))
        assert verbes <= PERMIS, (
            f"{chemin.name}:{nom} : verbe PostgREST inattendu "
            f"{sorted(verbes - PERMIS)}")


def test_le_calcul_ne_touche_pas_a_la_base():
    """La mesure et la CLI ne parlent à aucune table.

    Toute la lecture passe par `list_all_program_blobs`, donc par la couche
    données. Sans ça, il y aurait deux façons de lire les programmes, et le
    test ci-dessus n'en surveillerait qu'une.
    """
    for chemin in SANS_BASE:
        verbes = _verbes_postgrest(chemin.read_text(encoding="utf-8"))
        assert verbes == set(), f"{chemin.name} parle à une table : {sorted(verbes)}"


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


# ── La page /admin/blob ──────────────────────────────────────────────────

def test_la_page_est_invisible_sans_droits_admin(fake_db, logged_in):
    """404, pas 403 : la page ne doit pas révéler qu'elle existe."""
    assert logged_in.get("/admin/blob").status_code == 404


def test_la_page_rend_le_rapport_a_ladmin(fake_db, logged_in, monkeypatch):
    """Elle existe pour que la mesure se fasse là où vit la clé `service_role`.

    Rapatrier la clé pour lancer la CLI en local serait exactement ce qu'on
    cherche à éviter.
    """
    monkeypatch.setenv("ADMIN_EMAILS", "test@example.com")
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Ma séance secrète": [{"name": "Développé couché", "sets": 3}],
        "_seance_order": {"Ma séance secrète|2026-09-14": ["Développé couché"]},
    }}).execute()

    r = logged_in.get("/admin/blob")
    assert r.status_code == 200
    assert r.mimetype == "text/plain"
    corps = r.data.decode("utf-8")
    assert "_seance_order" in corps and "1 entrees" in corps
    # La promesse tient aussi par HTTP, pas seulement en appelant `rapport()`.
    for secret in ("Ma séance secrète", "Développé couché", USER_ID):
        assert secret not in corps, f"la page laisse fuir : {secret}"


def test_la_page_le_dit_quand_il_ny_a_rien(fake_db, logged_in, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "test@example.com")
    r = logged_in.get("/admin/blob")
    assert r.status_code == 200
    assert "Aucun programme" in r.data.decode("utf-8")


# ── La mesure de l'historique ────────────────────────────────────────────

def test_lhistorique_est_compte_par_utilisateur():
    # Le plus GROS compte est le plus RÉCENT : sans ça, prendre la plus vieille
    # date toutes lignes confondues donnerait la même réponse par hasard.
    lignes = [{"user_id": "a", "date": "2026-05-01"},
              {"user_id": "a", "date": "2026-07-02"},
              {"user_id": "b", "date": "2026-01-01"}]
    m = analyser_historique(lignes)
    assert m["lignes"] == 3 and m["comptes"] == 2
    assert m["pire"] == 2
    assert m["depuis"] == "2026-05-01", "la date doit être celle du PLUS GROS compte"


def test_le_nombre_de_pages_est_celui_de_postgrest():
    """C'est le chiffre qui décide : chaque page est un aller-retour réseau."""
    from core.blob_stats import PAGE_POSTGREST
    for n, pages in ((1, 1), (PAGE_POSTGREST, 1), (PAGE_POSTGREST + 1, 2),
                     (3 * PAGE_POSTGREST, 3)):
        m = analyser_historique([{"user_id": "a", "date": "2026-01-01"}] * n)
        assert m["pages_pire"] == pages, f"{n} lignes devraient faire {pages} page(s)"


def test_un_historique_vide_ne_fait_pas_tomber_la_page():
    m = analyser_historique([])
    assert m["lignes"] == 0 and m["pages_pire"] == 0
    assert "HISTORIQUE" not in rapport(analyser([{"_settings": {}}]), m)


def test_le_rapport_montre_lhistorique_quand_il_y_en_a():
    m = analyser_historique([{"user_id": "a", "date": "2026-01-05"}] * 1500)
    texte = rapport(analyser([{"_settings": {}}]), m)
    assert "HISTORIQUE" in texte and "1500" in texte
    assert "2 requete(s)" in texte


def test_la_mesure_de_lhistorique_ne_lit_que_deux_colonnes():
    """Ni exercice, ni charge, ni remarque : on compte et on date."""
    import ast
    src = (RACINE / "core" / "db_historique.py").read_text(encoding="utf-8")
    fn = _source_de(RACINE / "core" / "db_historique.py", "list_history_shape")
    demandes = [n.args[0].value for n in ast.walk(ast.parse(fn))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "select" and n.args
                and isinstance(n.args[0], ast.Constant)]
    assert demandes == ["user_id,date"], demandes


def test_le_rapport_dhistorique_ne_laisse_rien_fuir():
    """Un identifiant d'utilisateur n'a rien à faire dans un rapport collable."""
    m = analyser_historique([{"user_id": "u-secret-0001", "date": "2026-01-05"}])
    assert "u-secret-0001" not in rapport(analyser([{"_settings": {}}]), m)
