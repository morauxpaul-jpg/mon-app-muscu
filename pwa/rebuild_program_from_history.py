"""Reconstruit programs.data depuis history pour un user donné.

Usage :
  python rebuild_program_from_history.py --email toi@gmail.com           # dry-run, affiche
  python rebuild_program_from_history.py --email toi@gmail.com --apply   # écrit dans programs

Logique :
  - Lit toutes les rows history de l'user (hors "SESSION").
  - Groupe par Séance → dédoublonne par Exercice.
  - Pour chaque exo : sets = max(Série) jamais vu, muscle = le plus fréquent.
  - Construit un dict {seance: [exos...]} compatible programs.data.
  - Ajoute un _planning vide (à reconfigurer côté UI Programme/Gestion).
"""
import argparse
import json
import sys
from collections import Counter, defaultdict

from core import db as core_db


def find_user_id_by_email(email: str) -> str | None:
    client = core_db.get_client()
    # Pagine la liste des users auth pour trouver l'email
    page = 1
    while True:
        res = client.auth.admin.list_users(page=page, per_page=200)
        users = res if isinstance(res, list) else getattr(res, "users", []) or []
        if not users:
            return None
        for u in users:
            u_email = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else None)
            u_id = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
            if u_email and u_email.lower() == email.lower():
                return u_id
        if len(users) < 200:
            return None
        page += 1


def rebuild(user_id: str) -> dict:
    hist = core_db.get_hist(user_id)
    # Filtre les marqueurs de séance manquée
    rows = [r for r in hist if (r.get("Exercice") or "") and r["Exercice"] != "SESSION"]

    by_seance: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        s = r.get("Séance") or ""
        ex = r.get("Exercice") or ""
        if not s or not ex:
            continue
        slot = by_seance[s].setdefault(ex, {
            "max_serie": 0,
            "muscles": Counter(),
            "first_seen": (r.get("Semaine"), r.get("Date")),
        })
        try:
            slot["max_serie"] = max(slot["max_serie"], int(r.get("Série") or 1))
        except (TypeError, ValueError):
            pass
        m = (r.get("Muscle") or "").strip()
        if m:
            slot["muscles"][m] += 1

    prog: dict = {}
    for seance, exos in by_seance.items():
        # Ordre stable : premier vu en premier (par semaine puis date)
        ordered = sorted(exos.items(), key=lambda kv: (kv[1]["first_seen"] or (0, "")))
        prog[seance] = [
            {
                "name": name,
                "sets": int(slot["max_serie"] or 3),
                "muscle": (slot["muscles"].most_common(1)[0][0] if slot["muscles"] else "Autre"),
            }
            for name, slot in ordered
        ]

    # Planning vide — l'utilisateur le reconfigurera dans /programme
    from core.dates import DAYS_FR
    prog["_planning"] = {d: "" for d in DAYS_FR}
    prog["_origin"] = "rebuilt_from_history"
    return prog


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=False)
    ap.add_argument("--user-id", required=False)
    ap.add_argument("--apply", action="store_true", help="Écrire dans programs (sinon dry-run)")
    args = ap.parse_args()

    if args.user_id:
        user_id = args.user_id
    elif args.email:
        user_id = find_user_id_by_email(args.email)
        if not user_id:
            print(f"❌ Aucun user trouvé pour {args.email}")
            sys.exit(1)
    else:
        ap.error("--email ou --user-id requis")

    print(f"→ user_id : {user_id}")
    prog = rebuild(user_id)

    # Affichage lisible
    print("\n=== Programme reconstruit ===")
    for seance, exos in prog.items():
        if seance.startswith("_"):
            continue
        print(f"\n[{seance}]")
        for e in exos:
            print(f"  - {e['name']}  ({e['sets']} séries, {e['muscle']})")
    print("\n=== JSON brut ===")
    print(json.dumps(prog, ensure_ascii=False, indent=2))

    if args.apply:
        existing = core_db.get_prog(user_id)
        if existing and any(k for k in existing if not k.startswith("_")):
            print("\n⚠️  Un programme existe déjà — refuse d'écraser. Vide-le d'abord ou retire ce garde-fou.")
            sys.exit(2)
        core_db.save_prog(user_id, prog)
        print("\n✅ Écrit dans programs.")
    else:
        print("\n(dry-run — relance avec --apply pour écrire)")


if __name__ == "__main__":
    main()
