"""Journée logique du serveur aux nuits de changement d'heure.

Avant 4 h à l'horloge de Paris, c'est encore la veille (`logical_today_paris`).
Le navigateur fait le même calcul (static/js/jour-seance.js, base.html,
seance_choix.html) ; tests/js/test_jour_seance.js vérifie qu'il rend, pour les
MÊMES instants, les mêmes jours qu'ici. Le 25/10/2026 à 02 h 13 UTC, le
navigateur disait le 25 et le serveur le 24 : la page de séance se datait du
lendemain.
"""
import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import dates  # noqa: E402

# Instant UTC → journée logique attendue. Mêmes valeurs que test_jour_seance.js.
CAS = [
    # Passage à l'heure d'hiver : 03 h heure d'été redevient 02 h.
    ("2026-10-25T00:30:00", "2026-10-24"),  # 02 h 30 heure d'été
    ("2026-10-25T01:30:00", "2026-10-24"),  # 02 h 30 heure d'hiver
    ("2026-10-25T02:13:00", "2026-10-24"),  # 03 h 13 heure d'hiver
    ("2026-10-25T03:00:00", "2026-10-25"),  # 04 h 00 heure d'hiver
    # Passage à l'heure d'été : 02 h heure d'hiver saute à 03 h.
    ("2026-03-29T00:30:00", "2026-03-28"),  # 01 h 30 heure d'hiver
    ("2026-03-29T01:30:00", "2026-03-28"),  # 03 h 30 heure d'été
    ("2026-03-29T02:00:00", "2026-03-29"),  # 04 h 00 heure d'été
    ("2026-03-29T02:30:00", "2026-03-29"),  # 04 h 30 heure d'été
    ("2026-03-30T00:30:00", "2026-03-29"),  # lendemain, 02 h 30
]


@pytest.mark.parametrize("instant_utc,attendu", CAS)
def test_journee_logique_aux_changements_dheure(monkeypatch, instant_utc, attendu):
    instant = dt.datetime.fromisoformat(instant_utc).replace(tzinfo=dt.timezone.utc)
    monkeypatch.setattr(dates, "now_paris", lambda: instant.astimezone(dates.PARIS_TZ))
    assert dates.logical_today_paris().isoformat() == attendu
