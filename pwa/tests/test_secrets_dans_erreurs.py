"""Ce que l'app raconte quand une clé manque.

Un message d'erreur qui nomme `ANTHROPIC_API_KEY` apprend à qui le lit le
fournisseur d'IA utilisé et la forme de la configuration — pour un
renseignement qui ne lui sert à rien, puisqu'il ne peut pas poser la clé.
Le détail appartient aux logs, où quelqu'un peut agir ; à l'utilisateur, il
faut une phrase qui dise quoi faire.
"""
import re

import pytest

from conftest import USER_ID, CSRF

# Les fournisseurs et services qu'une erreur ne doit pas nommer.
INTERDITS = ("anthropic", "supabase", "stripe", "railway", "service_role")

# Et, plus généralement, toute variable d'environnement : elles s'écrivent
# toutes en capitales avec des underscores. La règle attrape aussi celles
# qui n'existent pas encore.
NOM_DE_VARIABLE = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")


def _sans_cle(monkeypatch):
    """Simule l'absence de clé, comme sur un déploiement mal configuré."""
    monkeypatch.setattr("routes.coach._env", lambda *a, **k: "", raising=False)
    monkeypatch.setattr("routes.generator._env", lambda *a, **k: "", raising=False)


def _seed(fake):
    fake.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
    }}).execute()


@pytest.mark.parametrize("chemin,charge", [
    ("/coach/ask", {"message": "Comment progresser ?"}),
    ("/generator/generate", {"objectif": "prise de masse", "jours": 3}),
])
def test_une_cle_manquante_ne_nomme_rien_a_lutilisateur(
        fake_db, logged_in, monkeypatch, chemin, charge):
    _seed(fake_db)
    _sans_cle(monkeypatch)
    r = logged_in.post(chemin, json=charge, headers={"X-CSRFToken": CSRF})
    assert r.status_code == 503, r.status_code
    corps = r.get_data(as_text=True)
    fuites = [m for m in INTERDITS if m in corps.lower()]
    fuites += NOM_DE_VARIABLE.findall(corps)
    assert not fuites, f"{chemin} laisse fuir {fuites} : {corps[:200]}"


@pytest.mark.parametrize("chemin,charge", [
    ("/coach/ask", {"message": "Comment progresser ?"}),
    ("/generator/generate", {"objectif": "prise de masse", "jours": 3}),
])
def test_lutilisateur_apprend_quand_meme_quoi_faire(
        fake_db, logged_in, monkeypatch, chemin, charge):
    """Assainir ne veut pas dire se taire : un 503 muet laisse l'utilisateur
    croire qu'il a mal cliqué."""
    _seed(fake_db)
    _sans_cle(monkeypatch)
    # get_json() et pas le texte brut : Flask échappe les accents en \uXXXX,
    # donc « réessaie » n'apparaît pas tel quel dans le corps.
    message = logged_in.post(chemin, json=charge,
                             headers={"X-CSRFToken": CSRF}).get_json()["error"]
    assert "indisponible" in message.lower()
    assert "réessaie" in message.lower()


# ── Quand le fournisseur répond une erreur ───────────────────────


@pytest.mark.parametrize("erreur", [
    "Your credit balance is too low to access the Anthropic API",
    "authentication_error: invalid x-api-key",
    "Internal server error",
])
def test_le_generateur_ne_raconte_pas_lerreur_du_fournisseur(
        fake_db, logged_in, monkeypatch, erreur):
    """Il affichait « Crédit Anthropic épuisé » ou « Clé API Anthropic
    invalide » — audit du 30/09, I22. Le coach, lui, était déjà propre."""
    import sys
    import types
    _seed(fake_db)
    monkeypatch.setattr("routes.generator._env", lambda *a, **k: "cle-de-test", raising=False)

    class Client:
        def __init__(self, **k):
            self.messages = types.SimpleNamespace(create=self._create)

        def _create(self, **k):
            raise RuntimeError(erreur)

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    r = logged_in.post("/generator/generate", json={"objectif": "prise de masse"},
                       headers={"X-CSRFToken": CSRF})
    assert r.status_code == 502
    message = r.get_json()["error"]
    fuites = [m for m in INTERDITS if m in message.lower()]
    assert not fuites, message
    assert "réessaie" in message.lower()
