"""Les dossiers de programmes d'un utilisateur (multi-programmes).

Le blob `programs.data` range TOUTES les séances à plat (clés sans « _ »),
plus :
  _programmes  : liste de dossiers {id, name}
  _seance_prog : séance → id de dossier
  _planning    : jour de semaine → séance (un seul planning, global)

Adopter un programme généré ou « Changer de programme » réécrivait tout le
corps du blob : un membre avec « Salle », « Maison » et « Vacances » perdait
les trois (audit du 30/09, I16). Ici, on ne remplace que le programme EN
COURS — les dossiers dont le planning utilise les séances — et on garde les
autres tels quels.
"""
import copy
import uuid

from core import catalog


def gen_prog_id() -> str:
    return "p_" + uuid.uuid4().hex[:8]


def ensure_programmes(prog):
    """Migre l'ancien schéma (dict plat de séances) vers le nouveau schéma
    multi-programmes : _programmes = liste de {id, name} et _seance_prog = map
    seance_name → prog_id. Les séances non mappées tombent dans "Non classé".
    """
    progs = prog.get("_programmes")
    mapping = prog.get("_seance_prog")
    seance_names = [k for k in prog.keys() if not k.startswith("_")]

    if not isinstance(progs, list):
        progs = []
    if not isinstance(mapping, dict):
        mapping = {}

    if not progs:
        # Premier chargement avec l'ancien schéma : crée un programme par
        # défaut et y assigne toutes les séances existantes.
        default_name = (prog.get("_name") or "").strip()
        origin = prog.get("_origin")
        if not default_name and origin:
            src = catalog.get_program(origin)
            if src:
                default_name = src["title"]
        if not default_name:
            default_name = "Mon programme"
        default_id = gen_prog_id()
        progs = [{"id": default_id, "name": default_name[:80]}]
        for sname in seance_names:
            mapping[sname] = default_id
    else:
        # Normalise : garde uniquement les entrées valides
        valid_ids = {p.get("id") for p in progs if isinstance(p, dict) and p.get("id")}
        existing = set(seance_names)
        mapping = {s: pid for s, pid in mapping.items() if s in existing and pid in valid_ids}

    prog["_programmes"] = progs
    prog["_seance_prog"] = mapping
    return progs, mapping


def dossiers_en_cours(prog) -> set:
    """Ids des dossiers dont le planning utilise au moins une séance. Sans
    planning exploitable et avec un seul dossier, c'est celui-là."""
    progs, mapping = ensure_programmes(prog)
    ids = {mapping.get(s) for s in (prog.get("_planning") or {}).values() if s}
    ids.discard(None)
    if not ids and len(progs) == 1:
        ids = {progs[0]["id"]}
    return ids


def _nom_libre(nom, pris):
    if nom not in pris:
        return nom
    n = 2
    while f"{nom} {n}" in pris:
        n += 1
    return f"{nom} {n}"


def remplacer_programme_en_cours(old, seances, planning, nom, started_at, extra=None):
    """Corps à passer à `save_prog_body` : le programme en cours est remplacé
    par `seances` (nouveau dossier `nom`), les AUTRES dossiers et leurs
    séances restent. Une séance nouvelle dont le nom est déjà pris ailleurs
    est suffixée (« Push 2 ») : les noms identifient l'historique."""
    old = copy.deepcopy(old or {})
    progs, mapping = ensure_programmes(old)
    en_cours = dossiers_en_cours(old)

    body = {s: exos for s, exos in old.items()
            if not s.startswith("_") and mapping.get(s) not in en_cours}
    nouveau = {"id": gen_prog_id(), "name": (nom or "Mon programme")[:80]}

    renomme = {}
    for s, exos in (seances or {}).items():
        n = _nom_libre(s, body)
        body[n] = exos
        renomme[s] = n

    body["_programmes"] = [p for p in progs if p.get("id") not in en_cours] + [nouveau]
    seance_prog = {s: pid for s, pid in mapping.items() if s in body and pid not in en_cours}
    seance_prog.update({n: nouveau["id"] for n in renomme.values()})
    body["_seance_prog"] = seance_prog
    body["_planning"] = {j: (renomme.get(s, s) if s else "") for j, s in (planning or {}).items()}
    body["_name"] = nouveau["name"]
    body["_started_at"] = started_at
    for k, v in (extra or {}).items():
        body[k] = v
    return body


def ajouter_et_planifier(old, seances, planning, nom, started_at, extra=None):
    """Corps à passer à `save_prog_body` : ajoute `seances` dans un nouveau
    dossier `nom` et lui donne le planning, SANS rien retirer.

    Pour refaire l'onboarding : l'utilisateur répond à un questionnaire, il
    n'a pas demandé qu'on efface ses séances. Les anciens dossiers restent,
    simplement plus planifiés (audit du 03/10, I6)."""
    old = copy.deepcopy(old or {})
    progs, mapping = ensure_programmes(old)
    body = {s: exos for s, exos in old.items() if not s.startswith("_")}
    nouveau = {"id": gen_prog_id(), "name": (nom or "Mon programme")[:80]}
    renomme = {}
    for s, exos in (seances or {}).items():
        n = _nom_libre(s, body)
        body[n] = exos
        renomme[s] = n
    # Un compte neuf n'a qu'un dossier vide créé à la volée : inutile de le garder.
    gardes = [p for p in progs if any(mapping.get(s) == p.get("id") for s in body)]
    body["_programmes"] = gardes + [nouveau]
    seance_prog = {s: pid for s, pid in mapping.items() if s in body}
    seance_prog.update({n: nouveau["id"] for n in renomme.values()})
    body["_seance_prog"] = seance_prog
    body["_planning"] = {j: (renomme.get(s, s) if s else "") for j, s in (planning or {}).items()}
    body["_name"] = nouveau["name"]
    body["_started_at"] = started_at
    for k, v in (extra or {}).items():
        body[k] = v
    return body


def fusionner_dans_le_programme_en_cours(old, seances):
    """Corps à passer à `save_prog_body` : ajoute les séances qui n'existent
    pas encore au programme en cours, sans rien retirer — ni séance, ni
    dossier, ni planning."""
    old = copy.deepcopy(old or {})
    progs, mapping = ensure_programmes(old)
    en_cours = sorted(dossiers_en_cours(old)) or [progs[0]["id"]]
    cible = en_cours[0]

    body = {s: exos for s, exos in old.items() if not s.startswith("_")}
    seance_prog = dict(mapping)
    for s, exos in (seances or {}).items():
        if s not in body:
            body[s] = exos
            seance_prog[s] = cible
    body["_programmes"] = progs
    body["_seance_prog"] = seance_prog
    body["_planning"] = old.get("_planning") or {}
    # Plus d'origine unique après une fusion : c'est devenu un programme perso.
    if old.get("_name"):
        body["_name"] = old["_name"]
    for k in ("_started_at", "_cardio"):
        if k in old:
            body[k] = old[k]
    return body
