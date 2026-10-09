"""Une séance prévue un jour à venir s'enregistre aujourd'hui, jamais à l'avance.

Audit du 06/10 (I-1), constaté en production : le 04/10 à 17:57, deux séries
« Push 1 » ont été écrites à la date du 05/10. Un jour sans séance prévue, la
seule action de l'accueil était « Prochaine séance · Demain », qui ouvrait la
page datée du lendemain avec un bandeau « RATTRAPAGE ».

Désormais :
* la carte ouvre une séance datée d'aujourd'hui (« Faire maintenant »), avec un
  bandeau « En avance » qui nomme le jour prévu ;
* une page datée d'un jour à venir (gardée pour le hors-ligne) est ramenée à
  aujourd'hui par le navigateur (tests/js/test_jour_seance.js) ;
* le serveur refuse toute écriture datée d'un jour à venir.
"""
import datetime as dt
import json
import re

from conftest import USER_ID, CSRF
from core.dates import logical_today_paris, today_paris

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
JSON_HEADERS = {"Accept": "application/json", "X-CSRFToken": CSRF}


def _programme(fake_db, jours):
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs", "reps": "8-12"}],
        "_planning": {JOURS[d.weekday()]: "Push" for d in jours},
        "_started_at": (logical_today_paris() - dt.timedelta(days=30)).isoformat(),
    }}).execute()


def _serie(client, date, **extra):
    data = {"_csrf": CSRF, "seance_name": "Push", "exo_base": "Développé couché",
            "variant": "Standard", "muscle": "Pecs", "date": date.isoformat(),
            "mode": "prefaite", "name": "Push", "partiel": "1",
            "sets_json": json.dumps([{"reps": 10, "poids": 60}])}
    data.update(extra)
    return client.post("/seance/save-exo", data=data, headers=JSON_HEADERS)


def _dates_en_base(fake_db):
    return sorted({r["date"] for r in fake_db.tables.get("history", [])})


# ── L'accueil ─────────────────────────────────────────────────────


def test_un_jour_de_repos_la_carte_ouvre_la_seance_daujourdhui(fake_db, logged_in):
    auj = logical_today_paris()
    demain = auj + dt.timedelta(days=1)
    _programme(fake_db, [demain])
    html = logged_in.get("/accueil", headers={"Sec-Fetch-Mode": "navigate"}).get_data(as_text=True)
    carte = re.search(r'<a href="([^"]+)" class="card next-session-card">(.*?)</a>', html, re.S)
    lien = carte.group(1).replace("&amp;", "&")
    assert f"date={auj.isoformat()}" in lien and f"prevue={demain.isoformat()}" in lien
    assert "Faire maintenant" in carte.group(2) and "Demain" in carte.group(2)


def test_le_jour_prevu_la_carte_dit_commencer_sans_bandeau(fake_db, logged_in):
    auj = logical_today_paris()
    _programme(fake_db, [auj])
    html = logged_in.get("/accueil", headers={"Sec-Fetch-Mode": "navigate"}).get_data(as_text=True)
    carte = re.search(r'<a href="([^"]+)" class="card next-session-card">(.*?)</a>', html, re.S)
    assert f"date={auj.isoformat()}" in carte.group(1) and "prevue=" not in carte.group(1)
    assert "Commencer" in carte.group(2)


def test_suivre_la_carte_enregistre_aujourdhui(fake_db, logged_in):
    """La reproduction RA de l'audit, à l'envers : même geste, bonne date."""
    auj = logical_today_paris()
    _programme(fake_db, [auj + dt.timedelta(days=1)])
    html = logged_in.get("/accueil", headers={"Sec-Fetch-Mode": "navigate"}).get_data(as_text=True)
    lien = re.search(r'<a href="([^"]+)" class="card next-session-card"', html).group(1).replace("&amp;", "&")
    page = logged_in.get(lien).get_data(as_text=True)
    date_page = re.search(r'name="date" value="([0-9-]+)"', page).group(1)
    assert date_page == auj.isoformat()
    assert _serie(logged_in, auj).status_code == 200
    assert _dates_en_base(fake_db) == [auj.isoformat()]


# ── La page de séance ─────────────────────────────────────────────


def test_la_page_daujourdhui_dit_en_avance_et_le_jour_prevu(fake_db, logged_in):
    auj = logical_today_paris()
    demain = auj + dt.timedelta(days=1)
    _programme(fake_db, [demain])
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={auj}&prevue={demain}").get_data(as_text=True)
    assert "EN AVANCE" in html and f"{demain.day:02d}/{demain.month:02d}" in html
    assert "RATTRAPAGE" not in html


