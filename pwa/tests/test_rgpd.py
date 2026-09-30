"""Droits RGPD : export pour tous, effacement complet, politique exacte
(audit du 30/09, I12).

- L'export de ses données était réservé aux membres PRO, et la page de
  suppression de compte conseillait d'exporter… vers un mur de paiement.
- L'export oubliait la nutrition et les conversations du coach.
- La table `events` (mesure d'usage) survivait à la suppression du compte,
  alors que la politique promet « toutes tes données ».
- La politique disait « un seul cookie », « aucune donnée de localisation »,
  et oubliait Stripe, Brevo et Sentry.
"""
import json
import time
from pathlib import Path

import pytest

from conftest import USER_ID, CSRF

PWA = Path(__file__).resolve().parents[1]


@pytest.fixture()
def gratuit(fake_db, client):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free", "prenom": "Alex"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {}}}).execute()
    fake_db.table("history").insert({
        "user_id": USER_ID, "date": "2026-09-14", "semaine": 1, "seance": "Push",
        "exercice": "Développé couché", "serie": 1, "reps": 8, "poids": 80.0,
        "remarque": "", "muscle": "Pecs"}).execute()
    fake_db.table("nutrition").insert({
        "user_id": USER_ID, "date": "2026-09-14", "meal_type": "diner",
        "calories": 600, "protein": 40, "carbs": 60, "fat": 20, "note": "Poulet riz"}).execute()
    fake_db.table("coach_conversations").insert({
        "id": "c1", "user_id": USER_ID, "title": "Progresser", "updated_at": "2026-09-14"}).execute()
    fake_db.table("coach_messages").insert({
        "user_id": USER_ID, "conversation_id": "c1", "role": "user",
        "content": "Comment progresser ?", "created_at": "2026-09-14"}).execute()
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True, _csrf=CSRF,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time())
    return client


def test_un_compte_gratuit_peut_exporter_ses_donnees(gratuit):
    r = gratuit.get("/gestion/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["Content-Disposition"]
    d = json.loads(r.data)
    assert len(d["historique"]) == 1


def test_lexport_contient_la_nutrition_et_le_coach(gratuit):
    d = json.loads(gratuit.get("/gestion/export").data)
    assert d["nutrition"][0]["note"] == "Poulet riz"
    assert "user_id" not in d["nutrition"][0]
    assert d["coach"]["conversations"][0]["title"] == "Progresser"
    assert d["coach"]["messages"][0]["content"] == "Comment progresser ?"


def test_la_page_gestion_propose_lexport_a_un_gratuit(gratuit):
    html = gratuit.get("/gestion").get_data(as_text=True)
    assert 'href="/gestion/export"' in html
    assert 'action="/gestion/import"' not in html, "la réimportation reste PRO"


def test_supprimer_son_compte_efface_aussi_la_mesure_dusage(gratuit, fake_db, monkeypatch):
    import core.stripe_client as sc
    monkeypatch.setattr(sc, "client", lambda: None)
    fake_db.table("events").insert({"user_id": USER_ID, "event": "workout_finished", "props": {}}).execute()
    fake_db.table("events").insert({"user_id": "autre", "event": "workout_finished", "props": {}}).execute()
    r = gratuit.post("/gestion/delete-account", data={"_csrf": CSRF, "confirm": "yes"})
    assert r.status_code == 302
    restants = [e["user_id"] for e in fake_db.tables.get("events", [])]
    assert restants == ["autre"]


def test_la_politique_dit_ce_que_lapp_fait():
    txt = (PWA / "templates" / "confidentialite.html").read_text(encoding="utf-8")
    for tiers in ("Stripe", "Brevo", "Sentry", "Open Food Facts"):
        assert tiers in txt, f"sous-traitant absent : {tiers}"
    assert "Un seul cookie" not in txt
    assert "Aucune donnée de localisation" not in txt
    assert "membres Premium) ou sur demande" not in txt
    faq = (PWA / "templates" / "faq.html").read_text(encoding="utf-8")
    assert "ne peut pas toucher à ta <strong>caméra, ton micro ni ta position" not in faq


# ── Pages légales ────────────────────────────────────────────────


@pytest.mark.parametrize("page", ["/mentions-legales", "/cgv"])
def test_les_pages_legales_sont_publiques(page, fake_db, client):
    """On doit pouvoir les lire avant de créer un compte ou de payer."""
    r = client.get(page)
    assert r.status_code == 200
    assert "Paul Moraux" in r.get_data(as_text=True)


def test_mentions_legales_sans_adresse_ne_montrent_pas_de_faux(fake_db, client, monkeypatch):
    monkeypatch.delenv("EDITEUR_ADRESSE", raising=False)
    html = client.get("/mentions-legales").get_data(as_text=True)
    assert "communiquée sur simple demande" in html
    assert "Supabase Pte. Ltd." in html and "Railway" in html


def test_mentions_legales_avec_adresse(fake_db, client, monkeypatch):
    monkeypatch.setenv("EDITEUR_ADRESSE", "12 rue de l'Exemple, 75000 Paris")
    html = client.get("/mentions-legales").get_data(as_text=True)
    assert "12 rue de l&#39;Exemple, 75000 Paris" in html


def test_les_cgv_disent_les_prix_et_la_retractation(fake_db, client):
    html = client.get("/cgv").get_data(as_text=True)
    for prix in ("4,99", "39,99", "79,99"):
        assert prix in html
    assert 'id="retractation"' in html and "14 jours" in html


def test_la_page_pro_renvoie_aux_cgv(gratuit):
    html = gratuit.get("/premium").get_data(as_text=True)
    assert 'href="/cgv"' in html and 'href="/cgv#retractation"' in html
