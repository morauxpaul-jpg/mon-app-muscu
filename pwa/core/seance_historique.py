"""Ce que l'historique dit d'un exercice.

Ses séries du jour, sa dernière variante, son record, ses semaines
précédentes, l'état de récupération du muscle et la suggestion de charge.
C'est le raisonnement qui remplit la carte d'un exercice avant que
l'utilisateur ne saisisse quoi que ce soit.

Les noms gardent leur préfixe `_` : ils viennent tels quels de
`routes/seance.py`, et le déplacement a été fait sans en renommer un seul
pour que chaque corps de fonction reste comparable au caractère près.
"""
import logging
from datetime import datetime

from core.dates import now_paris
from core.exercises_data import variantes
from core.muscu import VARIANTS, calc_1rm, overload_suggestion, parse_rpe

logger = logging.getLogger(__name__)

def _norm(s):
    """Normalise un nom (exercice/séance) pour comparer l'historique de façon
    tolérante à la casse et aux espaces parasites. Côté LECTURE uniquement :
    le stockage garde le nom tel que saisi. Résout les ruptures d'historique
    type « Développé incliné barre » vs « developpé incliné barre »."""
    return (s or "").strip().casefold()


def _exo_curr_rows(hist, date_str, seance, exercice):
    """Séries de CE jour pour cet exercice.

    Par date et non par semaine : deux séances du même nom dans une semaine
    sont deux séances distinctes. Comparer la semaine rouvrait le jeudi la
    séance du lundi, cochée et remplie, donc impossible à refaire.
    """
    return [r for r in hist
            if r.get("Date") == date_str and _norm(r["Séance"]) == _norm(seance)
            and _norm(r["Exercice"]) == _norm(exercice)]


def _exo_completed(curr_rows):
    if not curr_rows:
        return False
    has_data = any(r["Poids"] > 0 or r["Reps"] > 0 for r in curr_rows)
    has_skip = any("SKIP" in (r.get("Remarque") or "") for r in curr_rows)
    return has_data or has_skip


def _match_base_variant(exercice, exo_base):
    """True si `exercice` est le base name exact ou une variante parenthésée.
    Comparaison insensible à la casse/espaces."""
    ne, nb = _norm(exercice), _norm(exo_base)
    return ne == nb or ne.startswith(nb + " (")


def _extract_variant(exercice):
    if "(" in exercice:
        v = exercice.split("(")[1].replace(")", "").strip()
        return v if v in VARIANTS else "Standard"
    return "Standard"


def _last_variant(hist, seance, exo_base):
    """Dernière variante utilisée pour cet exo dans cette séance."""
    matches = [r for r in hist
               if _norm(r["Séance"]) == _norm(seance) and _match_base_variant(r["Exercice"], exo_base)]
    if not matches:
        return "Standard"
    return _extract_variant(matches[-1]["Exercice"])


def _all_used_variants(hist, seance, exo_base):
    """Toutes les variantes distinctes utilisées pour ce base name dans cette séance,
    dans l'ordre d'apparition (dernière en premier pour la plus récente)."""
    matches = [r for r in hist
               if _norm(r["Séance"]) == _norm(seance) and _match_base_variant(r["Exercice"], exo_base)]
    seen = set()
    variants = []
    for r in reversed(matches):
        v = _extract_variant(r["Exercice"])
        if v not in seen:
            seen.add(v)
            variants.append(v)
    return variants


def _best_record(hist, exo_final, is_bw):
    """Renvoie {best_weight, best_1rm, best_reps} pour la variante exacte."""
    matches = [r for r in hist if _norm(r["Exercice"]) == _norm(exo_final) and r["Reps"] > 0]
    if not matches:
        return None
    if is_bw:
        return {"reps": max(r["Reps"] for r in matches)}
    best_w = max(r["Poids"] for r in matches)
    best_1rm = max(calc_1rm(r["Poids"], r["Reps"]) for r in matches)
    return {"weight": best_w, "one_rm": round(best_1rm, 1)}


