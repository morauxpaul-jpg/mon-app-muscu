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


if __name__ == "__main__":
    appmod.app.run(host="127.0.0.1", port=5123, debug=False)
