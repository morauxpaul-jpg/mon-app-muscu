"""La fiche utilisateur de la console admin s'ouvre, et n'exécute rien de
ce qu'un utilisateur a écrit (audit du 30/09, C4 et I20).

Deux défauts qui se masquaient l'un l'autre : le prénom (libre, 40
caractères) était injecté par innerHTML — un prénom « <img onerror=…> »
s'exécutait dans la session de l'admin — mais la fiche ne s'ouvrait plus,
car `|tojson` dans un onclick entre guillemets coupait l'attribut. Corriger
le second sans le premier ouvrait la faille.
"""
import re
import types

import pytest

from conftest import USER_ID


@pytest.fixture()
def admin(fake_db, logged_in, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "test@example.com")
    fake_db.auth.admin.list_users = lambda **k: [types.SimpleNamespace(
        id=USER_ID, email='a"b@example.com', created_at="2026-09-01")]
    fake_db.table("profiles").insert(
        {"id": USER_ID, "tier": "free", "prenom": "<img src=x onerror=alert(1)>"}).execute()
    return logged_in


def test_la_ligne_ouvre_la_fiche_sans_onclick(admin):
    html = admin.get("/admin").get_data(as_text=True)
    assert "onclick=\"adminShowUser(" not in html
    ligne = re.search(r'<div class="admin-user-open"[^>]*>', html).group(0)
    assert f'data-uid="{USER_ID}"' in ligne
    assert 'data-label="a&#34;b@example.com"' in ligne or 'data-label="a&quot;b@example.com"' in ligne


def test_le_prenom_nest_jamais_injecte_brut(admin):
    html = admin.get("/admin").get_data(as_text=True)
    assert "<img src=x onerror" not in html, "le prénom de la liste reste échappé"
    script = html[html.index("function adminShowUser"):]
    script = script[:script.index("function adminResetQuota")]
    # Toute valeur venant de la fiche passe par esc() avant innerHTML.
    brutes = re.findall(r"'\s*\+\s*\(?(d\.\w+)", script)
    assert brutes == [], f"valeurs injectées sans esc() : {brutes}"
    assert "esc(d.prenom" in script
