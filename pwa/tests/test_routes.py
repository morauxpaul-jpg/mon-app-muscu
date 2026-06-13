"""Tests d'intégration — routes Flask sur fake Supabase.

Couvre en particulier la migration « semaine continue » (2026-06) :
le n° de semaine ISO recommençait chaque année, ce qui cassait le streak,
le « Dernière fois » et le remplacement de séries au passage du Nouvel An.
"""
import datetime as dt
import json
import types

from conftest import USER_ID, CSRF


def _fake_stripe_upgrade(rec, interval="month"):
    """Faux module Stripe pour les scénarios d'upgrade (client + abonnement
    actif). Les méthodes renvoient des dicts simples (cf. _to_plain)."""
    def sess_create(**k):
        rec["create"] = k
        return types.SimpleNamespace(url="https://checkout.test/x")

    def sub_list(**k):
        return {"data": [{"id": "sub_old", "customer": "cus_1",
                          "items": {"data": [{"price": {"recurring": {"interval": interval}}}]}}]}

    def sub_modify(sid, **k):
        rec.setdefault("modified", []).append(sid)

    def sub_cancel(sid):
        rec.setdefault("cancelled", []).append(sid)

    def cust_list(**k):
        return {"data": [{"id": "cus_1"}]}

    return types.SimpleNamespace(
        checkout=types.SimpleNamespace(Session=types.SimpleNamespace(create=sess_create)),
        Subscription=types.SimpleNamespace(list=sub_list, modify=sub_modify, cancel=sub_cancel),
        Customer=types.SimpleNamespace(list=cust_list),
    )

# Dates pivot autour du Nouvel An 2025→2026.
MONDAY_W51 = dt.date(2025, 12, 15)   # lundi, ISO W51 2025
MONDAY_W52 = dt.date(2025, 12, 22)   # lundi, ISO W52 2025
MONDAY_W01 = dt.date(2025, 12, 29)   # lundi, ISO W1 2026
MONDAY_W02 = dt.date(2026, 1, 5)     # lundi, ISO W2 2026

assert all(d.weekday() == 0 for d in (MONDAY_W51, MONDAY_W52, MONDAY_W01, MONDAY_W02))


def _hist_row(fake, date, exercice="Développé couché", seance="Push",
              serie=1, reps=8, poids=80.0, semaine=None, muscle="Pecs"):
    """Insère une ligne history au format colonnes Supabase. `semaine` par
    défaut = n° ISO legacy (comme les données écrites avant la migration)."""
    fake.table("history").insert({
        "user_id": USER_ID,
        "semaine": semaine if semaine is not None else date.isocalendar().week,
        "seance": seance,
        "exercice": exercice,
        "serie": serie,
        "reps": reps,
        "poids": poids,
        "remarque": "",
        "muscle": muscle,
        "date": date.isoformat(),
    }).execute()


def _seed_prog(fake, planning=None):
    fake.table("programs").insert({
        "user_id": USER_ID,
        "data": {
            "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
            "_planning": planning or {},
            "_settings": {},
            "_started_at": MONDAY_W51.isoformat(),
        },
    }).execute()


# ── Pages publiques ──────────────────────────────────────────────

def test_public_pages_render(client):
    for path in ("/", "/faq", "/confidentialite", "/manifest.json", "/service-worker.js"):
        assert client.get(path).status_code == 200, path


def test_protected_routes_redirect_anonymous(client):
    r = client.get("/accueil")
    assert r.status_code == 302 and r.headers["Location"] == "/"


# ── Semaine continue : passage d'année ───────────────────────────

def test_derniere_fois_traverse_le_nouvel_an(fake_db, logged_in):
    """Une perf de fin décembre doit alimenter « Dernière fois » et le
    pré-remplissage début janvier (cassait avec les semaines ISO : 52 < 1)."""
    _seed_prog(fake_db)
    _hist_row(fake_db, MONDAY_W52, poids=80.0, reps=8)

    r = logged_in.get(f"/seance?date={MONDAY_W02.isoformat()}&mode=prefaite&name=Push")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "80kg" in html  # last_summary "80kg × 8" injecté dans le payload exo


