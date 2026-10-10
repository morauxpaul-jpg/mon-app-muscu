"""Content-Security-Policy : la page n'exécute que les scripts de l'app.

Audit du 06/10 (m6) : la politique complète n'était qu'en observation
(Report-Only), et elle autorisait encore `unsafe-inline` et `unsafe-eval`.
Un texte glissé dans la page (prénom, note de séance, réponse du coach)
aurait donc pu s'y exécuter. Désormais, en blocage :

- les fichiers de /static s'exécutent ('self') ;
- un <script> écrit dans la page ne s'exécute que s'il porte le jeton
  (`nonce`) de CETTE réponse, neuf à chaque requête : `{{ csp_nonce() }}` ;
- plus d'`unsafe-eval` : Alpine tourne dans sa version CSP
  (static/js/alpine-composants.js) ;
- plus de onclick="…" dans le HTML : aucun jeton ne les autorise.

Les styles restent permis en ligne (`style="…"`, des centaines dans les
gabarits) : une règle de style ne lance pas de code.

Interrupteurs (variables d'environnement) :
- CSP_OBSERVER=1 : la politique complète repasse en observation
  (Report-Only), seule la couche sûre bloque — le retour arrière si un
  blocage gênait en production ;
- CSP_DISABLED=1 : plus aucun en-tête CSP.

Chaque blocage est signalé à POST /csp/rapport (routes/csp.py) et consigné
dans les journaux (« CSP bloqué »).
"""
import os
import secrets

from flask import g, has_request_context

RAPPORT = "/csp/rapport"

# form-action liste TOUTES les cibles vers lesquelles un <form> peut partir,
# y compris APRÈS une redirection 3xx. Le paiement Stripe POST /billing/checkout
# (self) puis redirige vers checkout.stripe.com → ce domaine DOIT y figurer,
# sinon le navigateur bloque silencieusement la redirection (paiement qui
# « charge sans aboutir »). billing.stripe.com = portail de gestion.
_STRIPE_FORM_ACTION = "https://checkout.stripe.com https://billing.stripe.com"

# Couche sûre : ne gouverne ni scripts, ni styles, ni ressources. Bloquante
# même en mode observation (clickjacking, <base> injecté, formulaire envoyé
# chez un tiers, plugins).
COUCHE_SURE = (
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    f"form-action 'self' https://accounts.google.com {_STRIPE_FORM_ACTION}; "
    "object-src 'none'"
)


def _actif(nom: str) -> bool:
    return os.getenv(nom, "").strip().lower() in ("1", "true", "yes", "on")


def jeton() -> str:
    """Le nonce de la réponse en cours, créé au premier usage. Vide hors
    requête (un gabarit rendu pour un e-mail n'a pas de politique)."""
    if not has_request_context():
        return ""
    if not getattr(g, "csp_nonce", None):
        g.csp_nonce = secrets.token_urlsafe(18)
    return g.csp_nonce


def politique(nonce: str = "", supabase_url: str = "") -> str:
    """La politique complète. `supabase_url` : la page de connexion parle à
    l'API d'authentification Supabase (connect-src)."""
    scripts = "'self'" + (f" 'nonce-{nonce}'" if nonce else "")
    connexions = "'self'" + (f" {supabase_url}" if supabase_url else "")
    return (
        "default-src 'self'; "
        f"script-src {scripts}; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        f"connect-src {connexions}; "
        f"{COUCHE_SURE}; "
        f"report-uri {RAPPORT}"
    )


def poser_entetes(response, supabase_url: str = ""):
    """Pose les en-têtes CSP sur une réponse (after_request d'app.py)."""
    if _actif("CSP_DISABLED"):
        return response
    complete = politique(getattr(g, "csp_nonce", "") if has_request_context() else "",
                         supabase_url)
    if _actif("CSP_OBSERVER"):
        response.headers.setdefault("Content-Security-Policy", COUCHE_SURE)
        response.headers.setdefault("Content-Security-Policy-Report-Only", complete)
    else:
        response.headers.setdefault("Content-Security-Policy", complete)
    return response
