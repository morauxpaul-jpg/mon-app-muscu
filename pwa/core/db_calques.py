"""Les calques du jour — la table `calques_seance` (migration v46).

Exercices ajoutés à la volée, brouillon de séance libre, échanges du jour,
ordre des cartes : ils vivaient dans le blob du programme, indexés par
« séance|date ». Chaque geste relisait et réécrivait le programme entier,
passait par son verrou optimiste et pouvait entrer en conflit avec une
modification du programme. Une ligne par séance et par date, une colonne
par calque ; une ligne vide n'est pas gardée.

Base en retard (table absente) : lecture et écriture dans le programme,
comme avant, et la table est redemandée au bout d'une minute (même règle que
`core/db_reglages.py`). Sans ligne, un reste de calque dans le programme
s'affiche encore : rien ne disparaît entre le déploiement et la migration.
"""
import datetime as _dt
import logging
import time
from datetime import timedelta

from core import partage
from core.dates import logical_today_paris
from core.db_base import get_client
from core.db_historique import _norm_date
from core.db_programme import get_prog, lire_prog, save_prog

logger = logging.getLogger(__name__)

# Colonne de la table → clé de l'ancien stockage dans le programme.
CLES_BLOB = {"extras": "_extras", "brouillon": "_libre_draft",
             "substituts": "_substituts", "ordre": "_seance_order"}
GARDE_JOURS = 84      # même fenêtre que la purge historique (12 semaines)
REESSAI = 60
_absente_depuis = None


def _vide() -> dict:
    return {"extras": [], "brouillon": [], "substituts": {}, "ordre": []}


def _marquer_absente():
    global _absente_depuis
    _absente_depuis = time.monotonic()
    logger.warning("calques_seance: table absente (v46 non appliquée) — calques dans le programme")


def _oublier_absence():
    global _absente_depuis
    _absente_depuis = None


def _disponible() -> bool:
    return _absente_depuis is None or time.monotonic() - _absente_depuis > REESSAI


def _table_absente(err) -> bool:
    msg = str(err).lower()
    return "calques_seance" in msg and any(m in msg for m in (
        "does not exist", "42p01", "pgrst205", "schema cache"))


def _completer(ligne) -> dict:
    out = _vide()
    for champ, defaut in out.items():
        v = (ligne or {}).get(champ)
        if isinstance(v, type(defaut)):
            out[champ] = v
    return out


def _depuis_prog(prog, seance, date) -> dict:
    cle = f"{seance}|{date}"
    return _completer({c: (prog.get(b) or {}).get(cle) for c, b in CLES_BLOB.items()})


def _table(fn):
    """Exécute `fn(client)` sur la table ; None si elle manque."""
    if not _disponible():
        return None
    try:
        return fn(get_client())
    except Exception as e:
        if not _table_absente(e):
            raise
        _marquer_absente()
        return None


def _ligne(client, user_id, seance, date):
    rows = (client.table("calques_seance").select("extras,brouillon,substituts,ordre")
            .eq("user_id", user_id).eq("seance", seance).eq("date", date).execute().data) or []
    return rows[0] if rows else None


def lire_calque(user_id: str, seance: str, date: str, prog: dict | None = None) -> dict:
    """Les quatre calques d'une séance ce jour-là. `prog` (le programme déjà
    lu par l'appelant) sert de repli sans ligne ou sans table."""
    date = _norm_date(date)
    ligne = _table(lambda c: _ligne(c, user_id, seance, date) or False)
    if ligne:
        return _completer(ligne)
    if prog is None:
        prog = lire_prog(user_id)
    return _depuis_prog(prog or {}, seance, date)


def _enregistrer(client, user_id, seance, date, valeurs):
    if not any(valeurs.values()):
        (client.table("calques_seance").delete().eq("user_id", user_id)
         .eq("seance", seance).eq("date", date).execute())
        return True
    client.table("calques_seance").upsert({
        "user_id": user_id, "seance": seance, "date": date, **valeurs,
        "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }, on_conflict="user_id,seance,date").execute()
    return True


def modifier_calque(user_id: str, seance: str, date: str, champ: str, fn) -> None:
    """Applique `fn(valeur) -> nouvelle valeur` à un calque. Sous verrou :
    deux taps rapprochés (« + exercice » deux fois) ne s'écrasent pas."""
    if champ not in CLES_BLOB:
        raise ValueError(champ)
    date = _norm_date(date)
    with partage.verrou("calque", user_id, seance, date):
        prog = get_prog(user_id)      # copie : modifiée et réécrite en repli
        valeurs = lire_calque(user_id, seance, date, prog)
        valeurs[champ] = fn(valeurs[champ])
        if _table(lambda c: _enregistrer(c, user_id, seance, date, valeurs)):
            return
        # Base en retard : dans le programme, comme avant.
        store = prog.setdefault(CLES_BLOB[champ], {})
        if valeurs[champ]:
            store[f"{seance}|{date}"] = valeurs[champ]
        else:
            store.pop(f"{seance}|{date}", None)
        save_prog(user_id, prog)


def ecrire_calque(user_id: str, seance: str, date: str, champ: str, valeur) -> None:
    modifier_calque(user_id, seance, date, champ, lambda _ancien: valeur)


def effacer_calques(user_id: str, seance: str, date: str, champs=None) -> None:
    """Fin de séance : vide ces calques (tous par défaut) pour ce jour."""
    champs = tuple(champs or CLES_BLOB)
    date = _norm_date(date)

    def effacer(client):
        ligne = _ligne(client, user_id, seance, date)
        if ligne:
            valeurs = _completer(ligne)
            for c in champs:
                valeurs[c] = _vide()[c]
            _enregistrer(client, user_id, seance, date, valeurs)
        return True
    _table(effacer)


def purger_calques(user_id: str, aujourd_hui=None) -> None:
    """Les séances ouvertes puis abandonnées ne passent jamais par la fin de
    séance : leurs calques partent après la fenêtre de 84 jours."""
    jour = (aujourd_hui or logical_today_paris()) - timedelta(days=GARDE_JOURS + 1)

    def purger(client):
        (client.table("calques_seance").delete().eq("user_id", user_id)
         .lte("date", jour.isoformat()).execute())
        return True
    _table(purger)


def renommer_seance_calques(user_id: str, ancien: str, nouveau: str) -> None:
    def renommer(client):
        (client.table("calques_seance").update({"seance": nouveau})
         .eq("user_id", user_id).eq("seance", ancien).execute())
        return True
    _table(renommer)


def effacer_tous_calques(user_id: str) -> None:
    def effacer(client):
        client.table("calques_seance").delete().eq("user_id", user_id).execute()
        return True
    _table(effacer)
