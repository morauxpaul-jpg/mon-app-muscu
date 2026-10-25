"""Amis : ce qu'on calcule sans toucher à la base (v52).

Le module ne connaît ni Flask ni Supabase : on lui passe des lignes déjà
lues (core/db_amis.py), il rend ce que la page affiche. C'est ici que se
décide ce qu'un ami voit d'une séance : `ligne_fil` ne recopie QUE le nom,
la date, la durée, le tonnage et les records. Ni note, ni commentaire, ni
poids du corps : ce qui n'est pas dans la ligne ne peut pas sortir.
"""
import re

# Le code personnel est le code de parrainage (profiles.referral_code) :
# 8 caractères base32 en minuscules (core/db_abonnement.py).
_CODE = re.compile(r"^[a-z2-7]{8}$")
_DANS_UN_LIEN = re.compile(r"[?&]ref=([A-Za-z2-7]{8})\b")

MAX_AMIS = 100          # amis et demandes envoyées, par compte
FIL_JOURS = 30          # le fil montre le dernier mois
FIL_MAX = 60            # et au plus 60 séances
RECORDS_MAX = 5         # records affichés par séance
NOM_MAX = 40


def lire_code(texte) -> str:
    """Le code tapé, ou extrait d'un lien collé (« …/?ref=abcd2345&ami=1 »).
    Vide s'il n'a pas la forme d'un code."""
    texte = str(texte or "").strip()
    m = _DANS_UN_LIEN.search(texte)
    if m:
        texte = m.group(1)
    texte = texte.lower().replace(" ", "")
    return texte if _CODE.match(texte) else ""


def nom_affiche(profil) -> str:
    """Le prénom choisi à l'inscription ; jamais l'e-mail."""
    profil = profil or {}
    for cle in ("prenom", "display_name"):
        nom = " ".join(str(profil.get(cle) or "").split())
        if nom:
            return nom[:NOM_MAX]
    return "Un ami"


def ligne_fil(session_id: str, date_str: str, seance: str, faits: dict | None,
              duree_min) -> dict:
    """La ligne du fil d'une séance terminée, à partir des chiffres du
    debrief (`core.debrief.collect_facts`). Rien d'autre n'y entre."""
    faits = faits or {}
    records = []
    for r in (faits.get("records") or [])[:RECORDS_MAX]:
        exo = " ".join(str(r.get("exo") or "").split())[:80]
        poids = float(r.get("poids") or 0)
        if exo and poids > 0:
            records.append({"exo": exo, "poids": round(poids, 2)})
    try:
        duree = int(duree_min or 0)
    except (TypeError, ValueError):
        duree = 0
    return {
        "session_id": session_id,
        "date": str(date_str)[:10],
        "seance": " ".join(str(seance or "").split())[:80] or "Séance",
        "duree_min": duree if 1 <= duree <= 600 else None,
        "tonnage": max(0, round(float(faits.get("volume") or 0))),
        "records": records,
    }


def autre(amitie: dict, moi: str) -> str:
    return amitie["destinataire"] if amitie.get("demandeur") == moi else amitie.get("demandeur")


def classer(amities, moi: str, profils: dict) -> dict:
    """{amis, recues, envoyees} : chaque entrée porte l'id de la ligne, l'id
    de l'autre compte et son prénom. Les amis par prénom, les demandes les
    plus récentes d'abord."""
    out = {"amis": [], "recues": [], "envoyees": []}
    for a in amities or []:
        qui = autre(a, moi)
        entree = {"id": a.get("id"), "compte": qui, "nom": nom_affiche(profils.get(qui)),
                  "depuis": str(a.get("acceptee_le") or a.get("created_at") or "")[:10]}
        if a.get("etat") == "acceptee":
            out["amis"].append(entree)
        elif a.get("destinataire") == moi:
            out["recues"].append(entree)
        else:
            out["envoyees"].append(entree)
    out["amis"].sort(key=lambda e: e["nom"].casefold())
    for cle in ("recues", "envoyees"):
        out[cle].sort(key=lambda e: e["depuis"], reverse=True)
    return out


def visibles(amities, moi: str, profils: dict) -> list:
    """Les comptes dont `moi` voit les séances : amitié ACCEPTÉE, et
    l'ami n'a pas masqué ses séances. La règle n'existe qu'ici."""
    out = []
    for a in amities or []:
        if a.get("etat") != "acceptee" or moi not in (a.get("demandeur"), a.get("destinataire")):
            continue
        qui = autre(a, moi)
        if qui and qui != moi and not (profils.get(qui) or {}).get("seances_masquees"):
            out.append(qui)
    return sorted(set(out))


def _nombre_fr(x) -> str:
    entier = int(round(float(x or 0)))
    return f"{entier:,}".replace(",", " ")


def _poids_fr(x) -> str:
    x = float(x or 0)
    texte = f"{x:.1f}".rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def fil_affiche(lignes, profils: dict, encouragements, moi: str) -> list:
    """Les cartes du fil, les plus récentes d'abord. Sur ses propres
    séances, l'auteur voit le nombre d'encouragements ; sur celles d'un
    ami, on voit seulement si on a déjà encouragé."""
    par_seance: dict = {}
    for e in encouragements or []:
        par_seance.setdefault((e.get("destinataire"), str(e.get("session_id"))), set()).add(e.get("auteur"))
    cartes = []
    for ligne in lignes or []:
        qui = ligne.get("user_id")
        sid = str(ligne.get("session_id"))
        auteurs = par_seance.get((qui, sid), set())
        cartes.append({
            "id": ligne.get("id"),
            "compte": qui,
            "session_id": sid,
            "moi": qui == moi,
            "nom": "Toi" if qui == moi else nom_affiche(profils.get(qui)),
            "seance": ligne.get("seance") or "Séance",
            "date": str(ligne.get("date") or "")[:10],
            "duree_min": ligne.get("duree_min"),
            "tonnage": _nombre_fr(ligne.get("tonnage")),
            "records": [{"exo": r.get("exo"), "poids": _poids_fr(r.get("poids"))}
                        for r in (ligne.get("records") or [])[:RECORDS_MAX]],
            "encouragements": len(auteurs) if qui == moi else None,
            "deja": moi in auteurs,
            "_tri": (str(ligne.get("date") or ""), str(ligne.get("created_at") or "")),
        })
    cartes.sort(key=lambda c: c["_tri"], reverse=True)
    for c in cartes:
        c.pop("_tri")
    return cartes
