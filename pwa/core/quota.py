"""Quotas coach et générateur : vérifier et réserver d'un seul geste.

Les deux quotas étaient vérifiés AVANT l'appel à l'IA et comptés APRÈS (ou
écrits depuis une lecture faite plus tôt) : dix requêtes lancées en même
temps passaient toutes le contrôle (audit du 03/10, M8 — coût API).

Un verrou par utilisateur met la vérification et la réservation en file. Il
suffit tant que l'app tourne en UN processus, ce qui est déjà la condition du
cache (railway.json, CONTEXT.md) ; à plusieurs instances, il faudra un
incrément atomique côté base.
"""
import threading

_VERROUS = [threading.Lock() for _ in range(64)]
_EN_COURS: dict = {}          # (nom, user_id) → appels en cours
_ETAT = threading.Lock()


def verrou(nom: str, user_id: str):
    return _VERROUS[hash((nom, user_id)) % len(_VERROUS)]


def reserver(nom: str, user_id: str, compter, limite: int) -> bool:
    """Réserve une unité si ce que `compter()` lit en base, plus les appels
    déjà en cours, reste sous `limite`. `compter` est appelé SOUS le verrou :
    une lecture faite avant pouvait déjà être dépassée."""
    cle = (nom, user_id)
    with verrou(nom, user_id):
        utilises = int(compter() or 0)
        with _ETAT:
            if utilises + _EN_COURS.get(cle, 0) >= limite:
                return False
            _EN_COURS[cle] = _EN_COURS.get(cle, 0) + 1
            return True


def liberer(nom: str, user_id: str) -> None:
    """Fin de l'appel. Une réussite est déjà écrite en base (événement
    synchrone, core/analytics.py) : la réservation peut tomber."""
    cle = (nom, user_id)
    with _ETAT:
        _EN_COURS[cle] = max(0, _EN_COURS.get(cle, 0) - 1)
