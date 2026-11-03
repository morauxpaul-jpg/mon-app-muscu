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
# Colonnes venues après la v45 : lues et écrites seulement si la base les a.
# Sans ce tri, une colonne manquante faisait passer TOUTE la table pour
# absente (l'erreur cite « reglages ») et chaque réglage retombait sur le
# programme jusqu'à la migration.
OPTIONNELS = {
    "notifs_amis": True,           # notifications des amis (v54, core/push_amis.py)
}
_OPTIONNELS_OK = {c: True for c in OPTIONNELS}
REESSAI = 60          # secondes avant de redemander une table vue absente
_absente_depuis = None


def _colonnes_lues() -> list:
    return list(DEFAUTS) + [c for c in OPTIONNELS if _OPTIONNELS_OK[c]]


def _optionnelle_absente(err) -> str | None:
    """L'optionnelle qu'une erreur PostgREST désigne comme inconnue, signalée
    à /admin ; ou None."""
    msg = str(err).lower()
    if not any(m in msg for m in ("42703", "pgrst204", "does not exist", "could not find")):
        return None
    col = next((c for c in OPTIONNELS if _OPTIONNELS_OK[c] and c in msg), None)
    if col:
        from core.schema import signaler_absence
        signaler_absence("reglages", col)
        _OPTIONNELS_OK[col] = False
        logger.warning("reglages : colonne %s absente — lue et écrite sans elle", col)
    return col


def _marquer_absente():
    global _absente_depuis
    from core.schema import signaler_absence
    signaler_absence("reglages")
    _absente_depuis = time.monotonic()
    logger.warning("reglages: table absente (v45 non appliquée) — réglages lus dans le programme")


def _oublier_absence():
    global _absente_depuis
    _absente_depuis = None
    _OPTIONNELS_OK.update({c: True for c in OPTIONNELS})


def _disponible() -> bool:
    return _absente_depuis is None or time.monotonic() - _absente_depuis > REESSAI


def _table_absente(err) -> bool:
    msg = str(err).lower()
    return "reglages" in msg and any(m in msg for m in (
        "does not exist", "42p01", "pgrst205", "schema cache"))


def _completer(valeurs) -> dict:
    """Les réglages connus, avec leur défaut pour ceux qui manquent. Une clé
    inconnue (ancien réglage sans effet) est ignorée."""
    out = {**DEFAUTS, **OPTIONNELS}
    if isinstance(valeurs, dict):
        out.update({k: valeurs[k] for k in out if valeurs.get(k) is not None})
    return out


def _lignes(uids: list) -> dict | None:
    """{user_id: ligne} pour ces comptes, ou None si la table manque."""
    if not _disponible():
        return None
    if not uids:
        return {}
    client = get_client()
    out = {}
    while True:
        try:
            for i in range(0, len(uids), 100):
                lot = uids[i:i + 100]
                for r in _fetch_all(lambda: (
                    client.table("reglages").select("user_id," + ",".join(_colonnes_lues()))
                    .in_("user_id", lot).order("user_id")
                )):
                    out[r["user_id"]] = r
            return out
        except Exception as e:
            if _optionnelle_absente(e):
                continue
            if not _table_absente(e):
                raise
            _marquer_absente()
            return None


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
    while True:
        complets = _completer(valeurs)
        ligne = {"user_id": user_id, **{c: complets[c] for c in _colonnes_lues()},
                 "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat()}
        try:
            get_client().table("reglages").upsert(ligne, on_conflict="user_id").execute()
            return True
        except Exception as e:
            if _optionnelle_absente(e):
                continue
            if not _table_absente(e):
                raise
            _marquer_absente()
            return False
