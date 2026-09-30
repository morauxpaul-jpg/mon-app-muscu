"""Lire l'export Strava : `activities.csv`, une ligne par séance.

Pourquoi le fichier et pas l'API : depuis juin 2026, l'accès API « Standard »
de Strava exige un abonnement actif (11,99 $/mois). Construire l'import
dessus, c'est construire quelque chose qui s'éteint le jour où on cesse de
payer. L'export de ses propres données, lui, reste gratuit — Paramètres →
Mon compte → « Demander votre archive ».

**Ce fichier n'est pas propre**, et chaque précaution ci-dessous répond à un
piège réel :

* Les en-têtes changent avec la langue du compte (« Activity Date » ou
  « Date de l'activité »). On compare donc des noms normalisés contre une
  liste d'alias, jamais une position de colonne.
* La date est écrite dans le format local (« Sep 14, 2026, 6:12:07 PM »,
  « 14 sept. 2026 18:12 », « 14/09/2026 »). On essaie plusieurs formes et on
  compte celles qu'on n'a pas su lire, au lieu de les perdre en silence.
* Les distances sont en mètres et les durées en secondes — mais pas toujours,
  selon la version de l'export. Plutôt que de parier, on tranche par la
  **vitesse que chaque hypothèse implique** : 5 000 pour une heure de course,
  c'est des mètres ; 5, c'est des kilomètres.

Le module ne fait que LIRE et proposer. Rien n'est écrit en base ici : c'est
la route qui décide, après que l'utilisateur a vu ce qui va entrer.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
import datetime as _dt

# Nos activités, telles que `routes/cardio.py` les nomme. Ce qui n'est pas du
# cardio (musculation, yoga…) n'a rien à faire ici : l'app le suit ailleurs.
_TYPES = {
    "run": "Course", "trailrun": "Course", "virtualrun": "Course",
    "coursesurroute": "Course", "courseapied": "Course", "trail": "Course",
    "ride": "Vélo", "virtualride": "Vélo", "mountainbikeride": "Vélo",
    "gravelride": "Vélo", "ebikeride": "Vélo", "velo": "Vélo",
    "sortieavelo": "Vélo", "cyclisme": "Vélo",
    "swim": "Natation", "natation": "Natation",
    "walk": "Marche", "marche": "Marche",
    "hike": "Marche", "randonnee": "Marche",
    "rowing": "Rameur", "virtualrow": "Rameur", "rameur": "Rameur",
    "elliptical": "Elliptique", "elliptique": "Elliptique",
    "stairstepper": "Montée d'escaliers", "escaliers": "Montée d'escaliers",
    "workout": "HIIT", "crossfit": "HIIT", "hiit": "HIIT",
    "entrainement": "HIIT",
    "jumprope": "Corde", "cordeasauter": "Corde",
}
# Reconnus, et volontairement ignorés : l'app les suit comme des séances.
_HORS_CARDIO = {
    "weighttraining": "musculation", "musculation": "musculation",
    "yoga": "yoga", "workoutstrength": "musculation",
    "crosstraining": "renforcement",
}

# Alias d'en-tête, normalisés. Le premier trouvé gagne.
_COLONNES = {
    "date": ("activitydate", "datedelactivite", "date"),
    "nom": ("activityname", "nomdelactivite", "nom"),
    "type": ("activitytype", "typedactivite", "typedelactivite", "sport", "type"),
    "duree": ("elapsedtime", "tempsecoule", "movingtime", "tempsdedeplacement",
              "duree", "tempstotal"),
    "distance": ("distance",),
    "calories": ("calories",),
}

_MOIS = {
    "jan": 1, "feb": 2, "fev": 2, "mar": 3, "apr": 4, "avr": 4, "may": 5,
    "mai": 5, "jun": 6, "juin": 6, "jul": 7, "juil": 7, "aug": 8, "aou": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Vitesses plausibles, en m/s. Marche lente d'un côté, descente à vélo de
# l'autre : au-delà, l'hypothèse d'unité est la mauvaise.
_V_MIN, _V_MAX = 0.3, 30.0


def _cle(texte) -> str:
    """Minuscules, sans accent ni ponctuation : « Date de l'activité » →
    « datedelactivite »."""
    t = unicodedata.normalize("NFD", str(texte or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", t.lower())


def _nombre(v) -> float:
    """Nombre, virgule décimale comprise, ou 0. Un « 1 234,5 » passe aussi."""
    s = str(v or "").strip().replace(" ", "").replace(" ", "")
    if not s:
        return 0.0
    s = s.replace(",", ".")
    # Un seul point décimal : « 1.234.5 » n'est pas un nombre.
    if s.count(".") > 1:
        s = s.replace(".", "", s.count(".") - 1)
    try:
        return float(s)
    except ValueError:
        return 0.0


def lire_date(texte):
    """Date d'une ligne d'export, quel que soit le format local. None si illisible."""
    s = str(texte or "").strip()
    if not s:
        return None
    # ISO, la forme la plus sûre.
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    # « 14/09/2026 » ou « 09/14/2026 » : on lève l'ambiguïté quand on peut.
    m = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b", s)
    if m:
        a, b, annee = int(m.group(1)), int(m.group(2)), int(m.group(3))
        jour, mois = (a, b) if a > 12 else ((b, a) if b > 12 else (a, b))
        try:
            return _dt.date(annee, mois, jour)
        except ValueError:
            return None
    # « Sep 14, 2026 » ou « 14 sept. 2026 » : on cherche un mois écrit.
    mots = re.findall(r"[A-Za-zÀ-ſ]+", s)
    mois = next((_MOIS[_cle(mot)[:3]] for mot in mots if _cle(mot)[:3] in _MOIS), None)
    if mois:
        nombres = [int(n) for n in re.findall(r"\b\d{1,4}\b", s)]
        annee = next((n for n in nombres if 1900 <= n <= 2999), None)
        jour = next((n for n in nombres if 1 <= n <= 31 and n != annee), None)
        if annee and jour:
            try:
                return _dt.date(annee, mois, jour)
            except ValueError:
                return None
    return None


def _entetes(champs):
    """Associe chaque champ dont on a besoin au nom de colonne trouvé."""
    vus = {_cle(c): c for c in (champs or [])}
    trouves = {}
    for besoin, alias in _COLONNES.items():
        for a in alias:
            if a in vus:
                trouves[besoin] = vus[a]
                break
    return trouves


def _unite_distance(brutes) -> str:
    """« m » ou « km » : on tranche par la vitesse que chaque hypothèse implique.

    5 000 pour une heure de course, c'est des mètres. 5, des kilomètres.
    Parier sur l'une des deux et se tromper diviserait — ou multiplierait —
    tout un historique par mille sans que rien ne le signale.
    """
    pour_m = pour_km = 0
    for distance, secondes in brutes:
        if distance <= 0 or secondes <= 0:
            continue
        if _V_MIN <= distance / secondes <= _V_MAX:
            pour_m += 1
        if _V_MIN <= (distance * 1000) / secondes <= _V_MAX:
            pour_km += 1
    if pour_m == pour_km == 0:
        return "m"          # rien de concluant : l'unité annoncée par Strava
    return "m" if pour_m >= pour_km else "km"


def lire_activites(contenu):
    """Lit un `activities.csv` et rend `(seances, rapport)`.

    `seances` : dicts prêts pour l'historique, les plus récentes d'abord.
    `rapport` : ce qui a été écarté et pourquoi — un import muet sur ce qu'il
    laisse de côté oblige à comparer à la main pour savoir si tout est là.
    """
    if isinstance(contenu, bytes):
        contenu = contenu.decode("utf-8-sig", errors="replace")
    contenu = (contenu or "").lstrip("﻿")

    rapport = {"lignes": 0, "sans_date": 0, "sans_duree": 0,
               "hors_cardio": {}, "colonnes": {}, "unite_distance": ""}
    if not contenu.strip():
        return [], rapport

    # Le séparateur varie avec la locale (virgule ou point-virgule).
    tete = contenu.splitlines()[0] if contenu.splitlines() else ""
    sep = ";" if tete.count(";") > tete.count(",") else ","
    lecteur = csv.DictReader(io.StringIO(contenu), delimiter=sep)
    cols = _entetes(lecteur.fieldnames)
    rapport["colonnes"] = dict(cols)
    if "date" not in cols or "duree" not in cols:
        return [], rapport

    lignes = list(lecteur)
    rapport["lignes"] = len(lignes)

    brutes = [(_nombre(l.get(cols.get("distance"))), _nombre(l.get(cols["duree"])))
              for l in lignes]
    unite = _unite_distance(brutes)
    rapport["unite_distance"] = unite

    seances = []
    for ligne in lignes:
        date = lire_date(ligne.get(cols["date"]))
        if date is None:
            rapport["sans_date"] += 1
            continue
        secondes = _nombre(ligne.get(cols["duree"]))
        if secondes <= 0:
            rapport["sans_duree"] += 1
            continue

        brut_type = ligne.get(cols.get("type")) or ""
        cle_type = _cle(brut_type)
        if cle_type in _HORS_CARDIO:
            nom = _HORS_CARDIO[cle_type]
            rapport["hors_cardio"][nom] = rapport["hors_cardio"].get(nom, 0) + 1
            continue

        distance = _nombre(ligne.get(cols.get("distance")))
        km = round(distance / 1000.0, 2) if unite == "m" else round(distance, 2)
        seances.append({
            "date": date.strftime("%Y-%m-%d"),
            "activite": _TYPES.get(cle_type, "Autre"),
            "type_strava": str(brut_type).strip(),
            "duree_min": max(1, int(round(secondes / 60.0))),
            "distance_km": km,
            "calories": int(_nombre(ligne.get(cols.get("calories")))),
            "nom": str(ligne.get(cols.get("nom")) or "").strip()[:60],
        })

    seances.sort(key=lambda s: s["date"], reverse=True)
    return seances, rapport


def marquer_doublons(seances, historique):
    """Marque `deja` les séances qu'on retrouve dans l'historique.

    Une séance compte pour un doublon si elle tombe le MÊME JOUR, sur la même
    activité, avec une durée à moins de deux minutes près. La durée entre dans
    la comparaison parce que deux footings le même jour sont deux séances —
    l'app les distingue déjà, l'import ne doit pas les confondre.
    """
    connues = []
    for r in historique or []:
        exo = str(r.get("Exercice") or "")
        if not exo.startswith("CARDIO:"):
            continue
        connues.append((str(r.get("Date") or "")[:10],
                        exo.split(":", 1)[1] or "Autre",
                        int(_nombre(r.get("Reps")))))
    for s in seances:
        s["deja"] = any(
            d == s["date"] and a == s["activite"] and abs(m - s["duree_min"]) <= 2
            for d, a, m in connues)
    return seances
