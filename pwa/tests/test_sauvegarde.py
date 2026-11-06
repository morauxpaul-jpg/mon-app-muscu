"""Sauvegarde quotidienne de la base (audit du 04/11, B3).

L'offre Supabase gratuite ne sauvegarde rien. Le workflow
.github/workflows/sauvegarde.yml copie la base chaque nuit avec
tools/sauvegarde_base.py, la restaure sur un PostgreSQL vide, puis range la
copie chiffrée 14 jours. Ici :

- le workflow : chaque nuit, secret désigné par son nom seulement, rien
  d'envoyé avant la restauration d'essai et le chiffrement, 14 jours ;
- le script, sur un vrai PostgreSQL (PG_TEST_URL) : une base au schéma du
  dépôt (socle + toutes les migrations), des comptes et des séries, copiée
  puis restaurée sur une base vide, revient table par table ;
- le chiffrement, avec `age` : seule la clé privée rouvre l'archive.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest

PWA = Path(__file__).resolve().parents[1]
RACINE = PWA.parent
WORKFLOW = RACINE / ".github" / "workflows" / "sauvegarde.yml"
SCRIPT = PWA / "tools" / "sauvegarde_base.py"
sys.path.insert(0, str(PWA / "tools"))

URL = os.getenv("PG_TEST_URL", "")
avec_postgres = pytest.mark.skipif(not URL, reason="PG_TEST_URL absent : pas de PostgreSQL")
# Sur GitHub, `age` est installé par tests.yml : jamais ignoré là-bas.
avec_age = pytest.mark.skipif(not shutil.which("age") and not os.getenv("GITHUB_ACTIONS"),
                              reason="age absent")


def _texte():
    return WORKFLOW.read_text(encoding="utf-8")


def _etapes():
    """Les étapes du workflow, dans l'ordre : (nom, texte de l'étape)."""
    blocs = re.split(r"\n(?=      - )", _texte().split("    steps:", 1)[1])
    return [(re.search(r"(?:name|uses): (.+)", b).group(1).strip(), b) for b in blocs if b.strip()]


# ------------------------------------------------------------- workflow --

def test_le_workflow_tourne_chaque_nuit_et_a_la_demande():
    texte = _texte()
    cron = re.search(r"- cron: '([^']+)'", texte).group(1).split()
    assert cron[2:] == ["*", "*", "*"], cron          # tous les jours
    assert "workflow_dispatch:" in texte              # lancement à la main


SECRETS = {"SUPABASE_DB_URL", "SUPABASE_S3_ID", "SUPABASE_S3_SECRET"}


def test_le_secret_nest_designe_que_par_son_nom():
    texte = _texte()
    assert set(re.findall(r"secrets\.(\w+)", texte)) == SECRETS
    # Aucune adresse de BASE (elle contient le mot de passe) ; seule l'adresse
    # publique du stockage, sans secret, y figure.
    assert "pooler.supabase" not in texte and not re.search(r"db\.\w+\.supabase\.co", texte)
    assert "postgresql://postgres." not in texte
    # Seulement passé en variable d'environnement, jamais recopié dans une
    # commande (où il pourrait s'afficher), jamais affiché.
    for ligne in texte.splitlines():
        if "secrets." in ligne:
            assert re.fullmatch(r" +[A-Z_0-9]+: \$\{\{ secrets\.(\w+) \}\}", ligne), ligne
        if "echo" in ligne:
            assert "$SAUVEGARDE_S" not in ligne and "${{ secrets" not in ligne, ligne
            assert "SOURCE" not in ligne and "DB_URL" not in ligne, ligne


def test_rien_ne_part_avant_la_restauration_dessai_et_le_chiffrement():
    noms = [n for n, _ in _etapes()]
    texte = _texte()
    position = {mot: next(i for i, (_, e) in enumerate(_etapes()) if mot in e)
                for mot in ("sauvegarde_base.py copier", "sauvegarde_base.py photos",
                            "sauvegarde_base.py verifier", "sauvegarde_base.py emballer",
                            "actions/upload-artifact", "PHOTOS == 'absentes'")}
    ordre = sorted(position, key=position.get)
    assert ordre == ["sauvegarde_base.py copier", "sauvegarde_base.py photos",
                     "sauvegarde_base.py verifier", "sauvegarde_base.py emballer",
                     "actions/upload-artifact", "PHOTOS == 'absentes'"], noms
    envoi = dict(_etapes())[next(n for n, e in _etapes() if "upload-artifact" in e)]
    assert re.search(r"path: .*\.tar\.age\s*$", envoi, flags=re.M), envoi
    assert "retention-days: 14" in envoi
    assert "if-no-files-found: error" in envoi
    assert "permissions:\n  contents: read" in texte


def test_la_restauration_dessai_vise_un_postgresql_de_la_version_de_production():
    """Production : PostgreSQL 17 (get_project, 05/11/2026). Même image que
    les tests de migrations."""
    image = re.search(r"image: (postgres:\S+)", _texte()).group(1)
    tests = (RACINE / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert image == "postgres:17" and f"image: {image}" in tests
    assert "postgresql-client-17" in _texte()


def test_les_forks_ne_lancent_pas_la_sauvegarde():
    assert "if: github.repository == 'morauxpaul-jpg/mon-app-muscu'" in _texte()


# --------------------------------------------------------------- script --

def test_les_roles_a_recreer_sont_tous_trouves():
    import sauvegarde_base as s
    sql = r'''
ALTER TABLE public.history OWNER TO postgres;
ALTER TABLE auth.users OWNER TO supabase_auth_admin;
GRANT ALL ON TABLE public.history TO service_role;
REVOKE ALL ON FUNCTION public.handle_new_user() FROM PUBLIC;
GRANT SELECT ON TABLE auth.users TO postgres,dashboard_user WITH GRANT OPTION;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO anon;
GRANT USAGE ON SCHEMA public TO "Rôle ""étrange""";
'''
    assert s.roles_cites(sql) == sorted(["Rôle \"étrange\"", "anon", "dashboard_user", "postgres",
                                         "service_role", "supabase_admin", "supabase_auth_admin"])


@pytest.mark.parametrize("cible", [
    "postgresql://postgres:x@db.pagrkndckkxlbmaasssl.supabase.co:5432/postgres",
    "postgresql://postgres.pagrkndckkxlbmaasssl:x@aws-0-eu-west-1.pooler.supabase.com:5432/postgres",
])
def test_la_restauration_dessai_refuse_la_production(cible, monkeypatch, tmp_path):
    import sauvegarde_base as s
    monkeypatch.setenv("SAUVEGARDE_CIBLE", cible)
    with pytest.raises(s.Echec, match="jamais sur la production"):
        s.verifier(tmp_path)


def test_sans_adresse_le_script_le_dit(monkeypatch, tmp_path, capsys):
    import sauvegarde_base as s
    monkeypatch.delenv("SAUVEGARDE_SOURCE", raising=False)
    assert s.main(["copier", str(tmp_path)]) == 1
    assert "SAUVEGARDE_SOURCE est vide" in capsys.readouterr().err


def test_une_cle_qui_nest_pas_une_cle_age_est_refusee(tmp_path):
    import sauvegarde_base as s
    with pytest.raises(s.Echec, match="pas une clé publique age"):
        s.emballer(tmp_path, "AGE-SECRET-KEY-1ABCDEF", tmp_path / "x.tar.age")


@avec_age
def test_seule_la_cle_privee_rouvre_larchive(tmp_path):
    import sauvegarde_base as s
    copie = tmp_path / "copie"
    copie.mkdir()
    for nom, contenu in ((s.MANIFESTE, '{"lignes": {}}'), (s.PUBLIC, "séries"), (s.COMPTES, "comptes")):
        (copie / nom).write_text(contenu, encoding="utf-8")
    cles = tmp_path / "cle.txt"
    subprocess.run(["age-keygen", "-o", str(cles)], check=True, capture_output=True)
    publique = re.search(r"public key: (age1\w+)", cles.read_text()).group(1)

    archive = tmp_path / "sauvegarde.tar.age"
    s.emballer(copie, publique, archive)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cle.txt", "copie", "sauvegarde.tar.age"]
    assert b"s\xc3\xa9ries" not in archive.read_bytes()        # rien de lisible

    autre = tmp_path / "autre.txt"
    subprocess.run(["age-keygen", "-o", str(autre)], check=True, capture_output=True)
    refus = subprocess.run(["age", "-d", "-i", str(autre), str(archive)], capture_output=True)
    assert refus.returncode != 0                                # une autre clé n'ouvre rien

    ouvert = tmp_path / "ouvert.tar"
    subprocess.run(["age", "-d", "-i", str(cles), "-o", str(ouvert), str(archive)], check=True)
    with tarfile.open(ouvert) as tar:
        assert sorted(tar.getnames()) == sorted([s.MANIFESTE, s.PUBLIC, s.COMPTES])
        assert tar.extractfile(s.PUBLIC).read().decode() == "séries"


# ------------------------------------------- copie et restauration réelles --

def _psql(url, sql=None, fichier=None):
    cmd = ["psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"]
    cmd += ["-f", str(fichier)] if fichier else []
    r = subprocess.run(cmd + [url], input=None if fichier else sql, capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "PGCLIENTENCODING": "UTF8"})
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _base(nom):
    _psql(URL, f"drop database if exists {nom} with (force)")
    _psql(URL, f"create database {nom}")
    return urlparse(URL)._replace(path=f"/{nom}").geturl()


@pytest.fixture(scope="module")
def source():
    """Une base au schéma du dépôt, comme la production : socle Supabase,
    toutes les migrations, la table des identités Google, deux comptes
    inscrits (le déclencheur crée profil et programme) et leurs séries."""
    from test_migrations_postgres import MIGRATIONS, PRELUDE
    url = _base(f"sauvegarde_source_{os.getpid()}")
    _psql(url, fichier=PRELUDE)
    for m in MIGRATIONS:
        _psql(url, fichier=m)
    _psql(url, """
        create table auth.identities (
          id uuid primary key default gen_random_uuid(),
          user_id uuid not null references auth.users(id) on delete cascade,
          provider text not null, identity_data jsonb not null);
        alter table auth.identities owner to supabase_auth_admin;
        set role supabase_auth_admin;
        insert into auth.users (id, email) values
          ('00000000-0000-0000-0000-00000000000a', 'a@exemple.fr'),
          ('00000000-0000-0000-0000-00000000000b', 'b@exemple.fr');
        insert into auth.identities (user_id, provider, identity_data)
          select id, 'google', jsonb_build_object('email', email) from auth.users;
        reset role;
        insert into public.history (user_id, semaine, seance, exercice, serie, reps, poids, date)
          select '00000000-0000-0000-0000-00000000000a', 1, 'Push', 'Développé couché', g, 8,
                 80 + g * 2.5, '2026-11-02' from generate_series(1, 4) g;
        insert into public.history (user_id, semaine, seance, exercice, serie, reps, poids, date)
          values ('00000000-0000-0000-0000-00000000000b', 1, 'Jambes', 'Squat', 1, 5, 120, '2026-11-03');
        insert into public.photos_corps (user_id, date, angle, chemin, miniature, octets) values
          ('00000000-0000-0000-0000-00000000000a', '2026-11-02', 'face',
           '00000000-0000-0000-0000-00000000000a/p1.jpg',
           '00000000-0000-0000-0000-00000000000a/p1_mini.jpg', 300),
          ('00000000-0000-0000-0000-00000000000a', '2026-11-02', 'dos',
           '00000000-0000-0000-0000-00000000000a/p2.jpg',
           '00000000-0000-0000-0000-00000000000a/p2_mini.jpg', 500);
    """)
    yield url
    _psql(URL, f"drop database if exists sauvegarde_source_{os.getpid()} with (force)")


def _script(commande, *args, **env):
    return subprocess.run([sys.executable, str(SCRIPT), commande, *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, **env})


@avec_postgres
def test_la_copie_restauree_sur_une_base_vide_redonne_toute_la_base(source, tmp_path):
    copie = tmp_path / "copie"
    r = _script("copier", copie, SAUVEGARDE_SOURCE=source)
    assert r.returncode == 0, r.stderr
    assert "a@exemple.fr" not in r.stdout + r.stderr        # rien de la base au journal
    lignes = json.loads((copie / "manifeste.json").read_text())["lignes"]
    assert lignes["auth.users"] == 2 and lignes["auth.identities"] == 2
    assert lignes["public.history"] == 5
    assert lignes["public.profiles"] == 2 and lignes["public.programs"] == 2   # déclencheur
    assert len([t for t in lignes if t.startswith("public.")]) >= 21

    cible = _base(f"sauvegarde_cible_{os.getpid()}")
    try:
        r = _script("verifier", copie, SAUVEGARDE_CIBLE=cible)
        assert r.returncode == 0, r.stderr
        assert "toutes retrouvées" in r.stdout
        # Les valeurs, pas seulement le nombre de lignes.
        requete = ("select string_agg(concat_ws(',', user_id, exercice, serie, reps, poids, date), ';' "
                   "order by user_id, serie) from public.history")
        assert _psql(cible, requete) == _psql(source, requete)
        assert _psql(cible, "select string_agg(email, ',' order by email) from auth.users") \
            == "a@exemple.fr,b@exemple.fr"
        # Les droits (v38, v48) et l'inscription reviennent aussi.
        # Droits effectifs : une liste vide vaut celle par défaut du propriétaire.
        droits = ("select string_agg(d, ';' order by d) from (select format('%s:%s:%s:rls=%s', "
                  "c.relname, a.grantee::regrole, a.privilege_type, c.relrowsecurity) d "
                  "from pg_class c, aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) a "
                  "where c.relnamespace = 'public'::regnamespace and c.relkind in ('r', 'v')) x")
        assert _psql(cible, droits) == _psql(source, droits)
        assert "reglages:service_role:UPDATE:rls=t" in _psql(cible, droits)
        assert ":anon:" not in _psql(cible, droits)          # fermées au navigateur (v38)
        uid = _psql(cible, "insert into auth.users (email) values ('c@exemple.fr') returning id")
        assert _psql(cible, f"select tier from public.profiles where id = '{uid}'") == "free"
        # Une seconde restauration sur une base non vide est refusée.
        r = _script("verifier", copie, SAUVEGARDE_CIBLE=cible)
        assert r.returncode == 1 and "n'est pas vide" in r.stderr
    finally:
        _psql(URL, f"drop database if exists sauvegarde_cible_{os.getpid()} with (force)")


@avec_postgres
def test_une_ligne_perdue_a_la_restauration_fait_echouer_la_verification(source, tmp_path):
    copie = tmp_path / "copie"
    assert _script("copier", copie, SAUVEGARDE_SOURCE=source).returncode == 0
    manifeste = copie / "manifeste.json"
    contenu = json.loads(manifeste.read_text())
    contenu["lignes"]["public.history"] += 1          # la copie aurait perdu une série
    manifeste.write_text(json.dumps(contenu))
    cible = _base(f"sauvegarde_ecart_{os.getpid()}")
    try:
        r = _script("verifier", copie, SAUVEGARDE_CIBLE=cible)
        assert r.returncode == 1
        assert "public.history : 6 attendues, 5 restaurées" in r.stderr
    finally:
        _psql(URL, f"drop database if exists sauvegarde_ecart_{os.getpid()} with (force)")


@avec_postgres
def test_la_copie_voit_une_seule_photo_de_la_base(source, monkeypatch):
    """Comptes et séries copiés au même instant : une inscription pendant la
    copie n'y entre pas à moitié (des séries sans leur compte ne se
    restaureraient pas : clé étrangère)."""
    import sauvegarde_base as s
    photo = s._Photo(source)
    try:
        avant = photo.compter(["auth.users", "public.profiles"])
        _psql(source, "insert into auth.users (email) values ('pendant@exemple.fr')")
        assert photo.compter(["auth.users", "public.profiles"]) == avant
        dump = subprocess.run(["pg_dump", f"--snapshot={photo.id}", "--data-only",
                               "--table=auth.users", source], capture_output=True, text=True)
        assert dump.returncode == 0 and "pendant@exemple.fr" not in dump.stdout
    finally:
        photo.fermer()
        _psql(source, "delete from auth.users where email = 'pendant@exemple.fr'")


# ---------------------------------------------------------------- photos --
# Un faux stockage S3 local (moto), à la place de Supabase Storage.

FICHIERS = {
    "00000000-0000-0000-0000-00000000000a/p1.jpg": b"\xff\xd8" + b"1" * 298,
    "00000000-0000-0000-0000-00000000000a/p1_mini.jpg": b"\xff\xd8" + b"m" * 40,
    "00000000-0000-0000-0000-00000000000a/p2.jpg": b"\xff\xd8" + b"2" * 498,
    "00000000-0000-0000-0000-00000000000a/p2_mini.jpg": b"\xff\xd8" + b"n" * 40,
}


@pytest.fixture
def stockage(monkeypatch):
    """Un dossier `photos-corps` avec les fichiers des deux photos de la
    base d'essai, et les variables que le workflow donne au script."""
    boto3 = pytest.importorskip("boto3")
    serveur_moto = pytest.importorskip("moto.server")
    serveur = serveur_moto.ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    serveur.start()
    hote, port = serveur.get_host_and_port()
    adresse = f"http://{hote}:{port}"
    # Le faux stockage garde son état d'un serveur à l'autre : on repart de zéro.
    urllib.request.urlopen(urllib.request.Request(f"{adresse}/moto-api/reset", method="POST"))
    env = {"SAUVEGARDE_S3_ID": "faux-id", "SAUVEGARDE_S3_SECRET": "faux-secret",
           "SAUVEGARDE_S3_ADRESSE": adresse, "SAUVEGARDE_S3_REGION": "eu-west-1"}
    for nom, valeur in env.items():
        monkeypatch.setenv(nom, valeur)
    s3 = boto3.client("s3", endpoint_url=adresse, region_name="eu-west-1",
                      aws_access_key_id="faux-id", aws_secret_access_key="faux-secret")
    s3.create_bucket(Bucket="photos-corps",
                     CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
    for cle, contenu in FICHIERS.items():
        s3.put_object(Bucket="photos-corps", Key=cle, Body=contenu)
    yield s3, env
    serveur.stop()


def _etat(s3):
    return sorted((o["Key"], o["Size"], o["ETag"])
                  for o in s3.list_objects_v2(Bucket="photos-corps").get("Contents", []))


def test_les_photos_sont_copiees_octet_pour_octet_sans_rien_changer_au_stockage(stockage, tmp_path):
    import sauvegarde_photos as p
    s3, _ = stockage
    avant = _etat(s3)
    p.copier_photos(tmp_path)
    for cle, contenu in FICHIERS.items():
        assert (tmp_path / "photos" / cle).read_bytes() == contenu
    liste = json.loads((tmp_path / "photos.json").read_text())
    assert liste == {"dossier": "photos-corps", "fichiers": {c: len(v) for c, v in FICHIERS.items()}}
    assert _etat(s3) == avant                                   # lecture seule


def test_le_stockage_nest_que_lu():
    """Les seuls appels au stockage : lister et télécharger. Jamais écrire,
    remplacer ni effacer (les clés S3 le permettraient)."""
    source = (PWA / "tools" / "sauvegarde_photos.py").read_text(encoding="utf-8")
    assert set(re.findall(r"\bs3\.(\w+)\(", source)) == {"get_paginator", "get_object"}
    assert "list_objects_v2" in source


def test_un_nom_de_fichier_ne_sort_pas_du_dossier(tmp_path):
    import sauvegarde_photos as p
    assert p._destination(tmp_path, "u/x.jpg") == (tmp_path / "u" / "x.jpg").resolve()
    for cle in ("../x.jpg", "u/../../x.jpg", "/etc/x.jpg"):
        with pytest.raises(p.Echec, match="refusé"):
            p._destination(tmp_path, cle)


def test_sans_les_cles_s3_le_script_les_nomme(monkeypatch, tmp_path, capsys):
    import sauvegarde_base as s
    for nom in ("SAUVEGARDE_S3_ID", "SAUVEGARDE_S3_SECRET"):
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setenv("SAUVEGARDE_S3_ADRESSE", "http://127.0.0.1:9")
    assert s.main(["photos", str(tmp_path)]) == 1
    assert "SAUVEGARDE_S3_ID, SAUVEGARDE_S3_SECRET vide" in capsys.readouterr().err


def test_un_stockage_injoignable_fait_echouer_sans_montrer_la_cle(monkeypatch, tmp_path, capsys):
    import sauvegarde_base as s
    for nom, valeur in (("SAUVEGARDE_S3_ID", "faux-id"), ("SAUVEGARDE_S3_SECRET", "faux-secret"),
                        ("SAUVEGARDE_S3_ADRESSE", "http://127.0.0.1:9"),   # rien n'écoute
                        ("SAUVEGARDE_S3_ESSAIS", "1")):
        monkeypatch.setenv(nom, valeur)
    assert s.main(["photos", str(tmp_path)]) == 1
    erreur = capsys.readouterr().err
    assert "copie des photos impossible" in erreur and "faux-secret" not in erreur


@avec_age
def test_larchive_contient_les_photos(tmp_path):
    import sauvegarde_base as s
    copie = tmp_path / "copie"
    (copie / "photos" / "u").mkdir(parents=True)
    for nom in (s.MANIFESTE, s.PUBLIC, s.COMPTES):
        (copie / nom).write_text("x", encoding="utf-8")
    (copie / "photos.json").write_text('{"fichiers": {"u/a.jpg": 3}}', encoding="utf-8")
    (copie / "photos" / "u" / "a.jpg").write_bytes(b"abc")
    cles = tmp_path / "cle.txt"
    subprocess.run(["age-keygen", "-o", str(cles)], check=True, capture_output=True)
    publique = re.search(r"public key: (age1\w+)", cles.read_text()).group(1)
    s.emballer(copie, publique, tmp_path / "a.tar.age")
    ouvert = tmp_path / "a.tar"
    subprocess.run(["age", "-d", "-i", str(cles), "-o", str(ouvert), str(tmp_path / "a.tar.age")],
                   check=True)
    with tarfile.open(ouvert) as tar:
        assert "photos/u/a.jpg" in tar.getnames() and "photos.json" in tar.getnames()
        assert tar.extractfile("photos/u/a.jpg").read() == b"abc"


@avec_postgres
def test_chaque_photo_de_la_base_a_son_fichier_dans_la_copie(source, stockage, tmp_path):
    copie = tmp_path / "copie"
    _, env = stockage
    assert _script("copier", copie, SAUVEGARDE_SOURCE=source).returncode == 0
    r = _script("photos", copie, **env)
    assert r.returncode == 0, r.stderr
    assert "Photos copiées : 4 fichiers" in r.stdout

    def verifier(nom):
        cible = _base(f"sauvegarde_{nom}_{os.getpid()}")
        try:
            return _script("verifier", copie, SAUVEGARDE_CIBLE=cible)
        finally:
            _psql(URL, f"drop database if exists sauvegarde_{nom}_{os.getpid()} with (force)")

    r = verifier("photos_ok")
    assert r.returncode == 0, r.stderr
    assert "Photos : 4 fichiers attendus par la base, tous présents (4 copiés)." in r.stdout

    photo = copie / "photos" / "00000000-0000-0000-0000-00000000000a" / "p2.jpg"
    photo.write_bytes(photo.read_bytes()[:-1])                   # tronquée
    r = verifier("photo_tronquee")
    assert r.returncode == 1
    assert "taille différente : 00000000-0000-0000-0000-00000000000a/p2.jpg (499 octets, 500 en base)" \
        in r.stderr

    (copie / "photos" / "00000000-0000-0000-0000-00000000000a" / "p1_mini.jpg").unlink()
    r = verifier("photo_absente")
    assert r.returncode == 1
    assert "fichier absent : 00000000-0000-0000-0000-00000000000a/p1_mini.jpg" in r.stderr
