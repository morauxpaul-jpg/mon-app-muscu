"""Statistiques par exercice — le cœur de la fiche « un exercice, toute son
histoire ».

Jusqu'ici, Progrès ne proposait qu'un « zoom » : le poids MAXIMAL par semaine.
C'est la stat la moins informative du lot — elle ignore le volume, le nombre
de reps, et ne dit pas si on progresse quand on passe de 3×8 à 4×10 à charge
égale. Hevy et Strong donnent gratuitement l'historique complet, le 1RM estimé
et le volume par séance ; c'est le minimum attendu par quelqu'un qui migre.

Tout est calculé à la lecture depuis l'historique normalisé (aucun stockage).
"""
from datetime import date, timedelta

from core.hist import is_muscu_perf
from core.muscu import calc_1rm, get_base_name


def _norm(s) -> str:
    return (s or "").strip().casefold()


def variants_of(hist, base_name: str) -> list[str]:
    """Variantes réellement utilisées pour ce mouvement (« Squat »,
    « Squat (Barre) »…), les plus récentes d'abord."""
    nb = _norm(base_name)
    seen, out = set(), []
    for r in reversed(hist):
        exo = (r.get("Exercice") or "").strip()
        if not exo or not is_muscu_perf(r):
            continue
        if _norm(get_base_name(exo)) != nb:
            continue
        if _norm(exo) not in seen:
            seen.add(_norm(exo))
            out.append(exo)
    return out


def sessions_for(hist, exercice: str, *, by_base: bool = False) -> list[dict]:
    """Une entrée par séance où cet exercice a été fait, la plus récente
    d'abord :

        {date, seance, sets:[{serie, reps, poids, rpe}], volume, best_set,
         e1rm, reps_total}

    `by_base=True` regroupe toutes les variantes du même mouvement (utile
    quand l'utilisateur alterne barre et haltères).
    """
    target = _norm(exercice)
    rows = []
    for r in hist:
        exo = r.get("Exercice") or ""
        key = _norm(get_base_name(exo)) if by_base else _norm(exo)
        if key != (_norm(get_base_name(exercice)) if by_base else target):
            continue
        if not is_muscu_perf(r) or not r.get("Date"):
            continue
        rows.append(r)

    by_session: dict = {}
    for r in rows:
        key = (r["Date"], r.get("Séance") or "")
        by_session.setdefault(key, []).append(r)

    out = []
    for (date_str, seance), sets in sorted(by_session.items(), reverse=True):
        sets = sorted(sets, key=lambda r: int(r.get("Série") or 0))
        detail = [{
            "serie": int(s.get("Série") or 0),
            "reps": int(s.get("Reps") or 0),
            "poids": float(s.get("Poids") or 0),
            "rpe": s.get("RPE"),
            "exercice": s.get("Exercice") or "",
        } for s in sets]
        volume = int(sum(d["reps"] * d["poids"] for d in detail))
        best = max(detail, key=lambda d: (d["poids"], d["reps"]))
        e1rm = max(calc_1rm(d["poids"], d["reps"]) for d in detail)
        out.append({
            "date": date_str,
            "seance": seance,
            "sets": detail,
            "volume": volume,
            "reps_total": sum(d["reps"] for d in detail),
            "best_set": best,
            "e1rm": round(e1rm, 1),
        })
    return out


MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
               "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def resume_mouvement(hist, base: str, n: int = 6) -> dict | None:
    """Une ligne de « Mes exercices » (page Progrès, style « Instrument ») :
    séances, date de la dernière, la force estimée de la dernière séance (les
    répétitions au poids du corps) et les `n` dernières valeurs en hauteurs
    relatives pour une mini-courbe. `nouveau_haut` : la dernière bat toutes
    celles d'avant dans la fenêtre.

    La courbe ne compare que des séances du même genre que la dernière : des
    dips au poids du corps entre deux séances lestées donnaient « 0 » (la
    force estimée d'une série sans charge) au lieu des répétitions (relu sur
    le vrai compte le 13/10)."""
    s = sessions_for(hist, base, by_base=True)
    if not s:
        return None
    au_pdc = s[0]["e1rm"] <= 0
    meme_genre = [x for x in s if (x["e1rm"] <= 0) == au_pdc]
    recentes = list(reversed(meme_genre[:n]))   # de la plus ancienne à la plus récente
    valeurs = [max(d["reps"] for d in x["sets"]) if au_pdc else x["e1rm"] for x in recentes]
    bas, haut = min(valeurs), max(valeurs)
    barres = [round(35 + 65 * (v - bas) / (haut - bas)) if haut > bas else 70 for v in valeurs]
    j = date.fromisoformat(s[0]["date"])
    return {
        "name": base,
        "sessions": len(s),
        "derniere": f"{j.day} {MOIS_COURTS[j.month - 1]}",
        "valeur": valeurs[-1],
        "au_pdc": au_pdc,
        "barres": barres,
        "nouveau_haut": len(valeurs) > 1 and valeurs[-1] > max(valeurs[:-1]),
    }


def summary(sessions: list[dict]) -> dict:
    """Chiffres d'en-tête : records, totaux, et progression sur la période."""
    if not sessions:
        return {}
    best = max(sessions, key=lambda s: (s["best_set"]["poids"], s["best_set"]["reps"]))
    best_e1rm = max(sessions, key=lambda s: s["e1rm"])
    best_vol = max(sessions, key=lambda s: s["volume"])
    # Meilleure série en reps, datée du jour où elle a été faite la première fois.
    best_reps, best_reps_date = 0, None
    for s in reversed(sessions):
        n = max(d["reps"] for d in s["sets"])
        if n > best_reps:
            best_reps, best_reps_date = n, s["date"]
    first, last = sessions[-1], sessions[0]
    # Progression = e1RM de la dernière séance vs la première enregistrée.
    delta_pct = None
    if first["e1rm"] > 0 and len(sessions) > 1:
        delta_pct = round((last["e1rm"] - first["e1rm"]) / first["e1rm"] * 100)
    return {
        "sessions": len(sessions),
        "sets_total": sum(len(s["sets"]) for s in sessions),
        "reps_total": sum(s["reps_total"] for s in sessions),
        "volume_total": sum(s["volume"] for s in sessions),
        "best_weight": best["best_set"]["poids"],
        "best_weight_reps": best["best_set"]["reps"],
        "best_weight_date": best["date"],
        "best_e1rm": best_e1rm["e1rm"],
        "best_e1rm_date": best_e1rm["date"],
        "best_volume": best_vol["volume"],
        "best_volume_date": best_vol["date"],
        "best_reps": best_reps,
        "best_reps_date": best_reps_date,
        # Surtout sans charge (dips, pompes, tractions lestées une fois sur
        # vingt) : les records en kg n'ont pas de sens, la page parle en
        # répétitions. « Jamais chargé » ne suffisait pas : une seule séance
        # de tractions à +10 kg laissait la courbe en kg, réduite à ce seul
        # point (vrai historique, 11/10).
        "poids_du_corps": sum(1 for s in sessions if s["best_set"]["poids"] <= 0) * 2 > len(sessions),
        "first_date": first["date"],
        "last_date": last["date"],
        "delta_pct": delta_pct,
    }


# Mesures en kg : une séance au poids du corps (0 kg) n'a pas de charge à
# suivre. La tracer à 0 creusait la courbe (tractions tantôt lestées, tantôt
# non) et faussait la tendance.
_EN_KG = {"e1rm", "best_weight"}


def series(sessions: list[dict], metric: str = "e1rm", limit: int | None = None) -> list[dict]:
    """Points du graphique, du plus ancien au plus récent :
    [{date, value, record}]. `metric` ∈ {e1rm, volume, best_weight, reps,
    best_reps}.

    `record` : la séance bat tout ce qui précède (la première n'en est pas
    un). À calculer sur tout l'historique, avant de couper à une période :
    un record de juin reste un record vu sur les 3 derniers mois."""
    picker = {
        "e1rm": lambda s: s["e1rm"],
        "volume": lambda s: s["volume"],
        "best_weight": lambda s: s["best_set"]["poids"],
        "reps": lambda s: s["reps_total"],
        "best_reps": lambda s: max(d["reps"] for d in s["sets"]),
    }.get(metric, lambda s: s["e1rm"])
    recent = list(reversed(sessions[:limit] if limit else sessions))
    out, meilleur = [], None
    for s in recent:
        v = round(picker(s), 1)
        if metric in _EN_KG and v <= 0:
            continue
        out.append({"date": s["date"], "value": v,
                    "record": meilleur is not None and v > meilleur})
        meilleur = v if meilleur is None else max(meilleur, v)
    return out


