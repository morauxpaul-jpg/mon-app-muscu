"""Les séries enregistrées — la table `history`.

C'est la source de vérité de l'app : les vues séance, les statistiques et le
calendrier se reconstruisent à partir de ces lignes. Une opération qui en perd
une perd un entraînement, silencieusement — d'où les tests de non-régression
qui entourent chaque fonction de ce module.
"""
import datetime as _dt
import logging

from core import partage
from core.db_base import (_cache_get, _cache_invalidate, _cache_modifier, _cache_set,
                          _continuous_week_of, _fetch_all, get_client, session_id_for)
from core.hist import CARDIO_PREFIX, TYPE_ECHAUFFEMENT
from core.muscu import parse_rpe
from core.db_colonnes import _COLONNES, _colonne_refusee, _noms, sans_colonnes_absentes
from core.seance_cardio import COLONNES_CARDIO, depuis_colonnes, vers_colonnes

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
# Historique des séries
# ────────────────────────────────────────────────────────────

def get_hist(user_id: str, echauffement: bool = False) -> list[dict]:
    """L'historique de l'user (clés Semaine/Séance/Exercice/...). Sans les
    séries d'échauffement, sauf `echauffement=True` (carte de séance, export) :
    tout le reste — records, suggestions, volume — les ignore ainsi d'office."""
    key = f"hist:{user_id}"
    cached = _cache_get(key)
    if cached is None:
        cached = [_nettoyer_ligne(r) for r in _lire_history(get_client(), user_id)]
        _cache_set(key, cached)
    return [dict(r) for r in cached
            if echauffement or r.get("Type") != TYPE_ECHAUFFEMENT]


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
    exercice = r.get("exercice") or ""
    # Cardio (v44) : mesures dans leurs colonnes en base, forme d'origine
    # dans l'app (Reps = minutes, Poids = distance, Cal/Vit en remarque).
    cardio = depuis_colonnes(r) if exercice.startswith(CARDIO_PREFIX) else None
    return {
        "Semaine": week,
        "Séance": r.get("seance") or "",
        "Exercice": exercice,
        "Série": int(r.get("serie") or 1),
        "Reps": cardio["reps"] if cardio else int(r.get("reps") or 0),
        "Poids": cardio["poids"] if cardio else float(r.get("poids") or 0),
        "Remarque": cardio["remarque"] if cardio else remarque,
        **({k: cardio[k] for k in ("Duree", "Distance", "Calories", "Vitesse")} if cardio else {}),
        "Muscle": r.get("muscle") or "",
        "Date": date_str,
        "RPE": float(rpe) if rpe is not None else None,
        **({"ExoId": r["exercise_id"]} if r.get("exercise_id") else {}),
        **({"Type": TYPE_ECHAUFFEMENT} if r.get("type_serie") == TYPE_ECHAUFFEMENT else {}),
    }


def _reporter_dans_le_cache(user_id, date_str, seance, exercice, payload, exo_id=None):
    """Après avoir réécrit les séries d'un exercice, on corrige l'historique
    en cache au lieu de le jeter. Le jeter forçait la relecture complète de
    l'historique juste après chaque « Série faite » — 4 pages sur un an
    d'entraînement, pour des lignes qu'on venait soi-même d'écrire (audit du
    30/09, I15). Sans cache, rien à corriger : la prochaine lecture lira."""
    def corriger(cached):
        garde = [r for r in cached
                 if not (r.get("Date") == date_str and r.get("Séance") == seance
                         and (r.get("Exercice") == exercice
                              or (exo_id and r.get("ExoId") == exo_id)))]
        return garde + [_nettoyer_ligne(p) for p in payload]

    # Invalide aussi la clé sur les autres instances : leur copie est périmée.
    _cache_modifier(f"hist:{user_id}", corriger)


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

# Les seules colonnes que `get_hist` regarde (`select("*")` doublait le
# transfert). `id` n'y est pas : PostgREST sait trier sur une colonne non lue.
_HIST_COLS_LUES = "date,semaine,seance,exercice,serie,reps,poids,remarque,muscle"

def _lire_history(client, user_id: str) -> list[dict]:
    """Les lignes d'historique d'un user, colonnes utiles seulement. Une
    colonne facultative absente (base en retard) fait échouer la requête : on
    la retire, une fois pour toutes, comme `_insert_history` à l'écriture."""
    global _hist_ext_supported

    def lire(colonnes):
        return _fetch_all(lambda: (
            client.table("history").select(colonnes)
            .eq("user_id", user_id).order("id")))

    while True:
        cols = _HIST_COLS_LUES + (",rpe" if _hist_ext_supported else "") \
            + "".join("," + n for c, ok in _COLONNES.items() if ok for n in _noms(c))
        try:
            return lire(cols)
        except Exception as e:
            msg = str(e).lower()
            refusee = _colonne_refusee(msg)
            if refusee:
                logger.warning("history: colonne %s absente — lecture sans elle", refusee)
                _COLONNES[refusee] = False
            elif _hist_ext_supported and "rpe" in msg:
                logger.warning("history: colonne rpe absente (%s) — lecture sans elle", e)
                _hist_ext_supported = False
            else:
                raise


