"""Une lecture coupée en route est retentée une fois ; chaque requête est chronométrée.

Audit du 06/10 (I-3), en production le 05/10 à 06:26 UTC : la connexion
HTTP/2 vers Supabase, inactive toute la nuit, avait été fermée par l'autre
bout (`<ConnectionTerminated error_code:9 …>`). La première requête du matin a
échoué : `/seance` a répondu 503 et l'accueil s'est affiché vide. La même
requête, sur une connexion neuve, passait.

Les requêtes vers les tables passent par le client HTTP que postgrest construit
lui-même. Depuis supabase 2.33, c'est un `httpx.Client` ordinaire, nommé
`Client` dans `postgrest._sync.client` : on y substitue `ClientAvecReprise`,
et seul postgrest le voit (le client HTTP du coach IA n'est pas touché).
Jusqu'à supabase 2.8, c'était `postgrest.utils.SyncClient`, toujours importable
mais plus utilisé : modifié seul, il laissait tout passer sans reprise ni
chronométrage, sans aucune erreur. Le test de bout en bout laisse donc
postgrest construire son client, comme dans l'app. On y pose :

* une seule nouvelle tentative, pour une LECTURE (GET, HEAD) et sur une coupure
  de connexion seulement. Une écriture coupée a pu aboutir avant la coupure :
  la rejouer risquerait un doublon, elle remonte comme avant ;
* le chronométrage de chaque requête (core/chrono.py).
"""
import logging
import time

import httpx

from core import chrono

logger = logging.getLogger(__name__)

METHODES_REJOUABLES = {"GET", "HEAD"}
_installe = False


def est_coupure(e) -> bool:
    """Connexion fermée ou perdue avant la réponse — pas un délai dépassé
    (rejouer une requête lente doublerait l'attente) ni une erreur de la base."""
    if isinstance(e, (httpx.RemoteProtocolError, httpx.ConnectError,
                      httpx.ReadError, httpx.WriteError)):
        return True
    return "ConnectionTerminated" in repr(e)


def avec_reprise(envoyer, methode, *args, **kwargs):
    """Appelle `envoyer(methode, …)`, et une seconde fois si c'est une lecture
    coupée en route."""
    t0 = time.perf_counter()
    try:
        try:
            return envoyer(methode, *args, **kwargs)
        except Exception as e:
            if str(methode).upper() not in METHODES_REJOUABLES or not est_coupure(e):
                raise
            logger.warning("base : connexion coupée (%s), nouvelle tentative", type(e).__name__)
            return envoyer(methode, *args, **kwargs)
    finally:
        chrono.ajouter("base", time.perf_counter() - t0)


class ClientAvecReprise(httpx.Client):
    """Le client HTTP de postgrest, avec la reprise et le chronométrage."""

    def request(self, method, url, *args, **kwargs):
        envoyer = super().request
        return avec_reprise(envoyer, method, url, *args, **kwargs)


def installer() -> bool:
    """Branche la reprise sur le client HTTP de postgrest (une fois).

    Rend False si postgrest ne construit plus son client sous ce nom : mieux
    vaut ne rien poser que poser à côté (le test de bout en bout le signale)."""
    global _installe
    if _installe:
        return True
    try:
        from postgrest._sync import client as module_postgrest
    except ImportError:  # pragma: no cover - postgrest absent
        return False
    if getattr(module_postgrest, "Client", None) is not httpx.Client:
        logger.warning("base : client HTTP de postgrest introuvable, pas de reprise")
        return False
    module_postgrest.Client = ClientAvecReprise
    _installe = True
    return True
