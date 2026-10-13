"""Ce que l'accueil du style « Instrument » met en tête (13/10/2026).

La maquette choisie par le propriétaire répond à trois questions en un coup
d'œil : qu'est-ce que je fais aujourd'hui (la séance, son contenu), où en
est mon poids, quel est mon dernier record. Les calculs vivent ici pour que
la route reste une couche HTTP mince.
"""
from datetime import date, timedelta

from core.muscu import BW_EXOS, calc_1rm, get_base_name

FENETRE_POIDS_JOURS = 42      # six semaines, comme « Ton rythme réel »
PESEES_MIN = 3
DUREE_MIN_JOURS = 14


def _fr(x: float, decimales: int = 1) -> str:
    """82.5 → « 82,5 » ; 80.0 → « 80 »."""
    t = f"{x:.{decimales}f}".rstrip("0").rstrip(".") if decimales else f"{x:.0f}"
    return t.replace(".", ",")


def contenu_seance(prog, seance: str) -> dict:
    """Exercices, séries et premier exercice d'une séance du programme."""
    exos = [e for e in (prog or {}).get(seance) or [] if isinstance(e, dict) and e.get("name")]
    series = 0
    for e in exos:
        try:
            series += max(0, int(e.get("sets") or 0))
        except (TypeError, ValueError):
            continue
    return {"exercices": len(exos), "series": series,
            "premier": exos[0]["name"] if exos else ""}


def _jour(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def poids_resume(pesees, aujourdhui: date) -> dict | None:
    """Dernière pesée et, si les pesées le permettent, la pente en kg par
    semaine sur six semaines (moindres carrés, comme la page Nutrition)."""
    vues = sorted((d, float(p["poids_kg"])) for p in pesees or []
                  if (d := _jour(p.get("date"))) and d <= aujourdhui
                  and float(p.get("poids_kg") or 0) > 0)
    if not vues:
        return None
    derniere, kg = vues[-1]
    out = {"kg": _fr(kg), "date": derniere.isoformat(), "kg_semaine": None,
           "texte": f"Pesée du {derniere.day:02d}/{derniere.month:02d}"}
    fenetre = [(d, p) for d, p in vues if d >= aujourdhui - timedelta(days=FENETRE_POIDS_JOURS)]
    if len(fenetre) >= PESEES_MIN and (fenetre[-1][0] - fenetre[0][0]).days >= DUREE_MIN_JOURS:
        from core.nutrition_rythme import pente_par_jour
        par_semaine = pente_par_jour([((d - fenetre[0][0]).days, p) for d, p in fenetre]) * 7
        out["kg_semaine"] = round(par_semaine, 2)
        signe = "\u2212" if par_semaine < 0 else "+"
        out["texte"] = f"{signe}{_fr(abs(par_semaine), 2)}\u00a0kg / semaine"
    return out


def _perf(r) -> bool:
    exo = str(r.get("Exercice") or "")
    return (int(r.get("Reps") or 0) > 0 and exo != "SESSION" and not exo.startswith("CARDIO:")
            and "SKIP" not in str(r.get("Remarque") or ""))


def dernier_record(hist) -> dict | None:
    """La dernière série qui a battu le meilleur précédent du même exercice :
    la force estimée (1RM, Epley) pour un exercice chargé — comme les points
    « Record battu » de la fiche exercice —, les répétitions au poids du
    corps. La première séance d'un exercice ne compte pas (rien à battre)."""
    lignes = sorted((r for r in hist or [] if _perf(r) and r.get("Date")),
                    key=lambda r: (str(r["Date"]), int(r.get("Série") or 0)))
    meilleur: dict = {}
    premier_jour: dict = {}
    record = None
    for r in lignes:
        exo, jour = r["Exercice"], str(r["Date"])
        poids, reps = float(r.get("Poids") or 0), int(r["Reps"])
        au_pdc = get_base_name(exo) in BW_EXOS or poids <= 0
        mesure = reps if au_pdc else round(calc_1rm(poids, reps), 1)
        cle = (exo, au_pdc)
        premier_jour.setdefault(cle, jour)
        avant = meilleur.get(cle)
        if avant is not None and mesure > avant and jour != premier_jour[cle]:
            record = {"exo": exo, "date": jour, "poids": poids, "reps": reps, "au_pdc": au_pdc}
        if avant is None or mesure > avant:
            meilleur[cle] = mesure
    if not record:
        return None
    d = _jour(record["date"])
    record["jour"] = f"{d.day} {MOIS_COURTS[d.month - 1]}" if d else record["date"]
    record["texte"] = (f"{record['reps']} reps" if record["au_pdc"]
                       else f"{_fr(record['poids'], 2)} × {record['reps']}")
    return record


MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
               "juil.", "août", "sept.", "oct.", "nov.", "déc."]
JOURS_COURTS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


def date_courte(d: date) -> str:
    """« mar. 13 oct. »"""
    return f"{JOURS_COURTS[d.weekday()]} {d.day} {MOIS_COURTS[d.month - 1]}"
