"""Les séries enregistrées — la table `history`.

C'est la source de vérité de l'app : les vues séance, les statistiques et le
calendrier se reconstruisent à partir de ces lignes. Une opération qui en perd
une perd un entraînement, silencieusement — d'où les tests de non-régression
qui entourent chaque fonction de ce module.
"""
import datetime as _dt
import logging

from core.db_base import (_cache_get, _cache_invalidate, _cache_set, _continuous_week_of,
                          _fetch_all, get_client, session_id_for)
from core.muscu import parse_rpe

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
# Historique des séries
# ────────────────────────────────────────────────────────────

def get_hist(user_id: str) -> list[dict]:
    """Retourne l'historique de l'user sous forme de liste de dicts
    (clés Semaine/Séance/Exercice/...), même forme que l'ancien backend."""
    key = f"hist:{user_id}"
    cached = _cache_get(key)
    if cached is not None:
        return [dict(r) for r in cached]

    client = get_client()
    rows = _lire_history(client, user_id)
    cleaned = [_nettoyer_ligne(r) for r in rows]
    _cache_set(key, cleaned)
    return [dict(r) for r in cleaned]


def _nettoyer_ligne(r: dict) -> dict:
    """Ligne `history` telle qu'en base → forme lue par l'app."""
    date_str = str(r.get("date") or "")
    # Semaine = index CONTINU recalculé depuis la date (le n° ISO stocké
    # recommence chaque année → collisions au-delà d'un an d'historique).
    # Repli sur la valeur stockée pour les rares lignes sans date.
    week = _continuous_week_of(date_str)
    if week is None:
        week = int(r.get("semaine") or 1)
    remarque = r.get("remarque") or ""
    # RPE : colonne dédiée (migration v34) sinon token « @RPE8 » hérité.
    rpe = r.get("rpe")
    if rpe is None:
        rpe = parse_rpe(remarque)
    return {
        "Semaine": week,
        "Séance": r.get("seance") or "",
        "Exercice": r.get("exercice") or "",
        "Série": int(r.get("serie") or 1),
        "Reps": int(r.get("reps") or 0),
        "Poids": float(r.get("poids") or 0),
        "Remarque": remarque,
        "Muscle": r.get("muscle") or "",
        "Date": date_str,
        "RPE": float(rpe) if rpe is not None else None,
    }


def _reporter_dans_le_cache(user_id, date_str, seance, exercice, payload):
    """Après avoir réécrit les séries d'un exercice, on corrige l'historique
    en cache au lieu de le jeter. Le jeter forçait la relecture complète de
    l'historique juste après chaque « Série faite » — 4 pages sur un an
    d'entraînement, pour des lignes qu'on venait soi-même d'écrire (audit du
    30/09, I15). Sans cache, rien à corriger : la prochaine lecture lira."""
    key = f"hist:{user_id}"
    cached = _cache_get(key)
    if cached is None:
        return
    garde = [r for r in cached
             if not (r.get("Date") == date_str and r.get("Séance") == seance
                     and r.get("Exercice") == exercice)]
    _cache_set(key, garde + [_nettoyer_ligne(p) for p in payload])


def save_hist(user_id: str, rows: list[dict]):
    """Réécrit tout l'historique de l'user (import de sauvegarde, reset).

    Ordre volontairement inversé par rapport à un clear+insert : on INSÈRE
    d'abord les nouvelles lignes, puis on SUPPRIME les anciennes par id. À
    aucun moment l'historique n'est vide ; si l'insertion échoue, on efface ce
    qu'on vient d'ajouter et l'ancien historique est intact."""
    client = get_client()

    old_ids = [r["id"] for r in _fetch_all(lambda: (
        client.table("history").select("id").eq("user_id", user_id).order("id")
    )) if r.get("id") is not None]

    inserted_ids: list = []
    try:
        if rows:
            payload = [_row_to_supabase(user_id, r) for r in rows]
            for i in range(0, len(payload), 500):
                resp = _insert_history(client, payload[i:i + 500])
                inserted_ids.extend(x["id"] for x in (resp.data or []) if x.get("id") is not None)
    except Exception as e:
        logger.error("save_hist insert FAILED user=%s: %s", user_id, e)
        try:
            _delete_history_ids(client, inserted_ids)
        except Exception as e2:
            logger.error("save_hist cleanup FAILED user=%s: %s", user_id, e2)
        raise

    _delete_history_ids(client, old_ids)
    _cache_invalidate(f"hist:{user_id}")


def _delete_history_ids(client, ids: list) -> None:
    """Supprime des lignes history par id, par paquets (longueur d'URL)."""
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        if not chunk:
            continue
        q = client.table("history").delete()
        if hasattr(q, "in_"):
            q.in_("id", chunk).execute()
        else:  # client minimal sans in_() : un delete par id
            for _id in chunk:
                client.table("history").delete().eq("id", _id).execute()


# Colonnes ajoutées par la migration v34 (history.session_id, history.rpe).
# Tant qu'elle n'est pas appliquée, l'insert les refuse : on les retire et on
# réessaie, puis on s'en souvient pour ce process.
_HIST_EXT_COLS = ("session_id", "rpe")
_hist_ext_supported = True  # migration v34 appliquée le 2026-09-23

