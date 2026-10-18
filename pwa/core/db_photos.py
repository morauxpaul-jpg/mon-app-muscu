"""Photos de progression — la table `photos_corps` et ses fichiers (v50).

Les fichiers sont dans le dossier PRIVÉ `photos-corps` de Supabase Storage,
rangés sous `<user_id>/`. Le client porte la clé service_role, qui passe
outre toutes les règles : chaque fonction filtre donc par `user_id`, et la
page ne sert un fichier qu'après avoir retrouvé sa ligne chez ce compte.

Ordre des écritures, pour ne jamais laisser une photo sans ligne (donc
invisible, et oubliée à la suppression du compte) :
  - ajout : fichiers d'abord, ligne ensuite ; la ligne refusée, les
    fichiers sont retirés ;
  - suppression : fichiers d'abord ; s'ils résistent, la ligne reste et
    l'utilisateur peut réessayer.

Base en retard (table absente) : `PhotosIndisponibles`. La page le dit, le
reste de l'app n'en sait rien. Le manque est signalé à /admin.
"""
import logging
import uuid

from core.db_base import _fetch_all, get_client
from core.photos_corps import PHOTOS_MAX

logger = logging.getLogger(__name__)

TABLE_PHOTOS = "photos_corps"
DOSSIER = "photos-corps"
COLONNES_PHOTOS = "id, date, angle, chemin, miniature, octets, created_at"


class PhotosIndisponibles(Exception):
    """La table manque (migration v50 pas encore passée)."""


def _absente(err) -> bool:
    from core.schema import signaler
    msg = str(err).lower()
    return TABLE_PHOTOS in msg and any(m in msg for m in (
        "does not exist", "42p01", "pgrst205", "schema cache")) and signaler(err, TABLE_PHOTOS)


def _requete(faire):
    try:
        return faire()
    except Exception as e:
        if _absente(e):
            raise PhotosIndisponibles() from e
        raise


def _dossier():
    return get_client().storage.from_(DOSSIER)


def list_photos(user_id: str) -> list[dict]:
    """Mes photos, les plus récentes d'abord."""
    resp = _requete(lambda: (
        get_client().table(TABLE_PHOTOS).select(COLONNES_PHOTOS)
        .eq("user_id", user_id).order("date", desc=True).limit(PHOTOS_MAX).execute()))
    return resp.data or []


def get_photo(user_id: str, photo_id: int) -> dict | None:
    resp = _requete(lambda: (
        get_client().table(TABLE_PHOTOS).select(COLONNES_PHOTOS)
        .eq("user_id", user_id).eq("id", int(photo_id)).limit(1).execute()))
    return (resp.data or [None])[0]


def _retirer_fichiers(chemins) -> None:
    chemins = [c for c in chemins if c]
    if chemins:
        _dossier().remove(chemins)


def enregistrer_photo(user_id: str, date_iso: str, angle: str, image: bytes, miniature: bytes) -> dict:
    """Ajoute la photo, ou remplace celle du même jour et du même angle.
    Rend la ligne enregistrée."""
    client = get_client()
    base = f"{user_id}/{uuid.uuid4().hex}"
    champs = {"chemin": base + ".jpg", "miniature": base + "_mini.jpg", "octets": len(image)}
    existante = _requete(lambda: (
        client.table(TABLE_PHOTOS).select(COLONNES_PHOTOS).eq("user_id", user_id)
        .eq("date", date_iso).eq("angle", angle).limit(1).execute())).data
    existante = existante[0] if existante else None

    options = {"content-type": "image/jpeg", "cache-control": "private, max-age=0"}
    _dossier().upload(champs["chemin"], bytes(image), options)
    try:
        _dossier().upload(champs["miniature"], bytes(miniature), options)
        if existante:
            resp = (client.table(TABLE_PHOTOS).update(champs)
                    .eq("user_id", user_id).eq("id", existante["id"]).execute())
        else:
            resp = client.table(TABLE_PHOTOS).insert(
                {"user_id": user_id, "date": date_iso, "angle": angle, **champs}).execute()
    except Exception:
        try:
            _retirer_fichiers([champs["chemin"], champs["miniature"]])
        except Exception as e:
            logger.error("photos : fichiers orphelins %s : %s", base, e)
        raise
    if existante:
        try:
            _retirer_fichiers([existante.get("chemin"), existante.get("miniature")])
        except Exception as e:
            logger.error("photos : ancienne photo %s non retirée : %s", existante.get("id"), e)
    return (resp.data or [{}])[0]


def lire_fichier(chemin: str) -> bytes:
    return _dossier().download(chemin)


def supprimer_photo(user_id: str, photo_id: int) -> bool:
    photo = get_photo(user_id, photo_id)
    if not photo:
        return False
    _retirer_fichiers([photo.get("chemin"), photo.get("miniature")])
    get_client().table(TABLE_PHOTOS).delete().eq("user_id", user_id).eq("id", photo["id"]).execute()
    return True


def supprimer_toutes_les_photos(user_id: str) -> int:
    """Suppression du compte : tous les fichiers, puis toutes les lignes.
    Table absente : rien à supprimer."""
    try:
        photos = list_photos(user_id)
    except PhotosIndisponibles:
        return 0
    chemins = [c for p in photos for c in (p.get("chemin"), p.get("miniature")) if c]
    for i in range(0, len(chemins), 100):
        _retirer_fichiers(chemins[i:i + 100])
    get_client().table(TABLE_PHOTOS).delete().eq("user_id", user_id).execute()
    return len(photos)


def dernieres_photos_par_compte() -> dict:
    """{user_id: 'YYYY-MM-DD'} de la photo la plus récente — le rappel des
    4 semaines, en une lecture pour tous les comptes."""
    client = get_client()
    try:
        lignes = _fetch_all(lambda: client.table(TABLE_PHOTOS).select("user_id, date").order("id"))
    except Exception as e:
        _absente(e)
        logger.error("dernieres_photos_par_compte FAILED: %s", e)
        return {}
    out: dict = {}
    for r in lignes:
        uid, d = r.get("user_id"), str(r.get("date") or "")[:10]
        if uid and d > out.get(uid, ""):
            out[uid] = d
    return out
