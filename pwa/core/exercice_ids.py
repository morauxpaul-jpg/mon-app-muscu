"""Identité stable des exercices : un identifiant, pas un nom.

L'historique retrouvait un exercice par son NOM (audit du 03/10, modèle de
données) : renommer « Curl » en « Curl marteau » coupait le passé, à moins de
réécrire toutes ses séries — ce que faisait le renommage suivi (PR #13), au
prix d'un historique qui ne garde pas le nom sous lequel la série a été faite.

Désormais :

* chaque exercice du programme porte un `id` (`e_` + 8 caractères). Il est
  calculé une fois à partir du nom, puis **ne bouge plus** : renommer garde
  l'identifiant ;
* une série enregistrée porte `exercise_id` (migration v42) : l'identifiant de
  son exercice, suivi de la variante (`e_1a2b3c4d~Haltères`) — la variante
  fait partie du nom stocké (« Curl (Haltères) ») ;
* à la lecture, une série dont l'identifiant est au programme s'affiche sous le
  nom ACTUEL de l'exercice (`afficher_selon_programme`). Le nom stocké reste
  celui du jour de la série.

Les lignes plus anciennes que la v42 n'ont pas d'identifiant : elles se lisent
par leur nom, comme avant, jusqu'à ce qu'un renommage « même exercice » les
marque (`core/db_identite.py`).

Deux exercices au nom identique (casse, accents et espaces mis à part) dans le
même programme partagent leur identifiant : c'est le même mouvement, comme
avant. Un nom qui retombe sur l'identifiant d'un exercice renommé en reçoit un
autre — un nouveau « Curl » n'hérite pas du passé de « Curl marteau ».
"""
import hashlib
import re
import unicodedata

_FORME = re.compile(r"^e_[0-9a-f]{8}(?:-\d+)?$")
SEPARATEUR = "~"


def cle(nom) -> str:
    """Nom comparable : minuscules, sans accents ni espaces superflus."""
    s = unicodedata.normalize("NFKD", str(nom or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def valide(eid) -> bool:
    return isinstance(eid, str) and bool(_FORME.match(eid))


def _depuis_nom(nom: str, rang: int = 1) -> str:
    base = "e_" + hashlib.sha1(cle(nom).encode("utf-8")).hexdigest()[:8]
    return base if rang == 1 else f"{base}-{rang}"


def _entrees(prog: dict):
    """Les exercices du programme, séance par séance (clés `_x` exclues)."""
    for nom_seance, exos in (prog or {}).items():
        if isinstance(nom_seance, str) and not nom_seance.startswith("_") and isinstance(exos, list):
            for ex in exos:
                if isinstance(ex, dict) and str(ex.get("name") or "").strip():
                    yield ex


def assurer_ids(prog: dict) -> dict:
    """Donne un identifiant à chaque exercice qui n'en a pas (sur place).

    Déterministe : relire le même programme donne les mêmes identifiants, qu'ils
    soient déjà enregistrés ou non. C'est ce qui permet de les attribuer dès la
    lecture, sans écrire en base."""
    proprietaire, par_nom = {}, {}
    for ex in _entrees(prog):
        eid = ex.get("id")
        if valide(eid):
            proprietaire.setdefault(eid, cle(ex["name"]))
            par_nom.setdefault(cle(ex["name"]), eid)
        elif "id" in ex:
            ex.pop("id")
    for ex in _entrees(prog):
        if valide(ex.get("id")):
            continue
        c = cle(ex["name"])
        eid = par_nom.get(c)
        if eid is None:
            rang = 1
            eid = _depuis_nom(ex["name"])
            while eid in proprietaire and proprietaire[eid] != c:
                rang += 1
                eid = _depuis_nom(ex["name"], rang)
            proprietaire[eid] = c
            par_nom[c] = eid
        ex["id"] = eid
    return prog


def noms_par_id(prog: dict) -> dict:
    """id → nom actuel. Deux noms pour un même id : le premier rencontré."""
    out = {}
    for ex in _entrees(prog):
        if valide(ex.get("id")):
            out.setdefault(ex["id"], str(ex["name"]).strip())
    return out


def pour_serie(exo_id, variante) -> str | None:
    """Valeur de `history.exercise_id` pour une série, ou None."""
    if not valide(exo_id):
        return None
    v = str(variante or "").strip()
    return exo_id if not v or v == "Standard" else f"{exo_id}{SEPARATEUR}{v[:60]}"


def separer(valeur):
    """`e_x~Haltères` → ("e_x", "Haltères") ; valeur absente → (None, "")."""
    if not valeur:
        return None, ""
    eid, _, variante = str(valeur).partition(SEPARATEUR)
    return (eid if valide(eid) else None), variante


def afficher_selon_programme(hist: list, prog: dict) -> list:
    """Remet chaque série identifiée sous le nom actuel de son exercice.

    Une série sans identifiant, ou dont l'exercice n'est plus au programme,
    garde son nom stocké. Les séries cardio ne sont pas concernées."""
    noms = noms_par_id(prog)
    if not noms:
        return hist
    for r in hist:
        eid, variante = separer(r.get("ExoId"))
        nom = noms.get(eid) if eid else None
        if nom and not str(r.get("Exercice") or "").startswith("CARDIO:"):
            r["Exercice"] = f"{nom} ({variante})" if variante else nom
    return hist
