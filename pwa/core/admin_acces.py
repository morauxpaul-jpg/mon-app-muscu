"""Qui a droit à la console d'administration.

Une adresse figurant dans `ADMIN_EMAILS` ne suffit pas : il faut aussi que le
compte se soit connecté par **Google**. L'adresse vient du jeton Supabase, et
la clé anon est publique (page de connexion) : si le projet Supabase accepte
un jour l'inscription par e-mail sans confirmation, n'importe qui pourrait
obtenir un jeton portant l'adresse de l'administrateur (audit du 03/10, CC2).
Google, lui, ne délivre que des adresses dont il a vérifié la propriété.

Le fournisseur est lu dans le jeton à la connexion (`routes/auth.py`) et gardé
en session. Une session ouverte avant cette règle n'a pas l'information :
l'administrateur se reconnecte une fois.
"""
import os


def adresses_admin() -> set[str]:
    raw = os.getenv("ADMIN_EMAILS", "") or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def fournisseurs_du_jeton(payload: dict) -> list[str]:
    """Fournisseurs d'identité du compte, d'après le jeton Supabase."""
    meta = (payload or {}).get("app_metadata") or {}
    out = {str(p) for p in (meta.get("providers") or []) if p}
    if meta.get("provider"):
        out.add(str(meta["provider"]))
    return sorted(out)


def connecte_par_google(sess) -> bool:
    return "google" in (sess.get("fournisseurs") or [])


def est_admin(sess) -> bool:
    email = (sess.get("email") or "").strip().lower()
    return bool(email) and email in adresses_admin() and connecte_par_google(sess)
