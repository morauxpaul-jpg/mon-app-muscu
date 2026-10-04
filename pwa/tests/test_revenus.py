"""Revenus (audit du 03/10 : M6, M7, M12, M13).

* M7 : un achat remboursé ou contesté retire PRO ; un litige gagné le rend.
* M6 : jamais de pubs de TEST en production sans le dire — coupées, journal
  critique, alerte dans la console admin.
* M13 : la vidéo PRO se lance au tap, pas toute seule.
* M12 : l'image de 1,1 Mo que rien n'utilisait n'est plus déployée.
"""
import logging
import types
from pathlib import Path

import pytest

from conftest import USER_ID
from core import admob, stripe_remboursements as remb

PWA = Path(__file__).resolve().parent.parent


def _profil(fake, tier="vip", customer="cus_1"):
    fake.table("profiles").insert({"id": USER_ID, "tier": tier, "stripe_customer_id": customer}).execute()


def _tier(fake):
    return next(p for p in fake.tables["profiles"] if p["id"] == USER_ID)["tier"]


class FauxStripe:
    """Le minimum de l'API Stripe que lisent les remboursements."""

    def __init__(self, abonnements=(), charges=None):
        self.Subscription = types.SimpleNamespace(
            list=lambda **k: {"data": list(abonnements)})
        self.Charge = types.SimpleNamespace(retrieve=lambda cid: (charges or {})[cid])


def _webhook(client, monkeypatch, event, fs=None):
    import routes.billing as billing
    fs = fs or FauxStripe()
    fs.Webhook = types.SimpleNamespace(construct_event=lambda p, s, sec: event)
    monkeypatch.setattr(billing, "_stripe", lambda: fs)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec")
    return client.post("/billing/webhook", data=b"{}", headers={"Stripe-Signature": "x"})


# ── Remboursements et litiges (M7) ───────────────────────────────

def test_un_achat_a_vie_rembourse_retire_pro(fake_db, client, monkeypatch):
    _profil(fake_db)
    r = _webhook(client, monkeypatch, {"type": "charge.refunded", "data": {"object": {
        "customer": "cus_1", "amount": 7999, "amount_refunded": 7999, "refunded": True}}})
    assert r.status_code == 200
    assert _tier(fake_db) == "free"


def test_un_remboursement_partiel_ne_change_rien(fake_db, client, monkeypatch):
    _profil(fake_db)
    _webhook(client, monkeypatch, {"type": "charge.refunded", "data": {"object": {
        "customer": "cus_1", "amount": 3999, "amount_refunded": 1000, "refunded": False}}})
    assert _tier(fake_db) == "vip"


def test_un_geste_sur_une_mensualite_ne_coupe_pas_labonnement_en_cours(fake_db, client, monkeypatch):
    _profil(fake_db)
    _webhook(client, monkeypatch, {"type": "charge.refunded", "data": {"object": {
        "customer": "cus_1", "amount": 499, "amount_refunded": 499, "refunded": True}}},
        FauxStripe(abonnements=[{"id": "sub_1"}]))
    assert _tier(fake_db) == "vip"


def test_un_litige_ouvert_suspend_pro_et_un_litige_gagne_le_rend(fake_db, client, monkeypatch):
    _profil(fake_db)
    fs = FauxStripe(charges={"ch_1": {"customer": "cus_1"}})
    r = _webhook(client, monkeypatch, {"type": "charge.dispute.created", "data": {"object": {
        "charge": "ch_1", "reason": "fraudulent"}}}, fs)
    assert r.status_code == 200 and _tier(fake_db) == "free"
    _webhook(client, monkeypatch, {"type": "charge.dispute.closed", "data": {"object": {
        "charge": "ch_1", "status": "won"}}}, fs)
    assert _tier(fake_db) == "vip"


def test_un_litige_perdu_laisse_le_compte_gratuit(fake_db, client, monkeypatch):
    _profil(fake_db, tier="free")
    _webhook(client, monkeypatch, {"type": "charge.dispute.closed", "data": {"object": {
        "charge": "ch_1", "status": "lost"}}}, FauxStripe(charges={"ch_1": {"customer": "cus_1"}}))
    assert _tier(fake_db) == "free"


def test_un_paiement_dun_client_inconnu_ne_touche_personne(fake_db, client, monkeypatch):
    _profil(fake_db)
    r = _webhook(client, monkeypatch, {"type": "charge.refunded", "data": {"object": {
        "customer": "cus_inconnu", "amount": 7999, "amount_refunded": 7999, "refunded": True}}})
    assert r.status_code == 200 and _tier(fake_db) == "vip"


