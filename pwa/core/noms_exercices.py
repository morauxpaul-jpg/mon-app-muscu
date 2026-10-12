"""Un mouvement, un nom ; l'équipement à côté.

Retour d'usage du 11/10 : Progrès listait « Développé decliné (Barre) »,
« Développé décliné barre (Barre) » et « Développer décliné » comme trois
exercices. Hevy et Strong affichent « Bench Press (Barbell) » : le mouvement,
puis le matériel entre parenthèses. L'app stocke déjà ses séries ainsi
(« Développé couché (Haltères) »). Ce qui manquait, c'est une règle pour le
NOM lui-même, appliquée partout où un nom naît (programme, séance, exercice
perso) et une fois pour toutes sur l'historique (Gestion → « Ranger mes
exercices ») :

1. Le matériel tapé à la fin du nom va dans le champ équipement :
   « Développé incliné haltères » → « Développé incliné (Haltères) ». Seulement
   si ce qui reste est un mouvement connu ; sinon le mot fait partie du nom
   (« Écarté machine », « Reverse fly machine » : c'est la machine).
2. Le même matériel deux fois se dit une fois : « Développé décliné barre
   (Barre) » → « Développé décliné (Barre) ».
3. Un même mouvement s'écrit d'une seule façon : accents, casse, espaces,
   pluriel, ordre des mots, petite faute de frappe. Deux mots qui existent
   tous les deux (« adducteurs » / « abducteurs ») ne sont jamais une faute.

Rien ici n'écrit en base : ces fonctions proposent, Gestion applique ce que
l'utilisateur a coché.
"""
import os
import re
from difflib import SequenceMatcher
from functools import lru_cache

from core.exercises_data import EXERCISES_INFO, _cle, _jetons, resoudre
from core.muscu import separer_variante

# Le mot tapé → le matériel de la liste (core.muscu.VARIANTS).
MOTS_MATERIEL = {
    "barre": "Barre",
    "haltere": "Haltères", "halteres": "Haltères",
    "poulie": "Poulie",
    "machine": "Machine",
    "leste": "Lesté", "lestes": "Lesté", "lestee": "Lesté", "lestees": "Lesté",
}

# Le mot de matériel y dit le MOUVEMENT, pas seulement l'outil : l'extension
# triceps à l'haltère se fait au-dessus de la tête, rien à voir avec les
# extensions à la poulie (pushdown). Retirer « haltère » les fondrait en un.
_MATERIEL_FAIT_LE_MOUVEMENT = {_cle("Extension triceps haltère")}

_BIBLIOTHEQUE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "static", "js", "exercise-library.js")


def _lire_bibliotheque():
    """Noms (et surnoms) de la bibliothèque d'exercices du sélecteur.

    C'est elle que l'utilisateur voit en ajoutant un exercice : ses noms sont
    l'orthographe de référence, avec ceux des fiches (core.exercises_data)."""
    try:
        with open(_BIBLIOTHEQUE, encoding="utf-8") as f:
            texte = f.read()
    except OSError:
        return []
    return re.findall(r'\{\s*name:\s*"([^"]+)"(?:,\s*alias:\s*"([^"]*)")?', texte)


_ENTREES_BIBLIO = _lire_bibliotheque()
# Les noms de référence, dans l'ordre de préférence : la bibliothèque (ce que
# l'on choisit), puis les fiches.
REFERENCES = list(dict.fromkeys([n for n, _a in _ENTREES_BIBLIO] + list(EXERCISES_INFO)))
_REF_PAR_CLE = {}
_REF_PAR_JETONS = {}
for _n in REFERENCES:
    _REF_PAR_CLE.setdefault(_cle(_n), _n)
    _REF_PAR_JETONS.setdefault(_jetons(_n), _n)
# Les mots que l'app connaît : deux d'entre eux ne sont jamais une faute de
# frappe l'un de l'autre (« adducteurs » / « abducteurs »).
_VOCABULAIRE = {m for n in REFERENCES for m in _jetons(n)}

def _espaces(nom: str) -> str:
    return " ".join((nom or "").split())


def _mots_proches(a: str, b: str) -> bool:
    if a == b:
        return True
    if a in _VOCABULAIRE and b in _VOCABULAIRE:
        return False
    if len(a) < 4 or len(b) < 4:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.82