def test_save_exo_remplace_les_lignes_legacy_meme_semaine(fake_db, logged_in):
    """Le remplacement d'un exo cible la semaine PAR DATES : une ligne écrite
    avant la migration (semaine stockée = n° ISO) doit quand même être
    remplacée, pas dupliquée."""
    from core.dates import continuous_week
    _seed_prog(fake_db)
    # Ligne legacy : même semaine calendaire que la saisie, semaine stockée ISO (2).
    _hist_row(fake_db, MONDAY_W02, poids=80.0, reps=8, semaine=2)

    r = logged_in.post("/seance/save-exo", data={
        "_csrf": CSRF,
        "semaine": str(continuous_week(MONDAY_W02)),
        "seance_name": "Push",
        "exo_base": "Développé couché",
        "variant": "Standard",
        "muscle": "Pecs",
        "date": MONDAY_W02.isoformat(),
        "mode": "prefaite",
        "name": "Push",
        "sets_json": json.dumps([
            {"reps": 8, "poids": 82.5},
            {"reps": 6, "poids": 85.0},
        ]),
    })
    assert r.status_code == 302

    rows = [row for row in fake_db.tables["history"]
            if row["exercice"] == "Développé couché"]
    # La ligne legacy a été remplacée : exactement les 2 nouvelles séries.
    assert len(rows) == 2
    assert sorted(row["poids"] for row in rows) == [82.5, 85.0]


def test_reset_exo_supprime_aussi_les_lignes_legacy(fake_db, logged_in):
    _seed_prog(fake_db)
    _hist_row(fake_db, MONDAY_W02, semaine=2)          # legacy ISO
    _hist_row(fake_db, MONDAY_W02 + dt.timedelta(days=1), serie=2, semaine=2)
    # Une perf d'une AUTRE semaine ne doit pas être touchée.
    _hist_row(fake_db, MONDAY_W51, serie=1, semaine=51)

    r = logged_in.post("/seance/reset-exo", data={
        "_csrf": CSRF,
        "seance_name": "Push",
        "exo_base": "Développé couché",
        "variant": "Standard",
        "date": MONDAY_W02.isoformat(),
        "mode": "prefaite",
        "name": "Push",
    })
    assert r.status_code == 302
    remaining = [row for row in fake_db.tables["history"]
                 if row["exercice"] == "Développé couché"]
    assert len(remaining) == 1
    assert remaining[0]["date"] == MONDAY_W51.isoformat()


def test_streak_traverse_le_nouvel_an(fake_db, logged_in):
    """3 semaines consécutives W51-2025 → W1-2026 = streak 3 (cassait en ISO :
    [52, 51, 1] non consécutifs)."""
    _seed_prog(fake_db)
    for monday in (MONDAY_W51, MONDAY_W52, MONDAY_W01):
        _hist_row(fake_db, monday)

    r = logged_in.get("/accueil")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "3 SEMAINES" in html


def test_accueil_affiche_semaine_relative(fake_db, logged_in):
    """Le n° de semaine affiché doit être relatif au programme (petit),
    pas l'index continu interne (>100)."""
    _seed_prog(fake_db)
    _hist_row(fake_db, MONDAY_W51)

    r = logged_in.get("/accueil")
    html = r.data.decode("utf-8")
    import re
    m = re.search(r"SEMAINE (\d+)", html)
    assert m, "numéro de semaine absent de l'accueil"
    assert int(m.group(1)) < 100  # relatif au _started_at, pas continu


# ── Suppression de compte ────────────────────────────────────────

