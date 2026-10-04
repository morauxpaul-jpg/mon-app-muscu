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


# Le matériel avec lequel une série a été faite, stocké entre parenthèses à
# la suite du nom : « Développé couché (Barre) ». Liste fermée — toute autre
# parenthèse fait partie du nom de l'exercice (« Hip thrust (sol) »).
VARIANTS = ["Standard", "Barre", "Haltères", "Banc", "Poulie", "Machine", "Lesté"]

# Les groupes musculaires que l'app sait nommer : étiquettes des sélecteurs,
# clés de la carte du corps, vocabulaire imposé au générateur IA. Cette liste
# vivait recopiée à l'identique dans seance.py, programme.py, gestion.py et
# generator.py — quatre exemplaires qu'il fallait penser à modifier ensemble.
MUSCLE_LIST = ["Pecs", "Dos", "Trapèzes", "Épaules", "Biceps", "Triceps", "Avant-bras", "Abdos",
               "Quadriceps", "Ischio-jambiers", "Fessiers", "Adducteurs", "Abducteurs", "Mollets", "Autre"]

# Les exercices dont la charge EST le corps : leur record se compte en
# répétitions, pas en kilos, et une série à 0 kg y est une vraie performance.
# La variante « Lesté » les fait sortir de cette liste, puisqu'on y ajoute du poids.
BW_EXOS = {"Dips", "Tractions"}


def get_base_name(full_name):
    """'Développé couché (Barre)' -> 'Développé couché'."""
    return full_name.split("(")[0].strip() if "(" in full_name else full_name


def separer_variante(nom):
    """« Développé couché (Barre) » → (« Développé couché », « Barre »).

    Seules les variantes CONNUES sont détachées. « Hip thrust (sol) » garde
    sa parenthèse : c'est le nom de l'exercice, pas le matériel du jour.
    """
    nom = (nom or "").strip()
    if not nom.endswith(")") or "(" not in nom:
        return nom, None
    base, _, fin = nom.rpartition("(")
    candidat = fin[:-1].strip()
    for v in VARIANTS:
        if v != "Standard" and candidat.casefold() == v.casefold():
            return base.strip(), v
    return nom, None


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


def _suggestion_dans_la_fourchette(weight, same_weight, min_reps, avg_rpe, cible):
    """Double progression dans la fourchette (lo, hi) du programme."""
    lo, hi = cible
    if avg_rpe is not None and avg_rpe >= 9.5 and min_reps < hi:
        return {
            "kind": "hold", "poids": weight, "reps": min_reps,
            "label": f"Consolide : {weight:g} kg × {min_reps} (RPE {avg_rpe:g} la dernière fois)",
            "why": "rpe_high",
        }
    # Haut de la fourchette atteint sur toutes les séries, à la même charge
    # (ou sans effort, RPE ≤ 7, dès le bas) : on monte.
    facile = avg_rpe is not None and avg_rpe <= 7 and min_reps >= lo
    if same_weight and (min_reps >= hi or facile):
        step = _load_step(weight)
        target = weight + step
        return {
            "kind": "load", "poids": target, "reps": lo,
            "label": f"Monte à {target:g} kg (+{step:g})",
            "why": "range_top" if min_reps >= hi else "rpe_low",
        }
    vise = min(hi, max(lo, min_reps + 1))
    if vise <= min_reps:
        # Déjà au haut de la fourchette, mais charges inégales : on consolide.
        return {
            "kind": "hold", "poids": weight, "reps": min_reps,
            "label": f"Même charge, {min_reps} reps sur toutes les séries",
            "why": "uneven",
        }
    return {
        "kind": "reps", "poids": weight, "reps": vise,
        "label": f"Même charge, vise {vise} reps",
        "why": "add_rep",
    }


def _load_step(weight):
    """Incrément de charge réaliste : 2,5 kg à partir de 30 kg (barre, disques
    de 1,25), 1 kg en dessous (haltères légers, machines, isolation)."""
    return 2.5 if weight >= 30 else 1.0


def parse_cible_reps(texte):
    """Fourchette de reps d'un programme → (min, max), ou None.

    « 5 » → (5, 5) ; « 8-12 », « 8–12 », « 8 à 12 » → (8, 12). Tout le reste
    (« AMRAP », « max », vide) → None : pas de cible, règles par défaut."""
    import re
    t = str(texte or "").strip().lower()
    m = re.fullmatch(r"(\d{1,2})\s*(?:-|–|à|a)\s*(\d{1,2})", t)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
    else:
        m = re.fullmatch(r"(\d{1,2})", t)
        if not m:
            return None
        lo = hi = int(m.group(1))
    if lo > hi:
        lo, hi = hi, lo
    return (lo, hi) if 1 <= lo <= 50 else None


