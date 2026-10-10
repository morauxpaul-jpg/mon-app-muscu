"""Où passe le temps d'une requête : la base, Redis, ou le reste.

Audit du 06/10 (I-2) : en production, « Série faite » met 2 s côté serveur
(médiane des 37 enregistrements du 04/10) contre 0,85 s le 29/09. La cause
n'a pas pu être isolée : le traçage de l'hébergeur est coupé, et en local,
avec une base simulée, l'enregistrement ne coûte que 2 requêtes et 13 appels
Redis. Chaque requête compte donc le temps passé à attendre la base
(core/reprise_base.py) et Redis (core/partage.py) :

* en-tête `Server-Timing`, visible dans les outils du navigateur ;
* une ligne de journal pour toute requête plus lente que `SEUIL_LENT_MS`,
  qui dit lequel des deux pèse. La prochaine séance réelle tranchera.
"""
import logging
import time

from flask import g, has_request_context

logger = logging.getLogger(__name__)

SEUIL_LENT_MS = 800


def ajouter(source: str, secondes: float) -> None:
    """Compte un appel à `source` ('base', 'redis') pour la requête en cours."""
    if not has_request_context():
        return
    try:
        mesures = g.setdefault("chrono", {})
        n, ms = mesures.get(source, (0, 0.0))
        mesures[source] = (n + 1, ms + secondes * 1000.0)
    except Exception:  # pragma: no cover - la mesure ne casse jamais une requête
        pass


def debut() -> None:
    g.chrono_t0 = time.perf_counter()


def entete(total_ms: float, mesures: dict) -> str:
    parts = [f'{source};dur={ms:.0f};desc="{n} appel{"s" if n > 1 else ""}"'
             for source, (n, ms) in sorted(mesures.items())]
    parts.append(f"total;dur={total_ms:.0f}")
    return ", ".join(parts)


def terminer(response, methode: str, chemin: str):
    t0 = g.pop("chrono_t0", None)
    mesures = g.pop("chrono", None) or {}
    if t0 is None:
        return response
    total = (time.perf_counter() - t0) * 1000.0
    response.headers["Server-Timing"] = entete(total, mesures)
    if total >= SEUIL_LENT_MS and not chemin.startswith("/static/"):
        n_b, ms_b = mesures.get("base", (0, 0.0))
        n_r, ms_r = mesures.get("redis", (0, 0.0))
        logger.info("lent : %s %s %d ms — base %d ms (%d requêtes), redis %d ms (%d appels), "
                    "reste %d ms", methode, chemin, total, ms_b, n_b, ms_r, n_r,
                    max(0.0, total - ms_b - ms_r))
    return response
