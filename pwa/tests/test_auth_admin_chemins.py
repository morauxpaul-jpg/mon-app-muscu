"""Connexion et console admin : les chemins qui n'étaient pas testés (I14).

La connexion décide QUI est l'utilisateur ; la console admin peut changer le
tier de n'importe quel compte. Les deux étaient couverts à moins de 50 %
(audit du 03/10). On teste ici ce qu'un défaut coûterait : un jeton mal
vérifié, une session qui garde des restes d'un autre compte, une action admin
ouverte à un non-admin, un secret qui fuit dans une page.
"""
import datetime as dt
import types

import jwt
import pytest

from conftest import CSRF, USER_ID
import routes.auth as auth

SECRET = "secret-de-test-assez-long-pour-hs256-0123456789"


def _jeton(secret=SECRET, alg="HS256", **charge):
    base = {"sub": USER_ID, "email": "a@b.fr", "aud": "authenticated",
            "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5),
            "app_metadata": {"providers": ["google"]}}
    base.update(charge)
    return jwt.encode({k: v for k, v in base.items() if v is not None}, secret, algorithm=alg)


@pytest.fixture()
def env_auth(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setenv("SUPABASE_URL", "https://projet.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "cle-anon-publique")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "cle-service-SECRETE")


# ── Vérification du jeton ────────────────────────────────────────

def test_un_jeton_hs256_valide_est_accepte(env_auth):
    assert auth._verify_supabase_jwt(_jeton())["sub"] == USER_ID


@pytest.mark.parametrize("jeton", [
    lambda: _jeton(secret="un-autre-secret-tout-aussi-long-0123456789"),          # signature fausse
    lambda: _jeton(aud="anon"),                                                   # mauvaise audience
    lambda: _jeton(exp=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)),  # expiré
])
def test_un_jeton_falsifie_ou_perime_est_refuse(env_auth, jeton):
    with pytest.raises(jwt.InvalidTokenError):
        auth._verify_supabase_jwt(jeton())


def test_un_algorithme_inconnu_est_refuse(env_auth):
    # « none » : jeton non signé, le piège classique.
    sans_signature = jwt.encode({"sub": USER_ID, "aud": "authenticated"}, None, algorithm="none")
    with pytest.raises(jwt.InvalidTokenError):
        auth._verify_supabase_jwt(sans_signature)


def test_sans_secret_cote_serveur_le_jeton_hs256_est_refuse(env_auth, monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET")
    with pytest.raises(jwt.InvalidTokenError):
        auth._verify_supabase_jwt(_jeton())


def test_un_jeton_rs256_est_verifie_par_la_cle_publique_du_projet(env_auth, monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import rsa
    privee = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    autre = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = types.SimpleNamespace(get_signing_key_from_jwt=lambda t: types.SimpleNamespace(key=privee.public_key()))
    monkeypatch.setattr(auth, "_get_jwks_client", lambda url: jwks)
    assert auth._verify_supabase_jwt(_jeton(secret=privee, alg="RS256"))["sub"] == USER_ID
    with pytest.raises(jwt.InvalidTokenError):
        auth._verify_supabase_jwt(_jeton(secret=autre, alg="RS256"))


# ── /auth/session ────────────────────────────────────────────────

def test_la_connexion_pose_une_session_neuve(fake_db, client, env_auth):
    with client.session_transaction() as s:
        s["user_id"] = "ancien-compte"
        s["is_vip"] = True          # reste d'une session précédente
    r = client.post("/auth/session", json={"access_token": _jeton()})
    assert r.status_code == 200 and r.get_json()["user_id"] == USER_ID
    with client.session_transaction() as s:
        assert s["user_id"] == USER_ID and s["email"] == "a@b.fr"
        assert "is_vip" not in s                    # rien n'est hérité de l'autre compte
        assert len(s["_csrf"]) >= 32 and s["fournisseurs"] == ["google"]


@pytest.mark.parametrize("corps,code", [
    ({}, 400),
    ({"access_token": "pas-un-jeton"}, 401),
])
def test_une_connexion_sans_jeton_valide_ne_cree_pas_de_session(fake_db, client, env_auth, corps, code):
    assert client.post("/auth/session", json=corps).status_code == code
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_un_jeton_sans_identifiant_est_refuse(fake_db, client, env_auth):
    assert client.post("/auth/session", json={"access_token": _jeton(sub=None)}).status_code == 401


def test_une_panne_de_verification_ne_raconte_rien(fake_db, client, env_auth, monkeypatch):
    def panne(t):
        raise ConnectionError("jwks.supabase.co injoignable — détail interne")
    monkeypatch.setattr(auth, "_verify_supabase_jwt", panne)
    r = client.post("/auth/session", json={"access_token": "x"})
    assert r.status_code == 500 and "jwks" not in r.get_data(as_text=True)


def test_les_pages_de_connexion_ne_livrent_aucun_secret(fake_db, client, env_auth):
    for page in ("/login", "/auth/bridge"):
        html = client.get(page).get_data(as_text=True)
        assert "cle-anon-publique" in html          # la clé anon est publique, c'est normal
        assert "cle-service-SECRETE" not in html and SECRET not in html


def test_la_deconnexion_vide_la_session(fake_db, logged_in):
    r = logged_in.post("/logout", data={"_csrf": CSRF})
    assert r.status_code == 302
    with logged_in.session_transaction() as s:
        assert "user_id" not in s


def test_le_diagnostic_est_ferme_par_defaut_et_ne_montre_jamais_de_valeur(fake_db, logged_in, env_auth, monkeypatch):
    monkeypatch.delenv("DEBUG_ENDPOINT", raising=False)
    assert logged_in.get("/auth/debug").status_code == 404
    monkeypatch.setenv("DEBUG_ENDPOINT", "1")
    monkeypatch.setenv("ADMIN_EMAILS", "autre@example.com")
    assert logged_in.get("/auth/debug").status_code == 404          # ouvert, mais pas admin
    monkeypatch.setenv("ADMIN_EMAILS", "test@example.com")
    r = logged_in.get("/auth/debug")
    assert r.status_code == 200
    texte = r.get_data(as_text=True)
    assert "cle-service-SECRETE" not in texte and SECRET not in texte
    assert r.get_json()["SUPABASE_JWT_SECRET_len"] == len(SECRET)


# ── Console admin ────────────────────────────────────────────────

@pytest.fixture()
def admin(fake_db, logged_in, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "test@example.com")
    fake_db.auth.admin.list_users = lambda **k: [types.SimpleNamespace(
        id=USER_ID, email="test@example.com", created_at="2026-09-01")]
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("profiles").insert({"id": "u-cible", "tier": "free"}).execute()
    return logged_in


def _tier(fake, uid):
    return next(p for p in fake.tables["profiles"] if p["id"] == uid)["tier"]


ACTIONS = [
    ("post", "/admin/set-tier", {"user_id": "u-cible", "tier": "vip"}),
    ("post", "/admin/reset-quota", {"user_id": "u-cible"}),
    ("post", "/admin/send-test-push", {}),
    ("post", "/admin/send-reactivation", {}),
    ("get", "/admin/user/u-cible", None),
    ("get", "/admin/newsletter-emails", None),
    ("get", "/admin/funnel", None),
    ("get", "/admin/blob", None),
]


@pytest.mark.parametrize("methode,chemin,donnees", ACTIONS)
def test_aucune_action_admin_nest_ouverte_a_un_non_admin(fake_db, logged_in, monkeypatch, methode, chemin, donnees):
    monkeypatch.setenv("ADMIN_EMAILS", "quelquun@example.com")
    fake_db.table("profiles").insert({"id": "u-cible", "tier": "free"}).execute()
    if methode == "post":
        r = logged_in.post(chemin, data={"_csrf": CSRF, **(donnees or {})})
    else:
        r = logged_in.get(chemin)
    assert r.status_code == 404
    assert _tier(fake_db, "u-cible") == "free"


def test_ladmin_passe_un_compte_en_pro_puis_le_rend_gratuit(fake_db, admin):
    admin.post("/admin/set-tier", data={"_csrf": CSRF, "user_id": "u-cible", "tier": "vip"})
    assert _tier(fake_db, "u-cible") == "vip"
    admin.post("/admin/set-tier", data={"_csrf": CSRF, "user_id": "u-cible", "tier": "free"})
    assert _tier(fake_db, "u-cible") == "free"


def test_un_tier_inconnu_est_ignore(fake_db, admin):
    admin.post("/admin/set-tier", data={"_csrf": CSRF, "user_id": "u-cible", "tier": "dieu"})
    assert _tier(fake_db, "u-cible") == "free"


def test_changer_son_propre_tier_force_la_relecture(fake_db, admin):
    with admin.session_transaction() as s:
        s["is_vip"] = False
    admin.post("/admin/set-tier", data={"_csrf": CSRF, "user_id": USER_ID, "tier": "vip"})
    with admin.session_transaction() as s:
        assert "is_vip" not in s


def test_la_console_saffiche_meme_si_les_statistiques_tombent(fake_db, admin, monkeypatch):
    import core.db as db

    def panne():
        raise RuntimeError("vue admin_history_stats absente")
    monkeypatch.setattr(db, "get_admin_stats", panne)
    r = admin.get("/admin")
    assert r.status_code == 200 and "test@example.com" in r.get_data(as_text=True)


def test_remise_a_zero_du_quota(fake_db, admin, monkeypatch):
    import core.db as db
    appels = []
    monkeypatch.setattr(db, "reset_user_coach_quota", lambda uid: appels.append(uid))
    assert admin.post("/admin/reset-quota", data={"_csrf": CSRF}).status_code == 400
    assert admin.post("/admin/reset-quota", data={"_csrf": CSRF, "user_id": "u-cible"}).get_json() == {"ok": True}
    assert appels == ["u-cible"]

    def panne(uid):
        raise RuntimeError("x")
    monkeypatch.setattr(db, "reset_user_coach_quota", panne)
    assert admin.post("/admin/reset-quota", data={"_csrf": CSRF, "user_id": "u-cible"}).status_code == 500


def test_la_fiche_dun_compte_et_sa_panne(fake_db, admin, monkeypatch):
    import core.db as db
    monkeypatch.setattr(db, "get_user_details", lambda uid: {"id": uid, "series": 12})
    assert admin.get("/admin/user/u-cible").get_json() == {"id": "u-cible", "series": 12}

    def panne(uid):
        raise RuntimeError("secret interne")
    monkeypatch.setattr(db, "get_user_details", panne)
    r = admin.get("/admin/user/u-cible")
    assert r.status_code == 500 and "secret" not in r.get_data(as_text=True)


def test_la_liste_newsletter_est_du_texte_brut(fake_db, admin, monkeypatch):
    import core.db as db
    monkeypatch.setattr(db, "list_newsletter_emails", lambda: ["a@b.fr", "c@d.fr"])
    r = admin.get("/admin/newsletter-emails")
    assert r.mimetype == "text/plain" and r.get_data(as_text=True) == "a@b.fr\nc@d.fr"
    monkeypatch.setattr(db, "list_newsletter_emails", lambda: [])
    assert "aucun abonné" in admin.get("/admin/newsletter-emails").get_data(as_text=True)


def test_la_notification_de_test(fake_db, admin, monkeypatch):
    import core.db as db
    import routes.admin as adm
    monkeypatch.setattr(adm.core_push, "is_configured", lambda: False)
    assert admin.post("/admin/send-test-push", data={"_csrf": CSRF}).status_code == 503
    monkeypatch.setattr(adm.core_push, "is_configured", lambda: True)
    monkeypatch.setattr(db, "list_push_subscriptions", lambda uid: [])
    assert admin.post("/admin/send-test-push", data={"_csrf": CSRF}).status_code == 400
    abonnements = [{"endpoint": "e1"}, {"endpoint": "e2"}, {"endpoint": "e3"}]
    statuts = iter(["ok", "expired", "error"])
    supprimes = []
    monkeypatch.setattr(db, "list_push_subscriptions", lambda uid: abonnements)
    monkeypatch.setattr(adm.core_push, "send_push", lambda sub, payload: next(statuts))
    monkeypatch.setattr(db, "delete_push_subscription", lambda ep: supprimes.append(ep))
    d = admin.post("/admin/send-test-push", data={"_csrf": CSRF}).get_json()
    assert (d["sent"], d["expired"], d["errors"], d["subs"]) == (1, 1, 1, 3)
    assert supprimes == ["e2"]          # l'abonnement expiré est nettoyé


def test_la_relance_des_inactifs(fake_db, admin, monkeypatch):
    import routes.admin as adm
    monkeypatch.setattr(adm.core_push, "is_configured", lambda: True)
    monkeypatch.setattr(adm.core_push, "run_reactivation_push",
                        lambda **k: {"ok": True, "envoyes": 2, "cibles": 3})
    assert admin.post("/admin/send-reactivation", data={"_csrf": CSRF}).get_json()["envoyes"] == 2
    monkeypatch.setattr(adm.core_push, "run_reactivation_push", lambda **k: {"ok": False, "error": "x"})
    assert admin.post("/admin/send-reactivation", data={"_csrf": CSRF}).status_code == 500
    monkeypatch.setattr(adm.core_push, "is_configured", lambda: False)
    assert admin.post("/admin/send-reactivation", data={"_csrf": CSRF}).status_code == 503


@pytest.mark.parametrize("jours,attendu", [("7", 7), ("90", 90), ("365", 30), ("abc", 30)])
def test_le_funnel_borne_sa_fenetre(fake_db, admin, monkeypatch, jours, attendu):
    import core.db as db
    vus = []
    monkeypatch.setattr(db, "get_funnel_stats", lambda d: vus.append(d) or
                        {"days": d, "steps": [], "coach_msgs_users": 0})
    assert admin.get(f"/admin/funnel?days={jours}").status_code == 200
    assert vus == [attendu]


def test_la_mesure_du_blob_survit_a_une_panne(fake_db, admin, monkeypatch):
    import core.db as db

    def panne():
        raise RuntimeError("x")
    monkeypatch.setattr(db, "list_all_program_blobs", panne)
    assert admin.get("/admin/blob").status_code == 503
    monkeypatch.setattr(db, "list_all_program_blobs", lambda: [])
    assert "Aucun programme" in admin.get("/admin/blob").get_data(as_text=True)