def test_delete_account_efface_tout_et_deconnecte(fake_db, logged_in):
    _seed_prog(fake_db)
    _hist_row(fake_db, MONDAY_W51)
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("nutrition").insert({"user_id": USER_ID, "date": "2026-06-01",
                                       "meal_type": "diner", "calories": 600}).execute()

    r = logged_in.post("/gestion/delete-account", data={"_csrf": CSRF, "confirm": "yes"})
    assert r.status_code == 302 and r.headers["Location"] == "/"

    for table in ("history", "programs", "profiles", "nutrition"):
        rows = [row for row in fake_db.tables.get(table, [])
                if row.get("user_id") == USER_ID or row.get("id") == USER_ID]
        assert rows == [], f"table {table} non vidée"
    assert fake_db.auth.admin.deleted_users == [USER_ID]
    # La session est purgée → la requête suivante redirige vers la landing.
    r2 = logged_in.get("/accueil")
    assert r2.status_code == 302 and r2.headers["Location"] == "/"


def test_delete_account_sans_confirmation_ne_fait_rien(fake_db, logged_in):
    _seed_prog(fake_db)
    r = logged_in.post("/gestion/delete-account", data={"_csrf": CSRF})
    assert r.status_code == 302
    assert fake_db.tables["programs"], "les données ne doivent PAS être effacées"
    assert fake_db.auth.admin.deleted_users == []


# ── Onboarding ───────────────────────────────────────────────────

def _fresh_login(client):
    """Session authentifiée mais PAS encore onboardée (nouveau compte)."""
    import time
    with client.session_transaction() as s:
        s["user_id"] = USER_ID
        s["email"] = "test@example.com"
        s["is_vip"] = False
        s["is_vip_ts"] = time.time()
        s["_csrf"] = CSRF
    return client


def test_onboarding_submit_avec_csrf_statique(fake_db, client):
    """Régression : le form caché est soumis via form.submit() programmatique,
    qui ne déclenche pas l'injection CSRF globale — le token statique du
    template doit suffire, sinon 400 et l'onboarding ne « passe pas »."""
    _fresh_login(client)
    r = client.post("/onboarding/submit", data={
        "_csrf": CSRF,
        "prenom": "Paul",
        "age": "25",
        "sexe": "homme",
        "niveau": "debutant",
        "frequence": "3",
        "objectif": "prise de masse",
        "equipement": "salle",
        "programme_id": "custom",
    })
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/accueil")
    rows = [x for x in fake_db.tables.get("onboarding", []) if x["user_id"] == USER_ID]
    assert rows and rows[0]["prenom"] == "Paul"


def test_onboarding_submit_sans_csrf_rejete(fake_db, client):
    _fresh_login(client)
    r = client.post("/onboarding/submit", data={"prenom": "Paul"})
    assert r.status_code == 400


def test_premium_accessible_pendant_onboarding(fake_db, client):
    """La carte « Plus de programmes PRO » de l'onboarding pointe vers
    /premium : la page ne doit pas re-rediriger vers /onboarding."""
    _fresh_login(client)
    r = client.get("/premium")
    assert r.status_code == 200


def test_onboarding_page_rend_le_catalogue(fake_db, client):
    _fresh_login(client)
    r = client.get("/onboarding")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "Plus de programmes avec PRO" in html
    assert "CATALOG_PROGRAMS" in html
    # Le token CSRF statique du form caché (form.submit() programmatique).
    assert 'name="_csrf"' in html


# ── Pubs (config AdMob injectée pour les Free uniquement) ────────

def test_ads_config_absente_pour_vip(fake_db, logged_in):
    _seed_prog(fake_db)
    r = logged_in.get("/accueil")  # fixture logged_in = VIP
    assert "__ADS__" not in r.data.decode("utf-8")


def test_ads_config_presente_pour_free(fake_db, client):
    _fresh_login(client)
    r = client.get("/onboarding")
    html = r.data.decode("utf-8")
    assert "__ADS__" in html and "ads.js" in html


# ── Upgrade d'abonnement ─────────────────────────────────────────

