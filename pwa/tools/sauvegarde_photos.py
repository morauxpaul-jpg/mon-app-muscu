"""Photos de progression dans la sauvegarde quotidienne (suite du B3).

`pg_dump` ne copie que la base : les photos sont des fichiers, dans le
dossier privé `photos-corps` de Supabase Storage (core/db_photos.py). Ce
module les copie par l'accès « S3 » de Supabase Storage, avec une paire de
clés S3 du projet. Ces clés n'ouvrent que les fichiers, pas la base ni les
comptes : c'est moins que la clé `service_role` de l'app.

LECTURE SEULE : les seuls appels au stockage sont la liste des fichiers et
leur téléchargement (`get_paginator`, `get_object`). Un test le vérifie
dans ce fichier.

Variables d'environnement (noms seulement dans le workflow) :
  SAUVEGARDE_S3_ID, SAUVEGARDE_S3_SECRET   la paire de clés S3 (secrets)
  SAUVEGARDE_S3_ADRESSE                    https://<ref>.storage.supabase.co/storage/v1/s3
  SAUVEGARDE_S3_REGION                     région du projet (eu-west-1)

Contrôle à la restauration d'essai : chaque photo et chaque miniature de la
table `photos_corps` restaurée a son fichier, et la photo a la taille notée
en base (`octets`).
"""
import json
import os
from pathlib import Path

SEAU = "photos-corps"
PHOTOS = "photos"              # dossier des fichiers dans l'archive
LISTE = "photos.json"          # liste des fichiers copiés et leur taille


class Echec(Exception):
    """Erreur lisible, sans contenu de fichier, destinée au journal."""


def _client():
    manque = [v for v in ("SAUVEGARDE_S3_ID", "SAUVEGARDE_S3_SECRET", "SAUVEGARDE_S3_ADRESSE")
              if not os.getenv(v, "").strip()]
    if manque:
        raise Echec(f"{', '.join(manque)} vide : voir docs/SAUVEGARDE.md (photos).")
    import boto3                      # seulement pour les photos
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=os.environ["SAUVEGARDE_S3_ADRESSE"].strip(),
        region_name=os.getenv("SAUVEGARDE_S3_REGION", "eu-west-1").strip(),
        aws_access_key_id=os.environ["SAUVEGARDE_S3_ID"].strip(),
        aws_secret_access_key=os.environ["SAUVEGARDE_S3_SECRET"].strip(),
        config=Config(s3={"addressing_style": "path"},
                      retries={"max_attempts": int(os.getenv("SAUVEGARDE_S3_ESSAIS", "5"))}))


def _destination(racine: Path, cle: str) -> Path:
    """Le fichier local d'une clé, sans jamais sortir du dossier (une clé
    `a/../../x` ne doit rien écrire ailleurs)."""
    chemin = (racine / cle).resolve()
    if racine.resolve() not in chemin.parents:
        raise Echec(f"nom de fichier refusé dans le stockage : {cle!r}")
    return chemin


def copier_photos(dossier):
    s3 = _client()
    racine = Path(dossier) / PHOTOS
    racine.mkdir(parents=True, exist_ok=True)
    fichiers = {}
    try:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=SEAU):
            for objet in page.get("Contents", []):
                cle = objet["Key"]
                chemin = _destination(racine, cle)
                chemin.parent.mkdir(parents=True, exist_ok=True)
                contenu = s3.get_object(Bucket=SEAU, Key=cle)["Body"].read()
                if len(contenu) != objet["Size"]:
                    raise Echec(f"fichier tronqué : {cle} ({len(contenu)} octets sur {objet['Size']})")
                chemin.write_bytes(contenu)
                fichiers[cle] = len(contenu)
    except Echec:
        raise
    except Exception as e:            # réseau, clé refusée… sans détail sensible
        raise Echec(f"copie des photos impossible : {type(e).__name__}: {e}") from None
    (Path(dossier) / LISTE).write_text(json.dumps(
        {"dossier": SEAU, "fichiers": fichiers}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Photos copiées : {len(fichiers)} fichiers, {sum(fichiers.values())} octets.")


def verifier_photos(dossier, interroger):
    """`interroger(sql)` rend le texte de psql (-A -t) sur la base restaurée."""
    dossier = Path(dossier)
    if not (dossier / LISTE).exists():
        return None
    copies = json.loads((dossier / LISTE).read_text(encoding="utf-8"))["fichiers"]
    lignes = interroger("select chemin, miniature, octets from public.photos_corps;")
    ecarts = []
    attendus = 0
    for ligne in filter(None, lignes.splitlines()):
        chemin, miniature, octets = ligne.split("|")
        for cle, taille in ((chemin, int(octets)), (miniature, None)):
            attendus += 1
            fichier = dossier / PHOTOS / cle
            if cle not in copies or not fichier.is_file():
                ecarts.append(f"fichier absent : {cle}")
            elif taille is not None and fichier.stat().st_size != taille:
                ecarts.append(f"taille différente : {cle} ({fichier.stat().st_size} octets, "
                              f"{taille} en base)")
    if ecarts:
        raise Echec("Les photos de la base ne sont pas toutes dans la copie :\n" + "\n".join(ecarts))
    print(f"Photos : {attendus} fichiers attendus par la base, tous présents "
          f"({len(copies)} copiés).")
    return attendus
