"""Défis entre amis (v53) — tables `defis` et `defis_participants`.

Le client porte la clé service_role, qui passe outre le RLS : la règle est
appliquée ICI, à chaque lecture et à chaque écriture.
  - Un compte ne lit que les défis dont il est participant (invité ou non).
  - Un défi réunit son créateur et SES amis acceptés : on n'invite qu'un
    ami accepté, et un participant qui n'est plus l'ami accepté du
    créateur sort du défi (il ne le voit plus, les autres ne le voient
    plus dans le classement). Le créateur qui n'est plus son ami : idem.
  - Le score n'est pas en base : `lignes_des_defis` lit les séries des
    participants et core/defis.py le calcule.

Base en retard (tables absentes) : `DefisIndisponibles`. La page Amis le
dit, l'accueil n'affiche rien, le manque est signalé à /admin.
"""
import datetime as _dt
import logging

from core import defis as calc
from core.amis import autre
from core.db_base import _fetch_all, get_client
from core.db_colonnes import _COLONNES, _colonne_refusee, lire_avec_mesures

logger = logging.getLogger(__name__)

TABLE_DEFIS = "defis"
TABLE_PARTICIPANTS = "defis_participants"
COLONNES_DEFIS = "id, createur, type, exercice, semaines, debut, fin, created_at"
COLONNES_PARTICIPANTS = "id, defi_id, user_id, etat, created_at, repondu_le"
_NOMS = (TABLE_DEFIS, TABLE_PARTICIPANTS)
_LOT_DEFIS = 100


class DefisIndisponibles(Exception):
    """Migration v53 (ou v52, dont dépendent les amis) pas encore passée."""


def _absente(err) -> bool:
    from core.schema import signaler
    msg = str(err).lower()
    return any(n in msg for n in _NOMS + ("amities",)) and any(m in msg for m in (
        "does not exist", "42p01", "42703", "pgrst204", "pgrst205", "schema cache")) \
        and signaler(err, TABLE_DEFIS)


def _requete(faire):
    try:
        return faire()
    except Exception as e:
        if _absente(e):
            raise DefisIndisponibles() from e
        raise


def _maintenant_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


# ── Qui est ami avec qui ─────────────────────────────────────────


def amis_de(comptes) -> dict:
    """{compte: {ses amis acceptés}} — deux requêtes pour toute la liste."""
    comptes = sorted({c for c in comptes or [] if c})
    out = {c: set() for c in comptes}
    client = get_client()
    for i in range(0, len(comptes), _LOT_DEFIS):
        lot = comptes[i:i + _LOT_DEFIS]
        for cote in ("demandeur", "destinataire"):
            lignes = _requete(lambda: _fetch_all(lambda: (
                client.table("amities").select("id, demandeur, destinataire, etat")
                .in_(cote, lot).eq("etat", "acceptee").order("id"))))
            for l in lignes:
                if l[cote] in out:
                    out[l[cote]].add(autre(l, l[cote]))
    return out


# ── Lire ─────────────────────────────────────────────────────────


def lire_defis(moi: str, depuis: str) -> list[dict]:
    """Les défis visibles par `moi` qui finissent le `depuis` (ISO) ou plus
    tard : [{"defi", "participants" (déjà filtrés par la règle), "moi" (ma
    ligne de participant)}], les plus proches de leur fin d'abord."""
    client = get_client()
    miennes = _requete(lambda: _fetch_all(lambda: (
        client.table(TABLE_PARTICIPANTS).select(COLONNES_PARTICIPANTS)
        .eq("user_id", moi).order("id"))))
    ids = sorted({m["defi_id"] for m in miennes})
    if not ids:
        return []
    defis = _requete(lambda: _fetch_all(lambda: (
        client.table(TABLE_DEFIS).select(COLONNES_DEFIS).in_("id", ids)
        .gte("fin", depuis).order("id"))))
    if not defis:
        return []
    tous = _requete(lambda: _fetch_all(lambda: (
        client.table(TABLE_PARTICIPANTS).select(COLONNES_PARTICIPANTS)
        .in_("defi_id", [d["id"] for d in defis]).order("id"))))
    amis = amis_de(d["createur"] for d in defis)
    sortie = []
    for d in defis:
        cercle = amis.get(d["createur"], set()) | {d["createur"]}
        if moi not in cercle:
            continue
        participants = [p for p in tous if p["defi_id"] == d["id"] and p["user_id"] in cercle]
        mienne = next((p for p in participants if p["user_id"] == moi), None)
        if mienne:
            sortie.append({"defi": d, "participants": participants, "moi": mienne})
    sortie.sort(key=lambda x: (str(x["defi"]["fin"]), x["defi"]["id"]))
    return sortie


