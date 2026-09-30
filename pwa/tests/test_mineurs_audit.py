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


# ── M5 : la mesure d'usage ne grossit pas sans fin ───────────────


def test_les_events_de_plus_de_13_mois_sont_effaces(fake_db):
    import datetime as dt
    import core.db as db
    vieux = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=400)).isoformat()
    recent = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10)).isoformat()
    fake_db.table("events").insert({"user_id": "a", "event": "x", "created_at": vieux}).execute()
    fake_db.table("events").insert({"user_id": "a", "event": "y", "created_at": recent}).execute()
    db.purge_old_events()
    assert [e["event"] for e in fake_db.tables["events"]] == ["y"]


def test_la_relance_affichee_ne_compte_quune_fois_par_jour(fake_db, logged_in, monkeypatch):
    import datetime as dt
    import routes.accueil as accueil
    monkeypatch.setattr(accueil, "logical_today_paris", lambda: dt.date(2026, 9, 30))
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "A": [{"name": "Squat", "sets": 3, "muscle": "Jambes"}],
        "_planning": {"Lundi": "A", "Mercredi": "A", "Vendredi": "A"}, "_settings": {}}}).execute()
    fake_db.table("history").insert({
        "user_id": USER_ID, "date": "2026-09-14", "semaine": 1, "seance": "A",
        "exercice": "Squat", "serie": 1, "reps": 5, "poids": 100.0,
        "remarque": "", "muscle": "Jambes"}).execute()
    for _ in range(3):
        logged_in.get("/accueil", headers={"Sec-Fetch-Mode": "navigate"})
    vus = [e for e in fake_db.tables.get("events", []) if e["event"] == "reactivation_nudge_shown"]
    assert len(vus) == 1


# ── M6 : les stats admin viennent d'une vue d'agrégats ───────────


def test_les_stats_admin_lisent_la_vue_quand_elle_existe(fake_db):
    import core.db as db
    fake_db.table("admin_history_stats").insert({
        "total_rows": 12, "total_tonnage": 3400, "total_seances": 3,
        "active_7d": 1, "active_30d": 2}).execute()
    s = db.get_admin_stats()
    assert s == {"total_rows": 12, "total_tonnage": 3400, "total_seances": 3,
                 "active_7d": 1, "active_30d": 2}


# ── M9 : lisible, et rien ne se chevauche ────────────────────────


def test_aucune_police_sous_0_7rem():
    """Une quarantaine de tailles descendaient jusqu'à 0,55 rem (≈ 9 px)."""
    import re
    trop_petit = re.compile(r"font-size:\s*0\.(?:[0-5]\d*|6\d*)rem")
    fautifs = []
    for p in list((PWA / "templates").glob("*.html")) + list((PWA / "static" / "css").glob("*.css")):
        for n, ligne in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if trop_petit.search(ligne):
                fautifs.append(f"{p.name}:{n}")
    assert not fautifs, fautifs


def test_le_badge_pro_ne_se_tronque_pas_avec_le_mail(fake_db, logged_in):
    html = logged_in.get("/plus").get_data(as_text=True)
    assert '<span class="topbar-email">' in html
    assert 'class="badge-pro topbar-badge">PRO<' in html
    assert 'aria-label="Déconnexion"' in html


def test_un_lien_bouton_nest_pas_inline():
    css = (PWA / "static" / "css" / "theme.css").read_text(encoding="utf-8")
    assert "a.btn { display: inline-flex;" in css


def test_les_decimales_du_record_sont_a_la_francaise():
    t = _tpl("_seance_carte_exercice.html")
    assert "record.one_rm + 'kg'" not in t
    assert "_kg(record.one_rm)" in t


# ── Retirés le 01/10 (audit, partie 4-C) ─────────────────────────


@pytest.mark.parametrize("chemin,methode", [
    ("/arcade", "get"),
    ("/programme/profile/switch", "post"),
    ("/programme/profile/add", "post"),
    ("/seance/mark-missed", "post"),
])
def test_les_fonctions_retirees_nexistent_plus(fake_db, logged_in, chemin, methode):
    r = getattr(logged_in, methode)(chemin, data={"_csrf": CSRF})
    assert r.status_code == 404


def test_plus_de_lien_vers_les_fonctions_retirees():
    for nom in ("plus.html", "landing.html", "seance_edit.html", "seance_choix.html", "programme.html"):
        t = _tpl(nom)
        assert "/arcade" not in t and "mark-missed" not in t
        assert "profile/switch" not in t and "PROFIL D'ENTRAÎNEMENT" not in t


def test_la_landing_parle_du_coach(fake_db, client):
    html = client.get("/").get_data(as_text=True)
    assert "coach ia" in html.lower()
    assert "Arcade" not in html


# ── M9 : les styles vivent dans des feuilles, pas dans les gabarits ─


def _gabarits():
    return list((PWA / "templates").glob("*.html"))


def test_les_styles_en_ligne_ne_reviennent_pas():
    """949 attributs style= avant l'extraction (outils/extraire_styles.py).
    Restent seulement ceux qui ne peuvent pas partir : valeur calculée par
    Jinja, ou display:none que des scripts lisent et changent. Cliquet :
    ce nombre ne doit que baisser."""
    import re
    n = sum(len(re.findall(r'(?<![:\w-])style=["\']', p.read_text(encoding="utf-8")))
            for p in _gabarits())
    assert n <= 56, f"{n} attributs style= : relancer outils/extraire_styles.py"


def test_chaque_classe_generee_existe_et_sert():
    import re
    css = (PWA / "static" / "css" / "styles-extraits.css").read_text(encoding="utf-8")
    definies = set(re.findall(r"\.(s-[0-9a-f]{6}):not", css))
    utilisees = set()
    for p in _gabarits():
        utilisees |= set(re.findall(r"\b(s-[0-9a-f]{6})\b", p.read_text(encoding="utf-8")))
    assert utilisees <= definies, f"classes sans règle : {sorted(utilisees - definies)[:5]}"
    assert definies <= utilisees, f"règles mortes : {sorted(definies - utilisees)[:5]}"


def test_la_feuille_generee_est_chargee_partout_ou_elle_sert(fake_db, logged_in):
    import app as appmod
    for page in ("/accueil", "/seance", "/premium"):
        assert "/static/css/styles-extraits.css" in logged_in.get(page).get_data(as_text=True)
    visiteur = appmod.app.test_client()
    assert "/static/css/styles-extraits.css" in visiteur.get("/").get_data(as_text=True)



# ── M11 : pas de fichier fourre-tout ─────────────────────────────


def test_aucun_gabarit_ni_feuille_ne_depasse_900_lignes():
    """seance_edit.html (1 055 l.), programme.html (1 011) et
    components.css (1 261) ont été découpés (audit du 30/09, M11)."""
    trop = []
    for p in list((PWA / "templates").glob("*.html")) + list((PWA / "static" / "css").glob("*.css")):
        if p.name == "styles-extraits.css":
            continue  # généré
        n = len(p.read_text(encoding="utf-8").splitlines())
        if n > 900:
            trop.append(f"{p.name}: {n}")
    assert not trop, trop
