"""Blueprint gestion — paramètres + opérations avancées (danger).

Le planning et le CRUD du programme sont déjà gérés dans /programme.
Cette page regroupe : paramètres d'affichage, auto-assignation des muscles,
reset soft, reset total, vider l'archive.
"""
import json
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, Response, g

from core.data import (
    get_hist, get_prog, save_prog, save_prog_body, save_hist, get_profile,
    get_onboarding, delete_user_account, set_newsletter_optin, list_body_weight,
    upsert_body_weight, rename_exercise_rows, list_session_notes,
)

logger = logging.getLogger(__name__)
from core.muscu import auto_muscles, get_base_name
from core.limiter import limiter
from core.analytics import paywall

MUSCLE_LIST = ["Pecs", "Dos", "Trapèzes", "Épaules", "Biceps", "Triceps", "Avant-bras", "Abdos",
               "Quadriceps", "Ischio-jambiers", "Fessiers", "Adducteurs", "Abducteurs", "Mollets", "Autre"]
PROFIL_OPTIONS = ["Maison", "Salle", "Les deux"]
bp = Blueprint("gestion", __name__)

DEFAULT_SETTINGS = {
    "auto_collapse": True,
    "show_1rm": True,
    "theme_animations": True,
    "auto_rest_timer": True,
    "auto_prefill_weight": True,
    "show_rpe": True,
    "show_overload_hint": True,
    "show_previous_weeks": 2,
    "notifications": False,
    "reminder_hour": 18,       # heure du rappel de séance (0 = aucun)
}


def _get_settings(prog):
    s = dict(DEFAULT_SETTINGS)
    s.update(prog.get("_settings", {}) or {})
    return s


def _norm_tokens(name):
    """Découpe un nom d'exercice en mots normalisés (sans accents, minuscule,
    sans ponctuation). « Développé couché (Barre) » → ['developpe','couche','barre']."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return [t for t in re.split(r"[^a-z0-9]+", s) if t]


def _tokens_match(a, b):
    """Deux mots = le même à une faute de frappe près. Match exact pour les mots
    courts (< 4 lettres) où le flou n'est pas fiable, sinon similarité ≥ 0.82."""
    if a == b:
        return True
    if len(a) < 4 or len(b) < 4:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.82


def _same_exercise(a, b):
    """Vrai seulement si a et b sont le même exercice écrit différemment (casse,
    accents, ponctuation, petite faute de frappe). Exige le MÊME nombre de mots :
    un mot en plus (« rowing machine » vs « rowing machine banc », « triceps
    extension » vs « triceps extension barre ») = exercice différent, pas un
    doublon. Chaque mot doit avoir un correspondant proche dans l'autre nom."""
    ta, tb = _norm_tokens(a), _norm_tokens(b)
    if not ta or not tb or len(ta) != len(tb):
        return False
    remaining = list(tb)
    for t in ta:
        idx = next((i for i, u in enumerate(remaining) if _tokens_match(t, u)), None)
        if idx is None:
            return False
        remaining.pop(idx)
    return True


def _duplicate_groups(exo_counts):
    """Regroupe les noms d'exercices de l'historique qui sont vraisemblablement
    le même exercice écrit différemment (accents, casse, ponctuation, petite
    faute de frappe). Union-find sur _same_exercise.

    Rien n'est modifié ici : on ne fait que PROPOSER des groupes à fusionner,
    la fusion reste validée manuellement par l'utilisateur (l'app ne peut pas
    deviner sans risque que « developper » = « développé »)."""
    names = list(exo_counts.keys())
    parent = {n: n for n in names}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if _same_exercise(names[i], names[j]):
                union(names[i], names[j])

    groups = {}
    for n in names:
        groups.setdefault(find(n), []).append(n)

    out = []
    for members in groups.values():
        if len(members) < 2:
            continue
        members_sorted = sorted(members, key=lambda n: (-exo_counts[n], n.lower()))
        out.append({
            "members": [{"name": n, "count": exo_counts[n]} for n in members_sorted],
            "suggested": members_sorted[0],  # le plus utilisé = candidat canonique
            "total": sum(exo_counts[n] for n in members),
        })
    # Les gros doublons (le plus de séries en jeu) d'abord.
    out.sort(key=lambda g: -g["total"])
    return out


