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