def faute_de_frappe(a: str, b: str) -> bool:
    """Mêmes mots à une faute près, un pour un (« Développer décliné » /
    « Développé décliné »). Pas deux mots connus l'un pour l'autre."""
    ja, jb = list(_jetons(a)), list(_jetons(b))
    if not ja or len(ja) != len(jb) or set(ja) == set(jb):
        return False
    restants = list(jb)
    for m in ja:
        i = next((k for k, autre in enumerate(restants) if _mots_proches(m, autre)), None)
        if i is None:
            return False
        restants.pop(i)
    return True


def meme_mouvement(a: str, b: str) -> str | None:
    """Pourquoi deux noms (sans matériel) désignent le même mouvement, ou None.

    « orthographe » : accents, casse, espaces, ponctuation ;
    « mots » : pluriel, accord, ordre des mots ;
    « faute » : une faute de frappe par mot au plus."""
    if _cle(a) == _cle(b):
        return "orthographe"
    # Deux fiches différentes sont deux exercices, même à un pluriel près :
    # le catalogue distingue « Squat » et « Squats », « Shrug » et « Shrugs ».
    fa, fb = _fiche(a), _fiche(b)
    if fa and fb and fa != fb:
        return None
    if _jetons(a) == _jetons(b):
        return "mots"
    if faute_de_frappe(a, b):
        return "faute"
    return None


def _prise(nom: str) -> str:
    mots = _cle(nom).split()
    return " ".join(mots[mots.index("prise"):]) if "prise" in mots else ""


def meme_fiche(a: str, b: str) -> bool:
    """Deux noms qui ouvrent la même fiche d'exercice (« Écarté poulie
    vis-à-vis » et « Écartés poulie »). Un indice, pas une preuve : la fiche
    est partagée par des exercices voisins (« Dips » et « Dips (triceps) »),
    et jamais entre deux prises, qui mènent chacune leur progression.

    Les surnoms de la bibliothèque ne servent pas ici : ils disent quelle
    fiche montrer (« Tirage vertical prise large » → « Tirage vertical »),
    pas que deux historiques n'en font qu'un."""
    if _prise(a) != _prise(b):
        return False
    (fa, na), (fb, nb) = _resolution(a), _resolution(b)
    return bool(fa) and fa == fb and _INDICE_SUR(na) and _INDICE_SUR(nb)


def _INDICE_SUR(niveau: str) -> bool:
    """Une fiche trouvée parce que le nom CONTIENT plus de mots qu'elle
    (« Squat sumo », « Mollets presse à cuisse », « Crunch inversé ») ne dit
    rien de l'exercice : ces mots en plus le changent. Ni la prise."""
    return niveau not in ("sous_ensemble", "prise")


# La reconnaissance ne dépend que du catalogue, figé au démarrage : la
# mémoriser rend Gestion instantanée (0,29 s → quelques ms sur 57 noms).
@lru_cache(maxsize=4096)
def _fiche(nom: str):
    return resoudre(nom)[0]


@lru_cache(maxsize=4096)
def _resolution(nom: str):
    return resoudre(nom)


@lru_cache(maxsize=4096)
def reference(nom: str) -> tuple[str | None, str]:
    """Le nom de référence (bibliothèque, puis fiches) de ce mouvement."""
    ref = _REF_PAR_CLE.get(_cle(nom))
    if ref:
        return ref, "orthographe"
    ref = _REF_PAR_JETONS.get(_jetons(nom))
    if ref:
        return ref, "mots"
    for ref in REFERENCES:
        if faute_de_frappe(nom, ref):
            return ref, "faute"
    return None, ""


def _connu(nom: str, connus) -> bool:
    if reference(nom)[0]:
        return True
    return any(meme_mouvement(nom, c) for c in connus)


def sortir_materiel(nom: str, connus=()) -> tuple[str, str | None, str]:
    """(mouvement, matériel, raison) : le matériel quitte le nom.

    `connus` : les autres mouvements de l'utilisateur, pour reconnaître
    « Développé incliné » dans « Développé incliné haltères » même hors
    bibliothèque. La raison vaut "" quand rien n'a bougé."""
    base, materiel = separer_variante(_espaces(nom))
    mots = base.split()
    if len(mots) < 2 or _cle(mots[-1]) not in MOTS_MATERIEL or _cle(base) in _MATERIEL_FAIT_LE_MOUVEMENT:
        return base, materiel, ""
    mot = MOTS_MATERIEL[_cle(mots[-1])]
    reste = " ".join(mots[:-1])
    if materiel == mot:
        # « Développé décliné barre (Barre) » : dit deux fois. Le reste doit
        # garder sa fiche (« Curl incliné » retrouve « Curl incliné haltères »).
        if _connu(reste, connus) or _fiche(reste):
            return reste, materiel, "equipement_double"
        return base, materiel, ""
    if materiel is None and _connu(reste, connus):
        return reste, mot, "equipement_dans_le_nom"
    # Rien de sûr : matériel contradictoire (« Tirage horizontal poulie
    # (Machine) »), ou le mot fait partie du nom (« Écarté machine »).
    return base, materiel, ""


