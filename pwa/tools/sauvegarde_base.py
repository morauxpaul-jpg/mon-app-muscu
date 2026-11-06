"""Sauvegarde quotidienne de la base (audit du 04/11, B3).

L'offre Supabase gratuite ne sauvegarde rien. Ce script, lancé chaque nuit
par .github/workflows/sauvegarde.yml, fait quatre choses :

  copier   DOSSIER          copie la base désignée par SAUVEGARDE_SOURCE
  photos   DOSSIER          copie les fichiers des photos de progression
                            (sauvegarde_photos.py)
  verifier DOSSIER          la restaure sur la base VIDE SAUVEGARDE_CIBLE et
                            compare, table par table, le nombre de lignes,
                            puis vérifie que chaque photo de la base a son fichier
  emballer DOSSIER CLE SORTIE
                            range le dossier dans une archive chiffrée avec
                            `age` pour la clé publique CLE (age1…)

Ce qui est copié (une seule photo de la base, `pg_export_snapshot`) :
- tout le schéma `public` : tables, données, fonctions, droits ;
- les comptes : `auth.users` et `auth.identities` (lien Google ↔ compte).
  Sans eux, les lignes de `public` ne se rattachent plus à personne.
Pas les sessions ni les jetons (on se reconnecte). Les fichiers des photos,
que `pg_dump` ne voit pas, sont copiés à part (commande `photos`).

La source n'est que lue : la photo est prise dans une transaction
« read only », et pg_dump travaille lui aussi en lecture seule.

Les adresses passent par l'environnement, jamais en argument du script :
elles contiennent le mot de passe. Rien de la base n'est écrit dans le
journal, seulement des noms de tables et des totaux.

Mode d'emploi pour le propriétaire : docs/SAUVEGARDE.md.
"""
import json
import os
import re
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import sauvegarde_photos

PUBLIC = "public.dump"
COMPTES = "comptes.dump"
MANIFESTE = "manifeste.json"
TABLES_AUTH = ("auth.users", "auth.identities")

# Une restauration d'essai ne doit JAMAIS viser la production.
HOTES_INTERDITS = ("supabase.co", "supabase.com")
CLE_AGE = re.compile(r"age1[0-9a-z]{58}")


class Echec(Exception):
    """Erreur lisible, sans donnée de la base, destinée au journal."""


def _outil(nom):
    """pg_dump, pg_restore, psql : ceux de PG_BIN s'il est donné (la version
    doit être au moins celle du serveur), sinon ceux du PATH."""
    dossier = os.getenv("PG_BIN")
    return str(Path(dossier) / nom) if dossier else nom


