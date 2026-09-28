"""Les trois endroits où l'app DONNE un nom d'exercice.

Le catalogue (`EXERCISES_INFO`) dit ce qu'un exercice est. Mais trois autres
listes en distribuent les noms : la bibliothèque du créateur de programme,
les programmes tout faits de l'inscription, et le générateur IA. Quand elles
dérivent du catalogue, chaque programme construit porte des noms qu'il
faudra rapprocher à vie.

C'est arrivé : le matériel est devenu une variante dans le catalogue, mais
la bibliothèque proposait encore « Élévation latérale haltères » et les
programmes tout faits le citaient 47 fois. Ces tests ferment la porte.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

from core.exercises_data import _ABSORBES, EXERCISES_INFO, resoudre

RACINE = Path(__file__).resolve().parent.parent


def _bibliotheque():
    """Les entrées du fichier JS, lues par Node — une seule source."""
    sortie = subprocess.run(
        ["node", "-e",
         "const l=require('./static/js/exercise-library.js');"
         "console.log(JSON.stringify(Object.entries(l.EXERCISE_LIBRARY)"
         ".flatMap(([g,v])=>v.map(e=>[g,e.name]))))"],
        capture_output=True, text=True, encoding="utf-8", cwd=RACINE)
    if sortie.returncode != 0:
        pytest.skip("node indisponible")
    return json.loads(sortie.stdout)


def _programmes_tout_faits():
    src = (RACINE / "core" / "catalog.py").read_text(encoding="utf-8")
    return sorted(set(re.findall(r'_ex\("([^"]+)"', src)))


# ── Aucune liste ne distribue un nom absorbé ─────────────────────


def test_la_bibliotheque_ne_propose_aucun_nom_absorbe():
    """« Élévation latérale haltères » ne doit plus être proposable : le
    matériel se choisit à côté du nom, pas en choisissant un autre
    exercice."""
    absorbes = {n.casefold() for n in _ABSORBES}
    fautifs = [f"{g} / {n}" for g, n in _bibliotheque() if n.casefold() in absorbes]
    assert not fautifs, fautifs


def test_les_programmes_tout_faits_ne_citent_aucun_nom_absorbe():
    """Un compte créé aujourd'hui doit repartir avec des noms que l'app
    reconnaît — sinon le problème renaît à chaque inscription."""
    absorbes = {n.casefold() for n in _ABSORBES}
    fautifs = [n for n in _programmes_tout_faits() if n.casefold() in absorbes]
    assert not fautifs, fautifs


# ── Tout ce qui est distribué se résout ──────────────────────────


# Trois exercices cités par les programmes tout faits n'ont pas de fiche au
# catalogue, et ce n'en sont pas des variantes : il faudrait les écrire.
# Ils sont nommés ici plutôt que tolérés en silence — le test bloque toute
# NOUVELLE dérive sans prétendre que celle-là est réglée.
SANS_FICHE_CONNUS = {"Dragon flag négatifs", "Good morning", "L-sit progression"}


def test_aucun_nouvel_exercice_sans_fiche_dans_les_programmes_tout_faits():
    """Un programme d'inscription qui cite un exercice inconnu donne des
    cartes sans illustration ni conseils dès la première séance."""
    perdus = {n for n in _programmes_tout_faits()
              if not n.startswith("CARDIO") and not resoudre(n)[0]}
    nouveaux = perdus - SANS_FICHE_CONNUS
    assert not nouveaux, f"sans fiche et pas encore recensés : {sorted(nouveaux)}"


def test_la_liste_des_exercices_sans_fiche_ne_ment_pas():
    """Si l'un d'eux reçoit enfin sa fiche, il doit sortir de la liste —
    sinon elle se fossilise et on ne sait plus ce qui reste à faire."""
    perdus = {n for n in _programmes_tout_faits()
              if not n.startswith("CARDIO") and not resoudre(n)[0]}
    regles = SANS_FICHE_CONNUS - perdus
    assert not regles, f"ont une fiche désormais, à retirer de la liste : {sorted(regles)}"


def test_la_bibliotheque_ne_propose_pas_deux_fois_le_meme_exercice():
    """Deux entrées qui mènent à la même fiche font hésiter pour rien."""
    par_groupe = {}
    for groupe, nom in _bibliotheque():
        par_groupe.setdefault(groupe, []).append(nom)
    doublons = {g: n for g, n in par_groupe.items() if len(set(n)) != len(n)}
    assert not doublons, doublons


def test_une_abduction_de_hanche_nest_pas_une_elevation_laterale():
    """« Élévation latérale jambe » se résolvait vers les élévations
    latérales d'ÉPAULES : les mots se ressemblent, pas les exercices.
    C'est le genre de rapprochement que le flou rend possible."""
    noms = [n for _, n in _bibliotheque()]
    assert "Élévation latérale jambe" not in noms
    for nom in noms:
        if "abduction" in nom.casefold() or "hanche" in nom.casefold():
            cle = resoudre(nom)[0]
            assert cle != "Élévations latérales", f"{nom} -> {cle}"


