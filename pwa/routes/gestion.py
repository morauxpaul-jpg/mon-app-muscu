"""Blueprint gestion — paramètres + opérations avancées (danger).

Le planning et le CRUD du programme sont déjà gérés dans /programme.
Cette page regroupe : paramètres d'affichage, auto-assignation des muscles,
reset total (le « reset soft » et son archive ont été retirés en v47).
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
    list_all_nutrition, export_coach, get_reglages, save_reglages, effacer_tous_calques,
)

logger = logging.getLogger(__name__)
from core.muscu import MUSCLE_LIST, auto_muscles, get_base_name
from core.exercises_data import canoniser, NIVEAUX_SURS
from core.limiter import limiter
from core import stripe_client
from core.analytics import paywall

PROFIL_OPTIONS = ["Maison", "Salle", "Les deux"]
bp = Blueprint("gestion", __name__)

def _get_settings(prog):
    """Réglages de l'utilisateur (table `reglages`, v45 ; défauts dans
    core/db_reglages.py)."""
    return get_reglages(prog)


def _enregistrer_reglages(prog, s):
    """Dans la table ; dans le programme si la base n'a pas encore la v45."""
    if not save_reglages(s):
        prog["_settings"] = s
        save_prog(prog)


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


def _alignements(exo_counts):
    """Ce que la migration PROPOSE de renommer, avec de quoi juger.

    Rien n'est modifié ici. Chaque ligne porte le nombre de séries en jeu,
    le niveau de certitude du rapprochement, et surtout si le renommage
    FUSIONNERAIT deux historiques — c'est là que ça devient irrattrapable,
    donc c'est écrit noir sur blanc.
    """
    propositions = []
    deja = {_cle_exo(n) for n in exo_counts}
    for nom, count in exo_counts.items():
        vers, niveau = canoniser(nom)
        if not vers:
            continue
        propositions.append({
            "depuis": nom,
            "vers": vers,
            "count": count,
            "niveau": niveau,
            "sur": niveau in NIVEAUX_SURS,
            # Le nom d'arrivée existe déjà : les deux historiques n'en
            # feront plus qu'un. Souvent voulu (deux orthographes du même
            # exercice), mais jamais anodin.
            "fusion": _cle_exo(vers) in deja,
        })
    # Les plus sûrs d'abord, puis le plus de séries en jeu.
    propositions.sort(key=lambda p: (not p["sur"], -p["count"], p["depuis"].lower()))
    return propositions


def _cle_exo(nom):
    return (nom or "").strip().casefold()


@bp.route("/gestion")
def gestion():
    prog = get_prog()
    hist = get_hist()
    settings = _get_settings(prog)

    nb_seances = len([k for k in prog if not k.startswith("_")])
    nb_exos = sum(len(prog[k]) for k in prog if not k.startswith("_"))
    nb_hist = len(hist)
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
        custom_exercises=custom_exercises,
        hist_exercises=hist_exercises,
        dup_groups=_duplicate_groups(exo_counts),
        alignements=_alignements(exo_counts),
        muscle_list=MUSCLE_LIST,
        profil_options=PROFIL_OPTIONS,
        newsletter_opt_in=newsletter_opt_in,
    )


@bp.route("/gestion/redo-onboarding", methods=["POST"])
def redo_onboarding():
    """Renvoie à l'onboarding. Rien n'est effacé : l'historique reste, et un
    programme choisi s'ajoute dans un nouveau dossier (routes/onboarding.py)."""
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


