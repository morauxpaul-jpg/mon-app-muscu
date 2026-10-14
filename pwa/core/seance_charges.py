"""Les boutons − / + de la séance (style « Instrument », 14/10/2026) : de
combien monte ou descend la charge d'un exercice."""
from core.seance_historique import _norm


# Écart par défaut sans historique : 2 kg aux haltères (paires de 2 en 2 en
# salle), 2,5 kg ailleurs (deux disques de 1,25 kg).
PAS_HALTERES = 2.0
PAS_DEFAUT = 2.5


def echelle_charges(hist, exo_final):
    """Les charges déjà soulevées sur cet exercice (ce matériel), et l'écart
    le plus courant entre deux charges voisines — de quoi régler les boutons
    − / + de la séance.

    Un pas fixe de 2,5 kg ne colle à aucune machine : sur le vrai compte
    (14/10), les plaques font 7 kg (adducteurs 52 → 59 → 66 → 73 → 79), les
    poulies 2,2 à 2,3 kg (22,5 → 24,8 → 27), les haltères 2 kg. À égalité,
    l'écart le plus fin l'emporte : il ne saute aucune charge."""
    vues = sorted({round(float(r.get("Poids") or 0), 1) for r in hist or []
                   if _norm(r.get("Exercice")) == _norm(exo_final)
                   and float(r.get("Poids") or 0) > 0 and int(r.get("Reps") or 0) > 0})
    ecarts = {}
    for a, b in zip(vues, vues[1:]):
        e = round(b - a, 1)
        ecarts[e] = ecarts.get(e, 0) + 1
    if ecarts:
        pas = min(ecarts, key=lambda e: (-ecarts[e], e))
    else:
        pas = PAS_HALTERES if "haltère" in _norm(exo_final) else PAS_DEFAUT
    return {"charges": vues[-60:], "pas": pas}
