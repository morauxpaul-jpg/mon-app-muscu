"""Accessibilité — garde-fous sur le rendu réel des pages.

Ces règles ont toutes été cassées au moins une fois : un bouton icône ajouté
sans `aria-label`, un champ dont l'étiquette n'est reliée à rien, une opacité
de texte baissée « pour l'esthétique ». Un lecteur d'écran ne proteste pas :
il lit « bouton », et l'utilisateur ne sait pas sur quoi il appuie.
"""
import glob
import io
import re
from html.parser import HTMLParser

import pytest

from conftest import USER_ID

PAGES = ["/accueil", "/programme", "/progres", "/gestion", "/nutrition",
         "/cardio", "/premium", "/plus", "/coach"]

# Attributs qui fabriquent un nom au moment de l'exécution (Alpine).
_DYNAMIC_NAME = ("x-text", ":aria-label", "x-bind:aria-label",
                 ":placeholder", "x-bind:placeholder", ":title", "x-bind:title")
_STATIC_NAME = ("aria-label", "aria-labelledby", "placeholder", "title", "alt")


class _Control:
    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = attrs
        self.text = ""
        self.dynamic = any(k in attrs for k in _DYNAMIC_NAME)
        self.label_text = ""     # étiquette englobante

    @property
    def label(self):
        return self.attrs.get("class") or self.attrs.get("name") or self.attrs.get("type") or ""

    def named(self, labelled_ids):
        a = self.attrs
        if any((a.get(k) or "").strip() for k in _STATIC_NAME):
            return True
        if self.dynamic or self.text.strip() or self.label_text.strip():
            return True
        return bool(a.get("id")) and a["id"] in labelled_ids


class _Controls(HTMLParser):
    """Relève les contrôles interactifs et ce qui pourrait les nommer.

    Approximation volontaire : on ne rejoue pas l'algorithme complet du
    navigateur, on vérifie qu'il RESTE quelque chose à annoncer — texte,
    aria-label (même posé par Alpine), étiquette reliée ou englobante.
    C'est le seuil qui compte.
    """

    CONTAINERS = {"button", "select", "textarea", "label"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.controls = []
        self.labelled_ids = set()
        self._open = []          # [(tag, control|None)]

    def _current_label(self):
        for tag, ctrl in reversed(self._open):
            if tag == "label":
                return ctrl
        return None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "label":
            if a.get("for"):
                self.labelled_ids.add(a["for"])
            holder = _Control("label", a)
            self._open.append(("label", holder))
            return

        if tag == "input":
            if a.get("type") in ("hidden",):
                return
            c = _Control(tag, a)
            lab = self._current_label()
            if lab is not None:
                # L'étiquette englobante nomme le champ ; son texte arrive
                # souvent APRÈS lui, d'où la référence partagée.
                c.label_holder = lab
            self.controls.append(c)
            return

        if tag in ("button", "select", "textarea"):
            c = _Control(tag, a)
            lab = self._current_label()
            if lab is not None:
                c.label_holder = lab
            self.controls.append(c)
            self._open.append((tag, c))
            return

        # Un enfant peut porter le nom : <button><span x-text="…"></span></button>
        if self._open and any(k in a for k in _DYNAMIC_NAME + _STATIC_NAME):
            for _, ctrl in self._open:
                if ctrl is not None:
                    ctrl.dynamic = True

    def handle_endtag(self, tag):
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i][0] == tag:
                del self._open[i:]
                return

    def handle_data(self, data):
        for _, ctrl in self._open:
            if ctrl is not None:
                ctrl.text += data

    def close(self):
        super().close()
        for c in self.controls:
            holder = getattr(c, "label_holder", None)
            if holder is not None:
                c.label_text = holder.text
        return self


def _parse(html):
    p = _Controls()
    p.feed(html)
    return p.close()


@pytest.mark.parametrize("path", PAGES)
def test_chaque_controle_a_un_nom_annoncable(fake_db, logged_in, path):
    p = _parse(logged_in.get(path).get_data(as_text=True))
    muets = [(c.tag, c.label) for c in p.controls if not c.named(p.labelled_ids)]
    assert not muets, f"{path} : contrôles sans nom accessible → {muets}"


def test_les_trois_niveaux_de_texte_passent_le_contraste_aa():
    """4,5:1 sur le fond de carte, calculé, pas estimé à l'œil."""
    css = io.open("static/css/tokens.css", encoding="utf-8").read()

    def alpha(var):
        m = re.search(rf"--{var}:\s*rgba\(255,255,255,([0-9.]+)\)", css)
        assert m, f"--{var} introuvable"
        return float(m.group(1))

    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    def lum(rgb):
        r, g, b = rgb
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

    def over(a, bg):
        return tuple(a * 255 + (1 - a) * c for c in bg)

    base = (10, 10, 15)                       # --bg-base
    carte = over(0.045, base)                 # --bg-surface par-dessus
    for var in ("text-1", "text-2", "text-3"):
        a = alpha(var)
        for fond in (base, carte):
            fg, lb = lum(over(a, fond)), lum(fond)
            ratio = (max(fg, lb) + 0.05) / (min(fg, lb) + 0.05)
            assert ratio >= 4.5, f"--{var} ({a}) tombe à {ratio:.2f}:1"


def test_la_feuille_accessibilite_est_chargee_en_dernier(fake_db, logged_in):
    """a11y.css corrige des tailles posées ailleurs : chargée avant, elle
    serait écrasée sans que rien ne le signale."""
    html = logged_in.get("/accueil").get_data(as_text=True)
    feuilles = re.findall(r'<link rel="stylesheet" href="(/static/css/[^"]+)"', html)
    assert feuilles, "aucune feuille de style"
    assert feuilles[-1] == "/static/css/a11y.css", feuilles


def test_les_choix_de_lonboarding_sont_des_boutons_radio(fake_db, client):
    """Avant : des <div @click>. Invisibles au clavier, muets pour un lecteur
    d'écran, et aucune notion de « une seule réponse »."""
    import time
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@e.com", onboarded=False,
                 is_vip=False, is_vip_ts=time.time())
    html = client.get("/onboarding").get_data(as_text=True)
    assert '<div class="opt"' not in html, "un choix est resté un <div @click>"
    for groupe in ("ob-sexe", "ob-niveau", "ob-objectif", "ob-equipement", "ob-frequence"):
        assert f'name="{groupe}"' in html, groupe
    assert html.count('role="radiogroup"') == 5


def test_les_expressions_alpine_ne_sont_pas_des_blocs():
    """Alpine évalue une EXPRESSION : `try { … }` lève SyntaxError au
    chargement et la directive ne s'exécute jamais — en silence."""
    fautifs = []
    for f in glob.glob("templates/*.html") + glob.glob("templates/**/*.html"):
        src = io.open(f, encoding="utf-8").read()
        for m in re.finditer(r'(x-init|x-show|x-text|x-if|@[\w.]+)="\s*(try|var|function|switch)\b', src):
            fautifs.append(f + " : " + m.group(0))
    assert not fautifs, fautifs
