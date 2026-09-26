"""Illustrations d'exercices — branchées par convention de nom.

Déposer `arnold-press.webp` dans `static/img/exercises/` suffit à illustrer
« Arnold press » : aucune ligne à éditer, aucune liste à tenir à jour. Une
liste manuelle de 87 entrées finit toujours par mentir — c'est déjà ce qui
s'était passé avec les 18 dessins au trait, recyclés sur 87 fiches
(`row.svg` servait à 11 exercices, dont les shrugs).
"""
import datetime as dt
import json

import pytest

from conftest import USER_ID, CSRF
from core import exercises_data
from core.exercises_data import get_exercise_info, illustration_slug

MONDAY = dt.date(2026, 9, 14)


@pytest.fixture()
def illustrations(monkeypatch):
    """Simule la présence de deux fichiers, sans toucher au dépôt."""
    monkeypatch.setattr(exercises_data, "_ILLUSTRATIONS",
                        {"arnold-press", "developpe-couche"})


# ── Convention de nom ────────────────────────────────────────────


def test_le_nom_de_fichier_se_deduit_du_nom_de_lexercice():
    assert illustration_slug("Développé couché") == "developpe-couche"
    assert illustration_slug("Arnold press") == "arnold-press"
    assert illustration_slug("Élévations latérales") == "elevations-laterales"
    assert illustration_slug("Rowing barre (pronation)") == "rowing-barre-pronation"


# ── Résolution ───────────────────────────────────────────────────


def test_lillustration_remplace_le_dessin_quand_elle_existe(illustrations):
    info = get_exercise_info("Arnold press")
    assert info["image"] == "arnold-press.webp"
    assert info["illustration"] is True


def test_sans_illustration_le_dessin_au_trait_reste(illustrations):
    """87 exercices ne s'illustrent pas en un jour : l'un ne doit pas
    empêcher l'autre d'être affiché."""
    info = get_exercise_info("Squat")
    assert info["image"].endswith(".svg")
    assert info.get("illustration") is not True


def test_une_variante_herite_de_lillustration_de_base(illustrations):
    """« Développé couché (Haltères) » retombe sur la fiche « Développé
    couché » : l'illustration doit suivre le même chemin."""
    info = get_exercise_info("Développé couché (Haltères)")
    assert info["image"] == "developpe-couche.webp"


def test_la_fiche_partagee_nest_jamais_modifiee(illustrations):
    """`EXERCISES_INFO` est un dictionnaire de module : le résoudre en place
    contaminerait toutes les requêtes suivantes."""
    get_exercise_info("Arnold press")
    assert exercises_data.EXERCISES_INFO["Arnold press"]["image"].endswith(".svg")


def test_un_dossier_absent_ne_casse_rien(monkeypatch):
    monkeypatch.setattr(exercises_data, "_DOSSIER_ART", "/chemin/qui/n/existe/pas")
    assert exercises_data._illustrations_presentes() == set()


# ── Affichage ────────────────────────────────────────────────────


def test_lillustration_apparait_sur_la_carte_pas_seulement_dans_la_fiche(
        fake_db, logged_in, illustrations):
    """Hevy la montre pendant la séance. Cachée derrière le « ? », elle ne
    sert qu'à ceux qui savent déjà qu'elle existe."""
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Arnold press", "sets": 3, "muscle": "Épaules"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": MONDAY.isoformat(),
    }}).execute()
    html = logged_in.get(
        f"/seance?mode=prefaite&name=Push&date={MONDAY.isoformat()}"
    ).get_data(as_text=True)
    assert 'class="exo-vignette"' in html, "la vignette manque sur la carte"
    assert "/static/img/exercises/arnold-press.webp" in html


def test_aucune_vignette_sans_illustration(fake_db, logged_in, illustrations):
    """Un dessin au trait de 80 px agrandi sur la carte serait laid : tant
    qu'il n'y a pas d'illustration, la carte reste telle quelle."""
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Squat", "sets": 3, "muscle": "Quadriceps"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": MONDAY.isoformat(),
    }}).execute()
    html = logged_in.get(
        f"/seance?mode=prefaite&name=Push&date={MONDAY.isoformat()}"
    ).get_data(as_text=True)
    # La règle CSS est toujours dans la page ; c'est l'ÉLÉMENT qui ne doit
    # pas y être.
    assert 'class="exo-vignette"' not in html


