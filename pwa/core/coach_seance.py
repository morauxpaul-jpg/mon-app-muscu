"""Séance créée par le coach : reprise après une pause, courte, légère.

Le module ne connaît ni Flask ni Supabase. L'IA choisit les exercices,
les séries et les reps ; les CHARGES, elle ne les donne jamais : elles sont
calculées ici depuis l'historique (règle des chiffres du coach, 26/10).

- Charge habituelle d'un exercice : la plus lourde de ses 3 dernières
  séances (séries de travail faites, avant aujourd'hui), au même matériel.
- Reprise : charge habituelle × un facteur qui dépend de la pause (jours
  depuis la dernière séance) ; choix du propriétaire, 02/11 :
  < 14 j −10 %, < 28 j −15 %, < 56 j −25 %, < 120 j −35 %, au-delà −45 %.
- Séance légère : −20 %. Courte ou libre : les charges habituelles.
- Arrondi : 2,5 kg à partir de 20 kg, 1 kg en dessous.
Au poids du corps, le même facteur s'applique aux répétitions.

Les conseils valent pour la PREMIÈRE fois que la séance est faite ; ensuite
la progression ordinaire reprend, depuis ces charges allégées.
"""
import datetime as _dt
import json
import math

from core.hist import CARDIO_PREFIX, TYPE_ECHAUFFEMENT, is_perf
from core.muscu import MUSCLE_LIST, VARIANTS, separer_variante

TYPES = {
    "reprise": {"nom": "Reprise après une pause",
                "pour_ia": "une séance de REPRISE après une pause : volume réduit, "
                           "mouvements simples et connus, pas d'échec, pas de série lourde"},
    "courte": {"nom": "Séance courte",
               "pour_ia": "une séance COURTE et efficace : peu d'exercices, polyarticulaires d'abord"},
    "legere": {"nom": "Séance légère",
               "pour_ia": "une séance LÉGÈRE de récupération active : volume modéré, loin de l'échec"},
    "libre": {"nom": "Autre demande", "pour_ia": "une séance qui répond à la demande ci-dessous"},
}
DUREES = (30, 45, 60, 75)
PALIERS = ((14, 0.90), (28, 0.85), (56, 0.75), (120, 0.65))
FACTEUR_LONGUE_PAUSE = 0.55
FACTEUR_LEGERE = 0.80
MAX_EXOS = 10
SEANCES_REFERENCE = 3
CLE_PROGRAMME = "_seances_coach"


# ── La pause et le facteur ───────────────────────────────────────


def _date(x) -> str:
    return str(x or "")[:10]


def jours_de_pause(hist, aujourdhui: _dt.date):
    """Jours depuis la dernière séance faite (muscu ou cardio), ou None sans
    historique. 0 si l'on s'est entraîné aujourd'hui."""
    dates = [_date(r.get("Date")) for r in hist or [] if r.get("Date") and is_perf(r)]
    dates = [d for d in dates if d <= aujourdhui.isoformat()]
    if not dates:
        return None
    return (aujourdhui - _dt.date.fromisoformat(max(dates))).days


def facteur(type_: str, jours) -> float:
    if type_ == "legere":
        return FACTEUR_LEGERE
    if type_ != "reprise" or jours is None:
        return 1.0
    for limite, f in PALIERS:
        if jours < limite:
            return f
    return FACTEUR_LONGUE_PAUSE


def arrondi(poids: float) -> float:
    if poids >= 20:
        return round(poids / 2.5) * 2.5
    return float(max(0, round(poids)))


def _kg(x: float) -> str:
    return f"{x:g}".replace(".", ",")


# ── Ce qu'on fait d'habitude ─────────────────────────────────────


def _travail(r, avant: str) -> bool:
    exo = str(r.get("Exercice") or "")
    return (bool(exo) and not exo.startswith(CARDIO_PREFIX) and exo != "SESSION"
            and r.get("Type") != TYPE_ECHAUFFEMENT and int(r.get("Reps") or 0) > 0
            and _date(r.get("Date")) and _date(r.get("Date")) < avant)


