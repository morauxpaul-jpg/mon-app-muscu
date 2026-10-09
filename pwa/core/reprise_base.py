"""Une lecture coupée en route est retentée une fois ; chaque requête est chronométrée.

Audit du 06/10 (I-3), en production le 05/10 à 06:26 UTC : la connexion
HTTP/2 vers Supabase, inactive toute la nuit, avait été fermée par l'autre
bout (`<ConnectionTerminated error_code:9 …>`). La première requête du matin a
échoué : `/seance` a répondu 503 et l'accueil s'est affiché vide. La même
requête, sur une connexion neuve, passait.

Toutes les requêtes du client Supabase passent par `postgrest.utils.SyncClient`
(une sous-classe de `httpx.Client` propre à postgrest : le client HTTP du coach
IA n'est pas touché). On y pose :

* une seule nouvelle tentative, pour une LECTURE (GET, HEAD) et sur une coupure
  de connexion seulement. Une écriture coupée a pu aboutir avant la coupure :
  la rejouer risquerait un doublon, elle remonte comme avant ;
* le chronométrage de chaque requête (core/chrono.py).
"""
import logging
import time

from core import chrono

logger = logging.getLogger(__name__)

METHODES_REJOUABLES = {"GET", "HEAD"}
_installe = False


def est_coupure(e) -> bool:
    """Connexion fermée ou perdue avant la réponse — pas un délai dépassé
    (rejouer une requête lente doublerait l'attente) ni une erreur de la base."""
    try:
        import httpx
        if isinstance(e, (httpx.RemoteProtocolError, httpx.ConnectError,
                          httpx.ReadError, httpx.WriteError)):
            return True
    except ImportError:  # pragma: no cover
        pass
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


def installer() -> bool:
    """Branche la reprise sur le client HTTP de postgrest (une fois)."""
    global _installe
    if _installe:
        return True
    try:
        import httpx
        from postgrest.utils import SyncClient
    except ImportError:  # pragma: no cover - postgrest absent
        return False

    def request(self, method, url, *args, **kwargs):
        return avec_reprise(lambda m, *a, **k: httpx.Client.request(self, m, *a, **k),
                            method, url, *args, **kwargs)

    SyncClient.request = request
    _installe = True
    return True
