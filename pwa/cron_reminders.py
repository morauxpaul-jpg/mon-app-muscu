"""Cron des rappels de séance — exécutable en ligne de commande.

À lancer TOUTES LES HEURES. Le script détermine lui-même l'heure de Paris et
n'envoie qu'aux personnes qui ont choisi cette heure-là, ont une séance
planifiée aujourd'hui, et ne l'ont pas encore faite. Les autres heures ne
coûtent qu'une lecture : c'est voulu, l'heure de rappel est un réglage
personnel (6 h pour qui s'entraîne avant le travail, 20 h pour qui y va le
soir).

Deux façons de planifier (choisir l'une) :

1. Railway cron : créer un service cron qui lance
       python cron_reminders.py
   avec le schedule "0 * * * *" (au début de chaque heure).
   Le service partage les mêmes variables d'env (Supabase + VAPID).

2. Scheduler HTTP externe (cron-job.org, GitHub Actions…) :
       curl -X POST -H "X-Cron-Secret: $CRON_SECRET" https://<domaine>/tasks/reminders
   (cf. routes/push.py:cron_reminders)

Ce script n'a PAS besoin du serveur Flask : il appelle directement la même
logique (core.reminders.run_reminders). Code de sortie 0 si OK, 1 sinon.
"""
import logging
import sys

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("cron_reminders")


def main() -> int:
    from core import push as core_push
    from core import reminders

    if not core_push.is_configured():
        logger.error("Push non configuré (VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY absents).")
        return 1

    result = reminders.run_reminders()
    logger.info("Rappels terminés : %s", result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