def exercices_habituels(hist, aujourdhui: _dt.date, limite: int = 25) -> list:
    """Les exercices de la dernière année, les plus pratiqués d'abord :
    [{nom (avec le matériel), seances, derniere}]. Ce que l'IA reçoit."""
    debut = (aujourdhui - _dt.timedelta(days=365)).isoformat()
    par_exo: dict = {}
    for r in hist or []:
        if _travail(r, aujourdhui.isoformat()) and _date(r["Date"]) >= debut:
            par_exo.setdefault(r["Exercice"], set()).add(_date(r["Date"]))
    tries = sorted(par_exo.items(), key=lambda kv: (-len(kv[1]), kv[0].casefold()))
    return [{"nom": n, "seances": len(d), "derniere": max(d)} for n, d in tries[:limite]]


def charge_habituelle(hist, exo_final: str, aujourdhui: _dt.date):
    """{poids, reps, date} : la série la plus lourde des 3 dernières séances de
    cet exercice (au poids du corps, la meilleure en reps). None jamais fait."""
    lignes = [r for r in hist or [] if _travail(r, aujourdhui.isoformat())
              and str(r["Exercice"]).casefold() == exo_final.casefold()]
    dates = sorted({_date(r["Date"]) for r in lignes}, reverse=True)[:SEANCES_REFERENCE]
    lignes = [r for r in lignes if _date(r["Date"]) in dates]
    if not lignes:
        return None
    meilleure = max(lignes, key=lambda r: (float(r.get("Poids") or 0), int(r.get("Reps") or 0)))
    return {"poids": float(meilleure.get("Poids") or 0), "reps": int(meilleure.get("Reps") or 0),
            "date": _date(meilleure["Date"])}


def nom_complet(exo: dict) -> str:
    materiel = exo.get("materiel")
    return f"{exo['name']} ({materiel})" if materiel else exo["name"]


def conseils(exercices, hist, type_: str, f: float, aujourdhui: _dt.date) -> dict:
    """{nom de l'exercice : {poids, reps, habituel, libelle}} — seulement
    quand la séance allège (f < 1) et que l'exercice a un historique."""
    if f >= 1:
        return {}
    titre = "Reprise" if type_ == "reprise" else "Séance légère"
    baisse = round((1 - f) * 100)
    out = {}
    for e in exercices or []:
        ref = charge_habituelle(hist, nom_complet(e), aujourdhui)
        if not ref:
            continue
        if ref["poids"] > 0:
            poids = arrondi(ref["poids"] * f)
            libelle = (f"{titre} : {_kg(poids)} kg, −{baisse} % de tes {_kg(ref['poids'])} kg "
                       f"habituels. Garde 2 à 3 reps en réserve.")
            out[e["name"]] = {"poids": poids, "reps": None, "habituel": ref["poids"], "libelle": libelle}
        else:
            reps = max(1, math.floor(ref["reps"] * f))
            libelle = (f"{titre} : {reps} reps, −{baisse} % de tes {ref['reps']} habituelles. "
                       f"Garde 2 à 3 reps en réserve.")
            out[e["name"]] = {"poids": None, "reps": reps, "habituel": ref["reps"], "libelle": libelle}
    return out


def conseils_actifs(prog: dict, seance: str, hist, date_str: str) -> dict:
    """Les conseils d'une séance du coach tant qu'elle n'a jamais été faite
    un AUTRE jour que `date_str` ; ensuite, la progression ordinaire."""
    fiche = ((prog or {}).get(CLE_PROGRAMME) or {}).get(seance)
    if not isinstance(fiche, dict) or not isinstance(fiche.get("conseils"), dict):
        return {}
    deja = any(r.get("Séance") == seance and _date(r.get("Date")) != _date(date_str) and is_perf(r)
               for r in hist or [])
    return {} if deja else fiche["conseils"]


# ── Ce que l'IA reçoit et rend ───────────────────────────────────


