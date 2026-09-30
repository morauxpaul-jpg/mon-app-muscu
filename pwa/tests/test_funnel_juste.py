"""Le funnel compte ce qui s'est passé (audit du 30/09, I11).

- Toucher quatre cartes de « Plus » sans cliquer enregistrait quatre
  « offre vue » : le préchargement des liens comptait comme des visites (R13).
- Une séance « terminée » sans une seule série comptait comme faite (R1).
- `auth.admin.list_users()` sans pagination ne rend que la première page
  (50 comptes) : liste admin et haut du funnel tronqués.
"""
import time
import types

import pytest

from conftest import USER_ID, CSRF


def _events(fake, nom=None):
    return [e for e in fake.tables.get("events", []) if nom is None or e["event"] == nom]


@pytest.fixture()
def gratuit(fake_db, client):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {}}}).execute()
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True, _csrf=CSRF,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time())
    return client


# ── Préchargement ────────────────────────────────────────────────


@pytest.mark.parametrize("entetes", [
    {"Sec-Fetch-Mode": "same-origin"},   # fetch() de prefetch.js
    {"X-Prefetch": "1"},                 # navigateurs sans Sec-Fetch-Mode
])
def test_un_prechargement_nest_pas_une_offre_vue(fake_db, gratuit, entetes):
    gratuit.get("/coach", headers=entetes)
    gratuit.get("/premium", headers=entetes)
    assert _events(fake_db, "paywall_viewed") == []
    assert _events(fake_db, "premium_viewed") == []


def test_une_vraie_visite_compte(fake_db, gratuit):
    gratuit.get("/coach", headers={"Sec-Fetch-Mode": "navigate"})
    gratuit.get("/premium", headers={"Sec-Fetch-Mode": "navigate"})
    assert len(_events(fake_db, "paywall_viewed")) == 1
    assert len(_events(fake_db, "premium_viewed")) == 1


def test_prefetch_js_se_signale():
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "static/js/prefetch.js").read_text(encoding="utf-8")
    assert '"X-Prefetch": "1"' in js


# ── Séance vide ──────────────────────────────────────────────────


def _terminer(client):
    return client.post("/seance/finish", data={
        "_csrf": CSRF, "mode": "prefaite", "seance_name": "Push", "date": "2026-09-28"})


def test_une_seance_vide_nest_pas_une_seance_faite(fake_db, gratuit):
    assert _terminer(gratuit).status_code == 302
    assert _events(fake_db, "workout_finished") == []
    assert len(_events(fake_db, "workout_finished_empty")) == 1
    with gratuit.session_transaction() as s:
        assert "last_workout" not in s, "pas de debrief pour une séance vide"


def test_une_vraie_seance_compte(fake_db, gratuit):
    fake_db.table("history").insert({
        "user_id": USER_ID, "date": "2026-09-28", "semaine": 1, "seance": "Push",
        "exercice": "Développé couché", "serie": 1, "reps": 8, "poids": 80.0,
        "remarque": "", "muscle": "Pecs"}).execute()
    _terminer(gratuit)
    assert len(_events(fake_db, "workout_finished")) == 1


# ── Comptes au-delà de la première page ──────────────────────────


def test_la_liste_admin_lit_toutes_les_pages(fake_db):
    import core.db as db
    pages = {1: [types.SimpleNamespace(id=f"u{i}", email=f"{i}@x", created_at="2026-09-01")
                 for i in range(1000)],
             2: [types.SimpleNamespace(id="u-der", email="der@x", created_at="2026-09-02")]}
    fake_db.auth.admin.list_users = lambda page=1, per_page=50: pages.get(page, [])
    users = db.list_all_users_with_tier()
    assert len(users) == 1001
    assert any(u["id"] == "u-der" for u in users)