def test_les_noms_absorbes_ne_sont_plus_au_catalogue():
    """Ils restent dans le fichier source pour documenter la fusion, mais
    ne doivent plus être servis : sinon le sélecteur les reproposerait."""
    presents = [n for n in _ABSORBES if n in EXERCISES_INFO]
    assert not presents, presents


# ── Les surnoms de la bibliothèque sont DÉRIVÉS du catalogue ─────


def test_les_surnoms_de_la_bibliotheque_suivent_le_catalogue():
    """« Overhead triceps extension » était introuvable alors que
    l'exercice existait sous « Extension nuque haltère ». Le catalogue
    connaissait pourtant le surnom : c'est la bibliothèque qui l'ignorait.

    Les deux listes ne s'écrivent plus séparément — celle des surnoms est
    générée depuis l'autre. Ce test échoue dès qu'elles divergent, et la
    commande à lancer est dans son message.
    """
    import sys
    sys.path.insert(0, str(RACINE / "tools"))
    from sync_library_aliases import ecarts
    a_resync = ecarts()
    assert not a_resync, (
        "surnoms désynchronisés pour " + ", ".join(a_resync)
        + " — relancer : python tools/sync_library_aliases.py")


@pytest.mark.parametrize("recherche,attendu", [
    ("overhead triceps extension", "Overhead extension triceps"),
    ("skull crusher", "Skull crusher"),
    ("front raise", "Élévation frontale"),
    ("pec fly", "Écarté machine"),
])
def test_un_nom_anglais_courant_trouve_son_exercice(recherche, attendu):
    """Ce qu'on tape vraiment au moment de construire une séance."""
    sortie = subprocess.run(
        ["node", "-e",
         "const l=require('./static/js/exercise-library.js');"
         "const q=process.argv[1];const t=[];"
         "Object.values(l.EXERCISE_LIBRARY).flat()"
         ".forEach(e=>{if(l.exerciseMatches(e,q))t.push(e.name)});"
         "console.log(JSON.stringify(t))", recherche],
        capture_output=True, text=True, encoding="utf-8", cwd=RACINE)
    if sortie.returncode != 0:
        pytest.skip("node indisponible")
    assert attendu in json.loads(sortie.stdout), sortie.stdout


def test_une_elevation_frontale_nest_pas_une_elevation_laterale():
    """« front raise » pointait vers les élévations LATÉRALES : deux
    faisceaux différents de l'épaule, et donc des conseils qui ne
    correspondent pas au geste qu'on est en train de faire."""
    assert resoudre("Élévation frontale")[0] == "Élévations frontales"
    assert resoudre("front raise")[0] == "Élévations frontales"


@pytest.mark.parametrize("saisi,attendu", [
    ("Skull crusher barre EZ", "Barre au front"),   # nom encore tapable
    ("Pushdown poulie corde", "Extensions triceps"),
])
def test_plusieurs_mots_de_materiel_a_la_suite_sont_tous_retires(saisi, attendu):
    """Le retrait se faisait en une seule passe, dans l'ordre d'une liste :
    « Skull crusher barre EZ » perdait « EZ », mais « barre » était déjà
    derrière nous. L'exercice restait introuvable pour un mot de trop."""
    assert resoudre(saisi)[0] == attendu, resoudre(saisi)


def test_un_nom_absorbe_garde_sa_fiche():
    """La fusion du matériel a failli coûter leur fiche à « Curl barre » et
    « Curl haltères » : leur base est « Curl biceps », et retirer le
    matériel ne laisse que « curl », qui n'est la clé de rien. Quiconque
    avait ces noms dans son programme ou son historique aurait perdu fiche,
    conseils et illustration — sans aucune erreur nulle part.

    Une fusion doit déplacer l'information, jamais la faire disparaître.
    """
    perdus = [n for n in _ABSORBES if not resoudre(n)[0]]
    assert not perdus, perdus


def test_un_nom_absorbe_mene_bien_a_SA_base():
    """Résoudre ne suffit pas : encore faut-il tomber sur le bon exercice."""
    for absorbe, (base, _materiel) in _ABSORBES.items():
        assert resoudre(absorbe)[0] == base, f"{absorbe} -> {resoudre(absorbe)[0]}"


# ── Le matériel ne s'écrit plus dans le nom ──────────────────────