# Une série = une clé (migration v41, index unique). Écrire PAR CLÉ rend une
# écriture rejouée inoffensive : la requête que le téléphone a abandonnée à
# 8 s et renvoyée réécrit les mêmes lignes au lieu de les doubler (audit du
# 03/10, I7). Le verrou par exercice ne protégeait qu'un seul processus ;
# l'index protège la base, quel que soit le nombre d'instances.
CLE_SERIE = "user_id,date,seance,exercice,serie"
_unicite = True     # passe à False si l'index v41 manque (erreur 42P10)


def _index_absent(err) -> bool:
    msg = str(err)
    return "42P10" in msg or "no unique or exclusion constraint" in msg


def _series_distinctes(payload: list[dict]) -> list[dict]:
    """Deux lignes d'un même envoi sur la même clé (fichier importé qui
    numérote deux fois la série 1) : la seconde prend le numéro suivant libre.
    Sans ça, l'index les fusionnerait et une série disparaîtrait."""
    vus, plus_haut = set(), {}
    for p in payload:
        g = (p["user_id"], p["date"], p["seance"], p["exercice"])
        plus_haut[g] = max(plus_haut.get(g, 0), int(p["serie"]))
    out = []
    for p in payload:
        g = (p["user_id"], p["date"], p["seance"], p["exercice"])
        if (*g, p["serie"]) in vus:
            plus_haut[g] += 1
            p = {**p, "serie": plus_haut[g]}
        vus.add((*g, p["serie"]))
        out.append(p)
    return out


def _insert_history(client, payload: list[dict], par_cle: bool = False, ignorer: bool = False):
    """Insère (par défaut) ou écrit par clé de série (`par_cle`, upsert ;
    `ignorer` = laisser intactes les séries déjà présentes). Retourne la
    réponse, ou None si l'écriture par clé est impossible (index v41 absent) :
    l'appelant reprend alors l'ancien chemin."""
    global _hist_ext_supported, _unicite
    if par_cle and not _unicite:
        return None
    origine, payload = payload, sans_colonnes_absentes(payload)

    def _ecrire(rows):
        t = client.table("history")
        if par_cle:
            return t.upsert(rows, on_conflict=CLE_SERIE, ignore_duplicates=ignorer).execute()
        return t.insert(rows).execute()

    if not _hist_ext_supported:
        payload = [{k: v for k, v in p.items() if k not in _HIST_EXT_COLS} for p in payload]
    try:
        return _ecrire(payload)
    except Exception as e:
        if par_cle and _index_absent(e):
            logger.warning("history: index unique v41 absent (%s) — écriture sans clé", e)
            _unicite = False
            return None
        msg = str(e).lower()
        if "history_cardio_colonnes_check" in msg and not _COLONNES["cardio"]:
            # La v44 a été appliquée après que ce processus a vu les colonnes
            # absentes : la base refuse désormais l'ancien format.
            logger.warning("history: colonnes cardio v44 présentes — retour au nouveau format")
            _COLONNES["cardio"] = True
            return _insert_history(client, origine, par_cle, ignorer)
        refusee = _colonne_refusee(msg)
        if refusee:
            logger.warning("history: colonne %s absente — écriture sans elle", refusee)
            _COLONNES[refusee] = False
            return _insert_history(client, payload, par_cle, ignorer)
        if not _hist_ext_supported or not any(c in msg for c in _HIST_EXT_COLS):
            raise
        logger.warning("history: colonnes v34 absentes (%s) — insert sans session_id/rpe", e)
        _hist_ext_supported = False
        return _ecrire([{k: v for k, v in p.items() if k not in _HIST_EXT_COLS} for p in payload])


def _row_to_supabase(user_id: str, r: dict) -> dict:
    date_val = r.get("Date")
    remarque = r.get("Remarque") or ""
    rpe = r.get("RPE")
    if rpe is None:
        rpe = parse_rpe(remarque)
    seance = r.get("Séance") or ""
    ligne = {
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
        "exercise_id": r.get("ExoId") or None,
        "type_serie": TYPE_ECHAUFFEMENT if r.get("Type") == TYPE_ECHAUFFEMENT else None,
        **{c: None for c in COLONNES_CARDIO},
    }
    if ligne["exercice"].startswith(CARDIO_PREFIX):
        ligne.update(vers_colonnes(ligne["reps"], ligne["poids"], remarque, r.get("Duree")))
    return ligne

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


