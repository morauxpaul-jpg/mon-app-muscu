"""Les réglages de l'utilisateur — la table `reglages` (migration v45).

Ils vivaient dans `programs.data['_settings']`, au milieu du programme : un
sac de clés non typé, et le cron des rappels relisait le blob de chaque
abonné pour connaître son heure. Une ligne par compte, une colonne par
réglage ; pas de ligne = valeurs par défaut.

Base en retard (table absente) : on lit et on écrit dans le blob comme
avant, et on redemande la table au bout d'une minute — la migration
appliquée, elle sert sans redémarrer. Tant qu'un compte n'a pas de ligne, un
reste de `_settings` dans son programme fait foi : rien ne revient aux
valeurs par défaut entre le déploiement et la migration.
"""
import datetime as _dt
import logging
import time

from core.db_base import _fetch_all, get_client

logger = logging.getLogger(__name__)

# Les réglages qui ont un effet, et leur valeur sans choix de l'utilisateur.
# Les mêmes défauts sont posés dans la table (v45).
DEFAUTS = {
    "auto_rest_timer": True,       # chrono de repos à « Série faite »
    "auto_prefill_weight": True,   # charges de la dernière séance
    "show_rpe": True,              # puces RPE dans le détail d'une série
    "show_overload_hint": True,    # suggestion de progression
    "notifications": False,        # rappels, relances et récap
    "reminder_hour": 18,           # heure du rappel (0 = aucun ; core/reminders.py)
    "recap_hebdo": True,           # récap du dimanche (core/recap.py)
}
REESSAI = 60          # secondes avant de redemander une table vue absente
_absente_depuis = None


def _marquer_absente():
    global _absente_depuis
    _absente_depuis = time.monotonic()
    logger.warning("reglages: table absente (v45 non appliquée) — réglages lus dans le programme")


def _oublier_absence():
    global _absente_depuis
    _absente_depuis = None


def _disponible() -> bool:
    return _absente_depuis is None or time.monotonic() - _absente_depuis > REESSAI


def _table_absente(err) -> bool:
    msg = str(err).lower()
    return "reglages" in msg and any(m in msg for m in (
        "does not exist", "42p01", "pgrst205", "schema cache"))


def _completer(valeurs) -> dict:
    """Les réglages connus, avec leur défaut pour ceux qui manquent. Une clé
    inconnue (ancien réglage sans effet) est ignorée."""
    out = dict(DEFAUTS)
    if isinstance(valeurs, dict):
        out.update({k: valeurs[k] for k in DEFAUTS if valeurs.get(k) is not None})
    return out


def _lignes(uids: list) -> dict | None:
    """{user_id: ligne} pour ces comptes, ou None si la table manque."""
    if not _disponible():
        return None
    if not uids:
        return {}
    client = get_client()
    out = {}
    try:
        for i in range(0, len(uids), 100):
            lot = uids[i:i + 100]
            for r in _fetch_all(lambda: (
                client.table("reglages").select("user_id," + ",".join(DEFAUTS))
                .in_("user_id", lot).order("user_id")
            )):
                out[r["user_id"]] = r
    except Exception as e:
        if not _table_absente(e):
            raise
        _marquer_absente()
        return None
    return out


def lire_reglages(user_id: str, prog: dict | None = None) -> dict:
    """Les réglages d'un compte. `prog` (son programme) sert de repli tant
    qu'il n'a pas de ligne, ou si la table manque."""
    lignes = _lignes([user_id]) or {}
    if user_id in lignes:
        return _completer(lignes[user_id])
    return _completer((prog or {}).get("_settings"))


def reglages_pour(progs: list) -> dict:
    """{user_id: réglages} pour les crons : une requête par lot de 100
    comptes. `progs` = [{user_id, data}] ; le blob sert de repli comme dans
    `lire_reglages`."""
    par_uid = {r.get("user_id"): (r.get("data") or {}) for r in progs or [] if r.get("user_id")}
    lignes = _lignes(sorted(par_uid)) or {}
    return {uid: _completer(lignes[uid]) if uid in lignes else _completer(data.get("_settings"))
            for uid, data in par_uid.items()}


def ecrire_reglages(user_id: str, valeurs: dict) -> bool:
    """Enregistre les réglages. False si la table manque : l'appelant les
    range alors dans le programme, comme avant la v45."""
    if not _disponible():
        return False
    ligne = {"user_id": user_id, **_completer(valeurs),
             "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
    try:
        get_client().table("reglages").upsert(ligne, on_conflict="user_id").execute()
    except Exception as e:
        if not _table_absente(e):
            raise
        _marquer_absente()
        return False
    return True