def test_premium_affiche_upgrades_pour_abonne_mensuel(fake_db, logged_in, monkeypatch):
    import routes.billing as billing
    monkeypatch.setattr(billing, "_stripe", lambda: _fake_stripe_upgrade({}, interval="month"))
    html = logged_in.get("/premium").data.decode("utf-8")
    assert "Passer à l'annuel" in html
    assert "Passer à vie" in html


def test_premium_pas_d_upgrade_mensuel_pour_abonne_annuel(fake_db, logged_in, monkeypatch):
    import routes.billing as billing
    monkeypatch.setattr(billing, "_stripe", lambda: _fake_stripe_upgrade({}, interval="year"))
    html = logged_in.get("/premium").data.decode("utf-8")
    assert "Ton plan actuel (annuel)" in html
    assert "Passer à vie" in html
    assert "Passer à l'annuel" not in html


def test_checkout_upgrade_marque_l_abonnement_precedent(fake_db, logged_in, monkeypatch):
    import routes.billing as billing
    rec = {}
    monkeypatch.setattr(billing, "_stripe", lambda: _fake_stripe_upgrade(rec))
    r = logged_in.post("/billing/checkout", data={"_csrf": CSRF, "plan": "annual"})
    assert r.status_code == 303
    md = rec["create"]["metadata"]
    assert md["previous_subscription"] == "sub_old"
    assert rec["create"].get("customer") == "cus_1"
    assert "customer_email" not in rec["create"]  # exclusif avec customer


def test_webhook_upgrade_annule_l_ancien_abonnement(fake_db, client, monkeypatch):
    import routes.billing as billing
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    rec = {}
    fs = _fake_stripe_upgrade(rec)
    event = {"type": "checkout.session.completed", "data": {"object": {
        "client_reference_id": USER_ID, "customer": "cus_1", "subscription": "sub_new",
        "metadata": {"user_id": USER_ID, "previous_subscription": "sub_old"}}}}
    fs.Webhook = types.SimpleNamespace(construct_event=lambda p, s, sec: event)
    monkeypatch.setattr(billing, "_stripe", lambda: fs)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec")
    r = client.post("/billing/webhook", data=b"{}", headers={"Stripe-Signature": "x"})
    assert r.status_code == 200
    assert "sub_old" in rec.get("cancelled", [])
    assert "sub_old" in rec.get("modified", [])


def test_webhook_superseded_ne_retrograde_pas(fake_db, client, monkeypatch):
    """L'annulation de l'ancien abo lors d'un upgrade ne doit PAS faire perdre
    le VIP (metadata.superseded)."""
    import routes.billing as billing
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    event = {"type": "customer.subscription.deleted", "data": {"object": {
        "customer": "cus_1", "metadata": {"user_id": USER_ID, "superseded": "1"}}}}
    fs = types.SimpleNamespace(Webhook=types.SimpleNamespace(construct_event=lambda p, s, sec: event))
    monkeypatch.setattr(billing, "_stripe", lambda: fs)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec")
    r = client.post("/billing/webhook", data=b"{}", headers={"Stripe-Signature": "x"})
    assert r.status_code == 200
    prof = next(p for p in fake_db.tables["profiles"] if p["id"] == USER_ID)
    assert prof["tier"] == "vip"  # toujours VIP


# ── Session d'un compte supprimé ─────────────────────────────────

def test_session_invalidee_apres_suppression_compte(fake_db, logged_in):
    """Un cookie encore valide sur un autre appareil ne doit plus donner accès
    après suppression du compte : la revalidation périodique (TTL VIP) vérifie
    l'existence du compte auth et purge la session."""
    fake_db.auth.admin.deleted_users.append(USER_ID)
    # Force la revalidation : timestamp VIP périmé.
    with logged_in.session_transaction() as s:
        s["is_vip_ts"] = 0
    r = logged_in.get("/accueil")
    assert r.status_code == 302 and r.headers["Location"] == "/"
    # La session est purgée → même une requête avec ts frais ne passe plus.
    r2 = logged_in.get("/accueil")
    assert r2.status_code == 302 and r2.headers["Location"] == "/"


