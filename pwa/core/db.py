"""Couche d'accès Supabase (Phase 3 — a remplacé l'ancien backend Google Sheets).

Phase 3 choix d'archi : le backend Flask utilise la clé `service_role` (bypass
RLS) et filtre manuellement **chaque** requête par `user_id`. L'authentification
de l'utilisateur se fait via Supabase Google OAuth côté client puis un "bridge"
qui valide le JWT et pose `user_id` dans la session Flask. Toutes les fonctions
de ce module exigent explicitement un `user_id`.

Config : deux variables d'env requises
  - SUPABASE_URL
  - SUPABASE_SERVICE_ROLE_KEY   (jamais exposée au client)
"""
import datetime as _dt
import os
import json
import logging
import time
import uuid
from collections import OrderedDict
from typing import Optional

from supabase import create_client, Client

from core.dates import continuous_week
from core.muscu import parse_rpe

logger = logging.getLogger(__name__)

# Taille de page PostgREST : Supabase plafonne chaque réponse à `max-rows`
# (1 000 par défaut) SANS erreur. Toute lecture potentiellement longue passe
# par _fetch_all() qui enchaîne les pages jusqu'à épuisement.
_PAGE = 1000


def _fetch_all(build) -> list:
    """`build()` renvoie une requête select prête (filtres + tri). On la
    ré-exécute par tranches de _PAGE lignes via .range() jusqu'à recevoir une
    page incomplète. Sans .range() (client minimal), une seule exécution."""
    out: list = []
    start = 0
    while True:
        q = build()
        paged = hasattr(q, "range")
        if paged:
            q = q.range(start, start + _PAGE - 1)
        resp = q.execute()
        rows = resp.data or []
        out.extend(rows)
        if not paged or len(rows) < _PAGE:
            return out
        start += _PAGE


# Identifiant de séance : dérivé de (user, date, nom de séance) → stable,
# sans lecture préalable, et partagé par toutes les séries d'une même séance.
_SESSION_NS = uuid.UUID("7f2b6d1e-9c4a-4b3e-8a6f-0d5e2c1b7a90")


def session_id_for(user_id: str, date_str: str, seance: str) -> str:
    return str(uuid.uuid5(_SESSION_NS, f"{user_id}|{date_str}|{seance}"))


def _continuous_week_of(date_str: str):
    """Index de semaine continu pour une date ISO, ou None si invalide."""
    try:
        return continuous_week(_dt.date.fromisoformat(str(date_str)[:10]))
    except (ValueError, TypeError):
        return None

def _env(name: str) -> str:
    v = os.getenv(name, "") or ""
    v = v.strip().strip('"').strip("'").lstrip("=").strip()
    if v:
        return v
    for k, val in os.environ.items():
        if k.strip() == name:
            v = val.strip().strip('"').strip("'").lstrip("=").strip()
            if v:
                return v
    return ""


_client: Optional[Client] = None


def get_client() -> Client:
    """Client Supabase process-wide avec clé service_role.
    ⚠️ bypass RLS : tous les appels DOIVENT filtrer explicitement par user_id."""
    global _client
    if _client is None:
        url = _env("SUPABASE_URL")
        key = _env("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants dans l'environnement."
            )
        _client = create_client(url, key)
    return _client


# ── Cache mémoire process-wide (TTL 60 s), clé par user_id ──
# Borné (LRU) : sans plafond, chaque user actif laisserait son historique
# complet en RAM du worker jusqu'à expiration — et la clé n'était jamais
# retirée, seulement ignorée.
_CACHE_MAX = 200
_data_cache: "OrderedDict[str, dict]" = OrderedDict()
_TTL = 60.0
# Le profil porte le tier VIP : TTL court pour qu'un passage PRO (Stripe,
# admin) se propage vite à toutes les requêtes (cf. FREE_RECHECK_TTL app.py).
_PROFILE_TTL = 15.0


def _cache_get(key: str, ttl: float | None = None):
    entry = _data_cache.get(key)
    if entry is None:
        return None
    if (time.time() - entry["ts"]) >= (ttl or _TTL):
        _data_cache.pop(key, None)
        return None
    _data_cache.move_to_end(key)
    return entry["value"]


def _cache_set(key: str, value):
    _data_cache[key] = {"value": value, "ts": time.time()}
    _data_cache.move_to_end(key)
    while len(_data_cache) > _CACHE_MAX:
        _data_cache.popitem(last=False)


def _cache_invalidate(key: str):
    _data_cache.pop(key, None)


def clear_user_cache(user_id: str):
    """Invalide explicitement toutes les entrées cache d'un utilisateur.
    Appelé après chaque save réussi pour éviter les séances vides au reload."""
    for prefix in ("hist", "prog", "profile", "onboarding"):
        _data_cache.pop(f"{prefix}:{user_id}", None)


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
    rows = _fetch_all(lambda: (
        client.table("history")
        .select("*")
        .eq("user_id", user_id)
        .order("id")
    ))
    cleaned = []
    for r in rows:
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
        cleaned.append({
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
        })
    _cache_set(key, cleaned)
    return [dict(r) for r in cleaned]


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
# Programme (stocké en JSON dans programs.data)
# ────────────────────────────────────────────────────────────

# Dernier instantané (data + version) lu par CE process pour chaque user :
# c'est la base à partir de laquelle save_prog calcule ce que la requête a
# réellement modifié. Borné comme le cache.
_prog_base: "OrderedDict[str, dict]" = OrderedDict()
_SAVE_PROG_RETRIES = 3


def _copy(obj):
    return json.loads(json.dumps(obj))


def _remember_base(user_id: str, data: dict, version):
    _prog_base[user_id] = {"data": _copy(data), "version": version}
    _prog_base.move_to_end(user_id)
    while len(_prog_base) > _CACHE_MAX:
        _prog_base.popitem(last=False)