@bp.route("/gestion/exercice/aligner", methods=["POST"])
@limiter.limit("10 per minute")
def aligner_exercices():
    """Applique les renommages COCHÉS, et eux seuls.

    On recalcule la proposition côté serveur au lieu de faire confiance au
    formulaire : sinon un champ trafiqué pourrait renommer un exercice vers
    n'importe quoi, et l'historique ne se rattrape pas.
    """
    choisis = {n.strip() for n in request.form.getlist("aligner") if n.strip()}
    if not choisis:
        return redirect(url_for("gestion.gestion") + "?align=noop#aligner")

    hist = get_hist()
    exo_counts = {}
    for r in hist:
        ex = (r.get("Exercice") or "").strip()
        if not ex or ex == "SESSION" or ex.startswith("CARDIO:"):
            continue
        exo_counts[ex] = exo_counts.get(ex, 0) + 1

    total = 0
    try:
        for p in _alignements(exo_counts):
            if p["depuis"] not in choisis:
                continue
            total += rename_exercise_rows([p["depuis"]], p["vers"],
                                          auto_muscles(get_base_name(p["vers"])))
    except Exception as e:
        logger.error("aligner_exercices FAILED user=%s: %s",
                     getattr(g, "user_id", "?"), e)
        return redirect(url_for("gestion.gestion") + "?align=error#aligner")
    if not total:
        return redirect(url_for("gestion.gestion") + "?align=none#aligner")
    return redirect(url_for("gestion.gestion") + f"?align=ok&n={total}#aligner")


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
    s["recap_hebdo"] = request.form.get("recap_hebdo") == "on"
    # Le pré-remplissage des charges n'est PAS une option payante : c'est la
    # fonction la plus utilisée de la saisie. La couper aux comptes gratuits
    # dès qu'ils touchaient un réglage ne faisait pas payer, ça faisait partir
    # — et sans le moindre message pour l'expliquer.
    s["auto_prefill_weight"] = request.form.get("auto_prefill_weight") == "on"
    # « Replier automatiquement », « Afficher le 1RM », « Animations du thème »
    # (vendu PRO) et « Semaines précédentes affichées » ont été retirés : rien
    # ne les lisait, ils n'avaient aucun effet (v45).
    _enregistrer_reglages(prog, s)
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
    _enregistrer_reglages(prog, s)
    return ("", 204)


@bp.route("/gestion/reset-total", methods=["POST"])
@limiter.limit("3 per minute")
def reset_total():
    if request.form.get("confirm") != "yes":
        return redirect(url_for("gestion.gestion") + "?reset=confirm")
    prog = get_prog()
    prog.pop("_extras", None)
    prog.pop("_libre_draft", None)
    save_prog(prog)
    effacer_tous_calques()
    save_hist([])
    return redirect(url_for("gestion.gestion") + "?reset=total")


@bp.route("/gestion/delete-account", methods=["POST"])
@limiter.limit("3 per minute")
def delete_account():
    """Suppression DÉFINITIVE du compte + toutes les données (exigence des
    stores : doit être faisable dans l'app, pas seulement par email)."""
    if request.form.get("confirm") != "yes":
        return redirect(url_for("gestion.gestion"))
    # D'abord l'abonnement : un compte effacé ne doit plus être prélevé. Si
    # Stripe ne répond pas, on ne supprime rien.
    try:
        stripe_client.resilier_avant_suppression(stripe_client.client())
    except Exception as e:
        logger.error("delete-account stripe FAILED user=%s: %s", getattr(g, "user_id", "?"), e)
        return render_template(
            "error.html", code=502,
            message="Ton abonnement n'a pas pu être résilié, donc ton compte n'a "
                    "pas été supprimé. Réessaie dans un instant, ou résilie depuis "
                    "« Gérer mon abonnement » (page PRO) puis reviens ici.",
        ), 502
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
    from core.rotation import rotation_nettoyee
    rotation = rotation_nettoyee(raw.get("_rotation"), names)
    if rotation:
        out["_rotation"] = rotation
    for key in ("_name", "_origin", "_started_at"):
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            out[key] = val.strip()[:80]
    return out


