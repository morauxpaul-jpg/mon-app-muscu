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


# ── Cache ──────────────────────────────────────────────────────────────
def clear_user_cache():
    """Invalide le cache mémoire de l'utilisateur courant (hist + prog)."""
    db.clear_user_cache(_uid())


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


# ── Onboarding (Phase 4) ────────────────────────────────────────────────
def get_onboarding():
    return db.get_onboarding(_uid())


def save_onboarding(fields):
    return db.save_onboarding(_uid(), fields)


# ── Nutrition (Prompt C) ────────────────────────────────────────────────
def list_nutrition(date_str):
    return db.list_nutrition(_uid(), date_str)


def insert_nutrition(row):
    return db.insert_nutrition(_uid(), row)


def delete_nutrition(entry_id):
    return db.delete_nutrition(_uid(), entry_id)


def sum_nutrition_day(date_str):
    return db.sum_nutrition_day(_uid(), date_str)


# ── Coach IA (historique) ───────────────────────────────────────────────
def list_coach_messages(limit=50):
    return db.list_coach_messages(_uid(), limit)


def insert_coach_message(role, content):
    return db.insert_coach_message(_uid(), role, content)


def clear_coach_messages():
    return db.clear_coach_messages(_uid())


# ── Tier (Prompt D — paywall préparé, non activé) ───────────────────────
def is_premium() -> bool:
    """True si l'utilisateur courant est tier 'vip'. Pour l'instant tout le
    monde est free — mais les templates peuvent déjà gater des features."""
    try:
        profile = db.get_profile(_uid()) or {}
    except Exception:
        return False
    return (profile.get("tier") or "free").strip().lower() == "vip"
