"""Que contient vraiment `programs.data` ? — outil de MESURE, en lecture seule.

Le blob JSON du programme porte une trentaine de clés `_x` : le programme,
le planning, les réglages, les calques du jour, les badges, les bilans… Il est
relu ET réécrit à chaque interaction, donc tout ce qu'on y laisse coûte à
chaque série validée.

Avant de décider quoi en sortir, il faut savoir ce qui pèse. Cet outil le dit,
sur les vraies données, sans rien écrire.

    cd pwa
    python tools/analyse_blob.py

Il lit `SUPABASE_URL` et `SUPABASE_SERVICE_ROLE_KEY` dans l'environnement. Sur
Windows, si elles sont posées en variables **utilisateur**, le shell Bash ne
les hérite pas ; en PowerShell :

    $env:SUPABASE_URL = [Environment]::GetEnvironmentVariable('SUPABASE_URL','User')
    $env:SUPABASE_SERVICE_ROLE_KEY = [Environment]::GetEnvironmentVariable('SUPABASE_SERVICE_ROLE_KEY','User')

**Ce qu'il n'imprime jamais** : aucun nom d'exercice, aucun commentaire de
bilan, aucune adresse e-mail, aucun identifiant, et évidemment aucune clé. Que
des noms de clés, des tailles et des comptages — le rapport peut se coller
dans une conversation sans y réfléchir.

**Ce qu'il n'écrit jamais** : rien. Aucun `insert`, `update`, `upsert` ou
`delete`. Un test le vérifie sur la source (`tests/test_analyse_blob.py`).
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


def rapport(mesures: dict) -> str:
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
    lignes.append("")
    lignes.append("  Rien n'a ete ecrit. Aucun contenu n'est imprime ci-dessus :")
    lignes.append("  que des noms de cles, des tailles et des comptages.")
    return "\n".join(lignes)


def _lire_les_blobs():
    """Lit la colonne `data` de tous les programmes. Aucune ecriture."""
    from core.db_base import get_client
    client = get_client()
    lignes = client.table("programs").select("data").execute().data or []
    return [ligne.get("data") for ligne in lignes]


def main() -> int:
    manquantes = [n for n in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
                  if not (os.getenv(n) or "").strip()]
    if manquantes:
        print("Variables d'environnement absentes : " + ", ".join(manquantes))
        print("Voir l'en-tete de ce fichier pour les poser sans les afficher.")
        return 2
    try:
        blobs = _lire_les_blobs()
    except Exception as e:
        # Le message d'une erreur Supabase peut contenir l'URL ; jamais la cle,
        # mais on reste prudent et on ne recopie que le type.
        print(f"Lecture impossible ({type(e).__name__}). "
              "Verifie que les deux variables pointent sur le bon projet.")
        return 1
    if not blobs:
        print("Aucun programme en base.")
        return 0
    print(rapport(analyser(blobs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