# Ceux où le mot d'équipement EST l'exercice : « poulie basse » et
# « poulie haute » désignent une station, « barre EZ » une barre
# particulière, « vis-à-vis » un montage, « machine adducteurs » une machine
# dédiée. Et « Rowing barre » n'est pas « Rowing haltère » : debout penché
# contre un genou sur le banc, ce n'est pas le même mouvement.
MATERIEL_QUI_EST_LEXERCICE = {
    "Écarté poulie vis-à-vis", "Écarté machine", "Machine adducteurs",
    "Machine abducteurs", "Curl barre EZ", "Curl poulie basse",
    "Développé machine", "Reverse fly machine",
    "Adduction poulie basse", "Abduction poulie basse",
    "Rowing barre", "Rowing haltère", "Pushdown poulie barre",
    "Pushdown poulie corde",
}

MOTS_DE_MATERIEL = {"barre", "haltere", "halteres", "poulie", "machine",
                    "elastique", "corde", "ez", "leste", "lestee", "lestees"}


def test_le_materiel_interchangeable_ne_sappelle_plus_un_exercice():
    """« Extension nuque haltère » empêchait de choisir la poulie : il
    fallait prendre l'entrée « haltère » pour faire autre chose. Le geste
    se choisit dans la liste, le matériel dans le sélecteur de variante."""
    from core.exercises_data import _cle
    fautifs = []
    for _groupe, nom in _bibliotheque():
        if nom in MATERIEL_QUI_EST_LEXERCICE:
            continue
        if any(m in MOTS_DE_MATERIEL for m in _cle(nom).split()):
            fautifs.append(nom)
    assert not fautifs, (
        "matériel dans le nom : " + ", ".join(fautifs)
        + " — soit le retirer, soit l'inscrire dans MATERIEL_QUI_EST_LEXERCICE"
        " en disant pourquoi")


def test_la_liste_des_exceptions_ne_se_fossilise_pas():
    """Une exception qui ne correspond plus à aucune entrée cache une liste
    qu'on n'ose plus toucher."""
    noms = {n for _g, n in _bibliotheque()}
    mortes = MATERIEL_QUI_EST_LEXERCICE - noms
    assert not mortes, f"exceptions sans entrée : {sorted(mortes)}"


def test_chaque_entree_de_bibliotheque_trouve_sa_fiche():
    """Une entrée proposée dans la liste mais absente du catalogue donne une
    carte muette dès la première séance — sans erreur nulle part.

    C'est arrivé : la fiche « Développé machine » a été perdue alors que
    l'entrée de bibliothèque, elle, était bien commitée. Les deux fichiers
    se modifient séparément, donc rien ne les tenait ensemble.
    """
    connues = {"Développé décliné", "Écarté couché", "Pull-over", "T-bar row",
               "Hyperextension", "Curl alterné", "Curl concentré",
               "Pushdown poulie corde", "Kick-back triceps", "Russian twist",
               "Roue abdominale", "Adduction poulie basse", "Copenhagen plank",
               "Abduction poulie basse", "Marche latérale", "Clam shell",
               "Abduction de hanche debout", "Mollets une jambe",
               "Curl poignet", "Curl inversé", "Extension poignet",
               "Farmer walk", "Gripper / pince", "Curl scott (preacher)",
               "Curl haltères alternés", "Tirage poitrine poulie haute"}
    perdues = sorted({nom for _g, nom in _bibliotheque()
                      if not resoudre(nom)[0]} - connues)
    assert not perdues, (
        "entrées de bibliothèque sans fiche : " + ", ".join(perdues))


def test_aucun_nom_de_la_bibliotheque_ne_designe_le_mauvais_endroit():
    """« Extension nuque » laissait croire à un exercice pour le cou : le
    nom d'usage en salle nomme l'endroit où on sent l'étirement, pas le
    muscle travaillé. Pour une liste qu'on parcourt sans lire les fiches,
    c'est trompeur.

    Ces mots-là désignent une partie du corps dans le nom d'un exercice
    qui n'y touche pas.
    """
    pieges = {"nuque": "cou", "cervical": "cou"}
    noms = [n for _g, n in _bibliotheque()]
    fautifs = [f"{n} (\u00e9voque : {quoi})"
               for n in noms for mot, quoi in pieges.items()
               if mot in n.lower()]
    assert not fautifs, fautifs


def test_un_nom_retire_de_la_bibliotheque_reste_reconnu():
    """Quelqu'un qui avait déjà « Extension nuque » dans son programme doit
    garder sa fiche : renommer une entrée de la liste ne renomme pas ce qui
    est déjà enregistré."""
    assert resoudre("Extension nuque")[0] == "Extension triceps haltère"
    assert resoudre("Overhead extension triceps")[0] == "Extension triceps haltère"
