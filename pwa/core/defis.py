"""Défis entre amis : ce qu'on calcule sans toucher à la base (v53).

Le module ne connaît ni Flask ni Supabase : on lui passe des lignes déjà
lues (core/db_defis.py), il rend ce que la page affiche. Le score n'est
JAMAIS stocké : il est recalculé ici depuis les lignes brutes de `history`
(user_id, date, seance, exercice, reps, poids, mesures cardio, type_serie).

Trois types :
  - régularité : séances faites pendant le défi (une séance = un couple
    date + nom de séance avec au moins une vraie série, cardio compris,
    comme partout dans l'app : `core.hist`) ;
  - volume : tonnage (kg × reps) des séries de travail, sans cardio ni
    échauffement ;
  - progression : hausse en % de la meilleure charge sur l'exercice.
    Référence : la meilleure charge des 4 semaines (28 jours) avant le
    début. Sans série chargée de cet exercice sur ces 28 jours, pas de
    référence : le participant est classé à part et ne peut pas gagner.
    Le % évite qu'un plus fort gagne d'office.

Gagner demande un score strictement positif ; des scores égaux (au chiffre
affiché près) partagent le rang, et tous les premiers gagnent ensemble.
"""
import datetime as _dt

from core.amis import nom_affiche
from core.hist import CARDIO_PREFIX, SESSION_MARKER, TYPE_ECHAUFFEMENT, perf_brute
from core.muscu import separer_variante

TYPES = {
    "regularite": {"nom": "Régularité", "but": "le plus de séances"},
    "volume": {"nom": "Volume", "but": "le plus de kilos soulevés"},
    "progression": {"nom": "Progression", "but": "la plus forte hausse de la meilleure charge"},
}
SEMAINES = (1, 2, 4)
DEPARTS = ("aujourdhui", "demain", "lundi")
REFERENCE_JOURS = 28
MAX_PARTICIPANTS = 10       # créateur compris
MAX_EN_COURS = 10           # défis pas encore finis, par compte
FIL_JOURS = 30              # un défi fini reste 30 jours dans le fil


def bornes(depart: str, semaines: int, aujourdhui: _dt.date) -> tuple:
    """(début, fin incluse). Lundi = le prochain lundi (pas aujourd'hui)."""
    if depart == "demain":
        debut = aujourdhui + _dt.timedelta(days=1)
    elif depart == "lundi":
        debut = aujourdhui + _dt.timedelta(days=7 - aujourdhui.weekday())
    else:
        debut = aujourdhui
    return debut, debut + _dt.timedelta(days=7 * int(semaines) - 1)


def _date(x) -> _dt.date:
    return x if isinstance(x, _dt.date) else _dt.date.fromisoformat(str(x)[:10])


def phase(defi: dict, aujourdhui: _dt.date) -> str:
    """a_venir, en_cours ou termine."""
    if aujourdhui < _date(defi["debut"]):
        return "a_venir"
    return "en_cours" if aujourdhui <= _date(defi["fin"]) else "termine"


def peut_repondre(defi: dict, aujourdhui: _dt.date) -> bool:
    """Une invitation se règle au plus tard le jour du début : le défi
    démarre avec ceux qui ont accepté."""
    return aujourdhui <= _date(defi["debut"])


def titre(defi: dict) -> str:
    nom = TYPES.get(defi.get("type"), {}).get("nom", "Défi")
    if defi.get("type") == "progression" and defi.get("exercice"):
        return f"{nom} · {defi['exercice']}"
    return nom


def jours_restants(defi: dict, aujourdhui: _dt.date) -> int:
    return max(0, (_date(defi["fin"]) - aujourdhui).days)


# ── Le score, depuis les lignes brutes de history ────────────────


def _travail(ligne) -> bool:
    """Série de musculation réellement faite, hors échauffement."""
    exo = str(ligne.get("exercice") or "")
    return (exo != SESSION_MARKER and not exo.startswith(CARDIO_PREFIX)
            and ligne.get("type_serie") != TYPE_ECHAUFFEMENT and perf_brute(ligne))


def _entre(lignes, debut, fin):
    d, f = str(debut)[:10], str(fin)[:10]
    return [l for l in lignes or [] if d <= str(l.get("date") or "")[:10] <= f]


def seances(lignes) -> int:
    return len({(str(l.get("date"))[:10], l.get("seance")) for l in lignes or []
                if l.get("date") and perf_brute(l)})


def volume(lignes) -> int:
    return int(sum(float(l.get("poids") or 0) * int(l.get("reps") or 0)
                   for l in lignes or [] if _travail(l)))


def _meme_exercice(cible: str):
    """Le mouvement compte quel que soit le matériel, à l'orthographe près
    (« Développé couché (Barre) » pour « développé couché »)."""
    from core.noms_exercices import meme_mouvement
    vus: dict = {}

    def teste(nom):
        if nom not in vus:
            vus[nom] = bool(meme_mouvement(separer_variante(nom or "")[0], cible))
        return vus[nom]
    return teste


def meilleure_charge(lignes, exercice: str) -> float:
    teste = _meme_exercice(exercice)
    charges = [float(l.get("poids") or 0) for l in lignes or []
               if _travail(l) and int(l.get("reps") or 0) > 0 and teste(l.get("exercice"))]
    return max([c for c in charges if c > 0], default=0.0)


