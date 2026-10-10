"""Stripe ne doit ni continuer à prélever un compte supprimé, ni oublier un
paiement parce qu'une écriture a échoué (audit du 30/09, C3 et I10)."""
import types

import pytest

from conftest import USER_ID, CSRF


def _faux_stripe(rec, abonnements, en_panne=False):
    def sub_list(**k):
        if en_panne:
            raise RuntimeError("Stripe indisponible")
        rec["list"] = k
        return {"data": abonnements}

    return types.SimpleNamespace(
        Subscription=types.SimpleNamespace(
            list=sub_list,
            modify=lambda sid, **k: rec.setdefault("modified", []).append((sid, k)),
            cancel=lambda sid: rec.setdefault("cancelled", []).append(sid),
        ),
        Customer=types.SimpleNamespace(list=lambda **k: {"data": []}),
    )


@pytest.fixture()
def abonne(fake_db):
    fake_db.table("profiles").insert(
        {"id": USER_ID, "tier": "vip", "stripe_customer_id": "cus_1"}).execute()
    return fake_db


def _supprimer(client):
    return client.post("/gestion/delete-account", data={"_csrf": CSRF, "confirm": "yes"})


# ── Suppression de compte ────────────────────────────────────────


def test_supprimer_son_compte_resilie_labonnement(abonne, logged_in, monkeypatch):
    import core.stripe_client as sc
    rec = {}
    monkeypatch.setattr(sc, "client", lambda: _faux_stripe(rec, [
        {"id": "sub_actif", "status": "active"},
        {"id": "sub_impaye", "status": "past_due"},
        {"id": "sub_fini", "status": "canceled"},
    ]))
    r = _supprimer(logged_in)
    assert r.status_code == 302
    assert rec["list"]["customer"] == "cus_1"
    assert sorted(rec["cancelled"]) == ["sub_actif", "sub_impaye"], \
        "tout abonnement encore capable de prélever est résilié, pas les autres"
    assert all(k["metadata"] == {"account_deleted": "1"} for _, k in rec["modified"])
    assert abonne.auth.admin.deleted_users == [USER_ID]


def test_si_stripe_ne_repond_pas_le_compte_nest_pas_supprime(abonne, logged_in, monkeypatch):
    """Mieux vaut un compte encore là qu'un prélèvement orphelin."""
    import core.stripe_client as sc
    monkeypatch.setattr(sc, "client", lambda: _faux_stripe({}, [], en_panne=True))
    r = _supprimer(logged_in)
    assert r.status_code == 502
    assert "pas pu être résilié" in r.get_data(as_text=True)
    assert abonne.auth.admin.deleted_users == []
    assert any(p["id"] == USER_ID for p in abonne.tables["profiles"])


def test_sans_stripe_configure_la_suppression_passe(abonne, logged_in, monkeypatch):
    import core.stripe_client as sc
    monkeypatch.setattr(sc, "client", lambda: None)
    assert _supprimer(logged_in).status_code == 302
    assert abonne.auth.admin.deleted_users == [USER_ID]


# ── Webhook ──────────────────────────────────────────────────────


def _webhook(client, monkeypatch, event):
    import routes.billing as billing
    fs = types.SimpleNamespace(Webhook=types.SimpleNamespace(construct_event=lambda p, s, sec: event))
    monkeypatch.setattr(billing, "_stripe", lambda: fs)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec")
    return client.post("/billing/webhook", data=b"{}", headers={"Stripe-Signature": "x"})


def test_le_webhook_demande_un_rejeu_si_lactivation_echoue(fake_db, client, monkeypatch):
    """Répondre 200 disait à Stripe « c'est fait » : il ne rejouait pas, et le
    payeur restait gratuit s'il avait fermé l'onglet avant /billing/success."""
    import core.db as db

    def panne(*a, **k):
        raise RuntimeError("Supabase indisponible")

    monkeypatch.setattr(db, "set_user_tier", panne)
    r = _webhook(client, monkeypatch, {"type": "checkout.session.completed", "data": {"object": {
        "client_reference_id": USER_ID, "customer": "cus_1", "metadata": {"user_id": USER_ID}}}})
    assert r.status_code == 500


def test_lannulation_dun_compte_supprime_ne_recree_pas_de_profil(fake_db, client, monkeypatch):
    r = _webhook(client, monkeypatch, {"type": "customer.subscription.deleted", "data": {"object": {
        "customer": "cus_1", "metadata": {"user_id": USER_ID, "account_deleted": "1"}}}})
    assert r.status_code == 200
    assert not any(p.get("id") == USER_ID for p in fake_db.tables.get("profiles", []))


def test_un_paiement_sans_compte_ne_passe_pas_en_silence(fake_db, client, monkeypatch, caplog):
    """Audit du 06/10 (4.1-5) : un paiement abouti qui n'active personne."""
    import logging
    caplog.set_level(logging.ERROR, logger="routes.billing")
    r = _webhook(client, monkeypatch, {"type": "checkout.session.completed", "data": {"object": {
        "id": "cs_1", "customer": "cus_9", "metadata": {}}}})
    assert r.status_code == 200
    assert any("paiement sans compte" in m for m in caplog.messages)
    ev = [e for e in fake_db.tables.get("events", []) if e["event"] == "paiement_sans_compte"]
    assert len(ev) == 1 and ev[0]["props"]["client"] == "cus_9"


def test_une_resiliation_laisse_une_trace(fake_db, client, monkeypatch):
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    r = _webhook(client, monkeypatch, {"type": "customer.subscription.deleted", "data": {"object": {
        "customer": "cus_1", "status": "canceled", "metadata": {"user_id": USER_ID}}}})
    assert r.status_code == 200
    ev = [e for e in fake_db.tables.get("events", []) if e["event"] == "vip_resilie"]
    assert len(ev) == 1 and ev[0]["user_id"] == USER_ID
