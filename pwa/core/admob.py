"""Identifiants AdMob : jamais d'annonces de test en production sans le dire.

Les défauts étaient les identifiants de TEST de Google : tant que les vraies
variables manquaient sur Railway, l'app native affichait des pubs de
démonstration qui ne rapportent rien, sans que personne ne le remarque
(audit du 03/10, M6).

Désormais :
* en local, les identifiants de test restent le défaut (développement) ;
* en production, des identifiants absents ou de test **coupent** les pubs
  (rien n'est affiché plutôt qu'une pub qui ne paie pas), le démarrage le
  journalise en CRITIQUE et la console admin l'affiche ;
* `ADMOB_TEST=1` autorise sciemment les pubs de test en production (build
  interne).
"""
import logging
import os

logger = logging.getLogger(__name__)

TEST_BANNIERE = "ca-app-pub-3940256099942544/6300978111"
TEST_INTERSTITIEL = "ca-app-pub-3940256099942544/1033173712"
EDITEUR_TEST = "ca-app-pub-3940256099942544"     # éditeur de démonstration de Google


def en_production(env=None) -> bool:
    """Même marqueur que app.py (`_IS_PROD`) : variables posées par Railway."""
    env = os.environ if env is None else env
    return bool(env.get("RAILWAY_ENVIRONMENT") or env.get("RAILWAY_PROJECT_ID"))


def _reel(valeur: str) -> bool:
    v = (valeur or "").strip()
    return v.startswith("ca-app-pub-") and not v.startswith(EDITEUR_TEST) and "/" in v


def identifiants(en_prod: bool | None = None, env=None) -> dict:
    """{banner, interstitial, etat} — etat : "reel", "test" ou "coupe"."""
    env = os.environ if env is None else env
    if en_prod is None:
        en_prod = en_production(env)
    banniere = (env.get("ADMOB_BANNER_ID") or "").strip()
    inter = (env.get("ADMOB_INTERSTITIAL_ID") or "").strip()
    if _reel(banniere):
        return {"banner": banniere, "interstitial": inter if _reel(inter) else "", "etat": "reel"}
    if not en_prod or env.get("ADMOB_TEST") == "1":
        return {"banner": TEST_BANNIERE, "interstitial": TEST_INTERSTITIEL, "etat": "test"}
    return {"banner": "", "interstitial": "", "etat": "coupe"}


def verifier_au_demarrage(en_prod: bool, env=None) -> dict:
    ids = identifiants(en_prod, env)
    if ids["etat"] == "coupe":
        logger.critical("AdMob : identifiants réels absents (ADMOB_BANNER_ID, ADMOB_INTERSTITIAL_ID) — "
                        "pubs COUPÉES dans l'app native. Définis-les dans les variables Railway.")
    elif ids["etat"] == "test" and en_prod:
        logger.warning("AdMob : identifiants de TEST en production (ADMOB_TEST=1) — aucune recette.")
    elif ids["etat"] == "reel" and not ids["interstitial"]:
        logger.warning("AdMob : ADMOB_INTERSTITIAL_ID absent ou de test — interstitiel désactivé.")
    return ids
