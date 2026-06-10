"""Muscu Tracker PRO — version PWA (Flask).

Phase 3 : multi-user via Supabase. L'authentification est gérée par
routes/auth.py (Google OAuth + bridge), et un `before_request` global
bloque l'accès aux pages protégées tant que la session Flask n'a pas de
`user_id`. Les routes lisent leurs données via `core.data` qui reprend
ce `user_id` dans `flask.g`.
"""
import logging
import os
import secrets
import time
from datetime import timedelta

from flask import Flask, render_template, send_from_directory, session, g, redirect, url_for, request, abort

from core.limiter import limiter

from routes.accueil import bp as accueil_bp
from routes.seance import bp as seance_bp
from routes.programme import bp as programme_bp
from routes.progres import bp as progres_bp
from routes.gestion import bp as gestion_bp
from routes.auth import bp as auth_bp
from routes.onboarding import bp as onboarding_bp
from routes.arcade import bp as arcade_bp
from routes.cardio import bp as cardio_bp
from routes.nutrition import bp as nutrition_bp
from routes.coach import bp as coach_bp
from routes.premium import bp as premium_bp
from routes.admin import bp as admin_bp

from core import db as core_db

# Logging structuré — remplace print() un peu partout dans le code.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# Monitoring d'erreurs (Sentry) — actif uniquement si SENTRY_DSN est défini.
# Sans la variable, zéro impact. send_default_pii=False : jamais d'emails ni
# de cookies dans les rapports.
_sentry_dsn = (os.getenv("SENTRY_DSN") or "").strip()
if _sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=_sentry_dsn, traces_sample_rate=0, send_default_pii=False)
        logger.info("Sentry actif (monitoring erreurs)")
    except Exception as _e:  # sdk absent ou DSN invalide : on boot quand même
        logger.error("Sentry init FAILED: %s", _e)

app = Flask(__name__, static_folder="static", template_folder="templates")

# Rate limiter global — protège les routes POST contre les clics compulsifs.
# default_limits s'applique à toutes les routes ; sur-limite ajoutée avec
# @limiter.limit(...) pour les actions sensibles dans les blueprints.
limiter.init_app(app)
# Trace au boot le backend du rate-limiter : "redis" = partagé entre workers
# et persistant ; "memory" = par worker, remis à zéro à chaque déploiement.
from core.limiter import _storage_uri as _rl_storage  # noqa: E402
logger.info(
    "Rate limiter backend: %s",
    "redis (partagé)" if str(_rl_storage).startswith(("redis://", "rediss://")) else "memory (par worker)",
)

# Secret_key : obligatoire pour signer le cookie de session Flask. Doit être
# défini en prod via la variable d'env FLASK_SECRET_KEY sur Railway.
_flask_secret = os.getenv("FLASK_SECRET_KEY")
if not _flask_secret:
    # En prod (2 workers gunicorn) une clé éphémère différente par worker
    # casse les sessions de façon aléatoire. On log fort sans empêcher le
    # boot (utile en dev local).
    logger.critical(
        "FLASK_SECRET_KEY absente — sessions instables en prod multi-worker. "
        "Définis-la dans les variables d'environnement Railway."
    )
app.secret_key = _flask_secret or "dev-insecure-change-me"
app.permanent_session_lifetime = timedelta(days=30)
# Revalidation du tier VIP depuis la base (cf. before_request). Court pour
# propager rapidement un passage VIP fait par l'admin, sans marteler la DB.
VIP_CACHE_TTL = 120  # secondes
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.getenv("FLASK_SECRET_KEY")),  # HTTPS-only en prod
    # Taille max d'une requête (uploads import JSON inclus) — évite qu'un
    # fichier énorme sature la mémoire du worker gunicorn.
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 5 Mo
)

