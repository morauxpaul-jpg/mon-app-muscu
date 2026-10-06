"""Le cardio d'une séance : le format stocké, et les mesures qui se déduisent.

En base (migration v44), une ligne cardio porte l'exercice « CARDIO:Course »
et ses mesures dans leurs colonnes : `duree_min`, `distance`, `calories`,
`vitesse` ; `reps` et `poids` y valent 0. Avant, la durée était dans `reps`,
la distance dans `poids`, calories et vitesse en texte dans la remarque
(« Cal:360 | Vit:10.5 | RPE:Modéré ») — et tout ce qui lisait la base sans
passer par l'app se trompait : le tonnage admin multipliait des minutes par
des kilomètres (audit du 03/10, M15).

Dans l'app, la ligne garde sa forme d'origine (Reps = minutes, Poids =
distance, Cal/Vit dans la remarque) : des dizaines d'écrans la lisent ainsi.
Le passage d'une forme à l'autre se fait ici, à un seul endroit, appelé par
`core/db_historique.py` à l'écriture (`vers_colonnes`) et à la lecture
(`depuis_colonnes`). Les clés Duree/Distance/Calories/Vitesse exposent en
plus les mesures sous leur nom.

Ce module porte aussi **l'unité de chaque activité** et la règle qui relie
durée, distance et vitesse. C'était jusqu'ici une table en JavaScript, donc
invisible du serveur : la vitesse calculée dans le formulaire s'affichait en
suggestion et **n'était jamais enregistrée**.

Les noms gardent leur préfixe `_` là où ils viennent tels quels de
`routes/seance.py` : le déplacement s'était fait sans en renommer un seul.
"""

from core.cardio_duree import reps_de

# Unité de distance et de vitesse, par activité. C'est la SEULE table : le
# formulaire de séance la reçoit en JSON (`seance-config`) au lieu d'en garder
# une copie, et un test vérifie qu'aucune copie ne réapparaît.
#
# `vitesse` nomme la règle de conversion, pas seulement l'étiquette :
#   par_heure   distance par heure          (km/h)
#   m_par_min   distance × 1000 par minute  (m/min, natation)
#   par_min     distance par minute         (sauts/min, marches/min)
#   ""          aucune vitesse n'a de sens ici (HIIT), ou la règle n'est pas
#               une simple division (l'allure du rameur, en min/500 m)
UNITES_CARDIO = {
    "Course":             {"dist": "Distance (km)",       "vit": "Vitesse (km/h)",    "regle": "par_heure", "pas": "0.01"},
    "Vélo":               {"dist": "Distance (km)",       "vit": "Vitesse (km/h)",    "regle": "par_heure", "pas": "0.01"},
    "Rameur":             {"dist": "Distance (km)",       "vit": "Allure (min/500m)", "regle": "",          "pas": "0.01"},
    "Natation":           {"dist": "Distance (km)",       "vit": "Vitesse (m/min)",   "regle": "m_par_min", "pas": "0.01"},
    "Corde":              {"dist": "Nombre de sauts",     "vit": "Sauts/min",         "regle": "par_min",   "pas": "1"},
    "HIIT":               {"dist": "Rounds",              "vit": "",                  "regle": "",          "pas": "1"},
    "Marche":             {"dist": "Distance (km)",       "vit": "Vitesse (km/h)",    "regle": "par_heure", "pas": "0.01"},
    "Elliptique":         {"dist": "Distance (km)",       "vit": "Vitesse (km/h)",    "regle": "par_heure", "pas": "0.01"},
    "Montée d'escaliers": {"dist": "Étages (ou marches)", "vit": "Marches/min",       "regle": "par_min",   "pas": "1"},
    "Autre":              {"dist": "Distance (km)",       "vit": "Vitesse (km/h)",    "regle": "par_heure", "pas": "0.01"},
}


def unites(activite):
    """L'unité d'une activité, « Autre » pour une activité inconnue."""
    return UNITES_CARDIO.get(activite) or UNITES_CARDIO["Autre"]


def _nombre(v):
    """Valeur numérique positive, ou 0. Accepte la virgule décimale."""
    try:
        n = float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return 0.0
    return n if n > 0 else 0.0


def completer_mesures(activite, duree_min, distance, vitesse):
    """Deux valeurs sur trois suffisent : la troisième se déduit.

    Le formulaire calculait déjà la vitesse à partir de la durée et de la
    distance — mais seulement dans ce sens, et seulement pour l'afficher en
    suggestion. On connaît souvent l'inverse : le tapis affiche 10 km/h
    pendant 30 minutes, et c'est la distance qu'on ignore.

    Retourne `(distance, vitesse)` complétées. Ne touche à rien de ce qui est
    déjà renseigné : une valeur saisie prime toujours sur une valeur déduite.
    La durée n'est jamais déduite — c'est elle qui identifie la séance.
    """
    t = _nombre(duree_min)
    d = _nombre(distance)
    v = _nombre(vitesse)
    regle = unites(activite)["regle"]
    if not regle or t <= 0 or (d > 0 and v > 0) or (d <= 0 and v <= 0):
        return d, v

    # Combien d'unités de distance pour une unité de vitesse.
    facteur = {"par_heure": t / 60.0, "m_par_min": t / 1000.0, "par_min": t}[regle]
    if facteur <= 0:
        return d, v
    if d > 0:
        v = d / facteur
    else:
        d = v * facteur
    return round(d, 2), round(v, 2)


