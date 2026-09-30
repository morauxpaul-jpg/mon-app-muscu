"""Console d'administration : statistiques, funnel, fiche utilisateur.

Ce module est le seul à lire en travers de tous les utilisateurs. Il porte
aussi la suppression de compte, qui doit vider chaque table sans en oublier
une — la liste est explicite pour cette raison.
"""
import datetime as _dt
import logging

from core.db_base import _fetch_all, clear_user_cache, get_client


def _tous_les_comptes(client) -> list:
    """Tous les comptes auth, page par page. `list_users()` sans pagination
    renvoie la première page seulement (50 par défaut) : au-delà de 50
    comptes, la liste admin et le haut du funnel étaient tronqués."""
    out: list = []
    page = 1
    while True:
        resp = client.auth.admin.list_users(page=page, per_page=1000)
        lot = list(getattr(resp, "users", None) or resp or [])
        out.extend(lot)
        if len(lot) < 1000 or page >= 100:
            return out
        page += 1
from core.db_profil import _profile_upsert

logger = logging.getLogger(__name__)

# ── Liste des utilisateurs (console admin) ───────────────────────
def list_all_users_with_tier() -> list[dict]:
    """Retourne la liste de tous les users (admin). Combine auth.users (email)
    et public.profiles (tier). Réservé au backend admin — utilise service_role.
    """
    client = get_client()
    # auth.users via Admin API
    try:
        auth_users = _tous_les_comptes(client)
    except Exception as e:
        logger.error("list_all_users_with_tier auth FAILED: %s", e)
        auth_users = []

    # profiles
    try:
        profiles = {p["id"]: p for p in _fetch_all(
            lambda: client.table("profiles").select("id, tier, prenom").order("id"))}
    except Exception as e:
        logger.error("list_all_users_with_tier profiles FAILED: %s", e)
        profiles = {}

    out = []
    for u in auth_users:
        uid = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
        email = getattr(u, "email", None) or (u.get("email") if isinstance(u, dict) else "")
        created = getattr(u, "created_at", None) or (u.get("created_at") if isinstance(u, dict) else "")
        p = profiles.get(uid) or {}
        out.append({
            "id": uid,
            "email": email or "",
            "created_at": str(created or "")[:10],
            "tier": (p.get("tier") or "free"),
            "prenom": (p.get("prenom") or ""),
        })
    out.sort(key=lambda u: u["created_at"], reverse=True)
    return out

# ────────────────────────────────────────────────────────────
# Admin — stats globales + fiche user
# ────────────────────────────────────────────────────────────

def get_admin_stats() -> dict:
    """Agrégats cross-users pour le dashboard admin.
    Retourne : total_rows, total_tonnage, total_seances (distinct user+date+seance),
    active_7d, active_30d (distinct user_id avec date récente)."""
    import datetime as _dt
    client = get_client()
    try:
        rows = _fetch_all(lambda: (
            client.table("history").select("user_id, date, seance, reps, poids").order("id")
        ))
    except Exception as e:
        logger.error("get_admin_stats FAILED: %s", e)
        return {"total_rows": 0, "total_tonnage": 0, "total_seances": 0, "active_7d": 0, "active_30d": 0}

    today = _dt.date.today()
    cutoff_7 = (today - _dt.timedelta(days=7)).isoformat()
    cutoff_30 = (today - _dt.timedelta(days=30)).isoformat()

    tonnage = 0.0
    sessions = set()
    a7, a30 = set(), set()
    for r in rows:
        reps = int(r.get("reps") or 0)
        poids = float(r.get("poids") or 0)
        tonnage += reps * poids
        d = str(r.get("date") or "")[:10]
        uid = r.get("user_id")
        if uid and d:
            sessions.add((uid, d, r.get("seance") or ""))
            if d >= cutoff_30:
                a30.add(uid)
                if d >= cutoff_7:
                    a7.add(uid)
    return {
        "total_rows": len(rows),
        "total_tonnage": int(tonnage),
        "total_seances": len(sessions),
        "active_7d": len(a7),
        "active_30d": len(a30),
    }


