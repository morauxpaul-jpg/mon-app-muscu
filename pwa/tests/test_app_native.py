"""Parcours d'achat dans l'application native (Android/iOS).

Google Play interdit de vendre un bien numérique consommé dans l'app
autrement que par Play Billing. Afficher un tarif ou un bouton « S'abonner »
qui mène vers Stripe suffit à tomber sous la règle — et se paye au moment de
la revue, quand l'app est déjà prête à publier.

Tant que Play Billing n'est pas intégré : aucun tarif, aucun bouton d'achat
dans l'app native. Sur le web et la PWA, rien ne change.
"""
import time

import pytest

from conftest import USER_ID

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
def test_aucun_tarif_dans_lapp_native(fake_db, gratuit, path):
    html = gratuit.get(path, headers=UA_NATIF).get_data(as_text=True)
    assert "€" not in html, f"{path} affiche un tarif dans l'app native"


@pytest.mark.parametrize("path", PAGES_AVEC_UPSELL)
def test_aucun_bouton_dachat_dans_lapp_native(fake_db, gratuit, path):
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


def test_lapp_native_explique_au_lieu_de_laisser_un_cul_de_sac(fake_db, gratuit):
    """Un bouton « Passer en PRO » menant à une page sans bouton, c'est pire
    que pas de bouton du tout."""
    html = gratuit.get("/premium", headers=UA_NATIF).get_data(as_text=True)
    assert "n'est pas proposé à l'achat dans l'application" in html
    mur = gratuit.get("/coach", headers=UA_NATIF).get_data(as_text=True)
    assert "Voir ce que PRO apporte" in mur
    assert "Passer en PRO" not in mur


def test_un_membre_pro_garde_son_acces_dans_lapp_native(fake_db, logged_in):
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
