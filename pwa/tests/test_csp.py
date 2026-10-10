"""La CSP bloque, sans `unsafe-inline` ni `unsafe-eval` pour les scripts.

Audit du 06/10 (m6) : la politique complète n'était qu'en observation
(Report-Only) et permettait encore les scripts écrits dans la page et
`eval`. Elle bloque désormais (core/csp.py). Ces tests gardent les règles
sans navigateur ; tests/e2e/test_csp_navigateur.py joue les pages pour de vrai.
"""
import glob
import logging
import os
import re

import pytest

from core import csp

PWA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GABARITS = sorted(glob.glob(os.path.join(PWA, "templates", "*.html")))
SCRIPT = re.compile(r"<script\b([^>]*)>", re.I)
NONCE = re.compile(r"'nonce-([^']+)'")


def _script_src(politique):
    return next(d for d in politique.split(";") if d.strip().startswith("script-src"))


def _sans_commentaires(texte):
    return re.sub(r"\{#.*?#\}", "", texte, flags=re.S)


def _scripts_en_ligne(html):
    """Attributs des <script> qui exécutent du code écrit dans la page."""
    for m in SCRIPT.finditer(html):
        attrs = m.group(1)
        if "src=" in attrs or re.search(r'type="application/(ld\+)?json"', attrs):
            continue
        yield attrs


def test_la_politique_bloque_et_refuse_unsafe_pour_les_scripts(client):
    r = client.get("/")
    politique = r.headers["Content-Security-Policy"]
    scripts = _script_src(politique)
    assert "'self'" in scripts
    assert "unsafe-inline" not in scripts and "unsafe-eval" not in scripts
    assert "object-src 'none'" in politique and "frame-ancestors 'self'" in politique
    assert "report-uri /csp/rapport" in politique
    assert "Content-Security-Policy-Report-Only" not in r.headers


def test_chaque_script_de_la_page_porte_le_jeton_de_la_reponse(client):
    r1, r2 = client.get("/login"), client.get("/login")
    n1 = NONCE.search(r1.headers["Content-Security-Policy"]).group(1)
    n2 = NONCE.search(r2.headers["Content-Security-Policy"]).group(1)
    assert n1 != n2 and len(n1) >= 16                   # neuf à chaque réponse
    attrs = list(_scripts_en_ligne(r1.get_data(as_text=True)))
    assert attrs and all(f'nonce="{n1}"' in a for a in attrs)


PAGES = ["/accueil", "/programme", "/gestion", "/nutrition", "/coach", "/generator",
         "/plaques", "/progres", "/parrainage", "/cardio", "/seance"]


def test_les_pages_connectees_aussi(logged_in):
    vues = 0
    for page in PAGES:
        r = logged_in.get(page)
        if r.status_code != 200:
            continue
        vues += 1
        politique = r.headers["Content-Security-Policy"]
        m = NONCE.search(politique)
        attrs = list(_scripts_en_ligne(r.get_data(as_text=True)))
        if attrs:
            assert m, page
            assert all(f'nonce="{m.group(1)}"' in a for a in attrs), page
    assert vues >= 8


@pytest.mark.parametrize("chemin", GABARITS, ids=os.path.basename)
def test_aucun_gabarit_ne_garde_de_onclick_ni_de_script_sans_jeton(chemin):
    """Un onclick="…" ou un <script> sans jeton ne casse rien à l'écran : le
    bouton ne fait juste plus rien. D'où la vérification à la source."""
    texte = _sans_commentaires(open(chemin, encoding="utf-8").read())
    gestionnaires = re.findall(r"""<[^>]*\son[a-z]+\s*=\s*["']""", texte)
    assert gestionnaires == []
    for attrs in _scripts_en_ligne(texte):
        assert 'nonce="{{ csp_nonce() }}"' in attrs, attrs
    assert "javascript:" not in texte


# Ce que le lecteur d'expressions d'Alpine CSP refuse, une fois les chaînes
# retirées : plusieurs instructions, fonctions fléchées, `?.`, `??`,
# gabarits `${}`, typeof/new, expressions régulières.
_INTERDITS = {";": "plusieurs instructions", "=>": "fonction fléchée", "?.": "?.", "??": "??",
              "`": "gabarit", "typeof ": "typeof", "new ": "new", "/(": "expression régulière",
              "/ ": "expression régulière"}
