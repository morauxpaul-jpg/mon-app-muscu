"""La page PRO ne promet que ce que le code fait (audit du 03/10, I10).

Elle vendait comme PRO deux programmes gratuits (PPL 3 j, Upper/Lower 4 j),
des « profils » retirés le 01/10, et un « Badge VIP doré » qui n'existe
nulle part ; et elle taisait le debrief après chaque séance."""
import re

from core import catalog


def _page(client):
    return client.get("/premium").get_data(as_text=True)


def test_rien_qui_nexiste_pas(fake_db, logged_in):
    html = _page(logged_in)
    for promesse in ("Badge VIP doré", "profils", "(PPL, Upper/Lower"):
        assert promesse not in html, promesse


def test_le_nombre_de_programmes_pro_est_celui_du_catalogue(fake_db, logged_in):
    n_pro = len(catalog.CATALOG) - len(catalog.FREE_PROGRAMS)
    assert f"{n_pro} programmes avancés" in _page(logged_in)


def test_le_debrief_est_annonce(fake_db, logged_in):
    html = _page(logged_in)
    assert "Debrief du coach après chaque séance" in html
    assert "1 debrief du coach par semaine" in html


def test_lonboarding_ne_dit_plus_que_ppl_et_upper_lower_sont_pro(fake_db, client):
    import time
    from conftest import USER_ID, CSRF
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=False, is_vip=False,
                 is_vip_full=False, is_vip_ts=time.time(), _csrf=CSRF)
    html = client.get("/onboarding").get_data(as_text=True)
    assert "(PPL, Upper/Lower" not in html
