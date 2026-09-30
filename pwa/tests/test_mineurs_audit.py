"""Points mineurs de l'audit du 30/09 : chacun tient par un test."""
import time
from pathlib import Path

import pytest

from conftest import USER_ID, CSRF

PWA = Path(__file__).resolve().parents[1]


def _tpl(nom):
    return (PWA / "templates" / nom).read_text(encoding="utf-8")


# ── M12 : pas de fausse rareté, pas de promesse fausse ───────────


def test_pas_de_fausse_rarete_ni_de_ton_exclusif():
    assert "100 premiers" not in _tpl("premium.html")
    assert "guerrier" not in _tpl("onboarding.html")
    assert "Soutien le" not in _tpl("premium.html")


def test_sans_publicite_ne_se_vend_que_la_ou_il_y_en_a():
    """Le web n'a pas de publicité : la vendre comme avantage était faux."""
    for nom in ("premium.html", "vip_wall.html"):
        for ligne in _tpl(nom).splitlines():
            if "Sans publicité" in ligne:
                assert "Android" in ligne, ligne.strip()


# ── M2 : pas de texte d'exception chez l'utilisateur ─────────────


def test_un_jeton_refuse_ne_renvoie_pas_le_detail(fake_db, client, monkeypatch):
    import jwt
    import routes.auth as auth

    def refuse(tok):
        raise jwt.InvalidTokenError("Signature verification failed for kid=abc123")

    monkeypatch.setattr(auth, "_verify_supabase_jwt", refuse)
    r = client.post("/auth/session", json={"access_token": "x"})
    assert r.status_code == 401
    assert "kid=abc123" not in r.get_data(as_text=True)


def test_laccueil_ne_montre_pas_lexception(fake_db, logged_in, monkeypatch):
    import routes.accueil as accueil

    def panne():
        raise RuntimeError("postgrest APIError: relation public.history timeout 57014")

    monkeypatch.setattr(accueil, "get_hist", panne)
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert "57014" not in html and "postgrest" not in html
    assert "Réessaie" in html


# ── M3 : déconnexion en POST seulement ───────────────────────────


def test_un_lien_ne_deconnecte_pas(fake_db, logged_in):
    r = logged_in.get("/logout")
    assert r.status_code == 405
    with logged_in.session_transaction() as s:
        assert s.get("user_id") == USER_ID


def test_le_bouton_deconnecte(fake_db, logged_in):
    r = logged_in.post("/logout", data={"_csrf": CSRF})
    assert r.status_code == 302
    with logged_in.session_transaction() as s:
        assert "user_id" not in s


# ── M8 : « Commencer » ouvre la séance ───────────────────────────


def test_commencer_ouvre_la_seance_du_jour(fake_db, logged_in, monkeypatch):
    import datetime as dt
    import routes.accueil as accueil
    lundi = dt.date(2026, 9, 28)
    monkeypatch.setattr(accueil, "logical_today_paris", lambda: lundi)
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Full Body A": [{"name": "Squat", "sets": 3, "muscle": "Jambes"}],
        "_planning": {"Lundi": "Full Body A"}, "_settings": {}}}).execute()
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert 'href="/seance?mode=prefaite&name=Full%20Body%20A&date=2026-09-28"' in html
