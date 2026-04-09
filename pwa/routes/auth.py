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


def _env(name: str) -> str:
    """Lit une env var et nettoie espaces + quotes parasites (Railway copie
    parfois des valeurs entourées de guillemets)."""
    v = os.getenv(name, "") or ""
    v = v.strip().strip('"').strip("'").lstrip("=").strip()
    return v


def _public_config() -> dict:
    url = _env("SUPABASE_URL")
    anon = _env("SUPABASE_ANON_KEY")
    if not url or not anon:
        print(f"[auth] ⚠️ config manquante : SUPABASE_URL={'OK' if url else 'VIDE'} "
              f"SUPABASE_ANON_KEY={'OK' if anon else 'VIDE'}", flush=True)
    return {"supabase_url": url, "supabase_anon": anon}


@bp.route("/login")
def login():
    return render_template("login.html", **_public_config())


@bp.route("/auth/bridge")
def bridge():
    return render_template("bridge.html", **_public_config())


@bp.route("/auth/session", methods=["POST"])
def set_session():
    data = request.get_json(silent=True) or {}
    access_token = data.get("access_token")
    if not access_token:
        return jsonify({"error": "missing access_token"}), 400
    jwt_secret = _env("SUPABASE_JWT_SECRET")
    if not jwt_secret:
        return jsonify({"error": "server misconfigured: SUPABASE_JWT_SECRET absent"}), 500
    try:
        payload = jwt.decode(
            access_token,
            jwt_secret,
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


@bp.route("/auth/debug")
def debug_env():
    """Route temporaire : montre si les env vars sont bien lues côté serveur.
    Ne révèle PAS les valeurs, uniquement présence + longueur + préfixe URL."""
    url = _env("SUPABASE_URL")
    anon = _env("SUPABASE_ANON_KEY")
    jwt_s = _env("SUPABASE_JWT_SECRET")
    svc = _env("SUPABASE_SERVICE_ROLE_KEY")
    fsk = _env("FLASK_SECRET_KEY")
    return jsonify({
        "SUPABASE_URL_present": bool(url),
        "SUPABASE_URL_prefix": url[:30] if url else "",
        "SUPABASE_URL_len": len(url),
        "SUPABASE_ANON_KEY_present": bool(anon),
        "SUPABASE_ANON_KEY_len": len(anon),
        "SUPABASE_JWT_SECRET_present": bool(jwt_s),
        "SUPABASE_JWT_SECRET_len": len(jwt_s),
        "SUPABASE_SERVICE_ROLE_KEY_present": bool(svc),
        "SUPABASE_SERVICE_ROLE_KEY_len": len(svc),
        "FLASK_SECRET_KEY_present": bool(fsk),
    })
