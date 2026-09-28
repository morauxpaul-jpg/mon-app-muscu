"""Un affleurement de doigt ne doit rien écrire en base.

`prefetch.js` charge la page visée au `touchstart` ET au survol, pour
remplir le cache avant le clic. Effleurer le lien Accueil — sans même
appuyer — déclenchait donc les écritures de `/accueil` : badges débloqués
et record de streak.

Le garde-fou `is_navigation` existait pour l'upsell et le défi, mais il
était calculé APRÈS ces deux écritures-là. Elles passaient à travers.

Une vraie navigation envoie `Sec-Fetch-Mode: navigate` ; le fetch du
prefetch envoie `same-origin`.

Une TROISIÈME écriture a survécu à ce correctif : `_display_week`, un helper
d'AFFICHAGE, gravait `_started_at` par un `save_prog` caché derrière un
import paresseux. Ni le garde-fou ni les tests ci-dessus ne la voyaient,
parce qu'ils donnent tous un `_started_at` au programme. Les tests de la fin
de ce fichier partent d'un programme qui n'en a pas.
"""
import datetime as dt

import pytest

from conftest import USER_ID, CSRF

LUNDI = dt.date(2026, 9, 14)
PREFETCH = {"Sec-Fetch-Mode": "same-origin"}
VISITE = {"Sec-Fetch-Mode": "navigate"}


@pytest.fixture()
def compte(fake_db):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": LUNDI.isoformat(),
    }}).execute()
    # Assez de séries pour débloquer au moins un badge.
    for i in range(12):
        jour = (LUNDI + dt.timedelta(days=i)).isoformat()
        fake_db.table("history").insert({
            "user_id": USER_ID, "date": jour, "semaine": "2026-W38",
            "seance": "Push", "exercice": "Développé couché", "muscle": "Pecs",
            "series": 1, "reps": 10, "poids": 60.0}).execute()
    return fake_db


def _prog(fake_db):
    return fake_db.table("programs").select("*").eq(
        "user_id", USER_ID).execute().data[0]["data"]


def test_un_prefetch_necrit_aucun_badge(compte, logged_in):
    avant = _prog(compte).get("_badges")
    assert logged_in.get("/accueil", headers=PREFETCH).status_code == 200
    assert _prog(compte).get("_badges") == avant


def test_un_prefetch_necrit_aucun_record_de_streak(compte, logged_in):
    avant = _prog(compte).get("_streak_record")
    logged_in.get("/accueil", headers=PREFETCH)
    assert _prog(compte).get("_streak_record") == avant


def test_une_vraie_visite_enregistre_bien(compte, logged_in):
    """Le garde-fou ne doit pas empêcher ce pour quoi le code existe."""
    logged_in.get("/accueil", headers=VISITE)
    prog = _prog(compte)
    assert prog.get("_badges") or prog.get("_streak_record"), \
        "une visite réelle doit graver quelque chose"


def test_un_prefetch_affiche_quand_meme_la_page(compte, logged_in):
    """On ne coupe que l'écriture : la page rendue doit rester identique,
    sinon le cache servirait une version appauvrie au vrai clic."""
    prefetche = logged_in.get("/accueil", headers=PREFETCH).get_data(as_text=True)
    visite = logged_in.get("/accueil", headers=VISITE).get_data(as_text=True)
    assert len(prefetche) > 500
    # Même nombre de badges affichés de part et d'autre.
    assert prefetche.count("badge-item") == visite.count("badge-item")


def test_sans_en_tete_on_considere_que_cest_une_visite(compte, logged_in):
    """Un vieux navigateur n'envoie pas `Sec-Fetch-Mode`. Mieux vaut écrire
    une fois de trop que perdre un badge pour toujours."""
    logged_in.get("/accueil")
    prog = _prog(compte)
    assert prog.get("_badges") or prog.get("_streak_record")


# ── Le repli de `_display_week` : calculer sans graver ───────────────────

@pytest.fixture()
def compte_sans_date_de_depart(fake_db):
    """Un programme d'avant l'onboarding — donc sans `_started_at`."""
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
    }}).execute()
    # Étalé sur trois semaines : la première séance et la dernière ne
    # tombent pas dans la même semaine, sinon un repli qui prendrait la
    # MAUVAISE extrémité donnerait quand même le bon numéro.
    for decalage in (0, 1, 2, 14, 15):
        jour = (LUNDI + dt.timedelta(days=decalage)).isoformat()
        fake_db.table("history").insert({
            "user_id": USER_ID, "date": jour, "semaine": "2026-W38",
            "seance": "Push", "exercice": "Développé couché", "muscle": "Pecs",
            "series": 1, "reps": 10, "poids": 60.0}).execute()
    return fake_db


def test_laccueil_ne_grave_pas_la_date_de_depart(compte_sans_date_de_depart, logged_in):
    """Un effleurement de l'accueil ne doit pas graver la date de départ.

    Le prefetch, et pas une visite : une visite écrit légitimement les badges
    juste après, avec un programme lu séparément qui écrase ce que
    `_display_week` venait d'écrire. Le test ne verrait donc rien.
    """
    assert logged_in.get("/accueil", headers=PREFETCH).status_code == 200
    assert "_started_at" not in _prog(compte_sans_date_de_depart)


def test_la_seance_ne_grave_pas_la_date_de_depart(compte_sans_date_de_depart, logged_in):
    assert logged_in.get("/seance", headers=VISITE).status_code == 200
    assert "_started_at" not in _prog(compte_sans_date_de_depart)


def test_le_numero_de_semaine_reste_affiche_sans_date_de_depart(
        compte_sans_date_de_depart, logged_in):
    """Retirer l'écriture ne doit pas dérégler l'affichage.

    Sans `_started_at`, la semaine se compte depuis la première séance de
    l'historique. La valeur attendue est calculée ici, pas recopiée : le
    test doit tomber si le repli change de référence.

    `/accueil` avale les exceptions de `_display_week` et affiche 1 — sans
    cette vérification chiffrée, une fonction cassée passerait inaperçue.
    """
    import re
    from core.dates import logical_today_paris
    aujourdhui = logical_today_paris()
    attendu = ((aujourdhui - dt.timedelta(days=aujourdhui.weekday()))
               - (LUNDI - dt.timedelta(days=LUNDI.weekday()))).days // 7 + 1

    page = logged_in.get("/accueil", headers=VISITE).get_data(as_text=True)
    trouve = re.search(r"SEMAINE (\d+)", page)
    assert trouve, "le numéro de semaine a disparu de l'accueil"
    assert int(trouve.group(1)) == max(1, attendu)


def test_les_deux_pages_comptent_la_meme_semaine(compte_sans_date_de_depart, logged_in):
    """`/progres` faisait déjà ce calcul sans graver. Les deux doivent
    s'accorder, sinon l'utilisateur lit deux numéros différents."""
    import routes.progres as progres
    from core.data import get_hist, get_prog
    from routes.seance import _display_week
    with logged_in.application.test_request_context():
        from flask import g
        g.user_id = USER_ID
        hist, prog = get_hist(), get_prog()
        depart = progres._compute_start_monday(hist, prog)
        # Une date assez loin pour que le numéro dépasse 1 : les deux calculs
        # plafonnent à 1 par le bas, ce qui masquerait un désaccord.
        cible = LUNDI + dt.timedelta(days=16)
        semaine_progres = progres._rel_week(cible.isoformat(), depart)
        semaine_accueil = _display_week(cible, prog, hist)
    assert semaine_accueil > 1, "date de comparaison trop proche du début"
    assert semaine_progres == semaine_accueil
