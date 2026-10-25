"""Amis (v52) — tables `amities`, `fil_seances`, `encouragements`, et le
réglage `profiles.seances_masquees`.

Le client porte la clé service_role, qui passe outre le RLS : la règle de
visibilité est appliquée ICI, à chaque lecture. Un compte ne lit que :
  - ses propres lignes d'amitié (il en est le demandeur ou le destinataire) ;
  - le fil de ses amis ACCEPTÉS qui n'ont pas masqué leurs séances, plus le
    sien (`core.amis.visibles`).
Écrire sur la ligne d'un autre suppose d'en être une des deux parties
(chaque update et delete filtre par l'id ET par le compte connecté).

Base en retard (tables absentes) : `AmisIndisponibles`. La page le dit, la
fin de séance n'écrit rien, le reste de l'app n'en sait rien. Le manque est
signalé à /admin.
"""
import datetime as _dt
import logging

from core import amis as calc
from core.db_base import get_client
from core.db_profil import _profile_upsert

logger = logging.getLogger(__name__)

TABLE_AMITIES = "amities"
TABLE_FIL = "fil_seances"
TABLE_ENCOURAGEMENTS = "encouragements"
COLONNES_AMITIES = "id, demandeur, destinataire, etat, created_at, acceptee_le"
COLONNES_FIL = "id, user_id, session_id, date, seance, duree_min, tonnage, records, created_at"
_NOMS = (TABLE_AMITIES, TABLE_FIL, TABLE_ENCOURAGEMENTS, "seances_masquees")


class AmisIndisponibles(Exception):
    """Migration v52 pas encore passée."""


def _absente(err) -> bool:
    from core.schema import signaler
    msg = str(err).lower()
    return any(n in msg for n in _NOMS) and any(m in msg for m in (
        "does not exist", "42p01", "42703", "pgrst204", "pgrst205", "schema cache")) \
        and signaler(err, TABLE_AMITIES)


def _requete(faire):
    try:
        return faire()
    except Exception as e:
        if _absente(e):
            raise AmisIndisponibles() from e
        raise


def _doublon(err) -> bool:
    return "23505" in str(err) or "duplicate key" in str(err).lower()


# ── Amitiés ──────────────────────────────────────────────────────


def amities_de(user_id: str) -> list[dict]:
    """Toutes les lignes où ce compte est une des deux parties."""
    client = get_client()
    lignes = []
    for cote in ("demandeur", "destinataire"):
        lignes += _requete(lambda: (
            client.table(TABLE_AMITIES).select(COLONNES_AMITIES).eq(cote, user_id)
            .limit(calc.MAX_AMIS * 3).execute())).data or []
    return lignes


def _entre(a: str, b: str) -> dict | None:
    for ligne in amities_de(a):
        if calc.autre(ligne, a) == b:
            return ligne
    return None


def profils(ids) -> dict:
    """{id: {prenom, display_name, seances_masquees}} — le prénom est tout
    ce qu'un ami lit du profil de l'autre."""
    ids = sorted({i for i in ids if i})
    if not ids:
        return {}
    resp = _requete(lambda: (
        get_client().table("profiles").select("id, prenom, display_name, seances_masquees")
        .in_("id", ids).execute()))
    return {p["id"]: p for p in (resp.data or [])}


def demander(moi: str, autre: str) -> str:
    """Demande d'ami de `moi` vers `autre`. Rend ce qui s'est passé :
    envoyee, acceptee (l'autre m'avait déjà demandé : les deux le veulent),
    deja_amis, deja_envoyee, soi_meme ou trop."""
    if not autre or autre == moi:
        return "soi_meme"
    lignes = amities_de(moi)
    existante = next((l for l in lignes if calc.autre(l, moi) == autre), None)
    if existante:
        if existante["etat"] == "acceptee":
            return "deja_amis"
        if existante["demandeur"] == moi:
            return "deja_envoyee"
        return "acceptee" if accepter(moi, existante["id"]) else "deja_envoyee"
    miennes = [l for l in lignes if l["etat"] == "acceptee" or l["demandeur"] == moi]
    if len(miennes) >= calc.MAX_AMIS:
        return "trop"
    try:
        _requete(lambda: get_client().table(TABLE_AMITIES).insert(
            {"demandeur": moi, "destinataire": autre, "etat": "en_attente"}).execute())
    except AmisIndisponibles:
        raise
    except Exception as e:
        if not _doublon(e):
            raise
        # Les deux se sont demandés en même temps : la ligne de l'autre existe.
        existante = _entre(moi, autre)
        if existante and existante["etat"] != "acceptee" and existante["destinataire"] == moi:
            return "acceptee" if accepter(moi, existante["id"]) else "deja_envoyee"
        return "deja_amis" if existante and existante["etat"] == "acceptee" else "deja_envoyee"
    return "envoyee"


def accepter(moi: str, amitie_id) -> bool:
    """Seul le destinataire accepte une demande en attente."""
    maintenant = _dt.datetime.now(_dt.timezone.utc).isoformat()
    resp = _requete(lambda: (
        get_client().table(TABLE_AMITIES).update({"etat": "acceptee", "acceptee_le": maintenant})
        .eq("id", int(amitie_id)).eq("destinataire", moi).eq("etat", "en_attente").execute()))
    return bool(resp.data)


def _effacer(moi: str, amitie_id, cote: str, etat: str) -> bool:
    resp = _requete(lambda: (
        get_client().table(TABLE_AMITIES).delete()
        .eq("id", int(amitie_id)).eq(cote, moi).eq("etat", etat).execute()))
    return bool(resp.data)


def refuser(moi: str, amitie_id) -> bool:
    return _effacer(moi, amitie_id, "destinataire", "en_attente")


