"""Style « Instrument », PR 3c (13/10/2026) : choix de la séance, Programme,
fiche exercice. Ce que les écrans disent, pas leur couleur."""
import datetime as dt
import re

from conftest import USER_ID
from core.dates import continuous_week, logical_today_paris


def _prog(fake):
    fake.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 4, "muscle": "Pecs"},
                 {"name": "Dips", "sets": 3, "muscle": "Triceps"}],
        "Pull": [{"name": "Tractions", "sets": 4, "muscle": "Dos"}],
        "_planning": {"Lundi": "Push", "Mercredi": "Pull"}, "_settings": {},
    }}).execute()


def _serie(fake, jour, poids, reps=8, exo="Développé couché", seance="Push"):
    fake.table("history").insert({
        "user_id": USER_ID, "semaine": continuous_week(jour), "seance": seance,
        "exercice": exo, "serie": 1, "reps": reps, "poids": poids,
        "remarque": "", "muscle": "Pecs", "date": jour.isoformat(),
    }).execute()


def _hero(html):
    return re.search(r'<div class="choix-hero">(.*?)</h1>', html, re.S).group(1)


def test_choix_d_un_jour_fait_le_nom_en_titre_l_etat_sur_la_date(fake_db, logged_in):
    _prog(fake_db)
    jour = logical_today_paris() - dt.timedelta(days=3)
    _serie(fake_db, jour, 80)
    html = logged_in.get(f"/seance?date={jour.isoformat()}").get_data(as_text=True)
    hero = _hero(html)
    assert '<span class="choix-etat choix-etat--faite">RÉALISÉE</span>' in hero
    assert '<h1 class="choix-titre">Push' in hero
    # Plus de « RÉALISÉE » répété sous le titre.
    assert html.count("RÉALISÉE") == 1
    lien = html.split('class="choix-encadre"')[0].rsplit("<a ", 1)[1]
    assert "mode=prefaite&amp;name=Push" in lien or "mode=prefaite&name=Push" in lien
    assert "Voir la séance" in html


def test_choix_d_un_jour_manque_l_etat_en_orange_sur_la_date(fake_db, logged_in):
    _prog(fake_db)
    jour = logical_today_paris() - dt.timedelta(days=3)
    hero = _hero(logged_in.get(f"/seance?date={jour.isoformat()}").get_data(as_text=True))
    assert '<span class="choix-etat choix-etat--manquee">MANQUÉE</span>' in hero
    assert '<h1 class="choix-titre">Quelle séance ?' in hero


def test_choix_d_aujourd_hui_sans_etat(fake_db, logged_in):
    _prog(fake_db)
    hero = _hero(logged_in.get("/seance?date=" + logical_today_paris().isoformat()).get_data(as_text=True))
    assert "choix-etat" not in hero
    assert "Quelle séance aujourd&#39;hui ?" in hero or "Quelle séance aujourd'hui ?" in hero


def test_programme_la_semaine_en_sept_cases(fake_db, logged_in):
    _prog(fake_db)
    html = logged_in.get("/programme").get_data(as_text=True)
    assert html.count('<label class="prog-jour"') == 7
    for abr in ("LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"):
        assert f'<span class="prog-jour-abbr" aria-hidden="true">{abr}</span>' in html
    # Chaque case garde son vrai menu, nommé par le jour (lecteur d'écran).
    assert 'data-day="Mercredi" aria-label="Mercredi"' in html
    # La ligne sous chaque séance vient de programme.js.
    assert 'x-text="resumeSeance(sname)"' in html
    assert 'role="switch"' in html


def test_filtre_jour_mois(client):
    f = client.application.jinja_env.filters["jour_mois"]
    assert f("2026-05-04") == "4 mai"
    assert f("2026-12-25T10:00:00") == "25 déc."
    assert f("") == "" and f(None) == ""


def test_fiche_exercice_la_force_estimee_en_tete_et_ce_qu_elle_a_gagne(fake_db, logged_in):
    _prog(fake_db)
    auj = logical_today_paris()
    _serie(fake_db, auj - dt.timedelta(days=14), 80, reps=8)    # 1RM 101,3
    _serie(fake_db, auj - dt.timedelta(days=7), 85, reps=8)     # 1RM 107,7
    html = logged_in.get("/progres/exercice?exo=D%C3%A9velopp%C3%A9%20couch%C3%A9&p=tout").get_data(as_text=True)
    hero = html.split('<div class="exo-hero">')[1].split('<div class="pr-grid')[0]
    assert "Force estimée · 1RM" in hero
    assert "107,7<span>kg</span>" in hero
    assert "+6&nbsp;%" in hero and "exo-hero-delta--gain" in hero
    debut = auj - dt.timedelta(days=14)
    assert f"depuis le {debut.day} " in hero
    cases = html.split('<div class="pr-grid pr-grid--3">')[1].split("{# ")[0]
    assert cases.count('class="pr-card"') == 3
    for libelle in ("Charge max", "Volume max", "Total"):
        assert f'<div class="pr-label">{libelle}</div>' in cases
