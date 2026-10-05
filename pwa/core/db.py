"""Couche d'accès Supabase — la carte, et l'API publique de la couche données.

Ce module ne contient plus de code : il réunit sous un seul nom les dix
modules qui se partagent le travail. Les routes continuent donc à écrire
`from core import db as core_db` sans rien savoir du découpage.

    db_base         connexion Supabase, cache mémoire, pagination PostgREST
    db_historique   les séries enregistrées — la source de vérité de l'app
    db_historique_lots  réécriture complète et ajout massif (sauvegarde, import)
    db_renommage    renommer une séance ou un exercice dans tout l'historique
    db_colonnes     les colonnes de `history` qu'une base en retard n'a pas encore
    db_reglages     les réglages de l'utilisateur (table `reglages`, v45)
    db_identite     rattacher les séries anciennes à l'identifiant de leur exercice (v42)
    db_programme    le programme, son planning et ses calques (blob JSON)
    db_profil       profil, onboarding, poids de corps
    db_nutrition    les repas et les sommes de macros
    db_bilans       les bilans de séance
    db_abonnement   tier PRO, Stripe, parrainage
    db_push         notifications, newsletter, relance des inactifs
    db_coach        les conversations du coach
    db_admin        statistiques, funnel, fiche et suppression d'un compte

Leurs dépendances forment un arbre : tous s'appuient sur `db_base`, et
quelques-uns sur un autre module (`db_abonnement`, `db_admin` et `db_push`
lisent le profil ; `db_push` et `db_bilans` normalisent une date avec
l'historique ; `db_historique` et `db_push` consultent `db_colonnes`).
Aucun cycle.

**Choix d'archi (Phase 3).** Le backend utilise la clé `service_role`, qui
contourne le RLS, et filtre donc manuellement **chaque** requête par
`user_id`. L'authentification se fait via Supabase Google OAuth côté client,
puis un « bridge » valide le JWT et pose `user_id` dans la session Flask.
Toutes les fonctions exposées ici exigent explicitement un `user_id` —
`core.data` est la façade qui le lit dans `flask.g` pour les routes.

Config : deux variables d'env requises
  - SUPABASE_URL
  - SUPABASE_SERVICE_ROLE_KEY   (jamais exposée au client)
"""
# flake8: noqa: F401  — ce module ne sert qu'à réexporter.

# ── connexion, cache, pagination ────────────────────────────────
from core.db_base import (
    clear_user_cache, current_client, get_client, session_id_for, use_client, vider_cache,
    _CACHE_MAX, _PAGE, _PROFILE_TTL, _SESSION_NS, _TTL, _cache_get, _cache_invalidate,
    _cache_lock, _cache_set, _continuous_week_of, _data_cache, _env, _fetch_all,
    _debuts, _lectures, _TOUT, _generations, _ranger, _cache_modifier
)

# ── les séries enregistrées ─────────────────────────────────────
from core.db_historique import (
    append_exo_rows, delete_exo_rows, delete_session_rows, get_hist, replace_exo_rows,
    _HIST_COLS_LUES, _HIST_EXT_COLS, _delete_history_ids,
    _hist_ext_supported, _insert_history, _lire_history, _nettoyer_ligne, _norm_date,
    _reporter_dans_le_cache, CLE_SERIE, _unicite, _index_absent, _series_distinctes, _append_une_fois,
    _row_to_supabase, _verrou, _COLONNES, _ids_cibles, _colonne_refusee, _replace_exo_rows, _append_exo_rows
)

from core.db_colonnes import (
    colonnes_mesures, lire_avec_mesures, sans_colonnes_absentes, _GROUPES, _noms
)
from core.db_historique_lots import ajouter_lignes, save_hist
from core.db_reglages import (
    DEFAUTS, REESSAI, ecrire_reglages, lire_reglages, reglages_pour,
    _completer, _disponible, _lignes, _marquer_absente, _oublier_absence, _table_absente
)
from core.db_identite import marquer_series, _variante
from core.db_renommage import (
    count_exercise_rows, list_history_shape, rename_exercise_rows, rename_seance_rows,
    _collision, _deplacer_ligne_a_ligne, _renommer
)

# ── le programme et son planning ────────────────────────────────
from core.db_programme import (
    PROG_BODY_KEYS, get_prog, lire_prog, list_all_program_blobs, replace_program_body, save_prog,
    _SAVE_PROG_RETRIES,
    _bases, _copy, _merge_prog, _prog_base, _prog_en_cache, _read_prog_row, _remember_base, _upsert_prog
)

# ── profil, onboarding, poids de corps ──────────────────────────
from core.db_profil import (
    delete_body_weight, get_onboarding, get_profile, list_body_weight, save_onboarding,
    save_profile, upsert_body_weight, _PROFILE_OPTIONAL_COLS, _profile_upsert
)

# ── les repas ───────────────────────────────────────────────────
from core.db_nutrition import (
    delete_nutrition, insert_nutrition, list_all_nutrition, list_nutrition, sum_nutrition_day,
    sum_nutrition_range, insert_nutrition_rows, get_nutrition, update_nutrition,
    list_nutrition_recents, COLONNES_V40, _colonne_absente, _sans_v40
)

# ── tier PRO, Stripe, parrainage ────────────────────────────────
from core.db_abonnement import (
    count_referrals, get_or_create_referral_code, get_referred_by,
    get_user_by_referral_code, get_user_by_stripe_customer, grant_vip_days,
    set_referred_by, set_stripe_customer, set_user_tier, vip_until_active, essai_restant
)

# ── notifications, newsletter, relances ─────────────────────────
from core.db_push import (
    delete_push_subscription, get_inactive_user_ids, get_inactive_users, list_all_programs,
    list_newsletter_emails, list_push_subscriptions, list_push_subscriptions_for_users,
    mark_reactivation_sent, save_push_subscription, set_newsletter_optin,
    users_trained_on, history_between_for_users, _last_activity_by_user, _row_to_subscription
)

# ── les conversations du coach ──────────────────────────────────
from core.db_coach import (
    clear_coach_messages, create_coach_conversation, delete_coach_conversation, export_coach,
    insert_coach_message, list_coach_conversations, list_coach_messages,
    rename_coach_conversation, touch_coach_conversation
)

# ── console d'administration ────────────────────────────────────
from core.db_admin import (
    auth_user_exists, delete_user_account, get_admin_stats, get_funnel_stats,
    get_user_details, insert_event, list_all_users_with_tier, purge_old_events,
    reset_user_coach_quota, EVENTS_RETENTION_DAYS,
    _FUNNEL_STEPS, _charge, _tous_les_comptes
)

# ── les bilans de séance ────────────────────────────────────────
from core.db_bilans import (
    get_session_note, list_session_notes, rename_session_notes, upsert_session_note,
    _mark_duration_unsupported, _session_duration_supported, _session_note_columns
)