# ── Période, tendance, comparaison, records ─────────────────────
# Audit du 06/10 (axe 4, idée 4.2-4) : la courbe montrait les 20 dernières
# séances à intervalles égaux, sans tendance ni comparaison. Strong montre
# la direction de la force sur une période choisie ; c'est ce qu'on lit
# pour savoir si un programme marche.

# (clé, libellé, jours) — None : tout l'historique.
PERIODES = [("1m", "1 mois", 30), ("3m", "3 mois", 91), ("6m", "6 mois", 182),
            ("1a", "1 an", 365), ("tout", "Tout", None)]
PERIODE_DEFAUT = "3m"
_JOURS = {k: j for k, _l, j in PERIODES}
_LIBELLES = {k: l for k, l, _j in PERIODES}
# Titres des deux colonnes de la comparaison.
_COMPARE = {"1m": ("30 derniers jours", "30 jours d'avant"),
            "3m": ("3 derniers mois", "3 mois d'avant"),
            "6m": ("6 derniers mois", "6 mois d'avant"),
            "1a": ("12 derniers mois", "12 mois d'avant")}


def libelle_periode(periode: str) -> str:
    return _LIBELLES.get(periode, "")
_PAR_MOIS = 30.44           # jours dans un mois moyen
# Variation plus petite que 2 % de la moyenne sur la période : « stable ».
_SEUIL_STABLE = 0.02


def nombre_fr(x, signe: bool = False) -> str:
    """1234.5 → « 1 234,5 » ; 80.0 → « 80 ». `signe` : « +1,4 », « −0,8 »
    (un vrai signe moins), « 0 » sans signe."""
    if x is None:
        return "—"
    t = f"{abs(float(x)):,.1f}".replace(",", "\u202f").replace(".", ",")
    if t.endswith(",0"):
        t = t[:-2]
    if t == "0":
        return t
    if x < 0:
        return "\u2212" + t
    return ("+" if signe else "") + t


def debut_periode(periode: str, aujourdhui: date) -> str | None:
    """Premier jour inclus (ISO), ou None pour tout l'historique."""
    jours = _JOURS.get(periode)
    return (aujourdhui - timedelta(days=jours - 1)).isoformat() if jours else None


def dans_periode(points: list[dict], debut: str | None) -> list[dict]:
    return [p for p in points if debut is None or p["date"] >= debut]


def _jour(iso: str) -> int:
    return date.fromisoformat(iso[:10]).toordinal()


