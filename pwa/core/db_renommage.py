"""Renommer une séance ou un exercice dans tout l'historique.

L'historique retrouve séances et exercices par leur NOM : renommer dans le
programme sans renommer ici couperait le passé — volume, records et
progression repartiraient de zéro, sans erreur nulle part.

Depuis l'index unique de la migration v41 (une série = une clé
user/date/séance/exercice/série), renommer peut entrer en collision : fusionner
« Squat » dans « Squat barre » quand les deux ont une série 1 le même jour.
L'UPDATE groupé est alors refusé en bloc ; on retombe sur un déplacement ligne
par ligne qui donne aux séries en collision le numéro suivant libre. Rien ne
se perd, rien ne se double.
"""
import logging

from core.db_base import _cache_invalidate, _fetch_all, get_client

logger = logging.getLogger(__name__)


def _collision(err) -> bool:
    """Violation de l'index unique (PostgreSQL 23505)."""
    msg = str(err)
    return "23505" in msg or "duplicate key" in msg.lower()


def _deplacer_ligne_a_ligne(client, user_id: str, colonne: str, ancien: str, nouveau: str,
                            extra: dict) -> int:
    """Renomme `colonne` de `ancien` en `nouveau` ligne par ligne, en
    renumérotant les séries qui tomberaient sur une clé déjà prise."""
    champs = "id,date,seance,exercice,serie"
    a_bouger = _fetch_all(lambda: client.table("history").select(champs)
                          .eq("user_id", user_id).eq(colonne, ancien).order("id"))
    deja = _fetch_all(lambda: client.table("history").select(champs)
                      .eq("user_id", user_id).eq(colonne, nouveau).order("id"))
    occupe = {(r["date"], r["seance"], r["exercice"], int(r["serie"] or 1)) for r in deja}
    plus_haut: dict = {}
    for r in deja:
        g = (r["date"], r["seance"], r["exercice"])
        plus_haut[g] = max(plus_haut.get(g, 0), int(r["serie"] or 1))
    n = 0
    for r in a_bouger:
        cible = dict(r, **{colonne: nouveau})
        g = (cible["date"], cible["seance"], cible["exercice"])
        serie = int(r["serie"] or 1)
        if (*g, serie) in occupe:
            serie = max(plus_haut.get(g, 0), serie) + 1
        occupe.add((*g, serie))
        plus_haut[g] = max(plus_haut.get(g, 0), serie)
        (client.table("history").update({colonne: nouveau, "serie": serie, **extra})
         .eq("user_id", user_id).eq("id", r["id"]).execute())
        n += 1
    return n


def _renommer(user_id: str, colonne: str, ancien: str, nouveau: str, extra: dict | None = None) -> int:
    client = get_client()
    extra = extra or {}
    try:
        resp = (client.table("history").update({colonne: nouveau, **extra})
                .eq("user_id", user_id).eq(colonne, ancien).execute())
        return len(resp.data or [])
    except Exception as e:
        if not _collision(e):
            raise
        logger.info("renommage %s %r → %r : collisions, déplacement ligne à ligne", colonne, ancien, nouveau)
        return _deplacer_ligne_a_ligne(client, user_id, colonne, ancien, nouveau, extra)


def rename_seance_rows(user_id: str, old_name: str, new_name: str) -> int:
    """Renomme une séance dans tout l'historique. Retourne les lignes touchées."""
    if not old_name or old_name == new_name:
        return 0
    try:
        return _renommer(user_id, "seance", old_name, new_name)
    finally:
        _cache_invalidate(f"hist:{user_id}")


def rename_exercise_rows(user_id: str, old_names: list[str], new_name: str,
                         muscle: str | None = None) -> int:
    """Renomme (ou fusionne) des exercices dans tout l'historique. Retourne le
    nombre de lignes touchées."""
    extra = {"muscle": muscle} if muscle else {}
    count = 0
    try:
        for old in old_names:
            if old and old != new_name:
                count += _renommer(user_id, "exercice", old, new_name, extra)
    finally:
        _cache_invalidate(f"hist:{user_id}")
    return count


def count_exercise_rows(user_id: str, name: str) -> int:
    """Séries enregistrées sous ce nom d'exercice (pour proposer de les suivre)."""
    resp = (get_client().table("history").select("id")
            .eq("user_id", user_id).eq("exercice", name).limit(5000).execute())
    return len(resp.data or [])


def list_history_shape() -> list[dict]:
    """(user_id, date) de TOUTES les lignes d'historique — lecture seule.

    Sert à mesurer ce que coûte `get_hist` (`core/blob_stats.py`). Deux
    colonnes seulement : ni exercice, ni charge, ni remarque.
    """
    return _fetch_all(lambda: get_client().table("history").select("user_id,date")) or []
