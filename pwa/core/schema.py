"""Les colonnes que le code attend en base, et leur contrôle au démarrage.

Audit du 06/10 (C1) : la migration v29 (`profiles.vip_until`, `referral_code`,
`referred_by`) n'avait jamais été appliquée en production. Pendant des mois,
l'essai PRO et le parrainage n'ont pas existé, alors que l'onglet Plus les
promettait. Rien ne l'a signalé : chaque lecture d'une colonne absente était
journalisée puis ignorée, et la fausse base des tests acceptait n'importe quel
nom de colonne.

Ce module ferme les deux trous :

* `ATTENDU` est le schéma que le code suppose (relevé en production le 09/10,
  v29 comprise). La fausse base des tests le fait respecter
  (`tests/conftest.py`) et `tests/test_schema.py` vérifie que chaque colonne
  ajoutée par une migration du dépôt y figure.
* `verifier()` interroge la vraie base au démarrage (une requête par table,
  davantage seulement s'il manque quelque chose) ; un manque est journalisé en
  ERREUR et affiché sur /admin, au lieu de désactiver une fonction en silence.
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)

# Une nouvelle migration qui ajoute une colonne l'ajoute ICI aussi
# (tests/test_schema.py le vérifie).
ATTENDU = {
    "history": (
        "id", "user_id", "semaine", "seance", "exercice", "serie", "reps", "poids",
        "remarque", "muscle", "date", "created_at",
        "session_id", "rpe",                                   # v34
        "exercise_id",                                         # v42
        "type_serie",                                          # v43
        "duree_min", "distance", "calories", "vitesse",        # v44
    ),
    "programs": ("user_id", "data", "updated_at", "version"),  # version : v32
    "profiles": (
        "id", "created_at", "display_name", "niveau", "objectif", "frequence",
        "equipement", "morphologie", "onboarding_done", "prenom",
        "poids_kg", "taille_cm", "age", "sexe", "activite", "objectif_nutrition",
        "tdee", "calories_cible",                              # v23
        "tier", "coach_quota_date", "coach_quota_count",       # v24
        "stripe_customer_id",                                  # v27
        "referral_code", "referred_by", "vip_until",           # v29
        "newsletter_opt_in", "newsletter_opt_in_at", "newsletter_email",  # v31
        "coach_memory",                                        # v36
    ),
    "onboarding": ("user_id", "prenom", "age", "sexe", "niveau", "frequence",
                   "objectif", "equipement", "completed_at"),
    "nutrition": ("id", "user_id", "date", "meal_type", "calories", "protein",
                  "carbs", "fat", "note", "created_at",
                  "grams", "food"),                            # v40
    "coach_messages": ("id", "user_id", "role", "content", "created_at",
                       "conversation_id"),                     # v26
    "coach_conversations": ("id", "user_id", "title", "created_at", "updated_at"),
    "events": ("id", "user_id", "event", "props", "tier", "created_at"),
    "push_subscriptions": ("id", "user_id", "endpoint", "p256dh", "auth", "created_at",
                           "last_reactivation_at", "reactivation_count"),  # v34
    "body_weight": ("id", "user_id", "date", "poids_kg", "created_at"),
    "session_notes": ("id", "user_id", "date", "seance", "rating", "comment",
                      "created_at", "updated_at", "duration_min"),  # v35
    "reglages": ("user_id", "auto_rest_timer", "auto_prefill_weight", "show_rpe",
                 "show_overload_hint", "notifications", "reminder_hour",
                 "recap_hebdo", "updated_at"),                 # v45
    "calques_seance": ("user_id", "seance", "date", "extras", "brouillon",
                       "substituts", "ordre", "updated_at"),   # v46
    "etat_compte": ("user_id", "badges", "record_serie", "defis_faits", "defis_gagnes",
                    "upsell_vu", "debrief_gratuit", "decharge_semaine",
                    "decharge_ignoree", "plats_semaine", "nutrition_perso",
                    "updated_at"),                             # v47
    # Vues (lecture seule, côté serveur)
    "user_last_activity": ("user_id", "last_date"),            # v37, v44
    "admin_history_stats": ("total_rows", "total_tonnage", "total_seances",
                            "active_7d", "active_30d"),        # v39, v44
}

REVERIFIER_APRES = 600.0   # /admin relance le contrôle au-delà (secondes)

_etat = {"verifie": False, "absentes": {}, "inconnues": [], "quand": 0.0}
_verrou = threading.Lock()


def _code_erreur(e) -> str:
    texte = str(e)
    for code in ("42703", "PGRST204", "42P01", "PGRST205"):
        if code in texte:
            return code
    if "does not exist" in texte:
        return "42703"
    return ""


def verifier(client) -> dict:
    """Compare la base à `ATTENDU`. Rend {"absentes": {table: [colonnes]},
    "inconnues": [tables qu'on n'a pas pu interroger]}.

    Une table manquante est notée `["(table)"]`. Une erreur qui n'est pas un
    nom inconnu (réseau, délai) ne compte pas comme un manque : la table passe
    en « inconnue », pour ne pas crier à la migration oubliée sur une panne."""
    absentes, inconnues = {}, []
    for table, colonnes in ATTENDU.items():
        try:
            client.table(table).select(",".join(colonnes)).limit(1).execute()
            continue
        except Exception as e:
            code = _code_erreur(e)
            if code in ("42P01", "PGRST205"):
                absentes[table] = ["(table)"]
                continue
            if not code:
                inconnues.append(table)
                continue
        manquent = []
        for c in colonnes:
            try:
                client.table(table).select(c).limit(1).execute()
            except Exception as e:
                if _code_erreur(e):
                    manquent.append(c)
        if manquent:
            absentes[table] = manquent
    return {"absentes": absentes, "inconnues": inconnues}


def _texte(absentes: dict) -> str:
    return ", ".join(f"{t}.{c}" if c != "(table)" else f"table {t}"
                     for t, cols in sorted(absentes.items()) for c in cols)


def enregistrer(resultat: dict) -> dict:
    with _verrou:
        _etat.update(verifie=True, quand=time.time(),
                     absentes=dict(resultat.get("absentes") or {}),
                     inconnues=list(resultat.get("inconnues") or []))
    if _etat["absentes"]:
        logger.error("schéma : colonnes absentes en base — %s. Migration oubliée : "
                     "les fonctions qui en dépendent ne marchent pas.", _texte(_etat["absentes"]))
    elif _etat["inconnues"]:
        logger.warning("schéma : contrôle incomplet, tables injoignables : %s",
                       ", ".join(_etat["inconnues"]))
    else:
        logger.info("schéma : %d tables et vues vérifiées, rien ne manque", len(ATTENDU))
    return etat()


def etat() -> dict:
    """{"verifie", "absentes", "alerte"} — affiché sur /admin."""
    with _verrou:
        absentes = dict(_etat["absentes"])
        verifie = _etat["verifie"]
    alerte = ""
    if absentes:
        alerte = ("Colonnes absentes en base : " + _texte(absentes) +
                  ". Une migration n'a pas été appliquée ; les fonctions qui en "
                  "dépendent ne marchent pas.")
    return {"verifie": verifie, "absentes": absentes, "alerte": alerte}


def verifier_et_enregistrer(get_client) -> dict:
    """Contrôle complet, sans jamais lever : l'app doit démarrer quoi qu'il arrive."""
    try:
        client = get_client()
    except Exception as e:
        logger.info("schéma : pas de base configurée, contrôle ignoré (%s)", type(e).__name__)
        return etat()
    try:
        return enregistrer(verifier(client))
    except Exception as e:  # pragma: no cover - filet
        logger.warning("schéma : contrôle impossible (%s)", type(e).__name__)
        return etat()


def verifier_au_demarrage(get_client) -> threading.Thread:
    """Lance le contrôle en tâche de fond : ~17 requêtes, le démarrage n'attend pas."""
    t = threading.Thread(target=verifier_et_enregistrer, args=(get_client,),
                         name="controle-schema", daemon=True)
    t.start()
    return t


def etat_a_jour(get_client) -> dict:
    """Pour /admin : relance le contrôle s'il date de plus de REVERIFIER_APRES,
    pour qu'une migration appliquée depuis le démarrage efface l'alerte."""
    with _verrou:
        vieux = (time.time() - _etat["quand"]) > REVERIFIER_APRES
    if vieux:
        return verifier_et_enregistrer(get_client)
    return etat()


def reinitialiser() -> None:
    """Tests."""
    with _verrou:
        _etat.update(verifie=False, absentes={}, inconnues=[], quand=0.0)
