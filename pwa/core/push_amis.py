"""Notifications push entre amis (choix du propriétaire, 03/11/2026).

Quatre événements préviennent l'autre :
  - une demande d'ami reçue ;
  - une invitation à un défi ;
  - un ami qui vous dépasse dans un défi en cours (vu à la fin de SA
    séance), au plus une fois par jour et par défi ;
  - un encouragement reçu, au plus une notification par séance.

Actives par défaut pour qui a déjà accepté les notifications (un abonnement
push existe) ; l'interrupteur « Notifications des amis » de Réglages les
coupe (`reglages.notifs_amis`, v54). Le message ne dit que le prénom et ce
qui s'est passé : ni charge, ni séance détaillée.

L'envoi part en tâche de fond : la route qui le déclenche ne l'attend pas,
et une panne du service de push ne la fait jamais échouer.
"""
import datetime as _dt
import logging
from concurrent.futures import ThreadPoolExecutor

from core import amis as calc_amis
from core import db as core_db
from core import defis as calc_defis
from core import partage

logger = logging.getLogger(__name__)

_EXEC = ThreadPoolExecutor(max_workers=2, thread_name_prefix="push-amis")
UNE_FOIS_PAR_SEANCE = 3 * 24 * 3600     # encouragements
UNE_FOIS_PAR_JOUR = 24 * 3600           # « t'a dépassé »
TTL_PUSH = 12 * 3600                    # livré plus tard, il ne veut plus rien dire


def _en_fond(travail) -> None:
    """Les tests le remplacent par un appel direct."""
    _EXEC.submit(travail)


def _prenom(uid: str) -> str:
    try:
        return calc_amis.nom_affiche(core_db.profils([uid]).get(uid))
    except Exception:
        return calc_amis.nom_affiche(None)


def _veut(uid: str) -> bool:
    try:
        return bool(core_db.lire_reglages(uid).get("notifs_amis", True))
    except Exception as e:
        logger.warning("push amis : réglages illisibles user=%s (%s)", uid, type(e).__name__)
        return False


def envoyer_a(uid: str, titre: str, corps: str, url: str, tag: str, une_fois=None) -> int:
    """Envoie à tous les appareils de `uid`, s'il le veut. `une_fois` =
    (clé, secondes) : rien si la même clé est déjà partie dans ce délai.
    Rend le nombre d'appareils atteints. Synchrone : appelée en tâche de fond."""
    from core.push import send_push
    if not uid or not _veut(uid):
        return 0
    abonnements = core_db.list_push_subscriptions(uid)
    if not abonnements:
        return 0
    if une_fois and not partage.fenetre(f"push-amis:{une_fois[0]}", 1, une_fois[1]):
        return 0
    payload = {"title": titre, "body": corps, "url": url, "tag": tag}
    atteints = 0
    for sub in abonnements:
        resultat = send_push(sub, payload, ttl=TTL_PUSH)
        if resultat == "ok":
            atteints += 1
        elif resultat == "expired":
            core_db.delete_push_subscription(sub.get("endpoint"), uid)
    return atteints


def _plus_tard(fonction, *args) -> None:
    def travail():
        try:
            fonction(*args)
        except Exception as e:  # jamais au-delà du journal
            logger.error("push amis : %s FAILED (%s) %s", fonction.__name__, type(e).__name__, e)
    _en_fond(travail)


# ── Les quatre événements ────────────────────────────────────────


def _demande(auteur, destinataire):
    envoyer_a(destinataire, "Demande d'ami", f"{_prenom(auteur)} veut devenir ton ami.",
              "/amis", "ami-demande")


def demande_recue(auteur: str, destinataire: str) -> None:
    _plus_tard(_demande, auteur, destinataire)


def _invitation(createur, invites, defi_id, titre, semaines):
    nom = _prenom(createur)
    duree = f"{semaines} semaine{'s' if int(semaines) > 1 else ''}"
    for uid in sorted(set(invites or [])):
        if uid != createur:
            envoyer_a(uid, "Nouveau défi", f"{nom} te lance un défi {titre} sur {duree}.",
                      "/amis#defis", f"defi-{defi_id}",
                      une_fois=(f"invit:{defi_id}:{uid}", 7 * 24 * 3600))


