"""Mesurer le blob `programs.data` en ligne de commande — LECTURE SEULE.

    cd pwa
    python tools/analyse_blob.py

Il lit `SUPABASE_URL` et `SUPABASE_SERVICE_ROLE_KEY` dans l'environnement. Sur
Windows, si elles sont posées en variables **utilisateur**, le shell Bash ne
les hérite pas ; en PowerShell :

    $env:SUPABASE_URL = [Environment]::GetEnvironmentVariable('SUPABASE_URL','User')
    $env:SUPABASE_SERVICE_ROLE_KEY = [Environment]::GetEnvironmentVariable('SUPABASE_SERVICE_ROLE_KEY','User')

Si la clé ne vit que chez l'hébergeur, **ne la rapatrie pas** : la page
`/admin/blob` donne exactement le même rapport, calculé là-bas.

La mesure elle-même est dans `core/blob_stats.py`, et elle ne rend aucun
contenu : que des noms de clés, des tailles et des comptages.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.blob_stats import analyser, rapport  # noqa: E402


def main() -> int:
    manquantes = [n for n in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
                  if not (os.getenv(n) or "").strip()]
    if manquantes:
        print("Variables d'environnement absentes : " + ", ".join(manquantes))
        print("Voir l'en-tete de ce fichier, ou ouvrir /admin/blob dans l'app.")
        return 2
    try:
        from core.db_programme import list_all_program_blobs
        blobs = list_all_program_blobs()
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
