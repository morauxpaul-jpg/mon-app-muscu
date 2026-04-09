"""Façade Flask au-dessus de core.db.

Les routes existantes appelaient `core.sheets.get_hist()` sans paramètre. Pour
garder les blueprints inchangés après la migration Supabase, ce module expose
les mêmes signatures (sans `user_id`) et lit l'utilisateur courant depuis
`flask.g.user_id`, qui est posé par le `before_request` de `app.py` après
vérification de la session.

Chaque appel traverse donc : route → core.data → core.db (service_role +
filtre `user_id` explicite). Toute route qui oublierait d'être protégée et
appellerait ces fonctions lèverait immédiatement une RuntimeError — c'est la
garde côté applicatif qui remplace le RLS Supabase.
"""
from flask import g

from . import db


def _uid() -> str:
    uid = getattr(g, "user_id", None)
    if not uid:
        raise RuntimeError(
            "core.data appelé sans g.user_id — la route n'est pas protégée "
            "par le before_request d'auth."
        )
    return uid


# ── Historique ──────────────────────────────────────────────────────────
def get_hist():
    return db.get_hist(_uid())


def save_hist(rows):
    return db.save_hist(_uid(), rows)


# ── Programme ───────────────────────────────────────────────────────────
def get_prog():
    return db.get_prog(_uid())


def save_prog(prog_dict):
    return db.save_prog(_uid(), prog_dict)


# ── Opérations ciblées ──────────────────────────────────────────────────
def replace_exo_rows(semaine, seance, exercice, new_rows):
    return db.replace_exo_rows(_uid(), semaine, seance, exercice, new_rows)


def delete_exo_rows(semaine, seance, exercice):
    return db.delete_exo_rows(_uid(), semaine, seance, exercice)


def delete_session_rows(semaine, seance):
    return db.delete_session_rows(_uid(), semaine, seance)


def mark_session_missed(semaine, seance_name, date_str):
    return db.mark_session_missed(_uid(), semaine, seance_name, date_str)


# ── Profil (Phase 4) ────────────────────────────────────────────────────
def get_profile():
    return db.get_profile(_uid())


def save_profile(fields):
    return db.save_profile(_uid(), fields)