@bp.route("/gestion")
def gestion():
    prog = get_prog()
    hist = get_hist()
    settings = _get_settings(prog)

    # Applique les limites Free côté affichage : historique capé à 2 semaines,
    # options premium forcées à off si affichage pour un non-VIP.
    if not getattr(g, "is_vip", False):
        settings["show_previous_weeks"] = min(settings.get("show_previous_weeks", 2), 2)

    nb_seances = len([k for k in prog if not k.startswith("_")])
    nb_exos = sum(len(prog[k]) for k in prog if not k.startswith("_"))
    nb_hist = len(hist)
    nb_archive = len(prog.get("_archive", []))
    custom_exercises = prog.get("_custom_exercises", [])

    # Noms d'exercices distincts présents dans l'historique (hors marqueurs
    # SESSION / cardio), avec le nombre de séries enregistrées pour chacun.
    # Sert à l'outil « Renommer un exercice dans l'historique ».
    exo_counts = {}
    for r in hist:
        ex = (r.get("Exercice") or "").strip()
        if not ex or ex == "SESSION" or ex.startswith("CARDIO:"):
            continue
        exo_counts[ex] = exo_counts.get(ex, 0) + 1
    hist_exercises = [
        {"name": name, "count": cnt}
        for name, cnt in sorted(exo_counts.items(), key=lambda kv: kv[0].lower())
    ]

    newsletter_opt_in = bool((get_profile() or {}).get("newsletter_opt_in"))

    return render_template(
        "gestion.html",
        active="plus",
        settings=settings,
        nb_seances=nb_seances,
        nb_exos=nb_exos,
        nb_hist=nb_hist,
        nb_archive=nb_archive,
        custom_exercises=custom_exercises,
        hist_exercises=hist_exercises,
        dup_groups=_duplicate_groups(exo_counts),
        muscle_list=MUSCLE_LIST,
        profil_options=PROFIL_OPTIONS,
        newsletter_opt_in=newsletter_opt_in,
    )


@bp.route("/gestion/redo-onboarding", methods=["POST"])
def redo_onboarding():
    """Force l'user à refaire l'onboarding (sans rien effacer)."""
    session.pop("onboarded", None)
    return redirect(url_for("onboarding.index"))


@bp.route("/gestion/exercice/ajouter", methods=["POST"])
@limiter.limit("20 per minute")
def add_custom_exercise():
    name = (request.form.get("name") or "").strip()
    if not name:
        return redirect(url_for("gestion.gestion"))
    muscle = (request.form.get("muscle") or "").strip()
    if not muscle:
        muscle = auto_muscles(name) or "Autre"
    profil = request.form.get("profil") or "Les deux"
    if profil not in PROFIL_OPTIONS:
        profil = "Les deux"
    prog = get_prog()
    customs = prog.setdefault("_custom_exercises", [])
    if any(e["name"].lower() == name.lower() for e in customs):
        return redirect(url_for("gestion.gestion") + "?exo=duplicate")
    customs.append({"name": name, "muscle": muscle, "profil": profil})
    save_prog(prog)
    return redirect(url_for("gestion.gestion") + "?exo=ok")


@bp.route("/gestion/exercice/supprimer", methods=["POST"])
@limiter.limit("20 per minute")
def delete_custom_exercise():
    idx = request.form.get("index")
    if idx is None:
        return redirect(url_for("gestion.gestion"))
    try:
        idx = int(idx)
    except (ValueError, TypeError):
        return redirect(url_for("gestion.gestion"))
    prog = get_prog()
    customs = prog.get("_custom_exercises", [])
    if 0 <= idx < len(customs):
        customs.pop(idx)
        prog["_custom_exercises"] = customs
        save_prog(prog)
    return redirect(url_for("gestion.gestion") + "?exo=deleted")


