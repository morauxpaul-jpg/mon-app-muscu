"""Logique métier muscu — extraite verbatim de app.py pour garantir le même comportement."""


def calc_1rm(weight, reps):
    """Estimation Epley du 1RM."""
    return weight * (1 + reps / 30) if reps > 0 else 0


def get_rep_estimations(one_rm):
    return {r: round(one_rm * pct, 1) for r, pct in
            {1: 1.0, 3: 0.94, 5: 0.89, 8: 0.81, 10: 0.75, 12: 0.71}.items()}


def get_rep_table(one_rm):
    """Table complète d'estimation du poids par nombre de reps via l'inverse
    de la formule d'Epley : poids = 1RM / (1 + reps/30).
    Retourne une liste de dicts {reps, weight, pct} ordonnée par reps croissant."""
    if not one_rm or one_rm <= 0:
        return []
    reps_list = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20]
    out = []
    for r in reps_list:
        w = one_rm / (1 + r / 30)
        out.append({
            "reps": r,
            "weight": round(w, 1),
            "pct": round(w / one_rm * 100),
        })
    return out


def get_base_name(full_name):
    """'Développé couché (Barre)' -> 'Développé couché'."""
    return full_name.split("(")[0].strip() if "(" in full_name else full_name


def auto_muscles(name):
    """Déduit les muscles à partir du nom d'exercice. Identique à app.py."""
    n = name.lower()
    muscles = set()
    rules = [
        (["écarté", "fly", "pec deck", "butterfly", "cable crossover", "poulie croisée", "crossover"], ["Pecs"]),
        (["dips"], ["Pecs"]),
        (["pompe", "push-up", "pushup", "push up"], ["Pecs"]),
        (["développé couché", "bench press", "dc haltères", "dc barre"], ["Pecs"]),
        (["développé incliné", "di haltères", "di barre"], ["Pecs"]),
        (["développé décliné", "dd "], ["Pecs"]),
        (["développé"], ["Pecs"]),
        (["traction", "pull-up", "pullup", "chin-up", "chinup", "chin up"], ["Dos"]),
        (["tirage", "lat machine", "lat pull", "lat pulldown"], ["Dos"]),
        (["rowing", "row", "t-bar", "barre t"], ["Dos"]),
        (["pull-over", "pullover"], ["Dos", "Pecs"]),
        (["hyperextension", "back extension", "good morning"], ["Dos", "Ischio-jambiers"]),
        (["soulevé de terre", "deadlift", "sdt", "sumo"], ["Dos", "Ischio-jambiers", "Fessiers"]),
        (["développé militaire", "overhead press", "ohp", "military press", "press assis", "press debout", "shoulder press"], ["Épaules"]),
        (["arnold"], ["Épaules"]),
        (["élévation latérale", "lateral raise", "élévation lat"], ["Épaules"]),
        (["élévation frontale", "front raise", "élévation front"], ["Épaules"]),
        (["oiseau", "reverse fly", "rear delt"], ["Épaules"]),
        (["face pull"], ["Épaules", "Trapèzes"]),
        (["shrug", "haussement"], ["Trapèzes"]),
        (["upright row", "tirage menton"], ["Épaules", "Trapèzes"]),
        (["curl marteau", "hammer curl", "marteau"], ["Biceps"]),
        (["reverse curl", "curl inversé"], ["Biceps"]),
        (["curl barre", "curl haltère", "curl poulie", "curl concentré", "curl incliné", "curl scott", "preacher curl", "zottman"], ["Biceps"]),
        (["curl"], ["Biceps"]),
        (["biceps"], ["Biceps"]),
        (["skull crusher", "barre front", "jm press", "lying extension", "extension nuque"], ["Triceps"]),
        (["pushdown", "tirage poulie triceps", "corde triceps", "triceps poulie", "poulie triceps"], ["Triceps"]),
        (["kick-back triceps", "kickback triceps"], ["Triceps"]),
        (["extension triceps", "triceps barre", "extension haltère"], ["Triceps"]),
        (["triceps"], ["Triceps"]),
        (["poignet", "wrist curl", "avant-bras", "forearm"], ["Avant-bras"]),
        (["crunch", "sit-up", "situp"], ["Abdos"]),
        (["gainage", "planche", "plank"], ["Abdos"]),
        (["relevé de jambe", "leg raise", "hanging leg", "knee raise"], ["Abdos"]),
        (["rotation", "twist", "russian", "oblique"], ["Abdos"]),
        (["abdos", "abdominal", "ab "], ["Abdos"]),
        (["roue abdos", "wheel"], ["Abdos"]),
        (["leg extension", "extension cuisse", "extension jambe"], ["Quadriceps"]),
        (["hack squat"], ["Quadriceps"]),
        (["split squat", "bulgare", "bulgarian"], ["Quadriceps", "Fessiers", "Ischio-jambiers"]),
        (["fente", "lunge", "walking lunge"], ["Quadriceps", "Fessiers", "Ischio-jambiers"]),
        (["leg press", "presse à cuisse", "presse cuisse", "presse jambe"], ["Quadriceps", "Fessiers"]),
        (["goblet"], ["Quadriceps", "Fessiers"]),
        (["squat", "back squat", "front squat", "box squat"], ["Quadriceps", "Fessiers"]),
        (["presse"], ["Quadriceps", "Fessiers"]),
        (["leg curl", "curl jambe", "ischio", "lying leg curl", "seated leg curl", "nordic"], ["Ischio-jambiers"]),
        (["rdl", "romanian", "roumain", "soulevé jambe tendue", "stiff leg"], ["Ischio-jambiers", "Fessiers"]),
        (["hip thrust", "hip-thrust", "hip extension"], ["Fessiers"]),
        (["abduction", "écartement cuisse"], ["Fessiers"]),
        (["kickback", "kick-back", "donkey kick"], ["Fessiers", "Ischio-jambiers"]),
        (["glute bridge", "fessier", "glute"], ["Fessiers"]),
        (["mollet", "calf raise", "calves", "talon", "standing calf", "seated calf"], ["Mollets"]),
        (["adducteur", "adduction poulie", "copenhagen"], ["Adducteurs"]),
        (["squat sumo"], ["Adducteurs"]),
        (["fente latérale"], ["Adducteurs"]),
        (["abducteur", "abduction poulie", "clam shell", "marche latérale élastique"], ["Abducteurs"]),
        (["machine abducteur"], ["Abducteurs"]),
        (["machine adducteur"], ["Adducteurs"]),
    ]
    for keywords, ms in rules:
        if any(kw in n for kw in keywords):
            muscles.update(ms)
    return ",".join(sorted(muscles)) if muscles else None


