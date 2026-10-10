"""« Cette semaine » et le streak de l'accueil partent d'aujourd'hui.

Avant, les deux partaient de la dernière semaine où existait une ligne
d'historique. Après 47 jours d'arrêt, l'accueil affichait « Séances 1/1 ·
10 080 kg cette semaine » et « Streak 4 semaines · Palier Bronze » : aucun
reflet de l'effort réel, et aucune raison de revenir (audit du 30/09, R6).
"""
import datetime as dt

import pytest

from conftest import USER_ID
from routes.accueil import streak_semaines


# ── Le calcul, seul ──────────────────────────────────────────────


def test_streak_compte_depuis_la_semaine_en_cours():
    assert streak_semaines({8, 9, 10}, 10) == 3


def test_la_semaine_en_cours_encore_vide_ne_casse_pas_le_streak():
    """Lundi matin, rien n'est encore fait : le streak de la veille tient."""
    assert streak_semaines({8, 9}, 10) == 2


def test_une_semaine_entiere_sans_seance_casse_le_streak():
    assert streak_semaines({6, 7, 8}, 10) == 0


def test_un_trou_arrete_le_compte():
    assert streak_semaines({5, 6, 8, 9, 10}, 10) == 3


def test_aucun_historique():
    assert streak_semaines(set(), 10) == 0


# ── Sur la page ──────────────────────────────────────────────────


AUJOURDHUI = dt.date(2026, 9, 30)  # un mercredi


@pytest.fixture()
def fige_la_date(monkeypatch):
    import routes.accueil as accueil
    monkeypatch.setattr(accueil, "logical_today_paris", lambda: AUJOURDHUI)


def _compte(fake_db, derniere_seance, semaines=4):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Full": [{"name": "Squat", "sets": 3, "muscle": "Jambes"}],
        "_planning": {"Mercredi": "Full"}, "_settings": {},
        "_started_at": (derniere_seance - dt.timedelta(weeks=semaines + 1)).isoformat(),
    }}).execute()
    for k in range(semaines):
        jour = (derniere_seance - dt.timedelta(weeks=k)).isoformat()
        for serie in (1, 2, 3):
            fake_db.table("history").insert({
                "user_id": USER_ID, "date": jour, "semaine": "x",
                "seance": "Full", "exercice": "Squat", "muscle": "Jambes",
                "serie": serie, "reps": 8, "poids": 100.0}).execute()


def _stats(html):
    import re
    streak = re.search(r"(\d+) SEMAINE", html).group(1)
    volume = re.search(r'<div class="stat-value">([\d\s ]+)</div>\s*<div class="stat-sub">kg cette semaine',
                       html).group(1)
    return int(streak), int(volume.replace(" ", "").replace(" ", "").replace("\xa0", ""))


def test_apres_un_mois_darret_la_semaine_est_vide_et_le_streak_tombe(
        fake_db, logged_in, fige_la_date):
    _compte(fake_db, derniere_seance=dt.date(2026, 8, 14))
    streak, volume = _stats(logged_in.get("/accueil").get_data(as_text=True))
    assert volume == 0, "la dernière semaine active n'est pas « cette semaine »"
    assert streak == 0, "sept semaines sans séance : le streak est tombé"


def test_un_regulier_garde_son_streak_avant_sa_seance_de_la_semaine(
        fake_db, logged_in, fige_la_date):
    """Dernière séance mercredi dernier : cette semaine n'a encore rien, le
    streak de 4 semaines tient, le volume de la semaine est 0."""
    _compte(fake_db, derniere_seance=dt.date(2026, 9, 23))
    streak, volume = _stats(logged_in.get("/accueil").get_data(as_text=True))
    assert streak == 4
    assert volume == 0


def test_la_seance_du_jour_compte_dans_la_semaine(fake_db, logged_in, fige_la_date):
    _compte(fake_db, derniere_seance=AUJOURDHUI)
    streak, volume = _stats(logged_in.get("/accueil").get_data(as_text=True))
    assert streak == 4
    assert volume == 3 * 8 * 100
