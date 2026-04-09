"""Blueprint auth — Google OAuth via Supabase (PKCE côté client + bridge).

Flow :
  1. /login      : rend login.html qui initialise supabase-js (clé anon) et
                   appelle signInWithOAuth({provider:'google', redirectTo:/auth/bridge}).
  2. /auth/bridge: page intermédiaire servie après le retour Google. Le SDK
                   Supabase a déjà échangé le code contre une session dans le
                   localStorage. On récupère cette session en JS et on POST
                   l'access_token à /auth/session.
  3. /auth/session : côté Flask, on vérifie le JWT avec SUPABASE_JWT_SECRET
                     (HS256), on en extrait `sub` (=user_id) et `email`, et on
                     les stocke dans la session Flask (cookie signé).
  4. /logout     : vide la session Flask et redirige vers /login.

Le backend n'utilise jamais le JWT utilisateur pour appeler Supabase : il tape
en service_role avec filtres manuels user_id (cf. core.db). Le JWT sert
uniquement à prouver côté Flask que l'utilisateur est bien qui il dit être.
"""
import os

import jwt
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify

bp = Blueprint("auth", __name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


@bp.route("/login")
def login():
    return render_template(
        "login.html",
        supabase_url=SUPABASE_URL,
        supabase_anon=SUPABASE_ANON_KEY,
    )


@bp.route("/auth/bridge")
def bridge():
    return render_template(
        "bridge.html",
        supabase_url=SUPABASE_URL,
        supabase_anon=SUPABASE_ANON_KEY,
    )


@bp.route("/auth/session", methods=["POST"])
def set_session():
    data = request.get_json(silent=True) or {}
    access_token = data.get("access_token")
    if not access_token:
        return jsonify({"error": "missing access_token"}), 400
    if not SUPABASE_JWT_SECRET:
        return jsonify({"error": "server misconfigured: SUPABASE_JWT_SECRET absent"}), 500
    try:
        payload = jwt.decode(
            access_token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.InvalidTokenError as e:
        return jsonify({"error": f"invalid token: {e}"}), 401

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id:
        return jsonify({"error": "token sans sub"}), 401

    session.clear()
    session["user_id"] = user_id
    session["email"] = email or ""
    session.permanent = True
    return jsonify({"ok": True, "user_id": user_id})


@bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