def _mediane(valeurs: list[float]) -> float:
    v = sorted(valeurs)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def _droite(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Moindres carrés : (pente, origine)."""
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    pente = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return pente, my - pente * mx


def tendance(points: list[dict], min_points: int = 4, min_jours: int = 21) -> dict | None:
    """Direction générale des points : la droite qui passe au plus près
    d'eux (moindres carrés), sans les fautes de frappe.

    Faute de frappe = une valeur 3 fois plus grande ou 3 fois plus petite que
    la médiane de la période (400 kg pour 40, 4 pour 40). Aucun progrès ne
    triple une force d'une séance à l'autre. Au plus une séance sur dix est
    écartée : au-delà, ce n'est plus une faute, c'est l'historique. On ne
    juge pas l'écart à une première droite : une faute sur la DERNIÈRE séance,
    la plus probable (celle qu'on vient de saisir), tire la droite jusqu'à
    elle et ne s'en écarte plus (+195 kg par mois, essayé le 11/10).

    Pas de médiane des pentes (Theil-Sen) : en muscu, les mêmes valeurs
    reviennent sans cesse (3 × 10 à 32 kg, séance après séance), et la
    médiane tombait sur 0 : « stable » pour des dips passés de 10 à 24 reps
    (vrai historique, 11/10).

    None s'il y a trop peu de séances ou de recul pour parler de tendance."""
    if len(points) < min_points:
        return None
    mediane = _mediane([float(p["value"]) for p in points])
    fautes = [mediane > 0 and not mediane / 3 <= float(p["value"]) <= mediane * 3 for p in points]
    if 0 < sum(fautes) <= max(1, len(points) // 10):
        points = [p for p, faute in zip(points, fautes) if not faute]
    if len(points) < min_points:
        return None
    xs = [float(_jour(p["date"])) for p in points]
    ys = [float(p["value"]) for p in points]
    if xs[-1] - xs[0] < min_jours or max(ys) <= 0:
        return None
    pente, origine = _droite(xs, ys)
    debut, fin = origine + pente * xs[0], origine + pente * xs[-1]
    variation = fin - debut
    if abs(variation) < _SEUIL_STABLE * (sum(ys) / len(ys)):
        sens = "stable"
    else:
        sens = "hausse" if variation > 0 else "baisse"
    return {
        "sens": sens,
        "par_mois": round(pente * _PAR_MOIS, 1),
        "variation": round(variation, 1),
        "variation_pct": round(variation / debut * 100) if debut > 0 else None,
        "debut": {"date": points[0]["date"], "value": round(debut, 1)},
        "fin": {"date": points[-1]["date"], "value": round(fin, 1)},
    }


def _bilan(sessions: list[dict]) -> dict:
    return {
        "seances": len(sessions),
        "e1rm": max((s["e1rm"] for s in sessions), default=0),
        "volume": sum(s["volume"] for s in sessions),
        "reps_serie": max((d["reps"] for s in sessions for d in s["sets"]), default=0),
        "reps": sum(s["reps_total"] for s in sessions),
    }


def comparaison(sessions: list[dict], periode: str, aujourdhui: date,
                poids_du_corps: bool = False) -> dict | None:
    """La période choisie contre celle d'avant, de même longueur : « 3
    derniers mois » contre « les 3 mois d'avant ». None pour « Tout » ou
    quand aucune des deux n'a de séance."""
    jours = _JOURS.get(periode)
    if not jours:
        return None
    debut = aujourdhui - timedelta(days=jours - 1)
    avant = debut - timedelta(days=jours)
    act = [s for s in sessions if debut.isoformat() <= s["date"] <= aujourdhui.isoformat()]
    prec = [s for s in sessions if avant.isoformat() <= s["date"] < debut.isoformat()]
    if not act and not prec:
        return None
    a, b = _bilan(act), _bilan(prec)
    cles = ([("seances", "Séances", ""), ("e1rm", "Force estimée max", "kg"),
             ("volume", "Volume total", "kg")] if not poids_du_corps else
            [("seances", "Séances", ""), ("reps_serie", "Meilleure série", "reps"),
             ("reps", "Répétitions", "")])
    lignes = []
    for cle, libelle, unite in cles:
        va, vb = a[cle], b[cle]
        lignes.append({
            "libelle": libelle, "unite": unite,
            "actuel": va if act else None, "avant": vb if prec else None,
            "delta_pct": round((va - vb) / vb * 100) if act and prec and vb else None,
        })
    titre, titre_avant = _COMPARE[periode]
    return {"lignes": lignes, "titre": titre, "titre_avant": titre_avant,
            "avant_vide": not prec, "actuel_vide": not act}


REPS_RECORDS = (1, 3, 5, 8, 10, 12)


def records_par_reps(sessions: list[dict]) -> list[dict]:
    """Le plus lourd soulevé pour AU MOINS 1, 3, 5, 8, 10, 12 reps, avec la
    série et le jour où il l'a été pour la première fois. « Au moins » : 100 kg
    × 6, c'est aussi un record à 5 reps. Rien pour une rep jamais atteinte ni
    pour le poids du corps (0 kg).

    Une même série qui tient plusieurs records n'occupe qu'une ligne : « 1 à
    10 reps : 36 kg × 10 », pas quatre lignes identiques (vrai historique,
    11/10). Chaque ligne : {de, a, poids, reps_faites, date}."""
    series_faites = [(d["poids"], d["reps"], s["date"])
                     for s in sessions for d in s["sets"] if d["poids"] > 0 and d["reps"] > 0]
    out = []
    for r in REPS_RECORDS:
        candidates = [x for x in series_faites if x[1] >= r]
        if not candidates:
            continue
        poids = max(x[0] for x in candidates)
        premiere = min((x for x in candidates if x[0] == poids), key=lambda x: (x[2], -x[1]))
        if out and (out[-1]["poids"], out[-1]["reps_faites"], out[-1]["date"]) == (poids, *premiere[1:]):
            out[-1]["a"] = r
        else:
            out.append({"de": r, "a": r, "poids": poids, "reps_faites": premiere[1],
                        "date": premiere[2]})
    return out


def sparkline(points: list[dict], width: int = 600, height: int = 160,
              tendance: dict | None = None) -> dict:
    """Polyline SVG pour un graphique simple, sans dépendance externe.

    L'app chargeait Plotly (~3,5 Mo) pour tracer une ligne de 8 points ; sur
    mobile c'est plusieurs secondes de données pour rien. Ici, quelques
    coordonnées suffisent — mêmes conventions que la courbe de poids.

    Les points sont placés à leur date : trois semaines sans séance se voient
    comme un trou, au lieu d'être collées à la séance d'avant. L'échelle va
    de la plus petite à la plus grande valeur, écrites dans la marge de
    gauche ; la droite de `tendance` (cf. tendance()) est coupée à ces bords
    plutôt que d'élargir l'échelle (sinon « 10,4 reps » en haut de l'axe).
    """
    if not points:
        return {}
    values = [p["value"] for p in points]
    lo, hi = min(values), max(values)
    etiquettes = {"haut": hi, "bas": lo} if hi != lo else None
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    pad_l, pad_r, pad_t, pad_b = 58, 10, 14, 20     # pad_t, pad_b : en px (hauteur 1:1)
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    d0, d1 = _jour(points[0]["date"]), _jour(points[-1]["date"])

    def x_de(jour):
        return round(pad_l + (inner_w * (jour - d0) / (d1 - d0) if d1 > d0 else inner_w / 2), 1)

    def y_de(v):
        return round(pad_t + inner_h * (1 - (v - lo) / (hi - lo)), 1)

    coords = [{"x": x_de(_jour(p["date"])), "y": y_de(p["value"]), "value": p["value"],
               "date": p["date"], "record": bool(p.get("record"))} for p in points]
    out = {
        "points": coords,
        "polyline": " ".join(f"{c['x']},{c['y']}" for c in coords),
        "area": (f"{coords[0]['x']},{height - pad_b} "
                 + " ".join(f"{c['x']},{c['y']}" for c in coords)
                 + f" {coords[-1]['x']},{height - pad_b}"),
        "min": round(lo, 1), "max": round(hi, 1),
        "etiquettes": etiquettes,
        "width": width, "height": height,
        "last": coords[-1],
        "records": sum(1 for c in coords if c["record"]),
    }
    if tendance:
        ja, jb = _jour(tendance["debut"]["date"]), _jour(tendance["fin"]["date"])
        va, vb = tendance["debut"]["value"], tendance["fin"]["value"]
        # Morceau de la droite qui reste entre lo et hi (t de 0 à 1).
        if va == vb:
            ta, tb = (0.0, 1.0) if lo <= va <= hi else (1.0, 0.0)
        else:
            t1, t2 = (lo - va) / (vb - va), (hi - va) / (vb - va)
            ta, tb = max(0.0, min(t1, t2)), min(1.0, max(t1, t2))
        if ta < tb:
            out["tendance"] = {
                "x1": x_de(ja + ta * (jb - ja)), "y1": y_de(va + ta * (vb - va)),
                "x2": x_de(ja + tb * (jb - ja)), "y2": y_de(va + tb * (vb - va)),
            }
    return out
