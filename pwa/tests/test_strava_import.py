"""Lire l'export Strava plutôt que d'appeler son API.

Depuis juin 2026, l'API « Standard » de Strava exige un abonnement actif.
Bâtir l'import dessus, c'est bâtir quelque chose qui s'éteint le jour où on
cesse de payer. L'export de ses propres données, lui, reste gratuit.

Mais `activities.csv` n'est pas un fichier propre, et chaque test ci-dessous
correspond à un piège réel :

* les en-têtes changent avec la langue du compte ;
* la date est écrite au format local, jamais en ISO ;
* le séparateur est une virgule ou un point-virgule selon la locale ;
* les distances sont en mètres — sauf quand elles sont en kilomètres.

Le dernier groupe vérifie la promesse qui compte : **rien n'est écrit avant
que l'utilisateur ait vu ce qui va entrer.**
"""
import pytest

from conftest import USER_ID, CSRF
from core.strava_import import lire_activites, lire_date, marquer_doublons

EN = ("Activity ID,Activity Date,Activity Name,Activity Type,Elapsed Time,Distance,Calories\n"
      '1,"Sep 14, 2026, 6:12:07 PM",Footing,Run,1800,5000,390\n'
      '2,"Sep 12, 2026, 7:00:00 AM",Sortie,Ride,3600,25000,700\n')


def _une(csv_texte, i=0):
    seances, _ = lire_activites(csv_texte)
    return seances[i]


# ── Le format, dans ses variantes ────────────────────────────────────────

def test_un_export_anglais_se_lit():
    s = _une(EN)
    assert s["date"] == "2026-09-14"
    assert s["activite"] == "Course"
    assert s["duree_min"] == 30
    assert s["distance_km"] == 5.0
    assert s["calories"] == 390


def test_un_export_francais_se_lit_aussi():
    """En-têtes traduits, point-virgule, virgule décimale, mois abrégé."""
    fr = ("Date de l'activité;Nom de l'activité;Type d'activité;Temps écoulé;Distance\n"
          "14 sept. 2026 18:12;Footing;Course à pied;1800;5,0\n")
    s = _une(fr)
    assert s["date"] == "2026-09-14"
    assert s["activite"] == "Course"
    assert s["distance_km"] == 5.0


@pytest.mark.parametrize("texte,attendu", [
    ("2026-09-14 18:12:07", "2026-09-14"),
    ("2026-09-14T18:12:07Z", "2026-09-14"),
    ("Sep 14, 2026, 6:12:07 PM", "2026-09-14"),
    ("14 sept. 2026 à 18:12", "2026-09-14"),
    ("14/09/2026 18:12", "2026-09-14"),
    ("09/14/2026 18:12", "2026-09-14"),
    ("1 mars 2026", "2026-03-01"),
])
def test_les_formats_de_date_courants(texte, attendu):
    assert lire_date(texte).strftime("%Y-%m-%d") == attendu


@pytest.mark.parametrize("texte", ["", None, "hier", "32/13/2026", "2026-02-30"])
def test_une_date_illisible_rend_none(texte):
    assert lire_date(texte) is None


# ── L'unité de distance, devinée par la vitesse ──────────────────────────

def test_des_metres_sont_reconnus_comme_tels():
    """5 000 pour 30 min de course : des mètres. L'interpréter en kilomètres
    donnerait 10 000 km/h."""
    seances, rapport = lire_activites(EN)
    assert rapport["unite_distance"] == "m"
    assert seances[0]["distance_km"] == 5.0


def test_des_kilometres_sont_reconnus_comme_tels():
    """Se tromper ici multiplie — ou divise — tout un historique par mille."""
    km = ("Activity Date,Activity Type,Elapsed Time,Distance\n"
          "2026-09-14,Run,1800,5.0\n2026-09-12,Ride,3600,25.0\n")
    seances, rapport = lire_activites(km)
    assert rapport["unite_distance"] == "km"
    assert seances[0]["distance_km"] == 5.0


def test_lunite_est_tranchee_sur_le_fichier_entier():
    """Une ligne aberrante ne doit pas faire basculer tout le fichier."""
    melange = ("Activity Date,Activity Type,Elapsed Time,Distance\n"
               "2026-09-14,Run,1800,5000\n2026-09-13,Run,1800,5200\n"
               "2026-09-12,Run,1800,4800\n2026-09-11,Run,60,3\n")
    _, rapport = lire_activites(melange)
    assert rapport["unite_distance"] == "m"


# ── Les types d'activité ─────────────────────────────────────────────────

@pytest.mark.parametrize("strava,chez_nous", [
    ("Run", "Course"), ("TrailRun", "Course"), ("Ride", "Vélo"),
    ("Swim", "Natation"), ("Walk", "Marche"), ("Hike", "Marche"),
    ("Rowing", "Rameur"), ("Elliptical", "Elliptique"),
    ("StairStepper", "Montée d'escaliers"), ("Workout", "HIIT"),
])
def test_les_types_strava_deviennent_les_notres(strava, chez_nous):
    csv_t = ("Activity Date,Activity Type,Elapsed Time,Distance\n"
             "2026-09-14," + strava + ",1800,5000\n")
    assert _une(csv_t)["activite"] == chez_nous


