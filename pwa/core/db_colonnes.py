"""Les colonnes facultatives de `history` : celles qu'une base en retard
n'a pas encore.

Chaque migration qui ajoute une colonne à `history` laisse un moment où le
code est déployé et la base pas encore : l'app lit et écrit alors sans la
colonne, et s'en souvient pour le processus. Ce registre est partagé par
`db_historique` (lecture, écriture), `db_identite` et `db_push`.
"""
import logging

from core.db_base import _fetch_all
from core.hist import TYPE_ECHAUFFEMENT
from core.seance_cardio import COLONNES_CARDIO, vers_ancien_format

logger = logging.getLogger(__name__)

# Colonnes facultatives : `exercise_id` (v42, core/exercice_ids.py),
# `type_serie` (v43, séries d'échauffement) et le groupe « cardio » (v44 :
# duree_min, distance, calories, vitesse). Base en retard : lu et écrit sans.
_COLONNES = {"exercise_id": True, "type_serie": True, "cardio": True}   # dict partagé (façade)
_GROUPES = {"cardio": COLONNES_CARDIO}


def _noms(cle: str) -> tuple:
    return _GROUPES.get(cle, (cle,))


def _colonne_refusee(msg: str):
    """La colonne facultative qu'une erreur PostgREST désigne, ou None. Le
    manque est signalé à /admin (core/schema.py) : le repli ne le cache plus."""
    refusee = next((c for c, ok in _COLONNES.items()
                    if ok and any(n in msg for n in _noms(c))), None)
    if refusee:
        from core.schema import signaler
        signaler(msg, "history")
    return refusee


def sans_colonnes_absentes(payload: list[dict]) -> list[dict]:
    """Lignes prêtes pour la base, ramenées à ce que la base sait recevoir."""
    absentes = {c for c, ok in _COLONNES.items() if not ok}
    if "type_serie" in absentes:    # sans la v43, l'échauffement compterait comme du travail
        payload = [p for p in payload if p.get("type_serie") != TYPE_ECHAUFFEMENT]
    if "cardio" in absentes:        # sans la v44, le cardio s'écrit à l'ancienne
        payload = [vers_ancien_format(p) for p in payload]
    if absentes:
        retirees = {n for c in absentes for n in _noms(c)}
        payload = [{k: v for k, v in p.items() if k not in retirees} for p in payload]
    return payload


def colonnes_mesures() -> str:
    """Ce qu'un lecteur brut de `history` doit lire pour savoir si une ligne
    est un entraînement réel (`hist.perf_brute`)."""
    return "reps,poids" + ("," + ",".join(COLONNES_CARDIO) if _COLONNES["cardio"] else "")


def lire_avec_mesures(fabrique):
    """`_fetch_all` d'une requête construite par `fabrique(colonnes_mesures())`.
    Colonnes cardio absentes (base en retard) : relue sans, une fois pour
    toutes, comme `_lire_history`."""
    while True:
        try:
            return _fetch_all(lambda: fabrique(colonnes_mesures()))
        except Exception as e:
            if _COLONNES["cardio"] and _colonne_refusee(str(e).lower()) == "cardio":
                logger.warning("history: colonnes cardio v44 absentes — lecture sans elles")
                _COLONNES["cardio"] = False
                continue
            raise
