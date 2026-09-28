"""Le programme — un blob JSON dans `programs.data`.

Le programme, le planning, les réglages, les badges et une vingtaine de calques
`_x` vivent dans une seule colonne JSON. `save_prog` fusionne donc trois
versions (la base lue par ce process, la nôtre, celle en base) pour qu'un
onglet n'écrase pas ce qu'un autre vient d'écrire, et `replace_program_body`
distingue le corps métier des données personnelles.

Cette forme est de la dette assumée : elle est nommée dans le rapport d'audit.
Ce module la contient.
"""
import json
import logging
from collections import OrderedDict

from core import db_base
from core.db_base import _cache_get, _cache_invalidate, _cache_set, get_client

logger = logging.getLogger(__name__)

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
    while len(_prog_base) > db_base._CACHE_MAX:
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