def test_une_panne_de_base_fait_rejouer_le_webhook(fake_db, client, monkeypatch):
    import core.db as db
    _profil(fake_db)

    def panne(*a, **k):
        raise RuntimeError("Supabase indisponible")
    monkeypatch.setattr(db, "set_user_tier", panne)
    r = _webhook(client, monkeypatch, {"type": "charge.refunded", "data": {"object": {
        "customer": "cus_1", "amount": 7999, "amount_refunded": 7999, "refunded": True}}})
    assert r.status_code == 500


def test_le_compte_designe_par_metadata_prime():
    assert remb._utilisateur(None, {"metadata": {"user_id": "u-42"}, "customer": "cus_x"}) == "u-42"


# ── AdMob (M6) ───────────────────────────────────────────────────

VRAIE_BANNIERE = "ca-app-pub-1234567890123456/1111111111"
VRAI_INTER = "ca-app-pub-1234567890123456/2222222222"


def test_en_local_les_identifiants_de_test_restent_le_defaut():
    ids = admob.identifiants(False, {})
    assert ids["etat"] == "test" and ids["banner"] == admob.TEST_BANNIERE


def test_en_production_sans_vrais_identifiants_les_pubs_sont_coupees(caplog):
    with caplog.at_level(logging.CRITICAL):
        ids = admob.verifier_au_demarrage(True, {})
    assert ids == {"banner": "", "interstitial": "", "etat": "coupe"}
    assert "COUPÉES" in caplog.text


def test_des_identifiants_de_test_en_production_sont_traites_comme_absents():
    ids = admob.identifiants(True, {"ADMOB_BANNER_ID": admob.TEST_BANNIERE,
                                    "ADMOB_INTERSTITIAL_ID": admob.TEST_INTERSTITIEL})
    assert ids["etat"] == "coupe"


def test_les_vrais_identifiants_passent():
    ids = admob.identifiants(True, {"ADMOB_BANNER_ID": VRAIE_BANNIERE, "ADMOB_INTERSTITIAL_ID": VRAI_INTER})
    assert ids == {"banner": VRAIE_BANNIERE, "interstitial": VRAI_INTER, "etat": "reel"}


def test_un_interstitiel_de_test_seul_est_desactive():
    ids = admob.identifiants(True, {"ADMOB_BANNER_ID": VRAIE_BANNIERE,
                                    "ADMOB_INTERSTITIAL_ID": admob.TEST_INTERSTITIEL})
    assert ids["banner"] == VRAIE_BANNIERE and ids["interstitial"] == ""


def test_admob_test_autorise_sciemment_les_pubs_de_test():
    assert admob.identifiants(True, {"ADMOB_TEST": "1"})["etat"] == "test"


def test_la_console_admin_signale_des_pubs_coupees(fake_db):
    from flask import render_template
    import app as appmod
    with appmod.app.test_request_context("/admin"):
        html = render_template("admin.html", users=[], vip_count=0, total_count=0,
                               current_email="a@b.c", admob="coupe",
                               stats={"total_rows": 0, "total_tonnage": 0, "total_seances": 0,
                                      "active_7d": 0, "active_30d": 0})
    assert "Pubs AdMob coupées" in html


def test_les_pages_recoivent_des_identifiants_vides_quand_les_pubs_sont_coupees(fake_db, client, monkeypatch):
    import time
    import app as appmod
    from conftest import CSRF
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {"_settings": {}}}).execute()
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True, is_vip=False,
                 is_vip_full=False, is_vip_ts=time.time(), _csrf=CSRF)
    monkeypatch.setattr(appmod, "_admob_ids", {"banner": "", "interstitial": "", "etat": "coupe"})
    html = client.get("/accueil").get_data(as_text=True)
    assert 'window.__ADS__ = {"banner": "", "interstitial": ""}' in html


# ── Vidéo au tap (M13) et média mort (M12) ───────────────────────

@pytest.mark.parametrize("page", ["vip_wall.html", "premium.html"])
def test_la_video_pro_se_lance_au_tap(page):
    src = (PWA / "templates" / page).read_text(encoding="utf-8")
    balise = src[src.index("<video"):src.index(">", src.index("<video"))]
    assert "autoplay" not in balise and "controls" in balise and 'preload="none"' in balise


def test_limage_de_1_mo_inutilisee_nest_plus_deployee():
    assert not (PWA / "static" / "promo-vip-poster.png").exists()