# ── Analytics produit (events de conversion / funnel) ────────────
def insert_event(user_id, event: str, props: dict | None = None,
                 tier: str | None = None) -> None:
    """Enregistre un event analytics (table `events`, migration v28).

    Best-effort : l'appelant (core.analytics.track) avale déjà les exceptions,
    mais on garde l'écriture minimale et tolérante (user_id peut être None)."""
    client = get_client()
    payload = {
        "user_id": user_id or None,
        "event": str(event)[:64],
        "props": props or {},
    }
    if tier:
        payload["tier"] = tier
    client.table("events").insert(payload).execute()


# Étapes du funnel : (clé, libellé, type, source).
# type 'signup'  → compte auth.users (haut de funnel)
# type 'event'   → distinct user_id ayant émis l'un des events listés
# type 'tier'    → distinct user_id actuellement VIP (profiles.tier)
_FUNNEL_STEPS = [
    ("signup",      "Inscrits",        "signup", None),
    ("onboarding",  "Onboarding fait", "event",  ("onboarding_completed",)),
    ("workout",     "1ʳᵉ séance",      "event",  ("workout_finished",)),
    ("offer",       "Offre vue",       "event",  ("premium_viewed", "paywall_viewed")),
    ("checkout",    "Checkout lancé",  "event",  ("checkout_started",)),
    ("vip",         "VIP",             "tier",   None),
]


def get_funnel_stats(days: int = 30) -> dict:
    """Entonnoir de conversion sur les `days` derniers jours.

    Interprétation (v1, orientée vue d'ensemble) : pour chaque étape, nombre
    d'utilisateurs DISTINCTS ayant atteint l'étape DANS la fenêtre. Le haut de
    funnel = comptes créés dans la fenêtre (auth.users). Les étapes du milieu
    lisent la table `events`. La dernière = users actuellement VIP.

    Retourne {days, steps:[{key,label,users,pct_of_top,pct_of_prev}], coach_msgs}.
    """
    import datetime as _dt
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)).isoformat()
    client = get_client()

    # Events de la fenêtre (un seul fetch, dédup en Python).
    users_by_event: dict[str, set] = {}
    coach_users: set = set()
    try:
        lignes = _fetch_all(lambda: (
            client.table("events")
            .select("user_id, event, created_at")
            .gte("created_at", cutoff)
            .order("id")
        ))
        for r in lignes:
            uid = r.get("user_id")
            ev = r.get("event") or ""
            if not uid:
                continue
            users_by_event.setdefault(ev, set()).add(uid)
            if ev == "coach_message":
                coach_users.add(uid)
    except Exception as e:
        logger.error("get_funnel_stats events FAILED: %s", e)

    # Haut de funnel : comptes créés dans la fenêtre.
    cutoff_day = cutoff[:10]
    signups = 0
    try:
        for u in _tous_les_comptes(client):
            created = getattr(u, "created_at", None) or (u.get("created_at") if isinstance(u, dict) else "")
            if str(created or "")[:10] >= cutoff_day:
                signups += 1
    except Exception as e:
        logger.error("get_funnel_stats signups FAILED: %s", e)

    # VIP actuels (étape finale).
    vip_count = 0
    try:
        prof = _fetch_all(lambda: client.table("profiles").select("tier").order("id"))
        vip_count = sum(1 for p in prof if (p.get("tier") or "") == "vip")
    except Exception as e:
        logger.error("get_funnel_stats vip FAILED: %s", e)

    steps = []
    top = None
    prev = None
    for key, label, kind, events in _FUNNEL_STEPS:
        if kind == "signup":
            n = signups
        elif kind == "tier":
            n = vip_count
        else:
            seen: set = set()
            for ev in (events or ()):
                seen |= users_by_event.get(ev, set())
            n = len(seen)
        if top is None:
            top = n or 0
        pct_top = round(100 * n / top, 1) if top else 0.0
        pct_prev = round(100 * n / prev, 1) if prev else 100.0
        steps.append({
            "key": key, "label": label, "users": n,
            "pct_of_top": pct_top, "pct_of_prev": pct_prev,
        })
        prev = n if n else prev
    return {"days": days, "steps": steps, "coach_msgs_users": len(coach_users)}