# ── Asset links (TWA Play Store) ─────────────────────────────────

def test_assetlinks_404_sans_config(client):
    import os
    os.environ.pop("TWA_SHA256_FINGERPRINT", None)
    assert client.get("/.well-known/assetlinks.json").status_code == 404


def test_assetlinks_avec_empreinte(client, monkeypatch):
    monkeypatch.setenv("TWA_SHA256_FINGERPRINT", "aa:bb:cc")
    monkeypatch.setenv("TWA_PACKAGE_NAME", "com.muscutracker.app")
    r = client.get("/.well-known/assetlinks.json")
    assert r.status_code == 200
    payload = r.get_json()
    assert payload[0]["target"]["package_name"] == "com.muscutracker.app"
    assert payload[0]["target"]["sha256_cert_fingerprints"] == ["AA:BB:CC"]
    assert payload[0]["relation"] == ["delegate_permission/common.handle_all_urls"]


# ── Billing / Stripe ─────────────────────────────────────────────

def test_premium_montre_boutons_achat_pour_free(fake_db, client):
    _fresh_login(client)
    r = client.get("/premium")
    html = r.data.decode("utf-8")
    assert r.status_code == 200
    assert '/billing/checkout' in html
    assert 'value="monthly"' in html and 'value="annual"' in html and 'value="lifetime"' in html


def test_premium_montre_portail_pour_vip(fake_db, logged_in):
    r = logged_in.get("/premium")
    html = r.data.decode("utf-8")
    assert "/billing/portal" in html
    # Pas de bouton d'achat pour un VIP.
    assert 'value="monthly"' not in html


def test_checkout_anonyme_redirige_login(client):
    r = client.post("/billing/checkout", data={"plan": "monthly"})
    assert r.status_code == 302 and r.headers["Location"] == "/"


