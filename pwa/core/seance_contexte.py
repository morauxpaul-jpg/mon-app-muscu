"""Ce que le gabarit de séance reçoit, exercice par exercice.

Assemble en un dictionnaire tout ce qu'une carte d'exercice affiche : la
variante du jour, les séries déjà faites, le record, les semaines
précédentes, la suggestion, la fiche et l'illustration. `seance()` n'a plus
qu'à rendre.

Reconstruit aussi les exercices présents dans l'historique du jour mais
absents du programme : un exercice ajouté à la volée, ou retiré du
programme depuis, doit rester visible dans la séance qui l'a vu.

Les noms gardent leur préfixe `_` : ils viennent tels quels de
`routes/seance.py`, et le déplacement a été fait sans en renommer un seul
pour que chaque corps de fonction reste comparable au caractère près.
"""
import logging

from core.exercises_data import detect_isometric, get_exercise_info, variantes
from core.decharge import suggestion_allegee
from core.muscu import (BW_EXOS, auto_muscles, charge_de_depart, conseil_depart, est_a_la_barre,
                        get_base_name, series_echauffement)
from core.seance_historique import (_all_used_variants, _best_record, _exo_completed,
                                    _exo_curr_rows, _extract_variant, _last_session_sets,
                                    _last_variant, _norm, _previous_weeks_data,
                                    _suggestion_for)

logger = logging.getLogger(__name__)

