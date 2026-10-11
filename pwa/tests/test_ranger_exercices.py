"""Un mouvement, un nom ; l'équipement à côté.

Retour d'usage du 11/10 : Progrès listait « Développé decliné (Barre) »,
« Développé décliné barre (Barre) » et « Développer décliné » comme trois
exercices. Hevy et Strong affichent « Bench Press (Barbell) » : le mouvement,
puis le matériel. La règle (core/noms_exercices.py) range l'historique une
fois (Gestion → « Ranger mes exercices ») et chaque nom qui naît ensuite.
"""
import datetime as dt

import pytest

from conftest import CSRF, USER_ID
from core import noms_exercices as ne
from core.exercises_data import resoudre
from core.seance_contexte import _build_exo_context

# Les 57 noms du propriétaire au 11/10 (nombre de séries), lus en select.
VRAIS_NOMS = {
    "Crunch (Banc)": 5, "Crunch (Machine)": 6, "Curl": 24, "Curl (Banc)": 2, "Curl (Machine)": 2,
    "Curl biceps": 2, "Curl incliné haltères (Haltères)": 4, "Curl marteau": 16,
    "Curl marteau (Haltères)": 6, "Curl marteau (Poulie)": 12, "Dead lift (Haltères)": 3,
    "Développé couché (Barre)": 7, "Développé couché (Haltères)": 42, "Développé decliné (Barre)": 5,
    "Développé décliné barre (Barre)": 11, "Développé incliné": 6, "Développé incliné (Barre)": 3,
    "Développé incliné (Haltères)": 38, "Développé incliné haltères": 7, "Développé militaire": 20,
    "Développer décliné": 15, "Dips": 36, "Dips (Lesté)": 16, "Dips (triceps)": 1,
    "Écarté machine": 27, "Écarté poulie vis-à-vis": 4, "Écartés poulie": 75,
    "Élévations latérales": 11, "Élévations latérales (Poulie)": 34, "Extension poignée": 4,
    "Extension poignet barre": 1, "Extension triceps haltère": 1, "Extension triceps haltère (Barre)": 2,
    "Extension triceps haltère (Poulie)": 38, "Extensions triceps": 17, "Extensions triceps (Barre)": 5,
    "Extensions triceps (Poulie)": 33, "Hip thrust": 14, "Leg curl": 19, "Machine abducteurs": 3,
    "Machine adducteurs": 28, "Mollet": 5, "Mollet (Machine)": 4, "Pompes": 1, "Presse à cuisses": 21,
    "Presse à cuisses (Machine)": 7, "Pushdown poulie corde": 2, "Reverse fly machine": 5,
    "Rowing machine": 39, "Rowing machine (Banc)": 3, "Shrug (Barre)": 5, "Squat": 3,
    "Tirage horizontal poulie (Machine)": 20, "Tirage vertical": 40, "Tirage vertical (Poulie)": 4,
    "Tirage verticale prise  neutre": 14, "Tractions": 44,
}


def _par_depuis(propositions):
    return {p["depuis"]: (p["vers"], p["sur"]) for p in propositions}


# ── La règle ─────────────────────────────────────────────────────


def test_le_vrai_historique_du_11_10():
    """Ce que la règle propose sur le vrai historique : rangé et coché quand
    c'est sûr, proposé décoché quand c'est un indice, rien ailleurs."""
    assert _par_depuis(ne.ranger(VRAIS_NOMS)) == {
        "Développé décliné barre (Barre)": ("Développé décliné (Barre)", True),
        "Développé decliné (Barre)": ("Développé décliné (Barre)", True),
        "Développer décliné": ("Développé décliné", True),
        "Développé incliné haltères": ("Développé incliné (Haltères)", True),
        "Curl incliné haltères (Haltères)": ("Curl incliné (Haltères)", True),
        "Extension poignet barre": ("Extension poignet (Barre)", True),
        "Extension poignée": ("Extension poignet", True),
        "Tirage verticale prise  neutre": ("Tirage verticale prise neutre", True),
        # Même fiche d'exercice : l'utilisateur tranche.
        "Pushdown poulie corde": ("Extensions triceps", False),
        "Dips (triceps)": ("Dips", False),
    }


@pytest.mark.parametrize("nom,connus", [
    ("Écarté machine", []),                  # « Écarté » seul n'est pas un mouvement connu :
    ("Reverse fly machine", []),             # le mot fait le nom, c'est la machine
    ("Machine adducteurs", []),
    ("Rowing machine (Banc)", []),
    ("Tirage horizontal poulie (Machine)", ["Tirage horizontal"]),   # contradictoire : on ne devine pas
    ("Extension triceps haltère (Poulie)", ["Extensions triceps"]),  # « haltère » dit le mouvement
    ("Extension triceps haltère", ["Extensions triceps"]),           # (au-dessus de la tête)
])
def test_le_materiel_qui_fait_partie_du_nom_reste(nom, connus):
    mouvement, materiel, raison = ne.sortir_materiel(nom, connus)
    assert raison == ""
    assert ne.nom_complet(mouvement, materiel) == nom


