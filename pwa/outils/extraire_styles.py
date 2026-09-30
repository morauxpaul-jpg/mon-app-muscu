"""Sort les attributs `style="…"` des gabarits vers une feuille de style.

Audit du 30/09 (M9) : 949 attributs style= dans les gabarits. Ce script
remplace chaque style FIXE par une classe générée (`s-xxxxxx`, une par valeur
distincte), écrite dans `static/css/styles-extraits.css`.

Ce qui reste en ligne, volontairement :
  - un style qui contient du Jinja (`{{ … }}`, `{% … %}`) : sa valeur change
    d'une page à l'autre ;
  - `display:none` : des scripts lisent et changent `el.style.display` pour
    ouvrir et fermer des fenêtres — le déplacer changerait leur logique.

Priorité : un style en ligne l'emporte sur toute règle de feuille (hors
!important). La règle générée porte donc `:not(#_s):not(#_s)`, qui lui donne
la priorité de deux identifiants — au-dessus de toutes les règles de l'app —
sans rien changer à ce qu'elle sélectionne. Un style posé par JavaScript
(`el.style.x = …`) reste en ligne, et garde donc le dernier mot, comme avant.

Idempotent : relancé, il ajoute seulement les nouveaux styles. Usage :
    cd pwa && python outils/extraire_styles.py
"""
import hashlib
import html
import re
from pathlib import Path

PWA = Path(__file__).resolve().parents[1]
GABARITS = PWA / "templates"
FEUILLE = PWA / "static" / "css" / "styles-extraits.css"

ENTETE = """/* ════════════════════════════════════════════════════════════════
   Styles sortis des gabarits — FICHIER GÉNÉRÉ par outils/extraire_styles.py
   ════════════════════════════════════════════════════════════════
   Chaque classe s-xxxxxx remplace un attribut style="…" identique.
   `:not(#_s):not(#_s)` leur donne la priorité qu'avait le style en ligne
   (deux identifiants : au-dessus de toute règle de l'app). Pour changer un
   style, modifier la règle ici — ou mieux, lui donner une vraie classe
   nommée dans components.css et retirer la s-xxxxxx du gabarit.
   ════════════════════════════════════════════════════════════════ */
"""


def declarations(valeur):
    """Découpe « a:b; c:d(e;f) » en déclarations, sans couper dans les ( )."""
    out, cur, prof = [], "", 0
    for ch in valeur:
        if ch == "(":
            prof += 1
        elif ch == ")":
            prof -= 1
        if ch == ";" and prof == 0:
            if cur.strip():
                out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return [" ".join(d.split()) for d in out]


def reste_en_ligne(decl):
    prop, _, val = decl.partition(":")
    return prop.strip().lower() == "display" and val.strip().lower().startswith("none")


def nom_classe(decls):
    return "s-" + hashlib.sha1("; ".join(decls).encode("utf-8")).hexdigest()[:6]


def attributs(balise):
    """[(nom, début, fin, valeur, quote)] des attributs d'une balise ouvrante,
    en respectant les guillemets et les blocs Jinja."""
    res, i, n = [], 0, len(balise)
    while i < n:
        if balise.startswith("{{", i) or balise.startswith("{%", i):
            j = balise.find("}}" if balise[i + 1] == "{" else "%}", i)
            i = n if j < 0 else j + 2
            continue
        m = re.compile(r'([:@\w.\-]+)\s*=\s*(["\'])').match(balise, i)
        if m and (i == 0 or balise[i - 1].isspace()):
            q = m.group(2)
            debut_val = m.end()
            fin_val = balise.find(q, debut_val)
            if fin_val < 0:
                break
            res.append((m.group(1), i, fin_val + 1, balise[debut_val:fin_val], q))
            i = fin_val + 1
            continue
        i += 1
    return res


