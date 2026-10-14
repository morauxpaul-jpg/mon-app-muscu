"""Style « Instrument », PR 3d (13-14/10/2026) : pages restantes (Coach,
Réglages, PRO, connexion, accueil des nouveaux) et plus aucun emoji dans
l'interface."""
import re
import time
from pathlib import Path

from conftest import USER_ID

PWA = Path(__file__).resolve().parent.parent
EMOJI = re.compile("[\U0001F300-\U0001FAFF️]")


def _fichiers_interface():
    for base in ("templates", "static/js"):
        for p in sorted((PWA / base).rglob("*")):
            if p.suffix in (".html", ".js") and "vendor" not in p.parts and not p.name.endswith(".min.js"):
                yield p


def test_plus_aucun_emoji_dans_l_interface():
    """Le propriétaire : l'app « ressemble aux apps vibe codées ». Les emojis
    (choix de l'accueil des nouveaux, PRO, toasts, carte de partage) en
    étaient la marque la plus visible. Les icônes du sprite les remplacent ;
    ✓ et ✕ restent : ce sont des caractères de texte."""
    trouves = []
    for p in _fichiers_interface():
        for i, ligne in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if EMOJI.search(ligne):
                trouves.append(f"{p.relative_to(PWA)}:{i}: {ligne.strip()[:80]}")
    assert not trouves, trouves


def test_une_seule_couleur_vive_l_or_suit_le_vert():
    """Le diamant PRO, les trophées et le premier du podium étaient jaune or
    (#ffd60a) : une deuxième couleur vive."""
    tokens = (PWA / "static/css/tokens.css").read_text(encoding="utf-8")
    accent = re.search(r"--accent:\s*(#[0-9a-fA-F]{6})", tokens).group(1).lower()
    assert re.search(r"--gold:\s*(#[0-9a-fA-F]{6})", tokens).group(1).lower() == accent
    css = "".join(p.read_text(encoding="utf-8") for p in (PWA / "static/css").glob("*.css"))
    gabarits = "".join(p.read_text(encoding="utf-8") for p in (PWA / "templates").glob("*.html"))
    for or_ in ("#FFD700", "rgba(255,215,0"):
        assert or_ not in css and or_ not in gabarits, or_


def test_la_difficulte_des_programmes_tient_dans_quatre_barres():
    """« '☆'.repeat(3 - difficulte) » levait « Invalid count value: -1 » pour
    les deux programmes de difficulté 4 (PPL Avancé 6j, Upper/Lower Avancé
    5j) : la ligne restait vide. Quatre barres, une par niveau."""
    from core import catalog
    assert max(p.get("difficulty", 1) for p in catalog.list_programs()) <= 4
    src = (PWA / "templates/onboarding.html").read_text(encoding="utf-8")
    assert ".repeat(" not in src
    assert src.count("x-for=\"n in [1, 2, 3, 4]\"") == 2


def test_l_accueil_des_nouveaux_est_en_mots(fake_db, client):
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=False,
                 is_vip=False, is_vip_ts=time.time())
    html = client.get("/onboarding").get_data(as_text=True)
    assert 'class="emoji"' not in html
    assert "p.icon" not in html and "previewProg.icon" not in html
    # Le choix fait est en blanc (sélection), plus en vert.
    assert ".opt.sel { border-color: var(--text-1); background: var(--text-1);" in html


def test_les_reglages_sont_des_interrupteurs(fake_db, logged_in):
    html = logged_in.get("/gestion").get_data(as_text=True)
    reglages = re.findall(r'<label class="reglage">.*?</label>', html, re.S)
    assert len(reglages) == 7
    for r in reglages:
        assert 'role="switch"' in r
    # Les cases « Je comprends » des zones dangereuses restent des cases.
    assert html.count('name="confirm" value="yes" required') == 2


def test_la_connexion_n_affiche_plus_l_ancienne_icone(client):
    html = client.get("/login").get_data(as_text=True)
    assert "icon-192.png\" alt" not in html
    assert '<h1 class="app-logo">Muscu Tracker</h1>' in html
    assert "Continuer avec Google" in html


def test_le_coach_n_a_plus_d_alerte_orange_ni_de_retrait_parasite(fake_db, logged_in):
    src = (PWA / "templates/coach.html").read_text(encoding="utf-8")
    assert "#FFB347" not in src and "rgba(255,159,10" not in src
    # white-space: pre-wrap : l'indentation du gabarit devenait un retrait
    # visible avant « Salut ».
    assert '<div class="msg-bubble">Salut <strong' in src


def test_la_connexion_n_est_plus_calee_en_bas_de_l_ecran(client):
    """Calé en bas (justify-content: flex-end), le bloc laissait sur
    téléphone un grand vide noir au-dessus du nom (retour du propriétaire,
    14/10/2026). Il est centré, ouvert par l'haltère de l'icône."""
    html = client.get("/login").get_data(as_text=True)
    regle = html[html.index(".login-wrap {"):]
    regle = regle[:regle.index("}")]
    assert "justify-content: center" in regle
    assert "flex-end" not in regle
    assert 'icons.svg#logo' in html


def test_la_page_publique_montre_l_accueil_actuel(client):
    """Le croquis de l'app sur la page publique montrait encore l'interface
    « verre » retirée le 13/10 : cartes translucides arrondies, « STREAK »
    en orange (retour du propriétaire, 14/10/2026)."""
    html = client.get("/").get_data(as_text=True)
    croquis = html[html.index('<svg class="landing-mockup"'):]
    croquis = croquis[:croquis.index("</svg>")]
    assert "PROCHAINE SÉANCE" in croquis and "COMMENCER" in croquis
    assert "STREAK" not in croquis and "rgba(" not in croquis
    # Le bouton principal : plein, texte noir, sans halo ni ombre.
    style = html[html.index("<style>"):html.index("</style>")]
    assert "box-shadow: 0 0" not in style
    assert "rgba(200,240,49,0.15)" not in style
    regle = style[style.index(".landing-cta {"):]
    regle = regle[:regle.index("}")]
    assert "background: var(--accent)" in regle
    assert "color: var(--on-accent)" in regle
