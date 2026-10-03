"""Lire l'export CSV de Hevy ou de Strong : l'historique de musculation.

Changer d'app sans emporter deux ans de charges, c'est repartir de zéro :
pas de « dernière fois », pas de suggestion, pas de record. C'est la raison
n° 1 de rester sur l'app qu'on a (audit du 03/10). Les deux exportent leurs
séances en CSV, une ligne par série :

* **Hevy** (Profil → Paramètres → Exporter les données) :
  ``title, start_time, end_time, description, exercise_title, superset_id,
  exercise_notes, set_index, set_type, weight_kg | weight_lbs, reps,
  distance_km, duration_seconds, rpe``.
  ``start_time`` vaut « 28 Sep 2024, 18:05 » (ou une date ISO selon la
  version) ; ``set_type`` vaut normal, warmup, failure ou dropset.
* **Strong** (Paramètres → Exporter les données) :
  ``Date, Workout Name, Duration, Exercise Name, Set Order, Weight, Reps,
  Distance, Seconds, Notes, Workout Notes, RPE`` — séparateur virgule ou
  point-virgule selon la version, ``Set Order`` à « W » pour un
  échauffement, une colonne ``Weight Unit`` sur les anciens exports.

Comme pour Strava (core/strava_import.py), les en-têtes sont comparés
normalisés contre des alias, jamais par position, et tout ce qui est
écarté est compté pour être dit.

Ce module LIT seulement. Rien n'est écrit en base ici.
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import re
import unicodedata

from core.dates import continuous_week
from core.exercises_data import required_equipment, resoudre
from core.muscu import fix_muscle

LBS_EN_KG = 0.45359237

# Matériel noté entre parenthèses par Hevy et Strong → variante de l'app.
# La barre est la variante par défaut des mouvements de base : rien à noter.
_MATERIEL = {
    "barbell": None, "dumbbell": "Haltères", "cable": "Poulie",
    "machine": "Machine", "smith machine": "Machine", "weighted": "Lesté",
    "plate loaded": "Machine", "ez bar": None, "band": None,
    "bodyweight": None, "assisted": None, "kettlebell": None,
}

# Variante → identifiant de matériel du catalogue (core/exercises_data.py).
_EQUIPEMENT_DE = {"Poulie": "machine", "Machine": "machine", "Haltères": "halteres"}

_COLONNES = {
    "date": ["starttime", "date", "workoutdate"],
    "seance": ["title", "workoutname", "workouttitle"],
    "exercice": ["exercisetitle", "exercisename", "exercise"],
    "type": ["settype"],
    "ordre": ["setorder", "setindex"],
    "poids_kg": ["weightkg"],
    "poids_lbs": ["weightlbs"],
    "poids": ["weight"],
    "unite": ["weightunit", "unit"],
    "reps": ["reps", "repetitions"],
    "rpe": ["rpe"],
    "distance": ["distancekm", "distance", "distancemeters"],
    "secondes": ["durationseconds", "seconds"],
}

_MOIS = {"jan": 1, "feb": 2, "fev": 2, "mar": 3, "apr": 4, "avr": 4, "may": 5,
         "mai": 5, "jun": 6, "juin": 6, "jul": 7, "juil": 7, "aug": 8, "aou": 8,
         "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", s or "")
                if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _nombre(v) -> float:
    s = str(v or "").strip().replace(" ", "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _mois(mot: str):
    m = _norm(mot)
    return _MOIS.get(m[:4]) or _MOIS.get(m[:3])


def lire_date(v):
    """Date d'une séance, ou None. Formes rencontrées : « 2024-09-28
    18:05:00 », « 28 Sep 2024, 18:05 », « Sep 28, 2024 6:05 PM »,
    « 28/09/2024 18:05 »."""
    s = str(v or "").strip()
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
        if m:
            d, mo, y = map(int, m.groups())
        else:
            mots = re.findall(r"[^\W\d_]+|\d+", s)
            mois = next((m for m in (_mois(w) for w in mots if not w.isdigit()) if m), None)
            nums = [int(w) for w in mots if w.isdigit()]
            annee = next((n for n in nums if n > 1900), None)
            jour = next((n for n in nums if 1 <= n <= 31), None)
            if not (mois and annee and jour):
                return None
            y, mo, d = annee, mois, jour
    try:
        return _dt.date(y, mo, d)
    except ValueError:
        return None


def nom_exercice(nom_source: str) -> str:
    """« Bench Press (Dumbbell) » → « Développé couché (Haltères) ».

    Un exercice inconnu du catalogue garde son nom d'origine : mieux vaut un
    nom anglais qu'un rapprochement faux, qui mélangerait deux historiques.
    """
    nom = (nom_source or "").strip()[:80]
    base, materiel = nom, None
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", nom)
    if m:
        cle_materiel = m.group(2).strip().lower()
        if cle_materiel in _MATERIEL:
            base, materiel = m.group(1).strip(), _MATERIEL[cle_materiel]
    cle, _niveau = resoudre(base)
    if not cle:
        return nom
    # Le matériel que l'exercice suppose déjà n'est pas une variante :
    # « Lat Pulldown (Cable) » est le tirage vertical tout court. En faire
    # « Tirage vertical (Poulie) » couperait l'historique en deux.
    if materiel and _EQUIPEMENT_DE.get(materiel) in (required_equipment(cle) or []):
        materiel = None
    return f"{cle} ({materiel})" if materiel else cle


def _colonnes(entetes):
    vues = {_norm(h): h for h in entetes if h}
    out = {}
    for champ, alias in _COLONNES.items():
        for a in alias:
            if a in vues:
                out[champ] = vues[a]
                break
    # « weight » seul chez Strong, mais aussi en tête de « weightkg » :
    # l'alias exact a déjà tranché ci-dessus.
    return out


def _source(col) -> str:
    if "type" in col or "poids_kg" in col or "poids_lbs" in col:
        return "Hevy"
    return "Strong"


def lire_export(brut: bytes):
    """(séances, rapport).

    séances : [{date, seance, exercices: [{nom, muscle, series: [{reps,
    poids, rpe}]}]}], une par (jour, nom de séance), dans l'ordre du fichier.
    rapport : lignes lues, source, colonnes trouvées, et ce qui a été écarté.
    """
    texte = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texte = brut.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    premiere = texte.splitlines()[0] if texte else ""
    sep = max((",", ";", "\t"), key=premiere.count)
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=sep)
    col = _colonnes(lecteur.fieldnames or [])
    rapport = {"lignes": 0, "source": _source(col), "colonnes": col,
               "echauffements": 0, "sans_reps": 0, "sans_date": 0,
               "exercices": {}}
    if not (col.get("date") and col.get("exercice") and col.get("reps")):
        return [], rapport

    seances: dict = {}
    for ligne in lecteur:
        rapport["lignes"] += 1
        date = lire_date(ligne.get(col["date"]))
        if date is None:
            rapport["sans_date"] += 1
            continue
        type_serie = str(ligne.get(col.get("type", ""), "") or "").strip().lower()
        ordre = str(ligne.get(col.get("ordre", ""), "") or "").strip().upper()
        if type_serie.startswith("warm") or ordre == "W":
            rapport["echauffements"] += 1
            continue
        reps = int(_nombre(ligne.get(col["reps"])))
        if reps <= 0:
            # Cardio, chrono, série notée vide : rien qu'une ligne de
            # musculation puisse porter honnêtement.
            rapport["sans_reps"] += 1
            continue
        if col.get("poids_kg"):
            poids = _nombre(ligne.get(col["poids_kg"]))
        elif col.get("poids_lbs"):
            poids = _nombre(ligne.get(col["poids_lbs"])) * LBS_EN_KG
        else:
            poids = _nombre(ligne.get(col.get("poids", ""), ""))
            unite = _norm(str(ligne.get(col.get("unite", ""), "") or ""))
            if unite.startswith("lb"):
                poids *= LBS_EN_KG
        poids = round(max(0.0, min(poids, 1000.0)) * 4) / 4   # au quart de kg
        rpe = _nombre(ligne.get(col.get("rpe", ""), ""))
        source = str(ligne.get(col["exercice"]) or "").strip()
        if not source:
            rapport["sans_reps"] += 1
            continue
        nom = rapport["exercices"].setdefault(source, nom_exercice(source))
        titre = str(ligne.get(col.get("seance", ""), "") or "").strip()[:60] or "Séance importée"
        cle = (date.isoformat(), titre)
        s = seances.setdefault(cle, {"date": cle[0], "seance": titre, "exercices": {}})
        e = s["exercices"].setdefault(nom, {"nom": nom, "muscle": fix_muscle(nom, None),
                                            "series": []})
        e["series"].append({"reps": min(reps, 999), "poids": poids,
                            "rpe": rpe if 1 <= rpe <= 10 else None})

    out = []
    for s in seances.values():
        s["exercices"] = list(s["exercices"].values())
        out.append(s)
    return out, rapport


def marquer_doublons(seances, historique):
    """`deja` = une séance du même nom existe déjà ce jour-là. Réimporter le
    même fichier ne double donc rien."""
    connues = {(str(r.get("Date") or "")[:10], str(r.get("Séance") or "").casefold())
               for r in historique or [] if r.get("Date")}
    for s in seances:
        s["deja"] = (s["date"], s["seance"].casefold()) in connues
    return seances


def compacter(seances) -> list:
    """Forme courte pour l'aller-retour par le formulaire de confirmation."""
    return [[s["date"], s["seance"],
             [[e["nom"], e["muscle"], [[x["reps"], x["poids"], x["rpe"]] for x in e["series"]]]
              for e in s["exercices"]]]
            for s in seances]


