"""Réglages gunicorn, lus automatiquement (gunicorn démarre dans `pwa/`).

Nombre de processus : `WEB_CONCURRENCY` (2, 3…) n'est appliqué que si
`REDIS_URL` est une vraie URL Redis. Sans Redis, le cache, les verrous et les
tâches IA vivent dans la mémoire du processus (`core/partage.py`) : deux
processus serviraient chacun leur version de l'historique (audit du 30/09, I8).
Une variable d'environnement seule ne peut donc pas casser l'app.

Le reste (fils, délais, journaux) est sur la ligne de commande, railway.json.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.partage import processus_annonces, url_redis  # noqa: E402

workers = processus_annonces() if url_redis() else 1
if processus_annonces() > 1 and workers == 1:
    print("gunicorn.conf: WEB_CONCURRENCY ignoré sans REDIS_URL, 1 processus.", file=sys.stderr)


# Journaux de gunicorn lui-même (« Starting gunicorn », « Booting worker ») :
# tout partait sur la sortie d'erreur, que Railway range en « error »
# (audit du 06/10, m5). Même partage que l'app (app.py) : INFO sur la
# sortie standard, WARNING et au-delà sur la sortie d'erreur.
import logging  # noqa: E402

from gunicorn.glogging import Logger as _Logger  # noqa: E402


class JournalScinde(_Logger):
    def setup(self, cfg):
        super().setup(cfg)
        for h in list(self.error_log.handlers):
            if type(h) is logging.StreamHandler and h.stream is sys.stderr:
                h.setLevel(logging.WARNING)
                sortie = logging.StreamHandler(sys.stdout)
                sortie.setFormatter(h.formatter)
                sortie.addFilter(lambda r: r.levelno < logging.WARNING)
                self.error_log.addHandler(sortie)


logger_class = JournalScinde