def _read_prog_row(user_id: str):
    """(data, version) depuis la DB. version=None si pas de ligne ou si la
    migration v32 n'est pas encore appliquée (→ save_prog repasse en upsert)."""
    client = get_client()
    resp = (
        client.table("programs")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    row = (resp.data or {}) if resp else {}
    return (row.get("data") or {}), row.get("version")


def get_prog(user_id: str) -> dict:
    key = f"prog:{user_id}"
    cached = _cache_get(key)
    if cached is None:
        data, version = _read_prog_row(user_id)
        cached = {"data": data, "version": version}
        _cache_set(key, cached)
    _remember_base(user_id, cached["data"], cached["version"])
    return _copy(cached["data"])


# ────────────────────────────────────────────────────────────
# Corps du programme vs données personnelles
# ────────────────────────────────────────────────────────────
# `programs.data` mélange DEUX choses : le programme lui-même (séances,
# planning, dossiers…) et des données personnelles rangées là faute de table
# dédiée (badges, record de streak, exos perso, défis…).
#
# Cinq chemins réécrivaient ce blob en repartant de zéro avec une liste
# blanche des clés à conserver — listes divergentes, donc perte silencieuse
# de tout ce qui n'y figurait pas (bilans, badges, exos perso, record…).
#
# Désormais un seul sens de lecture : `PROG_BODY_KEYS` décrit ce qui APPARTIENT
# au programme (donc remplaçable) ; tout le reste est personnel et survit
# toujours. Une nouvelle clé personnelle n'a rien à déclarer : elle est
# conservée par défaut.
PROG_BODY_KEYS = frozenset({
    "_planning",       # jour de semaine → nom de séance
    "_name",           # nom du programme
    "_origin",         # id catalogue d'origine
    "_programmes",     # dossiers de programmes
    "_seance_prog",    # séance → dossier
    "_cardio",         # cardio planifié (générateur IA)
    "_started_at",     # date de départ du programme
    "_jours",          # legacy : jours par séance
    "_reps_hint",      # legacy : indices de reps catalogue
})


def replace_program_body(old: dict, body: dict) -> dict:
    """Programme complet = nouveau corps + données personnelles de `old`.

    `body` contient les séances (clés sans underscore) et les clés de
    PROG_BODY_KEYS qu'il veut poser ; les clés de `body` absentes de
    PROG_BODY_KEYS et commençant par « _ » sont refusées (un appelant ne
    doit pas écraser une donnée perso par ce chemin).
    """
    out: dict = {}
    # 1. Données personnelles de l'ancien programme (tout ce qui n'est ni une
    #    séance ni une clé de corps) — conservées telles quelles.
    for k, v in (old or {}).items():
        if k.startswith("_") and k not in PROG_BODY_KEYS:
            out[k] = v
    # 2. Nouveau corps : séances d'abord (l'ordre du dict = ordre d'affichage).
    for k, v in (body or {}).items():
        if not k.startswith("_"):
            out[k] = v
    for k, v in (body or {}).items():
        if k.startswith("_"):
            if k in PROG_BODY_KEYS:
                out[k] = v
            else:
                logger.warning("replace_program_body: clé personnelle '%s' ignorée", k)
    return out


def _merge_prog(base: dict, ours: dict, theirs: dict, path: str = "") -> dict:
    """Fusion 3 voies par clé : `ours` = blob que la requête veut écrire,
    `base` = ce qu'elle avait lu, `theirs` = ce qui est en DB maintenant.
    On repart de `theirs` et on n'y applique QUE les clés que nous avons
    changées (ajoutées, modifiées, supprimées). Si les deux côtés ont touché
    la même clé et que ce sont des dicts, on descend d'un niveau ; sinon
    notre valeur l'emporte (dernier écrivain) — mais c'est loggué."""
    if not (isinstance(base, dict) and isinstance(ours, dict) and isinstance(theirs, dict)):
        return ours
    merged = dict(theirs)
    for k in set(base) | set(ours):
        sub = f"{path}.{k}" if path else str(k)
        if k not in ours:
            # Supprimée par nous
            merged.pop(k, None)
        elif k not in base or ours[k] != base[k]:
            # Ajoutée / modifiée par nous
            if k in theirs and theirs[k] != base.get(k):
                logger.warning("save_prog: clé '%s' modifiée des deux côtés", sub)
                merged[k] = _merge_prog(base.get(k), ours[k], theirs[k], sub)
            else:
                merged[k] = ours[k]
        # sinon : inchangée par nous → on garde la version DB (déjà dans merged,
        # ou absente si l'autre côté l'a supprimée)
    return merged


def _upsert_prog(user_id: str, prog_dict: dict):
    get_client().table("programs").upsert({
        "user_id": user_id,
        "data": prog_dict,
    }).execute()


def save_prog(user_id: str, prog_dict: dict):
    """Écrit le programme avec verrou optimiste (programs.version).

    Le blob est partagé entre 2 workers gunicorn qui ont chacun un cache de
    60 s : sans verrou, une écriture faite entre-temps par l'autre worker
    (défi validé, badge, note…) est écrasée sans erreur. Ici l'update est
    conditionné à la version lue ; en cas de conflit on relit et on ne
    réapplique que nos propres modifications (cf. _merge_prog)."""
    base = _prog_base.get(user_id)
    if base is None or base["version"] is None:
        # Pas de lecture préalable dans ce process (ou colonne version absente)
        # → écriture inconditionnelle, comme avant.
        _upsert_prog(user_id, prog_dict)
        _cache_invalidate(f"prog:{user_id}")
        return

    client = get_client()
    base_data, version = base["data"], base["version"]
    for attempt in range(1, _SAVE_PROG_RETRIES + 1):
        resp = (
            client.table("programs")
            .update({"data": prog_dict, "version": version + 1})
            .eq("user_id", user_id)
            .eq("version", version)
            .execute()
        )
        if resp.data:
            _cache_invalidate(f"prog:{user_id}")
            _remember_base(user_id, prog_dict, version + 1)
            return
        # Conflit : quelqu'un a écrit depuis notre lecture.
        theirs, their_version = _read_prog_row(user_id)
        if their_version is None:
            break
        logger.warning(
            "save_prog conflit user=%s (lu v%s, DB v%s) — fusion, tentative %d/%d",
            user_id, version, their_version, attempt, _SAVE_PROG_RETRIES,
        )
        prog_dict = _merge_prog(base_data, prog_dict, theirs)
        base_data, version = theirs, their_version

    logger.error("save_prog user=%s : verrou optimiste abandonné, upsert brut", user_id)
    _upsert_prog(user_id, prog_dict)
    _cache_invalidate(f"prog:{user_id}")
    _prog_base.pop(user_id, None)


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
    """Remplace les séries d'un exercice pour UNE séance (date + nom) :
    supprime les lignes existantes de cette date puis insère les nouvelles."""
    date_str = _norm_date(date_str)
    client = get_client()
    (
        client.table("history").delete()
        .eq("user_id", user_id)
        .eq("date", date_str)
        .eq("seance", seance)
        .eq("exercice", exercice)
        .execute()
    )
    if new_rows:
        payload = [_row_to_supabase(user_id, {**r, "Date": date_str}) for r in new_rows]
        _insert_history(client, payload)
    _cache_invalidate(f"hist:{user_id}")


def delete_exo_rows(user_id: str, date_str: str, seance: str, exercice: str):
    date_str = _norm_date(date_str)
    client = get_client()
    (
        client.table("history").delete()
        .eq("user_id", user_id)
        .eq("date", date_str)
        .eq("seance", seance)
        .eq("exercice", exercice)
        .execute()
    )
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


# ────────────────────────────────────────────────────────────
# Profil (Phase 4 — onboarding)
# ────────────────────────────────────────────────────────────

def get_profile(user_id: str) -> dict:
    """Profil (tier, prénom, poids, quotas…). Cache court (_PROFILE_TTL) :
    lu par before_request à chaque requête d'un FREE + par la plupart des
    pages — sans cache c'était un aller-retour Supabase par appel."""
    key = f"profile:{user_id}"
    cached = _cache_get(key, _PROFILE_TTL)
    if cached is not None:
        return dict(cached)
    client = get_client()
    resp = (
        client.table("profiles")
        .select("*")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    data = (resp.data if resp else None) or {}
    _cache_set(key, data)
    return dict(data)


# Colonnes de `profiles` ajoutées par des migrations récentes. Si l'une manque
# (migration pas encore appliquée), l'upsert entier échouerait — on la retire
# et on réessaie plutôt que de perdre l'écriture.
_PROFILE_OPTIONAL_COLS = ("coach_memory",)


def _profile_upsert(user_id: str, payload: dict) -> None:
    """Toute écriture de profil passe ici : upsert + invalidation du cache."""
    client = get_client()
    try:
        client.table("profiles").upsert({"id": user_id, **payload}).execute()
    except Exception as e:
        missing = [c for c in _PROFILE_OPTIONAL_COLS
                   if c in payload and c in str(e).lower()]
        if not missing:
            raise
        logger.warning("profiles : colonne(s) %s absente(s) — écriture partielle", missing)
        reduced = {k: v for k, v in payload.items() if k not in missing}
        if reduced:
            client.table("profiles").upsert({"id": user_id, **reduced}).execute()
    _cache_invalidate(f"profile:{user_id}")


def save_profile(user_id: str, fields: dict):
    """Upsert sur public.profiles (id = user_id). Phase 4 : doit pouvoir
    créer la row si elle n'existe pas encore (nouveau user qui passe
    l'onboarding pour la première fois)."""
    _profile_upsert(user_id, fields)


# ────────────────────────────────────────────────────────────
# Onboarding (Phase 4)
# ────────────────────────────────────────────────────────────

def get_onboarding(user_id: str) -> dict:
    """Retourne la row onboarding de l'user, ou {} si jamais complétée.
    Cache 60 s (ne change qu'au (re)onboarding)."""
    key = f"onboarding:{user_id}"
    cached = _cache_get(key)
    if cached is not None:
        return dict(cached)
    client = get_client()
    resp = (
        client.table("onboarding")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    data = (resp.data if resp else None) or {}
    _cache_set(key, data)
    return dict(data)


def save_onboarding(user_id: str, fields: dict):
    """Upsert sur public.onboarding. Les champs attendus :
    prenom, age, sexe, niveau, frequence, objectif, equipement."""
    client = get_client()
    payload = {"user_id": user_id, **fields}
    client.table("onboarding").upsert(payload).execute()
    _cache_invalidate(f"onboarding:{user_id}")


# ────────────────────────────────────────────────────────────
# Nutrition (Prompt C)
# ────────────────────────────────────────────────────────────

def list_nutrition(user_id: str, date_str: str) -> list[dict]:
    """Tous les repas loggés à une date donnée (ordre id)."""
    client = get_client()
    resp = (
        client.table("nutrition")
        .select("*")
        .eq("user_id", user_id)
        .eq("date", date_str)
        .order("id")
        .execute()
    )
    return resp.data or []


def insert_nutrition(user_id: str, row: dict) -> None:
    """Ajoute un repas (date, meal_type, calories, protein, carbs, fat, note)."""
    client = get_client()
    payload = {"user_id": user_id, **row}
    client.table("nutrition").insert(payload).execute()


def delete_nutrition(user_id: str, entry_id: int) -> None:
    client = get_client()
    (
        client.table("nutrition").delete()
        .eq("user_id", user_id)
        .eq("id", int(entry_id))
        .execute()
    )


# ────────────────────────────────────────────────────────────
# Poids corporel (migration v33) — une pesée par jour
# ────────────────────────────────────────────────────────────

def list_body_weight(user_id: str, limit: int = 400) -> list[dict]:
    """Pesées de l'user, de la plus ancienne à la plus récente :
    [{date, poids_kg}]. `limit` borne les plus récentes."""
    client = get_client()
    resp = (
        client.table("body_weight")
        .select("date, poids_kg")
        .eq("user_id", user_id)
        .order("date", desc=True)
        .limit(limit)
        .execute()
    )
    rows = resp.data or []
    out = [{"date": str(r.get("date") or "")[:10], "poids_kg": float(r.get("poids_kg") or 0)}
           for r in rows]
    out.sort(key=lambda r: r["date"])
    return out


def upsert_body_weight(user_id: str, date_str: str, poids_kg: float) -> None:
    """Enregistre (ou remplace) la pesée du jour `date_str` (YYYY-MM-DD)."""
    client = get_client()
    client.table("body_weight").upsert({
        "user_id": user_id,
        "date": date_str,
        "poids_kg": round(float(poids_kg), 1),
    }, on_conflict="user_id,date").execute()


def delete_body_weight(user_id: str, date_str: str) -> None:
    client = get_client()
    (
        client.table("body_weight").delete()
        .eq("user_id", user_id)
        .eq("date", date_str)
        .execute()
    )


def list_all_users_with_tier() -> list[dict]:
    """Retourne la liste de tous les users (admin). Combine auth.users (email)
    et public.profiles (tier). Réservé au backend admin — utilise service_role.
    """
    client = get_client()
    # auth.users via Admin API
    try:
        users_resp = client.auth.admin.list_users()
        # Le SDK peut retourner soit une liste directe soit un objet .users
        auth_users = getattr(users_resp, "users", None) or users_resp or []
    except Exception as e:
        logger.error("list_all_users_with_tier auth FAILED: %s", e)
        auth_users = []

    # profiles
    try:
        prof_resp = client.table("profiles").select("id, tier, prenom").execute()
        profiles = {p["id"]: p for p in (prof_resp.data or [])}
    except Exception as e:
        logger.error("list_all_users_with_tier profiles FAILED: %s", e)
        profiles = {}

    out = []
    for u in auth_users:
        uid = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
        email = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else "")
        created = getattr(u, "created_at", None) or (u.get("created_at") if isinstance(u, dict) else "")
        p = profiles.get(uid) or {}
        out.append({
            "id": uid,
            "email": email or "",
            "created_at": str(created or "")[:10],
            "tier": (p.get("tier") or "free"),
            "prenom": (p.get("prenom") or ""),
        })
    out.sort(key=lambda u: u["created_at"], reverse=True)
    return out


def set_user_tier(user_id: str, tier: str) -> None:
    """Upsert profiles.tier pour un user. tier ∈ {'free', 'vip'}."""
    if tier not in ("free", "vip"):
        raise ValueError(f"tier invalide: {tier}")
    _profile_upsert(user_id, {"tier": tier})


# ── Stripe (abonnements Premium) ─────────────────────────────────
def set_stripe_customer(user_id: str, customer_id: str) -> None:
    """Mémorise l'ID client Stripe sur le profil (pour le portail + le mapping
    customer→user lors des webhooks d'annulation). Nécessite la colonne
    profiles.stripe_customer_id (migration v27)."""
    if not customer_id:
        return
    _profile_upsert(user_id, {"stripe_customer_id": customer_id})


def get_user_by_stripe_customer(customer_id: str) -> Optional[str]:
    """Retrouve l'user_id à partir de l'ID client Stripe (webhook annulation)."""
    if not customer_id:
        return None
    client = get_client()
    resp = (
        client.table("profiles")
        .select("id")
        .eq("stripe_customer_id", customer_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0]["id"] if rows else None


# ── Parrainage + VIP à durée limitée (migration v29) ─────────────
import hashlib as _hashlib


def vip_until_active(vip_until) -> bool:
    """True si un VIP à durée limitée (`profiles.vip_until`) est encore valide."""
    if not vip_until:
        return False
    try:
        s = str(vip_until).replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return dt > _dt.datetime.now(_dt.timezone.utc)
    except (ValueError, TypeError):
        return False


def get_or_create_referral_code(user_id: str) -> str:
    """Code de parrainage stable de l'utilisateur. Généré (déterministe, dérivé
    de l'user_id) et persisté au premier appel. Sert au lien d'invitation et à
    la résolution inverse (`get_user_by_referral_code`)."""
    client = get_client()
    try:
        resp = client.table("profiles").select("referral_code").eq("id", user_id).maybe_single().execute()
        existing = (resp.data or {}).get("referral_code") if resp else None
    except Exception as e:
        logger.error("get_or_create_referral_code read FAILED user=%s: %s", user_id, e)
        existing = None
    if existing:
        return existing
    # Code court, lisible, déterministe (base32 d'un hash de l'user_id).
    digest = _hashlib.sha1(user_id.encode("utf-8")).digest()
    import base64 as _b64
    code = _b64.b32encode(digest).decode("ascii").rstrip("=").lower()[:8]
    try:
        _profile_upsert(user_id, {"referral_code": code})
    except Exception as e:
        logger.error("get_or_create_referral_code write FAILED user=%s: %s", user_id, e)
    return code


def get_user_by_referral_code(code: str) -> Optional[str]:
    """Retrouve l'id du parrain à partir de son code (résolution du lien ?ref=)."""
    code = (code or "").strip().lower()
    if not code:
        return None
    client = get_client()
    try:
        resp = client.table("profiles").select("id").eq("referral_code", code).limit(1).execute()
        rows = resp.data or []
        return rows[0]["id"] if rows else None
    except Exception as e:
        logger.error("get_user_by_referral_code FAILED code=%s: %s", code, e)
        return None


def set_referred_by(user_id: str, referrer_id: str) -> None:
    """Mémorise le parrain d'un filleul (posé une seule fois côté appelant)."""
    _profile_upsert(user_id, {"referred_by": referrer_id})


def grant_vip_days(user_id: str, days: int) -> None:
    """Étend (cumulatif) le VIP à durée limitée : vip_until = max(now, vip_until
    courant) + days. Utilisé par le parrainage (et réutilisable pour promos)."""
    if days <= 0:
        return
    client = get_client()
    base = _dt.datetime.now(_dt.timezone.utc)
    try:
        resp = client.table("profiles").select("vip_until").eq("id", user_id).maybe_single().execute()
        cur = (resp.data or {}).get("vip_until") if resp else None
        if cur:
            s = str(cur).replace("Z", "+00:00")
            cur_dt = _dt.datetime.fromisoformat(s)
            if cur_dt.tzinfo is None:
                cur_dt = cur_dt.replace(tzinfo=_dt.timezone.utc)
            if cur_dt > base:
                base = cur_dt
    except Exception as e:
        logger.error("grant_vip_days read FAILED user=%s: %s", user_id, e)
    new_until = (base + _dt.timedelta(days=int(days))).isoformat()
    _profile_upsert(user_id, {"vip_until": new_until})


def count_referrals(user_id: str) -> int:
    """Nombre de filleuls (comptes ayant ce user comme `referred_by`)."""
    client = get_client()
    try:
        resp = client.table("profiles").select("id", count="exact").eq("referred_by", user_id).execute()
        return int(getattr(resp, "count", None) or 0)
    except Exception as e:
        logger.error("count_referrals FAILED user=%s: %s", user_id, e)
        return 0


def get_referred_by(user_id: str) -> Optional[str]:
    """Parrain déjà enregistré pour ce user, ou None."""
    client = get_client()
    try:
        resp = client.table("profiles").select("referred_by").eq("id", user_id).maybe_single().execute()
        return (resp.data or {}).get("referred_by") if resp else None
    except Exception as e:
        logger.error("get_referred_by FAILED user=%s: %s", user_id, e)
        return None


# ── Push web (relance des inactifs, migration v30) ───────────────
def save_push_subscription(user_id: str, sub: dict) -> None:
    """Upsert d'un abonnement push (clé = endpoint, unique). `sub` au format
    PushSubscription.toJSON() : {endpoint, keys:{p256dh, auth}}."""
    endpoint = (sub or {}).get("endpoint")
    keys = (sub or {}).get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("subscription incomplète")
    client = get_client()
    client.table("push_subscriptions").upsert(
        {"user_id": user_id, "endpoint": endpoint,
         "p256dh": keys["p256dh"], "auth": keys["auth"]},
        on_conflict="endpoint",
    ).execute()


def delete_push_subscription(endpoint: str, user_id: str | None = None) -> None:
    """Supprime un abonnement par endpoint. Avec `user_id` (route utilisateur),
    on ne peut supprimer que les siens ; sans (cron : abonnement mort), libre."""
    if not endpoint:
        return
    client = get_client()
    q = client.table("push_subscriptions").delete().eq("endpoint", endpoint)
    if user_id:
        q = q.eq("user_id", user_id)
    q.execute()


def _row_to_subscription(row: dict) -> dict:
    """Ligne DB → format attendu par pywebpush."""
    return {
        "endpoint": row.get("endpoint"),
        "keys": {"p256dh": row.get("p256dh"), "auth": row.get("auth")},
    }


def list_push_subscriptions(user_id: str) -> list[dict]:
    client = get_client()
    try:
        resp = client.table("push_subscriptions").select("*").eq("user_id", user_id).execute()
        return [_row_to_subscription(r) for r in (resp.data or [])]
    except Exception as e:
        logger.error("list_push_subscriptions FAILED user=%s: %s", user_id, e)
        return []


def set_newsletter_optin(user_id: str, opt_in: bool, email: str = "") -> None:
    """Enregistre le consentement newsletter sur le profil (migration v31).
    Mémorise l'e-mail + la date au moment de l'opt-in (preuve RGPD)."""
    import datetime as _dt
    payload = {"id": user_id, "newsletter_opt_in": bool(opt_in)}
    if opt_in:
        payload["newsletter_opt_in_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        if email:
            payload["newsletter_email"] = email.strip().lower()
    else:
        # On garde la date/e-mail tels quels en cas de retrait (historique) —
        # seul le flag passe à false : on n'enverra plus rien.
        pass
    _profile_upsert(user_id, payload)


def list_newsletter_emails() -> list[str]:
    """E-mails distincts ayant consenti à la newsletter (pour export Brevo)."""
    client = get_client()
    try:
        resp = (
            client.table("profiles")
            .select("newsletter_email")
            .eq("newsletter_opt_in", True)
            .execute()
        )
    except Exception as e:
        logger.error("list_newsletter_emails FAILED: %s", e)
        return []
    seen = []
    for r in (resp.data or []):
        em = (r.get("newsletter_email") or "").strip().lower()
        if em and em not in seen:
            seen.append(em)
    return seen


def _last_activity_by_user() -> dict:
    """{user_id: 'YYYY-MM-DD' de la dernière perf réelle}. Lit la vue SQL
    `user_last_activity` (migration v34) — un seul agrégat côté base — et
    retombe sur un parcours paginé de `history` si la vue est absente/vide."""
    client = get_client()
    out: dict = {}
    try:
        resp = client.table("user_last_activity").select("user_id, last_date").execute()
        for r in (resp.data or []):
            uid, d = r.get("user_id"), str(r.get("last_date") or "")[:10]
            if uid and d:
                out[uid] = d
    except Exception as e:
        logger.info("user_last_activity indisponible (%s) — repli sur history", e)
    if out:
        return out
    rows = _fetch_all(lambda: (
        client.table("history").select("user_id, date, reps, poids").order("id")
    ))
    for r in rows:
        if int(r.get("reps") or 0) <= 0 and float(r.get("poids") or 0) <= 0:
            continue
        uid = r.get("user_id")
        d = str(r.get("date") or "")[:10]
        if uid and d and d > out.get(uid, ""):
            out[uid] = d
    return out


def get_inactive_user_ids(min_days: int = 3, max_days: int = 30) -> set:
    """user_id dont la dernière séance (perf réelle) remonte à entre `min_days`
    et `max_days` jours — cibles de relance (ni actifs, ni partis depuis trop
    longtemps). Exclut les comptes sans historique."""
    try:
        last_by_user = _last_activity_by_user()
    except Exception as e:
        logger.error("get_inactive_user_ids FAILED: %s", e)
        return set()
    today = _dt.date.today()
    lo = (today - _dt.timedelta(days=max_days)).isoformat()
    hi = (today - _dt.timedelta(days=min_days)).isoformat()
    return {uid for uid, last in last_by_user.items() if lo <= last <= hi}


def list_push_subscriptions_for_users(user_ids: set) -> list[dict]:
    """Abonnements push des users donnés : [{user_id, sub, endpoint,
    last_reactivation_at, reactivation_count}]. Les deux derniers champs
    (migration v34) servent au dédoublonnage des relances ; absents = jamais
    relancé."""
    if not user_ids:
        return []
    client = get_client()
    try:
        rows = _fetch_all(lambda: client.table("push_subscriptions").select("*").order("id"))
        out = []
        for r in rows:
            if r.get("user_id") in user_ids:
                out.append({
                    "user_id": r.get("user_id"),
                    "endpoint": r.get("endpoint"),
                    "sub": _row_to_subscription(r),
                    "last_reactivation_at": r.get("last_reactivation_at"),
                    "reactivation_count": int(r.get("reactivation_count") or 0),
                })
        return out
    except Exception as e:
        logger.error("list_push_subscriptions_for_users FAILED: %s", e)
        return []


def list_all_programs() -> list[dict]:
    """[{user_id, data}] pour tous les comptes — cron des rappels de séance.

    Le planning vit dans `programs.data['_planning']` : sans lecture groupée,
    il faudrait une requête par utilisateur à chaque heure. On ne prend que
    les deux colonnes utiles.
    """
    client = get_client()
    try:
        return _fetch_all(lambda: (
            client.table("programs").select("user_id, data").order("user_id")
        ))
    except Exception as e:
        logger.error("list_all_programs FAILED: %s", e)
        return []


def users_trained_on(date_str: str) -> set:
    """user_id ayant au moins une perf réelle à cette date (pour ne pas
    rappeler une séance déjà faite)."""
    client = get_client()
    try:
        rows = _fetch_all(lambda: (
            client.table("history").select("user_id, reps, poids")
            .eq("date", _norm_date(date_str)).order("id")
        ))
    except Exception as e:
        logger.error("users_trained_on FAILED: %s", e)
        return set()
    return {r["user_id"] for r in rows
            if r.get("user_id")
            and (int(r.get("reps") or 0) > 0 or float(r.get("poids") or 0) > 0)}


def mark_reactivation_sent(endpoint: str, count: int) -> None:
    """Mémorise l'envoi d'une relance sur un abonnement (colonnes v34).
    Best-effort : sans la migration, l'update échoue et on continue."""
    if not endpoint:
        return
    client = get_client()
    try:
        (
            client.table("push_subscriptions")
            .update({
                "last_reactivation_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                "reactivation_count": int(count),
            })
            .eq("endpoint", endpoint)
            .execute()
        )
    except Exception as e:
        logger.warning("mark_reactivation_sent FAILED (migration v34 ?): %s", e)


def list_coach_messages(user_id: str, conversation_id: str | None = None,
                         limit: int = 50) -> list[dict]:
    """Derniers messages du coach (rôle, content, created_at) en ordre
    chronologique. Si `conversation_id` est fourni, ne renvoie que les messages
    de cette conversation."""
    client = get_client()
    q = (
        client.table("coach_messages")
        .select("role, content, created_at")
        .eq("user_id", user_id)
    )
    if conversation_id:
        q = q.eq("conversation_id", conversation_id)
    resp = q.order("created_at", desc=True).limit(limit).execute()
    rows = list(resp.data or [])
    rows.reverse()
    return rows


def insert_coach_message(user_id: str, role: str, content: str,
                         conversation_id: str | None = None) -> None:
    if role not in ("user", "assistant"):
        raise ValueError(f"role invalide: {role}")
    client = get_client()
    row = {"user_id": user_id, "role": role, "content": content}
    if conversation_id:
        row["conversation_id"] = conversation_id
    try:
        client.table("coach_messages").insert(row).execute()
    except Exception:
        # Repli si la colonne conversation_id n'existe pas encore (migration
        # v26 non appliquée) : on insère au moins le message en mode legacy.
        if conversation_id:
            row.pop("conversation_id", None)
            client.table("coach_messages").insert(row).execute()
        else:
            raise


def clear_coach_messages(user_id: str) -> None:
    client = get_client()
    client.table("coach_messages").delete().eq("user_id", user_id).execute()


# ── Conversations du coach (migration v26) ───────────────────────────────
def list_coach_conversations(user_id: str, limit: int = 50) -> list[dict]:
    """Conversations du user, les plus récentes d'abord (id, title, updated_at)."""
    client = get_client()
    resp = (
        client.table("coach_conversations")
        .select("id, title, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(resp.data or [])


def create_coach_conversation(user_id: str, title: str = "Nouvelle conversation") -> str | None:
    """Crée une conversation et renvoie son id (ou None si échec)."""
    client = get_client()
    title = (title or "Nouvelle conversation").strip()[:80] or "Nouvelle conversation"
    resp = (
        client.table("coach_conversations")
        .insert({"user_id": user_id, "title": title})
        .execute()
    )
    rows = list(resp.data or [])
    return rows[0]["id"] if rows else None


def rename_coach_conversation(user_id: str, conversation_id: str, title: str) -> None:
    client = get_client()
    title = (title or "").strip()[:80] or "Sans titre"
    (
        client.table("coach_conversations")
        .update({"title": title})
        .eq("user_id", user_id)
        .eq("id", conversation_id)
        .execute()
    )


def touch_coach_conversation(user_id: str, conversation_id: str) -> None:
    """Met à jour updated_at pour faire remonter la conversation en tête de liste."""
    import datetime as _dt
    client = get_client()
    (
        client.table("coach_conversations")
        .update({"updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat()})
        .eq("user_id", user_id)
        .eq("id", conversation_id)
        .execute()
    )


def delete_coach_conversation(user_id: str, conversation_id: str) -> None:
    """Supprime une conversation et ses messages (ON DELETE CASCADE)."""
    client = get_client()
    (
        client.table("coach_conversations")
        .delete()
        .eq("user_id", user_id)
        .eq("id", conversation_id)
        .execute()
    )


# ────────────────────────────────────────────────────────────
# Admin — stats globales + fiche user
# ────────────────────────────────────────────────────────────

def get_admin_stats() -> dict:
    """Agrégats cross-users pour le dashboard admin.
    Retourne : total_rows, total_tonnage, total_seances (distinct user+date+seance),
    active_7d, active_30d (distinct user_id avec date récente)."""
    import datetime as _dt
    client = get_client()
    try:
        rows = _fetch_all(lambda: (
            client.table("history").select("user_id, date, seance, reps, poids").order("id")
        ))
    except Exception as e:
        logger.error("get_admin_stats FAILED: %s", e)
        return {"total_rows": 0, "total_tonnage": 0, "total_seances": 0, "active_7d": 0, "active_30d": 0}

    today = _dt.date.today()
    cutoff_7 = (today - _dt.timedelta(days=7)).isoformat()
    cutoff_30 = (today - _dt.timedelta(days=30)).isoformat()

    tonnage = 0.0
    sessions = set()
    a7, a30 = set(), set()
    for r in rows:
        reps = int(r.get("reps") or 0)
        poids = float(r.get("poids") or 0)
        tonnage += reps * poids
        d = str(r.get("date") or "")[:10]
        uid = r.get("user_id")
        if uid and d:
            sessions.add((uid, d, r.get("seance") or ""))
            if d >= cutoff_30:
                a30.add(uid)
                if d >= cutoff_7:
                    a7.add(uid)
    return {
        "total_rows": len(rows),
        "total_tonnage": int(tonnage),
        "total_seances": len(sessions),
        "active_7d": len(a7),
        "active_30d": len(a30),
    }


# ── Analytics produit (events de conversion / funnel) ────────────
def insert_event(user_id, event: str, props: dict | None = None,
                 tier: str | None = None) -> None:
    """Enregistre un event analytics (table `events`, migration v28).

    Best-effort : l'appelant (core.analytics.track) avale déjà les exceptions,
    mais on garde l'écriture minimale et tolérante (user_id peut être None)."""
    client = get_client()
    payload = {
        "user_id": user_id or None,
        "event": str(event)[:64],
        "props": props or {},
    }
    if tier:
        payload["tier"] = tier
    client.table("events").insert(payload).execute()


# Étapes du funnel : (clé, libellé, type, source).
# type 'signup'  → compte auth.users (haut de funnel)
# type 'event'   → distinct user_id ayant émis l'un des events listés
# type 'tier'    → distinct user_id actuellement VIP (profiles.tier)
_FUNNEL_STEPS = [
    ("signup",      "Inscrits",        "signup", None),
    ("onboarding",  "Onboarding fait", "event",  ("onboarding_completed",)),
    ("workout",     "1ʳᵉ séance",      "event",  ("workout_finished",)),
    ("offer",       "Offre vue",       "event",  ("premium_viewed", "paywall_viewed")),
    ("checkout",    "Checkout lancé",  "event",  ("checkout_started",)),
    ("vip",         "VIP",             "tier",   None),
]


def get_funnel_stats(days: int = 30) -> dict:
    """Entonnoir de conversion sur les `days` derniers jours.

    Interprétation (v1, orientée vue d'ensemble) : pour chaque étape, nombre
    d'utilisateurs DISTINCTS ayant atteint l'étape DANS la fenêtre. Le haut de
    funnel = comptes créés dans la fenêtre (auth.users). Les étapes du milieu
    lisent la table `events`. La dernière = users actuellement VIP.

    Retourne {days, steps:[{key,label,users,pct_of_top,pct_of_prev}], coach_msgs}.
    """
    import datetime as _dt
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)).isoformat()
    client = get_client()

    # Events de la fenêtre (un seul fetch, dédup en Python).
    users_by_event: dict[str, set] = {}
    coach_users: set = set()
    try:
        resp = (
            client.table("events")
            .select("user_id, event, created_at")
            .gte("created_at", cutoff)
            .execute()
        )
        for r in (resp.data or []):
            uid = r.get("user_id")
            ev = r.get("event") or ""
            if not uid:
                continue
            users_by_event.setdefault(ev, set()).add(uid)
            if ev == "coach_message":
                coach_users.add(uid)
    except Exception as e:
        logger.error("get_funnel_stats events FAILED: %s", e)

    # Haut de funnel : comptes créés dans la fenêtre.
    cutoff_day = cutoff[:10]
    signups = 0
    try:
        users_resp = client.auth.admin.list_users()
        auth_users = getattr(users_resp, "users", None) or users_resp or []
        for u in auth_users:
            created = getattr(u, "created_at", None) or (u.get("created_at") if isinstance(u, dict) else "")
            if str(created or "")[:10] >= cutoff_day:
                signups += 1
    except Exception as e:
        logger.error("get_funnel_stats signups FAILED: %s", e)

    # VIP actuels (étape finale).
    vip_count = 0
    try:
        prof = client.table("profiles").select("tier").execute()
        vip_count = sum(1 for p in (prof.data or []) if (p.get("tier") or "") == "vip")
    except Exception as e:
        logger.error("get_funnel_stats vip FAILED: %s", e)

    steps = []
    top = None
    prev = None
    for key, label, kind, events in _FUNNEL_STEPS:
        if kind == "signup":
            n = signups
        elif kind == "tier":
            n = vip_count
        else:
            seen: set = set()
            for ev in (events or ()):
                seen |= users_by_event.get(ev, set())
            n = len(seen)
        if top is None:
            top = n or 0
        pct_top = round(100 * n / top, 1) if top else 0.0
        pct_prev = round(100 * n / prev, 1) if prev else 100.0
        steps.append({
            "key": key, "label": label, "users": n,
            "pct_of_top": pct_top, "pct_of_prev": pct_prev,
        })
        prev = n if n else prev
    return {"days": days, "steps": steps, "coach_msgs_users": len(coach_users)}


def get_user_details(user_id: str) -> dict:
    """Fiche détaillée d'un user pour l'admin."""
    import datetime as _dt
    client = get_client()
    # Historique
    try:
        resp = client.table("history").select("date, seance, reps, poids").eq("user_id", user_id).execute()
        rows = resp.data or []
    except Exception as e:
        logger.error("get_user_details history FAILED user=%s: %s", user_id, e)
        rows = []
    tonnage = 0.0
    sessions = set()
    last_date = ""
    for r in rows:
        tonnage += int(r.get("reps") or 0) * float(r.get("poids") or 0)
        d = str(r.get("date") or "")[:10]
        if d:
            sessions.add((d, r.get("seance") or ""))
            if d > last_date:
                last_date = d
    # Profil + quota coach
    try:
        presp = client.table("profiles").select("tier, prenom, coach_quota_date, coach_quota_count").eq("id", user_id).maybe_single().execute()
        prof = (presp.data if presp else None) or {}
    except Exception as e:
        logger.error("get_user_details profile FAILED user=%s: %s", user_id, e)
        prof = {}
    # Nb msg coach total
    try:
        cresp = client.table("coach_messages").select("id", count="exact").eq("user_id", user_id).execute()
        coach_count = int(getattr(cresp, "count", None) or 0)
    except Exception as e:
        logger.error("get_user_details coach FAILED user=%s: %s", user_id, e)
        coach_count = 0
    today = _dt.date.today().isoformat()
    q_date = str(prof.get("coach_quota_date") or "")
    q_used = int(prof.get("coach_quota_count") or 0) if q_date == today else 0
    return {
        "user_id": user_id,
        "tier": prof.get("tier") or "free",
        "prenom": prof.get("prenom") or "",
        "total_rows": len(rows),
        "total_tonnage": int(tonnage),
        "total_seances": len(sessions),
        "last_date": last_date,
        "coach_msgs_total": coach_count,
        "coach_quota_used": q_used,
    }


def reset_user_coach_quota(user_id: str) -> None:
    """Remet à 0 le quota coach IA du jour pour un user (admin)."""
    _profile_upsert(user_id, {"coach_quota_count": 0})


def auth_user_exists(user_id: str) -> bool:
    """True si le compte auth Supabase existe encore. Lève en cas d'erreur
    transitoire (réseau, API down) — l'appelant décide alors de ne PAS
    déconnecter. Utilisé pour invalider les sessions d'un compte supprimé."""
    client = get_client()
    try:
        resp = client.auth.admin.get_user_by_id(user_id)
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg or "not_found" in msg or "404" in msg:
            return False
        raise
    user = getattr(resp, "user", None) or resp
    uid = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
    return bool(uid)


def delete_user_account(user_id: str) -> None:
    """Suppression DÉFINITIVE d'un compte : toutes les tables + l'utilisateur
    auth Supabase. Exigence des stores (Google Play / App Store) : la
    suppression de compte doit être disponible dans l'app.

    Ordre : données métier d'abord, auth en dernier — si la suppression auth
    échoue, l'utilisateur peut réessayer (les données restantes seront déjà
    parties, les deletes sont idempotents)."""
    client = get_client()
    # coach_conversations en premier : supprime aussi coach_messages liés
    # (ON DELETE CASCADE) ; le delete coach_messages qui suit couvre les
    # éventuels messages legacy sans conversation_id.
    for table, key in (
        ("coach_conversations", "user_id"),
        ("coach_messages", "user_id"),
        ("nutrition", "user_id"),
        ("body_weight", "user_id"),
        ("session_notes", "user_id"),
        ("push_subscriptions", "user_id"),
        ("history", "user_id"),
        ("programs", "user_id"),
        ("onboarding", "user_id"),
        ("profiles", "id"),
    ):
        try:
            client.table(table).delete().eq(key, user_id).execute()
        except Exception as e:
            # Une table optionnelle absente (migration non appliquée) ne doit
            # pas bloquer la suppression du reste.
            logger.error("delete_user_account %s FAILED user=%s: %s", table, user_id, e)
    clear_user_cache(user_id)
    # Compte auth Supabase (Google OAuth) — en dernier.
    client.auth.admin.delete_user(user_id)


# ────────────────────────────────────────────────────────────
# Bilans de séance (migration v34 : table session_notes, une ligne par
# (user, date, séance)). Avant la migration, les bilans vivaient dans
# programs.data["_session_notes"] avec une purge à 84 jours — l'appelant
# (routes/seance.py) garde ce repli si la table est absente.
# ────────────────────────────────────────────────────────────

# Colonne ajoutée par la migration v35 ; sans elle on écrit le bilan sans durée.
_session_duration_supported = True


def _mark_duration_unsupported():
    global _session_duration_supported
    _session_duration_supported = False
    logger.warning("session_notes.duration_min absente (migration v35 ?) "
                   "— durée de séance non enregistrée")


def _session_note_columns() -> str:
    base = "rating, comment, updated_at"
    return base + ", duration_min" if _session_duration_supported else base


def upsert_session_note(user_id: str, date_str: str, seance: str,
                        rating: int | None, comment: str | None,
                        duration_min: int | None = None) -> None:
    client = get_client()
    payload = {
        "user_id": user_id,
        "date": _norm_date(date_str),
        "seance": seance,
        "rating": int(rating) if rating else None,
        "comment": (comment or "")[:500] or None,
        "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    if duration_min and _session_duration_supported:
        payload["duration_min"] = int(duration_min)
    try:
        client.table("session_notes").upsert(
            payload, on_conflict="user_id,date,seance").execute()
    except Exception as e:
        # Colonne duration_min absente (migration v35 non appliquée) : on
        # ré-essaie sans elle plutôt que de perdre la note et le commentaire.
        if "duration_min" not in str(e).lower():
            raise
        _mark_duration_unsupported()
        payload.pop("duration_min", None)
        client.table("session_notes").upsert(
            payload, on_conflict="user_id,date,seance").execute()


def get_session_note(user_id: str, date_str: str, seance: str) -> dict | None:
    """{rating, comment, duration_min, ts} ou None. Lève si la table est
    absente (repli géré par l'appelant)."""
    client = get_client()
    try:
        resp = (
            client.table("session_notes")
            .select(_session_note_columns())
            .eq("user_id", user_id)
            .eq("date", _norm_date(date_str))
            .eq("seance", seance)
            .limit(1)
            .execute()
        )
    except Exception as e:
        if "duration_min" not in str(e).lower():
            raise
        _mark_duration_unsupported()
        resp = (
            client.table("session_notes")
            .select(_session_note_columns())
            .eq("user_id", user_id)
            .eq("date", _norm_date(date_str))
            .eq("seance", seance)
            .limit(1)
            .execute()
        )
    rows = resp.data or []
    if not rows:
        return None
    r = rows[0]
    out = {"ts": str(r.get("updated_at") or "")[:16].replace("T", " ")}
    if r.get("rating"):
        out["rating"] = int(r["rating"])
    if r.get("comment"):
        out["comment"] = r["comment"]
    if r.get("duration_min"):
        out["duration_min"] = int(r["duration_min"])
    return out


def list_session_notes(user_id: str) -> list[dict]:
    """Tous les bilans de l'user (export, stats)."""
    client = get_client()
    cols = "date, seance, rating, comment"
    if _session_duration_supported:
        cols += ", duration_min"
    try:
        rows = _fetch_all(lambda: (
            client.table("session_notes").select(cols)
            .eq("user_id", user_id).order("date")
        ))
    except Exception as e:
        if "duration_min" not in str(e).lower():
            raise
        _mark_duration_unsupported()
        rows = _fetch_all(lambda: (
            client.table("session_notes").select("date, seance, rating, comment")
            .eq("user_id", user_id).order("date")
        ))
    return [{"date": str(r.get("date") or "")[:10], "seance": r.get("seance") or "",
             "rating": r.get("rating"), "comment": r.get("comment"),
             "duration_min": r.get("duration_min")} for r in rows]


def sum_nutrition_day(user_id: str, date_str: str) -> dict:
    rows = list_nutrition(user_id, date_str)
    out = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    for r in rows:
        out["calories"] += int(r.get("calories") or 0)
        out["protein"] += int(r.get("protein") or 0)
        out["carbs"] += int(r.get("carbs") or 0)
        out["fat"] += int(r.get("fat") or 0)
    return out


def sum_nutrition_range(user_id: str, date_from: str, date_to: str) -> dict:
    """Totaux nutrition par jour sur une plage de dates. Retourne {date_str: {calories, protein, carbs, fat}}."""
    client = get_client()
    resp = (
        client.table("nutrition")
        .select("date, calories, protein, carbs, fat")
        .eq("user_id", user_id)
        .gte("date", date_from)
        .lte("date", date_to)
        .execute()
    )
    by_date = {}
    for r in (resp.data or []):
        d = r.get("date") or ""
        entry = by_date.setdefault(d, {"calories": 0, "protein": 0, "carbs": 0, "fat": 0})
        entry["calories"] += int(r.get("calories") or 0)
        entry["protein"] += int(r.get("protein") or 0)
        entry["carbs"] += int(r.get("carbs") or 0)
        entry["fat"] += int(r.get("fat") or 0)
    return by_date
