"""Rattacher les séries anciennes à l'identifiant de leur exercice.

Une série écrite depuis la migration v42 porte `exercise_id` (core/exercice_ids.py).
Les plus anciennes n'ont que leur nom. Quand l'éditeur renomme un exercice et
qu'on répond « c'est le même », ses séries sans identifiant le reçoivent :
elles suivent alors l'exercice sous son nouveau nom, sans que leur nom stocké
soit réécrit (ce que faisait `rename_exercise_rows`, et ce qu'il fait encore
quand la base n'a pas la colonne).
"""
import logging

from core import db_historique
from core.db_base import _cache_invalidate, _fetch_all, get_client
from core.exercice_ids import pour_serie, valide

logger = logging.getLogger(__name__)


def _variante(exercice: str, ancien: str):
    """« Curl (Haltères) » pour l'ancien nom « Curl » → "Haltères" ; le nom
    exact → "" ; un autre exercice → None."""
    if exercice == ancien:
        return ""
    prefixe = ancien + " ("
    if exercice.startswith(prefixe) and exercice.endswith(")"):
        return exercice[len(prefixe):-1]
    return None


def marquer_series(user_id: str, ancien: str, exo_id: str) -> int | None:
    """Donne `exo_id` aux séries de `ancien` (et de ses variantes) qui n'ont pas
    d'identifiant. Rend le nombre de séries qui suivent désormais l'exercice,
    ou None si la base n'a pas encore la colonne (migration v42)."""
    if not valide(exo_id) or not ancien or not db_historique._COLONNES["exercise_id"]:
        return None
    client = get_client()
    try:
        lignes = _fetch_all(lambda: client.table("history").select("id,exercice,exercise_id")
                            .eq("user_id", user_id).order("id"))
    except Exception as e:
        if "exercise_id" not in str(e).lower():
            raise
        logger.warning("history: colonne exercise_id absente (v42) — renommage par le nom")
        db_historique._COLONNES["exercise_id"] = False
        return None
    par_valeur: dict = {}
    suivent = 0
    for r in lignes:
        v = _variante(str(r.get("exercice") or ""), ancien)
        if v is None:
            continue
        suivent += 1
        if not r.get("exercise_id"):
            par_valeur.setdefault(pour_serie(exo_id, v), []).append(r["id"])
    for valeur, ids in par_valeur.items():
        for i in range(0, len(ids), 200):
            q = client.table("history").update({"exercise_id": valeur}).eq("user_id", user_id)
            q.in_("id", ids[i:i + 200]).execute()
    _cache_invalidate(f"hist:{user_id}")
    return suivent