def traiter(texte, regles):
    """Réécrit un gabarit ; remplit `regles` {classe: déclarations}."""
    sortie, i, n = [], 0, len(texte)
    brut = re.compile(r"<(script|style)\b", re.I)
    while i < n:
        if texte.startswith("{#", i):
            j = texte.find("#}", i)
            j = n if j < 0 else j + 2
            sortie.append(texte[i:j]); i = j; continue
        m = brut.match(texte, i)
        if m:
            fin = re.compile(r"</%s\s*>" % m.group(1), re.I).search(texte, i)
            j = n if not fin else fin.end()
            # La balise ouvrante <script …> elle-même peut porter un style : rare, ignoré.
            sortie.append(texte[i:j]); i = j; continue
        if texte[i] == "<" and i + 1 < n and texte[i + 1].isalpha():
            # Fin de la balise : premier « > » hors guillemets et hors Jinja.
            j, q = i + 1, None
            while j < n:
                c = texte[j]
                if q:
                    if c == q:
                        q = None
                elif c in "\"'":
                    q = c
                elif texte.startswith("{{", j) or texte.startswith("{%", j):
                    k = texte.find("}}" if texte[j + 1] == "{" else "%}", j)
                    j = n if k < 0 else k + 1
                elif c == ">":
                    break
                j += 1
            balise = texte[i:j + 1]
            sortie.append(reecrire_balise(balise, regles))
            i = j + 1
            continue
        sortie.append(texte[i]); i += 1
    return "".join(sortie)


def reecrire_balise(balise, regles):
    attrs = attributs(balise)
    style = next((a for a in attrs if a[0] == "style"), None)
    if not style or "{{" in style[3] or "{%" in style[3]:
        return balise
    decls = declarations(html.unescape(style[3]))
    en_ligne = [d for d in decls if reste_en_ligne(d)]
    a_sortir = [d for d in decls if not reste_en_ligne(d)]
    if not a_sortir:
        return balise
    classe = nom_classe(a_sortir)
    regles[classe] = a_sortir
    _nom, debut, fin, _valeur, _q = style
    if en_ligne:
        # Réduit l'attribut à ce qui doit rester en ligne.
        balise = balise[:debut] + f'style="{"; ".join(en_ligne)};"' + balise[fin:]
    else:
        # Retire l'attribut, espace qui le précède compris.
        balise = balise[:debut].rstrip() + balise[fin:]
    # Ajoute la classe à l'attribut class (statique) ou en crée un.
    attrs = attributs(balise)
    cls = next((a for a in attrs if a[0] == "class"), None)
    if cls:
        nom, debut, fin, valeur, q = cls
        valeur2 = (valeur + " " + classe).strip()
        return balise[:debut] + f"class={q}{valeur2}{q}" + balise[fin:]
    m = re.match(r"<[\w:-]+", balise)
    return balise[:m.end()] + f' class="{classe}"' + balise[m.end():]


def main():
    regles = {}
    if FEUILLE.exists():
        for m in re.finditer(r"\.(s-[0-9a-f]{6}):not\(#_s\):not\(#_s\) \{ (.*?) \}", FEUILLE.read_text(encoding="utf-8")):
            regles[m.group(1)] = [d.strip() for d in m.group(2).split(";") if d.strip()]
    avant = sum(len(re.findall(r'(?<![:\w-])style=["\']', p.read_text(encoding="utf-8")))
                for p in GABARITS.glob("*.html"))
    for p in sorted(GABARITS.glob("*.html")):
        t = p.read_text(encoding="utf-8")
        t2 = traiter(t, regles)
        if t2 != t:
            p.write_text(t2, encoding="utf-8")
    apres = sum(len(re.findall(r'(?<![:\w-])style=["\']', p.read_text(encoding="utf-8")))
                for p in GABARITS.glob("*.html"))
    lignes = [ENTETE]
    for classe in sorted(regles):
        lignes.append(f".{classe}:not(#_s):not(#_s) {{ {'; '.join(regles[classe])}; }}")
    FEUILLE.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"style= : {avant} -> {apres} ; {len(regles)} classes dans {FEUILLE.name}")


if __name__ == "__main__":
    main()