def nom_complet(mouvement: str, materiel: str | None) -> str:
    return f"{mouvement} ({materiel})" if materiel and materiel != "Standard" else mouvement


# ── Ranger un historique ────────────────────────────────────────
# Raisons, de la plus sûre à la moins sûre. Les deux dernières ne sont pas
# cochées d'office : une fusion d'historiques ne se défait pas.
RAISONS = {
    "equipement_double": "équipement écrit deux fois",
    "equipement_dans_le_nom": "équipement écrit dans le nom",
    "orthographe": "accents, majuscules ou espaces",
    "mots": "pluriel ou ordre des mots",
    "faute": "faute de frappe",
    "fiche": "même fiche d'exercice : à toi de voir",
}
RAISONS_SURES = {"equipement_double", "equipement_dans_le_nom", "orthographe", "mots"}
# Une faute de frappe est sûre quand elle mène à l'orthographe de la
# bibliothèque ou des fiches (« Développer décliné » → « Développé décliné ») ;
# vers un autre nom tapé à la main, l'utilisateur coche lui-même.


def ranger(noms_comptes: dict) -> list[dict]:
    """Ce qu'il faudrait renommer pour qu'un mouvement n'ait qu'un nom.

    `noms_comptes` : {nom complet tel qu'en base : nombre de séries}.
    Rend une liste de propositions {depuis, vers, mouvement, series,
    raisons, sur}, rien pour un nom déjà rangé. Le nom retenu pour un
    mouvement est l'orthographe de référence si l'un des noms en est une,
    sinon le plus utilisé — on ne renomme pas « Presse à cuisses » en
    « Leg press » parce que la bibliothèque dit « Leg press ».
    """
    # 1. Le matériel sort des noms.
    propres = {}
    bases = {separer_variante(_espaces(n))[0] for n in noms_comptes}
    for nom in noms_comptes:
        autres = bases - {separer_variante(_espaces(nom))[0]}
        mouvement, materiel, raison = sortir_materiel(nom, autres)
        propres[nom] = (mouvement, materiel, raison)

    # 2. Les mouvements qui sont le même, en groupes (union-find).
    series_par_mvt = {}
    for nom, (mvt, _m, _r) in propres.items():
        series_par_mvt[mvt] = series_par_mvt.get(mvt, 0) + noms_comptes[nom]
    mvts = sorted(series_par_mvt)
    parent = {m: m for m in mvts}

    def chef(m):
        while parent[m] != m:
            parent[m] = parent[parent[m]]
            m = parent[m]
        return m

    for i, a in enumerate(mvts):
        for b in mvts[i + 1:]:
            if meme_mouvement(a, b) or meme_fiche(a, b):
                parent[chef(b)] = chef(a)
    groupes = {}
    for m in mvts:
        groupes.setdefault(chef(m), []).append(m)

    # 3. Le nom retenu pour chaque groupe.
    retenu = {}
    for membres in groupes.values():
        refs = [m for m in membres if _REF_PAR_CLE.get(_cle(m)) == m]
        if refs:
            # À égalité : le nom de la fiche, puis le plus court (« Dips »
            # plutôt que « Dips (triceps) »).
            choix = max(refs, key=lambda m: (series_par_mvt[m], m in EXERCISES_INFO, -len(m), m))
        else:
            # Aucun n'est écrit comme la référence : sa référence si le
            # groupe en a une, sinon le nom de sa fiche (« ÉCARTÉ POULIE VIS
            # À VIS HAUTE » → « Écartés poulie », à vérifier), sinon le plus
            # utilisé — un exercice maison reste tel quel.
            le_plus = max(membres, key=lambda m: (series_par_mvt[m], m))
            ref, _comment = reference(le_plus)
            fiche, niveau = _resolution(le_plus)
            if ref:
                choix = ref
            elif fiche and _INDICE_SUR(niveau) and not _prise(le_plus):
                choix = fiche
            else:
                choix = le_plus
        for m in membres:
            retenu[m] = choix

    # 4. Les propositions.
    out = []
    for nom, (mvt, materiel, raison) in propres.items():
        cible = retenu[mvt]
        vers = nom_complet(cible, materiel)
        if vers == nom:
            continue
        raisons = [raison] if raison else []
        if cible != mvt:
            raisons.append(meme_mouvement(mvt, cible) or ("fiche" if meme_fiche(mvt, cible)
                                                          else reference(mvt)[1] or "fiche"))
        elif not raison:
            raisons.append("orthographe")        # espaces en trop
        cible_de_reference = _REF_PAR_CLE.get(_cle(cible)) == cible
        out.append({
            "depuis": nom, "vers": vers, "mouvement": cible,
            "series": noms_comptes[nom],
            # Le nom d'arrivée a déjà ses séries : deux historiques n'en
            # feront plus qu'un. Souvent voulu, jamais anodin.
            "fusion": vers in noms_comptes or any(
                p != nom and nom_complet(retenu[m], mat) == vers
                for p, (m, mat, _r) in propres.items()),
            "raisons": [RAISONS.get(r, r) for r in raisons],
            "sur": all(r in RAISONS_SURES or (r == "faute" and cible_de_reference)
                       for r in raisons),
        })
    out.sort(key=lambda p: (p["mouvement"].casefold(), p["depuis"].casefold()))
    return out


