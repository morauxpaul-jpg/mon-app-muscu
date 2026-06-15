"""Cron de relance push des inactifs — exécutable en ligne de commande.

Deux façons de planifier la relance (choisir l'une) :

1. Railway cron (recommandé) : créer un service cron qui lance
       python cron_reactivation.py
   avec un schedule (ex. "0 17 * * *" = tous les jours à 17h UTC).
   Le service partage les mêmes variables d'env (Supabase + VAPID).

2. Scheduler HTTP externe (cron-job.org, GitHub Actions…) :
       curl -X POST -H "X-Cron-Secret: $CRON_SECRET" https://<domaine>/tasks/reactivation
   (cf. routes/push.py:cron_reactivation)

Ce script n'a PAS besoin du serveur Flask : il appelle directement la même
logique (core.push.run_reactivation_push). Code de sortie 0 si OK, 1 sinon.
"""
import logging
import sys

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("cron_reactivation")


def main() -> int:
    from core import push as core_push

    if not core_push.is_configured():
        logger.error("Push non configuré (VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY absents).")
        return 1

    result = core_push.run_reactivation_push(min_days=3, max_days=30)
    logger.info("Relance terminée : %s", result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
