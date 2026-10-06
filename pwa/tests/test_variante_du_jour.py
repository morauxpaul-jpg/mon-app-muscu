"""Échanger un exercice contre une variante, pour aujourd'hui seulement.

« Mon programme dit curl incliné, mais aujourd'hui j'ai envie de le faire à
la poulie » : sans ce geste il fallait retirer l'exercice, rouvrir le
formulaire d'ajout, retaper un nom, choisir un muscle, remettre le nombre de
séries — pour un changement d'une séance.

La règle qui tient tout : le PROGRAMME NE BOUGE PAS. La semaine suivante,
l'exercice d'origine revient sans que personne ait à y penser.
"""
import datetime as dt
import re

import pytest

from conftest import USER_ID, CSRF
from core.exercises_data import variantes

MONDAY = dt.date(2026, 9, 14)
JOUR = MONDAY.isoformat()


@pytest.fixture()
def programme(fake_db):
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [
            {"name": "Curl incliné haltères", "sets": 4, "muscle": "Biceps"},
            {"name": "Développé couché", "sets": 3, "muscle": "Pectoraux"},
        ],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": MONDAY.isoformat(),
    }}).execute()
    return fake_db


def _seance(client, date=JOUR):
    return client.get(
        f"/seance?mode=prefaite&name=Push&date={date}").get_data(as_text=True)


def _exos_affiches(html):
    """Les exercices que porte la séance, pas ceux cités dans la page.

    Chercher un nom dans tout le HTML ne prouve rien : le panneau de
    variantes énumère les remplaçants possibles, donc « Curl barre » y
    figure même quand il n'est pas au programme du jour. Seul l'attribut
    que porte chaque carte fait foi.
    """
    return re.findall(r'data-exo-base="([^"]+)"', html)


def _echanger(client, origine, vers):
    return client.post("/seance/substitute", data={
        "mode": "prefaite", "name": "Push", "seance_name": "Push",
        "date": JOUR, "exo_name": origine, "vers": vers,
    }, headers={"X-CSRFToken": CSRF}, follow_redirects=True)


def _prog(fake_db):
    return fake_db.table("programs").select("*").eq(
        "user_id", USER_ID).execute().data[0]["data"]


# ── Le geste ─────────────────────────────────────────────────────


def test_lexercice_echange_apparait_a_la_place(programme, logged_in):
    _echanger(logged_in, "Curl incliné haltères", "Curl marteau")
    html = _seance(logged_in)
    assert "Curl marteau" in _exos_affiches(html)
    assert "Curl incliné haltères" not in _exos_affiches(html)
    assert "remplace Curl incliné haltères" in html


def test_le_creneau_garde_ses_series(programme, logged_in):
    """C'est tout l'intérêt : on ne resaisit rien. Le curl incliné était
    prévu en 4 séries, la variante l'est aussi."""
    _echanger(logged_in, "Curl incliné haltères", "Curl marteau")
    html = _seance(logged_in)
    assert "4 séries" in html


def test_les_autres_exercices_ne_bougent_pas(programme, logged_in):
    _echanger(logged_in, "Curl incliné haltères", "Curl marteau")
    assert "Développé couché" in _exos_affiches(_seance(logged_in))


# ── La règle : le programme ne bouge pas ─────────────────────────


def test_le_programme_nest_pas_reecrit(programme, logged_in):
    """Si l'échange touchait le programme, il faudrait penser à le remettre
    — et « de temps en temps une variante » deviendrait un piège."""
    _echanger(logged_in, "Curl incliné haltères", "Curl marteau")
    noms = [e["name"] for e in _prog(programme)["Push"]]
    assert noms == ["Curl incliné haltères", "Développé couché"]


def test_un_autre_jour_retrouve_lexercice_dorigine(programme, logged_in):
    _echanger(logged_in, "Curl incliné haltères", "Curl marteau")
    autre = (MONDAY + dt.timedelta(days=7)).isoformat()
    affiches = _exos_affiches(_seance(logged_in, autre))
    assert "Curl incliné haltères" in affiches
    assert "Curl marteau" not in affiches


# ── Revenir en arrière ───────────────────────────────────────────


def test_on_peut_revenir_a_lexercice_dorigine(programme, logged_in):
    _echanger(logged_in, "Curl incliné haltères", "Curl marteau")
    _echanger(logged_in, "Curl incliné haltères", "")
    html = _seance(logged_in)
    assert "Curl incliné haltères" in _exos_affiches(html)
    assert "remplace Curl" not in html


def _cibles_des_formulaires(html):
    """Le nom que chaque formulaire d'échange enverra réellement.

    On le lit dans la page plutôt que de poster à la main : c'est ce champ
    caché qui décide, et un test qui l'ignore laisserait passer un gabarit
    qui poste le mauvais nom.
    """
    cibles = []
    for bloc in html.split('action="/seance/substitute"')[1:]:
        trouve = re.search(r'name="exo_name" value="([^"]*)"', bloc)
        if trouve:
            cibles.append(trouve.group(1))
    return cibles