# Les seules colonnes que `get_hist` regarde. `select("*")` ramenait aussi
# `user_id`, `session_id` et `created_at` — une centaine d'octets par ligne
# que personne ne lit, soit presque autant que le contenu utile. Sur un an
# d'entraînement (~1 900 lignes) c'est la moitié du transfert pour rien.
# `id` n'y est pas : PostgREST sait trier sur une colonne non demandée.
_HIST_COLS_LUES = "date,semaine,seance,exercice,serie,reps,poids,remarque,muscle"


def _lire_history(client, user_id: str) -> list[dict]:
    """Les lignes d'historique d'un user, colonnes utiles seulement.

    `rpe` n'existe qu'après la migration v34. Une base en retard ferait
    échouer la requête au lieu d'ignorer la colonne comme le faisait
    `select("*")` : on retombe alors sur la liste courte, une fois pour
    toutes, exactement comme `_insert_history` le fait à l'écriture.
    """
    global _hist_ext_supported

    def lire(colonnes):
        return _fetch_all(lambda: (
            client.table("history").select(colonnes)
            .eq("user_id", user_id).order("id")))

    if not _hist_ext_supported:
        return lire(_HIST_COLS_LUES)
    try:
        return lire(_HIST_COLS_LUES + ",rpe")
    except Exception as e:
        if "rpe" not in str(e).lower():
            raise
        logger.warning("history: colonne rpe absente (%s) — lecture sans elle", e)
        _hist_ext_supported = False
        return lire(_HIST_COLS_LUES)


def _insert_history(client, payload: list[dict]):
    global _hist_ext_supported
    if not _hist_ext_supported:
        payload = [{k: v for k, v in p.items() if k not in _HIST_EXT_COLS} for p in payload]
        return client.table("history").insert(payload).execute()
    try:
        return client.table("history").insert(payload).execute()
    except Exception as e:
        msg = str(e).lower()
        if not any(c in msg for c in _HIST_EXT_COLS):
            raise
        logger.warning("history: colonnes v34 absentes (%s) — insert sans session_id/rpe", e)
        _hist_ext_supported = False
        stripped = [{k: v for k, v in p.items() if k not in _HIST_EXT_COLS} for p in payload]
        return client.table("history").insert(stripped).execute()


def _row_to_supabase(user_id: str, r: dict) -> dict:
    date_val = r.get("Date")
    remarque = r.get("Remarque") or ""
    rpe = r.get("RPE")
    if rpe is None:
        rpe = parse_rpe(remarque)
    seance = r.get("Séance") or ""
    return {
        "user_id": user_id,
        "semaine": int(r.get("Semaine") or 1),
        "seance": seance,
        "exercice": r.get("Exercice") or "",
        "serie": int(r.get("Série") or 1),
        "reps": int(r.get("Reps") or 0),
        "poids": float(r.get("Poids") or 0),
        "remarque": remarque,
        "muscle": r.get("Muscle") or "",
        "date": date_val if date_val else None,
        "session_id": session_id_for(user_id, str(date_val or ""), seance) if date_val else None,
        "rpe": float(rpe) if rpe is not None else None,
    }

# ────────────────────────────────────────────────────────────
# Opérations ciblées (remplacement de ligne par exercice / date)
# ────────────────────────────────────────────────────────────
# Une séance = (user, DATE, nom de séance). Le ciblage se fait par date exacte :
# l'ancien ciblage par plage de semaine effaçait la séance du lundi quand on
# enregistrait la même séance le vendredi (Full Body A/B, 5×5, PPL 5-6 j…).

def _norm_date(date_str: str) -> str:
    """YYYY-MM-DD validé — lève ValueError si invalide (les routes valident
    en amont, ceci est un garde-fou)."""
    return _dt.date.fromisoformat(str(date_str)[:10]).isoformat()


def replace_exo_rows(user_id: str, date_str: str, seance: str, exercice: str, new_rows: list[dict]):
    """Remplace les séries d'un exercice pour UNE séance (date + nom).

    Même ordre que `save_hist` : on INSÈRE les nouvelles lignes, puis on
    supprime les anciennes par id. Avant, c'était DELETE puis INSERT, sans
    transaction : une coupure entre les deux effaçait les séries déjà
    enregistrées de l'exercice. Maintenant, un échec d'insertion laisse
    l'ancien état intact."""
    date_str = _norm_date(date_str)
    client = get_client()
    old_ids = [r["id"] for r in (
        client.table("history").select("id")
        .eq("user_id", user_id)
        .eq("date", date_str)
        .eq("seance", seance)
        .eq("exercice", exercice)
        .execute()
    ).data or [] if r.get("id") is not None]
    payload = [_row_to_supabase(user_id, {**r, "Date": date_str}) for r in (new_rows or [])]
    try:
        if payload:
            _insert_history(client, payload)
        _delete_history_ids(client, old_ids)
    except Exception:
        _cache_invalidate(f"hist:{user_id}")
        raise
    _reporter_dans_le_cache(user_id, date_str, seance, exercice, payload)


