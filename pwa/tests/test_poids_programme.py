"""La page /programme ne doit plus porter ce qu'on ne regarde pas.

Elle pesait **313 ko**. Le détail des vingt programmes du catalogue — chaque
séance, chaque exercice, chaque nombre de séries — y était écrit côté serveur,
caché derrière un `x-show` qu'on ouvre pour un programme, parfois. Cela faisait
**88 ko, 28 % de la page**, en double du JSON `#catalog-data` qui portait déjà
exactement les mêmes données et que la page chargeait de toute façon.

Le détail est maintenant rendu à l'ouverture, depuis ce JSON. Ces tests
empêchent qu'il revienne, et que la page regrossisse.
"""
import datetime as dt
import re

import pytest

from conftest import USER_ID

PLAFOND_KO = 260
LUNDI = dt.date(2026, 9, 14)


@pytest.fixture()
def compte_charge(fake_db):
    """Cinq séances de huit exercices : un programme réaliste et copieux."""
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    seances = {nom: [{"name": f"Exercice {i}", "sets": 4, "muscle": "Pecs",
                      "reps": "8-12"} for i in range(8)]
               for nom in ("Push 1", "Pull 1", "Leg", "Push 2", "Pull 2")}
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        **seances,
        "_planning": {"Lundi": "Push 1", "Mardi": "Pull 1", "Mercredi": "Leg",
                      "Jeudi": "Push 2", "Vendredi": "Pull 2"},
        "_settings": {}, "_started_at": LUNDI.isoformat()}}).execute()
    return fake_db


def _page(client):
    r = client.get("/programme")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_la_page_reste_sous_le_plafond(compte_charge, logged_in):
    html = _page(logged_in)
    ko = len(html.encode("utf-8")) / 1024
    assert ko <= PLAFOND_KO, (
        f"/programme pèse {ko:.0f} ko (plafond {PLAFOND_KO}) — "
        "quelque chose y est rendu qu'on pourrait charger à la demande")


def test_le_detail_du_catalogue_nest_pas_rendu_cote_serveur(compte_charge, logged_in):
    """Les exercices des programmes tout faits ne sont pas dans le HTML.

    Ils arrivent par `#catalog-data`, que la page charge déjà pour le
    sélecteur « Ajouter une séance depuis le catalogue ».
    """
    html = _page(logged_in)
    corps = re.sub(r'<script id="catalog-data"[\s\S]*?</script>', "", html)
    lignes_exo = re.findall(r'<li><span[^>]*>[^<]+</span>\s*<span[^>]*>· \d+ séries', corps)
    assert lignes_exo == [], (
        f"{len(lignes_exo)} exercices de catalogue rendus dans le HTML")


def test_le_catalogue_nest_serialise_quune_fois(compte_charge, logged_in):
    """Une seule copie des données : le JSON. Pas deux, pas trois."""
    html = _page(logged_in)
    assert html.count('id="catalog-data"') == 1
    # Le JSON porte bien le détail — c'est lui qui remplace le HTML retiré.
    bloc = re.search(r'<script id="catalog-data"[^>]*>([\s\S]*?)</script>', html)
    assert bloc and '"seances_preview"' in bloc.group(1)


def test_les_cartes_du_catalogue_restent_visibles(compte_charge, logged_in):
    """On allège le détail, pas la liste : chaque programme garde sa carte,
    son titre et son bouton. Sinon la page serait légère et vide."""
    html = _page(logged_in)
    assert html.count('class="card catalog-card"') >= 10
    assert html.count("Détail des séances") >= 10
    assert "catalog-detail" in html


def test_le_gabarit_nitere_plus_sur_les_seances_du_catalogue():
    """Garde-fou de source : la boucle Jinja ne doit pas revenir.

    Le test de poids l'attraperait, mais seulement une fois la page assez
    grosse ; celui-ci nomme la cause.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "templates" / "programme.html"
           ).read_text(encoding="utf-8")
    assert "{% for sp in p.seances_preview %}" not in src
    assert 'x-for="sp in detailSeances(' in src