def lignes_historique(charge, source: str) -> list[dict]:
    """Lignes d'historique à partir de la charge renvoyée par le formulaire.

    Tout est REVALIDÉ : la charge a fait l'aller-retour par le navigateur,
    une ligne trafiquée n'a pas à devenir une ligne d'historique."""
    out = []
    remarque = f"Import {source if source in ('Hevy', 'Strong') else 'CSV'}"
    for s in charge if isinstance(charge, list) else []:
        if not (isinstance(s, list) and len(s) == 3 and isinstance(s[2], list)):
            continue
        date = lire_date(s[0])
        titre = str(s[1] or "").strip()[:60]
        if date is None or not titre or titre.startswith("_"):
            continue
        for e in s[2][:60]:
            if not (isinstance(e, list) and len(e) == 3 and isinstance(e[2], list)):
                continue
            nom = str(e[0] or "").strip()[:80]
            if not nom or nom.startswith("CARDIO:") or nom == "SESSION":
                continue
            muscle = str(e[1] or "").strip()[:60] or fix_muscle(nom, None)
            for i, x in enumerate(e[2][:50], start=1):
                try:
                    reps = max(0, min(999, int(x[0])))
                    poids = max(0.0, min(1000.0, float(x[1] or 0)))
                    rpe = float(x[2]) if x[2] not in (None, "") else None
                except (TypeError, ValueError, IndexError):
                    continue
                if reps <= 0:
                    continue
                out.append({
                    "Semaine": continuous_week(date), "Séance": titre,
                    "Exercice": nom, "Série": i, "Reps": reps, "Poids": poids,
                    "Remarque": remarque, "Muscle": muscle,
                    "Date": date.isoformat(),
                    "RPE": rpe if rpe is not None and 1 <= rpe <= 10 else None,
                })
    return out