def debut_lecture(defi: dict) -> _dt.date:
    """Première date de history utile au score (la référence pour la progression)."""
    debut = _date(defi["debut"])
    if defi.get("type") == "progression":
        return debut - _dt.timedelta(days=REFERENCE_JOURS)
    return debut


def score(defi: dict, lignes, aujourdhui: _dt.date) -> dict:
    """{valeur, texte, seances} pour UN participant. `valeur` vaut None quand
    il n'y a pas de score (pas de référence, exercice pas encore fait)."""
    debut = _date(defi["debut"])
    fin = min(_date(defi["fin"]), aujourdhui)
    pendant = _entre(lignes, debut, fin) if fin >= debut else []
    nb = seances(pendant)
    if defi.get("type") == "regularite":
        return {"valeur": nb, "texte": f"{nb} séance{'s' if nb > 1 else ''}", "seances": nb}
    if defi.get("type") == "volume":
        v = volume(pendant)
        return {"valeur": v, "texte": f"{_nombre(v)} kg", "seances": nb}
    avant = _entre(lignes, debut - _dt.timedelta(days=REFERENCE_JOURS), debut - _dt.timedelta(days=1))
    ref = meilleure_charge(avant, defi.get("exercice") or "")
    if ref <= 0:
        return {"valeur": None, "texte": "Pas de référence", "seances": nb}
    meilleure = meilleure_charge(pendant, defi.get("exercice") or "")
    if meilleure <= 0:
        return {"valeur": None, "texte": "Pas encore fait", "seances": nb}
    pct = round((meilleure - ref) * 100 / ref, 1)
    return {"valeur": pct, "texte": _pourcent(pct), "seances": nb}


def _nombre(x) -> str:
    return f"{int(round(x)):,}".replace(",", " ")


def _pourcent(p: float) -> str:
    if p == 0:
        return "0 %"
    texte = f"{abs(p):.1f}".replace(".", ",").replace(",0", "")
    return ("+" if p > 0 else "−") + texte + " %"


# ── Classement et résultat ───────────────────────────────────────


def classement(defi: dict, participants, lignes_par_compte: dict, profils: dict,
               moi: str, aujourdhui: _dt.date) -> list:
    """Les participants qui ont ACCEPTÉ, du meilleur au moins bon. Rangs
    partagés en cas d'égalité (1, 1, 3). Les sans-score à la fin, sans
    rang. Un ami aux séances masquées garde son score, mais aucun détail :
    `seances` (le nombre de séances du défi) n'est rempli que pour les
    autres, et pour soi."""
    lignes = []
    for p in participants or []:
        if p.get("etat") != "acceptee":
            continue
        qui = p["user_id"]
        s = score(defi, lignes_par_compte.get(qui, []), aujourdhui)
        masque = qui != moi and bool((profils.get(qui) or {}).get("seances_masquees"))
        lignes.append({
            "compte": qui, "moi": qui == moi,
            "nom": "Toi" if qui == moi else nom_affiche(profils.get(qui)),
            "valeur": s["valeur"], "texte": s["texte"],
            "seances": None if masque else s["seances"],
        })
    lignes.sort(key=lambda l: (l["valeur"] is None, -(l["valeur"] or 0), l["nom"].casefold()))
    rang, precedent = 0, object()
    for i, l in enumerate(lignes):
        if l["valeur"] is None:
            l["rang"] = None
            continue
        if l["valeur"] != precedent:
            rang, precedent = i + 1, l["valeur"]
        l["rang"] = rang
    return lignes


def gagnants(lignes) -> list:
    """Les premiers, s'ils ont un score strictement positif."""
    return [l for l in lignes if l.get("rang") == 1 and (l.get("valeur") or 0) > 0]


def annonce(defi: dict, lignes) -> str:
    """La phrase du résultat, une fois le défi fini."""
    tete = gagnants(lignes)
    if not tete:
        return "Pas de gagnant : personne n'a marqué de point."
    if len(tete) == 1:
        qui = "Tu gagnes" if tete[0]["moi"] else f"{tete[0]['nom']} gagne"
        return f"{qui} avec {tete[0]['texte']}."
    noms = ["toi" if l["moi"] else l["nom"] for l in tete]
    liste = ", ".join(noms[:-1]) + " et " + noms[-1]
    return f"Égalité entre {liste} : {tete[0]['texte']} chacun."


def exercices_proposes(hist, limite: int = 30) -> list:
    """Les mouvements de l'historique (app normalisée), les plus pratiqués
    d'abord : ce qu'on peut proposer pour un défi de progression."""
    comptes: dict = {}
    for r in hist or []:
        exo = str(r.get("Exercice") or "")
        if not exo or exo.startswith(CARDIO_PREFIX) or exo == SESSION_MARKER:
            continue
        if float(r.get("Poids") or 0) <= 0 or r.get("Type") == TYPE_ECHAUFFEMENT:
            continue
        nom = separer_variante(exo)[0][:80]
        comptes[nom] = comptes.get(nom, 0) + 1
    return [n for n, _ in sorted(comptes.items(), key=lambda kv: (-kv[1], kv[0].casefold()))][:limite]