def test_un_type_inconnu_devient_autre():
    csv_t = ("Activity Date,Activity Type,Elapsed Time,Distance\n"
             "2026-09-14,Kitesurf,1800,5000\n")
    s = _une(csv_t)
    assert s["activite"] == "Autre"
    assert s["type_strava"] == "Kitesurf"


def test_la_musculation_est_ecartee_et_annoncee():
    """L'app suit les séances de muscu ailleurs : les importer ferait doublon.
    Mais on le dit, plutôt que de les faire disparaître en silence."""
    csv_t = ("Activity Date,Activity Type,Elapsed Time,Distance\n"
             "2026-09-14,WeightTraining,2700,0\n2026-09-13,Run,1800,5000\n")
    seances, rapport = lire_activites(csv_t)
    assert [s["activite"] for s in seances] == ["Course"]
    assert rapport["hors_cardio"] == {"musculation": 1}


# ── Ce qui est écarté se compte ──────────────────────────────────────────

def test_les_lignes_illisibles_sont_comptees():
    csv_t = ("Activity Date,Activity Type,Elapsed Time,Distance\n"
             "2026-09-14,Run,1800,5000\n"
             "jamais,Run,1800,5000\n"
             "2026-09-12,Run,0,5000\n")
    seances, rapport = lire_activites(csv_t)
    assert len(seances) == 1
    assert rapport["sans_date"] == 1 and rapport["sans_duree"] == 1
    assert rapport["lignes"] == 3


def test_un_fichier_qui_nest_pas_un_export_ne_rend_rien():
    seances, rapport = lire_activites("nom,prenom\nAlex,Morau\n")
    assert seances == []
    assert "date" not in rapport["colonnes"]


@pytest.mark.parametrize("entree", ["", "   ", b"", None])
def test_un_fichier_vide_ne_fait_pas_tomber(entree):
    seances, rapport = lire_activites(entree)
    assert seances == [] and rapport["lignes"] == 0


def test_les_seances_sortent_des_plus_recentes_aux_plus_anciennes():
    seances, _ = lire_activites(EN)
    assert [s["date"] for s in seances] == ["2026-09-14", "2026-09-12"]


# ── Le dédoublonnage ─────────────────────────────────────────────────────

def _hist(date, activite, minutes):
    return {"Date": date, "Exercice": "CARDIO:" + activite, "Reps": minutes,
            "Séance": "Cardio " + activite}


def test_une_seance_deja_saisie_est_reconnue():
    seances, _ = lire_activites(EN)
    marquer_doublons(seances, [_hist("2026-09-14", "Course", 30)])
    assert [s["deja"] for s in seances] == [True, False]


def test_deux_minutes_decart_comptent_pour_la_meme():
    """Strava compte le temps écoulé, l'app la durée saisie : elles diffèrent
    de peu. Exiger l'égalité stricte doublerait presque tout."""
    seances, _ = lire_activites(EN)
    marquer_doublons(seances, [_hist("2026-09-14", "Course", 32)])
    assert seances[0]["deja"] is True


def test_deux_footings_le_meme_jour_restent_deux_seances():
    """L'app les distingue déjà par leur durée ; l'import ne doit pas les
    confondre, sinon le second n'entrerait jamais."""
    deux = ("Activity Date,Activity Type,Elapsed Time,Distance\n"
            "2026-09-14,Run,1800,5000\n2026-09-14,Run,3600,10000\n")
    seances, _ = lire_activites(deux)
    marquer_doublons(seances, [_hist("2026-09-14", "Course", 30)])
    assert sorted(s["deja"] for s in seances) == [False, True]


def test_une_seance_de_muscu_nempeche_pas_un_cardio():
    seances, _ = lire_activites(EN)
    marquer_doublons(seances, [{"Date": "2026-09-14", "Exercice": "Développé couché",
                                "Reps": 30, "Séance": "Push"}])
    assert seances[0]["deja"] is False


def test_un_historique_vide_ne_marque_rien():
    seances, _ = lire_activites(EN)
    marquer_doublons(seances, [])
    assert not any(s["deja"] for s in seances)


# ── Rien n'est écrit avant que l'utilisateur ait vu ──────────────────────

@pytest.fixture()
def compte(fake_db):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "_planning": {}, "_settings": {}}}).execute()
    return fake_db


def _cardio(fake_db):
    return [r for r in fake_db.table("history").select("*").eq(
        "user_id", USER_ID).execute().data
        if str(r.get("exercice") or "").startswith("CARDIO:")]


def _deposer(client, contenu=EN, nom="activities.csv"):
    import io as _io
    return client.post("/cardio/import", data={
        "fichier": (_io.BytesIO(contenu.encode("utf-8")), nom),
    }, headers={"X-CSRFToken": CSRF}, content_type="multipart/form-data")


