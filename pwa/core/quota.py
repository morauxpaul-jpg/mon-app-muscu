"""Quotas coach et générateur : vérifier et réserver d'un seul geste.

Les deux quotas étaient vérifiés AVANT l'appel à l'IA et comptés APRÈS (ou
écrits depuis une lecture faite plus tôt) : dix requêtes lancées en même
temps passaient toutes le contrôle (audit du 03/10, M8 — coût API).

Un verrou par utilisateur met la vérification et la réservation en file, et le
nombre d'appels en cours est un compteur. Les deux vivent dans `core/partage.py` :
communs à toutes les instances quand Redis est configuré, sinon à ce processus
(une instance, comme avant).
"""
from core import partage

# Une réservation oubliée (instance tuée pendant l'appel à l'IA) tombe seule :
# l'appel le plus long est borné à 150 s (core/taches_ia.py).
RESERVATION_TTL = 300


def verrou(nom: str, user_id: str):
    return partage.verrou("quota", nom, user_id)


def _cle(nom: str, user_id: str) -> str:
    return f"encours:{nom}:{user_id}"


def en_cours(nom: str, user_id: str) -> int:
    """Appels réservés et pas encore terminés."""
    return partage.valeur(_cle(nom, user_id))


def reserver(nom: str, user_id: str, compter, limite: int) -> bool:
    """Réserve une unité si ce que `compter()` lit en base, plus les appels
    déjà en cours, reste sous `limite`. `compter` est appelé SOUS le verrou :
    une lecture faite avant pouvait déjà être dépassée."""
    with verrou(nom, user_id):
        utilises = int(compter() or 0)
        if utilises + en_cours(nom, user_id) >= limite:
            return False
        partage.ajouter(_cle(nom, user_id), 1, RESERVATION_TTL)
        return True


def liberer(nom: str, user_id: str) -> None:
    """Fin de l'appel. Une réussite est déjà écrite en base (événement
    synchrone, core/analytics.py) : la réservation peut tomber."""
    partage.ajouter(_cle(nom, user_id), -1, RESERVATION_TTL)
