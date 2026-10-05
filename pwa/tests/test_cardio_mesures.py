"""Durée, distance, vitesse : deux valeurs sur trois suffisent.

Le formulaire calculait déjà la vitesse à partir de la durée et de la
distance. Dans ce sens seulement — et seulement pour l'AFFICHER en
suggestion : elle n'arrivait jamais jusqu'à la base. Or on connaît souvent
l'inverse : le tapis affiche 10 km/h pendant 30 minutes, et c'est la distance
qu'on ignore.

Trois défauts trouvés en mesurant, au-delà de ce cas :

1. la vitesse suggérée n'était pas enregistrée ;
2. la page `/cardio` n'avait **aucun** champ vitesse, alors que le formulaire
   de séance en a un — deux écrans pour la même chose, chacun avec un champ
   que l'autre n'a pas ;
3. la table des unités vivait en dur dans le JavaScript, et la règle de
   conversion se devinait à partir du LIBELLÉ : « Allure (min/500m) » ne
   tombait dans aucun cas, donc l'allure du rameur ne se calculait jamais.
"""
import re
from pathlib import Path

import pytest

from conftest import USER_ID, CSRF
from core.seance_cardio import UNITES_CARDIO, completer_mesures, unites

RACINE = Path(__file__).resolve().parent.parent


# ── Les deux sens ────────────────────────────────────────────────────────

def test_la_distance_se_deduit_de_la_vitesse():
    """Le cas demandé : 30 min à 10 km/h, c'est 5 km."""
    assert completer_mesures("Course", 30, "", 10) == (5.0, 10.0)


def test_la_vitesse_se_deduit_de_la_distance():
    """Le sens qui existait déjà — il ne doit pas casser."""
    assert completer_mesures("Course", 30, 5, "") == (5.0, 10.0)


def test_les_deux_sens_se_repondent():
    """Aller-retour : ce qu'on déduit redonne ce dont on est parti."""
    _, v = completer_mesures("Course", 45, 9, "")
    d, _ = completer_mesures("Course", 45, "", v)
    assert d == 9.0


@pytest.mark.parametrize("activite,duree,distance,attendu_vitesse", [
    ("Natation", 20, 1, 50.0),        # 1 km en 20 min = 50 m/min
    ("Corde", 5, 300, 60.0),          # 300 sauts en 5 min
    ("Montée d'escaliers", 10, 400, 40.0),
    ("Vélo", 60, 25, 25.0),
    ("Marche", 30, 2.5, 5.0),
])
def test_chaque_unite_a_sa_regle(activite, duree, distance, attendu_vitesse):
    """Chaque activité convertit dans son unité, pas en km/h par défaut."""
    assert completer_mesures(activite, duree, distance, "")[1] == attendu_vitesse


# ── Ce qu'on ne touche pas ───────────────────────────────────────────────

def test_une_valeur_saisie_prime_sur_une_valeur_deduite():
    """Si l'utilisateur donne les deux, on ne corrige rien.

    Un tapis qui ment sur sa distance reste ce que l'utilisateur a lu : ce
    n'est pas à l'app de trancher entre ses deux chiffres.
    """
    assert completer_mesures("Course", 30, 5, 12) == (5.0, 12.0)


def test_sans_rien_on_ne_deduit_rien():
    assert completer_mesures("Course", 30, "", "") == (0.0, 0.0)


def test_sans_duree_on_ne_deduit_rien():
    """La durée n'est jamais déduite : c'est elle qui identifie la séance."""
    assert completer_mesures("Course", 0, "", 10) == (0.0, 10.0)
    assert completer_mesures("Course", "", 5, "") == (5.0, 0.0)


@pytest.mark.parametrize("activite", ["HIIT", "Rameur"])
def test_une_activite_sans_regle_reste_intacte(activite):
    """HIIT compte des rounds ; l'allure du rameur est en min/500 m, ce qui
    n'est pas une simple division. Mieux vaut ne rien dire que dire faux."""
    assert completer_mesures(activite, 20, 5, "") == (5.0, 0.0)
    assert completer_mesures(activite, 20, "", 2) == (0.0, 2.0)


