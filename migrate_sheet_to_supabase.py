"""Script one-shot : import du Google Sheet actuel vers Supabase.

À lancer en LOCAL une seule fois. Crée (ou retrouve) l'utilisateur cible via
l'API admin Supabase, puis importe l'historique et le programme depuis le
Google Sheet existant sous son `user_id`.

Prérequis :
  - Variables d'environnement :
      SUPABASE_URL                 = https://<ref>.supabase.co
      SUPABASE_SERVICE_ROLE_KEY    = clé service_role (⚠️ jamais commit)
      GOOGLE_CREDENTIALS           = JSON complet du service account Google
        (ou GCP_* variables, comme en prod, cf. pwa/core/sheets.py)
  - Dépendances : `pip install -r pwa/requirements.txt`

Usage :
  python migrate_sheet_to_supabase.py --email moi@gmail.com
  python migrate_sheet_to_supabase.py --email moi@gmail.com --dry-run

Après la migration, quand tu te connecteras avec Google OAuth (Phase 3) en
utilisant la même adresse email, Supabase reliera automatiquement l'identité
Google au user existant.
"""
from __future__ import annotations

import argparse
import os
import sys

# Permet d'importer core.sheets depuis pwa/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "pwa"))

from supabase import create_client  # noqa: E402
from core.sheets import get_hist, get_prog  # noqa: E402


CHUNK = 500


def _row_to_supabase(user_id: str, r: dict) -> dict:
    date_val = r.get("Date")
    return {
        "user_id": user_id,
        "semaine": int(r.get("Semaine") or 1),
        "seance": r.get("Séance") or "",
        "exercice": r.get("Exercice") or "",
        "serie": int(r.get("Série") or 1),
        "reps": int(r.get("Reps") or 0),
        "poids": float(r.get("Poids") or 0),
        "remarque": r.get("Remarque") or "",
        "muscle": r.get("Muscle") or "",
        "date": date_val if date_val else None,
    }


def _find_or_create_user(admin, email: str) -> str:
    """Retourne l'id du user Supabase pour cette adresse. Le crée si absent."""
    # list_users renvoie une liste paginée ; on cherche dans les 1000 premiers.
    page = 1
    while True:
        users = admin.auth.admin.list_users(page=page, per_page=200)
        if not users:
            break
        for u in users:
            if getattr(u, "email", None) == email:
                return u.id
        if len(users) < 200:
            break
        page += 1

    print(f"[info] user {email} introuvable, création…")
    resp = admin.auth.admin.create_user({
        "email": email,
        "email_confirm": True,
    })
    user = getattr(resp, "user", None) or resp
    return user.id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email du user cible Supabase")
    parser.add_argument("--dry-run", action="store_true", help="N'écrit rien, affiche juste le résumé")
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_key:
        sys.exit("❌ SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY doivent être définis.")

    admin = create_client(url, service_key)

    print(f"→ Cible Supabase : {url}")
    user_id = _find_or_create_user(admin, args.email)
    print(f"→ user_id : {user_id}")

    print("→ Lecture Google Sheet…")
    hist = get_hist()
    prog = get_prog()
    n_seances_prog = len([k for k in prog if not k.startswith("_")])
    print(f"   {len(hist)} lignes d'historique")
    print(f"   {n_seances_prog} séances dans le programme (+ clés méta : {sorted(k for k in prog if k.startswith('_'))})")

    if args.dry_run:
        print("Dry run — rien n'a été écrit dans Supabase.")
        return

    print("→ Purge puis insertion de l'historique dans Supabase…")
    admin.table("history").delete().eq("user_id", user_id).execute()
    if hist:
        payload = [_row_to_supabase(user_id, r) for r in hist]
        for i in range(0, len(payload), CHUNK):
            admin.table("history").insert(payload[i:i + CHUNK]).execute()
            print(f"   insérées : {min(i + CHUNK, len(payload))} / {len(payload)}")

    print("→ Upsert du programme…")
    admin.table("programs").upsert({"user_id": user_id, "data": prog}).execute()

    print("✅ Migration terminée.")


if __name__ == "__main__":
    main()