def _build_exo_context(hist, exo_obj, seance, s_act, date_str, is_extra=False,
                       prefill_weight=True, forced_variant=None, exo_index=0,
                       show_overload_hint=True, decharge=False, echauffements=()):
    """Construit le dict passé au template pour un exercice.

    `decharge` : semaine allégée acceptée (core/decharge.py) — moitié des
    séries prévues, charges suggérées et pré-remplies à −10 %."""
    base = exo_obj["name"]
    p_sets = int(exo_obj.get("sets", 3))
    if decharge:
        p_sets = max(1, -(-p_sets // 2))
    muscle = exo_obj.get("muscle", "Autre")
    rest_seconds = int(exo_obj.get("rest_seconds", 90))
    # Le programme prescrit-il un repos ? Si oui, il passe avant le dernier
    # préréglage touché dans la barre du chrono (audit du 30/09, R12).
    rest_prescrit = "rest_seconds" in exo_obj
    # Cible de répétitions du programme (« 8-12 ») : affichée en filigrane
    # dans les cases reps. Sans elle, un programme n'est qu'une liste de noms.
    target_reps = str(exo_obj.get("reps") or "").strip()[:20]

    var = forced_variant if forced_variant is not None else _last_variant(hist, seance, base)
    exo_final = f"{base} ({var})" if var != "Standard" else base
    is_bw = base in BW_EXOS and var != "Lesté"

    curr = _exo_curr_rows(hist, date_str, seance, exo_final)
    curr.sort(key=lambda r: int(r["Série"] or 0))
    completed = _exo_completed(curr)          # séries de TRAVAIL seulement
    # Les échauffements du jour reviennent dans la carte (sinon ré-enregistrer
    # l'exercice les effacerait), mais ne comptent pour rien d'autre.
    echauff = _exo_curr_rows(list(echauffements), date_str, seance, exo_final)
    curr_carte = sorted(curr + echauff, key=lambda r: int(r["Série"] or 0))
    record = _best_record(hist, exo_final, is_bw)
    prev_weeks = _previous_weeks_data(hist, exo_final, seance, s_act, n_weeks=2)

    # Dernière séance pour pré-remplissage poids + affichage inline
    last_sets = _last_session_sets(hist, exo_final, seance, date_str)
    is_iso, target_sec = detect_isometric(base)
    suggestion = None
    if show_overload_hint and not is_iso:
        suggestion = _suggestion_for(hist, exo_final, seance, date_str, is_bw, target_reps)
    poids_allege = None
    if decharge and last_sets and not is_iso:
        suggestion, poids_allege = suggestion_allegee(last_sets, is_bw)

    # Sets à afficher dans l'éditeur : au moins p_sets, ou autant que déjà saisis
    n_rows = max(p_sets + len(echauff), len(curr_carte)) if curr_carte else p_sets
    sets = []
    existing_by_idx = {int(r["Série"] or 0): r for r in curr_carte}
    for i in range(1, n_rows + 1):
        r = existing_by_idx.get(i)
        if r:
            # Données déjà saisies — afficher les valeurs réelles
            reps_val = int(r.get("Reps") or 0)
            poids_val = float(r.get("Poids") or 0)
            sets.append({
                "serie": i,
                "reps": reps_val,
                "poids": poids_val,
                "remarque": r.get("Remarque") or "",
                "type": r.get("Type") or "",
            })
        else:
            poids_val = (charge_de_depart(base, is_bw, is_iso)  # cellule vide, 1re fois
                         if prefill_weight and not (completed or last_sets) else None)
            if prefill_weight and not completed and i <= len(last_sets):
                poids_val = poids_allege if poids_allege is not None else last_sets[i - 1]["poids"]
            sets.append({
                "serie": i,
                "reps": None,
                "poids": poids_val,
                "remarque": "",
            })

    # Échauffement : vers la charge suggérée si elle monte, sinon la plus
    # lourde de la dernière fois.
    echauffement = []
    if not is_bw and not is_iso and not completed:
        travail = (suggestion or {}).get("poids") or max(
            (s["poids"] for s in last_sets), default=0)
        echauffement = series_echauffement(travail, barre=est_a_la_barre(base))

    # Résumé inline : "80kg × 8, 85kg × 6"
    if last_sets:
        last_summary = ", ".join(
            f"{s['poids']:g}kg × {s['reps']}" for s in last_sets
        )
    else:
        last_summary = ""

    info = get_exercise_info(base)
    if not info:
        # Fallback: generate basic info from program data
        info = {
            "name": base,
            "muscles": [m.strip() for m in (muscle or "Autre").split(",")],
            "description": f"Exercice ciblant : {muscle}.",
            "tips": [],
            "image": None,
        }
    # Expose le 1RM courant au modal pour afficher la Table RM
    info = dict(info)
    info["one_rm"] = float(record.get("one_rm") or 0) if isinstance(record, dict) else 0

    return {
        "base": base,
        "exo_id": exo_obj.get("id") or "",
        "muscle": muscle,
        "p_sets": p_sets,
        "rest_seconds": rest_seconds,
        "target_reps": target_reps,
        "rest_prescrit": rest_prescrit,
        "is_extra": is_extra,
        "exo_index": exo_index,
        "variant": var,
        "exo_final": exo_final,
        "is_bw": is_bw or is_iso,  # iso : pas de poids par défaut
        "is_bw_base": base in BW_EXOS,
        "is_isometric": is_iso,
        "target_seconds": target_sec or 0,
        "completed": completed,
        "record": record,
        "prev_weeks": prev_weeks,
        "sets": sets,
        "last_summary": last_summary,
        "suggestion": suggestion,
        "echauffement": echauffement,
        "conseil_depart": "" if (last_sets or completed or is_iso) else conseil_depart(base, is_bw),
        "info": info,
        # Échanger l'exercice en un geste (vide hors catalogue). Le préfixe `_`
        # l'exclut du JSON passé à Alpine (`sans_prive`) : rendu côté serveur.
        "_variantes": variantes(base),
        # Renseigné quand cette carte remplace déjà un exercice du programme,
        # pour pouvoir revenir en arrière.
        "remplace": exo_obj.get("remplace") or "",
    }


def _build_all_exo_contexts(hist, all_exos, seance_name, s_act, date_str, prefill_weight,
                            show_overload_hint=True, decharge=False, echauffements=()):
    """Construit les contextes pour tous les exercices d'une séance, en
    assignant des variantes distinctes quand le même base name apparaît
    plusieurs fois (ex : 'Développé incliné' en Haltères ET en Barre)."""
    from collections import Counter
    bases = [e["name"] for e, _ in all_exos]
    base_counts = Counter(bases)
    base_variant_iters = {}
    for base_name, count in base_counts.items():
        if count > 1:
            used = _all_used_variants(hist, seance_name, base_name)
            while len(used) < count:
                used.append("Standard")
            base_variant_iters[base_name] = iter(used)

    out = []
    for idx, (e, is_extra) in enumerate(all_exos):
        forced = None
        it = base_variant_iters.get(e["name"])
        if it is not None:
            forced = next(it, "Standard")
        out.append(_build_exo_context(
            hist, e, seance_name, s_act, date_str, is_extra=is_extra,
            prefill_weight=prefill_weight, forced_variant=forced, exo_index=idx,
            show_overload_hint=show_overload_hint, decharge=decharge,
            echauffements=echauffements,
        ))
    # Supersets : « enchaîné avec le suivant » se lit dans le programme ; on
    # nomme le partenaire des deux côtés pour que chaque carte le dise.
    for i, (e, _extra) in enumerate(all_exos):
        if e.get("superset") is True and i + 1 < len(out):
            out[i]["superset_avec"] = out[i + 1]["base"]
            out[i + 1]["superset_de"] = out[i]["base"]
    return out


def _reconstruct_history_exos(hist, seance_name, s_act, date_str, covered_finals, start_index):
    """Reconstruit les exercices présents dans l'historique d'une (séance, date)
    mais absents de la liste déjà affichée (programme + extras live).

    Indispensable pour consulter une vieille séance : les exos ajoutés à la volée
    (extras) sont effacés du brouillon au `finish()`, et un exo retiré/renommé du
    programme disparaîtrait sinon — alors que leurs séries restent dans `history`.
    L'historique est la source de vérité de ce qui a réellement été fait.

    Rendus en cartes normales (`is_extra=False`) : éditables et effaçables via le
    `reset-exo` existant, sans casser l'indexation du formulaire `remove-extra`
    (qui suppose les extras live en dernier bloc contigu)."""
    # covered_finals est fourni déjà normalisé (casefold). On dédoublonne et
    # compare aussi en normalisé pour ne pas afficher deux fois le même exo
    # écrit avec une casse différente.
    seen = set()
    ordered_finals = []
    meta = {}
    for r in hist:
        if _norm(r.get("Séance")) != _norm(seance_name) or r.get("Date") != date_str:
            continue
        exo_final = (r.get("Exercice") or "").strip()
        if not exo_final or exo_final == "SESSION" or exo_final.startswith("CARDIO:"):
            continue
        nf = _norm(exo_final)
        if nf in covered_finals:
            continue
        if nf not in seen:
            seen.add(nf)
            ordered_finals.append(exo_final)  # garde la casse de la 1ère occurrence
            meta[exo_final] = {"muscle": r.get("Muscle") or "", "count": 0}
        # Compte toutes les séries de la même variante (toutes casses)
        for k in meta:
            if _norm(k) == nf:
                meta[k]["count"] += 1
                break

    out = []
    for i, exo_final in enumerate(ordered_finals):
        base = get_base_name(exo_final)
        variant = _extract_variant(exo_final)
        muscle = meta[exo_final]["muscle"] or auto_muscles(base) or "Autre"
        exo_obj = {"name": base, "muscle": muscle, "sets": max(1, meta[exo_final]["count"])}
        out.append(_build_exo_context(
            hist, exo_obj, seance_name, s_act, date_str, is_extra=False,
            prefill_weight=False, forced_variant=variant, exo_index=start_index + i,
        ))
    return out