# Deux écritures croisées du même exercice (requête abandonnée à 8 s par le
# téléphone, encore en cours, puis la série suivante) doublaient les séries
# (audit du 03/10, I7, R9). Le verrou par exercice les met en file, sur toutes
# les instances quand Redis est là (`core/partage.py`) ; l'index unique v41
# (CLE_SERIE) garantit le reste en base.
def _verrou(user_id, date_str, seance, exercice):
    return partage.verrou("exo", user_id, date_str, seance, exercice)


def replace_exo_rows(user_id: str, date_str: str, seance: str, exercice: str, new_rows: list[dict],
                     exo_id: str | None = None):
    date_str = _norm_date(date_str)
    with _verrou(user_id, date_str, seance, exercice):
        _replace_exo_rows(user_id, date_str, seance, exercice, new_rows, exo_id)


def _ids_cibles(client, user_id, date_str, seance, exercice, exo_id) -> list:
    """Les séries de l'exercice ce jour-là : par nom, et par identifiant — une
    série faite avant un renommage porte l'ancien nom (core/exercice_ids.py).
    Une requête sur la séance du jour, triée ici : deux (nom, identifiant)
    coûtaient un aller-retour par « Série faite » (audit du 06/10, I-2)."""
    def lire(colonnes):
        return (client.table("history").select(colonnes).eq("user_id", user_id)
                .eq("date", date_str).eq("seance", seance).execute()).data or []
    par_id = bool(exo_id) and _COLONNES["exercise_id"]
    try:
        lignes = lire("id,exercice,exercise_id" if par_id else "id,exercice")
    except Exception as e:                        # v42 absente : par le nom seul
        if not par_id or _colonne_refusee(str(e).lower()) != "exercise_id":
            raise
        _COLONNES["exercise_id"] = par_id = False
        lignes = lire("id,exercice")
    return [r["id"] for r in lignes if r.get("id") is not None
            and (r.get("exercice") == exercice or (par_id and r.get("exercise_id") == exo_id))]


def _replace_exo_rows(user_id: str, date_str: str, seance: str, exercice: str, new_rows: list[dict],
                      exo_id: str | None = None):
    """Remplace les séries d'un exercice pour UNE séance (date + nom).

    On INSÈRE les nouvelles lignes, puis on supprime les anciennes par id :
    DELETE puis INSERT, sans transaction, perdait tout sur une coupure entre
    les deux. Un échec d'insertion laisse l'ancien état intact."""
    client = get_client()
    old_ids = _ids_cibles(client, user_id, date_str, seance, exercice, exo_id)
    payload = _series_distinctes(
        [_row_to_supabase(user_id, {**r, "Date": date_str}) for r in (new_rows or [])])
    try:
        resp = _insert_history(client, payload, par_cle=True) if payload else None
        if payload and resp is None:
            resp = _insert_history(client, payload)
            gardes = set()
        else:
            # Écriture par clé : les séries qui gardent leur numéro sont mises
            # à jour sur place ; seules celles qui n'existent plus partent.
            gardes = {x["id"] for x in ((resp.data if resp else None) or []) if x.get("id") is not None}
        _delete_history_ids(client, [i for i in old_ids if i not in gardes])
    except Exception:
        _cache_invalidate(f"hist:{user_id}")
        raise
    _reporter_dans_le_cache(user_id, date_str, seance, exercice, payload, exo_id)


def append_exo_rows(user_id: str, date_str: str, seance: str, exercice: str,
                    new_rows: list[dict]) -> int:
    """Ajoute des séries SANS effacer les précédentes : deux footings le même
    jour sont deux séances, `replace_exo_rows` effaçait la première. Le numéro
    de série continue la suite. Retourne le numéro de la première ajoutée."""
    date_str = _norm_date(date_str)
    with _verrou(user_id, date_str, seance, exercice):
        return _append_exo_rows(user_id, date_str, seance, exercice, new_rows)


def _append_exo_rows(user_id, date_str, seance, exercice, new_rows, essai=0) -> int:
    try:
        return _append_une_fois(user_id, date_str, seance, exercice, new_rows)
    except Exception as e:
        # Une autre instance a pris le même numéro de série entre la lecture
        # et l'écriture : l'index refuse, on relit et on recommence une fois.
        if essai or not ("23505" in str(e) or "duplicate key" in str(e).lower()):
            raise
        return _append_exo_rows(user_id, date_str, seance, exercice, new_rows, essai=1)


def _append_une_fois(user_id, date_str, seance, exercice, new_rows) -> int:
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
                    serie: int | None = None, exo_id: str | None = None):
    """Supprime les lignes d'un exercice pour une séance ; avec `serie`, une
    seule — deux blocs du même cardio dans une séance sont deux séries, et
    en supprimer un ne doit pas emporter l'autre."""
    date_str = _norm_date(date_str)
    client = get_client()
    if exo_id and serie is None:
        _delete_history_ids(client, _ids_cibles(client, user_id, date_str, seance, exercice, exo_id))
        _cache_invalidate(f"hist:{user_id}")
        return
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