def overload_suggestion(last_sets, prev_sets=None, is_bw=False, cible=None):
    """Double progression simplifiée à partir des 1–2 dernières séances.

    last_sets / prev_sets : listes de dicts {reps, poids, rpe?} (série la plus
    ancienne en premier). Retourne None sans historique, sinon un dict :
      kind  : "load" (monter la charge) | "reps" (même charge, +1 rep)
              | "hold" (consolider : même charge, mêmes reps)
      poids : charge cible (None en poids de corps)
      reps  : reps cibles par série
      label : phrase courte pour l'UI
      why   : justification en un mot-clé

    cible : fourchette de reps du programme (min, max), cf. parse_cible_reps.
    Avec elle, c'est une vraie double progression DANS la fourchette : on
    monte la charge quand toutes les séries atteignent le haut, et on ne vise
    jamais au-dessus. Sans elle, les seuils codés en dur ci-dessous — qui,
    sur un 3 × 5, faisaient afficher « vise 6 reps » (audit du 30/09, R15).

    Règles (sans cible) :
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

    if cible:
        return _suggestion_dans_la_fourchette(weight, same_weight, min_reps, avg_rpe, cible)

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


# ── Échauffement ────────────────────────────────────────────────────
# Hevy et Strong proposent des séries d'échauffement ; ici, rien : on
# attaquait un squat à 100 kg à froid, ou on improvisait (audit du 03/10).
# Rampe classique en pourcentage de la charge de travail, arrondie au
# 2,5 kg, barre vide en tête pour les mouvements à la barre. Ces séries
# s'affichent, elles ne s'enregistrent pas : elles fausseraient volume,
# records et suggestion.
SEUIL_ECHAUFFEMENT = 30.0
POIDS_BARRE = 20.0
_PALIERS_ECHAUFFEMENT = ((0.4, 8), (0.6, 5), (0.8, 3))
_EXOS_BARRE = {"Squat", "Soulevé de terre", "Soulevé de terre roumain", "Développé couché",
               "Développé militaire", "Développé incliné barre", "Rowing barre",
               "Front squat", "Hip thrust"}


def est_a_la_barre(base: str) -> bool:
    if base in _EXOS_BARRE:
        return True
    try:
        from core.exercises_data import EQUIPMENT_FOR_EXERCISE
        if "barre" in (EQUIPMENT_FOR_EXERCISE.get(base) or []):
            return True
    except ImportError:
        pass
    return " barre" in f" {(base or '').casefold()}" and "traction" not in (base or "").casefold()


def series_echauffement(poids_travail, barre: bool = False) -> list[dict]:
    """[{poids, reps}] avant une charge de travail donnée, ou [] si elle est
    trop légère pour qu'un échauffement spécifique serve à quelque chose."""
    try:
        travail = float(poids_travail or 0)
    except (TypeError, ValueError):
        return []
    if travail < SEUIL_ECHAUFFEMENT:
        return []
    out: list[dict] = []
    if barre and travail > POIDS_BARRE + 10:
        out.append({"poids": POIDS_BARRE, "reps": 10})
    paliers = list(_PALIERS_ECHAUFFEMENT)
    if travail >= 100:
        paliers.append((0.9, 1))
    for pct, reps in paliers:
        p = round(travail * pct / 2.5) * 2.5
        if barre:
            p = max(p, POIDS_BARRE)
        if p >= travail or (out and p <= out[-1]["poids"]):
            continue
        out.append({"poids": p, "reps": reps})
    return out


def conseil_depart(base: str, is_bw: bool) -> str:
    """Première fois sur un exercice : comment choisir sa charge.

    Le débutant n'avait aucune indication (audit du 03/10, profil 1). Pas de
    chiffre tiré du poids de corps : une charge trop lourde le premier jour
    blesse ou dégoûte. Une méthode, qui marche quel que soit le niveau."""
    if is_bw:
        return "garde 2 ou 3 reps en réserve."
    if est_a_la_barre(base):
        return "barre vide (20 kg), puis monte tant qu'il te reste 3-4 reps."
    return "une charge que tu soulèverais encore 3-4 fois (RPE 6-7)."