def lignes_des_defis(comptes, debut, fin) -> dict:
    """{compte: [lignes brutes de history entre debut et fin inclus]} —
    ce que core/defis.score sait lire. Une requête par lot de 100 comptes."""
    comptes = sorted({c for c in comptes or [] if c})
    out = {c: [] for c in comptes}
    client = get_client()
    for i in range(0, len(comptes), _LOT_DEFIS):
        lot = comptes[i:i + _LOT_DEFIS]

        def requete(cols):
            extra = ",type_serie" if _COLONNES["type_serie"] else ""
            return (client.table("history").select("user_id,date,seance,exercice" + extra + "," + cols)
                    .in_("user_id", lot).gte("date", str(debut)[:10])
                    .lte("date", str(fin)[:10]).order("id"))
        while True:
            try:
                lignes = lire_avec_mesures(requete)
                break
            except Exception as e:
                if _COLONNES["type_serie"] and _colonne_refusee(str(e).lower()) == "type_serie":
                    _COLONNES["type_serie"] = False   # sans la v43 : lu sans
                    continue
                raise
        for l in lignes:
            out.setdefault(l.get("user_id"), []).append(l)
    return out


def defis_en_cours(moi: str, aujourdhui: _dt.date) -> int:
    """Défis pas encore finis que `moi` a acceptés (ou lancés)."""
    return sum(1 for x in lire_defis(moi, aujourdhui.isoformat()) if x["moi"]["etat"] == "acceptee")


def _defi_par_id(defi_id):
    lignes = _requete(lambda: (
        get_client().table(TABLE_DEFIS).select(COLONNES_DEFIS)
        .eq("id", int(defi_id)).limit(1).execute())).data or []
    return lignes[0] if lignes else None


def _participants_du_defi(defi_id) -> list:
    return _requete(lambda: (
        get_client().table(TABLE_PARTICIPANTS).select(COLONNES_PARTICIPANTS)
        .eq("defi_id", int(defi_id)).limit(500).execute())).data or []


# ── Écrire ───────────────────────────────────────────────────────


def _amis_acceptes_de(moi: str) -> set:
    return amis_de([moi]).get(moi, set())


def creer_defi(moi: str, type_: str, exercice, semaines: int, debut, fin, invites,
               aujourdhui: _dt.date) -> tuple:
    """(résultat, id) — cree, pas_ami (un invité n'est pas un ami
    accepté : rien n'est créé), personne, trop_invites ou trop."""
    invites = sorted({i for i in invites or [] if i and i != moi})
    if not invites:
        return "personne", None
    if len(invites) > calc.MAX_PARTICIPANTS - 1:
        return "trop_invites", None
    if not set(invites) <= _amis_acceptes_de(moi):
        return "pas_ami", None
    if defis_en_cours(moi, aujourdhui) >= calc.MAX_EN_COURS:
        return "trop", None
    client = get_client()
    ligne = _requete(lambda: client.table(TABLE_DEFIS).insert({
        "createur": moi, "type": type_, "exercice": exercice if type_ == "progression" else None,
        "semaines": int(semaines), "debut": str(debut), "fin": str(fin)}).execute()).data[0]
    try:
        _requete(lambda: client.table(TABLE_PARTICIPANTS).insert(
            [{"defi_id": ligne["id"], "user_id": moi, "etat": "acceptee", "repondu_le": _maintenant_utc()}]
            # Mêmes clés partout : PostgREST refuse un lot qui diffère (PGRST102).
            + [{"defi_id": ligne["id"], "user_id": i, "etat": "invite", "repondu_le": None}
               for i in invites]).execute())
    except Exception:
        client.table(TABLE_DEFIS).delete().eq("id", ligne["id"]).execute()
        raise
    return "cree", ligne["id"]


