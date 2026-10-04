"""Appels IA longs en tâche de fond.

Générer un programme prend 10 à 25 s. L'appel tenait un des 16 fils du
serveur pendant tout ce temps : cinq générations simultanées et le tiers des
fils attendait une IA, pendant que les autres utilisateurs patientaient pour
une simple page (audit du 03/10, I11).

Désormais la requête lance la tâche dans un petit groupe de fils dédié, attend
au plus `ATTENTE_REQUETE` secondes (une erreur immédiate — clé absente, quota —
revient ainsi directement), puis rend la main avec un identifiant. La page
interroge ensuite `lire()` jusqu'au résultat.

Mémoire du processus seulement, comme le cache et les verrous (une instance,
railway.json). Un redémarrage perd les tâches en cours : la page reçoit
« introuvable » et propose de relancer — le quota, compté sur les réussites,
n'est pas entamé.
"""
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

ATTENTE_REQUETE = 2.0      # secondes qu'une requête attend avant de rendre la main
DUREE_MAX = 150.0          # au-delà, une tâche est déclarée perdue
CONSERVATION = 30 * 60     # un résultat reste lisible 30 min
FILS = 3                   # appels IA simultanés au plus (le reste attend son tour)

_EXEC = ThreadPoolExecutor(max_workers=FILS, thread_name_prefix="tache-ia")
_TACHES: dict = {}
_VERROU = threading.Lock()


def _purger(maintenant: float) -> None:
    for tid in [t for t, v in _TACHES.items() if maintenant - v["debut"] > CONSERVATION]:
        _TACHES.pop(tid, None)


def en_cours(user_id: str, genre: str):
    """Identifiant d'une tâche de ce genre déjà en cours pour ce compte, ou None."""
    with _VERROU:
        for tid, t in _TACHES.items():
            if t["user_id"] == user_id and t["genre"] == genre and t["statut"] == "encours":
                return tid
    return None


def lancer(user_id: str, genre: str, fonction, app=None) -> str:
    """Lance `fonction()` → (corps: dict, code HTTP) en tâche de fond.

    `app` (l'application Flask) ouvre un contexte d'application dans le fil :
    la fonction ne doit dépendre ni de `request` ni de `g`."""
    tid = uuid.uuid4().hex
    fini = threading.Event()
    with _VERROU:
        _purger(time.time())
        _TACHES[tid] = {"user_id": user_id, "genre": genre, "statut": "encours",
                        "debut": time.time(), "corps": None, "code": None, "fini": fini}

    def _executer():
        try:
            if app is not None:
                with app.app_context():
                    corps, code = fonction()
            else:
                corps, code = fonction()
        except Exception:  # la fonction rend ses erreurs ; ceci est un filet
            corps, code = {"error": "La génération a échoué. Réessaie."}, 500
        with _VERROU:
            t = _TACHES.get(tid)
            if t is not None:
                t.update(statut="fini", corps=corps, code=code, fin=time.time())
        fini.set()

    _EXEC.submit(_executer)
    return tid


def attendre(tid: str, delai: float) -> None:
    with _VERROU:
        t = _TACHES.get(tid)
    if t is not None:
        t["fini"].wait(delai)


def lire(tid: str, user_id: str):
    """État d'une tâche de ce compte : (corps, code HTTP), ou None si inconnue.
    En cours : ({"statut": "encours", "tache": id, "ecoule": s}, 202)."""
    with _VERROU:
        t = _TACHES.get(tid)
        if t is None or t["user_id"] != user_id:
            return None
        if t["statut"] == "fini":
            return t["corps"], t["code"]
        ecoule = time.time() - t["debut"]
    if ecoule > DUREE_MAX:
        return {"error": "La génération a pris trop de temps. Réessaie."}, 504
    return {"statut": "encours", "tache": tid, "ecoule": round(ecoule, 1)}, 202


def reponse(tid: str, user_id: str, delai: float | None = None):
    """Attend jusqu'à `delai` (par défaut ATTENTE_REQUETE) puis rend l'état."""
    attendre(tid, ATTENTE_REQUETE if delai is None else delai)
    return lire(tid, user_id) or ({"error": "Génération introuvable. Relance-la."}, 404)
