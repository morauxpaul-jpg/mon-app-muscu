"""Ce qu'un exercice garde d'une séance à l'autre (routes/seance_exo.py).

Retour du 14/10 : « le chrono n'enregistre pas si je le change ». La durée
touchée dans la barre ne valait que pour le repos en cours."""
from conftest import CSRF, USER_ID

COUCHE = "e_0000c0de"      # identifiant stable d'exercice (forme e_ + 8 hexa)


def _programme(fake):
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push 1": [{"name": "Développé couché", "sets": 4, "muscle": "Pecs", "rest_seconds": 90, "id": COUCHE},
                   {"name": "Écartés poulie", "sets": 3, "muscle": "Pecs", "rest_seconds": 90}],
        "_planning": {"Lundi": "Push 1"}, "_settings": {},
    }}).execute()


def _repos(client, **corps):
    return client.post("/seance/repos", json=corps, headers={"X-CSRFToken": CSRF})


def _exos(fake):
    return fake.tables["programs"][-1]["data"]["Push 1"]


def test_la_duree_choisie_est_ecrite_pour_cet_exercice(fake_db, logged_in):
    _programme(fake_db)
    r = _repos(logged_in, seance="Push 1", exo_id=COUCHE, base="Développé couché", rest_seconds=120)
    assert r.status_code == 200 and r.get_json() == {"ok": True, "rest_seconds": 120}
    assert [e["rest_seconds"] for e in _exos(fake_db)] == [120, 90]


def test_sans_identifiant_on_retrouve_l_exercice_par_son_nom(fake_db, logged_in):
    _programme(fake_db)
    _repos(logged_in, seance="Push 1", exo_id="", base="Écartés poulie", rest_seconds=60)
    assert [e["rest_seconds"] for e in _exos(fake_db)] == [90, 60]


def test_les_bornes_de_l_editeur_s_appliquent(fake_db, logged_in):
    _programme(fake_db)
    _repos(logged_in, seance="Push 1", exo_id=COUCHE, base="Développé couché", rest_seconds=900)
    assert _exos(fake_db)[0]["rest_seconds"] == 300


def test_un_exercice_ajoute_aujourd_hui_ne_touche_pas_le_programme(fake_db, logged_in):
    _programme(fake_db)
    r = _repos(logged_in, seance="Push 1", exo_id="", base="Pull-over", rest_seconds=60)
    assert r.status_code == 404
    assert [e["rest_seconds"] for e in _exos(fake_db)] == [90, 90]


def test_une_duree_illisible_est_refusee(fake_db, logged_in):
    _programme(fake_db)
    assert _repos(logged_in, seance="Push 1", base="Développé couché", rest_seconds="vite").status_code == 400


# ── Réglages de la machine (même retour : « potentiel onglet réglage de machine ») ──


def _reglages(fake):
    """Rangés dans l'état du compte depuis la v51 (audit du 18/10, m7), et
    plus dans le programme."""
    assert "_reglages_machines" not in fake.tables["programs"][-1]["data"]
    [ligne] = fake.tables["etat_compte"]
    return ligne["reglages_machines"]


def test_les_reglages_d_une_machine_sont_gardes(fake_db, logged_in):
    _programme(fake_db)
    r = logged_in.post("/seance/reglages", headers={"X-CSRFToken": CSRF}, json={
        "exo_id": COUCHE, "base": "Développé couché", "variant": "Machine",
        "texte": "  siège 4 ·   goupille 7 "})
    assert r.get_json() == {"ok": True, "texte": "siège 4 · goupille 7"}
    entree = _reglages(fake_db)[COUCHE + "~Machine"]
    assert entree["texte"] == "siège 4 · goupille 7" and entree["maj"]


def test_un_texte_vide_efface_les_reglages(fake_db, logged_in):
    _programme(fake_db)
    corps = {"exo_id": COUCHE, "base": "Développé couché", "variant": "Machine"}
    logged_in.post("/seance/reglages", headers={"X-CSRFToken": CSRF}, json={**corps, "texte": "siège 4"})
    logged_in.post("/seance/reglages", headers={"X-CSRFToken": CSRF}, json={**corps, "texte": ""})
    assert _reglages(fake_db) == {}


def test_la_file_hors_ligne_peut_rejouer_les_reglages(fake_db, logged_in):
    """Au sous-sol, l'envoi part en formulaire quand le réseau revient."""
    _programme(fake_db)
    r = logged_in.post("/seance/reglages", data={
        "_csrf": CSRF, "exo_id": "", "base": "Écartés poulie", "variant": "Standard", "texte": "poulie au cran 3"})
    assert r.status_code == 200
    assert _reglages(fake_db)["n:écartés poulie"]["texte"] == "poulie au cran 3"


def test_les_reglages_survivent_a_un_changement_de_programme():
    from core.db_programme import replace_program_body
    ancien = {"Push 1": [], "_reglages_machines": {COUCHE: {"texte": "siège 4", "maj": "2026-10-15"}}}
    nouveau = replace_program_body(ancien, {"Haut": [{"name": "Tractions", "sets": 3}]})
    assert nouveau["_reglages_machines"] == ancien["_reglages_machines"]


def test_la_carte_affiche_les_reglages(fake_db, logged_in):
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push 1": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs", "id": COUCHE}],
        "_planning": {"Lundi": "Push 1"}, "_settings": {},
        "_reglages_machines": {COUCHE: {"texte": "banc cran 2", "maj": "2026-10-15"}},
    }}).execute()
    html = logged_in.get("/seance", query_string={"mode": "prefaite", "name": "Push 1"}).get_data(as_text=True)
    assert "banc cran 2" in html
    assert 'x-if="reglages &amp;&amp; !editReglages"' in html or 'x-if="reglages && !editReglages"' in html


def test_90_s_inscrites_ne_passent_pas_avant_la_barre(fake_db, logged_in):
    """Retour du 23/10 : « le chrono ne garde pas entre deux exos ». Chaque
    enregistrement du programme inscrit 90 s sur tous les exercices sans
    durée : comptées comme prescrites, elles passaient avant la durée
    choisie dans la barre, et celle-ci ne valait plus que pour un exercice."""
    import re
    _programme(fake_db)
    _exos(fake_db)[1]["rest_seconds"] = 180          # une vraie prescription
    html = logged_in.get("/seance?mode=prefaite&name=Push 1").get_data(as_text=True)
    # Une carte par exercice, dans l'ordre du programme.
    assert re.findall(r'"rest_prescrit":\s*(true|false)', html) == ["false", "true"]
