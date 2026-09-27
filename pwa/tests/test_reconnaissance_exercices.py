"""Retrouver la fiche d'un exercice dont le nom vient d'une saisie libre.

Les noms de séance ne sortent pas du catalogue : ils sont tapés à la main
ou importés. Accents, casse, ponctuation, matériel en suffixe, nom anglais —
tout varie. Tant que la reconnaissance échoue, l'exercice perd sa fiche, ses
conseils d'exécution ET son illustration d'un seul coup, sans erreur nulle
part.

Le défaut relevé à l'usage : le matcher comparait les chaînes telles quelles,
donc « Developpe couche » (sans accents, comme le produit un import) ne
trouvait rien alors que « Développé couché » marchait.
"""
import pytest

from core.exercises_data import EXERCISES_INFO, get_exercise_info


@pytest.mark.parametrize("saisi,attendu", [
    ("Développé couché", "Développé couché"),        # tel quel
    ("developpe couche", "Développé couché"),        # sans accents ← le défaut
    ("DEVELOPPE COUCHE", "Développé couché"),        # tout en capitales
    ("Developpé couché", "Développé couché"),        # accents à moitié
    ("developpe-couche", "Développé couché"),        # tirets
    ("  Développé   couché  ", "Développé couché"),  # espaces en trop
    ("Presse a cuisses", "Presse à cuisses"),
    ("Elevations laterales", "Élévations latérales"),
    ("Souleve de terre", "Soulevé de terre"),
])
def test_le_nom_est_reconnu_quelles_que_soient_les_fioritures(saisi, attendu):
    info = get_exercise_info(saisi)
    assert info is not None, f"« {saisi} » ne trouve aucune fiche"
    assert info["name"].startswith(attendu.split(" (")[0])


@pytest.mark.parametrize("saisi,attendu", [
    ("Squat barre", "Squat"),
    ("Curl biceps halteres", "Curl biceps"),
    ("Rowing barre buste penche", "Rowing barre"),
    ("Tractions pronation", "Tractions"),
])
def test_le_materiel_et_les_precisions_en_suffixe_ne_genent_pas(saisi, attendu):
    info = get_exercise_info(saisi)
    assert info is not None, saisi
    assert info["name"].startswith(attendu)


@pytest.mark.parametrize("surnom,attendu", [
    ("Leg press", "Presse à cuisses"),
    ("skull crusher", "Barre au front"),
    ("RDL", "Soulevé de terre roumain"),
    ("Glute bridge", "Hip thrust"),
    ("crossover", "Écartés poulie"),
])
def test_les_surnoms_annonces_par_la_fiche_sont_reconnus(surnom, attendu):
    """Ces noms sont déjà écrits dans le champ `name` des fiches. Les lire
    évite d'entretenir à côté une table de synonymes qui divergerait."""
    info = get_exercise_info(surnom)
    assert info is not None, surnom
    assert info["name"].startswith(attendu)


def test_un_surnom_ne_vole_jamais_la_fiche_dun_vrai_nom():
    """« Gainage (Planche) » et « Planche (Gainage) » se citent l'un l'autre.
    Sans garde-fou, ils échangeraient leurs fiches."""
    assert get_exercise_info("Gainage")["name"].startswith("Gainage")
    assert get_exercise_info("Planche")["name"].startswith("Planche")


def test_un_nom_inconnu_ne_renvoie_pas_nimporte_quoi():
    """Mieux vaut pas de fiche qu'une fiche fausse : afficher les conseils du
    squat sur un exercice inventé apprendrait un geste qui n'est pas le bon."""
    assert get_exercise_info("Zumba intergalactique") is None
    assert get_exercise_info("") is None
    assert get_exercise_info(None) is None


def test_tout_le_catalogue_se_retrouve_sans_ses_accents():
    """Le cas réel : un programme importé sans accents. Aucun exercice ne
    doit perdre sa fiche au passage."""
    import unicodedata
    perdus = []
    for nom in EXERCISES_INFO:
        sans = "".join(c for c in unicodedata.normalize("NFKD", nom)
                       if not unicodedata.combining(c))
        if get_exercise_info(sans) is None:
            perdus.append(nom)
    assert not perdus, f"{len(perdus)} exercices perdus sans accents : {perdus[:5]}"