def test_le_formulaire_vise_le_nom_du_programme_pas_celui_affiche(
        programme, logged_in):
    """Après un premier échange, la carte affiche « Curl barre » mais le
    programme, lui, contient toujours « Curl incliné haltères ». Si le
    formulaire postait le nom affiché, le deuxième échange chercherait dans
    le programme un exercice qui n'y est pas — et ne ferait rien."""
    _echanger(logged_in, "Curl incliné haltères", "Curl marteau")
    cibles = _cibles_des_formulaires(_seance(logged_in))
    assert "Curl incliné haltères" in cibles, cibles
    assert "Curl marteau" not in cibles, cibles


def test_un_deuxieme_echange_part_toujours_de_loriginal(programme, logged_in):
    _echanger(logged_in, "Curl incliné haltères", "Curl marteau")
    _echanger(logged_in, "Curl incliné haltères", "Curl biceps")
    affiches = _exos_affiches(_seance(logged_in))
    assert "Curl biceps" in affiches
    assert "Curl marteau" not in affiches


def test_echanger_un_exercice_contre_lui_meme_neffface_le_calque(programme, logged_in):
    """Sinon le blob programme se remplit d'échanges qui ne font rien."""
    _echanger(logged_in, "Curl incliné haltères", "Curl incliné haltères")
    assert "_substituts" not in _prog(programme) or not _prog(programme)["_substituts"]


# ── Hygiène du blob programme ────────────────────────────────────


def test_le_calque_est_efface_en_fin_de_seance(programme, logged_in):
    """Comme les exos ajoutés à la volée : l'échange ne vaut que pour la
    séance du jour (table `calques_seance`, v46)."""
    _echanger(logged_in, "Curl incliné haltères", "Curl marteau")
    assert programme.tables["calques_seance"]
    logged_in.post("/seance/finish", data={
        "mode": "prefaite", "name": "Push", "seance_name": "Push", "date": JOUR,
    }, headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    assert not programme.tables["calques_seance"]
    assert not (_prog(programme).get("_substituts") or {})


# ── Les propositions ─────────────────────────────────────────────


def _tous(v):
    return [x["nom"] for x in v["mouvement"] + v["muscle"]]


def test_les_variantes_proposees_travaillent_le_meme_muscle():
    from core.exercises_data import variantes, famille_musculaire, EXERCISES_INFO
    for depart in ("Curl incliné haltères", "Développé couché", "Squat"):
        attendu = famille_musculaire(EXERCISES_INFO[depart]["muscles"][0])
        for nom in _tous(variantes(depart)):
            obtenu = famille_musculaire(EXERCISES_INFO[nom]["muscles"][0])
            assert obtenu == attendu, f"{depart} propose {nom} ({obtenu})"


def test_un_exercice_ne_se_propose_pas_lui_meme():
    from core.exercises_data import variantes
    assert "Curl marteau" not in _tous(variantes("Curl marteau"))


def test_le_premier_rang_ne_contient_que_le_meme_geste():
    """Le défaut relevé à l'usage : on proposait TOUS les exercices du
    groupe musculaire. Ce qu'on veut, c'est le même mouvement au matériel
    près — les extensions triceps à la barre, à la poulie, à la corde."""
    from core.exercises_data import variantes, famille_geste
    for depart in ("Extensions triceps", "Curl incliné haltères",
                   "Développé couché"):
        attendu = famille_geste(depart)
        for v in variantes(depart)["mouvement"]:
            assert famille_geste(v["nom"]) == attendu,                 f"{depart} propose {v['nom']} au premier rang"


def test_le_premier_rang_reste_court():
    """Une liste qu'on parcourt du regard, pas un deuxième formulaire."""
    from core.exercises_data import variantes, EXERCISES_INFO
    for nom in EXERCISES_INFO:
        assert len(variantes(nom)["mouvement"]) <= 6, nom


def test_le_developpe_couche_ne_propose_pas_un_developpe_depaules():
    """Les deux s'appellent « développé » et se ressemblent sur le papier.
    C'est le muscle qui les sépare, pas le nom."""
    propositions = _tous(variantes("Développé couché"))
    assert "Développé militaire" not in propositions
    assert "Développé haltères assis" not in propositions


def test_le_tirage_vertical_ne_propose_pas_un_tirage_horizontal():
    """Tous deux tirent le dos, mais ce n'est pas le même mouvement."""
    premier = [v["nom"] for v in variantes("Tirage vertical")["mouvement"]]
    assert "Tirage horizontal poulie" not in premier


def test_un_exercice_inconnu_ne_propose_rien(programme, logged_in):
    """Mieux vaut pas de bouton qu'un bouton qui propose n'importe quoi."""
    from core.exercises_data import variantes
    assert _tous(variantes("Zumba intergalactique")) == []