def test_adducteurs_et_abducteurs_ne_sont_jamais_le_meme():
    """L'ancien outil de Gestion les proposait à la fusion : une lettre
    d'écart, mais deux muscles. Deux mots connus ne sont pas une faute."""
    assert ne.meme_mouvement("Machine adducteurs", "Machine abducteurs") is None
    assert ne.ranger({"Machine adducteurs": 28, "Machine abducteurs": 3}) == []


def test_deux_prises_restent_deux_exercices():
    assert ne.ranger({"Tirage vertical": 40, "Tirage vertical prise neutre": 14,
                      "Tirage vertical prise large": 3}) == []


def test_le_materiel_entre_parentheses_traverse_le_rangement():
    """« (Poulie) » dit avec quoi la série a été faite : le perdre effacerait
    trois façons de faire le même mouvement."""
    assert _par_depuis(ne.ranger({"TRICEPS EXTENSION (Poulie)": 2, "developpe couche (Barre)": 3,
                                  "Développé couché (Barre)": 1})) == {
        "TRICEPS EXTENSION (Poulie)": ("Extensions triceps (Poulie)", True),
        "developpe couche (Barre)": ("Développé couché (Barre)", True)}


@pytest.mark.parametrize("nom", ["Hip thrust (sol)", "Squat (poids du corps ou lesté)",
                                 "Développé couché prise inversée", "Tirage horizontal prise large"])
def test_une_parenthese_ou_une_prise_reste_dans_le_nom(nom):
    """« Hip thrust (sol) » est un nom d'exercice, pas un hip thrust au sol ;
    une prise mène sa propre progression."""
    assert ne.ranger({nom: 3}) == []


def test_aucun_rangement_ne_change_un_exercice_de_fiche():
    """Si « Squats » rejoignait « Squat », ou « Mollets presse à cuisse »
    « Presse à cuisses », l'historique d'un exercice passerait sous un autre,
    sans retour. Tous les noms de la bibliothèque et des fiches à la fois."""
    from core.muscu import separer_variante
    for p in ne.ranger({r: 1 for r in ne.REFERENCES}):
        avant = resoudre(separer_variante(p["depuis"])[0])[0]
        assert avant == resoudre(separer_variante(p["vers"])[0])[0], p


def test_un_exercice_maison_reste_tel_quel():
    assert ne.ranger({"Mon exercice à moi": 4, "Curl": 24}) == []


def test_a_egalite_le_nom_le_plus_simple_l_emporte():
    assert _par_depuis(ne.ranger({"Dips": 1, "Dips (triceps)": 1})) == {"Dips (triceps)": ("Dips", False)}


def test_le_materiel_n_est_jamais_perdu():
    """« Triceps extension barre » n'est pas un autre exercice que
    « Triceps extension » : c'est le même, à la barre — et ça reste écrit."""
    props = _par_depuis(ne.ranger({"Triceps extension": 12, "Triceps extension barre": 4}))
    assert props["Triceps extension barre"] == ("Extensions triceps (Barre)", True)
    assert props["Triceps extension"] == ("Extensions triceps", True)


def test_ranger_deux_fois_ne_change_plus_rien():
    apres, props = {}, _par_depuis(ne.ranger(VRAIS_NOMS))
    for nom, n in VRAIS_NOMS.items():
        vers = props.get(nom, (nom, True))[0]
        apres[vers] = apres.get(vers, 0) + n
    assert [p for p in ne.ranger(apres) if p["sur"]] == []


def test_chaque_nom_de_reference_garde_sa_fiche():
    """Taper un nom de la bibliothèque ou d'une fiche ne doit jamais faire
    perdre sa fiche (conseils, illustration) en sortant le matériel."""
    for ref in ne.REFERENCES:
        mouvement, _materiel = ne.nom_pour_saisie(ref)
        assert resoudre(mouvement)[0] == resoudre(ref)[0], (ref, mouvement)


