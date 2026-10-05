"""Façade Flask au-dessus de core.db.

Les routes appelaient historiquement `get_hist()` sans paramètre (ancien backend Sheets). Pour
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


# ── Réglages (table `reglages`, v45) ───────────────────────────────────
def get_reglages(prog=None):
    """Les réglages de l'utilisateur courant ; `prog` sert de repli."""
    return db.lire_reglages(_uid(), prog)


def save_reglages(valeurs):
    """False si la table manque (base en retard) : l'appelant range alors
    les réglages dans le programme."""
    return db.ecrire_reglages(_uid(), valeurs)


# ── Historique ──────────────────────────────────────────────────────────
def get_hist(echauffement=False):
    """L'historique, chaque série identifiée sous le nom ACTUEL de son
    exercice (core/exercice_ids.py) : renommer garde le passé. Sans les séries
    d'échauffement, sauf `echauffement=True` (carte de séance, export)."""
    from core.exercice_ids import afficher_selon_programme
    uid = _uid()
    return afficher_selon_programme(db.get_hist(uid, echauffement), db.lire_prog(uid))


def echauffements_disponibles() -> bool:
    """La base sait-elle les garder à part (migration v43) ? Lu après une
    lecture de l'historique : une colonne absente l'aura signalé."""
    return bool(db._COLONNES.get("type_serie"))


def echauffements_du_jour(date_str):
    """Les séries d'échauffement d'une date (carte de séance)."""
    from core.hist import est_echauffement
    return [r for r in get_hist(echauffement=True)
            if est_echauffement(r) and r.get("Date") == date_str]


def save_hist(rows):
    return db.save_hist(_uid(), rows)


# ── Programme ───────────────────────────────────────────────────────────
def get_prog():
    return db.get_prog(_uid())


def save_prog(prog_dict):
    return db.save_prog(_uid(), prog_dict)


def save_prog_body(body):
    """Remplace le CORPS du programme (séances + planning + dossiers) en
    conservant toutes les données personnelles (badges, record de streak,
    exos perso, défis…). Cf. db.replace_program_body."""
    uid = _uid()
    merged = db.replace_program_body(db.get_prog(uid), body)
    db.save_prog(uid, merged)
    return merged


# ── Opérations ciblées ──────────────────────────────────────────────────
# Le ciblage de semaine se fait par date (plage lun→dim), plus par n° ISO.
def replace_exo_rows(date_str, seance, exercice, new_rows, exo_id=None):
    return db.replace_exo_rows(_uid(), date_str, seance, exercice, new_rows, exo_id)


def ajouter_lignes(rows):
    return db.ajouter_lignes(_uid(), rows)


def append_exo_rows(date_str, seance, exercice, new_rows):
    return db.append_exo_rows(_uid(), date_str, seance, exercice, new_rows)


def delete_exo_rows(date_str, seance, exercice, serie=None, exo_id=None):
    return db.delete_exo_rows(_uid(), date_str, seance, exercice, serie, exo_id)


def delete_session_rows(date_str, seance):
    return db.delete_session_rows(_uid(), date_str, seance)




# ── Profil (Phase 4) ────────────────────────────────────────────────────
def get_profile():
    return db.get_profile(_uid())


def save_profile(fields):
    return db.save_profile(_uid(), fields)


def set_newsletter_optin(opt_in, email=""):
    return db.set_newsletter_optin(_uid(), opt_in, email)


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


# ── Poids corporel ──────────────────────────────────────────────────────
def list_body_weight(limit=400):
    return db.list_body_weight(_uid(), limit)


def upsert_body_weight(date_str, poids_kg):
    return db.upsert_body_weight(_uid(), date_str, poids_kg)


def delete_body_weight(date_str):
    return db.delete_body_weight(_uid(), date_str)


def insert_nutrition_rows(rows):
    return db.insert_nutrition_rows(_uid(), rows)


def get_nutrition(entry_id):
    return db.get_nutrition(_uid(), entry_id)


def update_nutrition(entry_id, fields):
    return db.update_nutrition(_uid(), entry_id, fields)


def list_nutrition_recents(since):
    return db.list_nutrition_recents(_uid(), since)


def delete_nutrition(entry_id):
    return db.delete_nutrition(_uid(), entry_id)


def sum_nutrition_day(date_str):
    return db.sum_nutrition_day(_uid(), date_str)


def sum_nutrition_range(date_from, date_to):
    return db.sum_nutrition_range(_uid(), date_from, date_to)


# ── Coach IA (historique + conversations) ───────────────────────────────
def list_coach_messages(conversation_id=None, limit=50):
    return db.list_coach_messages(_uid(), conversation_id, limit)


def insert_coach_message(role, content, conversation_id=None):
    return db.insert_coach_message(_uid(), role, content, conversation_id)


def clear_coach_messages():
    return db.clear_coach_messages(_uid())


def list_coach_conversations(limit=50):
    return db.list_coach_conversations(_uid(), limit)


def create_coach_conversation(title="Nouvelle conversation"):
    return db.create_coach_conversation(_uid(), title)


def rename_coach_conversation(conversation_id, title):
    return db.rename_coach_conversation(_uid(), conversation_id, title)


def touch_coach_conversation(conversation_id):
    return db.touch_coach_conversation(_uid(), conversation_id)


def delete_coach_conversation(conversation_id):
    return db.delete_coach_conversation(_uid(), conversation_id)


# ── Bilans de séance (table session_notes, migration v34) ───────────────
def upsert_session_note(date_str, seance, rating, comment, duration_min=None):
    return db.upsert_session_note(_uid(), date_str, seance, rating, comment,
                                  duration_min)


def get_session_note(date_str, seance):
    return db.get_session_note(_uid(), date_str, seance)


def list_session_notes():
    return db.list_session_notes(_uid())


def rename_session_notes(old_name, new_name):
    return db.rename_session_notes(_uid(), old_name, new_name)


def list_all_nutrition():
    return db.list_all_nutrition(_uid())


def export_coach():
    return db.export_coach(_uid())


# ── Renommage / fusion d'exercices (UPDATE ciblé, pas de réécriture) ────
def rename_seance_rows(old_name, new_name):
    return db.rename_seance_rows(_uid(), old_name, new_name)


def rename_exercise_rows(old_names, new_name, muscle=None):
    return db.rename_exercise_rows(_uid(), old_names, new_name, muscle)


def count_exercise_rows(name):
    return db.count_exercise_rows(_uid(), name)


def marquer_series(ancien, exo_id):
    return db.marquer_series(_uid(), ancien, exo_id)


# ── Suppression de compte (exigence stores) ─────────────────────────────
def delete_user_account():
    return db.delete_user_account(_uid())