def test_un_jour_passe_reste_un_rattrapage(fake_db, logged_in):
    auj = logical_today_paris()
    hier = auj - dt.timedelta(days=1)
    _programme(fake_db, [hier])
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={hier}").get_data(as_text=True)
    assert "RATTRAPAGE" in html


def test_une_page_a_venir_nest_pas_un_rattrapage_et_charge_le_garde(fake_db, logged_in):
    """Rendue telle quelle pour le cache hors-ligne : c'est le navigateur qui la
    ramène à aujourd'hui à l'ouverture (jour-seance.js, avant seance.js)."""
    demain = logical_today_paris() + dt.timedelta(days=1)
    _programme(fake_db, [demain])
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={demain}").get_data(as_text=True)
    visibles = re.sub(r'<div class="bandeau-avance" id="seance-en-avance" hidden>.*?</div>', "", html, flags=re.S)
    assert "RATTRAPAGE" not in visibles and "EN AVANCE" not in visibles
    assert html.index("/static/js/jour-seance.js") < html.index("/static/js/seance.js")
    assert 'id="seance-en-avance" hidden' in html


def test_prevue_est_ignore_sil_nest_pas_apres_la_date(fake_db, logged_in):
    auj = logical_today_paris()
    _programme(fake_db, [auj])
    hier = auj - dt.timedelta(days=1)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={auj}&prevue={hier}").get_data(as_text=True)
    visibles = re.sub(r'<div class="bandeau-avance" id="seance-en-avance" hidden>.*?</div>', "", html, flags=re.S)
    assert "EN AVANCE" not in visibles


# ── Le serveur refuse l'avance ────────────────────────────────────


def test_une_serie_datee_de_demain_est_refusee(fake_db, logged_in):
    demain = today_paris() + dt.timedelta(days=1)
    _programme(fake_db, [demain])
    r = _serie(logged_in, demain)
    assert r.status_code == 400 and "à venir" in r.get_json()["error"]
    assert _dates_en_base(fake_db) == []


def test_sans_javascript_le_refus_est_une_page_derreur(fake_db, logged_in):
    demain = today_paris() + dt.timedelta(days=1)
    _programme(fake_db, [demain])
    r = logged_in.post("/seance/save-exo", data={
        "_csrf": CSRF, "seance_name": "Push", "exo_base": "Développé couché", "variant": "Standard",
        "muscle": "Pecs", "date": demain.isoformat(), "mode": "prefaite", "name": "Push",
        "sets_json": json.dumps([{"reps": 10, "poids": 60}])}, headers={"X-CSRFToken": CSRF})
    assert r.status_code == 400 and _dates_en_base(fake_db) == []


def test_aujourdhui_et_hier_passent(fake_db, logged_in):
    auj = logical_today_paris()
    _programme(fake_db, [auj])
    assert _serie(logged_in, auj).status_code == 200
    assert _serie(logged_in, auj - dt.timedelta(days=2)).status_code == 200
    assert _dates_en_base(fake_db) == sorted([auj.isoformat(), (auj - dt.timedelta(days=2)).isoformat()])


def test_un_cardio_en_seance_date_de_demain_est_refuse(fake_db, logged_in):
    demain = today_paris() + dt.timedelta(days=1)
    _programme(fake_db, [demain])
    r = logged_in.post("/seance/add-cardio", data={
        "_csrf": CSRF, "seance_name": "Push", "date": demain.isoformat(), "activite": "Vélo",
        "duree_min": "10", "mode": "prefaite", "name": "Push"}, headers={"X-CSRFToken": CSRF})
    assert r.status_code == 400 and _dates_en_base(fake_db) == []


def test_la_page_cardio_dun_jour_a_venir_enregistre_aujourdhui(fake_db, logged_in):
    demain = today_paris() + dt.timedelta(days=1)
    html = logged_in.get(f"/cardio?date={demain}").get_data(as_text=True)
    assert f'value="{today_paris().isoformat()}"' in html
    assert f'value="{demain.isoformat()}"' not in html
    r = logged_in.post("/cardio/save", data={
        "_csrf": CSRF, "date": demain.isoformat(), "activite": "Vélo", "duree_min": "10"},
        headers={"X-CSRFToken": CSRF})
    assert r.status_code == 400 and _dates_en_base(fake_db) == []


def test_pas_de_bilan_date_dun_jour_a_venir(fake_db, logged_in):
    demain = today_paris() + dt.timedelta(days=1)
    _programme(fake_db, [demain])
    r = logged_in.post("/seance/finish", data={
        "_csrf": CSRF, "mode": "prefaite", "seance_name": "Push", "date": demain.isoformat(),
        "rating": "5", "comment": "top"}, headers={"X-CSRFToken": CSRF})
    assert r.status_code == 302
    assert fake_db.tables.get("session_notes", []) == []