@bp.route("/gestion/exercice/renommer", methods=["POST"])
@limiter.limit("10 per minute")
def rename_exercise_history():
    """Renomme un exercice dans TOUT l'historique (match exact sur le nom).

    Usage typique : j'ai loggé « Développé incliné (Barre) » alors que je
    faisais en réalité du décliné — je renomme rétroactivement toutes ces
    séries en « Développé décliné (Barre) ». Le match étant exact, les autres
    variantes (ex. « Développé incliné » standard / haltères) restent intactes.
    """
    old = (request.form.get("old_name") or "").strip()
    new = (request.form.get("new_name") or "").strip()
    if not old or not new or old == new:
        return redirect(url_for("gestion.gestion") + "?rename=noop")

    # UPDATE ciblé : on ne réécrit plus tout l'historique (un delete+insert
    # global sur des milliers de lignes est une occasion de perte de données).
    try:
        count = rename_exercise_rows([old], new, auto_muscles(get_base_name(new)))
    except Exception as e:
        logger.error("rename_exercise FAILED user=%s: %s", getattr(g, "user_id", "?"), e)
        return redirect(url_for("gestion.gestion") + "?rename=error")
    if count:
        return redirect(url_for("gestion.gestion") + f"?rename=ok&n={count}")
    return redirect(url_for("gestion.gestion") + "?rename=none")


@bp.route("/gestion/exercice/fusionner", methods=["POST"])
@limiter.limit("10 per minute")
def merge_exercise_history():
    """Fusionne un groupe de doublons : renomme toutes les séries des noms
    du groupe vers le nom canonique choisi par l'utilisateur. Match exact sur
    chaque nom → aucune autre variante n'est touchée."""
    keep = (request.form.get("keep") or "").strip()
    members = [m.strip() for m in request.form.getlist("member") if m.strip()]
    if not keep or len(members) < 2:
        return redirect(url_for("gestion.gestion") + "?merge=noop#doublons")

    to_merge = {m for m in members if m != keep}
    if not to_merge:
        return redirect(url_for("gestion.gestion") + "?merge=noop#doublons")

    try:
        count = rename_exercise_rows(sorted(to_merge), keep,
                                     auto_muscles(get_base_name(keep)))
    except Exception as e:
        logger.error("merge_exercise FAILED user=%s: %s", getattr(g, "user_id", "?"), e)
        return redirect(url_for("gestion.gestion") + "?merge=error#doublons")
    if count:
        return redirect(url_for("gestion.gestion") + f"?merge=ok&n={count}#doublons")
    return redirect(url_for("gestion.gestion") + "?merge=none#doublons")


@bp.route("/gestion/settings", methods=["POST"])
def update_settings():
    prog = get_prog()
    s = _get_settings(prog)
    is_vip = bool(getattr(g, "is_vip", False))
    s["auto_collapse"] = request.form.get("auto_collapse") == "on"
    s["show_1rm"] = request.form.get("show_1rm") == "on"
    s["auto_rest_timer"] = request.form.get("auto_rest_timer") == "on"
    s["show_rpe"] = request.form.get("show_rpe") == "on"
    s["show_overload_hint"] = request.form.get("show_overload_hint") == "on"
    # Notifications : disponibles pour TOUS (rétention — on veut faire revenir
    # surtout les gratuits). Dé-gaté du PRO.
    s["notifications"] = request.form.get("notifications") == "on"
    # Heure du rappel de séance : envoyé par le serveur (cf. core/reminders.py),
    # donc il arrive même quand l'app est fermée.
    from core.reminders import clean_hour
    s["reminder_hour"] = clean_hour(request.form.get("reminder_hour"),
                                    s.get("reminder_hour", 18))
    # Options VIP : en Free on force à off quoi qu'il arrive.
    if is_vip:
        s["theme_animations"] = request.form.get("theme_animations") == "on"
        s["auto_prefill_weight"] = request.form.get("auto_prefill_weight") == "on"
    else:
        s["theme_animations"] = False
        s["auto_prefill_weight"] = False
    try:
        weeks = int(request.form.get("show_previous_weeks", 2))
    except (ValueError, TypeError):
        weeks = 2
    max_weeks = 10 if is_vip else 2
    s["show_previous_weeks"] = max(0, min(max_weeks, weeks))
    prog["_settings"] = s
    save_prog(prog)
    # Newsletter : consentement stocké dans profiles (requêtable pour l'export),
    # avec l'e-mail du compte + la date (preuve RGPD). Best-effort : ne casse
    # pas l'enregistrement des autres réglages.
    try:
        opt = request.form.get("newsletter") == "on"
        set_newsletter_optin(opt, getattr(g, "email", "") or session.get("email", ""))
    except Exception as e:
        logger.error("newsletter opt-in FAILED user=%s: %s", getattr(g, "user_id", "?"), e)
    return redirect(url_for("gestion.gestion"))


