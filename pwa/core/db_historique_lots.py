"""Écritures en lot dans `history` : réécriture complète et ajout massif.

`save_hist` sert à la restauration d'une sauvegarde et au reset ;
`ajouter_lignes` à l'import Hevy/Strong. Les deux écrivent par clé de série
(index unique v41) : relancées après une coupure, elles convergent au lieu de
doubler.
"""
import logging

from core.db_base import _cache_invalidate, _fetch_all, get_client
from core.db_historique import (_delete_history_ids, _insert_history, _norm_date,
                                _row_to_supabase, _series_distinctes)

logger = logging.getLogger(__name__)


def save_hist(user_id: str, rows: list[dict]):
    """Réécrit tout l'historique de l'user (import de sauvegarde, reset).

    Ordre volontairement inversé par rapport à un clear+insert : on INSÈRE
    d'abord les nouvelles lignes, puis on SUPPRIME les anciennes par id. À
    aucun moment l'historique n'est vide ; si l'insertion échoue, on efface ce
    qu'on vient d'ajouter et l'ancien historique est intact."""
    client = get_client()

    old_ids = [r["id"] for r in _fetch_all(lambda: (
        client.table("history").select("id").eq("user_id", user_id).order("id")
    )) if r.get("id") is not None]

    # Avec l'index v41, une ligne qui reprend la clé d'une ancienne la met à
    # jour sur place (même id) : elle ne doit pas être effacée ensuite. Un
    # import interrompu se relance sans rien doubler.
    payload = _series_distinctes([_row_to_supabase(user_id, r) for r in rows or []])
    written_ids: list = []
    try:
        for i in range(0, len(payload), 500):
            chunk = payload[i:i + 500]
            resp = _insert_history(client, chunk, par_cle=True)
            if resp is None:
                resp = _insert_history(client, chunk)
            written_ids.extend(x["id"] for x in (resp.data or []) if x.get("id") is not None)
    except Exception as e:
        logger.error("save_hist insert FAILED user=%s: %s", user_id, e)
        anciens = set(old_ids)
        try:
            _delete_history_ids(client, [i for i in written_ids if i not in anciens])
        except Exception as e2:
            logger.error("save_hist cleanup FAILED user=%s: %s", user_id, e2)
        _cache_invalidate(f"hist:{user_id}")
        raise

    gardes = set(written_ids)
    _delete_history_ids(client, [i for i in old_ids if i not in gardes])
    _cache_invalidate(f"hist:{user_id}")


def ajouter_lignes(user_id: str, rows: list[dict]) -> int:
    """Ajoute des lignes en lots de 500, sans rien effacer (import Hevy/Strong :
    une requête par exercice en ferait 900 pour trois ans). Un lot qui échoue
    lève, les précédents restent."""
    client = get_client()
    payload = _series_distinctes([_row_to_supabase(user_id, {**r, "Date": _norm_date(r["Date"])})
                                  for r in rows or []])
    try:
        for i in range(0, len(payload), 500):
            # Séries déjà présentes laissées telles quelles : réimporter le
            # même fichier, même interrompu au milieu, ne double rien.
            if _insert_history(client, payload[i:i + 500], par_cle=True, ignorer=True) is None:
                _insert_history(client, payload[i:i + 500])
    finally:
        _cache_invalidate(f"hist:{user_id}")
    return len(payload)
