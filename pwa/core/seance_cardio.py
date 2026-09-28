"""Le cardio d'une séance, encodé dans une remarque.

Une ligne cardio est stockée avec l'exercice « CARDIO:Course » et ses
détails empilés dans la remarque (« Cal:360 | Vit:10.5 | RPE:Modéré »).
Ce module sait écrire et relire ce format. Le rapport d'audit le nomme
comme de la dette de modèle de données ; la lecture est au moins à un
seul endroit.

Les noms gardent leur préfixe `_` : ils viennent tels quels de
`routes/seance.py`, et le déplacement a été fait sans en renommer un seul
pour que chaque corps de fonction reste comparable au caractère près.
"""
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
            **parsed,
        })
    return out
