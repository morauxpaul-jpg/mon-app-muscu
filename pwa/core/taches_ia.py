"""Appels IA longs en tâche de fond.

Générer un programme prend 10 à 25 s. L'appel tenait un des 16 fils du
serveur pendant tout ce temps : cinq générations simultanées et le tiers des
fils attendait une IA, pendant que les autres utilisateurs patientaient pour
une simple page (audit du 03/10, I11).

Désormais la requête lance la tâche dans un petit groupe de fils dédié, attend
au plus `ATTENTE_REQUETE` secondes (une erreur immédiate — clé absente, quota —
revient ainsi directement), puis rend la main avec un identifiant. La page
interroge ensuite `lire()` jusqu'au résultat.

L'appel tourne dans l'instance qui l'a lancé, mais son ÉTAT (en cours, résultat)
est rangé dans `core/partage.py` : avec Redis et plusieurs instances, la page
qui interroge peut tomber sur n'importe laquelle. Sans Redis, l'état reste dans
le processus (une instance). Une instance qui meurt pendant l'appel laisse une
tâche « en cours » que `DUREE_MAX` finit par déclarer perdue ; le quota,
compté sur les réussites, n'est pas entamé.
"""
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from core import partage

ATTENTE_REQUETE = 2.0      # secondes qu'une requête attend avant de rendre la main
DUREE_MAX = 150.0          # au-delà, une tâche est déclarée perdue
CONSERVATION = 30 * 60     # un résultat reste lisible 30 min
FILS = 3                   # appels IA simultanés par instance (le reste attend son tour)
SONDAGE = 0.2              # attente d'une tâche lancée par une autre instance

_EXEC = ThreadPoolExecutor(max_workers=FILS, thread_name_prefix="tache-ia")
_FINIS: dict = {}          # tid → Event, pour les tâches lancées ICI (réveil immédiat)
_VERROU = threading.Lock()


def _cle(tid: str) -> str:
    return f"tache:{tid}"


def _cle_en_cours(user_id: str, genre: str) -> str:
    return f"tache-en-cours:{genre}:{user_id}"


def en_cours(user_id: str, genre: str):
    """Identifiant d'une tâche de ce genre déjà en cours pour ce compte, ou None."""
    ref = partage.lire(_cle_en_cours(user_id, genre)) or {}
    tid = ref.get("tid")
    t = partage.lire(_cle(tid)) if tid else None
    if t and t["statut"] == "encours" and time.time() - t["debut"] <= DUREE_MAX:
        return tid
    return None


def lancer(user_id: str, genre: str, fonction, app=None) -> str:
    """Lance `fonction()` → (corps: dict, code HTTP) en tâche de fond.

    `app` (l'application Flask) ouvre un contexte d'application dans le fil :
    la fonction ne doit dépendre ni de `request` ni de `g`."""
    tid = uuid.uuid4().hex
    fini = threading.Event()
    etat = {"user_id": user_id, "genre": genre, "statut": "encours", "debut": time.time()}
    partage.ecrire(_cle(tid), etat, CONSERVATION)
    partage.ecrire(_cle_en_cours(user_id, genre), {"tid": tid}, DUREE_MAX)
    with _VERROU:
        _FINIS[tid] = fini

    def _executer():
        try:
            if app is not None:
                with app.app_context():
                    corps, code = fonction()
            else:
                corps, code = fonction()
        except Exception:  # la fonction rend ses erreurs ; ceci est un filet
            corps, code = {"error": "La génération a échoué. Réessaie."}, 500
        partage.ecrire(_cle(tid), {**etat, "statut": "fini", "corps": corps, "code": code,
                                   "fin": time.time()}, CONSERVATION)
        if (partage.lire(_cle_en_cours(user_id, genre)) or {}).get("tid") == tid:
            partage.supprimer(_cle_en_cours(user_id, genre))
        with _VERROU:
            _FINIS.pop(tid, None)
        fini.set()

    _EXEC.submit(_executer)
    return tid


def attendre(tid: str, delai: float) -> None:
    """Attend la fin d'une tâche au plus `delai` secondes. Lancée ici : réveil
    immédiat. Lancée par une autre instance : sondage du stockage partagé."""
    with _VERROU:
        fini = _FINIS.get(tid)
    if fini is not None:
        fini.wait(delai)
        return
    limite = time.monotonic() + delai
    while time.monotonic() < limite:
        t = partage.lire(_cle(tid))
        if t is None or t["statut"] == "fini":
            return
        time.sleep(min(SONDAGE, max(0.0, limite - time.monotonic())))


def lire(tid: str, user_id: str):
    """État d'une tâche de ce compte : (corps, code HTTP), ou None si inconnue.
    En cours : ({"statut": "encours", "tache": id, "ecoule": s}, 202)."""
    t = partage.lire(_cle(tid))
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