def invitation_defi(createur: str, invites, defi_id, titre: str, semaines) -> None:
    _plus_tard(_invitation, createur, list(invites or []), defi_id, titre, semaines)


def _invitation_ajoutee(createur, invites, defi_id):
    defi = core_db._defi_par_id(defi_id)
    if defi and defi["createur"] == createur:
        _invitation(createur, invites, defi_id, calc_defis.titre(defi), defi["semaines"])


def invitation_ajoutee(createur: str, invites, defi_id) -> None:
    """« Inviter d'autres amis » : le défi est relu, rien n'est cru du formulaire."""
    _plus_tard(_invitation_ajoutee, createur, list(invites or []), defi_id)


def _encouragement(auteur, destinataire, session_id, seance):
    envoyer_a(destinataire, "Encouragement",
              f"{_prenom(auteur)} t'a encouragé pour ta séance {seance or ''}".strip() + ".",
              "/amis", f"encouragement-{session_id}",
              une_fois=(f"encourage:{destinataire}:{session_id}", UNE_FOIS_PAR_SEANCE))


def encouragement_recu(auteur: str, destinataire: str, session_id: str, seance: str = "") -> None:
    _plus_tard(_encouragement, auteur, destinataire, session_id, seance)


# ── « Ton ami t'a dépassé » ──────────────────────────────────────


def _valeur(s):
    return s["valeur"] if s and s.get("valeur") is not None else None


def depasses(defi: dict, participants, lignes: dict, moi: str, date_str: str, seance: str,
             aujourdhui: _dt.date) -> list:
    """Les participants que `moi` vient de dépasser avec la séance (date,
    nom) : devant ou à égalité avant elle, strictement derrière après.
    Calcul pur, sur les lignes déjà lues."""
    mes_lignes = lignes.get(moi, [])
    sans = [l for l in mes_lignes
            if not (str(l.get("date"))[:10] == date_str and l.get("seance") == seance)]
    if len(sans) == len(mes_lignes):
        return []
    apres = _valeur(calc_defis.score(defi, mes_lignes, aujourdhui))
    avant = _valeur(calc_defis.score(defi, sans, aujourdhui))
    if apres is None:
        return []
    out = []
    for p in participants or []:
        qui = p.get("user_id")
        if qui == moi or p.get("etat") != "acceptee":
            continue
        autre = _valeur(calc_defis.score(defi, lignes.get(qui, []), aujourdhui))
        if autre is None:
            continue
        if (avant is None or avant <= autre) and apres > autre:
            out.append(qui)
    return sorted(out)


def _depassements(moi, date_str, seance):
    aujourdhui = _dt.date.fromisoformat(date_str)
    entrees = [x for x in core_db.lire_defis(moi, date_str)
               if x["moi"]["etat"] == "acceptee"
               and calc_defis.phase(x["defi"], aujourdhui) == "en_cours"]
    if not entrees:
        return
    comptes = {p["user_id"] for x in entrees for p in x["participants"] if p["etat"] == "acceptee"}
    debut = min(calc_defis.debut_lecture(x["defi"]) for x in entrees)
    lignes = core_db.lignes_des_defis(comptes, debut, aujourdhui)
    nom = _prenom(moi)
    for x in entrees:
        titre = calc_defis.titre(x["defi"])
        for qui in depasses(x["defi"], x["participants"], lignes, moi, date_str, seance, aujourdhui):
            envoyer_a(qui, "Tu t'es fait dépasser", f"{nom} t'a dépassé au défi {titre}.",
                      "/amis#defis", f"defi-{x['defi']['id']}",
                      une_fois=(f"depasse:{x['defi']['id']}:{qui}:{date_str}", UNE_FOIS_PAR_JOUR))


def apres_la_seance(moi: str, date_str: str, seance: str) -> None:
    """Fin de séance : prévient ceux que cette séance vient de dépasser."""
    _plus_tard(_depassements, moi, str(date_str)[:10], seance)
