"""Ce que pèse chaque clé du blob `programs.data` — mesure, sans contenu.

Le blob porte une trentaine de clés `_x` : le programme, le planning, les
réglages, les calques du jour, les badges, les bilans… Il est relu ET réécrit
à chaque interaction, donc tout ce qu'on y laisse coûte à chaque série
validée. Avant d'en sortir quoi que ce soit, il faut savoir ce qui pèse.

Ce module ne fait que mesurer : on lui passe les blobs déjà lus. Il ne touche
ni à la base ni à Flask.

**Il ne rend jamais de contenu** — ni nom d'exercice, ni nom de séance, ni
commentaire de bilan, ni adresse. Que des noms de clés `_x`, des tailles et
des comptages. C'est ce qui permet de coller un rapport n'importe où sans y
réfléchir, et `tests/test_analyse_blob.py` le vérifie.

Deux points d'entrée l'utilisent : `tools/analyse_blob.py` en ligne de
commande, et `/admin/blob` dans l'app — cette dernière évite de sortir la clé
`service_role` de l'hébergeur.
"""
import json
from collections import defaultdict


# Les clés dont on sait qu'elles grandissent avec l'usage, et pourquoi.
CROISSANTES = {
    "_extras":        "une entrée par séance+date (vidée en fin de séance)",
    "_libre_draft":   "une entrée par séance+date (vidée en fin de séance)",
    "_substituts":    "une entrée par séance+date (vidée en fin de séance)",
    "_seance_order":  "une entrée par séance+date (vidée en fin de séance)",
    "_session_notes": "une entrée par séance+date (fenêtre de 84 jours)",
    "_archive":       "séances archivées",
    "_legacy_volume": "volume d'avant la table history",
    "_meal_plan":     "plats de la semaine",
    "_challenges_won": "un par défi gagné",
    "_challenges_done": "un par défi terminé",
    "_badges":        "un par badge débloqué",
    "_custom_exercises": "un par exercice perso",
}

# Les calques indexés par « séance|date » : ceux dont on veut l'âge.
CALQUES = ("_extras", "_libre_draft", "_substituts", "_seance_order", "_session_notes")


def _octets(valeur) -> int:
    """Poids JSON d'une valeur, tel qu'il part vraiment en base."""
    return len(json.dumps(valeur, ensure_ascii=False, separators=(",", ":"))
               .encode("utf-8"))


def _ko(n: int) -> str:
    return f"{n / 1024:7.1f} ko" if n >= 1024 else f"{n:7d} o "


def _dates_du_calque(store) -> list[str]:
    """Les parties date des clés « séance|date », triées. Ignore le reste."""
    if not isinstance(store, dict):
        return []
    dates = []
    for cle in store:
        fin = str(cle).rsplit("|", 1)[-1]
        if len(fin) == 10 and fin[4] == "-" and fin[7] == "-":
            dates.append(fin)
    return sorted(dates)


def analyser(blobs: list[dict]) -> dict:
    """Agrège les mesures. Prend les blobs déjà lus : testable sans base."""
    par_cle_total = defaultdict(int)
    par_cle_max = defaultdict(int)
    par_cle_presente = defaultdict(int)
    entrees_calque = defaultdict(int)
    plus_vieille = {}
    total = 0
    seances_total = 0

    for blob in blobs:
        if not isinstance(blob, dict):
            continue
        total += _octets(blob)
        for cle, valeur in blob.items():
            poids = _octets(valeur)
            if not cle.startswith("_"):
                seances_total += poids
                continue
            par_cle_total[cle] += poids
            par_cle_max[cle] = max(par_cle_max[cle], poids)
            par_cle_presente[cle] += 1
            if cle in CALQUES and isinstance(valeur, dict):
                entrees_calque[cle] += len(valeur)
                dates = _dates_du_calque(valeur)
                if dates:
                    actuelle = plus_vieille.get(cle)
                    if actuelle is None or dates[0] < actuelle:
                        plus_vieille[cle] = dates[0]

    return {
        "programmes": len(blobs),
        "total": total,
        "seances": seances_total,
        "par_cle": {c: {"total": par_cle_total[c], "max": par_cle_max[c],
                        "comptes": par_cle_presente[c]}
                    for c in par_cle_total},
        "entrees_calque": dict(entrees_calque),
        "plus_vieille": plus_vieille,
    }