@bp.route("/gestion/notifications", methods=["POST"])
@limiter.limit("30 per minute")
def set_notifications():
    """Persiste juste le réglage `notifications` (JSON {enabled: bool}).

    Utilisé par la proposition d'activation affichée aux nouveaux utilisateurs
    (base.html) pour que le toggle en Gestion reflète leur choix sans qu'ils
    aient à y passer. Le toggle de la page Gestion, lui, passe par
    update_settings (formulaire).
    """
    prog = get_prog()
    s = _get_settings(prog)
    s["notifications"] = bool((request.get_json(silent=True) or {}).get("enabled"))
    prog["_settings"] = s
    save_prog(prog)
    return ("", 204)


@bp.route("/gestion/reset-soft", methods=["POST"])
@limiter.limit("3 per minute")
def reset_soft():
    prog = get_prog()
    hist = get_hist()

    # Volume legacy : sum(Poids * Reps)
    v_tot = 0
    for r in hist:
        try:
            v_tot += int(float(r.get("Poids", 0) or 0) * float(r.get("Reps", 0) or 0))
        except (ValueError, TypeError):
            pass
    prog["_legacy_volume"] = int(prog.get("_legacy_volume", 0) or 0) + v_tot

    # Archive : par (exo, semaine), garde le set au plus gros poids
    by_key = {}
    for r in hist:
        try:
            reps = int(float(r.get("Reps", 0) or 0))
            poids = float(r.get("Poids", 0) or 0)
            sem = int(float(r.get("Semaine", 0) or 0))
        except (ValueError, TypeError):
            continue
        if reps <= 0:
            continue
        key = (r.get("Exercice", ""), sem)
        cur = by_key.get(key)
        if cur is None or poids > cur["Poids"]:
            by_key[key] = {
                "Exercice": r.get("Exercice", ""),
                "Semaine": sem,
                "Poids": poids,
                "Reps": reps,
                "Muscle": r.get("Muscle", ""),
            }
    archive = prog.get("_archive", []) or []
    archive.extend(by_key.values())
    prog["_archive"] = archive[-2000:]

    save_prog(prog)
    save_hist([])
    return redirect(url_for("gestion.gestion") + "?reset=soft")


@bp.route("/gestion/reset-total", methods=["POST"])
@limiter.limit("3 per minute")
def reset_total():
    if request.form.get("confirm") != "yes":
        return redirect(url_for("gestion.gestion"))
    prog = get_prog()
    prog.pop("_archive", None)
    prog.pop("_legacy_volume", None)
    prog.pop("_extras", None)
    prog.pop("_libre_draft", None)
    save_prog(prog)
    save_hist([])
    return redirect(url_for("gestion.gestion") + "?reset=total")


@bp.route("/gestion/delete-account", methods=["POST"])
@limiter.limit("3 per minute")
def delete_account():
    """Suppression DÉFINITIVE du compte + toutes les données (exigence des
    stores : doit être faisable dans l'app, pas seulement par email)."""
    if request.form.get("confirm") != "yes":
        return redirect(url_for("gestion.gestion"))
    try:
        delete_user_account()
    except Exception as e:
        logger.error("delete-account FAILED user=%s: %s", getattr(g, "user_id", "?"), e)
        return render_template(
            "error.html", code=500,
            message="La suppression du compte a échoué. Réessaie, ou écris à "
                    "muscutracker@gmail.com pour une suppression manuelle.",
        ), 500
    session.clear()
    return redirect("/")


def _sanitize_program(raw: dict) -> dict:
    """Nettoie un programme importé : séances = listes d'exercices typés,
    planning = jours FR connus. Un fichier bricolé à la main ne doit jamais
    pouvoir rendre les pages inutilisables (une séance non-liste faisait
    planter /gestion et /seance)."""
    from routes.programme import _exo_entry
    from core.dates import DAYS_FR as _DAYS
    out: dict = {}
    for sname, exos in (raw or {}).items():
        if not isinstance(sname, str) or sname.startswith("_") or not isinstance(exos, list):
            continue
        cleaned = []
        for e in exos:
            if not isinstance(e, dict):
                continue
            name = (e.get("name") or "").strip()[:80]
            if not name:
                continue
            try:
                sets = max(1, min(20, int(e.get("sets") or 3)))
            except (TypeError, ValueError):
                sets = 3
            muscle = (e.get("muscle") or "Autre").strip()[:60] or "Autre"
            cleaned.append(_exo_entry(name, sets, muscle, e))
        out[sname[:60]] = cleaned
    names = set(out)
    raw_planning = raw.get("_planning") if isinstance(raw.get("_planning"), dict) else {}
    out["_planning"] = {d: (raw_planning.get(d) if raw_planning.get(d) in names else "")
                        for d in _DAYS}
    for key in ("_name", "_origin", "_started_at"):
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            out[key] = val.strip()[:80]
    return out