def _previous_weeks_data(hist, exo_final, seance, s_act, n_weeks=2):
    """Semaines précédentes avec leurs séries, + semaines manquées.

    Par défaut on filtre sur la séance courante (progression semaine par semaine
    de CE créneau). Mais si l'exo n'a jamais été fait dans cette séance, on
    retombe sur son historique TOUTES séances confondues : ainsi un exo déplacé
    d'un jour à l'autre (ex : développé couché fait en Push 1 puis ajouté en
    Push 2) garde son historique visible. Même repli que _last_session_sets."""
    f_h = [r for r in hist if _norm(r["Exercice"]) == _norm(exo_final) and _norm(r["Séance"]) == _norm(seance)]
    cross_session = False
    if not any(r["Semaine"] < s_act and r["Poids"] > 0 for r in f_h):
        alt = [r for r in hist if _norm(r["Exercice"]) == _norm(exo_final)]
        if any(r["Semaine"] < s_act and r["Poids"] > 0 for r in alt):
            f_h = alt
            cross_session = True

    hist_weeks_all = sorted({r["Semaine"] for r in f_h if r["Semaine"] < s_act})
    hist_weeks = [w for w in hist_weeks_all
                  if any(r["Semaine"] == w and r["Poids"] > 0 for r in f_h)]
    # Les séances manquées ne concernent que le créneau courant : on les ignore
    # quand l'historique affiché provient d'autres séances.
    missed = set() if cross_session else {
        r["Semaine"] for r in hist
        if _norm(r["Séance"]) == _norm(seance) and r["Exercice"] == "SESSION" and r["Semaine"] < s_act}

    if not hist_weeks:
        return []

    weeks_to_show = hist_weeks[-n_weeks:]
    min_w = weeks_to_show[0]
    combined = sorted(set(weeks_to_show) | {w for w in missed if w >= min_w})
    out = []
    for w in combined:
        if w in missed and w not in weeks_to_show:
            out.append({"week": w, "missed": True, "rows": [], "cross_session": False})
        else:
            rows = [r for r in f_h if r["Semaine"] == w and r["Poids"] > 0]
            rows.sort(key=lambda r: int(r["Série"] or 0))
            out.append({"week": w, "missed": False, "rows": rows, "cross_session": cross_session})
    return out


def _recup_status(hist, s_act):
    """Statut de récupération par muscle pour la semaine active."""
    muscles = ["Pecs", "Dos", "Épaules", "Biceps", "Triceps", "Abdos", "Quadriceps",
               "Adducteurs", "Abducteurs", "Mollets"]
    now = now_paris().replace(tzinfo=None)
    out = []
    for m in muscles:
        trained = [r for r in hist if r["Semaine"] == s_act and m in (r.get("Muscle") or "")]
        color, label = "#00FF7F", "PRÊT"
        if trained:
            dates = [r["Date"] for r in trained if r.get("Date")]
            if dates:
                last = max(dates)
                try:
                    diff = (now - datetime.strptime(last, "%Y-%m-%d")).days
                    if diff < 1:
                        color, label = "#FF453A", "REPAR."
                    elif diff < 2:
                        color, label = "#FFA500", "RECON."
                except ValueError:
                    pass
        out.append({"muscle": m, "color": color, "label": label})
    return out


def _recent_sessions_sets(hist, exo_final, seance, date_str, n=2):
    """Séries des `n` dernières SÉANCES où cet exo a été réalisé, de la plus
    récente à la plus ancienne : liste de listes de dicts {reps, poids, rpe}.

    Groupé par date : quand on fait Push le lundi et le jeudi, « la dernière
    fois » c'est lundi. Par semaine, on proposait les charges d'il y a sept
    jours en ignorant la séance de l'avant-veille — et la suggestion de
    surcharge se calculait sur ces données périmées.
    """
    def _avant(r):
        # Reps > 0 : une série à zéro répétition n'a pas été faite, elle ne
        # peut pas servir de référence pour la suivante. (Les anciennes lignes
        # « charge pré-remplie, 0 rep » sont ainsi écartées sans migration.)
        return (bool(r.get("Date")) and r["Date"] < date_str
                and int(r.get("Reps") or 0) > 0)

    matches = [r for r in hist
               if _norm(r["Exercice"]) == _norm(exo_final)
               and _norm(r["Séance"]) == _norm(seance) and _avant(r)]
    if not matches:
        # Repli toutes séances confondues : un exo déplacé d'un créneau à
        # l'autre garde son historique.
        matches = [r for r in hist
                   if _norm(r["Exercice"]) == _norm(exo_final) and _avant(r)]
    if not matches:
        return []
    dates = sorted({r["Date"] for r in matches}, reverse=True)[:n]
    out = []
    for d in dates:
        rows = [r for r in matches if r["Date"] == d]
        rows.sort(key=lambda r: int(r["Série"] or 0))
        out.append([{"reps": int(r["Reps"]), "poids": float(r["Poids"]),
                     "rpe": parse_rpe(r.get("Remarque"))} for r in rows])
    return out


def _last_session_sets(hist, exo_final, seance, date_str):
    """Séries de la dernière séance où cet exo a été réalisé, sous forme de
    liste de dicts {reps, poids, rpe}. Utilisé pour le pré-remplissage des
    poids et l'affichage inline « Dernière fois »."""
    recent = _recent_sessions_sets(hist, exo_final, seance, date_str, n=1)
    return recent[0] if recent else []


def _suggestion_for(hist, exo_final, seance, date_str, is_bw):
    """Suggestion de surcharge (cf. core.muscu.overload_suggestion) à partir
    des deux dernières séances de cet exo."""
    recent = _recent_sessions_sets(hist, exo_final, seance, date_str, n=2)
    if not recent:
        return None
    return overload_suggestion(recent[0], recent[1] if len(recent) > 1 else None, is_bw=is_bw)