def nom_pour_saisie(nom: str, connus=()) -> tuple[str, str | None]:
    """Le nom à enregistrer pour ce que l'utilisateur vient de taper, et le
    matériel qu'il y avait mis : (mouvement, matériel).

    « developpe incline halteres » → (« Développé incliné », « Haltères »).
    Un mouvement déjà connu de l'utilisateur garde SON orthographe ; sinon
    celle de la bibliothèque si elle est sûre ; sinon ce qui a été tapé."""
    connus = [_espaces(c) for c in connus if c]
    mouvement, materiel, _r = sortir_materiel(nom, connus)
    for c in connus:
        if c != mouvement and meme_mouvement(mouvement, c) in ("orthographe", "mots"):
            return c, materiel
    if mouvement in connus:
        return mouvement, materiel
    ref, comment = reference(mouvement)
    if ref and comment in ("orthographe", "mots", "faute"):
        return ref, materiel
    return mouvement, materiel


def connus_de(hist, prog) -> list[str]:
    """Les mouvements que l'utilisateur a déjà nommés : historique (sans le
    matériel), programme, exercices perso. Un nom tapé qui en rejoint un
    prend son orthographe."""
    noms = set()
    for r in hist or []:
        ex = str(r.get("Exercice") or "").strip()
        if ex and ex != "SESSION" and not ex.startswith("CARDIO:"):
            noms.add(separer_variante(ex)[0])
    for cle, exos in (prog or {}).items():
        if str(cle).startswith("_") or not isinstance(exos, list):
            continue
        noms.update(str(e.get("name") or "").strip() for e in exos if isinstance(e, dict))
    noms.update(str(e.get("name") or "").strip()
                for e in (prog or {}).get("_custom_exercises") or [] if isinstance(e, dict))
    noms.discard("")
    return sorted(noms)


def ranger_nouveaux(seances: dict, connus_fn) -> list:
    """Range le nom des exercices qui ENTRENT au programme : ceux qui n'ont
    pas encore d'identifiant (core/exercice_ids.py). Jamais un exercice déjà
    là : renommer son nom sans son historique couperait « dernière fois » et
    ses records. Le matériel sorti du nom devient son équipement par défaut
    en séance (`materiel`).

    `connus_fn` ne sert qu'au besoin (il lit l'historique). Rend les
    renommages [séance, ancien nom, nouveau nom, matériel], pour l'éditeur."""
    renommes, connus = [], None
    for sname, exos in seances.items():
        if str(sname).startswith("_") or not isinstance(exos, list):
            continue
        for e in exos:
            if not isinstance(e, dict) or e.get("id") or not e.get("name"):
                continue
            if connus is None:
                connus = connus_fn()
            nom, materiel = nom_pour_saisie(e["name"], connus)
            if materiel and not e.get("materiel"):
                e["materiel"] = materiel
            if nom != e["name"]:
                renommes.append([sname, e["name"], nom, e.get("materiel") or ""])
                e["name"] = nom
    return renommes
