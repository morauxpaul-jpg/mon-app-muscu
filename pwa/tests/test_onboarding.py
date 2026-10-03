"""Onboarding — collecte du gabarit, et ce qui en dépend.

Trois écrans comparent l'utilisateur à lui-même plutôt qu'à une moyenne :
les standards de force (`core/strength.py`), le calcul des calories, la
courbe de poids. Tous ont besoin du poids de corps, et pendant des mois
aucun formulaire ne le demandait — le calcul existait sans jamais servir.
"""
import time

import pytest

from conftest import USER_ID, CSRF
from core import strength


@pytest.fixture()
def nouveau(client):
    """Compte authentifié qui n'a pas encore passé l'onboarding."""
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=False,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time(), _csrf=CSRF)
    return client


def _inscription(client, **extra):
    data = {
        "_csrf": CSRF, "prenom": "Alex", "age": "30", "sexe": "homme",
        "poids_kg": "72.5", "taille_cm": "178", "niveau": "débutant",
        "frequence": "3", "objectif": "prise de masse", "equipement": "salle",
        "programme_id": "", "equipment_details": "[]",
    }
    data.update(extra)
    return client.post("/onboarding/submit", data=data)


# ── Le formulaire demande le gabarit ─────────────────────────────


def test_le_formulaire_demande_le_poids_et_la_taille(fake_db, nouveau):
    html = nouveau.get("/onboarding").get_data(as_text=True)
    assert 'id="onb-poids"' in html
    assert 'id="onb-taille"' in html


def test_le_formulaire_envoye_contient_tout_ce_que_la_route_lit(fake_db, nouveau):
    """Le navigateur ne poste pas les champs visibles : il poste le formulaire
    caché `onb-form`. Poids et taille y manquaient — la route les attendait,
    les tests les lui donnaient directement, et en vrai ils partaient à la
    poubelle. On compare donc le formulaire RENDU à ce que la route lit."""
    import re
    html = nouveau.get("/onboarding").get_data(as_text=True)
    bloc = re.search(r'<form id="onb-form".*?</form>', html, re.S).group(0)
    envoyes = set(re.findall(r'name="([^"]+)"', bloc))
    attendus = {
        "_csrf", "prenom", "age", "sexe", "poids_kg", "taille_cm", "niveau",
        "frequence", "objectif", "equipement", "programme_id", "equipment_details",
    }
    assert attendus <= envoyes, f"absents du formulaire envoyé : {attendus - envoyes}"


def test_on_ne_peut_pas_passer_letape_sans_le_gabarit(fake_db, nouveau):
    """Facultatif, personne ne le remplit, et les trois écrans restent vides."""
    html = nouveau.get("/onboarding").get_data(as_text=True)
    assert "form.poids_kg >= 30" in html
    assert "form.taille_cm >= 100" in html


# ── Ce qui est enregistré ────────────────────────────────────────


def test_le_gabarit_atterrit_dans_le_profil(fake_db, nouveau):
    _inscription(nouveau)
    profil = fake_db.tables["profiles"][0]
    assert profil["poids_kg"] == 72.5
    assert profil["taille_cm"] == 178.0
    assert profil["age"] == 30
    assert profil["sexe"] == "H", "profiles.sexe attend H/F, pas « homme »"


def test_la_courbe_de_poids_demarre_avec_un_point(fake_db, nouveau):
    """Sinon le premier écran de suivi du poids est vide le jour de
    l'inscription, alors que la donnée vient d'être saisie."""
    _inscription(nouveau)
    pesees = fake_db.tables.get("body_weight", [])
    assert len(pesees) == 1
    assert pesees[0]["poids_kg"] == 72.5


def test_un_gabarit_hors_bornes_est_ignore_plutot_que_stocke(fake_db, nouveau):
    """Mieux vaut absent qu'aberrant : `strength.py` retombe alors sur ses
    seuils absolus au lieu de calculer des ratios sur 900 kg."""
    _inscription(nouveau, poids_kg="900", taille_cm="12")
    profil = fake_db.tables["profiles"][0]
    assert "poids_kg" not in profil
    assert "taille_cm" not in profil
    assert fake_db.tables.get("body_weight", []) == []