# …et les globales, qu'elle ne voit pas (seules les données du composant
# et les magies `$…` existent pour elle).
_GLOBALES = re.compile(r"(?<![\w.$])(Math|JSON|Number|String|Object|Array|Date|window|document|"
                       r"localStorage|sessionStorage|console|location|navigator|parseInt|"
                       r"parseFloat|EXERCISE_\w+|LIBRARY_\w+)\b|(?<![\w.$])(confirm|alert)\s*\(")
_ATTR_ALPINE = re.compile(r"""\s((?:x-[\w:.\-]+|@[\w.\-:]+|:[\w.\-]+))\s*=\s*("([^"]*)"|'([^']*)')""", re.S)
_SANS_EXPRESSION = ("x-ref", "x-cloak", "x-transition", "x-ignore", "x-teleport", "x-id")


def _sans_chaines(expr):
    return re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", "''", expr)


@pytest.mark.parametrize("chemin", GABARITS, ids=os.path.basename)
def test_les_expressions_alpine_restent_lisibles_par_la_version_csp(chemin):
    texte = _sans_commentaires(open(chemin, encoding="utf-8").read())
    fautes = []
    for m in _ATTR_ALPINE.finditer(texte):
        nom = m.group(1)
        if nom.split(".")[0].split(":")[0] in _SANS_EXPRESSION or nom.startswith("x-transition"):
            continue
        valeur = m.group(3) if m.group(3) is not None else m.group(4)
        valeur = valeur.replace("&quot;", '"').replace("&#39;", "'")
        valeur = re.sub(r"\{\{.*?\}\}", "0", valeur)       # Jinja : une valeur
        nu = _sans_chaines(valeur)
        if nom.startswith("x-for"):
            nu = nu.split(" in ", 1)[-1]
        if re.search(r"^\s*\{.*\(\)\s*\{", nu, re.S):          # méthode dans un x-data
            fautes.append((nom, valeur[:60], "méthode dans un objet"))
        for motif, pourquoi in _INTERDITS.items():
            if motif in nu:
                fautes.append((nom, valeur[:60], pourquoi))
        g = _GLOBALES.search(nu)
        if g:
            fautes.append((nom, valeur[:60], "globale " + (g.group(1) or g.group(2))))
    assert fautes == []


def test_mode_observation_et_coupure(client, monkeypatch):
    monkeypatch.setenv("CSP_OBSERVER", "1")
    r = client.get("/")
    assert r.headers["Content-Security-Policy"] == csp.COUCHE_SURE
    assert "script-src 'self'" in r.headers["Content-Security-Policy-Report-Only"]
    monkeypatch.delenv("CSP_OBSERVER")
    monkeypatch.setenv("CSP_DISABLED", "1")
    r = client.get("/")
    assert "Content-Security-Policy" not in r.headers
    assert "Content-Security-Policy-Report-Only" not in r.headers


def test_un_blocage_arrive_dans_les_journaux_une_fois(client, caplog):
    """Sans session ni jeton CSRF : c'est le navigateur qui poste."""
    from routes import csp as route
    route._DEJA_VUS.clear()
    rapport = {"csp-report": {
        "document-uri": "https://muscu.example/programme?apply=ppl",
        "effective-directive": "script-src-attr", "blocked-uri": "inline",
        "source-file": "https://muscu.example/programme", "line-number": 42,
        "script-sample": "moveSeanceExo(this,1)"}}
    with caplog.at_level(logging.WARNING, logger="routes.csp"):
        for _ in range(3):
            r = client.post("/csp/rapport", json=rapport,
                            headers={"Content-Type": "application/csp-report"})
            assert r.status_code == 204
    lignes = [rec.getMessage() for rec in caplog.records if "CSP bloqué" in rec.getMessage()]
    assert len(lignes) == 1
    assert "script-src-attr" in lignes[0] and "/programme" in lignes[0]
    assert "apply=ppl" not in lignes[0]                 # pas de paramètres au journal


def test_un_rapport_malforme_ne_fait_pas_d_erreur(client):
    assert client.post("/csp/rapport", data="pas du json").status_code == 204
    assert client.post("/csp/rapport", json=[1, 2]).status_code == 204
