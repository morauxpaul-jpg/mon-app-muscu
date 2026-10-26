"""Défis entre amis (v53) : ce que les pages Amis et Accueil affichent.

Lit la base (core/db_defis.py, qui applique la règle de visibilité), puis
confie tout le calcul à core/defis.py. Une seule lecture de `history` pour
tous les défis affichés. Ni l'une ni l'autre fonction ne fait jamais
échouer la page qui l'appelle.
"""
import datetime as _dt
import logging

from core import amis as calc_amis
from core import db as core_db
from core import defis as calc

logger = logging.getLogger(__name__)

# Ce que la page Amis dit après une action sur un défi (?m=…).
MESSAGES = {
    "defi_cree": "Défi lancé. Tes amis le verront dans leur page Amis.",
    "defi_personne": "Choisis au moins un ami à défier.",
    "defi_pas_ami": "On ne peut défier que ses amis acceptés.",
    "defi_trop_invites": f"{calc.MAX_PARTICIPANTS} participants au plus par défi.",
    "defi_trop": f"Tu as déjà {calc.MAX_EN_COURS} défis en cours.",
    "defi_invalide": "Ce défi n'est pas valable : vérifie le type, la durée et l'exercice.",
    "defi_invites": "Invitation envoyée.",
    "defi_acceptee": "C'est parti : tu es dans le défi.",
    "defi_refusee": "Défi refusé.",
    "defi_annule": "Défi annulé.",
    "defi_expire": "Ce défi a déjà commencé, l'invitation n'est plus valable.",
    "defi_indisponible": "Les défis arrivent bientôt.",
}


def _vue(entree: dict, lignes: dict, profils: dict, moi: str, aujourdhui: _dt.date) -> dict:
    d = entree["defi"]
    phase = calc.phase(d, aujourdhui)
    classement = calc.classement(d, entree["participants"], lignes, profils, moi, aujourdhui)
    createur = d["createur"]
    return {
        "id": d["id"], "type": d["type"], "titre": calc.titre(d), "phase": phase,
        "but": calc.TYPES.get(d["type"], {}).get("but", ""),
        "semaines": d["semaines"], "debut": str(d["debut"])[:10], "fin": str(d["fin"])[:10],
        "jours_restants": calc.jours_restants(d, aujourdhui),
        "createur": "Toi" if createur == moi else calc_amis.nom_affiche(profils.get(createur)),
        "lance_par_moi": createur == moi,
        "mon_etat": entree["moi"]["etat"],
        "peut_repondre": calc.peut_repondre(d, aujourdhui),
        "classement": classement,
        # Ceux qui ont déjà accepté, hors créateur (déjà nommé) et hors soi.
        "avec": [l["nom"] for l in classement if not l["moi"] and l["compte"] != createur],
        "comptes": [p["user_id"] for p in entree["participants"]],
        # Les invités sans réponse : seulement pour le créateur.
        "en_attente": sorted(calc_amis.nom_affiche(profils.get(p["user_id"]))
                             for p in entree["participants"] if p["etat"] == "invite")
                      if createur == moi else [],
        "annonce": calc.annonce(d, classement) if phase == "termine" else "",
    }


def _vues(moi: str, aujourdhui: _dt.date, depuis: _dt.date) -> list:
    entrees = core_db.lire_defis(moi, depuis.isoformat())
    if not entrees:
        return []
    comptes = {p["user_id"] for x in entrees for p in x["participants"]}
    profils = core_db.profils(comptes | {moi})
    acceptes = {p["user_id"] for x in entrees for p in x["participants"] if p["etat"] == "acceptee"}
    debut = min(calc.debut_lecture(x["defi"]) for x in entrees)
    fin = min(max(calc._date(x["defi"]["fin"]) for x in entrees), aujourdhui)
    lignes = core_db.lignes_des_defis(acceptes, debut, fin) if fin >= debut else {}
    return [_vue(x, lignes, profils, moi, aujourdhui) for x in entrees]


def pour_la_page(moi: str, aujourdhui: _dt.date) -> dict:
    """{indisponible, invitations, actifs, termines} — les défis finis
    depuis moins de 30 jours vont dans le fil (`cartes_du_fil`)."""
    vide = {"indisponible": False, "invitations": [], "actifs": [], "termines": []}
    try:
        vues = _vues(moi, aujourdhui, aujourdhui - _dt.timedelta(days=calc.FIL_JOURS))
    except (core_db.DefisIndisponibles, core_db.AmisIndisponibles):
        return {**vide, "indisponible": True}
    for v in vues:
        if v["mon_etat"] == "invite":
            if v["peut_repondre"]:
                vide["invitations"].append(v)
        elif v["phase"] == "termine":
            vide["termines"].append(v)
        else:
            vide["actifs"].append(v)
    return vide


def cartes_du_fil(cartes: list, termines: list) -> list:
    """Le fil des séances, avec le résultat des défis finis à la date de
    leur fin (avant les séances du même jour)."""
    resultats = [{**v, "genre": "defi", "date": v["fin"]} for v in termines]
    return sorted(resultats + list(cartes), key=lambda c: c["date"], reverse=True)


def pour_accueil(moi: str, aujourdhui: _dt.date) -> dict | None:
    """Le classement en direct des défis en cours (2 au plus, les plus
    proches de leur fin), et le nombre d'invitations à régler."""
    try:
        vues = _vues(moi, aujourdhui, aujourdhui)
    except (core_db.DefisIndisponibles, core_db.AmisIndisponibles):
        return None
    except Exception as e:
        logger.warning("accueil : défis indisponibles (%s)", type(e).__name__)
        return None
    actifs = [v for v in vues if v["mon_etat"] == "acceptee" and v["phase"] == "en_cours"]
    invitations = [v for v in vues if v["mon_etat"] == "invite" and v["peut_repondre"]]
    if not actifs and not invitations:
        return None
    for v in actifs:
        tete = v["classement"][:3]
        mienne = next((l for l in v["classement"] if l["moi"]), None)
        v["tete"] = tete + ([mienne] if mienne and mienne not in tete else [])
    return {"actifs": actifs[:2], "invitations": invitations}