def inviter_au_defi(moi: str, defi_id, invites, aujourdhui: _dt.date) -> str:
    """Le créateur ajoute des amis, jusqu'au jour du début : invites,
    pas_ami, trop_invites, personne, ou "" (pas son défi, trop tard)."""
    defi = _defi_par_id(defi_id)
    if not defi or defi["createur"] != moi or not calc.peut_repondre(defi, aujourdhui):
        return ""
    deja = {p["user_id"] for p in _participants_du_defi(defi["id"])}
    nouveaux = sorted({i for i in invites or [] if i and i not in deja})
    if not nouveaux:
        return "personne"
    if not set(nouveaux) <= _amis_acceptes_de(moi):
        return "pas_ami"
    if len(deja) + len(nouveaux) > calc.MAX_PARTICIPANTS:
        return "trop_invites"
    _requete(lambda: get_client().table(TABLE_PARTICIPANTS).insert(
        [{"defi_id": defi["id"], "user_id": i, "etat": "invite"} for i in nouveaux]).execute())
    return "invites"


def repondre_au_defi(moi: str, defi_id, accepte: bool, aujourdhui: _dt.date) -> str:
    """acceptee, refusee, trop (trop de défis en cours), ou "" (pas
    invité, invitation passée, créateur qui n'est plus un ami)."""
    defi = _defi_par_id(defi_id)
    if not defi or not calc.peut_repondre(defi, aujourdhui):
        return ""
    if defi["createur"] not in _amis_acceptes_de(moi):
        return ""
    client = get_client()
    if not accepte:
        resp = _requete(lambda: client.table(TABLE_PARTICIPANTS).delete()
                        .eq("defi_id", defi["id"]).eq("user_id", moi).eq("etat", "invite").execute())
        return "refusee" if resp.data else ""
    if defis_en_cours(moi, aujourdhui) >= calc.MAX_EN_COURS:
        return "trop"
    resp = _requete(lambda: client.table(TABLE_PARTICIPANTS)
                    .update({"etat": "acceptee", "repondu_le": _maintenant_utc()})
                    .eq("defi_id", defi["id"]).eq("user_id", moi).eq("etat", "invite").execute())
    return "acceptee" if resp.data else ""


def annuler_defi(moi: str, defi_id, aujourdhui: _dt.date) -> bool:
    """Le créateur annule un défi pas encore commencé : il disparaît pour tous."""
    defi = _defi_par_id(defi_id)
    if not defi or defi["createur"] != moi or calc.phase(defi, aujourdhui) != "a_venir":
        return False
    client = get_client()
    _requete(lambda: client.table(TABLE_PARTICIPANTS).delete().eq("defi_id", defi["id"]).execute())
    _requete(lambda: client.table(TABLE_DEFIS).delete().eq("id", defi["id"]).eq("createur", moi).execute())
    return True


# ── Compte ───────────────────────────────────────────────────────


def export_defis(moi: str) -> list:
    """Portabilité (RGPD) : mes défis et ma réponse. Des autres comptes,
    seulement le prénom ; pas leurs scores (calculés depuis LEUR historique)."""
    from core.db_amis import profils
    vus = lire_defis(moi, "0001-01-01")
    noms = profils({p["user_id"] for x in vus for p in x["participants"]})
    from core.amis import nom_affiche
    return [{
        "type": x["defi"]["type"], "exercice": x["defi"].get("exercice"),
        "semaines": x["defi"]["semaines"], "debut": str(x["defi"]["debut"])[:10],
        "fin": str(x["defi"]["fin"])[:10], "lance_par_moi": x["defi"]["createur"] == moi,
        "ma_reponse": x["moi"]["etat"],
        "avec": sorted(nom_affiche(noms.get(p["user_id"])) for p in x["participants"]
                       if p["user_id"] != moi and p["etat"] == "acceptee"),
    } for x in vus]


def effacer_defis_du_compte(moi: str) -> None:
    """Suppression du compte : les défis que j'ai lancés (avec leurs
    participants), puis mes participations aux défis des autres."""
    client = get_client()
    try:
        miens = _requete(lambda: _fetch_all(lambda: client.table(TABLE_DEFIS).select("id")
                                            .eq("createur", moi).order("id")))
        ids = [d["id"] for d in miens]
        if ids:
            _requete(lambda: client.table(TABLE_PARTICIPANTS).delete().in_("defi_id", ids).execute())
        _requete(lambda: client.table(TABLE_DEFIS).delete().eq("createur", moi).execute())
        _requete(lambda: client.table(TABLE_PARTICIPANTS).delete().eq("user_id", moi).execute())
    except DefisIndisponibles:
        pass
