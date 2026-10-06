"""Blueprint cardio — saisie d'une séance cardio (chrono + distance + calories + RPE).

Stockage dans la même table `history` que la muscu, avec convention :
  Exercice = "CARDIO:Type"  (ex. "CARDIO:Course")
  Reps     = durée en minutes (int)
  Poids    = distance en km (float, 0 si non applicable)
  Remarque = "FC:145 | Cal:350 | RPE:Modéré"
  Muscle   = "Cardio"
  Série    = 1
"""
import json
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for

from core.data import append_exo_rows, get_hist, get_profile
from core.cardio_duree import lire_duree, reps_de
from core.seance_cardio import UNITES_CARDIO, completer_mesures
from core.strava_import import lire_activites, lire_date, marquer_doublons
from core.analytics import track
from core.dates import today_paris, today_paris_str, continuous_week, DAYS_FR, MONTHS_FR
from core.limiter import limiter

from core.cardio_activites import (  # noqa: F401 — réexportés sous les mêmes noms
    ACTIVITES, ACTIVITES_MAP, INCLINE_MET_BONUS, KM_BASED_ACTIVITES, RPE_LABELS,
    _activity_of, _adjust_met_for_incline, _estimate_calories, sum_cardio_km,
)

logger = logging.getLogger(__name__)

bp = Blueprint("cardio", __name__)


def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _iso_week(d):
    # Index de semaine continu — cf. core.dates.continuous_week.
    return continuous_week(d)


@bp.route("/cardio")
def new():
    date_iso = request.args.get("date") or today_paris_str()
    target = _parse_date(date_iso) or today_paris()
    date_iso = target.strftime("%Y-%m-%d")
    date_label = f"{DAYS_FR[target.weekday()]} {target.day} {MONTHS_FR[target.month-1]}"

    profile = get_profile() or {}
    poids_kg = float(profile.get("poids_kg") or 0)

    # Pré-sélection (ex. depuis un cardio planifié par le générateur IA).
    pre_activite = (request.args.get("activite") or "").strip()
    if pre_activite not in ACTIVITES_MAP:
        pre_activite = ""
    try:
        pre_duree = max(0, min(600, int(request.args.get("duree") or 0)))
    except (TypeError, ValueError):
        pre_duree = 0

    return render_template(
        "cardio.html",
        active="seance",
        date_iso=date_iso,
        date_label=date_label,
        activites=ACTIVITES,
        rpe_labels=RPE_LABELS,
        poids_kg=poids_kg,
        pre_activite=pre_activite,
        pre_duree=pre_duree,
        unites_cardio=UNITES_CARDIO,
    )


@bp.route("/cardio/save", methods=["POST"])
@limiter.limit("20 per minute")
def save():
    f = request.form
    target = _parse_date(f.get("date")) or today_paris()
    date_str = target.strftime("%Y-%m-%d")
    semaine = _iso_week(target)

    activite = (f.get("activite") or "Autre").strip()
    if activite not in ACTIVITES_MAP:
        activite = "Autre"
    _icon, met = ACTIVITES_MAP[activite]

    # Minutes + secondes : le champ secondes manquait (retour du 06/10).
    duree_min = lire_duree(f)
    try:
        distance_km = max(0.0, float((f.get("distance_km") or "0").replace(",", ".")))
    except ValueError:
        distance_km = 0.0
    try:
        vitesse = max(0.0, float((f.get("vitesse") or "0").replace(",", ".")))
    except ValueError:
        vitesse = 0.0
    # Deux valeurs sur trois suffisent : le tapis affiche 10 km/h pendant
    # 30 min, c'est la distance qu'on ignore. Cet écran n'avait même pas de
    # champ vitesse, alors que celui de la séance en a un.
    distance_km, vitesse = completer_mesures(activite, duree_min, distance_km, vitesse)
    try:
        fc_moy = int(float(f.get("fc_moy") or 0))
    except ValueError:
        fc_moy = 0

    rpe = (f.get("rpe") or "").strip()
    if rpe not in RPE_LABELS:
        rpe = ""

    try:
        incline_pct = max(0, min(30, float(f.get("incline") or 0)))
    except (ValueError, TypeError):
        incline_pct = 0
    met = _adjust_met_for_incline(met, activite, incline_pct)

    # Calories : soit saisies, soit estimées
    try:
        cal_saisie = int(float(f.get("calories") or 0))
    except ValueError:
        cal_saisie = 0
    if cal_saisie > 0:
        calories = cal_saisie
    else:
        try:
            poids_kg = float(f.get("poids_kg") or 0)
        except ValueError:
            poids_kg = 0
        calories = _estimate_calories(met, duree_min, poids_kg) if duree_min > 0 else 0

    note = (f.get("note") or "").strip()

    remarque_parts = []
    if fc_moy > 0:
        remarque_parts.append(f"FC:{fc_moy}")
    if calories > 0:
        remarque_parts.append(f"Cal:{calories}")
    if vitesse > 0:
        remarque_parts.append(f"Vit:{vitesse:g}")
    if incline_pct > 0:
        remarque_parts.append(f"Incl:{incline_pct:g}%")
    if rpe:
        remarque_parts.append(f"RPE:{rpe}")
    if note:
        remarque_parts.append(note[:60])
    remarque = " | ".join(remarque_parts)

    exo_final = f"CARDIO:{activite}"
    seance_name = f"Cardio {activite}"

    rows = [{
        "Semaine": semaine,
        "Séance": seance_name,
        "Exercice": exo_final,
        "Série": 1,
        "Reps": reps_de(duree_min),
        "Duree": duree_min,
        "Poids": distance_km,
        "Remarque": remarque,
        "Muscle": "Cardio",
        "Date": date_str,
    }]

    try:
        # AJOUT et non remplacement : deux footings le même jour sont deux
        # séances. `replace_exo_rows` effaçait la première, et elle
        # disparaissait des stats et du calendrier sans un mot.
        append_exo_rows(date_str, seance_name, exo_final, rows)
    except Exception as e:
        logger.error("cardio save FAILED: %s", e)
        return render_template(
            "error.html", code=503,
            message="Impossible de sauvegarder la séance cardio. Réessaie.",
        ), 503

    return redirect(url_for("accueil.index"))

