"""Mes aliments et mes recettes — la table `aliments_perso` (migration v49).

Les calculs (valeurs pour 100 g, parts, contrôles) sont dans
core/nutrition_recettes.py ; ici, seulement la lecture et l'écriture.

Base en retard (table absente) : lecture et écriture lèvent
`AlimentsIndisponibles`. La page Nutrition s'en passe (sa recherche marche
comme avant), la page « Mes recettes et aliments » dit qu'elle n'est pas
prête. Le manque est signalé à /admin (core/schema.py).
"""
import datetime as _dt

from core.db_base import get_client

TABLE_ALIMENTS = "aliments_perso"
COLONNES_ALIMENTS = "id, nom, food, recette, updated_at"
LIMITE_ALIMENTS = 200


class AlimentsIndisponibles(Exception):
    """La table manque (migration v49 pas encore passée)."""


def _aliments_absents(err) -> bool:
    from core.schema import signaler
    msg = str(err).lower()
    return TABLE_ALIMENTS in msg and any(m in msg for m in (
        "does not exist", "42p01", "pgrst205", "schema cache")) and signaler(err, TABLE_ALIMENTS)


def list_aliments_perso(user_id: str) -> list[dict]:
    """Mes aliments, les derniers modifiés d'abord."""
    try:
        resp = (get_client().table(TABLE_ALIMENTS).select(COLONNES_ALIMENTS)
                .eq("user_id", user_id).order("updated_at", desc=True)
                .limit(LIMITE_ALIMENTS).execute())
    except Exception as e:
        if _aliments_absents(e):
            raise AlimentsIndisponibles() from e
        raise
    return resp.data or []


def get_aliment_perso(user_id: str, aliment_id: int) -> dict | None:
    try:
        resp = (get_client().table(TABLE_ALIMENTS).select(COLONNES_ALIMENTS)
                .eq("user_id", user_id).eq("id", int(aliment_id)).limit(1).execute())
    except Exception as e:
        if _aliments_absents(e):
            raise AlimentsIndisponibles() from e
        raise
    return (resp.data or [None])[0]


def enregistrer_aliment_perso(user_id: str, nom: str, food: dict, recette: dict | None,
                              aliment_id: int | None = None) -> int | None:
    """Crée (sans `aliment_id`) ou remplace un de mes aliments ; rend son id."""
    maintenant = _dt.datetime.now(_dt.timezone.utc).isoformat()
    champs = {"nom": nom, "food": food, "recette": recette, "updated_at": maintenant}
    client = get_client()
    try:
        if aliment_id:
            (client.table(TABLE_ALIMENTS).update(champs)
             .eq("user_id", user_id).eq("id", int(aliment_id)).execute())
            return int(aliment_id)
        resp = client.table(TABLE_ALIMENTS).insert({"user_id": user_id, **champs}).execute()
    except Exception as e:
        if _aliments_absents(e):
            raise AlimentsIndisponibles() from e
        raise
    return ((resp.data or [{}])[0]).get("id")


def supprimer_aliment_perso(user_id: str, aliment_id: int) -> None:
    try:
        (get_client().table(TABLE_ALIMENTS).delete()
         .eq("user_id", user_id).eq("id", int(aliment_id)).execute())
    except Exception as e:
        if _aliments_absents(e):
            raise AlimentsIndisponibles() from e
        raise


def list_all_aliments_perso(user_id: str) -> list[dict]:
    """Export RGPD : tout, sans limite d'affichage."""
    from core.db_base import _fetch_all
    return _fetch_all(lambda: (
        get_client().table(TABLE_ALIMENTS).select("id, nom, food, recette, created_at, updated_at")
        .eq("user_id", user_id).order("id")))