@pytest.mark.parametrize("tape,connus,attendu", [
    ("developpe incline halteres", [], ("Développé incliné", "Haltères")),
    ("Développer décliné", [], ("Développé décliné", None)),
    ("presse a cuisses", ["Presse à cuisses"], ("Presse à cuisses", None)),   # son orthographe à lui
    ("Leg press", ["Presse à cuisses"], ("Leg press", None)),                 # pas de synonyme forcé
    ("Mon truc à moi", [], ("Mon truc à moi", None)),
    ("  Curl   marteau  poulie ", ["Curl marteau"], ("Curl marteau", "Poulie")),
])
def test_un_nom_tape_est_range(tape, connus, attendu):
    assert ne.nom_pour_saisie(tape, connus) == attendu


# ── Gestion : « Ranger mes exercices » ───────────────────────────

LUNDI = dt.date(2026, 9, 7)


def _serie(fake, exercice, jour=0, serie=1, exo_id=None):
    ligne = {"user_id": USER_ID, "date": (LUNDI + dt.timedelta(days=jour)).isoformat(),
             "semaine": "2026-W37", "seance": "Push", "exercice": exercice, "muscle": "Pecs",
             "serie": serie, "reps": 10, "poids": 40.0, "remarque": ""}
    if exo_id:
        ligne["exercise_id"] = exo_id
    fake.table("history").insert(ligne).execute()


def _programme(fake, exos):
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": exos, "_planning": {"Lundi": "Push"}, "_settings": {},
        "_custom_exercises": [{"name": "Développé decliné", "muscle": "Pecs", "profil": "Les deux"}],
    }}).execute()


def _historique(fake):
    return sorted({r["exercice"] for r in fake.table("history").select("*").eq("user_id", USER_ID)
                   .execute().data})


@pytest.fixture()
def desordre(fake_db):
    _programme(fake_db, [{"name": "Développé décliné barre", "sets": 3, "muscle": "Pecs"},
                         {"name": "Machine adducteurs", "sets": 3, "muscle": "Adducteurs"}])
    for nom, n in (("Développé décliné barre (Barre)", 3), ("Développé decliné (Barre)", 2),
                   ("Développer décliné", 2), ("Machine adducteurs", 2), ("Machine abducteurs", 1)):
        for i in range(n):
            _serie(fake_db, nom, jour=i, serie=1)
    return fake_db


def test_gestion_propose_et_coche_le_rangement(desordre, logged_in):
    html = logged_in.get("/gestion").get_data(as_text=True)
    assert "Ranger mes exercices (3)" in html
    for depuis in ("Développé décliné barre (Barre)", "Développé decliné (Barre)", "Développer décliné"):
        assert f'name="aligner" value="{depuis}" checked' in html
    assert 'name="aligner" value="Machine abducteurs"' not in html
    assert "Doublons détectés" not in html and "Aligner sur les noms" not in html


def test_ranger_regroupe_l_historique_et_le_programme_suit(desordre, logged_in):
    r = logged_in.post("/gestion/exercice/aligner", headers={"X-CSRFToken": CSRF}, data={
        "aligner": ["Développé décliné barre (Barre)", "Développé decliné (Barre)", "Développer décliné"]})
    assert "align=ok&n=7" in r.headers["Location"]
    assert _historique(desordre) == ["Développé décliné", "Développé décliné (Barre)",
                                     "Machine abducteurs", "Machine adducteurs"]
    prog = desordre.table("programs").select("*").eq("user_id", USER_ID).execute().data[0]["data"]
    decline = prog["Push"][0]
    assert decline["name"] == "Développé décliné" and decline["materiel"] == "Barre"
    assert prog["Push"][1]["name"] == "Machine adducteurs"
    assert prog["_custom_exercises"][0]["name"] == "Développé décliné"
    html = logged_in.get("/gestion?align=ok&n=7").get_data(as_text=True)
    assert "7 séries rangées" in html and "Ranger mes exercices" not in html


def test_les_series_identifiees_gardent_leur_materiel(fake_db, logged_in):
    """Une série enregistrée avec l'identifiant de l'exercice s'affiche sous
    le nom du programme. « Développé décliné barre » devient « Développé
    décliné » : sans « ~Barre », elle aurait perdu sa barre en route."""
    _programme(fake_db, [{"name": "Développé décliné barre", "sets": 3, "muscle": "Pecs",
                          "id": "e_12345678"}])
    _serie(fake_db, "Développé décliné barre", exo_id="e_12345678")
    logged_in.post("/gestion/exercice/aligner", headers={"X-CSRFToken": CSRF},
                   data={"aligner": ["Développé décliné barre"]})
    ligne = fake_db.table("history").select("*").eq("user_id", USER_ID).execute().data[0]
    assert ligne["exercise_id"] == "e_12345678~Barre"
    assert ligne["exercice"] == "Développé décliné (Barre)"


# ── À la saisie ──────────────────────────────────────────────────


