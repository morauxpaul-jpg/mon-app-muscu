"""Ramener l'historique sur les noms du catalogue, sans rien casser.

En refaisant son programme avec les noms de l'app, tout l'historique écrit
« à l'ancienne » se retrouve orphelin : plus de records, plus de « dernière
fois », progression illisible. Cet outil le rebranche.

Un renommage d'historique ne s'annule pas. D'où la discipline : proposer,
montrer ce qui est en jeu, et n'appliquer que ce qui a été coché.
"""
import re

import pytest

from conftest import USER_ID, CSRF


def _serie(exercice, date="2026-09-14", reps=10, poids=50.0):
    return {"user_id": USER_ID, "date": date, "semaine": "2026-W38",
            "seance": "Push", "exercice": exercice, "muscle": "Pecs",
            "series": 1, "reps": reps, "poids": poids}


@pytest.fixture()
def historique(fake_db):
    for nom, n in (("developpe couche", 3), ("TRICEPS EXTENSION", 2),
                   ("Développé couché", 1), ("Mon exercice à moi", 4),
                   ("ÉCARTÉ POULIE VIS À VIS HAUTE", 2)):
        for i in range(n):
            fake_db.table("history").insert(_serie(nom)).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
    }}).execute()
    return fake_db


def _propositions(html):
    """Les couples proposés, lus dans la page telle qu'elle est rendue."""
    bloc = html.split('action="/gestion/exercice/aligner"')
    if len(bloc) < 2:
        return []
    return re.findall(r'name="aligner" value="([^"]+)"', bloc[1])


def _coches(html):
    bloc = html.split('action="/gestion/exercice/aligner"')[1]
    return re.findall(r'name="aligner" value="([^"]+)"\s*\n?\s*checked', bloc)


def _noms_en_base(fake_db):
    lignes = fake_db.table("history").select("*").eq("user_id", USER_ID).execute().data
    return sorted({r["exercice"] for r in lignes})


# ── Ce qui est proposé ───────────────────────────────────────────


def test_les_noms_non_reconnus_sont_proposes(historique, logged_in):
    props = _propositions(logged_in.get("/gestion").get_data(as_text=True))
    assert "developpe couche" in props
    assert "TRICEPS EXTENSION" in props


def test_un_nom_deja_bon_nest_pas_propose(historique, logged_in):
    """Sinon la liste se remplit de renommages qui ne font rien, et on finit
    par tout cocher sans regarder."""
    assert "Développé couché" not in _propositions(
        logged_in.get("/gestion").get_data(as_text=True))


def test_un_exercice_maison_est_laisse_tranquille(historique, logged_in):
    """Tout le monde a ses exercices à lui. Ils doivent survivre."""
    assert "Mon exercice à moi" not in _propositions(
        logged_in.get("/gestion").get_data(as_text=True))


def test_seuls_les_rapprochements_surs_sont_coches_davance(historique, logged_in):
    """« ÉCARTÉ POULIE VIS À VIS HAUTE » se résout par sous-ensemble : les
    mots en trop peuvent changer l'exercice. Proposé, mais décoché."""
    html = logged_in.get("/gestion").get_data(as_text=True)
    assert "developpe couche" in _coches(html)
    assert "ÉCARTÉ POULIE VIS À VIS HAUTE" not in _coches(html)


def test_la_page_annonce_ce_qui_fusionne(historique, logged_in):
    """« developpe couche » va rejoindre « Développé couché », qui existe
    déjà : deux historiques n'en feront plus qu'un. Jamais anodin."""
    html = logged_in.get("/gestion").get_data(as_text=True)
    assert "fusionne" in html


# ── Ce qui est appliqué ──────────────────────────────────────────


def test_seuls_les_exercices_coches_sont_renommes(historique, logged_in):
    logged_in.post("/gestion/exercice/aligner",
                   data={"aligner": ["developpe couche"]},
                   headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    noms = _noms_en_base(historique)
    assert "developpe couche" not in noms
    assert "TRICEPS EXTENSION" in noms, "un nom non coché a été renommé"


def test_le_renommage_regroupe_bien_lhistorique(historique, logged_in):
    logged_in.post("/gestion/exercice/aligner",
                   data={"aligner": ["developpe couche"]},
                   headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    lignes = historique.table("history").select("*").eq(
        "user_id", USER_ID).execute().data
    couche = [r for r in lignes if r["exercice"] == "Développé couché"]
    assert len(couche) == 4, "les 3 anciennes séries n'ont pas rejoint la 1"


def test_rien_coche_ne_touche_rien(historique, logged_in):
    avant = _noms_en_base(historique)
    logged_in.post("/gestion/exercice/aligner", data={},
                   headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    assert _noms_en_base(historique) == avant


def test_un_nom_trafique_dans_le_formulaire_est_ignore(historique, logged_in):
    """La proposition est recalculée côté serveur : le formulaire choisit
    QUOI appliquer, jamais VERS QUOI. Sinon un champ modifié renommerait un
    exercice vers n'importe quoi, sans retour possible."""
    logged_in.post("/gestion/exercice/aligner",
                   data={"aligner": ["Mon exercice à moi"]},
                   headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    assert "Mon exercice à moi" in _noms_en_base(historique)


def test_rejouer_le_meme_alignement_ne_change_plus_rien(historique, logged_in):
    """Une migration doit pouvoir être relancée sans dégâts — double clic,
    retour arrière du navigateur, réseau qui rejoue la requête."""
    choix = ["developpe couche", "TRICEPS EXTENSION"]
    logged_in.post("/gestion/exercice/aligner", data={"aligner": choix},
                   headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    apres_un_tour = _noms_en_base(historique)
    logged_in.post("/gestion/exercice/aligner", data={"aligner": choix},
                   headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    assert _noms_en_base(historique) == apres_un_tour


def test_ce_qui_na_pas_ete_coche_reste_proposable(historique, logged_in):
    """On aligne en plusieurs fois : ce qu'on a laissé de côté doit encore
    être là au tour suivant."""
    logged_in.post("/gestion/exercice/aligner",
                   data={"aligner": ["developpe couche"]},
                   headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    props = _propositions(logged_in.get("/gestion").get_data(as_text=True))
    assert "TRICEPS EXTENSION" in props
    assert "developpe couche" not in props