def fix_muscle(exercice, muscle):
    """Corrige les valeurs muscle legacy via auto_muscles."""
    if muscle is None or str(muscle) in ("Bras", "Jambes", "Autre", "nan", "", "None"):
        result = auto_muscles(get_base_name(str(exercice)))
        if result:
            return result
        return "Autre"
    return str(muscle)


# ── Suggestion de surcharge progressive ─────────────────────────────────
import re as _re

_RPE_TOKEN = _re.compile(r"@RPE(\d+(?:\.5)?)", _re.I)


def parse_rpe(remarque):
    """RPE (float) encodé dans une remarque sous la forme '@RPE8' / '@RPE8.5',
    ou None."""
    m = _RPE_TOKEN.search(remarque or "")
    return float(m.group(1)) if m else None


def _load_step(weight):
    """Incrément de charge réaliste : 2,5 kg à partir de 30 kg (barre, disques
    de 1,25), 1 kg en dessous (haltères légers, machines, isolation)."""
    return 2.5 if weight >= 30 else 1.0


def overload_suggestion(last_sets, prev_sets=None, is_bw=False):
    """Double progression simplifiée à partir des 1–2 dernières séances.

    last_sets / prev_sets : listes de dicts {reps, poids, rpe?} (série la plus
    ancienne en premier). Retourne None sans historique, sinon un dict :
      kind  : "load" (monter la charge) | "reps" (même charge, +1 rep)
              | "hold" (consolider : même charge, mêmes reps)
      poids : charge cible (None en poids de corps)
      reps  : reps cibles par série
      label : phrase courte pour l'UI
      why   : justification en un mot-clé

    Règles :
      - RPE moyen ≥ 9,5 la dernière fois → hold (la charge n'est pas digérée).
      - Toutes les séries à la même charge ET (≥ 12 reps partout, OU ≥ 8 reps
        avec RPE moyen ≤ 8, OU ≥ 8 reps deux séances de suite à cette charge
        sans régression) → load (+2,5 kg / +1 kg).
      - Sinon → reps : même charge, viser min(reps) + 1.
    """
    sets = [s for s in (last_sets or []) if int(s.get("reps") or 0) > 0]
    if not sets:
        return None
    reps = [int(s["reps"]) for s in sets]
    min_reps = min(reps)
    rpes = [float(s["rpe"]) for s in sets if s.get("rpe")]
    avg_rpe = sum(rpes) / len(rpes) if rpes else None

    if is_bw:
        return {
            "kind": "reps", "poids": None, "reps": min_reps + 1,
            "label": f"Objectif : {min_reps + 1} reps par série",
            "why": "bodyweight",
        }

    weights = {float(s.get("poids") or 0) for s in sets}
    weight = max(weights)
    if weight <= 0:
        return None
    same_weight = len(weights) == 1

    if avg_rpe is not None and avg_rpe >= 9.5 and min_reps < 12:
        return {
            "kind": "hold", "poids": weight, "reps": min_reps,
            "label": f"Consolide : {weight:g} kg × {min_reps} (RPE {avg_rpe:g} la dernière fois)",
            "why": "rpe_high",
        }

    ready = False
    why = ""
    if same_weight:
        if min_reps >= 12:
            ready, why = True, "reps_ceiling"
        elif min_reps >= 8 and avg_rpe is not None and avg_rpe <= 8:
            ready, why = True, "rpe_low"
        elif min_reps >= 8 and prev_sets:
            p = [s for s in prev_sets if int(s.get("reps") or 0) > 0]
            p_weights = {float(s.get("poids") or 0) for s in p}
            if p and p_weights == {weight}:
                p_min = min(int(s["reps"]) for s in p)
                if p_min >= 8 and min_reps >= p_min:
                    ready, why = True, "two_sessions"

    if ready:
        step = _load_step(weight)
        target = weight + step
        return {
            "kind": "load", "poids": target, "reps": max(6, min_reps - 2),
            "label": f"Monte à {target:g} kg (+{step:g})",
            "why": why,
        }
    return {
        "kind": "reps", "poids": weight, "reps": min_reps + 1,
        "label": f"Même charge, vise {min_reps + 1} reps",
        "why": "add_rep",
    }