def _lancer(cmd, quoi, entree=None):
    r = subprocess.run(cmd, input=entree, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PGCLIENTENCODING": "UTF8"})
    if r.returncode:
        raise Echec(f"{quoi} a échoué :\n{r.stderr.strip()[-2000:]}")
    return r.stdout


def _psql(url, sql, quoi="psql"):
    return _lancer([_outil("psql"), "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", url],
                   quoi, entree=sql).strip()


def _adresse(variable):
    url = os.getenv(variable, "").strip()
    if not url:
        raise Echec(f"{variable} est vide : voir docs/SAUVEGARDE.md.")
    return url


# ---------------------------------------------------------------- copier --

class _Photo:
    """Une session psql ouverte qui tient une photo de la base. Tant qu'elle
    vit, pg_dump --snapshot voit exactement le même état : les comptes et les
    tables qui s'y rattachent sont donc d'accord entre eux."""

    def __init__(self, url):
        self.p = subprocess.Popen(
            [_outil("psql"), "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", url],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env={**os.environ, "PGCLIENTENCODING": "UTF8"})
        self.id = self._demander("begin isolation level repeatable read read only;\n"
                                 "select pg_export_snapshot();")[0]

    def _demander(self, sql):
        """Envoie une requête, lit ses lignes jusqu'à un repère de fin."""
        self.p.stdin.write(f"{sql}\nselect '__fin__';\n")
        self.p.stdin.flush()
        lignes = []
        while (ligne := self.p.stdout.readline()) and ligne.strip() != "__fin__":
            lignes.append(ligne.rstrip("\n"))
        if not ligne:
            raise Echec(f"la connexion à la source a échoué :\n{self.p.stderr.read().strip()[-2000:]}")
        return lignes

    def compter(self, tables):
        sql = " union all ".join(f"select '{t}', count(*) from {t}" for t in tables)
        return {nom: int(n) for nom, n in (l.split("|") for l in self._demander(sql + ";"))}

    def tables_public(self):
        return self._demander("select format('%I.%I', schemaname, tablename) from pg_tables "
                              "where schemaname = 'public' order by 1;")

    def fermer(self):
        if self.p.poll() is None:
            self.p.stdin.write("commit;\n")
            self.p.stdin.close()
            self.p.wait(timeout=30)


def copier(dossier):
    source = _adresse("SAUVEGARDE_SOURCE")
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    photo = _Photo(source)
    try:
        tables = photo.tables_public() + list(TABLES_AUTH)
        comptes = photo.compter(tables)
        serveur = photo._demander("show server_version;")[0]
        commun = [_outil("pg_dump"), f"--snapshot={photo.id}", "--format=custom", "--strict-names"]
        _lancer(commun + ["--schema=public", f"--file={dossier / PUBLIC}", source],
                "pg_dump du schéma public")
        _lancer(commun + [f"--table={t}" for t in TABLES_AUTH]
                + [f"--file={dossier / COMPTES}", source], "pg_dump des comptes")
    finally:
        photo.fermer()
    (dossier / MANIFESTE).write_text(json.dumps({
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "serveur": serveur,
        "lignes": comptes,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Copie faite : {len(tables)} tables, {sum(comptes.values())} lignes en tout.")


# -------------------------------------------------------------- verifier --

_ROLE = r'("(?:[^"]|"")+"|[\w$]+)'


def roles_cites(sql):
    """Les rôles qu'un script de restauration suppose exister : propriétaires,
    bénéficiaires et auteurs des droits. Une base vide ne les a pas."""
    roles = set(re.findall(rf"OWNER TO {_ROLE};", sql))
    roles |= set(re.findall(rf"FOR ROLE {_ROLE}", sql))
    for liste in re.findall(r"^(?:ALTER DEFAULT PRIVILEGES .*?)?(?:GRANT|REVOKE)\b.*?\b(?:TO|FROM) (.+?)"
                            r"(?: WITH GRANT OPTION)?;$",
                            sql, flags=re.M):
        roles |= {r.strip() for r in liste.split(",")}
    roles |= set(re.findall(rf"^SET (?:SESSION )?(?:AUTHORIZATION|ROLE) {_ROLE};", sql, flags=re.M))
    roles = {r[1:-1].replace('""', '"') if r.startswith('"') else r for r in roles}
    return sorted(r for r in roles if r.upper() != "PUBLIC" and r != "CURRENT_USER")


def _litteral(texte):
    return "'" + texte.replace("'", "''") + "'"


def _identifiant(texte):
    return '"' + texte.replace('"', '""') + '"'


def _verifier_cible(cible):
    hote = (urlparse(cible).hostname or "").lower()
    if any(hote == h or hote.endswith("." + h) for h in HOTES_INTERDITS):
        raise Echec("SAUVEGARDE_CIBLE désigne un serveur Supabase : la restauration d'essai "
                    "se fait sur un PostgreSQL vide, jamais sur la production.")
    if cible == os.getenv("SAUVEGARDE_SOURCE", "").strip():
        raise Echec("SAUVEGARDE_CIBLE est la source : refusé.")
    occupees = _psql(cible, "select count(*) from pg_tables where schemaname in ('public', 'auth');")
    if occupees != "0":
        raise Echec(f"SAUVEGARDE_CIBLE n'est pas vide ({occupees} tables) : refusé.")


def verifier(dossier):
    cible = _adresse("SAUVEGARDE_CIBLE")
    dossier = Path(dossier)
    _verifier_cible(cible)
    attendu = json.loads((dossier / MANIFESTE).read_text(encoding="utf-8"))["lignes"]
    public, comptes = str(dossier / PUBLIC), str(dossier / COMPTES)

    # 1. Les rôles de Supabase (anon, service_role, supabase_admin…), sans
    #    connexion possible : seulement pour que les droits se restaurent.
    sql = "".join(_lancer([_outil("pg_restore"), "--schema-only", "--file=-", f], "lecture de la copie")
                  for f in (public, comptes))
    creer = "".join(f"do $$ begin if not exists (select from pg_roles where rolname = {_litteral(r)}) "
                    f"then create role {_identifiant(r)} nologin; end if; end $$;\n"
                    for r in roles_cites(sql))
    _psql(cible, creer + "create schema if not exists auth;\n", "création des rôles")

    # 2. Ordre imposé par les liens entre tables et par le déclencheur
    #    on_auth_user_created (auth.users → public.handle_new_user) :
    #    structure de public, puis les comptes (leur déclencheur n'est posé
    #    qu'APRÈS leurs lignes), puis les lignes de public, puis ses clés
    #    étrangères vers les comptes. Toute base neuve a déjà un schéma
    #    `public` : sa création est retirée de la liste à restaurer.
    liste = dossier / "liste.txt"
    table = _lancer([_outil("pg_restore"), "--list", public], "lecture de la copie")
    liste.write_text("".join(l for l in table.splitlines(keepends=True)
                             if not re.search(r"\bSCHEMA - public\b", l)), encoding="utf-8")
    restaurer = [_outil("pg_restore"), "--exit-on-error", f"--dbname={cible}"]
    _lancer(restaurer + [f"--use-list={liste}", "--section=pre-data", public],
            "restauration de la structure")
    _lancer(restaurer + [comptes], "restauration des comptes")
    _lancer(restaurer + ["--section=data", public], "restauration des lignes")
    _lancer(restaurer + ["--section=post-data", public], "restauration des index et des liens")

    # 3. Chaque table a-t-elle retrouvé toutes ses lignes ?
    sql = " union all ".join(f"select '{t}', count(*) from {t}" for t in attendu)
    trouve = {nom: int(n) for nom, n in (l.split("|") for l in _psql(cible, sql + ";").splitlines())}
    ecarts = [f"{t} : {attendu[t]} attendues, {trouve.get(t)} restaurées"
              for t in attendu if trouve.get(t) != attendu[t]]
    if ecarts:
        raise Echec("La restauration ne redonne pas la base :\n" + "\n".join(ecarts))
    print(f"Restauration d'essai réussie : {len(attendu)} tables, "
          f"{sum(attendu.values())} lignes, toutes retrouvées.")

    # 4. Les photos, si elles ont été copiées : un fichier par photo et par
    #    miniature de la base restaurée, de la bonne taille.
    sauvegarde_photos.verifier_photos(dossier, lambda sql: _psql(cible, sql))


# --------------------------------------------------------------- emballer --

def emballer(dossier, cle, sortie):
    """Archive le dossier puis la chiffre pour la clé publique. Seule la clé
    privée du propriétaire, gardée hors de GitHub, peut l'ouvrir. L'archive
    en clair n'existe que le temps du chiffrement, puis est effacée."""
    cle = cle.strip()
    if not CLE_AGE.fullmatch(cle):
        raise Echec("SAUVEGARDE_CLE_AGE n'est pas une clé publique age (age1…) : "
                    "voir docs/SAUVEGARDE.md.")
    dossier, sortie = Path(dossier), Path(sortie)
    en_clair = sortie.with_name(sortie.name + ".tmp.tar")
    try:
        with tarfile.open(en_clair, "w") as tar:
            for nom in (MANIFESTE, PUBLIC, COMPTES):
                tar.add(dossier / nom, arcname=nom)
            if (dossier / sauvegarde_photos.LISTE).exists():
                for nom in (sauvegarde_photos.LISTE, sauvegarde_photos.PHOTOS):
                    tar.add(dossier / nom, arcname=nom)
        _lancer(["age", "--encrypt", "--recipient", cle, "--output", str(sortie), str(en_clair)],
                "le chiffrement (age)")
    finally:
        en_clair.unlink(missing_ok=True)
    print(f"Archive chiffrée : {sortie.name} ({sortie.stat().st_size} octets).")


def main(args):
    try:
        if args[:1] == ["copier"] and len(args) == 2:
            copier(args[1])
        elif args[:1] == ["photos"] and len(args) == 2:
            sauvegarde_photos.copier_photos(args[1])
        elif args[:1] == ["verifier"] and len(args) == 2:
            verifier(args[1])
        elif args[:1] == ["emballer"] and len(args) == 4:
            emballer(*args[1:])
        else:
            print(__doc__)
            return 2
    except (Echec, sauvegarde_photos.Echec) as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
