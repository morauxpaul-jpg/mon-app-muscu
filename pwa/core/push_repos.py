"""Fin du repos annoncée par le serveur, écran éteint compris.

Retour du 14/10 : « notification qui ne s'affiche pas toujours, quand
j'éteins l'écran je n'ai rien ». Dans l'app installée depuis Chrome, la fin
du repos reposait sur un minuteur du téléphone (page, puis service worker) :
écran éteint, le téléphone le gèle, rien ne part. Seul un push venu du
serveur réveille le téléphone.

Le navigateur annonce donc chaque repos (« fini dans 90 s ») ; ce module
envoie le push au bon moment, en urgence haute et avec une durée de vie
courte. Un nouveau repos, un « Passer » ou la fin de séance l'annulent.

Plusieurs instances : le repos en cours est écrit dans l'état partagé
(core/partage.py, Redis en production). Au moment d'envoyer, l'instance qui
l'a programmé vérifie qu'il est toujours le dernier : une annulation reçue
par une autre instance est respectée. Un redémarrage perd les repos en
cours : le téléphone garde ses propres rappels, comme avant.
"""
import hashlib
import heapq
import logging
import threading
import time
import uuid

from core import partage
from core import push

logger = logging.getLogger(__name__)

DELAI_MAX = 15 * 60       # au-delà, ce n'est plus un repos entre deux séries
TTL_PUSH = 120            # livré plus de deux minutes en retard : inutile
_file = []                # (fin, jeton, clé, abonnement, nom, url), triée par fin
_cond = threading.Condition()
_fil = None


def _cle(user_id, endpoint):
    """Un repos à la fois par appareil (un abonnement = un appareil)."""
    return "repos:" + hashlib.sha256(f"{user_id}|{endpoint}".encode()).hexdigest()[:32]


def programmer(user_id, abonnement, dans, nom="", url="/seance", maintenant=None, demarrer=True):
    """Programme le push de fin de repos dans `dans` secondes. Remplace le
    repos précédent de cet appareil. Rend le jeton, ou None si la durée
    n'est pas celle d'un repos."""
    try:
        dans = float(dans)
    except (TypeError, ValueError):
        return None
    if not (0 < dans <= DELAI_MAX):
        return None
    maintenant = time.time() if maintenant is None else maintenant
    jeton = uuid.uuid4().hex
    cle = _cle(user_id, abonnement.get("endpoint") or "")
    partage.ecrire(cle, jeton, ttl=dans + 60)        # le dernier programmé gagne
    with _cond:
        heapq.heappush(_file, (maintenant + dans, jeton, cle, abonnement,
                               str(nom or "")[:60], url or "/seance"))
        _cond.notify()
    if demarrer:
        _demarrer()
    return jeton


def annuler(user_id, endpoint):
    partage.supprimer(_cle(user_id, endpoint))


def envoyer_les_echus(maintenant=None):
    """Envoie les repos arrivés à leur fin et toujours d'actualité. Rend le
    nombre de pushs envoyés (sert aux tests ; le fil l'appelle en boucle)."""
    maintenant = time.time() if maintenant is None else maintenant
    echus = []
    with _cond:
        while _file and _file[0][0] <= maintenant:
            echus.append(heapq.heappop(_file))
    envoyes = 0
    for _fin, jeton, cle, abonnement, nom, url in echus:
        if partage.lire(cle) != jeton:
            continue                       # annulé, ou remplacé par un repos plus récent
        partage.supprimer(cle)
        corps = f"{nom} : série suivante" if nom else "C'est reparti, série suivante"
        resultat = push.send_push(abonnement, {
            "title": "Repos terminé", "body": corps, "url": url, "tag": "rest-timer",
        }, ttl=TTL_PUSH, urgence="high")
        if resultat == "ok":
            envoyes += 1
        else:
            logger.info("push de fin de repos : %s", resultat)
    return envoyes


def _boucle():
    while True:
        with _cond:
            while not _file:
                _cond.wait()
            attente = _file[0][0] - time.time()
            if attente > 0:
                _cond.wait(timeout=min(attente, 30))
                continue
        try:
            envoyer_les_echus()
        except Exception as e:             # le fil ne doit jamais mourir
            logger.error("push de fin de repos : %s", e)


def _demarrer():
    global _fil
    with _cond:
        if _fil is None or not _fil.is_alive():
            _fil = threading.Thread(target=_boucle, name="push-repos", daemon=True)
            _fil.start()
