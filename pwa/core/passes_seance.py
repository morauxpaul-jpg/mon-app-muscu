"""Refaire une séance le même jour.

Retour du 14/10 : « si je veux refaire la séance deux fois d'affilée, je ne
peux pas, cela me remet dessus ». Une séance est rangée par (date, nom) à
tous les niveaux (séries, bilan, calques) : la rouvrir le même jour rouvrait
celle déjà faite, et « Recommencer » l'effaçait.

Sans migration, la seconde passe porte son propre nom : « Push 1 · 2 », puis
« · 3 »… Ses exercices viennent de la séance du programme ; ses séries, son
bilan et sa durée sont les siens, la première passe reste intacte.

Module pur : ni Flask ni base.
"""
import re

SEPARATEUR = " · "
_PASSE = re.compile(r"^(.+) · (\d+)$")


def seance_de_base(nom, seances_du_programme):
    """« Push 1 · 2 » → « Push 1 », si « Push 1 » est une séance du programme.
    Un nom qui est lui-même une séance du programme reste tel quel (une
    séance peut s'appeler « Jambes · 2 »)."""
    nom = nom or ""
    if nom in seances_du_programme:
        return nom
    m = _PASSE.match(nom)
    if m and m.group(1) in seances_du_programme:
        return m.group(1)
    return nom


def prochaine_passe(nom, hist, date_iso):
    """Le nom de la passe suivante de `nom` ce jour-là : la première passe
    numérotée sans aucune série enregistrée. Une passe ouverte puis laissée
    vide est donc rouverte, pas doublée."""
    deja = {r.get("Séance") for r in hist if r.get("Date") == date_iso}
    n = 2
    while f"{nom}{SEPARATEUR}{n}" in deja:
        n += 1
    return f"{nom}{SEPARATEUR}{n}"