def append_exo_rows(user_id: str, date_str: str, seance: str, exercice: str,
                    new_rows: list[dict]) -> int:
    """Ajoute des séries à un exercice SANS effacer les précédentes.

    `replace_exo_rows` convient quand on réécrit une saisie qu'on est en
    train de modifier. Pour une séance qu'on vient de faire, non : deux
    footings le même jour sont deux séances, et remplacer efface la
    première. Le numéro de série continue la suite existante, pour que les
    deux se distinguent à la lecture.

    Retourne le numéro de la première série ajoutée.
    """
    date_str = _norm_date(date_str)
    client = get_client()
    existantes = (
        client.table("history").select("serie")
        .eq("user_id", user_id)
        .eq("date", date_str)
        .eq("seance", seance)
        .eq("exercice", exercice)
        .execute()
    ).data or []
    depart = max((int(r.get("serie") or 0) for r in existantes), default=0) + 1
    if new_rows:
        payload = [_row_to_supabase(user_id, {**r, "Date": date_str,
                                              "Série": depart + i})
                   for i, r in enumerate(new_rows)]
        _insert_history(client, payload)
    _cache_invalidate(f"hist:{user_id}")
    return depart


def delete_exo_rows(user_id: str, date_str: str, seance: str, exercice: str,
                    serie: int | None = None):
    """Supprime les lignes d'un exercice pour une séance ; avec `serie`, une
    seule — deux blocs du même cardio dans une séance sont deux séries, et
    en supprimer un ne doit pas emporter l'autre."""
    date_str = _norm_date(date_str)
    client = get_client()
    q = (
        client.table("history").delete()
        .eq("user_id", user_id)
        .eq("date", date_str)
        .eq("seance", seance)
        .eq("exercice", exercice)
    )
    if serie is not None:
        q = q.eq("serie", int(serie))
    q.execute()
    _cache_invalidate(f"hist:{user_id}")


def delete_session_rows(user_id: str, date_str: str, seance: str):
    date_str = _norm_date(date_str)
    client = get_client()
    (
        client.table("history").delete()
        .eq("user_id", user_id)
        .eq("date", date_str)
        .eq("seance", seance)
        .execute()
    )
    _cache_invalidate(f"hist:{user_id}")


def rename_seance_rows(user_id: str, old_name: str, new_name: str) -> int:
    """Renomme une séance dans tout l'historique. Retourne les lignes touchées.

    L'historique est indexé sur le NOM de la séance : renommer le programme
    sans renommer l'historique couperait la séance de son passé — volume,
    records et progression repartiraient de zéro, sans erreur nulle part.
    """
    if not old_name or old_name == new_name:
        return 0
    client = get_client()
    resp = (
        client.table("history").update({"seance": new_name})
        .eq("user_id", user_id)
        .eq("seance", old_name)
        .execute()
    )
    _cache_invalidate(f"hist:{user_id}")
    return len(resp.data or [])


def rename_exercise_rows(user_id: str, old_names: list[str], new_name: str,
                         muscle: str | None = None) -> int:
    """Renomme un exercice dans tout l'historique par UPDATE ciblé (plus de
    réécriture complète de la table). Retourne le nombre de lignes touchées."""
    client = get_client()
    payload = {"exercice": new_name}
    if muscle:
        payload["muscle"] = muscle
    count = 0
    for old in old_names:
        if not old or old == new_name:
            continue
        resp = (
            client.table("history").update(payload)
            .eq("user_id", user_id)
            .eq("exercice", old)
            .execute()
        )
        count += len(resp.data or [])
    _cache_invalidate(f"hist:{user_id}")
    return count


def mark_session_missed(user_id: str, semaine: int, seance_name: str, date_str: str):
    """Insère une ligne SESSION "manquée" à la date donnée si aucune n'existe
    déjà. Utilise une requête ciblée au lieu de relire tout l'historique."""
    client = get_client()
    resp = (
        client.table("history").select("id")
        .eq("user_id", user_id)
        .eq("date", date_str)
        .eq("exercice", "SESSION")
        .limit(1)
        .execute()
    )
    if resp.data:
        return
    row = {
        "Semaine": semaine,
        "Séance": seance_name,
        "Exercice": "SESSION",
        "Série": 1,
        "Reps": 0,
        "Poids": 0.0,
        "Remarque": "SÉANCE MANQUÉE",
        "Muscle": "Autre",
        "Date": date_str,
    }
    _insert_history(client, [_row_to_supabase(user_id, row)])
    _cache_invalidate(f"hist:{user_id}")

def list_history_shape() -> list[dict]:
    """(user_id, date) de TOUTES les lignes d'historique — lecture seule.

    Sert à mesurer ce que coûte `get_hist` (`core/blob_stats.py`). Deux
    colonnes seulement : ni exercice, ni charge, ni remarque. De quoi compter
    et dater, rien de plus.
    """
    return _fetch_all(lambda: get_client().table("history").select("user_id,date")) or []
