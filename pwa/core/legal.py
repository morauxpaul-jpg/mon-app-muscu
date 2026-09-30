"""Informations d'éditeur affichées dans les pages légales.

L'adresse et le SIRET viennent de l'environnement (Railway) : on les
renseigne ou on les change sans déployer de code, et ils n'ont rien à faire
dans le dépôt. Absents, les pages le disent au lieu d'afficher un faux.
"""
import os

EDITEUR_NOM = "Paul Moraux"
EDITEUR_STATUT = "particulier (personne physique)"
EDITEUR_EMAIL = "muscutracker@gmail.com"


def infos_editeur() -> dict:
    return {
        "nom": EDITEUR_NOM,
        "statut": EDITEUR_STATUT,
        "email": EDITEUR_EMAIL,
        "adresse": (os.getenv("EDITEUR_ADRESSE") or "").strip() or None,
        "siret": (os.getenv("EDITEUR_SIRET") or "").strip() or None,
    }
