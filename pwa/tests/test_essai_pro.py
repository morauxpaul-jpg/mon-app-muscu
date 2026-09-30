"""L'essai PRO (parrainage, promo : `vip_until`) peut acheter.

Il ouvre Nutrition et les stats, pas le Coach. Mais tout ce qui affichait le
statut lisait `is_vip`, qui compte l'essai : la page PRO lui disait « Tu es
VIP — Toutes les features premium sont débloquées », « ✓ Débloqué à vie »,
sans un seul bouton d'achat, pendant que le Coach lui restait fermé. Ce sont
les comptes arrivés par recommandation — les plus chauds (audit du 30/09, R5).
"""
import datetime as dt

import pytest

from conftest import USER_ID, CSRF


def _session_essai(client, heures=20):
    import core.db as db
    fin = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=heures)).isoformat()
    db.get_client().table("profiles").insert(
        {"id": USER_ID, "tier": "free", "vip_until": fin}).execute()
    db.get_client().table("onboarding").insert(
        {"user_id": USER_ID, "completed_at": "2026-01-01"}).execute()
    with client.session_transaction() as s:
        s["user_id"] = USER_ID
        s["email"] = "t@e.com"
        s["onboarded"] = True
        s["_csrf"] = CSRF
    return client


@pytest.fixture()
def essai(fake_db, client):
    return _session_essai(client)


def test_la_page_pro_propose_lachat_a_lessai(essai):
    html = essai.get("/premium").get_data(as_text=True)
    assert 'action="/billing/checkout"' in html
    assert "Tu es VIP" not in html
    assert "Débloqué à vie" not in html
    assert "Inclus dans ton accès" not in html


def test_lessai_voit_quand_il_finit(essai):
    html = essai.get("/premium").get_data(as_text=True)
    assert "Essai PRO — encore" in html
    plus = essai.get("/plus").get_data(as_text=True)
    assert "Essai PRO · encore" in plus
    assert "Membre PRO" not in plus


def test_la_barre_dit_essai_et_non_pro(essai):
    html = essai.get("/plus").get_data(as_text=True)
    barre = html.split("topbar-user", 1)[1].split("</span></span>", 1)[0]
    assert "ESSAI" in barre and ">PRO<" not in barre


def test_le_payant_garde_son_statut(fake_db, logged_in):
    html = logged_in.get("/premium").get_data(as_text=True)
    assert "Tu es VIP" in html
    assert "Essai PRO" not in html
    assert "Membre PRO" in logged_in.get("/plus").get_data(as_text=True)


def test_un_gratuit_na_pas_de_bandeau_essai(fake_db, client):
    import time
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True, _csrf=CSRF,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time())
    html = client.get("/premium").get_data(as_text=True)
    assert "Essai PRO" not in html
    assert 'action="/billing/checkout"' in html


def test_essai_restant():
    from core.db import essai_restant
    t0 = dt.datetime(2026, 9, 30, 12, tzinfo=dt.timezone.utc)
    iso = lambda h: (t0 + dt.timedelta(hours=h)).isoformat()
    assert essai_restant(iso(20), t0) == "encore 20 h"
    assert essai_restant(iso(0.5), t0) == "moins d'une heure"
    assert essai_restant(iso(24 * 5), t0) == "encore 5 jours"
    assert essai_restant(iso(-1), t0) is None
    assert essai_restant(None, t0) is None


def test_un_essai_fini_se_referme_a_lheure(fake_db, client):
    """Le statut VIP est gardé en session longtemps (TTL des VIP) : sans
    revérification à l'échéance, l'essai durait au-delà de sa fin."""
    import time
    import core.db as db
    passe = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)).isoformat()
    db.get_client().table("profiles").insert(
        {"id": USER_ID, "tier": "free", "vip_until": passe}).execute()
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True, _csrf=CSRF,
                 is_vip=True, is_vip_full=False, is_vip_ts=time.time(),
                 vip_until=passe)
    html = client.get("/plus").get_data(as_text=True)
    assert "Essai PRO" not in html
    assert "Passe en PRO" in html
