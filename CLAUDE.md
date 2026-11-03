# Règles du propriétaire — à appliquer dans chaque session

Muscu Tracker PRO : app web de musculation (Flask, Supabase, Railway), dans `pwa/`.
**Avant toute tâche, lire `CONTEXT.md`** (architecture, choix, écarts connus). `RAPPORT_AUDIT.md` contient le dernier audit en tête.

## Échanges
- Réponses en **français**, ton direct, phrases courtes. Le propriétaire n'est pas développeur : expliquer sans jargon.
- **Chaque affirmation a une preuve** : fichier et ligne, commande et sortie, requête, journal. **Reproduire un problème avant de l'affirmer**, et dire franchement quand une hypothèse ne se vérifie pas.
- Pour chaque tâche proposée, indiquer le **mode conseillé** : moyen (petit changement localisé) ou élevé (migration, plusieurs fichiers, sécurité, IA).

## Production
- **Lecture seule par défaut.**
  - Supabase (projet `pagrkndckkxlbmaasssl`) : uniquement des `select` via `execute_sql`, plus `list_tables`, `list_migrations` et `get_advisors`.
  - Railway (projet `12a5b212-08c2-47d6-81a2-06e2da9c7b0e`, service web `7193adb3-038d-423c-8833-70239f64efc6`) : déploiements, journaux, métriques, noms des variables.
- **Toute écriture en base, migration comprise, attend un « oui » explicite** du propriétaire. Une migration s'applique juste avant la fusion de sa PR, puis se vérifie par `select`.
- Ne jamais lire ni afficher la valeur d'une variable secrète.

## Code et PR
- **Une PR par tâche**, ouverte **en brouillon**, avec une description en français : problème, changement, tests.
- **Ne jamais fusionner sans un « oui » explicite** du propriétaire. Un message ambigu (faute de frappe, « ok » isolé) se fait confirmer.
- **Ne jamais fusionner, fermer ni modifier une PR Dependabot.** Le propriétaire s'en charge.
- **Après chaque fusion, vérifier le déploiement Railway** : statut SUCCESS, puis la ligne de démarrage « schéma : N tables et vues vérifiées, rien ne manque », sans erreur dans les journaux.
- **Tests avant de pousser** :
  - `cd pwa && python -m pytest tests -q`, tests navigateur `tests/e2e` compris ;
  - `node tests/js/run.js` ;
  - un correctif doit avoir un test qui **échoue sans lui**.
- Tenir `CONTEXT.md` à jour dans la même PR : description, arbre des fichiers, nombre de tests.
- Le test `test_couche_seance` limite les modules de calcul à 250 lignes.
- Alpine est en mode CSP : pas d'expression complexe dans les gabarits (voir `CONTEXT.md`, « Sécurité du navigateur »).

## Audits
- Les alertes Supabase listées dans `CONTEXT.md`, section « Alertes Supabase acceptées », ne sont plus à relever, tant que leur justification tient.

## Session sur le PC du propriétaire (Windows)
- Pour ouvrir des PR, il faut `gh` (outil GitHub en ligne de commande, connexion une fois dans le navigateur) ou le connecteur GitHub (`/mcp`). `git push` seul ne crée pas de PR.