def consigne_ia(type_: str, duree: int, demande: str, habituels: list, jours, profil: dict) -> str:
    """Le prompt. Aucune charge dedans : elles ne viennent pas de l'IA."""
    connus = "; ".join(f"{h['nom']} ({h['seances']} séances, dernière le {h['derniere']})"
                       for h in habituels) or "aucun (débutant ou nouveau compte)"
    pause = ("aucune séance enregistrée" if jours is None
             else f"dernière séance il y a {jours} jour{'s' if jours > 1 else ''}")
    return (
        "Tu es un coach de musculation. Crée " + TYPES[type_]["pour_ia"] + ".\n"
        f"- Durée visée : {duree} minutes, échauffement compris.\n"
        f"- Pause : {pause}.\n"
        f"- Niveau : {profil.get('niveau') or 'non précisé'} · Objectif : {profil.get('objectif') or 'non précisé'}"
        f" · Équipement : {profil.get('equipement') or 'non précisé'}.\n"
        f"- Demande de l'utilisateur : {demande or 'aucune précision'}.\n"
        f"- SES EXERCICES HABITUELS (nom exact, matériel entre parenthèses) : {connus}.\n\n"
        "Règles : reprends en priorité SES exercices habituels, écrits EXACTEMENT comme ci-dessus "
        "(nom et matériel), pour qu'on puisse lui conseiller des charges depuis son historique. "
        f"Au plus {MAX_EXOS} exercices, 1 à 5 séries, une fourchette de reps, repos 45 à 180 s. "
        "Ne donne AUCUNE charge en kg : l'application les calcule. Champ \"muscle\" parmi : "
        + ", ".join(MUSCLE_LIST) + ".\n"
        "RÉPONDS UNIQUEMENT avec un objet JSON : "
        '{"nom": "Reprise haut du corps", "notes": "deux phrases au plus", "exercices": '
        '[{"name": "Développé couché (Barre)", "sets": 3, "reps": "8-10", "rest_seconds": 120, "muscle": "Pecs"}]}'
    )


def _muscle(x) -> str:
    texte = str(x or "").strip().casefold()
    return next((m for m in MUSCLE_LIST if m.casefold() == texte), "Autre")


def lire_reponse(raw) -> dict:
    """{nom, notes, exercices: [{name, materiel, sets, reps, rest_seconds,
    muscle}]}. Lève ValueError si rien n'est exploitable."""
    data = raw
    if not isinstance(raw, dict):
        texte = "\n".join(l for l in str(raw or "").strip().split("\n") if not l.strip().startswith("```"))
        try:
            data = json.loads(texte)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON invalide : {e}")
    if not isinstance(data, dict) or not isinstance(data.get("exercices"), list):
        raise ValueError("pas d'exercices")
    exercices = []
    for e in data["exercices"]:
        if not isinstance(e, dict):
            continue
        nom, materiel = separer_variante(" ".join(str(e.get("name") or "").split())[:80])
        # Relue à l'ajout, la proposition a déjà le matériel à part.
        if not materiel and e.get("materiel") in VARIANTS and e.get("materiel") != "Standard":
            materiel = e["materiel"]
        if not nom or nom.startswith("_") or any(x["name"] == nom for x in exercices):
            continue
        try:
            sets = max(1, min(5, int(e.get("sets") or 3)))
            repos = max(45, min(180, int(e.get("rest_seconds") or 90)))
        except (TypeError, ValueError):
            sets, repos = 3, 90
        exercices.append({"name": nom, "materiel": materiel, "sets": sets,
                          "reps": str(e.get("reps") or "").strip()[:20], "rest_seconds": repos,
                          "muscle": _muscle(e.get("muscle"))})
    if not exercices:
        raise ValueError("aucun exercice valide")
    nom = " ".join(str(data.get("nom") or "").split())[:40] or "Séance du coach"
    return {"nom": nom.lstrip("_") or "Séance du coach",
            "notes": " ".join(str(data.get("notes") or "").split())[:300],
            "exercices": exercices[:MAX_EXOS]}


def nom_libre(nom: str, existants) -> str:
    """« Reprise », « Reprise 2 »… : jamais une séance du programme écrasée."""
    existants = {str(n).casefold() for n in existants}
    if nom.casefold() not in existants:
        return nom
    n = 2
    while f"{nom} {n}".casefold() in existants:
        n += 1
    return f"{nom} {n}"


def suggestion_du_coach(conseil: dict):
    """(suggestion, charge pré-remplie) d'un exercice de séance du coach, comme
    la semaine allégée (core/decharge.py) : le bandeau dit d'où vient la charge."""
    poids = conseil.get("poids") or None
    return ({"kind": "hold", "poids": poids, "reps": conseil.get("reps"),
             "label": conseil.get("libelle") or "", "why": "coach"}, poids)
