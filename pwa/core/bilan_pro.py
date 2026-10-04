"""Ce que PRO a apporté ce mois-ci.

Au troisième mois, le membre PRO se demande s'il reste. Rien ne lui disait
ce qu'il avait reçu (audit du 03/10, profil 7) : les debriefs, les échanges
avec le coach, les programmes générés vivaient chacun dans leur coin. La page
Plus les rassemble, sur 30 jours glissants.

Les compteurs viennent de la table events (une requête groupée), les records
de l'historique déjà en cache. Best-effort : sans la table, on n'affiche que
ce qu'on sait.
"""
import datetime as _dt
import logging

logger = logging.getLogger(__name__)

EVENEMENTS = {
    "debrief_generated": "debriefs",
    "coach_message": "coach",
    "program_generated": "programmes",
    "seance_regenerated": "seances_refaites",
}


def _compter_evenements(user_id: str, jours: int = 30) -> dict:
    from core import db as core_db
    depuis = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=jours)).isoformat()
    out = {v: 0 for v in EVENEMENTS.values()}
    try:
        client = core_db.get_client()
        rows = core_db._fetch_all(lambda: (
            client.table("events").select("event")
            .eq("user_id", user_id).in_("event", list(EVENEMENTS))
            .gte("created_at", depuis).order("id")
        ))
    except Exception as e:
        logger.warning("bilan PRO : événements illisibles (%s)", e)
        return out
    for r in rows:
        cle = EVENEMENTS.get(r.get("event"))
        if cle:
            out[cle] += 1
    return out


def records_du_mois(hist, aujourd_hui, jours: int = 30) -> int:
    """Exercices dont la meilleure charge des 30 derniers jours dépasse tout
    ce qui précède."""
    debut = (aujourd_hui - _dt.timedelta(days=jours)).isoformat()
    avant, pendant = {}, {}
    for r in hist or []:
        exo, d = str(r.get("Exercice") or ""), str(r.get("Date") or "")
        if not d or exo == "SESSION" or exo.startswith("CARDIO:") or int(r.get("Reps") or 0) <= 0:
            continue
        p = float(r.get("Poids") or 0)
        if p <= 0:
            continue
        cible = pendant if d >= debut else avant
        cible[exo] = max(p, cible.get(exo, 0))
    return sum(1 for exo, p in pendant.items() if exo in avant and p > avant[exo])


def bilan_mois(user_id: str, hist, aujourd_hui) -> dict:
    out = _compter_evenements(user_id)
    out["records"] = records_du_mois(hist, aujourd_hui)
    out["vide"] = not any(out.values())
    return out
