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


# ── Scripts et styles versionnés par déploiement ─────────────────


def test_les_scripts_et_styles_portent_la_version_du_deploiement(fake_db, logged_in):
    """Le SW sert JS et CSS cache d'abord : sans version dans l'URL, la
    première page après un déploiement mélangeait nouveau HTML et ancien
    script (une séance pouvait s'ouvrir cassée)."""
    import re
    import app as appmod
    html = logged_in.get("/accueil").get_data(as_text=True)
    assets = re.findall(r'(?:src|href)="(/static/[^"]+\.(?:js|css)[^"]*)"', html)
    assert assets
    for a in assets:
        assert a.endswith(f"?v={appmod._ASSET_BUILD}"), a
    # Les icônes et images ne sont pas concernées (fragments #id conservés).
    assert 'href="/static/img/icons.svg#' in html


def test_hors_ligne_le_sw_se_rabat_sur_une_version_gardee():
    sw = (PWA / "static" / "service-worker.js").read_text(encoding="utf-8")
    assert "ignoreSearch: true" in sw


def test_la_page_de_connexion_ne_charge_rien_dun_cdn():
    for nom in ("login.html", "bridge.html"):
        t = _tpl(nom)
        assert "cdn.jsdelivr" not in t and "unpkg" not in t
        assert "/static/vendor/supabase-js-" in t
    assert list((PWA / "static" / "vendor").glob("supabase-js-*.umd.js"))


# ── M4 : une seule copie de chaque chose ─────────────────────────


def test_env_na_quune_definition():
    import routes.auth as auth
    import core.db_base as base
    assert auth._env is base._env


def test_progres_utilise_la_normalisation_commune():
    """Un exercice du programme sans muscle renseigné n'efface plus celui de
    l'historique (c'est ce que faisait la copie de routes/progres.py)."""
    from routes.progres import _normalize
    hist = [{"Exercice": "Squat", "Muscle": "Quadriceps", "Reps": 5, "Poids": 100.0,
             "Semaine": 1, "Séance": "A", "Série": 1, "Remarque": "", "Date": "2026-09-01"}]
    prog = {"A": [{"name": "Squat", "sets": 3, "muscle": ""}]}
    assert _normalize(hist, prog)[0]["Muscle"] == "Quadriceps"


def test_les_medias_marketing_ne_sont_pas_servis():
    """5,4 Mo déployés et servis sans qu'aucune page ne s'en serve (M11)."""
    assert not (PWA / "static" / "promo").exists()
    assert not (PWA / "static" / "promo-vip.mp4").exists()
    assert (PWA / "static" / "promo-vip-motion.mp4").exists(), "celle-là, la page PRO s'en sert"
