"""Un seul vocabulaire de groupes musculaires.

`MUSCLE_LIST` remplit les sélecteurs du créateur de programme, les étiquettes
de la gestion, les zones de la carte du corps et le vocabulaire imposé au
générateur IA. Elle vivait recopiée à l'identique dans quatre fichiers : quatre
exemplaires qu'il fallait penser à modifier ensemble, et rien ne le rappelait.

Elle vit maintenant dans `core.muscu`. Ces tests interdisent le retour d'un
second exemplaire, et tiennent ensemble les deux listes qui en DÉRIVENT :
la carte du corps (tous les muscles sauf « Autre », qui n'a pas de zone) et
les muscles que `auto_muscles` sait déduire d'un nom d'exercice.

À ne pas confondre avec `fiche["muscles"]`, qui est de l'anatomie lisible
(« Pectoraux (haut) », « Rhomboïdes ») affichée sur la fiche d'un exercice.
C'est un autre métier, et il n'a pas à s'aligner sur celui-ci.
"""
import re
from pathlib import Path

from core.exercises_data import EXERCISES_INFO
from core.muscu import MUSCLE_LIST, auto_muscles

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / "core" / "muscu.py"


def _sources_python():
    for chemin in list((RACINE / "routes").glob("*.py")) + list((RACINE / "core").glob("*.py")):
        if chemin != SOURCE:
            yield chemin


def test_aucun_second_exemplaire_de_la_liste():
    """Personne ne redéclare MUSCLE_LIST ailleurs que dans core/muscu.py."""
    coupables = [c.relative_to(RACINE).as_posix() for c in _sources_python()
                 if re.search(r"^MUSCLE_LIST\s*=", c.read_text(encoding="utf-8"), re.M)]
    assert coupables == [], (
        "MUSCLE_LIST est redéclarée dans " + ", ".join(coupables)
        + " — elle doit être importée de core.muscu.")


def test_aucune_liste_de_muscles_recopiee():
    """Aucune liste littérale ne recommence par les muscles de MUSCLE_LIST.

    Attrape la copie déguisée sous un autre nom (`MUSCLES = [...]`), qui est
    exactement la forme qu'avait la duplication dans le générateur.
    """
    debut = f'"{MUSCLE_LIST[0]}", "{MUSCLE_LIST[1]}", "{MUSCLE_LIST[2]}"'
    coupables = [c.relative_to(RACINE).as_posix() for c in _sources_python()
                 if debut in c.read_text(encoding="utf-8")]
    assert coupables == [], (
        "liste de muscles recopiée dans " + ", ".join(coupables))


def test_carte_du_corps_couvre_tous_les_muscles_sauf_autre():
    """Un muscle ajouté à MUSCLE_LIST doit recevoir une zone sur le dessin.

    Sans ce test, il disparaîtrait de la carte ET des filtres de /progres
    sans le moindre signe.
    """
    from routes.progres import MUSCLES as zones
    attendu = [m for m in MUSCLE_LIST if m != "Autre"]
    assert list(zones.keys()) == attendu


def test_chaque_zone_de_la_carte_a_un_cote():
    """Une zone sans face avant ni arrière ne se dessine nulle part."""
    from routes.progres import MUSCLES as zones
    orphelines = [m for m, info in zones.items()
                  if not info.get("zid_f") and not info.get("zid_b")]
    assert orphelines == []


def test_auto_muscles_ne_sort_jamais_du_vocabulaire():
    """Les muscles déduits d'un nom doivent être affichables.

    `auto_muscles` écrit dans le champ muscle d'un exercice. Une faute de
    frappe dans sa table de règles produirait une étiquette que les
    sélecteurs ne savent pas montrer et que les filtres ignorent.
    """
    connus = set(MUSCLE_LIST)
    hors = set()
    for nom in EXERCISES_INFO:
        deduit = auto_muscles(nom)
        if deduit:
            hors |= {m for m in deduit.split(",") if m not in connus}
    assert hors == set(), f"auto_muscles invente : {sorted(hors)}"


def test_auto_muscles_couvre_le_catalogue():
    """Presque tout le catalogue doit se voir attribuer un muscle.

    Chiffre constaté, pas choisi : il n'est là que pour signaler une chute.
    Si une refonte des règles fait tomber la couverture, ce test le dit.
    """
    reconnus = sum(1 for nom in EXERCISES_INFO if auto_muscles(nom))
    assert reconnus >= int(len(EXERCISES_INFO) * 0.8), (
        f"{reconnus}/{len(EXERCISES_INFO)} exercices reçoivent un muscle")