def test_checkout_sans_cle_stripe_renvoie_503(fake_db, logged_in, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    r = logged_in.post("/billing/checkout", data={"_csrf": CSRF, "plan": "monthly"})
    assert r.status_code == 503


def test_checkout_plan_invalide_redirige(fake_db, logged_in):
    r = logged_in.post("/billing/checkout", data={"_csrf": CSRF, "plan": "pirate"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/premium")


def test_checkout_cree_session_stripe(fake_db, logged_in, monkeypatch):
    import routes.billing as billing
    captured = {}

    import types as _types

    class FakeSession:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            # Le vrai SDK renvoie un objet avec attribut .url
            return _types.SimpleNamespace(url="https://checkout.stripe.test/abc")

    fake_stripe = type("S", (), {"checkout": type("C", (), {"Session": FakeSession})})
    monkeypatch.setattr(billing, "_stripe", lambda: fake_stripe)

    r = logged_in.post("/billing/checkout", data={"_csrf": CSRF, "plan": "annual"})
    assert r.status_code == 303
    assert r.headers["Location"] == "https://checkout.stripe.test/abc"
    assert captured["mode"] == "subscription"
    assert captured["client_reference_id"] == USER_ID
    assert captured["line_items"][0]["price_data"]["unit_amount"] == 3999
    assert captured["line_items"][0]["price_data"]["recurring"]["interval"] == "year"


class _FakeStripeObj:
    """Imite un StripeObject v15 : str() = JSON, mais .get() lève AttributeError
    (le SDK v15 n'expose pas .get) → vérifie que _to_plain neutralise ça."""
    def __init__(self, d):
        self._d = d

    def __str__(self):
        import json as _j
        return _j.dumps(self._d)

    def get(self, *a, **k):
        raise AttributeError("get")

    @property
    def url(self):
        return self._d.get("url")


def test_success_active_vip_malgre_stripeobject(fake_db, client, monkeypatch):
    """Régression du bug : .get() sur l'objet Stripe plantait → activation
    silencieusement ratée. _to_plain doit récupérer status/ref via JSON."""
    import time, routes.billing as billing
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    with client.session_transaction() as s:
        s["user_id"] = USER_ID
        s["email"] = "test@example.com"
        s["onboarded"] = True
        s["is_vip"] = False
        s["is_vip_ts"] = time.time()
        s["_csrf"] = CSRF

    sess_obj = _FakeStripeObj({
        "status": "complete", "payment_status": "paid",
        "client_reference_id": USER_ID, "customer": "cus_abc",
    })
    fake_stripe = type("S", (), {
        "checkout": type("C", (), {"Session": type("X", (), {
            "retrieve": staticmethod(lambda sid: sess_obj)})}),
    })
    monkeypatch.setattr(billing, "_stripe", lambda: fake_stripe)

    r = client.get("/billing/success?session_id=cs_test_123")
    assert r.status_code == 200
    assert "VIP" in r.data.decode("utf-8")
    prof = next(p for p in fake_db.tables["profiles"] if p["id"] == USER_ID)
    assert prof["tier"] == "vip"


def test_webhook_public_et_csrf_exempt(fake_db, client):
    # Pas de session, pas de token CSRF : le webhook ne doit PAS être redirigé
    # vers /login ni rejeté en 400-CSRF. Sans clé Stripe configurée → 503.
    import os
    os.environ.pop("STRIPE_SECRET_KEY", None)
    r = client.post("/billing/webhook", data=b"{}", content_type="application/json")
    assert r.status_code == 503  # pas 302 (auth) ni 400 (csrf)


def test_webhook_active_vip_sur_paiement(fake_db, client, monkeypatch):
    import routes.billing as billing
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()

    event = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "client_reference_id": USER_ID,
            "customer": "cus_test_123",
            "metadata": {"user_id": USER_ID},
        }},
    }
    fake_stripe = type("S", (), {
        "Webhook": type("W", (), {"construct_event": staticmethod(lambda payload, sig, secret: event)}),
    })
    monkeypatch.setattr(billing, "_stripe", lambda: fake_stripe)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    r = client.post("/billing/webhook", data=b"{}",
                    headers={"Stripe-Signature": "t=1,v1=x"})
    assert r.status_code == 200
    prof = next(p for p in fake_db.tables["profiles"] if p["id"] == USER_ID)
    assert prof["tier"] == "vip"
    assert prof.get("stripe_customer_id") == "cus_test_123"


def test_webhook_downgrade_sur_annulation(fake_db, client, monkeypatch):
    import routes.billing as billing
    fake_db.table("profiles").insert(
        {"id": USER_ID, "tier": "vip", "stripe_customer_id": "cus_x"}
    ).execute()

    event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"customer": "cus_x", "metadata": {"user_id": USER_ID}}},
    }
    fake_stripe = type("S", (), {
        "Webhook": type("W", (), {"construct_event": staticmethod(lambda p, s, sec: event)}),
    })
    monkeypatch.setattr(billing, "_stripe", lambda: fake_stripe)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    r = client.post("/billing/webhook", data=b"{}", headers={"Stripe-Signature": "x"})
    assert r.status_code == 200
    prof = next(p for p in fake_db.tables["profiles"] if p["id"] == USER_ID)
    assert prof["tier"] == "free"


# ── Import JSON : validation ─────────────────────────────────────

def test_import_json_malforme_rejete(fake_db, logged_in):
    import io
    _seed_prog(fake_db)
    before = json.dumps(fake_db.tables["programs"], sort_keys=True, default=str)
    r = logged_in.post(
        "/gestion/import",
        data={"_csrf": CSRF,
              "file": (io.BytesIO(b'{"programme": "pas un dict"}'), "backup.json")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 302 and "import=error" in r.headers["Location"]
    after = json.dumps(fake_db.tables["programs"], sort_keys=True, default=str)
    assert before == after, "un import invalide ne doit rien écraser"