PAGE_POSTGREST = 1000  # `max-rows` côté Supabase : au-delà, une requête de plus


def analyser_historique(lignes: list[dict]) -> dict:
    """Ce que coûte la lecture de l'historique, par utilisateur.

    `get_hist()` lit **toutes** les lignes d'un utilisateur à chaque affichage
    non mis en cache, par pages de 1 000. Savoir combien de lignes porte le
    plus gros compte dit si ça vaut une table d'agrégats — ou pas encore.

    On ne reçoit que `user_id` et `date` : aucun exercice, aucune charge.
    """
    par_user = defaultdict(int)
    premiere = {}
    for r in lignes:
        if not isinstance(r, dict):
            continue
        uid = r.get("user_id")
        par_user[uid] += 1
        d = str(r.get("date") or "")[:10]
        if len(d) == 10 and (uid not in premiere or d < premiere[uid]):
            premiere[uid] = d
    if not par_user:
        return {"lignes": 0, "comptes": 0, "pire": 0, "pages_pire": 0, "depuis": ""}
    pire_uid = max(par_user, key=lambda u: par_user[u])
    pire = par_user[pire_uid]
    return {
        "lignes": sum(par_user.values()),
        "comptes": len(par_user),
        "pire": pire,
        "pages_pire": (pire + PAGE_POSTGREST - 1) // PAGE_POSTGREST,
        "depuis": premiere.get(pire_uid, ""),
        "median": sorted(par_user.values())[len(par_user) // 2],
    }


def rapport(mesures: dict, hist: dict | None = None) -> str:
    lignes = []
    n = mesures["programmes"]
    lignes.append(f"{n} programme(s) lu(s).")
    lignes.append("")
    lignes.append(f"  Blob complet          {_ko(mesures['total'])}"
                  f"   (moyenne {_ko(mesures['total'] // max(1, n))})")
    lignes.append(f"  dont les seances       {_ko(mesures['seances'])}"
                  "   (le programme lui-meme, pas une cle _x)")
    lignes.append("")
    lignes.append("  CLE                     TOTAL      LE PLUS GROS   PRESENTE")
    lignes.append("  " + "-" * 62)
    for cle, m in sorted(mesures["par_cle"].items(), key=lambda kv: -kv[1]["total"]):
        note = ""
        if cle in mesures["entrees_calque"]:
            note = f"  {mesures['entrees_calque'][cle]} entrees"
            vieille = mesures["plus_vieille"].get(cle)
            if vieille:
                note += f", la plus vieille {vieille}"
        elif cle in CROISSANTES:
            note = f"  ({CROISSANTES[cle]})"
        lignes.append(f"  {cle:22}{_ko(m['total'])}  {_ko(m['max'])}   "
                      f"{m['comptes']:4}{note}")
    # Un historique vide n'a rien à dire : la section ne s'affiche pas.
    if hist and hist.get("lignes"):
        lignes.append("")
        lignes.append("  HISTORIQUE (ce que /accueil relit a chaque affichage)")
        lignes.append("  " + "-" * 62)
        lignes.append(f"  lignes en base          {hist['lignes']:6}"
                      f"   sur {hist['comptes']} compte(s)")
        lignes.append(f"  le plus gros compte     {hist['pire']:6}"
                      f"   soit {hist['pages_pire']} requete(s) PostgREST"
                      + (f", depuis {hist['depuis']}" if hist.get("depuis") else ""))
        lignes.append(f"  compte median           {hist.get('median', 0):6}")
    lignes.append("")
    lignes.append("  Rien n'a ete ecrit. Aucun contenu n'est imprime ci-dessus :")
    lignes.append("  que des noms de cles, des tailles et des comptages.")
    return "\n".join(lignes)
