"""L'état du compte — la table `etat_compte` (migration v47).

Badges, record de série, défis, « upsell vu », quota de debrief gratuit,
semaine allégée, plats de la semaine et cibles nutrition perso ne sont pas
le programme. Ils vivaient pourtant dans son blob, et l'accueil réécrivait le
programme entier quand un badge tombait. Une ligne par compte, une colonne
par donnée.

La conversion se fait ici, à un seul endroit, appelée par `get_prog` et
`save_prog` (core/db_programme.py) :
  - `superposer` remet ces valeurs dans le programme lu, sous leurs anciennes
    clés : les lecteurs (badges, défis, semaine allégée, nutrition…) ne
    changent pas ;
  - `extraire` les retire du programme à écrire et les range dans la table,
    seulement si elles ont changé. Une écriture qui passe par le programme
    atterrit donc quand même ici.

Base en retard (table absente) : le programme garde tout, comme avant, et la
table est redemandée au bout d'une minute. Sans ligne, un reste dans le
programme fait foi ; la première sauvegarde l'y retire et le range en table.
"""
import datetime as _dt
import logging
import time

from core.db_base import _cache_get, _cache_invalidate, _cache_set, get_client

logger = logging.getLogger(__name__)

# Clé de l'ancien stockage dans le programme → (colonne, valeur vide, type).
CLES_BLOB = {
    "_badges":           ("badges",           [],    list),
    "_streak_record":    ("record_serie",     0,     int),
    "_challenges_done":  ("defis_faits",      [],    list),
    "_challenges_won":   ("defis_gagnes",     0,     int),
    "_upsell_seen":      ("upsell_vu",        False, bool),
    "_debrief_free":     ("debrief_gratuit",  {},    dict),
    "_decharge_semaine": ("decharge_semaine", None,  int),
    "_decharge_ignoree": ("decharge_ignoree", None,  int),
    "_meal_plan":        ("plats_semaine",    None,  dict),
    "_nutrition":        ("nutrition_perso",  None,  dict),
}
COLONNES = tuple(c for c, _v, _t in CLES_BLOB.values())
REESSAI = 60
_absente_depuis = None


def _vide() -> dict:
    return {c: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
            for c, v, _t in CLES_BLOB.values()}


def _marquer_absente():
    global _absente_depuis
    from core.schema import signaler_absence
    signaler_absence("etat_compte")
    _absente_depuis = time.monotonic()
    logger.warning("etat_compte: table absente (v47 non appliquée) — état gardé dans le programme")


def _oublier_absence():
    global _absente_depuis
    _absente_depuis = None


def _disponible() -> bool:
    return _absente_depuis is None or time.monotonic() - _absente_depuis > REESSAI


def _table_absente(err) -> bool:
    msg = str(err).lower()
    return "etat_compte" in msg and any(m in msg for m in (
        "does not exist", "42p01", "pgrst205", "schema cache"))


def _propre(valeur, defaut, type_):
    """La valeur si elle a le bon type, sinon la valeur vide. Un entier lu
    en flottant (139.0) est tronqué ; un compteur négatif reprend sa valeur
    vide, comme dans la migration (la table le refuserait)."""
    if type_ is int:
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)) or valeur != valeur:
            return defaut
        valeur = int(valeur)
        return defaut if (defaut == 0 and valeur < 0) else valeur
    return valeur if isinstance(valeur, type_) else defaut


def _depuis_prog(prog: dict) -> dict:
    return {c: _propre(prog.get(cle), v, t) for cle, (c, v, t) in CLES_BLOB.items()}


def _lire(user_id: str, frais: bool = False):
    """La ligne du compte ({} sans ligne), ou None si la table manque.
    `frais` : relue en base, sans le cache (avant une écriture)."""
    if not _disponible():
        return None
    cle = f"etat:{user_id}"
    ligne = None if frais else _cache_get(cle)
    if ligne is not None:
        return ligne
    try:
        rows = (get_client().table("etat_compte").select(",".join(COLONNES))
                .eq("user_id", user_id).execute().data) or []
    except Exception as e:
        if not _table_absente(e):
            raise
        _marquer_absente()
        return None
    ligne = {c: rows[0].get(c) for c in COLONNES} if rows else {}
    _cache_set(cle, ligne)
    return ligne


def superposer(user_id: str, prog: dict) -> dict:
    """Le programme lu, avec l'état du compte sous ses anciennes clés."""
    ligne = _lire(user_id)
    if not ligne:
        return prog          # table absente ou pas de ligne : le programme fait foi
    for cle, (col, vide, type_) in CLES_BLOB.items():
        valeur = _propre(ligne.get(col), vide, type_)
        if valeur is None:
            prog.pop(cle, None)
        else:
            prog[cle] = valeur
    return prog


def etat_lu(prog: dict) -> dict:
    """Ce que la requête a vu de l'état du compte : la base de `extraire`."""
    return _depuis_prog(prog)


def extraire(user_id: str, prog: dict, base: dict | None = None) -> dict:
    """Le programme à écrire, sans l'état du compte, qui part dans sa table.

    Seules les colonnes que la requête a CHANGÉES depuis sa lecture (`base`)
    sont écrites, par-dessus la ligne relue en base : deux requêtes du même
    compte ne s'écrasent pas (A grave un badge, B enregistre un réglage avec
    son état lu avant : le badge reste — même règle que le verrou du
    programme). Sans base (pas de lecture dans cette requête), tout est écrit.
    Table absente : le programme est rendu tel quel."""
    ligne = _lire(user_id, frais=True)
    if ligne is None:
        return prog
    valeurs = _depuis_prog(prog)
    actuelles = {c: _propre(ligne.get(c), v, t) for c, v, t in CLES_BLOB.values()} if ligne else _vide()
    # Sans ligne, ce que la requête a lu venait du programme (reste d'avant
    # la v47) : c'est la seule copie, elle s'écrit en entier. Sinon, seules
    # les colonnes changées depuis la lecture.
    if base is not None and ligne:
        valeurs = {c: (valeurs[c] if valeurs[c] != base.get(c) else actuelles[c]) for c in valeurs}
    if valeurs != actuelles:
        try:
            get_client().table("etat_compte").upsert({
                "user_id": user_id, **valeurs,
                "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            }, on_conflict="user_id").execute()
        except Exception as e:
            if not _table_absente(e):
                raise
            _marquer_absente()
            return prog
        _cache_invalidate(f"etat:{user_id}")
    return {k: v for k, v in prog.items() if k not in CLES_BLOB}