def test_chaque_exercice_du_catalogue_garde_sa_propre_fiche():
    """Une normalisation trop large ferait converger deux exercices voisins
    vers la même fiche — « Shrug » et « Shrugs », « Gainage » et « Gainage
    latéral » — et l'un afficherait les conseils de l'autre."""
    melanges = []
    for nom in EXERCISES_INFO:
        info = get_exercise_info(nom)
        if info is not EXERCISES_INFO[nom] and info["name"] != EXERCISES_INFO[nom]["name"]:
            melanges.append(nom)
    assert not melanges, melanges


# ── Noms relevés dans un vrai programme ──────────────────────────
# Cinq exercices d'une séance réelle n'avaient ni illustration ni conseils
# d'exécution. Trois causes distinctes, aucune n'était un nom inventé :
# le singulier contre le pluriel du catalogue, l'ordre des mots inversé,
# et le vocabulaire anglais de salle.


@pytest.mark.parametrize("saisi,attendu", [
    ("ÉCARTÉ POULIE VIS À VIS HAUTE", "Écartés poulie"),   # singulier + précisions
    ("ELÉVATION LATÉRALE", "Élévations latérales"),        # singulier des deux mots
    ("TRICEPS EXTENSION", "Extensions triceps"),           # ordre inversé
    ("PEC FLY", "Écartés poulie"),                         # anglais, aucun mot commun
    ("OVERHEAD TRICEPS EXTENSION", "Extension triceps haltère"),
])
def test_les_noms_releves_dans_un_vrai_programme(saisi, attendu):
    info = get_exercise_info(saisi)
    assert info is not None, f"« {saisi} » reste sans fiche"
    assert info["name"].startswith(attendu)


@pytest.mark.parametrize("saisi,attendu", [
    ("Élévation latérale", "Élévations latérales"),
    ("Pompe", "Pompes"),
    ("Fente", "Fentes"),
    ("Traction", "Tractions"),
])
def test_le_singulier_retrouve_le_pluriel_du_catalogue(saisi, attendu):
    info = get_exercise_info(saisi)
    assert info is not None, saisi
    assert info["name"].startswith(attendu)


@pytest.mark.parametrize("anglais,attendu", [
    ("bench press", "Développé couché"),
    ("deadlift", "Soulevé de terre"),
    ("lat pulldown", "Tirage vertical"),
    ("hammer curl", "Curl marteau"),
    ("push up", "Pompes"),
])
def test_le_vocabulaire_anglais_de_salle_est_reconnu(anglais, attendu):
    """Le catalogue est en français, mais personne ne dit « écartés à la
    poulie vis-à-vis » devant sa machine."""
    info = get_exercise_info(anglais)
    assert info is not None, anglais
    assert info["name"].startswith(attendu)


def test_la_table_anglaise_ne_pointe_que_sur_des_exercices_existants():
    """Une entrée qui vise une fiche disparue ferait planter la résolution
    au lieu de retomber sur « pas de fiche »."""
    from core.exercises_data import _ANGLAIS
    fantomes = [k for k, v in _ANGLAIS.items() if v not in EXERCISES_INFO]
    assert not fantomes, fantomes


def test_la_table_anglaise_ne_recouvre_aucun_nom_francais():
    """Sinon elle détournerait un exercice qui se résolvait très bien tout
    seul, et l'erreur serait invisible."""
    from core.exercises_data import _ANGLAIS, _cle
    vrais = {_cle(n) for n in EXERCISES_INFO}
    recouvrants = [k for k in _ANGLAIS if _cle(k) in vrais]
    assert not recouvrants, recouvrants


def test_les_variantes_voisines_ne_se_confondent_pas():
    """Le rattrapage par jeu de mots est large : il ne doit pas faire
    converger deux exercices que l'utilisateur distingue."""
    assert get_exercise_info("Dips machine")["name"] != get_exercise_info("Dips")["name"]
    assert (get_exercise_info("Gainage latéral")["name"]
            != get_exercise_info("Gainage")["name"])
    assert (get_exercise_info("Élévations latérales haltères")["name"]
            != get_exercise_info("Élévations latérales")["name"])