def get_user_details(user_id: str) -> dict:
    """Fiche détaillée d'un user pour l'admin."""
    import datetime as _dt
    client = get_client()
    # Historique
    try:
        rows = _fetch_all(lambda: (
            client.table("history").select("date, seance, reps, poids")
            .eq("user_id", user_id).order("id")
        ))
    except Exception as e:
        logger.error("get_user_details history FAILED user=%s: %s", user_id, e)
        rows = []
    tonnage = 0.0
    sessions = set()
    last_date = ""
    for r in rows:
        tonnage += int(r.get("reps") or 0) * float(r.get("poids") or 0)
        d = str(r.get("date") or "")[:10]
        if d:
            sessions.add((d, r.get("seance") or ""))
            if d > last_date:
                last_date = d
    # Profil + quota coach
    try:
        presp = client.table("profiles").select("tier, prenom, coach_quota_date, coach_quota_count").eq("id", user_id).maybe_single().execute()
        prof = (presp.data if presp else None) or {}
    except Exception as e:
        logger.error("get_user_details profile FAILED user=%s: %s", user_id, e)
        prof = {}
    # Nb msg coach total
    try:
        cresp = client.table("coach_messages").select("id", count="exact").eq("user_id", user_id).execute()
        coach_count = int(getattr(cresp, "count", None) or 0)
    except Exception as e:
        logger.error("get_user_details coach FAILED user=%s: %s", user_id, e)
        coach_count = 0
    today = _dt.date.today().isoformat()
    q_date = str(prof.get("coach_quota_date") or "")
    q_used = int(prof.get("coach_quota_count") or 0) if q_date == today else 0
    return {
        "user_id": user_id,
        "tier": prof.get("tier") or "free",
        "prenom": prof.get("prenom") or "",
        "total_rows": len(rows),
        "total_tonnage": int(tonnage),
        "total_seances": len(sessions),
        "last_date": last_date,
        "coach_msgs_total": coach_count,
        "coach_quota_used": q_used,
    }


def reset_user_coach_quota(user_id: str) -> None:
    """Remet à 0 le quota coach IA du jour pour un user (admin)."""
    _profile_upsert(user_id, {"coach_quota_count": 0})


def auth_user_exists(user_id: str) -> bool:
    """True si le compte auth Supabase existe encore. Lève en cas d'erreur
    transitoire (réseau, API down) — l'appelant décide alors de ne PAS
    déconnecter. Utilisé pour invalider les sessions d'un compte supprimé."""
    client = get_client()
    try:
        resp = client.auth.admin.get_user_by_id(user_id)
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg or "not_found" in msg or "404" in msg:
            return False
        raise
    user = getattr(resp, "user", None) or resp
    uid = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
    return bool(uid)


def delete_user_account(user_id: str) -> None:
    """Suppression DÉFINITIVE d'un compte : toutes les tables + l'utilisateur
    auth Supabase. Exigence des stores (Google Play / App Store) : la
    suppression de compte doit être disponible dans l'app.

    Ordre : données métier d'abord, auth en dernier — si la suppression auth
    échoue, l'utilisateur peut réessayer (les données restantes seront déjà
    parties, les deletes sont idempotents)."""
    client = get_client()
    # coach_conversations en premier : supprime aussi coach_messages liés
    # (ON DELETE CASCADE) ; le delete coach_messages qui suit couvre les
    # éventuels messages legacy sans conversation_id.
    for table, key in (
        ("coach_conversations", "user_id"),
        ("coach_messages", "user_id"),
        ("nutrition", "user_id"),
        ("body_weight", "user_id"),
        ("session_notes", "user_id"),
        ("push_subscriptions", "user_id"),
        # Mesure d'usage interne : sans clé étrangère vers le compte, ses
        # lignes survivaient à la suppression (la politique promet « toutes
        # tes données »).
        ("events", "user_id"),
        ("history", "user_id"),
        ("programs", "user_id"),
        ("onboarding", "user_id"),
        ("profiles", "id"),
    ):
        try:
            client.table(table).delete().eq(key, user_id).execute()
        except Exception as e:
            # Une table optionnelle absente (migration non appliquée) ne doit
            # pas bloquer la suppression du reste.
            logger.error("delete_user_account %s FAILED user=%s: %s", table, user_id, e)
    clear_user_cache(user_id)
    # Compte auth Supabase (Google OAuth) — en dernier.
    client.auth.admin.delete_user(user_id)
