"""Parcours d'achat dans l'application native (Android/iOS).

Google Play interdit de vendre un bien numérique consommé dans l'app
autrement que par Play Billing. Afficher un tarif ou un bouton « S'abonner »
qui mène vers Stripe suffit à tomber sous la règle — et se paye à la revue,
quand l'app est déjà prête à publier.

Mais la règle ne lie que les apps DISTRIBUÉES par Play. L'APK est installé
à la main : le parcours d'achat y est donc visible, et `HIDE_NATIVE_BILLING`
le retire le jour d'un dépôt sur le Store. Ces tests vérifient les deux
positions de l'interrupteur — celle d'aujourd'hui et celle de la revue.
"""
import time

import pytest

from conftest import USER_ID


@pytest.fixture()
def play_store(monkeypatch):
    """Simule la distribution par Play : tarifs masqués en natif."""
    monkeypatch.setenv("HIDE_NATIVE_BILLING", "1")

# Ajouté par la coquille Capacitor (capacitor.config.json → appendUserAgent).
UA_NATIF = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/120 MuscuTrackerApp/1"}
UA_WEB = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) Chrome/120 Mobile Safari/537.36"}

PAGES_AVEC_UPSELL = ["/premium", "/coach", "/nutrition"]


@pytest.fixture()
def gratuit(client):
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=True,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time(), _csrf="x")
    return client


@pytest.mark.parametrize("path", PAGES_AVEC_UPSELL)
def test_aucun_tarif_dans_lapp_native(fake_db, gratuit, play_store, path):
    html = gratuit.get(path, headers=UA_NATIF).get_data(as_text=True)
    assert "€" not in html, f"{path} affiche un tarif dans l'app native"


@pytest.mark.parametrize("path", PAGES_AVEC_UPSELL)
def test_aucun_bouton_dachat_dans_lapp_native(fake_db, gratuit, play_store, path):
    html = gratuit.get(path, headers=UA_NATIF).get_data(as_text=True)
    assert "/billing/checkout" not in html
    assert "/billing/portal" not in html


@pytest.mark.parametrize("path", PAGES_AVEC_UPSELL)
def test_le_web_garde_son_parcours_dachat(fake_db, gratuit, path):
    """La restriction ne doit pas déborder sur le navigateur : c'est le seul
    endroit où l'app peut encaisser."""
    html = gratuit.get(path, headers=UA_WEB).get_data(as_text=True)
    assert "€" in html


def test_le_web_garde_ses_boutons_dachat(fake_db, gratuit):
    html = gratuit.get("/premium", headers=UA_WEB).get_data(as_text=True)
    assert html.count("/billing/checkout") >= 3     # mensuel, annuel, à vie


def test_lapp_native_explique_au_lieu_de_laisser_un_cul_de_sac(fake_db, gratuit, play_store):
    """Un bouton « Passer en PRO » menant à une page sans bouton, c'est pire
    que pas de bouton du tout."""
    html = gratuit.get("/premium", headers=UA_NATIF).get_data(as_text=True)
    assert "n'est pas proposé à l'achat dans l'application" in html
    mur = gratuit.get("/coach", headers=UA_NATIF).get_data(as_text=True)
    assert "Voir ce que PRO apporte" in mur
    assert "Passer en PRO" not in mur


def test_un_membre_pro_garde_son_acces_dans_lapp_native(fake_db, logged_in, play_store):
    """L'abonnement pris sur le web suit le compte : rien à « restaurer »."""
    html = logged_in.get("/premium", headers=UA_NATIF).get_data(as_text=True)
    assert "Tu es VIP" in html
    # …mais toujours pas de gestion d'abonnement (elle passe par Stripe).
    assert "/billing/portal" not in html


def test_la_coquille_capacitor_annonce_son_user_agent():
    """Sans ce marqueur, le serveur ne peut pas distinguer l'app du navigateur
    et rendrait les tarifs avant même que le JavaScript ne s'exécute."""
    import json
    import io
    from app import NATIVE_UA_MARKER
    cfg = json.load(io.open("../capacitor.config.json", encoding="utf-8"))
    assert NATIVE_UA_MARKER in cfg["android"]["appendUserAgent"]


# ── Hors Play Store : le parcours d'achat reste ouvert ──


@pytest.mark.parametrize("path", PAGES_AVEC_UPSELL)
def test_sans_publication_sur_play_lapp_native_affiche_les_tarifs(fake_db, gratuit, path):
    """C'est l'état par défaut : l'APK est installé à la main, la règle de
    Play ne s'y applique pas, et masquer l'achat ne ferait que fermer une
    porte sans rien protéger."""
    html = gratuit.get(path, headers=UA_NATIF).get_data(as_text=True)
    assert "€" in html


def test_sans_publication_sur_play_lachat_est_possible_en_natif(fake_db, gratuit):
    html = gratuit.get("/premium", headers=UA_NATIF).get_data(as_text=True)
    assert html.count("/billing/checkout") >= 3


def test_linterrupteur_ne_touche_jamais_le_web(fake_db, gratuit, play_store):
    """Même en position « Play Store », le navigateur garde tout : c'est le
    seul endroit où l'app encaisse."""
    html = gratuit.get("/premium", headers=UA_WEB).get_data(as_text=True)
    assert "€" in html and "/billing/checkout" in html


# ── Publicités ───────────────────────────────────────────────────
# La pub « App Open » est en Java : elle ne peut pas lire la session. La page
# lui recopie le statut à chaque chargement (window.MTAds.setTier). Sans cet
# appel, un membre payant reçoit une pub plein écran au retour dans l'app.


def test_le_statut_pro_est_annonce_a_la_couche_native(fake_db, logged_in):
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert 'window.MTAds.setTier("vip")' in html


def test_le_statut_gratuit_est_annonce_aussi(fake_db, gratuit):
    html = gratuit.get("/accueil").get_data(as_text=True)
    assert 'window.MTAds.setTier("free")' in html


def test_lannonce_du_statut_precede_le_script_de_pub(fake_db, gratuit):
    """ads.js gère bandeau et interstitiel ; la pub App Open, elle, part du
    Java. Les deux doivent connaître le statut avant de faire quoi que ce
    soit."""
    html = gratuit.get("/accueil").get_data(as_text=True)
    assert html.index("MTAds.setTier") < html.index("/static/js/ads.js")


def test_les_scripts_de_pub_restent_absents_pour_un_membre_pro(fake_db, logged_in):
    html = logged_in.get("/accueil").get_data(as_text=True)
    assert "/static/js/ads.js" not in html
    assert "__ADS__" not in html


def test_la_couche_java_consulte_le_statut_avant_dafficher():
    """Garde-fou sur le code natif : sans ces trois éléments, la pub
    redeviendrait aveugle au statut, et aucun test Python ne le verrait."""
    import io
    app = io.open("../android/app/src/main/java/com/muscutracker/fit/MainApplication.java",
                  encoding="utf-8").read()
    act = io.open("../android/app/src/main/java/com/muscutracker/fit/MainActivity.java",
                  encoding="utf-8").read()
    assert "adsDisabled()" in app
    assert "if (isShowingAd || adsDisabled())" in app, "showAdIfAvailable ne filtre plus"
    assert "isAdAvailable() || adsDisabled()" in app, "loadAd ne filtre plus"
    assert '"MTAds"' in act, "le pont JS a disparu de MainActivity"