app.register_blueprint(auth_bp)
app.register_blueprint(accueil_bp)
app.register_blueprint(seance_bp)
app.register_blueprint(programme_bp)
app.register_blueprint(progres_bp)
app.register_blueprint(gestion_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(arcade_bp)
app.register_blueprint(cardio_bp)
app.register_blueprint(nutrition_bp)
app.register_blueprint(coach_bp)
app.register_blueprint(premium_bp)
app.register_blueprint(admin_bp)


# ────────────────────────────────────────────────────────────────
# Auth gate — toutes les routes sauf celles listées nécessitent user_id
# ────────────────────────────────────────────────────────────────
# /faq et /confidentialite sont publics : les stores (Play/App Store) exigent
# une URL de politique de confidentialité consultable sans compte.
_PUBLIC_PATHS = {"/", "/login", "/auth/bridge", "/auth/session", "/auth/debug", "/manifest.json", "/service-worker.js", "/faq", "/confidentialite", "/.well-known/assetlinks.json"}


@app.before_request
def _require_login():
    path = request.path or "/"
    if path.startswith("/static/"):
        return None
    if path in _PUBLIC_PATHS:
        return None
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("landing"))
    g.user_id = user_id
    g.email = session.get("email", "")

    # Phase 5 : statut VIP disponible partout via g.is_vip. Lu depuis
    # profiles.tier ∈ {'free','vip'}. Mis en cache session avec un TTL court :
    # la session est un cookie 30 j, donc sans revalidation un user promu VIP
    # par l'admin resterait « free » jusqu'à reconnexion. On re-lit la base
    # toutes les VIP_CACHE_TTL s pour propager les changements de tier.
    cached_vip = session.get("is_vip")
    checked_at = session.get("is_vip_ts", 0)
    if cached_vip is None or (time.time() - checked_at) > VIP_CACHE_TTL:
        # On profite de cette revalidation périodique pour vérifier que le
        # compte auth existe toujours : après une suppression de compte, un
        # cookie de session encore valide sur un AUTRE appareil pourrait sinon
        # recréer des données orphelines via l'onboarding.
        try:
            if not core_db.auth_user_exists(user_id):
                session.clear()
                return redirect(url_for("landing"))
        except Exception:
            # Erreur transitoire (API auth indisponible) : on ne déconnecte pas.
            pass
        try:
            profile = core_db.get_profile(user_id) or {}
            cached_vip = (profile.get("tier") or "free").strip().lower() == "vip"
        except Exception:
            # En cas d'erreur DB transitoire, on garde la valeur connue plutôt
            # que de rétrograder à tort en free.
            cached_vip = bool(cached_vip) if cached_vip is not None else False
        session["is_vip"] = cached_vip
        session["is_vip_ts"] = time.time()
    g.is_vip = bool(cached_vip)

    # Phase 4 : gate onboarding. Les routes /onboarding/* et /logout sont
    # exemptées pour éviter la boucle de redirection. /premium, /faq et
    # /confidentialite aussi : la carte « Plus de programmes PRO » de
    # l'onboarding pointe vers les offres, et ces pages de présentation
    # ne nécessitent aucune donnée utilisateur.
    if path.startswith("/onboarding") or path in ("/logout", "/premium", "/faq", "/confidentialite"):
        return None
    # Cache le flag en session pour éviter un hit DB à chaque requête
    if not session.get("onboarded"):
        try:
            onboarding = core_db.get_onboarding(user_id)
        except Exception:
            onboarding = {}
        if not onboarding:
            # Fix bug Phase 4 : un user pré-Phase 4 (qui a déjà un programme
            # ou de l'historique) ne doit JAMAIS voir l'onboarding — sinon
            # il risque d'écraser ses données. On crée une row minimale et
            # on le laisse passer.
            try:
                has_prog = bool(core_db.get_prog(user_id))
                has_hist = bool(core_db.get_hist(user_id))
            except Exception:
                has_prog = has_hist = False
            if has_prog or has_hist:
                try:
                    core_db.save_onboarding(user_id, {"prenom": ""})
                except Exception:
                    pass
                session["onboarded"] = True
                return None
            return redirect(url_for("onboarding.index"))
        session["onboarded"] = True
    return None


# ────────────────────────────────────────────────────────────────
# Protection CSRF — token par session, auto-injecté côté client.
# Kill-switch : poser CSRF_DISABLED=1 dans l'env désactive tout (filet de
# sécurité si un cas non prévu bloquait des actions en prod).
# ────────────────────────────────────────────────────────────────
_CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# /auth/session = handshake de login (pas encore de session Flask, déjà protégé
# par la vérification du JWT Supabase). Exempté.
_CSRF_EXEMPT_PATHS = {"/auth/session"}