def test_une_virgule_decimale_est_acceptee(fake_db, nouveau):
    """Le clavier numérique d'Android produit une virgule en français."""
    _inscription(nouveau, poids_kg="72,5")
    assert fake_db.tables["profiles"][0]["poids_kg"] == 72.5


def test_le_sexe_autre_ne_corrompt_pas_le_profil(fake_db, nouveau):
    _inscription(nouveau, sexe="autre")
    profil = fake_db.tables["profiles"][0]
    assert profil.get("sexe") in (None, ""), profil.get("sexe")
    assert profil["poids_kg"] == 72.5, "le reste du gabarit passe quand même"


def test_refaire_lonboarding_repropose_le_gabarit_connu(fake_db, nouveau):
    """Il vit dans `profiles`, pas dans `onboarding` : sans rapatriement,
    l'utilisateur devait le retaper."""
    _inscription(nouveau)
    import core.db as core_db
    core_db._data_cache.clear()
    html = nouveau.get("/onboarding").get_data(as_text=True)
    assert "72.5" in html and "178" in html


# ── Ce que le gabarit débloque ───────────────────────────────────


def test_les_standards_de_force_suivent_le_poids_de_corps(fake_db, nouveau):
    """C'est la raison d'être de la collecte : 60 kg au développé ne veut pas
    dire la même chose à 55 kg qu'à 95 kg."""
    leger = strength.standard_for("Pecs", poids_kg=55, sexe="H")
    lourd = strength.standard_for("Pecs", poids_kg=95, sexe="H")
    assert lourd > leger

    inconnu = strength.standard_for("Pecs", poids_kg=None, sexe="H")
    assert inconnu == strength.standard_for("Pecs", poids_kg=0, sexe="H"), \
        "sans poids, on doit retomber sur le seuil absolu, pas sur un ratio"


# ── Refaire l'onboarding ne détruit rien (audit du 03/10, I6) ──────────


def _deux_dossiers(fake):
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "Maison A": [{"name": "Pompes", "sets": 3, "muscle": "Pecs"}],
        "_programmes": [{"id": "p1", "name": "Salle"}, {"id": "p2", "name": "Maison"}],
        "_seance_prog": {"Push": "p1", "Maison A": "p2"},
        "_planning": {"Lundi": "Push", "Jeudi": "Maison A"},
        "_badges": ["first_session"],
    }}).execute()


def test_refaire_lonboarding_garde_les_autres_programmes(fake_db, nouveau):
    """« Refaire l'onboarding » puis choisir un programme remplaçait TOUT le
    corps : séances et dossiers des autres programmes disparaissaient."""
    _deux_dossiers(fake_db)
    _inscription(nouveau, programme_id="fb_deb_3j")
    data = fake_db.tables["programs"][0]["data"]
    seances = [k for k in data if not k.startswith("_")]
    assert "Full Body A" in seances and "Full Body B" in seances
    # Rien n'est retiré : les deux anciens dossiers et leurs séances restent,
    # le nouveau programme prend le planning.
    noms = [p["name"] for p in data["_programmes"]]
    assert noms == ["Salle", "Maison", "Full Body Débutant — Salle"]
    assert "Push" in seances and "Maison A" in seances
    assert data["_seance_prog"]["Push"] == "p1" and data["_seance_prog"]["Maison A"] == "p2"
    assert data["_planning"]["Lundi"] == "Full Body A"
    assert "Push" not in data["_planning"].values()
    assert data["_badges"] == ["first_session"]
    assert data["_origin"] == "fb_deb_3j"


def test_premier_onboarding_cree_un_programme_nomme(fake_db, nouveau):
    _inscription(nouveau, programme_id="fb_deb_3j")
    data = fake_db.tables["programs"][0]["data"]
    assert [p["name"] for p in data["_programmes"]] == ["Full Body Débutant — Salle"]
    assert data["_planning"]["Lundi"] == "Full Body A"
    assert data.get("_started_at")
