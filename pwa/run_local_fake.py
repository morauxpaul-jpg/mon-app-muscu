"""Lance l'app en local sur une FAUSSE base (aucun accès Supabase).

Usage : cd pwa && python run_local_fake.py  → http://127.0.0.1:5123/test-login
Sert uniquement au debug manuel des flows UI (onboarding, séance…).
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

# Stub supabase avant l'import de core.db (paquet local cassé / pas de creds)
stub = types.ModuleType("supabase")
stub.Client = type("Client", (), {})
stub.create_client = lambda url, key: (_ for _ in ()).throw(RuntimeError("no db"))
sys.modules.setdefault("supabase", stub)

from conftest import FakeSupabase, USER_ID  # noqa: E402

import core.db as core_db  # noqa: E402
core_db.use_client(FakeSupabase())

import os  # noqa: E402

if os.environ.get("FAUX_IA") == "lent":
    # IA simulée (tests navigateur du générateur) : répond un programme valide
    # au bout de 3 s, assez pour que la page passe par le suivi de tâche.
    import json as _json
    import time as _time
    _PROG = _json.dumps({"name": "Programme de test", "seances": {"Haut du corps": [
        {"name": "Développé couché", "sets": 4, "reps": "6-8", "rest_seconds": 150, "muscle": "Pecs"}]},
        "planning": {"Lundi": "Haut du corps"}})

    class _FauxClient:
        def __init__(self, **k):
            self.messages = types.SimpleNamespace(create=self._create)

        def _create(self, **k):
            _time.sleep(3)
            return types.SimpleNamespace(content=[types.SimpleNamespace(text=_PROG)])

    sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=_FauxClient)
    os.environ.setdefault("ANTHROPIC_API_KEY", "cle-factice")

import app as appmod  # noqa: E402
from flask import session, redirect, request  # noqa: E402
from core.limiter import limiter  # noqa: E402

# Tests navigateur : toutes les pages viennent de 127.0.0.1, et la limite de
# 60 requêtes par minute et par adresse finissait par répondre 429 au milieu
# de la suite (une page de séance sans « Série faite »). Coupée à la demande.
if os.environ.get("SANS_LIMITE") == "1":
    limiter.enabled = False

# L'auth gate tourne avant la route : /test-login doit être public.
appmod._PUBLIC_PATHS.add("/test-login")
appmod._PUBLIC_PATHS.add("/test-seed")
appmod._PUBLIC_PATHS.add("/test-vierge")
appmod._PUBLIC_PATHS.add("/test-historique")
appmod._PUBLIC_PATHS.add("/test-programme")
appmod._PUBLIC_PATHS.add("/test-nutrition")


@appmod.app.route("/test-login")
def test_login():
    import time
    session.clear()
    session["user_id"] = USER_ID
    session["email"] = "test@example.com"
    session["is_vip"] = (request.args.get("vip") == "1")
    session["is_vip_full"] = session["is_vip"]      # PRO payant (générateur, coach)
    session["is_vip_ts"] = time.time()
    if request.args.get("essai") == "1":
        # Essai PRO de 20 h (parrainage) : profil free + vip_until, statut
        # relu en base par le before_request.
        import datetime as dt
        fin = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=20)).isoformat()
        c = core_db.current_client()
        c.tables["profiles"] = [p for p in c.tables.get("profiles", []) if p.get("id") != USER_ID]
        c.table("profiles").insert({"id": USER_ID, "tier": "free", "vip_until": fin}).execute()
        session.pop("is_vip", None)
        session.pop("is_vip_full", None)
    session["onboarded"] = (request.args.get("onb") != "0")
    session.permanent = True
    return redirect(request.args.get("to") or "/accueil")


@appmod.app.route("/test-seed")
def test_seed():
    """Remplit la fausse base de données réalistes (pour captures marketing)."""
    import datetime as dt
    from flask import jsonify
    c = core_db.current_client()
    c.tables.clear()
    c._id = 0
    core_db.vider_cache()  # purge le cache (hist/prog d'une visite vide précédente)
    core_db._prog_base.clear()

    today = dt.date(2026, 6, 12)
    monday0 = today - dt.timedelta(days=today.weekday())  # lundi de cette semaine

    # Profil VIP complet (prénom neutre pour les captures marketing)
    c.table("profiles").insert({
        "id": USER_ID, "tier": "vip", "prenom": "Alex",
        "poids_kg": 78, "taille_cm": 180, "age": 25, "sexe": "H",
        "activite": "actif", "objectif_nutrition": "masse",
        "tdee": 2550, "calories_cible": 2950,
    }).execute()

    # Onboarding
    c.table("onboarding").insert({
        "user_id": USER_ID, "prenom": "Alex", "age": 25, "sexe": "H",
        "niveau": "intermédiaire", "frequence": 3, "objectif": "prise de masse",
        "equipement": "salle", "completed_at": (monday0 - dt.timedelta(weeks=6)).isoformat(),
    }).execute()

    # Programme PPL
    prog = {
        "Push": [
            {"name": "Développé couché", "sets": 4, "muscle": "Pecs"},
            {"name": "Développé militaire", "sets": 3, "muscle": "Épaules"},
            {"name": "Dips", "sets": 3, "muscle": "Triceps"},
        ],
        "Pull": [
            {"name": "Tractions", "sets": 4, "muscle": "Dos"},
            {"name": "Rowing barre", "sets": 3, "muscle": "Dos"},
            {"name": "Curl biceps", "sets": 3, "muscle": "Biceps"},
        ],
        "Legs": [
            {"name": "Squat", "sets": 4, "muscle": "Quadriceps"},
            {"name": "Soulevé de terre", "sets": 3, "muscle": "Ischio-jambiers"},
            {"name": "Mollets debout", "sets": 3, "muscle": "Mollets"},
        ],
        "_planning": {"Lundi": "Push", "Mardi": "", "Mercredi": "Pull",
                      "Jeudi": "", "Vendredi": "Legs", "Samedi": "", "Dimanche": ""},
        "_name": "PPL Intermédiaire",
        "_started_at": (monday0 - dt.timedelta(weeks=6)).isoformat(),
        "_streak_record": 6,
        "_settings": {},
        "_badges": ["first_session", "regulier", "tonnage_10k", "tonnage_50k", "costaud"],
    }
    c.table("programs").insert({"user_id": USER_ID, "data": prog}).execute()

    # Historique : 6 semaines, Push/Pull/Legs (lun/mer/ven), surcharge progressive
    base = {
        "Développé couché": (70, "Pecs"), "Développé militaire": (40, "Épaules"),
        "Dips": (0, "Triceps"),
        "Tractions": (0, "Dos"), "Rowing barre": (60, "Dos"), "Curl biceps": (14, "Biceps"),
        "Squat": (90, "Quadriceps"), "Soulevé de terre": (110, "Ischio-jambiers"),
        "Mollets debout": (80, "Mollets"),
    }
    sessions = {0: ("Push", ["Développé couché", "Développé militaire", "Dips"]),
                2: ("Pull", ["Tractions", "Rowing barre", "Curl biceps"]),
                4: ("Legs", ["Squat", "Soulevé de terre", "Mollets debout"])}
    rows = []
    for w in range(6):  # semaines passées 0..5 (5 = semaine courante)
        wk_monday = monday0 - dt.timedelta(weeks=(5 - w))
        for dow, (seance, exos) in sessions.items():
            d = wk_monday + dt.timedelta(days=dow)
            if d > today:
                continue
            for exo in exos:
                start_w, muscle = base[exo]
                for s in range(1, 4):
                    poids = start_w + w * 2.5 if start_w > 0 else 0
                    reps = 10 - s + (1 if exo == "Dips" else 0)
                    rows.append({
                        "user_id": USER_ID, "semaine": 1, "seance": seance,
                        "exercice": exo, "serie": s, "reps": max(5, reps),
                        "poids": poids if exo not in ("Dips", "Tractions") else 0,
                        "remarque": "", "muscle": muscle, "date": d.isoformat(),
                    })
    for r in rows:
        c.table("history").insert(r).execute()

    # Nutrition du jour
    for mt, cal, p, gl, li, note in [
        ("petit_dej", 620, 35, 70, 18, "Flocons + whey + banane"),
        ("dejeuner", 880, 55, 90, 28, "Poulet riz légumes"),
        ("collation", 410, 30, 45, 12, "Skyr + fruits secs"),
        ("diner", 760, 48, 70, 26, "Saumon patate douce"),
    ]:
        c.table("nutrition").insert({
            "user_id": USER_ID, "date": today.isoformat(), "meal_type": mt,
            "calories": cal, "protein": p, "carbs": gl, "fat": li, "note": note,
        }).execute()

    # Coach IA : une conversation avec un échange
    c.table("coach_conversations").insert({
        "user_id": USER_ID, "title": "Progresser au développé couché",
        "updated_at": today.isoformat(),
    }).execute()
    conv = c.tables["coach_conversations"][-1]["id"]
    msgs = [
        ("user", "Je stagne à 80 kg au développé couché, comment progresser ?"),
        ("assistant", "Bravo pour ta régularité 💪 Tu es à **80 kg × 8**, c'est déjà solide.\n\n"
                      "3 leviers concrets :\n\n"
                      "- **Surcharge progressive** : vise +2,5 kg toutes les 2 semaines, quitte à baisser à 6 reps.\n"
                      "- **Volume** : ajoute une 4ᵉ série lourde, ou un travail aux haltères en finition.\n"
                      "- **Récup** : 48 h entre deux séances pecs + 7-8 h de sommeil.\n\n"
                      "Ton apport actuel (~2950 kcal, 168 g de protéines) soutient bien la prise. Continue comme ça !"),
    ]
    for role, content in msgs:
        c.table("coach_messages").insert({
            "user_id": USER_ID, "role": role, "content": content,
            "conversation_id": str(conv), "created_at": today.isoformat(),
        }).execute()

    import time
    session.clear()
    session["user_id"] = USER_ID
    session["email"] = "alex@example.com"
    session["is_vip"] = True
    session["is_vip_full"] = True
    session["is_vip_ts"] = time.time()
    session["onboarded"] = True
    session.permanent = True
    return jsonify({"ok": True, "conversation_id": conv, "history_rows": len(rows)})


# Requêtes en cours (hors /test-*). Un test qui se termine peut laisser une
# sauvegarde en route : si /test-vierge vidait la base avant qu'elle aboutisse,
# elle atterrirait dans le décor du test SUIVANT (série 1 déjà « faite », son
# bouton masqué — échec de la CI du 04/10). /test-vierge attend donc qu'elles
# soient finies. E2E_LATENCE (secondes) ralentit chaque requête, comme un
# runner de CI chargé, pour rejouer ces courses à volonté.
import threading  # noqa: E402
_EN_COURS = [0]
_VERROU = threading.Lock()
_LATENCE = float(os.environ.get("E2E_LATENCE") or 0)


def _debut_requete():
    from flask import g
    if request.path.startswith(("/test-", "/static")):
        return
    with _VERROU:
        _EN_COURS[0] += 1
    g.e2e_suivie = True
    if _LATENCE:
        import time
        time.sleep(_LATENCE)


# En tête de chaîne : les before_request de l'app (auth, onboarding) peuvent
# répondre eux-mêmes, et ceux placés après ne tournent alors pas.
appmod.app.before_request_funcs.setdefault(None, []).insert(0, _debut_requete)


@appmod.app.teardown_request
def _fin_requete(_exc):
    from flask import g
    if g.pop("e2e_suivie", False):
        with _VERROU:
            _EN_COURS[0] -= 1


@appmod.app.route("/test-vierge")
@limiter.exempt
def test_vierge():
    """Compte neuf avec un programme « Push » de deux exercices, sans
    historique : le décor des tests navigateur (tests/e2e/)."""
    import time
    from flask import jsonify
    fin = time.time() + 10
    while _EN_COURS[0] > 0 and time.time() < fin:
        time.sleep(0.05)
    c = core_db.current_client()
    c.tables.clear()
    c._id = 0
    core_db.vider_cache()
    core_db._prog_base.clear()
    c.table("profiles").insert({"id": USER_ID, "tier": "free", "prenom": "Alex"}).execute()
    c.table("onboarding").insert({"user_id": USER_ID, "completed_at": "2026-01-01"}).execute()
    c.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [
            {"name": "Développé couché", "sets": 3, "muscle": "Pecs", "reps": "5", "rest": 120,
             **({"superset": True} if request.args.get("ss") else {})},
            {"name": "Développé militaire", "sets": 2, "muscle": "Épaules"},
        ],
        "_planning": {j: "Push" for j in ("Lundi", "Mardi", "Mercredi", "Jeudi",
                                          "Vendredi", "Samedi", "Dimanche")},
        "_settings": {},
        **({"Pull": [{"name": "Rowing barre", "sets": 3, "muscle": "Dos"}]}
           if request.args.get("ab") else {}),
    }}).execute()
    session.clear()
    session["user_id"] = USER_ID
    session["email"] = "test@example.com"
    session["is_vip"] = False
    session["is_vip_full"] = False
    session["is_vip_ts"] = time.time()
    session["onboarded"] = True
    return jsonify({"ok": True})


@appmod.app.route("/test-historique")
@limiter.exempt
def test_historique():
    """Lignes d'historique telles qu'en base (fausse), pour les assertions."""
    from flask import jsonify
    c = core_db.current_client()
    return jsonify(c.tables.get("history", []))


@appmod.app.route("/test-nutrition")
@limiter.exempt
def test_nutrition():
    """Lignes de la table nutrition (fausse base), pour les assertions."""
    from flask import jsonify
    c = core_db.current_client()
    return jsonify(c.tables.get("nutrition", []))


@appmod.app.route("/test-programme")
@limiter.exempt
def test_programme():
    """Blob du programme tel qu'en base (fausse), pour les assertions."""
    from flask import jsonify
    rows = core_db.current_client().tables.get("programs", [])
    return jsonify(rows[0]["data"] if rows else {})


if __name__ == "__main__":
    import os
    appmod.app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5123")), debug=False)