# ── Import de l'export Strava ────────────────────────────────────
# L'API Strava exige un abonnement depuis juin 2026 ; l'export de ses propres
# données reste gratuit. On lit donc le fichier plutôt que d'appeler l'API :
# rien à payer, rien à renouveler, aucun secret à manipuler.

MAX_IMPORT_OCTETS = 8 * 1024 * 1024   # un `activities.csv` de 10 ans ≈ 1 Mo
MAX_IMPORT_SEANCES = 800


@bp.route("/cardio/import")
def import_page():
    return render_template("cardio_import.html", active="seance", etape="depot")


@bp.route("/cardio/import", methods=["POST"])
@limiter.limit("10 per minute")
def import_apercu():
    """Lit le fichier et montre ce qui ENTRERAIT. N'écrit rien.

    Un import qui écrit d'abord et explique ensuite oblige à défaire à la
    main. On montre, l'utilisateur confirme, et alors seulement on écrit.
    """
    fichier = request.files.get("fichier")
    if not fichier or not fichier.filename:
        return render_template("cardio_import.html", active="seance",
                               etape="depot", erreur="Choisis le fichier "
                               "`activities.csv` de ton archive Strava.")
    brut = fichier.read(MAX_IMPORT_OCTETS + 1)
    if len(brut) > MAX_IMPORT_OCTETS:
        return render_template("cardio_import.html", active="seance",
                               etape="depot", erreur="Fichier trop volumineux "
                               "(plus de 8 Mo). Est-ce bien `activities.csv` ?")
    try:
        seances, rapport = lire_activites(brut)
    except Exception as e:
        logger.warning("import Strava illisible : %s", type(e).__name__)
        return render_template("cardio_import.html", active="seance",
                               etape="depot", erreur="Fichier illisible. "
                               "Envoie `activities.csv`, pas l'archive .zip.")
    if not rapport.get("colonnes", {}).get("date"):
        return render_template("cardio_import.html", active="seance",
                               etape="depot", erreur="Ce fichier n'a pas la "
                               "forme d'un `activities.csv` Strava : aucune "
                               "colonne de date reconnue.")

    seances = marquer_doublons(seances, get_hist())
    a_importer = [s for s in seances if not s["deja"]][:MAX_IMPORT_SEANCES]
    return render_template(
        "cardio_import.html", active="seance", etape="apercu",
        seances=seances[:200], a_importer=a_importer, rapport=rapport,
        nb_total=len(seances),
        nb_deja=sum(1 for s in seances if s["deja"]),
        charge=json.dumps(a_importer, ensure_ascii=False),
    )


@bp.route("/cardio/import/confirmer", methods=["POST"])
@limiter.limit("5 per minute")
def import_confirmer():
    """Écrit ce que l'utilisateur vient de voir.

    Le contenu revient par le formulaire : on le REVALIDE entièrement plutôt
    que de lui faire confiance, une ligne trafiquée n'ayant pas à devenir une
    ligne d'historique.
    """
    try:
        proposees = json.loads(request.form.get("charge") or "[]")
    except (TypeError, ValueError):
        proposees = []
    if not isinstance(proposees, list):
        proposees = []

    lignes, ecrites = [], 0
    for s in proposees[:MAX_IMPORT_SEANCES]:
        if not isinstance(s, dict):
            continue
        date = lire_date(s.get("date"))
        activite = s.get("activite") if s.get("activite") in ACTIVITES_MAP else "Autre"
        try:
            duree = max(1, min(1440, int(s.get("duree_min") or 0)))
            km = max(0.0, min(1000.0, float(s.get("distance_km") or 0)))
            cal = max(0, min(30000, int(s.get("calories") or 0)))
        except (TypeError, ValueError):
            continue
        if date is None:
            continue
        date_str = date.strftime("%Y-%m-%d")
        km, vitesse = completer_mesures(activite, duree, km, 0)
        parts = ["Import Strava"]
        if cal > 0:
            parts.insert(0, f"Cal:{cal}")
        if vitesse > 0:
            parts.insert(-1, f"Vit:{vitesse:g}")
        lignes.append({
            "Semaine": continuous_week(date), "Séance": f"Cardio {activite}",
            "Exercice": f"CARDIO:{activite}", "Série": 1, "Reps": duree,
            "Poids": km, "Remarque": " | ".join(parts), "Muscle": "Cardio",
            "Date": date_str,
        })

    # Une séance à la fois : `append_exo_rows` numérote les séries par
    # (date, séance, exercice), donc deux footings du même jour cohabitent.
    for l in lignes:
        try:
            append_exo_rows(l["Date"], l["Séance"], l["Exercice"], [l])
            ecrites += 1
        except Exception as e:
            logger.error("import Strava : ligne %s perdue (%s)", l["Date"],
                         type(e).__name__)
    try:
        track("strava_import", {"seances": ecrites})
    except Exception:
        pass
    return render_template("cardio_import.html", active="seance",
                           etape="fini", nb_ecrites=ecrites,
                           nb_proposees=len(lignes))