def test_l_editeur_range_un_nouvel_exercice_et_pas_les_anciens(fake_db, logged_in):
    _programme(fake_db, [{"name": "Développé décliné barre", "sets": 3, "muscle": "Pecs",
                          "id": "e_12345678"}])
    r = logged_in.post("/programme/state", headers={"X-CSRFToken": CSRF}, json={
        "name": "Mon programme", "planning": {}, "seance_order": ["Push"],
        "seances": {"Push": [
            {"name": "Développé décliné barre", "sets": 3, "muscle": "Pecs", "id": "e_12345678"},
            {"name": "developpe incline halteres", "sets": 4, "muscle": "Pecs"},
        ]}})
    assert r.get_json() == {"ok": True, "noms": [
        ["Push", "developpe incline halteres", "Développé incliné", "Haltères"]]}
    push = fake_db.table("programs").select("*").eq("user_id", USER_ID).execute().data[0]["data"]["Push"]
    assert [(e["name"], e.get("materiel")) for e in push] == [
        ("Développé décliné barre", None),            # déjà là : son historique le suit par ce nom
        ("Développé incliné", "Haltères")]


def test_un_exercice_ajoute_en_seance_est_range(fake_db, logged_in):
    _programme(fake_db, [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}])
    _serie(fake_db, "Développé incliné (Haltères)")
    logged_in.post("/seance/add-extra", headers={"X-CSRFToken": CSRF}, data={
        "mode": "prefaite", "name": "Push", "seance_name": "Push", "date": "2026-10-11",
        "exo_name": "developpe incline halteres", "sets_count": "3"})
    calque = fake_db.table("calques_seance").select("*").eq("user_id", USER_ID).execute().data[0]
    assert calque["extras"][-1]["name"] == "Développé incliné"
    assert calque["extras"][-1]["materiel"] == "Haltères"


def test_la_carte_de_seance_part_sur_l_equipement_du_programme():
    exo = {"name": "Développé incliné", "sets": 3, "muscle": "Pecs", "materiel": "Haltères"}
    sans_historique = _build_exo_context([], exo, "Push", 2, "2026-10-11")
    assert sans_historique["variant"] == "Haltères"
    deja_fait = [{"Séance": "Push", "Exercice": "Développé incliné (Barre)", "Date": "2026-10-04",
                  "Série": 1, "Reps": 10, "Poids": 40.0, "Semaine": 1, "Muscle": "Pecs"}]
    assert _build_exo_context(deja_fait, exo, "Push", 2, "2026-10-11")["variant"] == "Barre"


def test_un_exercice_perso_est_range(fake_db, logged_in):
    _programme(fake_db, [{"name": "Hip thrust", "sets": 3, "muscle": "Fessiers"}])
    logged_in.post("/gestion/exercice/ajouter", headers={"X-CSRFToken": CSRF},
                   data={"name": "hip thrust machine", "muscle": "Fessiers"})
    customs = fake_db.table("programs").select("*").eq("user_id", USER_ID).execute().data[0]["data"]
    assert customs["_custom_exercises"][-1]["name"] == "Hip thrust"


# ── Progrès ──────────────────────────────────────────────────────


def test_progres_liste_chaque_mouvement_une_fois(fake_db, logged_in):
    _programme(fake_db, [{"name": "Curl marteau", "sets": 3, "muscle": "Biceps"}])
    for i, nom in enumerate(("Curl marteau", "Curl marteau (Poulie)", "Curl marteau (Haltères)")):
        _serie(fake_db, nom, jour=i)
    html = logged_in.get("/progres").get_data(as_text=True)
    choix = html.split('id="exo-pick"')[1].split("</select>")[0]
    assert choix.count("<option") == 1 and "Curl marteau</option>" in choix


def test_la_fiche_s_ouvre_sur_l_equipement_le_plus_pratique(fake_db, logged_in):
    """40 kg aux haltères ne sont pas 40 kg à la barre : la courbe et les
    records suivent un équipement à la fois, comme chez Hevy et Strong."""
    _programme(fake_db, [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}])
    for i in range(3):
        _serie(fake_db, "Développé couché (Haltères)", jour=i)
    _serie(fake_db, "Développé couché (Barre)", jour=5)
    html = logged_in.get("/progres/exercice?exo=D%C3%A9velopp%C3%A9+couch%C3%A9").get_data(as_text=True)
    assert "3 séances" in html                        # les haltères seulement
    assert 'class="variant-chip on"' in html.split("Haltères")[0][-400:]
    assert "variante=tous" in html
    tous = logged_in.get("/progres/exercice?exo=D%C3%A9velopp%C3%A9+couch%C3%A9&variante=tous")
    assert "4 séances" in tous.get_data(as_text=True)