def annuler(moi: str, amitie_id) -> bool:
    return _effacer(moi, amitie_id, "demandeur", "en_attente")


def retirer(moi: str, amitie_id) -> bool:
    """Retirer un ami, quel que soit celui qui avait demandé : la ligne
    disparaît, chacun cesse aussitôt de voir les séances de l'autre."""
    return (_effacer(moi, amitie_id, "demandeur", "acceptee")
            or _effacer(moi, amitie_id, "destinataire", "acceptee"))


def visibles_par(moi: str) -> list:
    lignes = amities_de(moi)
    acceptes = [calc.autre(l, moi) for l in lignes if l.get("etat") == "acceptee"]
    return calc.visibles(lignes, moi, profils(acceptes))


def masquer_seances(moi: str, valeur: bool) -> None:
    try:
        _profile_upsert(moi, {"seances_masquees": bool(valeur)})
    except Exception as e:
        if _absente(e):
            raise AmisIndisponibles() from e
        raise


# ── Le fil des séances terminées ─────────────────────────────────


def publier_seance(user_id: str, ligne: dict) -> bool:
    """Fin de séance : la ligne du fil (`core.amis.ligne_fil`), remplacée si
    la même séance est terminée une seconde fois. Faux si la table manque."""
    try:
        _requete(lambda: get_client().table(TABLE_FIL).upsert(
            {"user_id": user_id, **ligne}, on_conflict="user_id,session_id").execute())
        return True
    except AmisIndisponibles:
        return False


def retirer_du_fil(user_id: str, session_id: str) -> None:
    """Une séance effacée sort du fil (ses encouragements avec elle : clé
    étrangère en base, ici pour la fausse base des tests)."""
    client = get_client()
    try:
        _requete(lambda: client.table(TABLE_ENCOURAGEMENTS).delete()
                 .eq("destinataire", user_id).eq("session_id", session_id).execute())
        _requete(lambda: client.table(TABLE_FIL).delete()
                 .eq("user_id", user_id).eq("session_id", session_id).execute())
    except AmisIndisponibles:
        pass


def effacer_fil(user_id: str) -> None:
    """Remise à zéro de l'historique : le fil part avec."""
    client = get_client()
    try:
        _requete(lambda: client.table(TABLE_ENCOURAGEMENTS).delete().eq("destinataire", user_id).execute())
        _requete(lambda: client.table(TABLE_FIL).delete().eq("user_id", user_id).execute())
    except AmisIndisponibles:
        pass


def fil(moi: str, comptes: list, depuis: str) -> list[dict]:
    """Les séances de `comptes` (déjà filtrés par `visibles_par`) et les
    miennes, depuis la date ISO `depuis`."""
    ids = sorted(set(comptes) | {moi})
    resp = _requete(lambda: (
        get_client().table(TABLE_FIL).select(COLONNES_FIL).in_("user_id", ids)
        .gte("date", depuis).order("date", desc=True).limit(calc.FIL_MAX).execute()))
    return resp.data or []


def encouragements_pour(lignes_fil) -> list[dict]:
    sids = sorted({str(l.get("session_id")) for l in lignes_fil or [] if l.get("session_id")})
    if not sids:
        return []
    resp = _requete(lambda: (
        get_client().table(TABLE_ENCOURAGEMENTS).select("auteur, destinataire, session_id")
        .in_("session_id", sids).limit(5000).execute()))
    return resp.data or []


def encourager(moi: str, auteur_seance: str, session_id: str) -> str:
    """ok, deja, ou interdit (pas un ami, séances masquées, séance absente
    du fil, ou la sienne)."""
    if not auteur_seance or auteur_seance == moi or auteur_seance not in visibles_par(moi):
        return "interdit"
    client = get_client()
    seance = _requete(lambda: (
        client.table(TABLE_FIL).select("id").eq("user_id", auteur_seance)
        .eq("session_id", session_id).limit(1).execute())).data
    if not seance:
        return "interdit"
    try:
        _requete(lambda: client.table(TABLE_ENCOURAGEMENTS).insert(
            {"auteur": moi, "destinataire": auteur_seance, "session_id": session_id}).execute())
    except AmisIndisponibles:
        raise
    except Exception as e:
        if _doublon(e):
            return "deja"
        raise
    return "ok"


def export_amis(moi: str) -> dict:
    """Portabilité (RGPD) : mes amis et demandes, mes séances du fil, les
    encouragements que j'ai donnés et reçus. Des autres comptes, seulement
    le prénom qu'ils me montrent déjà."""
    client = get_client()
    lignes = amities_de(moi)
    classes = calc.classer(lignes, moi, profils(calc.autre(l, moi) for l in lignes))
    mes_seances = _requete(lambda: client.table(TABLE_FIL).select(COLONNES_FIL)
                           .eq("user_id", moi).limit(5000).execute()).data or []
    donnes = _requete(lambda: client.table(TABLE_ENCOURAGEMENTS).select("session_id, created_at")
                      .eq("auteur", moi).limit(5000).execute()).data or []
    recus = _requete(lambda: client.table(TABLE_ENCOURAGEMENTS).select("session_id, created_at")
                     .eq("destinataire", moi).limit(5000).execute()).data or []

    def sans_ids(liste):
        return [{"nom": e["nom"], "depuis": e["depuis"]} for e in liste]

    return {
        "amis": sans_ids(classes["amis"]),
        "demandes_recues": sans_ids(classes["recues"]),
        "demandes_envoyees": sans_ids(classes["envoyees"]),
        "fil_seances": [{k: v for k, v in s.items() if k not in ("id", "user_id")} for s in mes_seances],
        "encouragements_donnes": donnes,
        "encouragements_recus": recus,
    }
