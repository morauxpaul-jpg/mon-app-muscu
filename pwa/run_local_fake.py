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
core_db._client = FakeSupabase()

import app as appmod  # noqa: E402
from flask import session, redirect, request  # noqa: E402

# L'auth gate tourne avant la route : /test-login doit être public.
appmod._PUBLIC_PATHS.add("/test-login")
appmod._PUBLIC_PATHS.add("/test-seed")


@appmod.app.route("/test-login")
def test_login():
    import time
    session.clear()
    session["user_id"] = USER_ID
    session["email"] = "test@example.com"
    session["is_vip"] = (request.args.get("vip") == "1")
    session["is_vip_ts"] = time.time()
    session["onboarded"] = (request.args.get("onb") != "0")
    session.permanent = True
    return redirect(request.args.get("to") or "/accueil")


@appmod.app.route("/test-seed")
def test_seed():
    """Remplit la fausse base de données réalistes (pour captures marketing)."""
    import datetime as dt
    from flask import jsonify
    c = core_db._client
    c.tables.clear()
    c._id = 0
    core_db._data_cache.clear()  # purge le cache (hist/prog d'une visite vide précédente)

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


if __name__ == "__main__":
    appmod.app.run(host="127.0.0.1", port=5123, debug=False)