def _csrf_enabled() -> bool:
    return os.getenv("CSRF_DISABLED", "").strip().lower() not in ("1", "true", "yes", "on")


def _get_or_create_csrf() -> str:
    tok = session.get("_csrf")
    if not tok:
        tok = secrets.token_urlsafe(32)
        session["_csrf"] = tok
    return tok


@app.before_request
def _csrf_protect():
    if not _csrf_enabled():
        return None
    if request.method not in _CSRF_METHODS:
        return None
    path = request.path or "/"
    if path.startswith("/static/") or path in _CSRF_EXEMPT_PATHS:
        return None
    # Les requêtes non authentifiées mutantes sont soit exemptées (login),
    # soit déjà bloquées par l'auth gate — pas de token à vérifier ici.
    if not session.get("user_id"):
        return None
    expected = session.get("_csrf")
    if not expected:
        # Session antérieure au déploiement CSRF : on initialise sans bloquer
        # cette première action (évite de verrouiller un user déjà connecté).
        _get_or_create_csrf()
        return None
    sent = (request.form.get("_csrf")
            or request.headers.get("X-CSRFToken")
            or request.headers.get("X-CSRF-Token")
            or "")
    if not sent or not secrets.compare_digest(str(sent), str(expected)):
        logger.warning("CSRF refusé sur %s (sent=%s)", path, bool(sent))
        abort(400)
    return None


# Content-Security-Policy — stratégie en deux couches (décidée après audit du
# code : ~700 styles inline, handlers onclick, scripts inline, + dépendances
# externes Google Fonts, jsDelivr/Supabase sur le login, Plotly).
#
# Couche 1 — TOUJOURS bloquante (_CSP_ENFORCED) : uniquement les directives
#   prouvées sans impact sur les ressources réellement chargées. Elles ne
#   gouvernent ni les scripts, ni les styles, ni les CDN → impossible de casser
#   l'app, tout en bloquant clickjacking, injection de <base>, exfiltration de
#   formulaire vers un tiers, et plugins.
# Couche 2 — Report-Only (_CSP_REPORT) : politique complète, corrigée avec les
#   vraies dépendances (jsDelivr pour supabase-js, Google Fonts, Plotly, le
#   domaine Supabase pour connect-src). N'bloque rien ; sert de base pour un
#   futur durcissement total via CSP_ENFORCE=1. CSP_DISABLED=1 retire tout.
_CSP_ENFORCED = (
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self' https://accounts.google.com; "
    "object-src 'none'"
)


def _csp_report_policy() -> str:
    # Domaine Supabase autorisé en connect-src (auth/OAuth) — lu depuis l'env.
    supa = ""
    try:
        supa = core_db._env("SUPABASE_URL")
    except Exception:
        supa = ""
    connect_extra = f" {supa}" if supa else ""
    return (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.plot.ly https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        f"connect-src 'self' https://cdn.plot.ly https://cdn.jsdelivr.net{connect_extra}; "
        "frame-ancestors 'self'; "
        "base-uri 'self'; "
        "form-action 'self' https://accounts.google.com; "
        "object-src 'none'"
    )


@app.after_request
def _security_headers(response):
    """Durcissement défensif. Anti-clickjacking, anti-MIME-sniffing, referrer,
    permissions, et CSP (couche bloquante sûre + couche report-only complète)."""
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")

    if os.getenv("CSP_DISABLED", "").strip().lower() in ("1", "true", "yes", "on"):
        return response

    if os.getenv("CSP_ENFORCE", "").strip().lower() in ("1", "true", "yes", "on"):
        # Durcissement total demandé explicitement : politique complète bloquante.
        response.headers.setdefault("Content-Security-Policy", _csp_report_policy())
    else:
        # Par défaut : couche sûre bloquante + politique complète en observation.
        response.headers.setdefault("Content-Security-Policy", _CSP_ENFORCED)
        response.headers.setdefault("Content-Security-Policy-Report-Only", _csp_report_policy())
    return response