def test_une_activite_inconnue_retombe_sur_autre():
    assert unites("Zumba") is UNITES_CARDIO["Autre"]
    assert completer_mesures("Zumba", 30, "", 10) == (5.0, 10.0)


# ── Ce que l'utilisateur tape vraiment ───────────────────────────────────

def test_la_virgule_decimale_est_acceptee():
    """Un clavier français met une virgule."""
    assert completer_mesures("Course", 30, "", "10,5") == (5.25, 10.5)
    assert completer_mesures("Course", 30, "5,5", "") == (5.5, 11.0)


@pytest.mark.parametrize("bruit", ["", None, "abc", "-3", "0"])
def test_une_saisie_absurde_ne_fait_rien_deduire(bruit):
    assert completer_mesures("Course", 30, bruit, bruit) == (0.0, 0.0)


def test_le_resultat_est_arrondi_au_centieme():
    """Sans arrondi, 20 min à 7 km/h donnerait 2.3333333333333335 km."""
    d, _ = completer_mesures("Course", 20, "", 7)
    assert d == 2.33


# ── Une seule table d'unités ─────────────────────────────────────────────

def test_le_javascript_ne_garde_pas_sa_propre_table():
    """Elle vivait en dur dans `static/js/seance.js`. Deux copies d'une table
    d'unités finissent toujours par diverger."""
    src = (RACINE / "static" / "js" / "seance.js").read_text(encoding="utf-8")
    assert not re.search(r"var UNITS = \{\s*\n\s*\"Course\"", src), \
        "seance.js a de nouveau sa propre table d'unités"
    assert "CONFIG.cardioUnits" in src, "elle doit venir du serveur"


def test_les_deux_ecrans_recoivent_la_table():
    """`/cardio` et l'écran de séance servent la même, depuis Python."""
    for gabarit, cle in (("cardio.html", "unites_cardio|tojson"),
                         ("seance_edit.html", '"cardioUnits": unites_cardio')):
        src = (RACINE / "templates" / gabarit).read_text(encoding="utf-8")
        assert cle in src, f"{gabarit} ne reçoit pas la table"


def test_chaque_activite_declare_une_regle_connue():
    """Une faute de frappe dans `regle` ferait taire le calcul en silence."""
    connues = {"par_heure", "m_par_min", "par_min", ""}
    for nom, u in UNITES_CARDIO.items():
        assert u["regle"] in connues, f"{nom} : règle inconnue {u['regle']!r}"
        assert u["dist"], f"{nom} : pas d'étiquette de distance"
        if u["regle"]:
            assert u["vit"], f"{nom} : une règle sans étiquette de vitesse"


def test_les_activites_du_formulaire_ont_toutes_leur_unite():
    """Une activité proposée sans unité retomberait muettement sur « Autre »."""
    from routes.cardio import ACTIVITES
    manquantes = [nom for nom, _icone, _met in ACTIVITES if nom not in UNITES_CARDIO]
    assert manquantes == [], f"sans unité déclarée : {manquantes}"


# ── Ce qui arrive vraiment en base ───────────────────────────────────────

JOUR = "2026-09-14"


@pytest.fixture()
def compte(fake_db):
    fake_db.table("profiles").insert(
        {"id": USER_ID, "tier": "free", "poids_kg": 75}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {}, "_settings": {}}}).execute()
    return fake_db


def _ligne_cardio(fake_db):
    lignes = [r for r in fake_db.table("history").select("*").eq(
        "user_id", USER_ID).execute().data
        if str(r.get("exercice") or "").startswith("CARDIO:")]
    assert len(lignes) == 1, lignes
    return lignes[0]


