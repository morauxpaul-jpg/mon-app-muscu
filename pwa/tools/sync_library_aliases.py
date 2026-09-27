# -*- coding: utf-8 -*-
"""Recopie dans la bibliothèque les surnoms que le catalogue connaît déjà.

La bibliothèque (`static/js/exercise-library.js`) est ce qu'on parcourt pour
choisir un exercice. Le catalogue (`core/exercises_data.py`), lui, sait que
« overhead triceps extension » désigne l'extension nuque haltère. Tant que
la bibliothèque l'ignore, l'exercice est là mais introuvable — et on conclut
qu'il n'existe pas.

Plutôt que de tenir deux listes de surnoms qui divergeront, celle-ci est
DÉRIVÉE de l'autre. Un surnom ajouté côté Python se propage ici.

    cd pwa && python tools/sync_library_aliases.py           # écrit
    cd pwa && python tools/sync_library_aliases.py --verifie # compare
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.exercises_data import (EXERCISES_INFO, _ABSORBES, _ANGLAIS,  # noqa: E402
                                 _PAR_ALIAS, resoudre)

RACINE = os.path.join(os.path.dirname(__file__), "..")
FICHIER = os.path.join(RACINE, "static", "js", "exercise-library.js")


def _surnoms_par_exercice():
    """Tout ce qui, dans le catalogue, désigne chaque exercice."""
    surnoms = {}
    for nom, fiche in EXERCISES_INFO.items():
        mots = {nom, fiche.get("name") or nom}
        # Le nom entre parenthèses : « Presse à cuisses (Leg press) ».
        mots |= set(re.findall(r"\(([^)]*)\)", fiche.get("name") or ""))
        surnoms[nom] = mots
    for surnom, cible in list(_ANGLAIS.items()) + list(_PAR_ALIAS.items()):
        if cible in surnoms:
            surnoms[cible].add(surnom)
    # Les noms absorbés restent des façons de nommer l'exercice : quelqu'un
    # qui tape « développé incliné haltères » doit toujours le trouver.
    for absorbe, (base, materiel) in _ABSORBES.items():
        if base in surnoms:
            surnoms[base].add(absorbe)
            surnoms[base].add(materiel)
    return surnoms


def _entrees_bibliotheque():
    sortie = subprocess.run(
        ["node", "-e",
         "const l=require('./static/js/exercise-library.js');"
         "console.log(JSON.stringify(Object.values(l.EXERCISE_LIBRARY)"
         ".flat().map(e=>e.name)))"],
        capture_output=True, text=True, encoding="utf-8", cwd=RACINE)
    if sortie.returncode != 0:
        raise SystemExit("node indisponible : " + sortie.stderr[:200])
    return json.loads(sortie.stdout)


def alias_attendus():
    """{nom de bibliothèque: chaîne de surnoms}, pour ce qui en mérite."""
    surnoms = _surnoms_par_exercice()
    attendus = {}
    for nom in _entrees_bibliotheque():
        cle = resoudre(nom)[0]
        if not cle:
            continue
        mots = {m.strip() for m in surnoms.get(cle, set()) if m and m.strip()}
        # Inutile de répéter ce que le nom de l'entrée contient déjà.
        mots = {m for m in mots if m.casefold() not in nom.casefold()}
        if mots:
            attendus[nom] = " ".join(sorted(mots))
    return attendus


def ecrire():
    attendus = alias_attendus()
    s = io.open(FICHIER, encoding="utf-8").read()
    # On repart d'une bibliothèque sans alias : le fichier est dérivé, il ne
    # doit pas accumuler les couches des exécutions précédentes.
    s = re.sub(r'(\{ name: "[^"]+",) alias: "[^"]*",', r"\1", s)
    faits = 0
    for nom, alias in attendus.items():
        motif = '{ name: "%s",' % nom
        if motif in s:
            s = s.replace(motif, '{ name: "%s", alias: "%s",' % (nom, alias))
            faits += 1
    io.open(FICHIER, "w", encoding="utf-8", newline="\n").write(s)
    return faits


def ecarts():
    """Ce qui manque ou diffère entre le fichier et ce qu'on attend."""
    s = io.open(FICHIER, encoding="utf-8").read()
    presents = dict(re.findall(r'\{ name: "([^"]+)", alias: "([^"]*)"', s))
    manquants = []
    for nom, alias in alias_attendus().items():
        if presents.get(nom) != alias:
            manquants.append(nom)
    return sorted(manquants)


if __name__ == "__main__":
    if "--verifie" in sys.argv:
        m = ecarts()
        print("à resynchroniser :", m or "rien")
        raise SystemExit(1 if m else 0)
    print(f"{ecrire()} entrées annotées")