def test_lapercu_necrit_rien(compte, logged_in):
    """La promesse centrale : on montre, puis l'utilisateur décide.

    Un import qui écrit d'abord et explique ensuite oblige à défaire à la main.
    """
    r = _deposer(logged_in)
    assert r.status_code == 200
    assert _cardio(compte) == [], "l'aperçu ne doit rien avoir écrit"


def test_lapercu_annonce_ce_qui_va_entrer(compte, logged_in):
    corps = _deposer(logged_in).get_data(as_text=True)
    assert "2026-09-14" in corps and "Course" in corps
    assert "Importer ces 2" in corps


def test_la_confirmation_ecrit_ce_qui_a_ete_montre(compte, logged_in):
    import json
    charge = json.dumps([
        {"date": "2026-09-14", "activite": "Course", "duree_min": 30,
         "distance_km": 5.0, "calories": 390}])
    logged_in.post("/cardio/import/confirmer", data={"charge": charge},
                   headers={"X-CSRFToken": CSRF})
    lignes = _cardio(compte)
    assert len(lignes) == 1
    assert int(lignes[0]["duree_min"]) == 30
    assert float(lignes[0]["distance"]) == 5.0
    assert "Import Strava" in (lignes[0]["remarque"] or "")


def test_la_vitesse_est_calculee_a_limport(compte, logged_in):
    """L'export ne donne pas la vitesse : elle se déduit de la durée et de la
    distance, comme pour une saisie manuelle."""
    import json
    charge = json.dumps([{"date": "2026-09-14", "activite": "Course",
                          "duree_min": 30, "distance_km": 5.0}])
    logged_in.post("/cardio/import/confirmer", data={"charge": charge},
                   headers={"X-CSRFToken": CSRF})
    assert _cardio(compte)[0]["vitesse"] == 10.0


def test_une_charge_trafiquee_est_revalidee(compte, logged_in):
    """Le contenu revient par le formulaire : lui faire confiance laisserait
    entrer n'importe quoi dans l'historique."""
    import json
    charge = json.dumps([
        {"date": "pas une date", "activite": "Course", "duree_min": 30},
        {"date": "2026-09-14", "activite": "<script>", "duree_min": 99999,
         "distance_km": -5},
        "pas un objet",
    ])
    logged_in.post("/cardio/import/confirmer", data={"charge": charge},
                   headers={"X-CSRFToken": CSRF})
    lignes = _cardio(compte)
    assert len(lignes) == 1, "seule la ligne datée devait passer"
    assert lignes[0]["exercice"] == "CARDIO:Autre", "type inconnu ramené à Autre"
    assert int(lignes[0]["reps"]) <= 1440, "durée bornée"
    assert float(lignes[0]["poids"]) >= 0, "distance jamais négative"


def test_une_charge_absurde_necrit_rien(compte, logged_in):
    for charge in ("", "pas du json", "{}", "null"):
        logged_in.post("/cardio/import/confirmer", data={"charge": charge},
                       headers={"X-CSRFToken": CSRF})
    assert _cardio(compte) == []


def test_un_fichier_qui_nest_pas_un_export_le_dit(compte, logged_in):
    corps = _deposer(logged_in, "nom,prenom\nAlex,Morau\n").get_data(as_text=True)
    assert "colonne de date" in corps
    assert _cardio(compte) == []


def test_relancer_limport_ne_double_pas(compte, logged_in):
    """Le même fichier deux fois de suite : la seconde fois, tout est déjà là."""
    import json
    charge = json.dumps([{"date": "2026-09-14", "activite": "Course",
                          "duree_min": 30, "distance_km": 5.0}])
    logged_in.post("/cardio/import/confirmer", data={"charge": charge},
                   headers={"X-CSRFToken": CSRF})
    corps = _deposer(logged_in).get_data(as_text=True)
    assert "déjà chez toi" in corps
    assert "Importer ces 1" in corps, "seule la seconde séance reste à importer"


def test_la_page_explique_comment_recuperer_larchive(compte, logged_in):
    """Sans ces quatre étapes, personne ne trouve l'export : il est enterré
    sous « Télécharger ou supprimer votre compte »."""
    corps = logged_in.get("/cardio/import").get_data(as_text=True)
    assert "Demander votre archive" in corps
    assert "activities.csv" in corps
    assert "gratuit" in corps, "dire pourquoi on passe par le fichier"


def test_la_page_cardio_mene_a_limport(compte, logged_in):
    corps = logged_in.get("/cardio").get_data(as_text=True)
    assert "/cardio/import" in corps


def test_sans_fichier_la_page_le_dit(compte, logged_in):
    r = logged_in.post("/cardio/import", data={},
                       headers={"X-CSRFToken": CSRF},
                       content_type="multipart/form-data")
    assert r.status_code == 200
    assert "Choisis le fichier" in r.get_data(as_text=True)
