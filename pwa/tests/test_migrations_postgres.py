"""Les migrations du dépôt, rejouées sur un vrai PostgreSQL.

Audit du 06/10 (I-4, 4.1-7) : la fausse base des tests ne connaît que ce
qu'on lui dit. La v29 est restée des mois hors de la production, et rien ne
prouvait qu'enchaîner les fichiers SQL du dépôt redonnait la base que le
code attend. Ici, sur une base neuve :

- le socle (v00) puis chaque migration, dans l'ordre, sans erreur ;
- une seconde fois : chacune doit pouvoir se rejouer sans rien casser ;
- chaque colonne que le code lit (core/schema.ATTENDU) existe ;
- une inscription crée encore profil et programme, v48 comprise.

Lancé quand PG_TEST_URL désigne un serveur PostgreSQL (la CI en démarre
un) ; ignoré sinon. Exemple :
PG_TEST_URL=postgresql://postgres:postgres@localhost:5432/postgres
"""
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import pytest

URL = os.getenv("PG_TEST_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="PG_TEST_URL absent : pas de PostgreSQL")

PWA = Path(__file__).resolve().parents[1]
PRELUDE = PWA / "tests" / "sql" / "supabase_minimal.sql"


def _numero(chemin: Path) -> int:
    return int(re.match(r"supabase_schema_v(\d+)", chemin.name).group(1))


MIGRATIONS = sorted(PWA.glob("supabase_schema_v*.sql"), key=_numero)


def _psql(url, sql=None, fichier=None) -> str:
    cmd = ["psql", url, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"]
    cmd += ["-f", str(fichier)] if fichier else ["-c", sql]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f"{fichier.name if fichier else sql}\n{r.stderr}")
    return r.stdout.strip()


@pytest.fixture(scope="module")
def base():
    """Une base neuve, le décor Supabase minimal, puis toutes les migrations."""
    nom = f"migrations_{os.getpid()}"
    _psql(URL, f"drop database if exists {nom}")
    _psql(URL, f"create database {nom}")
    url = urlparse(URL)._replace(path=f"/{nom}").geturl()
    _psql(url, fichier=PRELUDE)
    for m in MIGRATIONS:
        _psql(url, fichier=m)
    yield url
    _psql(URL, f"drop database if exists {nom}")


def test_les_numeros_de_migration_sont_uniques():
    numeros = [_numero(m) for m in MIGRATIONS]
    assert len(numeros) == len(set(numeros)), numeros
    assert numeros[0] == 0 and numeros[-1] >= 48


def test_chaque_migration_se_rejoue_sans_rien_casser(base):
    for m in MIGRATIONS:
        _psql(base, fichier=m)


def test_chaque_colonne_lue_par_le_code_existe(base):
    from core.schema import ATTENDU
    lignes = _psql(base, "select table_name || '.' || column_name from information_schema.columns "
                         "where table_schema = 'public'")
    presentes = set(lignes.splitlines())
    manquent = [f"{t}.{c}" for t, cols in ATTENDU.items() for c in cols if f"{t}.{c}" not in presentes]
    assert manquent == [], manquent


def test_une_inscription_cree_profil_et_programme_v48_comprise(base):
    """Supabase insère le compte sous le rôle supabase_auth_admin ; la v48 lui
    a retiré, comme à tous, le droit d'appeler handle_new_user. PostgreSQL ne
    vérifie ce droit qu'à la création du déclencheur : l'inscription marche."""
    uid = _psql(base, "set role supabase_auth_admin; "
                      "insert into auth.users (email) values ('nouveau@exemple.fr') returning id")
    uid = uid.splitlines()[-1]
    assert _psql(base, f"select tier from public.profiles where id = '{uid}'") == "free"
    assert _psql(base, f"select data::text from public.programs where user_id = '{uid}'") == "{}"


def test_personne_ne_peut_appeler_la_fonction_dinscription(base):
    for role in ("anon", "authenticated", "public"):
        assert _psql(base, f"select has_function_privilege('{role}', "
                           "'public.handle_new_user()', 'execute')") == "f", role