@bp.route("/gestion/export")
def export_data():
    """Exporte toutes les données utilisateur en JSON (VIP uniquement)."""
    if not getattr(g, "is_vip_full", False):
        return paywall("Export complet", 403)
    prog = get_prog()
    hist = get_hist()
    profile = get_profile() or {}
    onboarding = get_onboarding() or {}
    try:
        poids = list_body_weight(limit=5000)
    except Exception as e:  # migration v33 absente → export sans les pesées
        logger.error("export list_body_weight FAILED: %s", e)
        poids = []
    try:
        bilans = list_session_notes()
    except Exception as e:  # migration v34 absente
        logger.error("export list_session_notes FAILED: %s", e)
        bilans = []
    payload = {
        "version": 2,
        "exported_at": date.today().isoformat(),
        "programme": prog,
        "historique": hist,
        "poids": poids,
        "bilans": bilans,
        "profil": {k: v for k, v in profile.items() if k != "id"},
        "onboarding": {k: v for k, v in onboarding.items() if k not in ("user_id", "id")},
    }
    filename = f"muscu-tracker-backup-{date.today().isoformat()}.json"
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/gestion/import", methods=["POST"])
@limiter.limit("5 per minute")
def import_data():
    """Importe des données depuis un fichier JSON (VIP uniquement)."""
    if not getattr(g, "is_vip_full", False):
        return paywall("Import complet", 403)
    f = request.files.get("file")
    if not f:
        return redirect(url_for("gestion.gestion") + "?import=error")
    try:
        data = json.loads(f.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return redirect(url_for("gestion.gestion") + "?import=error")

    # Validation structurelle : un fichier malformé ne doit JAMAIS écraser
    # les données existantes (un `programme` non-dict casserait toute l'app).
    if not isinstance(data, dict):
        return redirect(url_for("gestion.gestion") + "?import=error")
    prog_in = data.get("programme")
    hist_in = data.get("historique")
    if prog_in is not None and not isinstance(prog_in, dict):
        return redirect(url_for("gestion.gestion") + "?import=error")
    if hist_in is not None:
        if not isinstance(hist_in, list) or not all(isinstance(r, dict) for r in hist_in):
            return redirect(url_for("gestion.gestion") + "?import=error")
        if len(hist_in) > 100_000:
            return redirect(url_for("gestion.gestion") + "?import=error")
    if prog_in is None and hist_in is None:
        return redirect(url_for("gestion.gestion") + "?import=error")

    if prog_in is not None:
        try:
            save_prog_body(_sanitize_program(prog_in))
        except (TypeError, ValueError, AttributeError):
            return redirect(url_for("gestion.gestion") + "?import=error")
    if hist_in is not None:
        try:
            save_hist(hist_in)
        except (ValueError, TypeError):
            # Lignes aux types invalides (Reps/Poids non numériques…)
            return redirect(url_for("gestion.gestion") + "?import=error")
    # Bilans de séance (facultatif, export v2).
    bilans_in = data.get("bilans")
    if isinstance(bilans_in, list):
        from core.data import upsert_session_note
        for bn in bilans_in[:5000]:
            if not isinstance(bn, dict):
                continue
            try:
                upsert_session_note(str(bn.get("date"))[:10], str(bn.get("seance") or "")[:60],
                                    bn.get("rating"), bn.get("comment"))
            except Exception:
                continue

    # Pesées (facultatif) : fusion par date, une entrée invalide est ignorée.
    poids_in = data.get("poids")
    if isinstance(poids_in, list):
        for e in poids_in[:5000]:
            try:
                kg = float(e.get("poids_kg"))
                d = str(e.get("date"))[:10]
                date.fromisoformat(d)
                if 20 <= kg < 500:
                    upsert_body_weight(d, kg)
            except (AttributeError, TypeError, ValueError):
                continue

    return redirect(url_for("gestion.gestion") + "?import=ok")


