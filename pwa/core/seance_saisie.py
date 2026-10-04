"""Ce que le formulaire devient.

Les séries saisies deviennent des lignes d'historique, la date du
formulaire est validée, le total de la séance est calculé, et le record
éventuel est annoncé à l'instant où il tombe plutôt que trois écrans plus
loin.

Les noms gardent leur préfixe `_` : ils viennent tels quels de
`routes/seance.py`, et le déplacement a été fait sans en renommer un seul
pour que chaque corps de fonction reste comparable au caractère près.
"""
import logging

from core.dates import logical_today_paris, now_paris
from core.hist import TYPE_ECHAUFFEMENT, is_muscu_perf, tonnage
from core.muscu import get_base_name
from core.seance_historique import _norm
from core.seance_semaine import _parse_date

logger = logging.getLogger(__name__)

def _form_date(form):
    """Date du formulaire validée et normalisée (YYYY-MM-DD). Une valeur
    malformée retombe sur l'aujourd'hui logique au lieu de provoquer un 500
    (les opérations ciblées dérivent la plage de semaine de cette date)."""
    d = _parse_date(form.get("date"))
    return (d or logical_today_paris()).strftime("%Y-%m-%d")


def _known_exo_names(hist, prog, prog_seances):
    """Noms d'exercices déjà utilisés (historique + exos perso + programmes),
    dédoublonnés à la casse près, pour l'autocomplétion à l'ajout d'un exo.
    But : réutiliser un nom existant plutôt qu'en recréer un mal orthographié
    (« developper couché » vs « Développé couché »), source de doublons dans
    l'historique et le sélecteur de progression."""
    seen = {}

    def _add(nm):
        nm = (nm or "").strip()
        if not nm:
            return
        k = _norm(nm)
        if k not in seen:
            seen[k] = nm

    for r in hist:
        ex = (r.get("Exercice") or "").strip()
        if not ex or ex == "SESSION" or ex.startswith("CARDIO:"):
            continue
        _add(get_base_name(ex))
    for e in (prog.get("_custom_exercises") or []):
        _add(e.get("name"))
    for _sn, _exos in prog_seances.items():
        for _e in _exos:
            _add(_e.get("name"))
    return sorted(seen.values(), key=lambda s: s.lower())


def _reps_saisies(s) -> int:
    """Répétitions d'une série saisie (JSON du client) ; 0 si illisible."""
    try:
        return int(float(s.get("reps") or 0))
    except (ValueError, TypeError, AttributeError):
        return 0


def _rows_from_sets(sets, *, semaine, seance, exo_final, muscle, date_str, is_bw):
    """Lignes history à partir des séries saisies (JSON du client)."""
    rows = []
    for i, s in enumerate(sets, start=1):
        try:
            reps = int(float(s.get("reps") or 0))
        except (ValueError, TypeError):
            reps = 0
        try:
            poids = 0.0 if is_bw else float(s.get("poids") or 0)
        except (ValueError, TypeError):
            poids = 0.0
        try:
            rpe = float(s.get("rpe")) if s.get("rpe") not in (None, "") else None
        except (ValueError, TypeError):
            rpe = None
        remarque = (s.get("remarque") or "").strip()
        # Série sans répétition = série non faite. La charge affichée venait du
        # pré-remplissage : la conserver inventait une performance « 82,5 kg × 0 »
        # qui polluait « Dernière fois » et comptait comme un entraînement.
        # On la marque SKIP, comme le bouton « Passer » d'un exercice entier :
        # la trace reste (l'exercice a été traité), la performance non.
        passee = reps <= 0
        if passee:
            poids = 0.0
            rpe = None
            remarque = ("SKIP " + remarque).strip()[:200]

        rows.append({
            "Semaine": semaine,
            "Séance": seance,
            "Exercice": exo_final,
            "Série": i,
            "Reps": max(0, reps),
            "Poids": max(0.0, poids),
            "Remarque": remarque[:200],
            "Muscle": muscle,
            "Date": date_str,
            "RPE": rpe if (rpe is None or 1 <= rpe <= 10) else None,
            # Échauffement (core/hist.py) : gardé, mais hors records et volume.
            **({"Type": TYPE_ECHAUFFEMENT}
               if s.get("type") == TYPE_ECHAUFFEMENT and not passee else {}),
        })
    return rows


def _session_totals(hist, seance, date_str):
    """Volume et nombre de séries réellement faites pour cette séance."""
    rows = [r for r in hist if r.get("Date") == date_str
            and _norm(r.get("Séance")) == _norm(seance)]
    return {
        "volume": tonnage(rows),
        "sets": sum(1 for r in rows if is_muscu_perf(r)),
    }


def _pr_check(hist_before, new_rows, exo_final, is_bw):
    """Record battu par cette saisie ? Compare la meilleure série enregistrée
    maintenant à ce qui existait AVANT, sur la même variante d'exercice.

    Retourne None, ou {kind, value, previous} — affiché en direct dans la
    séance : c'est le moment où un record a de la valeur, pas trois écrans
    plus loin dans l'onglet Progrès."""
    done = [r for r in new_rows if int(r.get("Reps") or 0) > 0]
    if not done:
        return None
    previous = [r for r in hist_before
                if _norm(r.get("Exercice")) == _norm(exo_final)
                and int(r.get("Reps") or 0) > 0]
    if is_bw:
        best_now = max(int(r["Reps"]) for r in done)
        best_before = max((int(r["Reps"]) for r in previous), default=0)
        if best_now > best_before:
            return {"kind": "reps", "value": best_now, "previous": best_before}
        return None
    best_now = max(float(r.get("Poids") or 0) for r in done)
    best_before = max((float(r.get("Poids") or 0) for r in previous), default=0.0)
    if best_now > 0 and not previous:
        return {"kind": "first", "value": best_now, "previous": 0}
    if best_now > best_before > 0:
        return {"kind": "weight", "value": best_now, "previous": best_before}
    # Même charge mais plus de reps = record d'endurance sur cette charge.
    if best_now > 0 and best_now == best_before:
        reps_now = max(int(r["Reps"]) for r in done
                       if float(r.get("Poids") or 0) == best_now)
        reps_before = max((int(r["Reps"]) for r in previous
                           if float(r.get("Poids") or 0) == best_now), default=0)
        if reps_now > reps_before:
            return {"kind": "reps_at_weight", "value": reps_now,
                    "previous": reps_before, "weight": best_now}
    return None


def _session_duration_min(form):
    """Durée de la séance en minutes, mesurée côté client (début = première
    saisie). Bornée à 8 h pour ignorer un onglet resté ouvert la nuit."""
    try:
        return max(0, min(480, int(form.get("duration_min") or 0)))
    except (TypeError, ValueError):
        return 0


def _parse_session_note(form):
    """Note /5 + commentaire du bilan de fin de séance. Retourne None si
    l'utilisateur a cliqué « Passer » (les deux champs vides)."""
    try:
        rating = int(form.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= 5:
        rating = 0
    comment = (form.get("comment") or "").strip()[:500]
    if not rating and not comment:
        return None
    note = {"ts": now_paris().strftime("%Y-%m-%d %H:%M")}
    if rating:
        note["rating"] = rating
    if comment:
        note["comment"] = comment
    return note
