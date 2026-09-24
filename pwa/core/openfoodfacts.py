"""Recherche d'un produit emballé par code-barres, via Open Food Facts.

La base d'aliments maison (`core/foods_data.py`) couvre les aliments courants
avec des valeurs moyennes. Elle ne peut pas couvrir les produits de marque :
un skyr, une barre protéinée ou un pain de mie n'ont pas les mêmes macros
d'une marque à l'autre. Scanner l'étiquette évite de tout retaper.

Open Food Facts est une base ouverte (ODbL), sans clé d'API. Deux règles de
leur documentation sont respectées ici : un User-Agent identifiant l'app, et
pas de martèlement — d'où le cache mémoire.

Le réseau peut être lent ou absent : toutes les erreurs sont avalées et
renvoient None. L'appelant affiche alors « produit introuvable » et l'user
passe en saisie manuelle — jamais de page en erreur.
"""
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

API_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
FIELDS = ("product_name,product_name_fr,generic_name_fr,generic_name,brands,"
          "quantity,serving_size,serving_quantity,nutriments,nutriscore_grade")
# Open Food Facts demande un User-Agent identifiant l'application appelante.
USER_AGENT = "MuscuTrackerPRO/1.0 (https://muscu-tracker.app)"
TIMEOUT = 6.0

# Un code-barres EAN-8/UPC-A/EAN-13/ITF-14 : 8 à 14 chiffres.
CODE_RE = re.compile(r"^\d{8,14}$")

# Cache mémoire par worker. Les gens scannent les mêmes produits (leur skyr du
# matin) et l'app tourne en gthread : un verrou suffit, pas besoin de Redis.
_CACHE_TTL = 12 * 3600
_CACHE_MAX = 300
_cache: dict = {}
_cache_lock = threading.Lock()

KJ_PER_KCAL = 4.184


def clean_code(raw) -> str:
    """Code-barres normalisé, ou "" s'il est invalide.

    Les scanners renvoient parfois des espaces ou des tirets ; certains codes
    EAN-13 courts arrivent sur 12 chiffres avec un zéro de tête implicite —
    on ne tente pas de le deviner, Open Food Facts accepte les deux formes.
    """
    s = re.sub(r"[^0-9]", "", str(raw or ""))
    return s if CODE_RE.match(s) else ""


def _num(value):
    """Nombre positif, ou None. Open Food Facts renvoie parfois des chaînes."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def _kcal_100g(nutriments: dict):
    """kcal pour 100 g. L'étiquette européenne donne des kJ : on convertit."""
    kcal = _num(nutriments.get("energy-kcal_100g"))
    if kcal is not None:
        return kcal
    kj = _num(nutriments.get("energy-kj_100g"))
    if kj is None and (nutriments.get("energy_unit") or "").lower() == "kj":
        kj = _num(nutriments.get("energy_100g"))
    if kj is not None:
        return kj / KJ_PER_KCAL
    # Dernier recours : `energy_100g` sans unité déclarée. Au-delà de 900,
    # aucune denrée n'atteint cette valeur en kcal (l'huile pure plafonne à
    # ~900) : c'est donc des kJ.
    raw = _num(nutriments.get("energy_100g"))
    if raw is None:
        return None
    return raw / KJ_PER_KCAL if raw > 900 else raw


def serving_grams(product: dict):
    """Grammes d'une portion déclarée, ou None.

    `serving_quantity` est déjà numérique chez Open Food Facts mais absent de
    beaucoup de fiches ; on retombe sur le texte libre (« 30 g », « 2 tranches
    (50g) »). Les millilitres sont assimilés aux grammes : pour un yaourt ou
    une boisson l'écart est négligeable devant l'imprécision des étiquettes.
    """
    qty = _num(product.get("serving_quantity"))
    if qty and 1 <= qty <= 1500:
        return round(qty)
    text = str(product.get("serving_size") or "")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(g|gr|ml|cl)\b", text, re.I)
    if not m:
        return None
    val = _num(m.group(1).replace(",", "."))
    if val is None:
        return None
    if m.group(2).lower() == "cl":
        val *= 10
    return round(val) if 1 <= val <= 1500 else None


def _label(product: dict) -> str:
    for key in ("product_name_fr", "product_name", "generic_name_fr", "generic_name"):
        name = str(product.get(key) or "").strip()
        if name:
            return name[:80]
    return ""


def _http_get(url: str) -> dict | None:
    """Réponse JSON, ou None. Isolé pour être remplacé dans les tests."""
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            # 2 Mo de garde-fou : une fiche produit pèse quelques kilo-octets.
            raw = resp.read(2_000_000)
        return json.loads(raw.decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        logger.warning("openfoodfacts fetch failed (%s): %s", url, e)
        return None


def _cache_get(code: str):
    now = time.time()
    with _cache_lock:
        entry = _cache.get(code)
        if entry and now - entry[0] < _CACHE_TTL:
            return entry[1]
        if entry:
            _cache.pop(code, None)
    return None


def _cache_put(code: str, value):
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX:
            # Purge grossière : on vide la moitié la plus ancienne. Un LRU
            # complet n'apporterait rien à cette échelle.
            for old in sorted(_cache, key=lambda k: _cache[k][0])[:_CACHE_MAX // 2]:
                _cache.pop(old, None)
        _cache[code] = (time.time(), value)


def normalize(product: dict, code: str) -> dict | None:
    """Fiche Open Food Facts → aliment au format de `core/foods_data.py`.

    Retourne None si la fiche existe mais n'a pas de valeurs nutritionnelles :
    c'est fréquent sur les produits peu renseignés, et un aliment à 0 kcal
    fausserait silencieusement la journée de l'utilisateur.
    """
    nutriments = product.get("nutriments") or {}
    kcal = _kcal_100g(nutriments)
    name = _label(product)
    if kcal is None or not name:
        return None

    brand = str(product.get("brands") or "").split(",")[0].strip()[:40]
    portion = serving_grams(product)
    units = []
    if portion:
        # Libellé sans les grammes : le sélecteur de portion les ajoute déjà
        # (« 1 portion (30 g) »), sinon ils s'affichent deux fois.
        units.append(["1 portion", portion])
    units.append(["100 g", 100])

    return {
        "n": name,
        "k": round(kcal, 1),
        "p": round(_num(nutriments.get("proteins_100g")) or 0, 1),
        "c": round(_num(nutriments.get("carbohydrates_100g")) or 0, 1),
        "f": round(_num(nutriments.get("fat_100g")) or 0, 1),
        "g": brand or "Produit scanné",
        "r": 0,
        "u": units,
        "code": code,
        "brand": brand,
        "nutriscore": str(product.get("nutriscore_grade") or "").strip().lower()[:1],
        "quantity": str(product.get("quantity") or "").strip()[:30],
    }


def lookup(code: str) -> dict | None:
    """Produit normalisé pour un code-barres, ou None (inconnu ou réseau HS).

    Le cache mémorise aussi les échecs (valeur None) : un code inconnu re-scanné
    trois fois de suite ne déclenche pas trois appels.
    """
    code = clean_code(code)
    if not code:
        return None

    cached = _cache_get(code)
    if cached is not None:
        return cached or None

    data = _http_get(API_URL.format(code=code) + "?fields=" + FIELDS)
    if data is None:
        # Panne réseau : on ne met PAS en cache, le prochain essai doit retenter.
        return None

    product = data.get("product") if isinstance(data, dict) else None
    food = normalize(product, code) if isinstance(product, dict) else None
    _cache_put(code, food or False)
    return food