@bp.route("/gestion/export")
def export_data():
    """Exporte TOUTES les données de l'utilisateur en JSON — pour tout le
    monde. C'est le droit à la portabilité (RGPD, art. 20) : il était réservé
    aux membres PRO, et la page de suppression de compte conseillait
    d'exporter… vers un mur de paiement (audit du 30/09, I12). La
    RÉimportation reste une fonction PRO."""
    prog = get_prog()
    hist = get_hist(echauffement=True)      # la portabilité porte tout
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
    optionnels = {}
    for nom, lire in (("nutrition", list_all_nutrition), ("coach", export_coach)):
        try:
            optionnels[nom] = lire()
        except Exception as e:  # table absente : export sans elle
            logger.error("export %s FAILED: %s", nom, e)
            optionnels[nom] = [] if nom == "nutrition" else {}
    payload = {
        "version": 3,
        "exported_at": date.today().isoformat(),
        "programme": prog,
        "historique": hist,
        "poids": poids,
        "bilans": bilans,
        "profil": {k: v for k, v in profile.items() if k != "id"},
        "onboarding": {k: v for k, v in onboarding.items() if k not in ("user_id", "id")},
        "nutrition": [{k: v for k, v in r.items() if k != "user_id"}
                      for r in optionnels["nutrition"]],
        "coach": optionnels["coach"],
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




# ── Import de l'historique Hevy / Strong ─────────────────────────
# Pour tout le monde : c'est ce qui permet de venir sans repartir de zéro.
# Même parcours que l'import Strava : déposer, voir ce qui entrerait,
# valider. Rien n'est écrit avant la validation, rien n'est jamais effacé.

MAX_IMPORT_MUSCU_OCTETS = 4 * 1024 * 1024   # sous MAX_CONTENT_LENGTH (5 Mo)
MAX_IMPORT_MUSCU_SEANCES = 3000


@bp.route("/gestion/import-muscu")
def import_muscu_page():
    return render_template("import_muscu.html", active="plus", etape="depot")


@bp.route("/gestion/import-muscu", methods=["POST"])
@limiter.limit("10 per minute")
def import_muscu_apercu():
    from core.import_muscu import compacter, lire_export, marquer_doublons

    def depot(erreur):
        return render_template("import_muscu.html", active="plus", etape="depot", erreur=erreur)

    fichier = request.files.get("fichier")
    if not fichier or not fichier.filename:
        return depot("Choisis le fichier .csv exporté depuis Hevy ou Strong.")
    brut = fichier.read(MAX_IMPORT_MUSCU_OCTETS + 1)
    if len(brut) > MAX_IMPORT_MUSCU_OCTETS:
        return depot("Fichier trop volumineux (plus de 4 Mo).")
    try:
        seances, rapport = lire_export(brut)
    except Exception as e:
        logger.warning("import muscu illisible : %s", type(e).__name__)
        return depot("Fichier illisible. Envoie le .csv tel qu'exporté.")
    if not seances and not rapport["lignes"]:
        return depot("Ce fichier n'a pas la forme d'un export Hevy ou Strong : "
                     "aucune colonne de date, d'exercice et de répétitions reconnue.")

    try:
        seances = marquer_doublons(seances, get_hist())
    except Exception as e:
        logger.error("import muscu : historique illisible (%s)", e)
        return depot("Ton historique n'a pas pu être lu. Réessaie dans un instant.")
    a_importer = [s for s in seances if not s["deja"]][:MAX_IMPORT_MUSCU_SEANCES]
    renommes = sorted((src, nom) for src, nom in rapport["exercices"].items() if src != nom)
    return render_template(
        "import_muscu.html", active="plus", etape="apercu",
        a_importer=a_importer, rapport=rapport, renommes=renommes[:60],
        nb_deja=sum(1 for s in seances if s["deja"]),
        nb_series=sum(len(e["series"]) for s in a_importer for e in s["exercices"]),
        charge=json.dumps(compacter(a_importer), ensure_ascii=False, separators=(",", ":")),
    )


@bp.route("/gestion/import-muscu/confirmer", methods=["POST"])
@limiter.limit("5 per minute")
def import_muscu_confirmer():
    from core.data import ajouter_lignes
    from core.import_muscu import lignes_historique, marquer_doublons
    try:
        charge = json.loads(request.form.get("charge") or "[]")
    except (TypeError, ValueError):
        charge = []
    lignes = lignes_historique(charge[:MAX_IMPORT_MUSCU_SEANCES] if isinstance(charge, list) else [],
                               request.form.get("source") or "")
    # Revérifie les doublons : un double clic ou un retour arrière ne doit
    # pas écrire deux fois la même séance.
    par_seance = {}
    for l in lignes:
        par_seance.setdefault((l["Date"], l["Séance"]), []).append(l)
    try:
        hist = get_hist()
    except Exception:
        hist = []
    connues = {(s["date"], s["seance"]) for s in marquer_doublons(
        [{"date": d, "seance": n} for d, n in par_seance], hist) if s["deja"]}

    # Écrit par paquets de séances entières : un lot qui échoue ne laisse
    # jamais une séance à moitié écrite, que le réimport croirait complète.
    nb_seances = nb_ecrites = 0
    paquet, n_paquet = [], 0
    erreur = ""

    def ecrire():
        nonlocal nb_seances, nb_ecrites, paquet, n_paquet
        if paquet:
            nb_ecrites += ajouter_lignes([l for s in paquet for l in s])
            nb_seances += len(paquet)
        paquet, n_paquet = [], 0

    try:
        for cle, ls in par_seance.items():
            if cle in connues:
                continue
            paquet.append(ls)
            n_paquet += len(ls)
            if n_paquet >= 400:
                ecrire()
        ecrire()
    except Exception as e:
        logger.error("import muscu : écriture interrompue (%s)", e)
        erreur = ("L'import s'est interrompu. Relance-le avec le même fichier : "
                  "les séances déjà entrées seront reconnues et ne seront pas doublées.")
    try:
        from core.analytics import track
        track("import_muscu", {"source": request.form.get("source") or "", "seances": nb_seances})
    except Exception:
        pass
    return render_template("import_muscu.html", active="plus", etape="fini",
                           nb_seances=nb_seances, nb_ecrites=nb_ecrites, erreur=erreur)