@app.context_processor
def _inject_user():
    # is_premium : exposé à tous les templates pour gater des features (Coach
    # IA, export, stats avancées…). Pour l'instant tout le monde est free,
    # donc is_premium = False — mais l'infra est prête.
    # is_vip est déjà résolu et caché en session par le before_request — on le
    # réutilise au lieu de refaire un get_profile() en DB à chaque rendu de page.
    uid = session.get("user_id")
    premium = bool(uid) and bool(session.get("is_vip", False))
    email = (session.get("email") or "").strip().lower()
    admin_emails = {e.strip().lower() for e in (os.getenv("ADMIN_EMAILS", "") or "").split(",") if e.strip()}
    return {
        "current_user_email": session.get("email", ""),
        "is_authenticated": bool(uid),
        "is_premium": premium,
        "is_vip": premium,
        "is_admin": bool(email) and email in admin_emails,
        "csrf_token": _get_or_create_csrf() if uid else "",
        # IDs AdMob (app native Capacitor, comptes Free uniquement). Défauts =
        # IDs de TEST officiels Google — à remplacer par les vrais via l'env
        # Railway une fois le compte AdMob créé. Côté web/PWA : sans effet.
        "admob_banner_id": os.getenv("ADMOB_BANNER_ID", "ca-app-pub-3940256099942544/6300978111"),
        "admob_interstitial_id": os.getenv("ADMOB_INTERSTITIAL_ID", "ca-app-pub-3940256099942544/1033173712"),
    }


# ────────────────────────────────────────────────────────────────
# Landing page publique + page "Plus"
# ────────────────────────────────────────────────────────────────


@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("accueil.index"))
    return render_template("landing.html")


@app.route("/plus")
def plus():
    return render_template("plus.html", active="plus")


@app.route("/plaques")
def plaques():
    # Calculateur de disques — 100% client-side, aucune donnée.
    return render_template("plaques.html", active="plus")


@app.route("/faq")
def faq():
    # FAQ statique : confidentialité, sécurité, données, IA…
    return render_template("faq.html", active="plus")


@app.route("/confidentialite")
def confidentialite():
    # Politique de confidentialité — publique (exigence stores).
    return render_template("confidentialite.html", active="plus")


# ────────────────────────────────────────────────────────────────
# Manifest et service worker servis depuis la racine pour scope /
# ────────────────────────────────────────────────────────────────
@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory("static", "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.route("/.well-known/assetlinks.json")
def assetlinks():
    """Digital Asset Links — requis par le TWA Android (Play Store) pour
    prouver que l'app possède ce domaine (sinon la barre d'URL Chrome reste
    visible). Configuration via env :
      - TWA_SHA256_FINGERPRINT : empreinte SHA-256 du certificat de signature
        (Play Console → Signature de l'application), plusieurs possibles
        séparées par des virgules.
      - TWA_PACKAGE_NAME : nom de package Android (défaut com.muscutracker.app).
    Tant que l'empreinte n'est pas configurée → 404 (pas de fichier vide)."""
    from flask import jsonify
    fingerprints = [f.strip().upper() for f in (os.getenv("TWA_SHA256_FINGERPRINT") or "").split(",") if f.strip()]
    if not fingerprints:
        abort(404)
    package = (os.getenv("TWA_PACKAGE_NAME") or "com.muscutracker.app").strip()
    return jsonify([{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": package,
            "sha256_cert_fingerprints": fingerprints,
        },
    }])


# ────────────────────────────────────────────────────────────────
# Error handlers globaux — jamais de trace Flask blanche pour l'user.
# ────────────────────────────────────────────────────────────────
@app.errorhandler(400)
def handle_400(e):
    return render_template(
        "error.html",
        code=400,
        message="Requête invalide ou expirée (jeton de sécurité). Recharge la page et réessaie.",
    ), 400


@app.errorhandler(404)
def handle_404(e):
    return render_template(
        "error.html",
        code=404,
        message="Page introuvable.",
    ), 404


@app.errorhandler(500)
def handle_500(e):
    logger.error("500 on %s: %s", request.path, e)
    return render_template(
        "error.html",
        code=500,
        message="Erreur serveur. Réessaie dans quelques secondes.",
    ), 500


@app.errorhandler(413)
def handle_413(e):
    return render_template(
        "error.html",
        code=413,
        message="Fichier trop volumineux (5 Mo max).",
    ), 413


@app.errorhandler(429)
def handle_429(e):
    return render_template(
        "error.html",
        code=429,
        message="Tu cliques un peu trop vite — attends quelques secondes et réessaie.",
    ), 429


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