def test_la_page_cardio_enregistre_la_distance_deduite(compte, logged_in):
    """Le cas demandé, de bout en bout : 30 min à 10 km/h.

    Cet écran n'avait même pas de champ vitesse.
    """
    logged_in.post("/cardio/save", data={
        "activite": "Course", "date": JOUR, "duree_min": "30",
        "distance_km": "", "vitesse": "10",
    }, headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    ligne = _ligne_cardio(compte)
    assert float(ligne["distance"]) == 5.0, "la distance déduite doit être stockée"
    assert ligne["vitesse"] == 10.0


def test_la_page_cardio_enregistre_la_vitesse_deduite(compte, logged_in):
    """L'autre sens : la vitesse n'était nulle part sur cet écran."""
    logged_in.post("/cardio/save", data={
        "activite": "Course", "date": JOUR, "duree_min": "30",
        "distance_km": "5", "vitesse": "",
    }, headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    assert _ligne_cardio(compte)["vitesse"] == 10.0


def test_la_seance_enregistre_la_vitesse_quon_lui_suggerait(compte, logged_in):
    """Le défaut de fond : le formulaire de séance CALCULAIT la vitesse et
    l'affichait en suggestion, mais elle n'arrivait jamais en base."""
    logged_in.post("/seance/add-cardio", data={
        "mode": "prefaite", "name": "Push", "seance_name": "Push", "date": JOUR,
        "activite": "Course", "duree_min": "30", "distance_km": "5",
        "vitesse": "", "_csrf": CSRF,
    }, headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    assert _ligne_cardio(compte)["vitesse"] == 10.0


def test_la_seance_deduit_aussi_la_distance(compte, logged_in):
    logged_in.post("/seance/add-cardio", data={
        "mode": "prefaite", "name": "Push", "seance_name": "Push", "date": JOUR,
        "activite": "Course", "duree_min": "30", "distance_km": "",
        "vitesse": "10", "_csrf": CSRF,
    }, headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    assert float(_ligne_cardio(compte)["distance"]) == 5.0


def test_ce_que_lutilisateur_a_saisi_nest_pas_recalcule(compte, logged_in):
    """Deux chiffres lus sur un tapis peuvent être incohérents. Ce n'est pas
    à l'app de trancher : on garde les deux tels quels."""
    logged_in.post("/cardio/save", data={
        "activite": "Course", "date": JOUR, "duree_min": "30",
        "distance_km": "4", "vitesse": "12",
    }, headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    ligne = _ligne_cardio(compte)
    assert float(ligne["distance"]) == 4.0
    assert ligne["vitesse"] == 12.0


def test_la_relecture_retrouve_la_vitesse(compte, logged_in):
    """L'app doit savoir relire ce qu'on vient d'écrire, sinon la séance
    passée s'affiche sans vitesse."""
    import core.db as db
    from core.seance_cardio import _parse_cardio_remarque
    logged_in.post("/cardio/save", data={
        "activite": "Course", "date": JOUR, "duree_min": "30",
        "distance_km": "", "vitesse": "10",
    }, headers={"X-CSRFToken": CSRF}, follow_redirects=True)
    (ligne,) = [r for r in db.get_hist(USER_ID) if r["Exercice"].startswith("CARDIO:")]
    assert _parse_cardio_remarque(ligne["Remarque"])["vitesse"] == "10"
    assert ligne["Vitesse"] == 10.0


# ── Le GPS n'est pas bloqué par nos propres en-têtes ─────────────


def test_la_position_est_autorisee_pour_notre_propre_page(fake_db, logged_in):
    """Permissions-Policy geolocation=() refusait la position avant tout code
    JS : la page disait « Autorise la position » à qui l'avait autorisée."""
    policy = logged_in.get("/cardio").headers.get("Permissions-Policy", "")
    assert "geolocation=(self)" in policy


def test_lapp_android_declare_la_permission_de_position():
    manifest = (Path(__file__).resolve().parents[2]
                / "android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert "android.permission.ACCESS_FINE_LOCATION" in manifest