def _parse_cardio_remarque(remarque):
    """Extrait Cal/Vit/RPE/note d'une remarque CARDIO du type
    'Cal:360 | Vit:10.5 | RPE:Modéré | commentaire libre'."""
    out = {"calories": 0, "vitesse": "", "rpe": "", "note": ""}
    if not remarque:
        return out
    parts = [p.strip() for p in remarque.split("|") if p.strip()]
    for p in parts:
        low = p.lower()
        if low.startswith("cal:"):
            try:
                out["calories"] = int(float(p[4:].strip()))
            except ValueError:
                pass
        elif low.startswith("vit:"):
            out["vitesse"] = p[4:].strip()
        elif low.startswith("fc:"):
            out["fc"] = p[3:].strip()
        elif low.startswith("rpe:"):
            out["rpe"] = p[4:].strip()
        else:
            out["note"] = p
    return out


def _duree_ligne(r):
    """Minutes d'une ligne de l'app : `Duree` (décimale, avec les secondes)
    si elle est là, sinon les minutes entières de `Reps`."""
    duree = r.get("Duree")
    duree = float(duree) if duree is not None else float(r.get("Reps") or 0)
    return int(duree) if duree == int(duree) else duree


def _build_cardio_done(hist, seance_name, date_iso):
    """Retourne la liste des blocs cardio déjà enregistrés pour cette séance/date."""
    out = []
    for r in hist:
        if r.get("Date") != date_iso or r.get("Séance") != seance_name:
            continue
        exo = r.get("Exercice") or ""
        if not exo.startswith("CARDIO:"):
            continue
        activite = exo.split(":", 1)[1] or "Autre"
        parsed = _parse_cardio_remarque(r.get("Remarque") or "")
        out.append({
            "activite": activite,
            "duree": _duree_ligne(r),
            "distance": float(r.get("Poids") or 0),
            "semaine": int(r.get("Semaine") or 0),
            "serie": int(r.get("Série") or 1),
            **parsed,
        })
    return out


# ── Le format en base (v44) ──────────────────────────────────────────────

COLONNES_CARDIO = ("duree_min", "distance", "calories", "vitesse")


def _jetons(remarque):
    return [p.strip() for p in str(remarque or "").split("|") if p.strip()]


def _mesure(txt):
    """Nombre positif ou nul lu dans un jeton, sinon None (« 2:05 »)."""
    try:
        n = float(str(txt).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def vers_colonnes(reps, poids, remarque, duree=None) -> dict:
    """Ligne cardio telle que l'app l'écrit → valeurs des colonnes en base.

    `duree` : la durée exacte en minutes (clé `Duree` de la ligne), quand
    elle porte des secondes ; sinon les minutes entières de `Reps`.

    Calories et vitesse quittent la remarque seulement si ce sont des
    nombres : une allure saisie « 2:05 » reste en texte, plutôt que perdue.
    """
    calories = vitesse = None
    reste = []
    for p in _jetons(remarque):
        bas = p.lower()
        n = _mesure(p[4:]) if bas[:4] in ("cal:", "vit:") else None
        if bas.startswith("cal:") and calories is None and n is not None:
            calories = int(round(n))
        elif bas.startswith("vit:") and vitesse is None and n is not None:
            vitesse = n
        else:
            reste.append(p)
    return {"reps": 0, "poids": 0.0, "remarque": " | ".join(reste),
            "duree_min": round(float(duree), 4) if duree is not None else int(reps or 0),
            "distance": float(poids or 0),
            "calories": calories, "vitesse": vitesse}


def _remarque_complete(remarque, calories, vitesse) -> str:
    """La remarque telle que l'app la connaît : Cal et Vit en tête."""
    jetons = _jetons(remarque)
    deja = {j.lower()[:4] for j in jetons}
    tete = []
    if calories is not None and "cal:" not in deja:
        tete.append(f"Cal:{int(calories)}")
    if vitesse is not None and "vit:" not in deja:
        tete.append(f"Vit:{float(vitesse):g}")
    return " | ".join(tete + jetons)


def depuis_colonnes(ligne: dict) -> dict:
    """Ligne `history` en base → reps, poids, remarque de l'app, et mesures.

    Une ligne sans les colonnes (écrite avant la v44, ou base en retard) se
    lit dans l'ancien format, à l'identique."""
    rem = ligne.get("remarque") or ""
    lu = _parse_cardio_remarque(rem)
    duree = ligne.get("duree_min")
    distance = ligne.get("distance")
    calories = ligne.get("calories")
    vitesse = ligne.get("vitesse")
    duree = float(duree) if duree is not None else float(ligne.get("reps") or 0)
    distance = float(distance) if distance is not None else float(ligne.get("poids") or 0)
    if calories is None and lu["calories"]:
        calories = lu["calories"]
    if vitesse is None:
        vitesse = _mesure(lu["vitesse"]) if lu["vitesse"] else None
    return {
        "reps": reps_de(duree), "poids": distance,
        "remarque": _remarque_complete(rem, ligne.get("calories"), ligne.get("vitesse")),
        "Duree": duree, "Distance": distance,
        "Calories": int(calories) if calories is not None else None,
        "Vitesse": float(vitesse) if vitesse is not None else None,
    }


def vers_ancien_format(p: dict) -> dict:
    """Ligne prête pour la base, reconvertie au format d'avant la v44 (base
    en retard : les colonnes n'existent pas encore)."""
    if not str(p.get("exercice") or "").startswith("CARDIO:") or p.get("duree_min") is None:
        return p
    return {**p, "reps": reps_de(p.get("duree_min")), "poids": float(p.get("distance") or 0),
            "remarque": _remarque_complete(p.get("remarque"), p.get("calories"), p.get("vitesse"))}
