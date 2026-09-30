"""Le cardio d'une séance : le format stocké, et les mesures qui se déduisent.

Une ligne cardio est stockée avec l'exercice « CARDIO:Course », la durée dans
`Reps`, la distance dans `Poids`, et le reste empilé dans la remarque
(« Cal:360 | Vit:10.5 | RPE:Modéré »). Le rapport d'audit nomme ce format
comme de la dette de modèle de données ; la lecture est au moins à un seul
endroit.

Ce module porte aussi **l'unité de chaque activité** et la règle qui relie
durée, distance et vitesse. C'était jusqu'ici une table en JavaScript, donc
invisible du serveur : la vitesse calculée dans le formulaire s'affichait en
suggestion et **n'était jamais enregistrée**.

Les noms gardent leur préfixe `_` là où ils viennent tels quels de
`routes/seance.py` : le déplacement s'était fait sans en renommer un seul.
"""

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
            "duree": int(r.get("Reps") or 0),
            "distance": float(r.get("Poids") or 0),
            "semaine": int(r.get("Semaine") or 0),
            "serie": int(r.get("Série") or 1),
            **parsed,
        })
    return out
