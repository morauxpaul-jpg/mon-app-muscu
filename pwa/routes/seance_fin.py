"""Fin de séance : bilan (note, commentaire, durée), nettoyage des calques
du jour, et debrief par l'IA juste après.

Sorti de routes/seance.py (audit du 30/09, M11)."""
import logging

from flask import Blueprint, request, redirect, url_for, jsonify, g, session

from core.data import (
    get_hist, get_prog, clear_user_cache, effacer_calques, purger_calques,
)
from core.dates import logical_today_paris, now_paris
from core.limiter import limiter
from core.analytics import track
from core.bilans_seance import _save_session_note, _load_session_note
from core.seance_semaine import _normalize_hist
from core.seance_calques import purger_les_calques
from core.seance_saisie import _form_date, _parse_session_note, _session_duration_min

logger = logging.getLogger(__name__)

bp = Blueprint("seance_fin", __name__)


@bp.route("/seance/finish", methods=["POST"])
def finish():
    """Termine la séance : enregistre le bilan (note /5 + commentaire, tous deux
    facultatifs — le bouton « Passer » n'envoie rien), nettoie le brouillon libre
    ou les extras, et retourne à l'accueil."""
    f = request.form
    mode = f["mode"]
    seance_name = f["seance_name"]
    date_str = _form_date(f)
    key = f"{seance_name}|{date_str}"
    # Calques du jour (table v46) : le brouillon libre ou les exos ajoutés,
    # les échanges et l'ordre des cartes ne servent qu'à cette séance-là.
    effacer_calques(seance_name, date_str,
                    ("brouillon" if mode == "libre" else "extras", "substituts", "ordre"))
    # Et les séances ouvertes puis abandonnées, qui ne passent jamais ici.
    purger_calques()
    # Restes de l'ancien stockage dans le programme (avant la v46).
    prog = get_prog()
    changed = False
    if mode == "libre" and "_libre_draft" in prog and key in prog["_libre_draft"]:
        prog["_libre_draft"].pop(key, None)
        changed = True
    if mode == "prefaite" and "_extras" in prog and key in prog["_extras"]:
        prog["_extras"].pop(key, None)
        changed = True
    # Comme les extras : le calque d'échanges ne concerne que la séance du
    # jour. Le garder ferait grossir le blob programme d'une entrée par
    # séance, à vie — et il est relu et réécrit à chaque interaction.
    if "_substituts" in prog and key in prog["_substituts"]:
        prog["_substituts"].pop(key, None)
        changed = True
    # Même règle, et c'est le calque qui y échappait : l'ordre des cartes
    # était écrit et jamais effacé. Les cartes d'une séance terminée sont de
    # toute façon reconstruites depuis l'historique, dans l'ordre où les
    # séries ont été saisies : l'ordre gardé ne servait plus à rien.
    if "_seance_order" in prog and key in prog["_seance_order"]:
        prog["_seance_order"].pop(key, None)
        changed = True
    # Rattrapage : les quatre lignes ci-dessus ne nettoient que la séance
    # qu'on vient de TERMINER. Une séance ouverte puis abandonnée ne passe
    # jamais par ici et garde son calque à vie — mesuré en production, des
    # entrées d'avril et de juin traînaient encore fin septembre.
    if purger_les_calques(prog):
        changed = True

    duration = _session_duration_min(f)
    note = _parse_session_note(f)
    if duration:
        note = note or {"ts": now_paris().strftime("%Y-%m-%d %H:%M")}
        note["duration_min"] = duration
    if note:
        _save_session_note(prog, date_str, seance_name, note)
        if prog.get("_session_notes") is not None:
            changed = True

    if changed:
        from core.data import save_prog
        save_prog(prog)
        clear_user_cache()
    # Une séance « terminée » sans une seule série n'est pas une séance faite :
    # la compter gonflait le funnel (et proposait un debrief de rien).
    series = [r for r in get_hist()
              if r.get("Date") == date_str and r.get("Séance") == seance_name
              and int(r.get("Reps") or 0) > 0]
    if not series:
        track("workout_finished_empty", {"mode": mode, "seance": seance_name})
        return redirect(url_for("accueil.index"))
    # L'accueil (écran suivant) propose le debrief de CETTE séance.
    session["last_workout"] = {"seance": seance_name, "date": date_str}
    track("workout_finished", {
        "mode": mode, "seance": seance_name,
        "rating": note.get("rating", 0) if note else 0,
        "has_comment": bool(note and note.get("comment")),
        "duration_min": duration,
    })
    return redirect(url_for("accueil.index"))


# ── Debrief de fin de séance ────────────────────────────────────
# Le coach est une page qu'il faut penser à ouvrir. Ce debrief va au-devant,
# au seul moment où l'attention est garantie : l'écran qui suit la séance.
# PRO complet ; un aperçu gratuit par semaine sert de démonstration honnête
# (on montre le produit réel, pas une capture).
FREE_DEBRIEFS_PER_WEEK = 1


def _debrief_allowed(prog) -> tuple[bool, str]:
    """(autorisé, raison). La raison sert à l'UI : « PRO » ou « quota »."""
    # L'essai compris : le debrief est, avec le coach, ce que l'essai doit
    # montrer (audit du 03/10, profil 6). ~250 jetons par séance.
    if getattr(g, "is_vip_full", False) or getattr(g, "is_vip", False):
        return True, "vip"
    from core.dates import continuous_week
    week = continuous_week(logical_today_paris())
    used = (prog.get("_debrief_free") or {}).get(str(week), 0)
    if used < FREE_DEBRIEFS_PER_WEEK:
        return True, "free_trial"
    return False, "quota"


@bp.route("/seance/debrief", methods=["POST"])
@limiter.limit("10 per hour")
def debrief():
    """Trois phrases sur la séance qui vient d'être terminée."""
    from core import debrief as core_debrief
    from core.db import _env

    data = request.get_json(silent=True) or {}
    seance = str(data.get("seance") or "").strip()
    date_str = _form_date({"date": data.get("date")})
    if not seance:
        return jsonify({"ok": False, "error": "séance manquante"}), 400

    prog = get_prog()
    allowed, reason = _debrief_allowed(prog)
    if not allowed:
        return jsonify({"ok": False, "locked": True,
                        "message": "Le debrief après séance fait partie de PRO."}), 200

    hist, _ = _normalize_hist(get_hist(), prog)
    facts = core_debrief.collect_facts(
        hist, seance, date_str, _load_session_note(prog, date_str, seance))
    if not facts:
        return jsonify({"ok": False, "error": "aucune série enregistrée"}), 200

    text = core_debrief.generate(_env("ANTHROPIC_API_KEY"), facts)
    if not text:
        return jsonify({"ok": False, "error": "indisponible"}), 200

    # Consomme l'aperçu gratuit seulement si la génération a abouti.
    if reason == "free_trial":
        from core.dates import continuous_week
        week = str(continuous_week(logical_today_paris()))
        store = prog.setdefault("_debrief_free", {})
        store[week] = int(store.get(week, 0)) + 1
        # Fenêtre glissante : on ne garde que les 4 dernières semaines.
        for k in sorted(store)[:-4]:
            store.pop(k, None)
        from core.data import save_prog
        save_prog(prog)

    track("debrief_generated", {"seance": seance, "tier": reason})
    return jsonify({"ok": True, "text": text, "trial": reason == "free_trial",
                    "volume": facts["volume"], "records": len(facts["records"])})