# ── Poids des fichiers ───────────────────────────────────────────


def test_les_illustrations_livrees_restent_legeres():
    """Une image générée pèse 1,5 Mo. Telles quelles, 87 feraient 130 Mo et
    la séance mettrait une minute à s'afficher en 4G."""
    import glob
    import io
    import os
    lourdes = []
    for f in glob.glob("static/img/exercises/*.webp"):
        ko = os.path.getsize(f) // 1024
        if ko > 60:
            lourdes.append(f"{os.path.basename(f)} : {ko} ko")
    assert not lourdes, lourdes


# ── Prompts de génération ────────────────────────────────────────
# Les illustrations sont générées à partir de `tools/exercise_prompts.json`.
# Un prompt faux coûte de l'argent ET apprend un mauvais geste : ces
# vérifications valent d'être automatiques.


def _prompts():
    import io
    import json
    import os
    import sys
    sys.path.insert(0, "tools")
    from build_exercise_prompts import construire
    return {e["nom"]: e for e in construire()}


def test_le_prompt_decrit_le_mouvement_pas_seulement_la_position_de_depart():
    """Le bug qui a produit un développé couché au lieu d'une barre au front.

    La description de « Barre au front » commence par « Allongé sur un banc,
    barre tenue à bout de bras au-dessus de la poitrine » — c'est la position
    de départ, et c'est mot pour mot celle du développé couché. Le prompt ne
    gardait que cette première phrase : le modèle a dessiné un développé
    couché, red flag invisible tant qu'on ne regarde pas l'image.
    """
    p = _prompts()["Barre au front"]["prompt"].lower()
    assert "forehead" in p or "vers le front" in p, \
        "le prompt ne dit pas où va la barre : bras tendus au-dessus de " \
        "la poitrine, c'est un développé couché — et c'est ce qui est sorti"


def test_aucune_description_nest_tronquee_en_chemin():
    """Généralise le cas « barre au front » aux 87 fiches.

    Chaque fiche décrit le départ PUIS le mouvement. Ne garder qu'un bout,
    c'est laisser le modèle inventer la moitié du geste — et une illustration
    fausse apprend un mauvais mouvement à celui qui la regarde pendant sa
    série.
    """
    from build_exercise_prompts import GESTES
    from core.exercises_data import EXERCISES_INFO
    tronquees = []
    for nom, entree in _prompts().items():
        if nom in GESTES:          # geste écrit à la main, la fiche ne sert plus
            continue
        description = " ".join((EXERCISES_INFO[nom].get("description") or "").split())
        if description and description not in entree["prompt"]:
            tronquees.append(nom)
    assert not tronquees, f"description coupée dans le prompt : {tronquees}"


def test_les_fiches_qui_ne_decrivent_aucun_geste_en_recoivent_un():
    """« Même principe que le curl classique mais avec une barre droite ou EZ.
    La barre permet de charger plus lourd. » — rien, dans ces trois phrases,
    ne dit à quoi ressemble un curl. Le modèle avait dessiné les bras le long
    du corps, épaules en rouge.
    """
    p = _prompts()["Curl barre"]["prompt"].lower()
    assert "barbell" in p and "elbows" in p, \
        "le geste du curl n'est décrit nulle part dans le prompt"


def test_aucun_prompt_ne_demande_de_muscle_en_couleur():
    """La fiche affiche déjà une carte anatomique juste, calculée à partir
    des muscles déclarés. Le modèle d'image, lui, recopiait la zone rouge de
    l'image de référence : tous les exercices ressortaient avec les épaules
    en rouge, curl compris. Deux sources pour la même information, dont une
    fausse."""
    fautifs = [n for n, e in _prompts().items()
               if "highlight the" in e["prompt"].lower()
               or "in soft red" in e["prompt"].lower()]
    assert not fautifs, fautifs


def test_le_nom_de_fichier_du_prompt_est_celui_que_lapp_ira_chercher():
    """Les deux viennent de `illustration_slug` : un fichier généré sous un
    autre nom ne serait jamais affiché, sans aucune erreur nulle part."""
    for nom, entree in _prompts().items():
        assert entree["fichier"] == illustration_slug(nom) + ".png"
