"""Debrief de fin de séance — trois lignes générées juste après « Terminer ».

Le coach IA est une page qu'il faut penser à ouvrir : la plupart des gens ne
l'ouvrent jamais. Ce debrief va au-devant, au seul moment où l'on est certain
d'avoir l'attention de l'utilisateur — l'écran qui suit sa séance.

Il coûte ~250 tokens (moins d'un dixième de centime par séance) et donne au
PRO une raison de rester visible à chaque entraînement, pas seulement quand
il pense à consulter le coach.

Le texte est fabriqué à partir de chiffres déjà calculés (volume, records,
comparaison à la dernière fois) : l'IA rédige, elle n'invente pas les données.
"""
import logging

from core.hist import is_muscu_perf, tonnage
from core.muscu import calc_1rm

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 260

PROMPT = (
    "Tu es le coach de cette personne. Elle vient de terminer sa séance.\n"
    "Écris un debrief de 3 phrases MAXIMUM, en français, en la tutoyant.\n\n"
    "Structure :\n"
    "1. Ce qui s'est bien passé, en citant un chiffre précis de la séance.\n"
    "2. Un point d'attention OU une comparaison avec la dernière fois.\n"
    "3. Une consigne concrète pour la prochaine séance de ce type.\n\n"
    "Règles :\n"
    "- Pas de liste à puces, pas de titre, pas de formule d'accueil.\n"
    "- Pas de compliment vide (« bravo », « super séance ») sans chiffre.\n"
    "- N'invente aucun chiffre : utilise uniquement ceux fournis.\n"
    "- Jamais de conseil médical ; en cas de douleur, renvoie vers un "
    "professionnel de santé.\n\n"
    "DONNÉES DE LA SÉANCE\n{facts}"
)


def collect_facts(hist, seance: str, date_str: str, note: dict | None = None) -> dict:
    """Chiffres de la séance + comparaison avec la fois précédente.

    Retourne None si la séance ne contient aucune performance réelle (rien à
    debriefer), sinon un dict prêt pour le prompt et pour l'affichage.
    """
    def _norm(x):
        return (x or "").strip().casefold()

    today_rows = [r for r in hist
                  if r.get("Date") == date_str and _norm(r.get("Séance")) == _norm(seance)
                  and is_muscu_perf(r)]
    if not today_rows:
        return {}

    exos: dict = {}
    for r in today_rows:
        e = exos.setdefault(r["Exercice"], {"sets": 0, "reps": 0, "best": 0.0, "rpe": []})
        e["sets"] += 1
        e["reps"] += int(r.get("Reps") or 0)
        e["best"] = max(e["best"], float(r.get("Poids") or 0))
        if r.get("RPE"):
            e["rpe"].append(float(r["RPE"]))

    # Séance précédente portant le même nom (hors aujourd'hui).
    previous_dates = sorted({r["Date"] for r in hist
                             if _norm(r.get("Séance")) == _norm(seance)
                             and r.get("Date") and r["Date"] < date_str
                             and is_muscu_perf(r)}, reverse=True)
    prev_date = previous_dates[0] if previous_dates else None
    prev_rows = [r for r in hist if r.get("Date") == prev_date
                 and _norm(r.get("Séance")) == _norm(seance) and is_muscu_perf(r)] if prev_date else []

    # Records battus : meilleure charge du jour vs tout l'historique antérieur.
    records = []
    for exo, data in exos.items():
        before = [float(r.get("Poids") or 0) for r in hist
                  if _norm(r.get("Exercice")) == _norm(exo) and r.get("Date")
                  and r["Date"] < date_str and is_muscu_perf(r)]
        if data["best"] > 0 and (not before or data["best"] > max(before)):
            records.append({"exo": exo, "poids": data["best"]})

    all_rpe = [v for e in exos.values() for v in e["rpe"]]
    vol = tonnage(today_rows)
    prev_vol = tonnage(prev_rows)
    best_1rm = max((calc_1rm(float(r.get("Poids") or 0), int(r.get("Reps") or 0))
                    for r in today_rows), default=0)

    return {
        "seance": seance,
        "date": date_str,
        "volume": vol,
        "volume_prev": prev_vol,
        "volume_delta_pct": round((vol - prev_vol) / prev_vol * 100) if prev_vol else None,
        "exos": exos,
        "sets": len(today_rows),
        "reps": sum(int(r.get("Reps") or 0) for r in today_rows),
        "records": records,
        "rpe_moyen": round(sum(all_rpe) / len(all_rpe), 1) if all_rpe else None,
        "e1rm_max": round(best_1rm, 1),
        "prev_date": prev_date,
        "duration_min": (note or {}).get("duration_min"),
        "rating": (note or {}).get("rating"),
        "comment": (note or {}).get("comment"),
    }


def format_facts(facts: dict) -> str:
    """Faits en texte compact pour le prompt."""
    lines = [
        f"Séance : {facts['seance']} ({facts['date']})",
        f"Volume : {facts['volume']} kg sur {facts['sets']} séries "
        f"et {facts['reps']} répétitions",
    ]
    if facts.get("duration_min"):
        lines.append(f"Durée : {facts['duration_min']} min")
    if facts.get("volume_prev"):
        delta = facts["volume_delta_pct"]
        signe = "+" if delta is not None and delta >= 0 else ""
        lines.append(
            f"Dernière séance du même nom ({facts['prev_date']}) : "
            f"{facts['volume_prev']} kg, soit {signe}{delta} % aujourd'hui")
    else:
        lines.append("Première séance de ce type enregistrée.")
    if facts.get("rpe_moyen"):
        lines.append(f"RPE moyen : {facts['rpe_moyen']} sur 10")
    if facts.get("records"):
        recs = ", ".join(f"{r['exo']} à {r['poids']:g} kg" for r in facts["records"])
        lines.append(f"Records battus : {recs}")
    lines.append("Détail par exercice :")
    for exo, d in facts["exos"].items():
        rpe = f", RPE {round(sum(d['rpe']) / len(d['rpe']), 1)}" if d["rpe"] else ""
        lines.append(f"  - {exo} : {d['sets']} séries, {d['reps']} reps, "
                     f"max {d['best']:g} kg{rpe}")
    if facts.get("rating"):
        lines.append(f"Ressenti déclaré : {facts['rating']}/5")
    if facts.get("comment"):
        lines.append(f"Commentaire : {facts['comment'][:200]}")
    return "\n".join(lines)


def generate(api_key: str, facts: dict) -> str | None:
    """Texte du debrief, ou None si l'appel échoue (on n'affiche rien plutôt
    que d'afficher une erreur au moment d'une victoire)."""
    if not facts or not api_key:
        return None
    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": PROMPT.format(facts=format_facts(facts))}],
        )
        parts = [getattr(b, "text", "") for b in (resp.content or []) if getattr(b, "text", "")]
        text = " ".join(p.strip() for p in parts).strip()
    except Exception as e:
        logger.warning("debrief generation failed: %s", e)
        return None
    return text or None
