"""HSTS en production et robots.txt public (audit du 18/10, m6 et m10)."""


def test_robots_txt_est_public_et_ferme_l_app(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200 and r.mimetype == "text/plain"
    texte = r.get_data(as_text=True)
    assert "Allow: /faq" in texte and texte.rstrip().endswith("Disallow: /")


def test_hsts_seulement_en_production(client, monkeypatch):
    import app as appmod
    assert "Strict-Transport-Security" not in client.get("/robots.txt").headers
    monkeypatch.setattr(appmod, "_IS_PROD", True)
    assert client.get("/robots.txt").headers["Strict-Transport-Security"] == "max-age=31536000"



def test_la_suggestion_de_charge_est_ecrite_a_la_francaise():
    """« Monte à 82,5 kg (+2,5) » sous « Dernière fois : 80 kg × 12 »,
    plus « (+2.5) » (audit du 18/10, m4)."""
    from core.muscu import overload_suggestion
    s = overload_suggestion([{"reps": 12, "poids": 80, "rpe": None}] * 3)
    assert s["label"].startswith("Monte à 82,5 kg (+2,5)")


def test_la_page_daccueil_prouve_a_google_que_le_site_est_au_proprietaire(client):
    """Search Console lit cette balise sur `/` (visiteur non connecté) pour
    valider la propriété de muscu-tracker.up.railway.app, préalable à la
    validation de la marque sur l'écran de connexion Google (07/11/2026)."""
    r = client.get("/")
    assert r.status_code == 200
    assert ('<meta name="google-site-verification" '
            'content="VmeFTTguVR2SFtdMCPHqHAp_TARcIaYxHtAdBWxBJkk">') in r.get_data(as_text=True)
    assert "Allow: /$" in client.get("/robots.txt").get_data(as_text=True)
