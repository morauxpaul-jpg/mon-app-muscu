"""Connexion Supabase et cache mémoire — le socle des modules `db_*`.

Tout ce qui lit ou écrit passe par `get_client()`. Le client est unique pour
le process et porte la clé `service_role`, qui **contourne le RLS** : chaque
requête doit donc filtrer explicitement par `user_id`. C'est la contrainte qui
tient toute la couche données, et la raison pour laquelle elle se relit module
par module plutôt que dans un seul fichier de 1 700 lignes.

Les tests substituent une fausse base avec `use_client()`.

Config : deux variables d'env requises
  - SUPABASE_URL
  - SUPABASE_SERVICE_ROLE_KEY   (jamais exposée au client)
"""
import datetime as _dt
import os
import threading
import time
import uuid
from collections import OrderedDict
from typing import Optional

from supabase import create_client, Client

from core import partage
from core.dates import continuous_week

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
    """Lit une env var et nettoie espaces + quotes parasites (Railway copie
    parfois des valeurs entourées de guillemets ou des noms avec espaces)."""
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


# ── Cache mémoire (TTL 60 s), clé par user_id, cohérent entre instances ──
# Borné (LRU) : sans plafond, chaque user actif laisserait son historique
# complet en RAM du worker jusqu'à expiration.
#
# Chaque instance garde ses valeurs, mais la VALIDITÉ est partagée : une
# écriture incrémente le numéro de génération de la clé (`core/partage.py`,
# dans Redis quand il y en a un) et une entrée n'est servie que si les
# numéros lus avant sa lecture en base n'ont pas bougé. Avant, le cache n'était
# juste qu'avec UN processus : avec deux, l'un servait l'ancien historique
# jusqu'à 60 s après une écriture sur l'autre (audit du 30/09, I8 ; 03/10, I11).
#
# Le même mécanisme règle la course lecture lente / écriture : une requête lit
# la base (cache vide), une autre écrit et invalide, puis la première remettait
# en cache l'ANCIENNE valeur (F1). Elle porte les numéros d'avant l'écriture :
# elle n'est jamais servie.
_CACHE_MAX = 200
_data_cache: "OrderedDict[str, dict]" = OrderedDict()
_cache_lock = threading.RLock()
_TTL = 60.0
# Le profil porte le tier VIP : TTL court pour qu'un passage PRO (Stripe,
# admin) se propage vite à toutes les requêtes (cf. FREE_RECHECK_TTL app.py).
_PROFILE_TTL = 15.0
_TOUT = "*"                    # génération de « tout le cache » (vider_cache)
_lectures = threading.local()


def _debuts() -> dict:
    """Clé → générations lues par CE fil juste avant sa lecture en base."""
    d = getattr(_lectures, "debuts", None)
    if d is None:
        d = _lectures.debuts = {}
    return d


def _generations(key: str):
    """Numéros actuels (clé, tout), ou None : Redis en panne, pas de cache."""
    return partage.generations([f"cache:{key}", f"cache:{_TOUT}"])


def _cache_get(key: str, ttl: float | None = None):
    gens = _generations(key)
    with _cache_lock:
        entry = _data_cache.get(key)
        if entry is not None and (gens is None or entry["gens"] != gens
                                  or (time.time() - entry["ts"]) >= (ttl or _TTL)):
            _data_cache.pop(key, None)
            entry = None
        if entry is None:
            _debuts()[key] = gens            # ce fil va lire la base
            return None
        _debuts().pop(key, None)
        _data_cache.move_to_end(key)
        return entry["value"]


def _ranger(key: str, value, gens) -> None:
    with _cache_lock:
        _data_cache[key] = {"value": value, "ts": time.time(), "gens": gens}
        _data_cache.move_to_end(key)
        while len(_data_cache) > _CACHE_MAX:
            _data_cache.popitem(last=False)


def _cache_set(key: str, value):
    """Range ce que ce fil vient de lire, avec les numéros d'AVANT sa lecture :
    si une écriture est passée entre-temps, l'entrée ne sera jamais servie."""
    with _cache_lock:
        gens = _debuts().pop(key, None) if key in _debuts() else _generations(key)
    if gens is not None:
        _ranger(key, value, gens)


def _cache_modifier(key: str, corriger) -> None:
    """Après une écriture : invalide la clé partout, et corrige l'entrée de
    CETTE instance au lieu de la jeter (`corriger(ancienne) → nouvelle`).

    La correction n'est gardée que si personne d'autre n'a écrit entre la
    lecture de l'entrée et notre invalidation (numéro avancé d'exactement 1) :
    sinon elle mélangerait notre écriture à une donnée déjà périmée."""
    avant = _generations(key)
    with _cache_lock:
        entry = _data_cache.pop(key, None)
    apres = partage.nouvelle_generation(f"cache:{key}")
    if (entry is None or avant is None or apres is None or entry["gens"] != avant
            or apres != avant[1] + 1 or (time.time() - entry["ts"]) >= _TTL):
        return
    _ranger(key, corriger(entry["value"]), (avant[0], apres, *avant[2:]))


def _cache_invalidate(key: str):
    with _cache_lock:
        _data_cache.pop(key, None)
    partage.nouvelle_generation(f"cache:{key}")


def vider_cache():
    """Vide tout le cache, et refuse les lectures commencées avant."""
    with _cache_lock:
        _data_cache.clear()
    partage.nouvelle_generation(f"cache:{_TOUT}")


def clear_user_cache(user_id: str):
    """Invalide explicitement toutes les entrées cache d'un utilisateur.
    Appelé après chaque save réussi pour éviter les séances vides au reload."""
    for prefix in ("hist", "prog", "profile", "onboarding", "etat"):
        _cache_invalidate(f"{prefix}:{user_id}")


def use_client(client) -> None:
    """Impose le client (les tests y branchent leur fausse base).

    Passer `None` rend la main au vrai client, reconstruit au prochain appel.
    C'est un point d'entrée et non une affectation directe de `_client` :
    depuis le découpage, `get_client()` vit ici et une affectation faite
    ailleurs ne serait plus lue.
    """
    global _client
    _client = client


def current_client():
    """Le client en place, sans en construire un. `None` si aucun.

    Sert à `run_local_fake.py`, qui a besoin de la fausse base elle-même pour
    la remplir. Lire `_client` de l'extérieur ne marcherait plus : depuis le
    découpage, il n'existe que dans ce module.
    """
    return _client
