# RAPPORT D'AUDIT — Muscu Tracker PRO

**Mise à jour** : 05/10/2026 (après la PR #29 : réglages sortis de `programs.data`, v45) · **Commit audité** : `6fcc9f6` (tête de `main` après les PR #6 à #29, CI verte, déployé) · **Audit initial** : 03/10/2026 sur `6126f95` (5,6/10). Mises à jour précédentes : 04/10 — 6,5 (`d2362f9`), 6,7 (`c4528b3`), 6,8 (`ee13985`), 6,8 (`158d1e0`), 6,9 (`67b346f`, 137 / 20) ; 05/10 — 6,9 (`345334c`, 138 / 20, après les PR #22 à #24), 6,9 (`0144587`, après la PR #27).
**Historique** : 30/09/2026, `ac44673`, 4,9/10. Les versions précédentes de ce fichier restent dans l'historique git ; `RAPPORT_AUDIT_2.md` n'a pas été touché.

---

## Note globale : **6,9 / 10** (138 / 20 · 04/10 : 6,5, 6,7, 6,8, 6,8, 6,85 · 03/10 : 5,6 · 30/09 : 4,9)

> Les trois défauts qui faisaient de l'app un carnet « qui note juste mais raisonne faux » sont corrigés et prouvés par des tests : le RPE saisi pilote la suggestion, « Série faite » valide la valeur affichée en un tap, et la fin de séance ne se bloque plus au sous-sol. Les programmes ne sont plus amputés (rotation A/B réelle), refaire l'onboarding ne détruit plus rien, et l'app a rattrapé l'essentiel de ce qui manquait face à Hevy/Strong : import de leur historique, supersets, échauffement, séries par muscle et par semaine, semaine allégée proposée. Depuis, la nutrition — seul axe resté à 5 — est passée à des repas détaillés aliment par aliment, avec des cibles reliées au poids et aux jours d'entraînement (PR #10), et les petits trous visibles sont bouchés : « Créer mon propre programme » ouvre l'éditeur, l'éditeur est borné, vider l'historique se confirme (PR #11). Enfin, une série ne peut plus exister en double en base (index unique v41, écritures par clé) et renommer un exercice propose d'emmener son historique (PR #13) ; la génération IA ne tient plus de fil du serveur (PR #14). Les revenus ne fuient plus : un remboursement total ou un litige bancaire retire PRO (rendu si le litige est gagné), et la production n'affiche jamais de pub de test en silence (PR #16). Les chemins de connexion, d'admin et du programme sont testés à 84-91 %, ce qui a révélé et corrigé deux façons de laisser une séance fantôme dans le planning (PR #17). Enfin, le cache, les verrous, les quotas et les tâches IA ne vivent plus seulement dans la mémoire d'un processus : avec Redis, l'app peut tourner sur plusieurs instances sans servir de donnée périmée, et la CI rejoue toute la suite sur un vrai Redis (PR #19). Un exercice a maintenant un identifiant qui survit aux renommages (PR #22, v42) et une série peut être marquée d'échauffement, hors records et volume de travail (PR #24, v43). Surtout, **la première séance réelle du propriétaire, sur Android, a révélé dix problèmes que 1 185 tests n'avaient pas vus** (§ A.4 bis) : affichage cassé en portrait dès qu'un record tombait, saisie non validée perdue en quittant l'app, chrono qui partait seul et notifiait le mauvais exercice, carte refermée d'office, défilement trop loin. Huit sont corrigés (PR #23), un n'a pas pu être reproduit, un portait sur la batterie et reste à mesurer sur le téléphone. **6,9, et ce n'est pas encore 8.** Seul le modèle de données monte (6 → 7). Ce retour confirme ce que le barème dit : un niveau Hevy/Strong se *prouve* à l'usage, pas en CI. Le 05/10, la PR #27 a fermé les trois derniers mineurs retenus (funnel VIP compté sur la fenêtre, tonnage admin sans le cardio, commentaires périmés) et rangé le cardio dans ses propres colonnes (v44, appliquée) : la base refuse désormais des minutes dans `reps` et des kilomètres dans `poids`, et le tonnage admin a perdu 86 685 « kg » qui venaient du cardio. **La note ne bouge pas (6,9)** : ce travail est invisible à l'écran et le modèle de données garde son blob `programs.data` fourre-tout. Redis est branché en production (un seul processus pour l'instant). Puis la PR #29 a sorti les réglages du blob (table `reglages`, v45, appliquée) ; en les déplaçant, **quatre réglages de la page Gestion se sont révélés sans aucun effet**, dont un vendu comme avantage PRO : ils sont retirés (§ A.4, F4). Restent dans le blob les calques, les défis et badges, les plats de la semaine et l'archive héritée, et aucun chiffre d'usage (rétention, conversion). **6,9, toujours** : aucun axe n'atteint 8 ; dix-huit sont à 7, deux à 6.

**Avertissement de méthode** : cette mise à jour est faite par le même agent qui a écrit les corrections. Le risque de complaisance est réel ; pour le contenir, chaque note qui monte s'appuie sur un test ou une mesure cités plus bas, et les constats non traités restent ouverts, même mineurs.

| Bloc | 30/09 | 03/10 | 04/10 (6,5) | 04/10 (6,7) | après #13-#14 (6,8) | après #16-#17 (6,8) | après #19 (6,9) | après #22-#24 (6,9) | après #27 (6,9) | après #29 (6,9) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Produit (onboarding, saisie, programme, progression, coach, générateur, nutrition, cardio) | 5,0 | 5,4 | 6,4 | 6,8 | 6,9 | 6,9 | 6,9 | 6,9 | 6,9 | **6,9** |
| Plateforme (hors-ligne, notifications, design, performance) | 4,8 | 5,5 | 6,8 | 6,8 | 6,8 | 6,8 | 6,8 | 6,8 | 6,8 | **6,8** |
| Technique (architecture, données, sécurité, robustesse, tests) | 5,0 | 5,6 | 6,4 | 6,4 | 6,6 | 6,6 | 6,8 | 7,0 | 7,0 | **7,0** |
| Business (monétisation, rétention, accessibilité) | 4,7 | 6,0 | 6,7 | 6,7 | 6,7 | 7,0 | 7,0 | 7,0 | 7,0 | **7,0** |

**Constats du 03/10** : 2 critiques conditionnels **clos** · 14 importants : **14 corrigés** (I11 actif en production avec Redis, sur un seul processus) · 16 mineurs : **15 corrigés**, 1 ouvert et non retenu (M5). **4 nouveaux défauts** trouvés et corrigés pendant les corrections (cache, séances fantômes dans le planning, réglages sans effet, § A.4). **10 retours d'usage réel** le 04/10 : 8 corrigés, 1 non reproduit, 1 à mesurer (§ A.4 bis).

---

## Sommaire

A. [Mise à jour du 04/10](#a-mise-à-jour-du-0410) (dernière révision après la PR #29, le 05/10)
  - A.1 Méthode · A.2 Notes par axe · A.3 Parcours par profil · A.4 Statut des constats · A.4 bis Usage réel · A.4 ter PR #27 · A.4 quater PR #29 · A.5 Ce qui manque pour 8 · A.6 Non vérifiable
B. [Audit du 03/10 — détail conservé (état avant corrections)](#b-audit-du-0310--détail-conservé)
  - 0. Méthode · Parties 1 à 4 · 5. Suivi du 30/09 · 6. Écarts doc/code · 7. Non vérifiable · 8. Annexe

---

## A. Mise à jour du 04/10

### A.1 Méthode

- **Code** : lecture de `main` après la PR #24 (64 modules `core/`, 19 blueprints, 37 gabarits) ; diff complet des PR #6 à #24 relu.
- **Exécution** (sur `345334c`) : `pytest` **1 192 passés** en mémoire, et la même suite rejouée avec cache, verrous, quotas et tâches IA dans Redis — simulé et vrai serveur local, 1 174 passés avec les tests dédiés au vrai Redis ; la CI la rejoue sur `redis:7-alpine` ; tests navigateur (Chromium, 375 × 812) **23 passés** (dont repas détaillé, renommage qui garde l'identifiant, génération suivie jusqu'au programme, saisie reprise à la relance, carte ouverte après la dernière série, échauffement enregistré à part) ; suite JS **113 passés** ; couverture de lignes Python **81 %** (03/10 : 71 %) — connexion 91 %, admin 89 %, programme 84 %, paiement 76 %, état partagé 91 %. Gunicorn lancé localement : 2 processus avec `REDIS_URL` et `WEB_CONCURRENCY=2`, 1 seul sans Redis (alerte journalisée). La fausse base des tests applique désormais l'index unique de production. Suite Python rejouée date figée sur chacun des 7 jours de la semaine (matin du 04/10) : verte.
- **Reproductions** : chacune des reproductions corrigées du 03/10 (R1 à R12) est rejouée par un test du dépôt (par exemple `tests/test_rpe_suggestion.py` pour R11, `tests/e2e/test_seance_navigateur.py` pour R1 et R2, `tests/test_rotation.py` pour R3, `tests/test_ecritures_croisees.py` pour R9).
- **Mesures** : premier champ de saisie à **519 px** du haut sur un compte neuf (03/10 : 836 px) ; poids réseau compressé — Programme 216 → 28 ko, séance 126 → 20 ko, accueil 28 → 8 ko.
- **Base de production** : migrations v37, v38, v39 vérifiées le 03/10 par le connecteur Supabase (lecture seule) : aucune règle RLS côté client, aucun droit `anon`/`authenticated`, vues en `security_invoker`, RLS actif sur les 11 tables. Migration **v40** (`nutrition.grams`, `nutrition.food`, contrainte `nutrition_grams_check`) appliquée le 04/10 avec l'accord du propriétaire, colonnes et contrainte relues en base. Migration **v41** (index unique `history_serie_unique`) appliquée le 04/10 avec son accord, après vérification en lecture seule : 1 136 lignes, 0 doublon ; index relu en base. Le site n'étant pas joignable d'ici, la fenêtre entre l'index et le déploiement de la PR #13 n'a pu être surveillée que par les journaux Supabase (aucun refus d'unicité relevé). Les PR #16, #17 et #19 n'apportent aucune migration. Migrations **v42** (`history.exercise_id` + index partiel) et **v43** (`history.type_serie` + contrainte) appliquées le 04/10 avec l'accord du propriétaire, relues en base, aucune ligne réécrite. Au 05/10, aucune série n'a encore été enregistrée depuis leur déploiement : identifiants et échauffements restent à constater sur une vraie séance. Migration **v44** (colonnes cardio `duree_min`, `distance`, `calories`, `vitesse`, contrainte `history_cardio_colonnes_check`, vues `user_last_activity` et `admin_history_stats`) appliquée le 05/10 avec l'accord du propriétaire, **après** le déploiement du code de la PR #27, puis service web redémarré. Avant : rejouée deux fois sur un PostgreSQL 16 local avec les 25 lignes cardio de production (SQL et Python identiques, idempotente). Après, relu en base : 25 lignes cardio, 0 avec des minutes ou des km dans `reps`/`poids`, 24 calories et 8 vitesses passées en colonnes, plus aucun « Cal: »/« Vit: » numérique en remarque, aucun droit `anon`/`authenticated` sur les vues ; tonnage admin 394 009 → 307 324. Migration **v45** (table `reglages`) appliquée le 05/10 avec l'accord du propriétaire, après le déploiement de la PR #29 (aucun redémarrage requis : la table est redemandée chaque minute). Avant : les deux blobs `_settings` de production relus, identiques à ceux du rejeu local (PostgreSQL 16, 5 profils dont valeurs invalides et heures hors bornes : 0 écart avec le code, idempotente). Après, relu en base : 2 lignes, chacune fidèle à son ancien réglage (heure 15 h et pré-remplissage coupé conservés pour l'un, heure par défaut pour l'autre), plus aucun programme portant `_settings`, versions incrémentées une fois, RLS actif sans règle, aucun droit `anon`/`authenticated` ; journaux du démarrage sans erreur.
- **Barème inchangé** : 10 = état de l'art · 8-9 = niveau Hevy/Strong, **prouvé** · 6-7 = correct, un concurrent fait mieux · 4-5 = utilisable mais faible · 1-3 = cassé ou absent.

### A.2 Notes par axe

| # | Axe | 30/09 | 03/10 | 04/10 | En une phrase |
|---|---|---:|---:|---:|---|
| 1 | Onboarding | 5 | 5 | **7** | Plus de programme amputé, refaire l'onboarding ne détruit rien, charge de départ expliquée, « Créer mon propre programme » ouvre l'éditeur avec un mode d'emploi ; connexion Google seule, pas de première séance guidée. |
| 2 | Saisie de séance | 4 | 5 | **7** | « Série faite » valide la valeur affichée, première série dans le premier écran, séries d'échauffement à part, supersets, aucun doublon, saisie reprise à la relance, repos lancé par « Série faite » seulement ; pas de séries dégressives, et l'usage réel du 04/10 a montré dix accrocs (§ A.4 bis). |
| 3 | Programme et planning | 6 | 5 | **7** | Rotation A/B réelle et réglable, supersets, semaine allégée, éditeur borné, planning qui ne pointe jamais vers une séance absente ; pas de blocs ni de pourcentage d'e1RM. |
| 4 | Progression et statistiques | 5 | 6 | **7** | Séries par muscle et par semaine face aux repères, progression racontée, compteur juste ; graphiques moins riches que les concurrents. |
| 5 | Coach IA | 6 | 6 | **7** | Voit RPE, prescription, bilans, cardio à part et semaine allégée ; quota atomique ; ouvert à l'essai. |
| 6 | Générateur de programme IA | 5 | 5 | **7** | Tâche de fond : la requête rend la main en 2 s, la page suit la tâche, reprend après un rechargement, un second tap rejoint la génération en cours ; « Refaire cette séance ». Tâches en mémoire d'une seule instance. |
| 7 | Nutrition | 5 | 5 | **7** | Repas aliment par aliment (quantité corrigeable, « reprendre la veille »), aliments habituels en tête, 429 aliments + produits du commerce par nom et code-barres, protéines en g/kg, plus de glucides les jours de séance. Manque face à MyFitnessPal / MacroFactor : recettes et aliments perso, tendance hebdo, cible adaptative. |
| 8 | Cardio | 4 | 6 | **6** | Durée, distance, calories et vitesse dans leurs colonnes (v44) ; une journée de cardio seul compte enfin pour le rappel et la relance. Rien de neuf à l'écran : pas de GPS ni de zones cardiaques, Strava seulement par import CSV. |
| 9 | Mode hors-ligne | 4 | 5 | **7** | « Terminer » borné à 6 s, rejeu borné à 8 s, semaine entière gardée avec pastille ; prouvé en mode avion (test navigateur). |
| 10 | Notifications et relances | 5 | 6 | **7** | Récap du dimanche ajouté, rappels suivant la rotation ; tout dépend d'un cron externe, invérifiable d'ici. |
| 11 | Design et cohérence UI | 5 | 5 | **6** | Écran de séance allégé, équipement en tête de carte, en-tête qui ne casse plus en portrait (il cassait dès qu'un record tombait, vu en usage réel) ; 61 `style=` en ligne, cohérence inégale entre pages. |
| 12 | Performance ressentie | 5 | 6 | **7** | Compression gzip (pages 4 à 8 fois plus légères), vidéo PRO chargée seulement au tap (895 ko épargnés), flux du coach plafonnés à 6 par instance, plus de flou GPU sur les cartes et les barres fixes (batterie, effet non mesuré) ; Redis branché en production (état partagé actif), mais toujours un seul processus (`WEB_CONCURRENCY` non défini). |
| 13 | Architecture du code | 6 | 6 | **7** | Modules isolés, plafonds de taille tenus par tests, état partagé entre instances (`core/partage.py`, Redis ou mémoire, repli si Redis tombe) ; le blob `programs.data` a perdu ses réglages (v45) mais garde calques, défis et plats. |
| 14 | Modèle de données | 4 | 4 | **7** | Une série = une ligne (index unique), écritures idempotentes, identifiant d'exercice stable qui survit aux renommages (v42), type de série dans sa colonne (v43), cardio dans ses propres colonnes, verrouillé par une contrainte (v44), réglages dans leur table typée (v45), repas par aliment ; restent dans le blob les calques, défis et badges, plats de la semaine et l'archive héritée. |
| 15 | Sécurité | 5 | 6 | **7** | Admin réservé à une connexion Google, v37-v39 vérifiées en base, quotas non contournables ; CSP sans `script-src` stricte. |
| 16 | Robustesse et gestion d'erreurs | 4 | 6 | **7** | Échecs signalés, fin de séance bornée, quota rendu si l'IA échoue, cache cohérent après écriture même entre instances, Redis en panne sans casse. |
| 17 | Tests | 6 | 6 | **7** | 1 230 + 23 navigateur + 113 JS, 81 % de couverture, suite rejouée sur un vrai Redis en CI ; tout tourne sur une fausse base (v44 et v45 rejouées à la main sur un vrai Postgres, pas en CI), et une seule séance réelle a trouvé dix défauts qu'ils ne voyaient pas. |
| 18 | Monétisation et paywall | 4 | 5 | **7** | Page PRO honnête, essai qui montre coach et debrief, remboursement et litige retirent PRO (webhook abonné aux trois événements), vrais identifiants AdMob, funnel juste sur sa fenêtre (M14) ; achat Android qui peut sortir de l'app, conversion jamais mesurée. |
| 19 | Boucle de rétention | 4 | 6 | **7** | Défi relatif, récap du dimanche, progression racontée, semaine allégée ; aucune dimension sociale. |
| 20 | Accessibilité | 6 | 7 | **7** | Inchangé. |

Moyenne : **6,9** (138 / 20, inchangée après les PR #27 et #29). Étapes : 6,5 (130 / 20), puis 6,7 (133 / 20) avec l'onboarding (6 → 7) et la nutrition (5 → 7), puis 6,8 (135 / 20) avec le modèle de données (5 → 6) et le générateur (6 → 7), puis 136 / 20 avec la monétisation (6 → 7), 137 / 20 avec l'architecture (6 → 7), enfin **138 / 20** avec le modèle de données (6 → 7). Ni la saisie ni le design ne montent malgré les corrections du 04/10 : ce qu'elles réparent, c'est ce que l'usage réel a trouvé cassé. Les tests restent à 7 malgré I14 clos : 8 demanderait des tests contre une vraie base et plus de parcours navigateur. **Après la PR #27, aucun axe ne monte**, et c'est voulu : le modèle de données reste à 7 tant que `programs.data` mélange programme, réglages et calques ; le cardio reste à 6, rien n'ayant changé pour l'utilisateur ; le funnel juste ne vaut pas une conversion mesurée. **Après la PR #29, toujours rien** : le blob a perdu une famille de clés sur quatre, le modèle de données reste à 7 ; retirer des réglages qui ne faisaient rien rend Gestion honnête, mais n'ajoute aucune fonction.

Réserve sur la nutrition : la recherche Open Food Facts par nom n'a pu être testée qu'avec un service simulé (le réseau de l'environnement d'audit ne l'atteint pas), et son plafond global de 8 recherches par minute, imposé par leurs conditions, saturera avec quelques dizaines d'utilisateurs simultanés.

### A.3 Parcours par profil

| # | Profil | 03/10 | 04/10 | Ce qui a changé · ce qui manque |
|---|---|---:|---:|---|
| 1 | Débutant complet, jour 1 | 5 | **7** | La valeur grisée s'enregistre, la série est à l'écran, la charge de départ est expliquée, le A/B alterne vraiment ; s'il veut son propre programme, il arrive dans l'éditeur avec un mode d'emploi. Manque : une première séance guidée. |
| 2 | Débutant, semaine 3 | 5 | **7** | Compteur juste, défi à sa mesure, « Tes progrès » et récap du dimanche lui racontent sa progression. |
| 3 | Intermédiaire venant de Hevy/Strong | 4 | **7** | Il importe son historique (CSV), retrouve supersets, échauffement et le geste « valider la valeur grisée ». Manque : séries dégressives. |
| 4 | Avancé / « pro » | 3 | **6** | RPE pris en compte, semaine allégée, séries par muscle, échauffement. Manque : blocs, pourcentages d'e1RM dans la séance. |
| 5 | Utilisateur FREE | 6 | **7** | Page PRO honnête, vidéo qui ne se lance plus seule ; séries par muscle et import gratuits. |
| 6 | Utilisateur en ESSAI | 4 | **6** | L'essai ouvre enfin le coach (5 messages/jour) et le debrief. Manque : 24 h restent courtes pour juger. |
| 7 | VIP payant | 5 | **7** | Coach qui lit ses RPE, générateur qui ne bloque plus et se reprend, « Refaire cette séance », bilan PRO du mois, nutrition détaillée reliée à ses séances. Manque : recettes et aliments perso. |
| 8 | App native Android | 5 | **6** | Plus de pub avant la première série, reprise de séance juste après minuit. Reste : webview distante, achat qui peut sortir de l'app. |
| 9 | Salle sans réseau (sous-sol) | 5 | **7** | « Terminer » ne bloque plus, la semaine entière est gardée et la pastille le dit (prouvé en mode avion). |

### A.4 Statut des constats du 03/10

| # | Constat (résumé) | Statut au 04/10 | Preuve |
|---|---|---|---|
| CC1 | Escalade de tier si v38 absente | **Clos** | v38 appliquée, vérifiée en base (§ A.1) |
| CC2 | Admin sur un e-mail non vérifié | **Corrigé** | `core/admin_acces.py` (connexion Google exigée), `tests/test_acces_admin.py` |
| I1 | RPE ignoré par la suggestion | **Corrigé** | `core/seance_historique.py` (`_rpe_de`), `tests/test_rpe_suggestion.py` |
| I2 | « Série faite » sur champ vide | **Corrigé** | `static/js/seance.js` (`serieFaite`), tests JS et navigateur |
| I3 | « Terminer » figé derrière la file | **Corrigé** | délais 8 s / 6 s, test navigateur réseau coupé |
| I4 | Test dépendant du jour | **Corrigé** | suite verte date figée sur 7 jours |
| I5 | Catalogue tronqué, A-B-A figé | **Corrigé** | `core/rotation.py`, `tests/test_rotation.py` |
| I6 | Onboarding qui efface les dossiers | **Corrigé** | `ajouter_et_planifier`, `tests/test_onboarding.py` |
| I7 | Doublons sur écritures croisées | **Corrigé** | index unique v41 en base (appliqué, relu), écritures par clé (`CLE_SERIE`), `tests/test_unicite_series.py`, `tests/test_ecritures_croisees.py` |
| I8 | Compteur « Séances x/y » faux | **Corrigé** | `tests/test_compteur_seances.py` |
| I9 | Contexte du coach pauvre | **Corrigé** | `tests/test_coach_contexte.py` |
| I10 | Promesses fausses (PRO, onboarding) | **Corrigé** | `tests/test_promesses_pro.py` |
| I11 | Serveur mono-processus, IA synchrone | **Corrigé** | génération en tâche de fond (PR #14) ; cache, verrous, quotas et tâches IA dans `core/partage.py` (Redis si `REDIS_URL`), flux du coach plafonnés, `gunicorn.conf.py` (PR #19) ; `tests/test_partage.py` (deux instances sur un même Redis). Redis branché sur Railway (même région que web), journal « partage: stockage redis » ; un seul processus tant que `WEB_CONCURRENCY` n'est pas défini |
| I12 | Renommer un exercice coupe l'historique | **Corrigé** | identifiant stable (`core/exercice_ids.py`, v42) : « oui » garde l'identifiant et rattache les séries anciennes sans les réécrire, « non » en crée un nouveau ; `tests/test_identite_exercice.py`, test navigateur |
| I13 | Échecs avalés (repas, cardio) | **Corrigé** | `tests/test_integrite_0310.py` |
| I14 | Couverture faible auth/admin/programme | **Corrigé** | 91 % / 89 % / 84 % (03/10 : 47 % / 43 % / 49 %) ; `tests/test_auth_admin_chemins.py`, `tests/test_programme_chemins.py` |
| M1 | Bilan écrasé par « Passer » | **Corrigé** | `tests/test_integrite_0310.py` |
| M2 | Bilans orphelins au renommage | **Corrigé** | `rename_session_notes` |
| M3 | Semaines vides au poids du corps | **Corrigé** | filtre `Reps > 0` |
| M4 | Défi unique 10 000 kg | **Corrigé** | cibles relatives, `tests/test_challenges.py` |
| M5 | CSP sans `script-src` | **Ouvert (non retenu)** | Alpine.js impose `unsafe-eval` ; durcir exigerait sa version CSP |
| M6 | Identifiants AdMob de test par défaut | **Corrigé** | `core/admob.py` : en production sans identifiants réels, les pubs sont coupées, journalisées au démarrage et signalées sur `/admin` ; `tests/test_revenus.py` |
| M7 | Webhook sans remboursement ni litige | **Corrigé** | `core/stripe_remboursements.py` (`charge.refunded`, `charge.dispute.created`, `charge.dispute.closed`), `tests/test_revenus.py` ; webhook abonné aux trois événements côté Stripe (confirmé par le propriétaire le 05/10) |
| M8 | Quotas contournables en parallèle | **Corrigé** | `core/quota.py`, `tests/test_quota_atomique.py` |
| M9 | Reprise de séance sur la date UTC | **Corrigé** | `templates/base.html` (journée logique locale) |
| M10 | Reset « soft » sans confirmation serveur | **Corrigé** | `confirm=yes` exigé (`routes/gestion.py`), `tests/test_petits_trous.py` |
| M11 | Séries non bornées dans l'éditeur | **Corrigé** | `MAX_SERIES` 20, 30 exercices, 40 séances, dans `_exo_entry` et chaque route ; éditeur aligné ; `tests/test_petits_trous.py` |
| M12 | Image de 1,1 Mo non référencée | **Corrigé** | fichier supprimé |
| M13 | Vidéo en lecture automatique | **Corrigé** | `controls preload="none"` dans `templates/vip_wall.html` et `templates/premium.html` |
| M14 | Funnel VIP hors fenêtre | **Corrigé** (PR #27) | l'étape VIP compte les `vip_activated` de la fenêtre (`core/db_admin.py`) ; `tests/test_mineurs_m14_m16.py` |
| M15 | Tonnage admin avec le cardio | **Corrigé** (PR #27, v44 appliquée) | vue `admin_history_stats` hors cardio, repli Python et fiche utilisateur aussi ; 394 009 → 307 324 en production ; `tests/test_mineurs_m14_m16.py` |
| M16 | Commentaires périmés | **Corrigé** (PR #27) | `core/catalog.py`, `routes/onboarding.py` (« on écrase le programme »), `routes/gestion.py` ; `tests/test_mineurs_m14_m16.py` |

**Nouveau, trouvé et corrigé** : **F1 — course du cache serveur.** Une lecture lente pouvait remettre en cache une valeur périmée juste après une écriture, servie jusqu'à 60 s (`core/db_base.py`). Révélé par les tests navigateur ; corrigé et testé (`tests/test_cache_course.py`). Pendant les corrections, une erreur 500 sur génération réussie a aussi été introduite puis corrigée avant toute mise en ligne (`3d0e678`, test ajouté).

**F2 — séances fantômes dans le planning.** Enregistrer le planning acceptait n'importe quel nom de séance, et importer un programme gardait les jours qui visaient une séance absente du fichier. L'accueil annonçait alors une séance qui n'existait pas. Trouvé en écrivant les tests de la PR #17 ; seules les séances existantes sont gardées (`routes/programme.py`, `tests/test_programme_chemins.py`).

**F3 — suppression de séance incomplète.** Supprimer une séance laissait le planning, la rotation et le rattachement à son programme pointer vers elle. Le nettoyage se fait désormais avec la suppression, et une rotation réduite à une séance disparaît (même PR, mêmes tests).

**F4 — quatre réglages sans effet, dont un vendu PRO.** « Replier automatiquement les exercices terminés », « Afficher l'estimation 1RM », « Animations du thème » (badge PRO pour les gratuits) et « Nombre de semaines précédentes affichées » (« PRO au-delà de 2 ») étaient enregistrés mais **lus nulle part** : aucun effet. Trouvé en déplaçant les réglages (PR #29) ; retirés avec l'accord du propriétaire, et `tests/test_reglages.py` interdit leur retour sans usage.

### A.4 bis Premier retour d'usage réel (séance du 04/10, Android)

Une séance de 7 exercices, faite par le propriétaire avec l'app native. Chaque retour a été reproduit dans Chromium en 412 px avant correction (PR #23, tests navigateur ajoutés).

| # | Retour | Cause trouvée | Statut |
|---|---|---|---|
| U1 | Saisie non validée perdue en quittant l'app, sans proposition de reprendre | séance marquée « en cours » seulement à la première série validée ; au retour, la saisie revenait cochée en vert comme si elle était enregistrée | **Corrigé** |
| U2 | Affichage cassé en mode portrait | le bandeau de record s'insérait dans la colonne des flèches, qui écrasait le titre | **Corrigé** |
| U3 | Exercice refermé d'office après la 3e série | repli automatique à la dernière série prévue | **Corrigé** (« Exercice suivant ») |
| U4 | Différencier les séries d'échauffement ? | absent | **Fait** (PR #24, v43) |
| U5 | Toucher une série faite demande de revalider les 3 | non reproduit (seule la série touchée se rouvre) ; peut-être lié à U1 | **Non reproduit** |
| U6 | Équipement caché en bas de carte | replié sous « Historique, équipement et options » | **Corrigé** |
| U7 | Batterie vidée vite | `backdrop-filter` sur chaque carte et sur les barres fixes, recalculé au défilement et à chaque seconde du chrono | **Atténué** (à mesurer sur le téléphone) |
| U8 | Notification du chrono sur le mauvais exercice | sélecteur `.exo-card.open` inexistant : toujours le premier exercice | **Corrigé** |
| U9 | Chrono lancé tout seul | lancé au `change` des champs reps et poids | **Corrigé** (« Série faite » seulement) |
| U10 | Skip qui descend trop bas | défilement lancé pendant le repli de la carte précédente | **Corrigé** |

Leçon pour la notation : les tests navigateur jouaient la séance en 375 px sans jamais battre un record ni quitter l'app ; U1, U2, U8 et U9 étaient invisibles pour eux. C'est pourquoi aucune note de saisie ou de design ne monte sur ces corrections.

### A.4 ter PR #27 (05/10) : derniers mineurs et cardio en colonnes

Chaque point a été reproduit par un test en échec avant correction (19 tests nouveaux, `tests/test_mineurs_m14_m16.py` et `tests/test_cardio_colonnes.py`).

- **M14, M15, M16** : voir § A.4.
- **Cardio (v44)** : en base, `duree_min`, `distance`, `calories`, `vitesse`, et `reps = poids = 0` sur toute ligne cardio, imposé par une contrainte. La conversion se fait à un seul endroit (`core/seance_cardio.py`, appelé par `core/db_historique.py`) : l'app relit le cardio exactement comme avant, aucun écran ne change.
- **Défaut évité en passant** : le rappel de séance, la relance des inactifs et le récap du dimanche lisent la table directement et ne regardaient que `reps` et `poids`. Avec le nouveau format, une journée de cardio seul serait devenue invisible et le rappel serait parti le soir d'un footing. Ils passent par `hist.perf_brute`, et la vue `user_last_activity` a été mise à jour dans la même migration.
- **Mise en production** : base en retard = ancien format ; après la migration, une écriture refusée par la contrainte repasse d'elle-même au nouveau. Ordre suivi : déploiement, migration, redémarrage.

### A.4 quater PR #29 (05/10) : les réglages sortent de `programs.data`

- **Table `reglages` (v45)** : une ligne par compte, une colonne typée par réglage, valeurs par défaut et borne de l'heure en base ; fermée au navigateur (comme v38) et effacée avec le compte. Les crons de rappel et de récap la lisent par lots de 100 comptes au lieu de chercher les réglages dans le blob de chaque abonné.
- **F4** : voir § A.4.
- **Mise en production sans fenêtre** : avant la migration, l'app lisait et écrivait dans le programme comme avant ; un compte sans ligne garde son ancien `_settings` ; la table est redemandée chaque minute, donc aucun redémarrage. La migration incrémente la version des programmes touchés pour qu'un onglet ouvert ne réécrive pas l'ancienne clé.
- 17 tests (`tests/test_reglages.py`), écrits en échec avant le code.

### A.5 Ce qui manque pour atteindre 8

Par impact décroissant :

Faits le 04/10 : la nutrition (PR #10), les petits trous visibles (PR #11), l'unicité des séries et le suivi des renommages (PR #13), la génération IA en tâche de fond (PR #14), les revenus (PR #16 : M6, M7, M12, M13), les tests de connexion, d'admin et du programme (PR #17 : I14), l'état partagé entre instances (PR #19 : I11), l'identifiant d'exercice (PR #22), les retours d'usage réel (PR #23), les séries d'échauffement (PR #24). Le 05/10 : les mineurs M14 à M16 et le cardio en colonnes (PR #27, v44), puis les réglages sortis du blob (PR #29, v45).

1. **Usage réel répété** : d'autres séances du propriétaire (et d'autres utilisateurs) pour vérifier U5, mesurer U7, et constater en base les identifiants, les échauffements et le cardio au nouveau format. C'est ce qui sépare « testé » de « prouvé ».
2. **Fin du modèle de données** : sortir de `programs.data` ce qui n'est pas le programme. Faits : le cardio (v44), les réglages (v45). Restent les calques de séance, les défis et badges, les plats de la semaine, et l'archive héritée du « reset soft » (§ B, Partie 4, C).
3. **Nutrition, pour passer de 7 à 8** : recettes et aliments personnels, tendance de la semaine, cible qui s'ajuste au poids réel.
4. **Rétention sociale** : binôme de régularité ou streak partagé.
5. **Preuve d'usage chiffrée** : le barème exige un niveau *prouvé* ; il faudra des chiffres réels (rétention J7/J30, conversion de l'essai) que le dépôt ne contient pas.
6. **Mineurs** : tous fermés sauf M5 (CSP stricte), écarté tant qu'Alpine.js impose `unsafe-eval`.

### A.6 Non vérifiable depuis le dépôt (au 05/10)

- **Cron horaire** (`/tasks/reminders` ou `cron_reminders.py`) : rappels, récap du dimanche et purge des événements en dépendent.
- **Railway** : Redis ajouté et branché (`REDIS_URL` sur web, même région europe-west4) ; le journal « partage: stockage redis, 1 processus » a été relu par le connecteur après le redémarrage du 05/10. 1 réplique et `WEB_CONCURRENCY` non défini, d'après le propriétaire. Option « Wait for CI » active : le déploiement de la PR #27 a attendu la CI de `main`. Le site lui-même n'est pas joignable depuis l'environnement d'audit.
- **Variables** : identifiants AdMob réels posés (éditeur `ca-app-pub-3523578671547864`, aucune alerte au démarrage, d'après le propriétaire) ; `CRON_SECRET` et `ANTHROPIC_API_KEY` non vérifiés.
- **Stripe** : webhook abonné à `charge.refunded`, `charge.dispute.created` et `charge.dispute.closed` (confirmé par le propriétaire, invérifiable d'ici). Aucun remboursement ni litige réel n'a encore exercé ce chemin.
- **Usage réel** : rétention, conversion, satisfaction. Un seul retour de séance à ce jour (§ A.4 bis).
- **Sur le téléphone** : l'effet du retrait du flou sur la batterie (Paramètres → Batterie), et les premières séries écrites avec `exercise_id` et `type_serie` (aucune au 05/10), ainsi que le premier cardio au format v44.
- **Open Food Facts en production** : la recherche par nom n'a été exercée qu'avec un service simulé.

---

## B. Audit du 03/10 — détail conservé

*État du commit `6126f95`, avant les corrections. Les statuts à jour sont au § A.4 ; les notes ci-dessous sont celles du 03/10.*

### Note du 03/10 : **5,6 / 10** (le 30/09 : 4,9)

> Le défaut central du 30/09 est réparé et prouvé dans un navigateur : une série validée est en base, « Terminer » ne perd plus rien, et 28 des 38 constats sont corrigés dans le code. Aucun défaut critique reproductible ne subsiste. Ce qui reste, c'est un carnet **qui note juste mais qui raisonne faux** : le RPE que l'utilisateur saisit n'arrive jamais à la suggestion de charge (reproduit : 3 × 8 à RPE 10 → « vise 9 reps »), le champ de reps affiche l'objectif en gris mais « Série faite » sur ce champ n'enregistre rien, le compteur « Séances » de l'accueil affiche 2/2 à un débutant qui en a fait 3, le catalogue ampute un PPL de sa séance Jambes si l'on choisit 2 jours, et refaire l'onboarding efface les autres programmes d'un membre PRO. En salle sans réseau fiable, une série en attente suffit à bloquer « Terminer » sur « Enregistrement… » (reproduit, 30 s et plus). Et la CI est verte… quatre jours sur sept : un test dépend du jour de la semaine et échoue le samedi, le dimanche et le lundi.

| Bloc | 30/09 | 03/10 |
|---|---:|---:|
| Produit (onboarding, saisie, programme, progression, coach, générateur, nutrition, cardio) | 5,0 | **5,4** |
| Plateforme (hors-ligne, notifications, design, performance) | 4,8 | **5,5** |
| Technique (architecture, données, sécurité, robustesse, tests) | 5,0 | **5,6** |
| Business (monétisation, rétention, accessibilité) | 4,7 | **6,0** |

**Constats** : 0 critique reproduit · 2 critiques **conditionnels** (dépendent de la configuration Supabase, invérifiable d'ici) · 14 importants · 16 mineurs. **12 reproductions** et 3 mesures en annexe.

### 0. Méthode

- **Périmètre** : `pwa/` (19 blueprints dont `seance_fin` et `seance_cardio` sortis le 01/10, 41 modules `core/`, 37 gabarits, 20 scripts JS, 14 feuilles CSS, 17 migrations SQL v23→v39), `android/`, `capacitor.config.json`, `railway.json`, `.github/`, `CONTEXT.md`. Chemins relatifs à `pwa/` sauf mention.
- **Lecture** : `app.py`, toutes les routes, toute la couche données, les modules de calcul de séance, les gabarits et scripts de la séance, de l'accueil, de l'onboarding, de la page PRO, le service worker, la file hors-ligne, `MainApplication.java`, le manifeste Android, les migrations v37-v39.
- **Exécution** (sur une copie du dépôt placée hors du dépôt, rien n'a été écrit dans le dépôt sauf ce fichier) :
  - `pytest` : **876 passés, 1 échoué, 7 ignorés** en 14 s (Chromium attendu par Playwright 1.60 absent de la machine) ; les 7 tests navigateur relancés avec un alias vers le Chromium installé : **7 passés**. Suite JS : **100 passés**. Couverture de lignes Python : **71 %** (outil `coverage`, hors dépôt).
  - CI GitHub : dernière exécution du workflow `Tests` sur `6126f95` **verte** (30/09, 23 h 53 UTC — un mercredi, jour logique).
  - 12 reproductions et 3 mesures sur la fausse base des tests (`tests/conftest.py`) : client de test Flask, et Chromium piloté par Playwright en 375 × 812 px. Scripts jetables, hors dépôt.
- **Conventions** : *reproduit* = observé en exécutant le code ; *déduit* = lu dans le code, non exécuté. Repères **R1…R12** et **Q1…Q3** → annexe.
- **Barème** : 10 = état de l'art · 8-9 = niveau Hevy/Strong, prouvé · 6-7 = correct, un concurrent fait mieux · 4-5 = utilisable mais faible ou frustrant · 1-3 = cassé, absent ou contre-productif. Aucun axe n'atteint 8.

---

### Partie 1 — Notes par axe

| # | Axe | 30/09 | 03/10 | En une phrase |
|---|---|---:|---:|---|
| 1 | Onboarding | 5 | **5** | Poids et taille enfin enregistrés ; mais le catalogue ampute les programmes selon la fréquence, et « Créer mon programme » promet un éditeur qui n'arrive jamais. |
| 2 | Saisie de séance | 4 | **5** | La série validée est en base (prouvé en navigateur) ; mais les reps se tapent à chaque série, l'objectif en gris est un piège, et le premier champ est sous la ligne de flottaison. |
| 3 | Programme et planning | 6 | **5** | Dossiers protégés au changement de programme ; planning A-B-A figé, programmes tronqués, refaire l'onboarding efface les dossiers. |
| 4 | Progression et statistiques | 5 | **6** | Semaine et streak justes ; compteur « Séances x/y » faux, pas de séries par muscle et par semaine. |
| 5 | Coach IA | 6 | **6** | Flux, mémoire, poids et taille ; toujours ni RPE ni reps cibles, et le cardio lu comme des kilos. |
| 6 | Générateur de programme IA | 5 | **5** | L'adoption ne détruit plus rien ; attente muette de 10-25 s, pas de régénération partielle. |
| 7 | Nutrition | 5 | **5** | Inchangée : calculs corrects, 269 aliments, repas en totaux, échec d'ajout silencieux. |
| 8 | Cardio | 4 | **6** | GPS débloqué (écran allumé), import Strava, deux blocs coexistent. |
| 9 | Mode hors-ligne | 4 | **5** | Délai de 8 s et page en cache à 3,5 s ; mais « Terminer » se bloque derrière un envoi en attente. |
| 10 | Notifications et relances | 5 | **6** | Rappel serveur, relances par arrêt, bandeau de retour juste ; tout dépend d'un cron absent du dépôt. |
| 11 | Design et cohérence UI | 5 | **5** | 63 `style=` au lieu de 924, chevauchements corrigés ; écran de séance toujours encombré. |
| 12 | Performance ressentie | 5 | **6** | « Série faite » = 3 requêtes au lieu de 11 ; pages de 180 et 215 ko, appels IA qui tiennent un des 16 fils. |
| 13 | Architecture du code | 6 | **6** | Découpage réel et garde-fous de structure ; blob fourre-tout et serveur mono-processus. |
| 14 | Modèle de données | 4 | **4** | Identité par nom, cardio dans des colonnes détournées, écritures non idempotentes. |
| 15 | Sécurité | 5 | **6** | XSS admin et escalade de tier fermées dans le code ; admin accordé sur la foi d'un e-mail non vérifié, CSP sans scripts. |
| 16 | Robustesse et gestion d'erreurs | 4 | **6** | Webhook honnête, insertion avant suppression ; doublons sur écritures croisées, quelques échecs encore avalés. |
| 17 | Tests | 6 | **6** | 884 tests dont 7 navigateur, couverture 71 % ; un test dépend du jour et le RPE ignoré passe tout. |
| 18 | Monétisation et paywall | 4 | **5** | L'essai peut acheter, la suppression résilie ; la page PRO vend trois choses fausses. |
| 19 | Boucle de rétention | 4 | **6** | Streak qui tombe, défis au poids du corps, relances justes ; aucune dimension sociale, défi unique à 10 000 kg. |
| 20 | Accessibilité | 6 | **7** | Plancher de police à 0,7 rem testé, contrastes et cibles testés, tutoriel à jour. |

Moyenne : **5,55**, arrondie à 5,6.

#### Détail et preuves

**1. Onboarding — 5/10**
- **Pour** : poids et taille partent enfin au serveur (`templates/onboarding.html:411-412`) et créent la première pesée (`routes/onboarding.py:136-158`) ; recommandation pondérée fréquence/équipement/niveau/objectif (`core/catalog.py:964-1047`) ; RPE et split expliqués.
- **Contre (reproduit R3)** : `build_program` tronque la liste des séances à la fréquence choisie (`core/catalog.py:1088-1089`). PPL 3 j choisi à 2 j/sem → Push et Pull, **jamais de jambes** ; Upper/Lower 4 j à 3 j/sem → Lower B disparaît. Les descriptions promettent « 2 séances alternées (A/B) » (`core/catalog.py:57`, `:89`, `:121`) alors que `planning_for` fige A-B-A chaque semaine (`core/catalog.py:24-35`).
- **Contre** : la carte « Créer mon propre programme » promet « amené directement dans l'éditeur » (`templates/onboarding.html:462-467`), la soumission redirige vers l'accueil (`routes/onboarding.py:195`). La carte PRO annonce « PPL, Upper/Lower… réservés aux membres Premium » (`templates/onboarding.html:477`) alors que PPL 3 j et Upper/Lower 4 j sont gratuits (`core/catalog.py:855-861`). Connexion Google seule.

**2. Saisie de séance — 5/10**
- **Pour** : chaque « Série faite » écrit en base (`static/js/seance.js:425-435`), « Terminer » envoie ce qui reste avant d'effacer (`:892-915`), prouvé par 7 tests navigateur (`tests/e2e/test_seance_navigateur.py`) ; Skip demande confirmation (`:628-671`, `routes/seance.py:459-468`) ; repos prescrit respecté (`static/js/seance.js:484-488`) ; chrono de repos avec compte à rebours natif Android, toujours le meilleur morceau.
- **Contre (reproduit R2)** : le champ Reps n'est jamais pré-rempli, seulement *affiché* en gris (`templates/_seance_carte_exercice.html:240-242`). Toucher « Série faite » sans taper replie la série comme faite avec « — » (`static/js/seance.js:426`, le `push` précède le test de remplissage) et **n'envoie rien**. Chez Hevy ou Strong, la valeur grisée est celle qui s'enregistre. Une série = au minimum une frappe clavier + un tap ; pas de boutons ±.
- **Contre (mesure Q3)** : à 375 × 812, premier champ de reps à **836 px** sur un compte neuf (au-delà de l'écran) et à **1 355 px** avec historique, derrière « Recommencer cette séance », le bloc « Récupération », le volume et l'en-tête de carte ; chaque carte porte en plus « Enregistrer », « Skip », « Recommencer cet exercice », « Réinitialiser les poids ».

**3. Programme et planning — 5/10**
- **Pour** : changer de programme ou adopter un programme généré ne remplace plus que le programme en cours (`routes/programme.py:627-634`, `routes/generator.py:432-434`) ; renommer une séance suit l'historique (`routes/programme.py:388-422`) ; reps et repos conservés.
- **Contre (reproduit R4)** : refaire l'onboarding puis choisir un programme passe par `save_prog_body(prog)` (`routes/onboarding.py:180`), qui remplace **tout** le corps : séances et dossiers des autres programmes disparaissent (badges conservés).
- **Contre** : planning « jour de semaine → séance » (`core/catalog.py:24-35`) ; ni superset, ni série d'échauffement, ni cycle, ni décharge ; renommer un exercice dans l'éditeur coupe son historique (aucun renommage côté `history` dans `routes/programme.py:190-310`) ; nombre de séries non borné dans l'éditeur (`routes/programme.py:230-235`).

**4. Progression et statistiques — 6/10**
- **Pour** : la semaine affichée est celle d'aujourd'hui et le streak tombe après une semaine vide (`routes/accueil.py:48-59`, `:283`) ; fiche exercice gratuite ; standards de force relatifs au poids, désormais connu dès l'onboarding.
- **Contre (reproduit R5)** : « Séances x/y » = séances **distinctes par nom** sur le nombre de séances du programme (`routes/accueil.py:314-315`) : Full Body A/B fait lundi-mercredi-vendredi → **2/2** ; un membre à trois dossiers lit 3/9.
- **Contre** : la carte du corps mesure une part relative (`routes/progres.py:295-331`), pas des séries par muscle et par semaine ; les semaines précédentes d'un exercice au poids du corps sont vides (reproduit R8, filtre `Poids > 0` dans `core/seance_historique.py:109-117`).

**5. Coach IA — 6/10**
- **Pour** : flux SSE, mémoire entre conversations, quota rendu en cas d'échec, poids et taille désormais dans le contexte (`routes/coach.py:497-500`). Ni Hevy ni Strong n'en ont (à ma connaissance, § 7).
- **Contre (reproduit R7)** : le programme est résumé en « Squat (5 séries) », sans reps ni repos (`routes/coach.py:130-134`) ; les séances récentes ignorent le RPE et les bilans, et le cardio est compté comme de la charge (« CARDIO:Course 1s @5kg », volume gonflé, `:149-163`).
- **Contre** : le prompt système décrit les « profils d'entraînement » supprimés le 01/10 (`routes/coach.py:54`) ; quota en lecture-écriture sur un profil caché 15 s, contournable en parallèle (`:178-198`).

**6. Générateur de programme IA — 5/10**
- **Pour** : JSON validé par une fonction pure testée ; reps et repos conservés ; l'adoption respecte les autres dossiers.
- **Contre** : appel synchrone de 2 600 tokens (`routes/generator.py:368-374`) qui occupe un des 16 fils du seul processus pendant 10-25 s, sans progression ; aucune régénération d'une séance ou d'un exercice ; quota vérifié avant l'appel et compté après (`:326-330`, `:397`), donc contournable par requêtes parallèles (plafond 10/h du limiteur).

**7. Nutrition — 5/10**
- **Pour** : Mifflin-St Jeor, TDEE suivant la pesée, scan de code-barres côté serveur.
- **Contre** : 269 aliments ; repas stockés en quatre totaux ; un ajout qui échoue est journalisé puis redirigé comme un succès (`routes/nutrition.py:381-385`) ; réservée au PRO et à l'essai.

**8. Cardio — 6/10**
- **Pour** : `geolocation=(self)` (`app.py:366`) et permissions Android déclarées (`android/app/src/main/AndroidManifest.xml`, bloc « Position ») ; le GPS filtre et **compte** ce qu'il rate (`static/js/gps-track.js:1-20`) ; deux blocs du même cardio en séance coexistent (`routes/seance_cardio.py:258-269`) ; import Strava.
- **Contre** : suivi seulement écran allumé et app au premier plan (`static/js/gps-track.js:3-8`) ; pas de fréquence cardiaque ni Health Connect ; suppression d'un bloc qui échoue avalée (`routes/seance_cardio.py:286-291`).

**9. Mode hors-ligne — 5/10**
- **Pour** : envoi abandonné à 8 s puis mis en file (`static/js/seance.js:46`, `:66-93`) ; page déjà vue servie après 3,5 s (`static/service-worker.js:9`, `:222-235`) ; jeton CSRF rafraîchi au rejeu, refus mis de côté au lieu de bloquer (`static/js/offline.js:142-177`) ; déconnexion avertie.
- **Contre (reproduit R1)** : le rejeu de la file n'a **aucun délai** (`static/js/offline.js:148-155`) et « Terminer » l'attend (`static/js/seance.js:910-911`). Une série en attente + un réseau qui ne répond pas = bouton « Enregistrement… » figé (30 s et plus observés).
- **Contre** : seules les séances planifiées aujourd'hui et demain sont pré-cachées (`routes/accueil.py:403-414`) ; les envois refusés sont rangés dans `muscu_offline_rejets` (`static/js/offline.js:200-208`) et plus jamais montrés.

**10. Notifications et relances — 6/10**
- **Pour** : rappel serveur à l'heure choisie, limité aux séances prévues et non faites (`core/reminders.py:45-81`) ; plafond de relances remis à zéro à la reprise (`core/push.py:94-106`) ; bandeau de retour fondé sur les séances prévues ratées (`routes/accueil.py:520-528`).
- **Contre** : rien dans le dépôt ne déclenche `/tasks/reminders` ni `/tasks/reactivation` (§ 7) — sans cron, ni rappel, ni relance, ni purge des `events` (`routes/push.py:111`) ; heure de Paris pour tous.

**11. Design et cohérence UI — 5/10**
- **Pour** : 949 → 63 attributs `style=` (`tests/test_mineurs_audit.py` tient le cliquet), plancher de police, chevauchements corrigés, décimales françaises.
- **Contre** : e-mail et déconnexion en tête de chaque page (`templates/base.html:122-127`) ; écran de séance (Q3) ; promesse non tenue « Badge VIP doré » (`templates/premium.html:167`, aucun badge distinct dans les gabarits).

**12. Performance ressentie — 6/10**
- **Pour (mesure Q1)** : « Série faite » = 3 requêtes Supabase cache chaud, 6 à froid (contre 11) ; accueil 7 requêtes à froid, 1 à chaud.
- **Contre (mesure Q2)** : `/seance` = **180 ko** de HTML pour 5 exercices (21 ko compressé, mais l'app ne compresse pas), `/programme` = 215 ko ; rendu de la séance ≈ 100 ms de CPU avec 2 600 séries (boucles sur tout l'historique pour chaque carte, `core/seance_contexte.py:27-141`) ; un seul processus à 16 fils (`railway.json`), où chaque flux du coach et chaque génération tient un fil.

**13. Architecture du code — 6/10**
- **Pour** : routes ≤ 850 lignes et gabarits ≤ 900 tenus par test (`tests/test_mineurs_audit.py`), couche données en dix modules sans cycle (`tests/test_couche_donnees.py`), calcul de séance en modules purs.
- **Contre** : le blob `programs.data` porte toujours réglages, badges, défis, calques, quotas de debrief, plats ; la justesse du cache **exige** un seul processus (`core/db_base.py:106-112`) — passer à deux instances réintroduit le défaut I8 sans qu'un test ne le voie.

**14. Modèle de données — 4/10**
- **Contre** : séances et exercices identifiés par leur nom (renommer = `UPDATE` en masse, `core/db_historique.py:313-353`) ; cardio dans des colonnes détournées (Reps = minutes, Poids = km, `routes/cardio.py:3-9`) ; aucune contrainte d'unicité par série : deux écritures croisées du même exercice **dupliquent** les séries (reproduit R9, `core/db_historique.py:229-241`) ; aucun agrégat, chaque page relit tout l'historique.
- **Pour** : `session_id`, colonne `rpe`, tables dédiées pour bilans et pesées, vue d'agrégats admin (v39).

**15. Sécurité — 6/10**
- **Pour** : XSS de la console admin fermée (`templates/admin.html:144-184`) ; migration v38 retirant toutes les règles côté client, dont celle qui permettait `update profiles set tier='vip'` depuis la console du navigateur (`supabase_schema_v38_tables_fermees_au_client.sql:4-9`) ; supabase-js servi en version exacte (`templates/login.html:57`) ; déconnexion en POST ; CSRF, JWT HS256/JWKS, webhook signé.
- **Contre** : l'accès admin repose sur le seul claim `email` du JWT (`routes/auth.py:113-120`, `routes/admin.py:37-51`), sans vérifier le fournisseur ni `email_verified` — sûr seulement si l'inscription par e-mail sans confirmation est fermée côté Supabase (§ 7) ; la CSP bloquante ne couvre pas les scripts (`app.py:325-330`) ; identifiants AdMob de test par défaut (`app.py:457-458`).

**16. Robustesse et gestion d'erreurs — 6/10**
- **Pour** : webhook en 500 sur échec pour que Stripe rejoue (`routes/billing.py:276-283`) ; insertion avant suppression (`core/db_historique.py:219-245`) ; résiliation Stripe avant suppression du compte, sinon refus (`routes/gestion.py:489-500`).
- **Contre** : doublons sur écritures croisées (R9) ; bilan écrasé par une seconde fin de séance « Passer » (reproduit R6, `routes/seance_fin.py:63-69` → upsert de `rating`/`comment` à `None`, `core/db_bilans.py:84-96`) ; échecs avalés en nutrition et au retrait de cardio.

**17. Tests — 6/10**
- **Pour** : 884 tests Python dont 7 de bout en bout dans Chromium, 100 tests JS, couverture 71 %, CI qui vérifie que l'app démarre avec les seules dépendances de production (`.github/workflows/tests.yml`).
- **Contre (reproduit R10)** : `tests/test_routes.py:807-815` construit une séance « il y a 5 jours » et attend le bandeau de retour, qui dépend désormais du planning : **échoue le lundi, le samedi et le dimanche**. La CI est verte parce qu'elle a tourné un mercredi.
- **Contre** : le RPE ignoré par la suggestion (R11) passe tout : les tests de `overload_suggestion` appellent la fonction avec un RPE fourni à la main, jamais la chaîne saisie → base → suggestion. Couverture faible là où l'argent et les droits se jouent : `routes/auth.py` 34 %, `routes/admin.py` 43 %, `routes/programme.py` 48 %, `core/db_admin.py` 42 %.

**18. Monétisation et paywall — 5/10**
- **Pour** : l'essai voit « Essai PRO — encore X h » et peut acheter (`templates/premium.html:37-46`, `app.py:439-449`) ; suppression = résiliation (`core/stripe_client.py:399-419`) ; export gratuit ; CGV et mentions légales.
- **Contre** : la page PRO vend « Programmes avancés (PPL, Upper/Lower…) » alors que deux sont gratuits, « Multi-programmes & profils » alors que les profils ont été retirés, et un « Badge VIP doré » qui n'existe pas (`templates/premium.html:110-111`, `:167`) ; le debrief après chaque séance, l'avantage PRO le plus tangible, n'y figure pas ; remboursements et litiges Stripe non traités (`routes/billing.py:264-275`) ; vidéo de 895 ko en lecture automatique sur le mur.

**19. Boucle de rétention — 6/10**
- **Pour** : streak qui tombe vraiment, défis en reps pour le poids du corps (`core/challenges.py:42-53`), debrief juste après la séance, relances par arrêt.
- **Contre** : défi unique « 10 000 kg » pour tous (`core/challenges.py:73-76`) — 1 440 kg mesurés sur une semaine de débutant (R5) ; compteur « Séances » faux ; aucune dimension sociale ; le parrain gagne 3 jours d'**essai restreint** (`routes/parrainage.py:22`), sans valeur pour un payant.

**20. Accessibilité — 7/10**
- **Pour** : contrastes calculés et cibles de 44 px testés (`tests/test_accessibilite.py`, `static/css/a11y.css`), 38 tailles de police remontées à 0,7 rem et un test l'impose, noms accessibles, `prefers-reduced-motion`, toasts annoncés.
- **Contre** : l'objectif de reps n'existe qu'en placeholder (illisible pour beaucoup de lecteurs d'écran comme valeur) ; `user-select: none` sur des composants (`static/css/components-pages.css:21`, `:282`).

---

### Partie 2 — Parcours par profil

| # | Profil | Note | En une phrase |
|---|---|---:|---|
| 1 | Débutant complet, jour 1 | **5** | Il comprend le vocabulaire, pas la mécanique : l'objectif gris n'est pas une valeur. |
| 2 | Débutant, semaine 3 | **5** | L'app compte mal ses séances et lui fixe un défi inatteignable. |
| 3 | Intermédiaire venant de Hevy/Strong | **4** | Il perd son historique, ses supersets et le geste « valider = la valeur grisée ». |
| 4 | Avancé / « pro » | **3** | Son RPE est ignoré par la suggestion, aucune périodisation. |
| 5 | Utilisateur FREE | **6** | Généreux et cohérent ; quelques promesses PRO fausses. |
| 6 | Utilisateur en ESSAI restreint | **4** | Enfin cohérent, mais 24 h sur la nutrition, ça ne démontre rien. |
| 7 | VIP payant (4,99 €/mois) | **5** | Coach et debrief uniques, carnet moins abouti que les concurrents. |
| 8 | App native Android | **5** | Pubs mieux placées, GPS débloqué ; même site dans une webview. |
| 9 | Salle sans réseau (sous-sol) | **5** | Mode avion : ça marche. Réseau faible : « Terminer » se fige. |

#### 1. Débutant complet, jour 1 — 5/10
**Parcours** : landing → Google → onboarding en 4 étapes (poids et taille exigés, enfin utilisés) → programme recommandé (Full Body Débutant) → accueil et tutoriel → carte « Prochaine séance · Commencer » qui ouvre directement la séance (`templates/accueil.html`, lien `mode=prefaite`) → écran de séance.
**RPE et split ?** Expliqués : chaque niveau et chaque programme a sa bulle, le RPE est replié derrière « RPE, remarque » avec une explication juste dans le tutoriel (`static/js/tuto-seance.js:59`).
**Frictions les plus coûteuses** :
1. Le champ Reps affiche « 5 » en gris ; il touche « Série faite » ; la ligne se replie avec « — » et rien n'est enregistré (R2). Il recommence la série suivante de la même façon.
2. Le premier champ est hors écran (836 px, Q3) derrière « Recommencer cette séance » et un bloc « Récupération : PRÊT » qui ne lui dit rien.
3. Aucune aide pour la première charge (le poids n'est pas pré-rempli au premier essai) et un planning A-B-A qu'on lui a présenté comme « alterné » (`core/catalog.py:57`).
**Ce qui lui manque** : valeur pré-remplie réelle, une première séance guidée, une indication de charge de départ.

#### 2. Débutant, semaine 3 — 5/10
**Ce qu'il vit** : à sa 3ᵉ séance, la modale PRO (`routes/accueil.py:496-507`) ; un debrief gratuit par semaine ; la suggestion « vise N+1 reps » respecte désormais la fourchette du programme.
**Ce qui le fait décrocher** :
1. Il fait lundi, mercredi, vendredi ; l'accueil dit « Séances 2/2 » (R5). L'effort du vendredi n'est pas compté.
2. Défi « Soulève 10 000 kg » quand sa semaine pèse 1 440 kg (R5) : il le rate toutes les semaines où il tombe.
3. Rien ne lui raconte sa progression (« +10 kg au squat en 3 semaines ») : elle existe dans la fiche exercice, personne ne la lui pousse.

#### 3. Intermédiaire (2 ans, vient de Hevy/Strong) — 4/10
**Ce qu'il perd** :
1. Son historique : aucun import CSV Hevy/Strong (seul l'export Strava est lu, `routes/cardio.py`) ; records et « dernière fois » repartent de zéro.
2. Le geste appris : chez eux, la valeur grisée est validée d'un tap ; ici elle n'est qu'un placeholder et la série validée vide disparaît (R2).
3. Supersets, séries d'échauffement, dégressives : absents ; en gratuit, 1 programme et 5 programmes du catalogue sur 20.
**Ce qu'il gagne** : coach IA qui lit son carnet, debrief, nutrition, interface française, compte à rebours natif.

#### 4. Avancé / « pro » — 3/10
**L'app tient-elle la route ?** Comme carnet, à peine ; comme outil de pilotage, non.
1. **Son RPE ne sert à rien** : il saisit 3 × 8 à 100 kg à RPE 10 ; la suggestion suivante dit « Même charge, vise 9 reps » au lieu de « Consolide » (R11). Le RPE est écrit dans la colonne `rpe` (`core/seance_saisie.py:105`, `core/db_historique.py:203`) mais la suggestion le cherche dans le texte de la remarque (`core/seance_historique.py:198`).
2. Aucune périodisation : ni blocs, ni décharge, ni pourcentage d'e1RM dans la séance ; planning hebdomadaire figé ; StrongLifts annoncé « alternance A/B » (`core/catalog.py:573`) mais planifié A-B-A chaque semaine.
3. Pas de séries d'échauffement (elles comptent dans volume et records) ; pas de séries par muscle et par semaine ; le coach ne voit ni ses RPE ni ses reps cibles (R7).

#### 5. Utilisateur FREE — 6/10
**Jusqu'où il va** : séances illimitées, 5 programmes (dont PPL 3 j et Upper/Lower 4 j), fiche exercice, calendrier, courbe de poids, cardio + GPS + import Strava, badges, défis, un debrief par semaine, rappels, **export complet gratuit** (`routes/gestion.py:550-596`).
**Murs** : Coach IA, générateur, nutrition, carte du corps / hall of fame / table RM, multi-programmes, réimport. Ils tombent au bon moment (après la 3ᵉ séance, cadenas visibles dans « Plus »).
**Ratés** : la page PRO lui vend comme PRO deux programmes qu'il a déjà (`templates/premium.html:110`) ; le mur charge une vidéo de 895 ko.

#### 6. Utilisateur en ESSAI restreint (vip_until) — 4/10
**Parcours** : lien d'invitation → 1 jour d'essai (`routes/parrainage.py:23`) → badge **ESSAI** (`templates/base.html:123`) → « Plus » : « Essai PRO · encore X h — Passe en PRO pour le garder » (`templates/plus.html:8-13`) → Coach : mur PRO → page PRO : encadré d'essai et **boutons d'achat** (`templates/premium.html:37-46`, `:131-142`).
**Cohérent ou frustrant ?** Cohérent désormais. Mais l'essai ouvre la nutrition et les statistiques — deux fonctions qui montrent leur valeur au bout de plusieurs jours — pendant 24 h, et ferme le coach et le debrief illimité, les deux seules choses que personne d'autre n'a. Le parrain, lui, reçoit 3 jours du même essai restreint.

#### 7. Utilisateur VIP payant (4,99 €/mois) — 5/10
**Ce qu'il a** : coach 15 messages/jour, générateur 3/semaine, debrief après chaque séance, nutrition + scan, statistiques, 20 programmes, multi-programmes, pas de pub dans l'app native.
**En a-t-il pour son argent ?** Il paie le prix de Hevy Pro ou Strong Pro (ordre de grandeur, § 7) pour un carnet moins rapide à remplir mais avec un coach et un debrief qu'ils n'ont pas.
**Réabonnement au mois 3** : le debrief et le coach sont les seules raisons récurrentes ; contre elles, un coach qui ignore ses RPE, une suggestion qui ignore ses RPE, un « refaire l'onboarding » qui efface ses dossiers (R4), et aucun écran « ce que PRO t'a apporté ce mois-ci ».

#### 8. Utilisateur de l'app native Android — 5/10
**Écarts avec le web** : même site dans une webview (`capacitor.config.json:4-6`) ; compte à rebours natif du repos ; publicités pour les gratuits, mais plus de pub « App Open » pendant une séance (`MainApplication.java`, `inSession()`) — sauf entre l'ouverture de la séance et la première série, car le drapeau n'est posé qu'à la première série (`static/js/seance.js:98-114`) ; GPS désormais permis ; achat masqué si `HIDE_NATIVE_BILLING` est posé (`app.py:396-410`), et alors aucun moyen d'acheter dans l'app ; identifiants AdMob de test si l'environnement ne les fournit pas (`app.py:457-458`).
**Frictions** : démarrage dépendant du réseau (webview distante) ; reprise de séance au démarrage à froid fondée sur la date UTC (`templates/base.html:108`), donc ratée entre minuit et 2 h ; achat qui peut basculer dans le navigateur (`templates/premium.html:67-72`).

#### 9. Utilisateur en salle sans réseau (sous-sol) — 5/10
**Étape par étape** :
1. À la maison : l'accueil fait garder la séance planifiée d'aujourd'hui et de demain (`routes/accueil.py:403-414`). Une séance non planifiée n'est pas gardée.
2. Mode avion : bandeau orange, page servie par le cache, « Série faite » met en file, « Terminer » met le bilan derrière les séries (`static/js/seance.js:917-931`) ; au retour du réseau, tout part dans l'ordre (prouvé, `tests/e2e/test_seance_navigateur.py:172-190`).
3. Réseau faible (le cas courant) : la page s'ouvre depuis le cache après 3,5 s ; chaque série abandonnée à 8 s part en file — bien.
4. « Terminer » avec une série en file : `OfflineQueue.sync()` attend un `fetch` sans délai (`static/js/offline.js:148-155`) ; le bouton reste sur « Enregistrement… » **indéfiniment** (R1). L'utilisateur finit par fermer l'app : ses séries sont en file (pas perdues), son bilan et sa durée ne partent pas, et la séance n'est jamais close.
5. Le chrono de repos fonctionne parfaitement hors ligne.

#### Verdict
- **Meilleure du marché pour** : le pratiquant francophone débutant ou intermédiaire, sur Android, qui veut un coach IA branché sur son vrai carnet et un debrief après chaque séance, pour 4,99 € — combinaison absente de Hevy et Strong à ma connaissance (§ 7), avec le compte à rebours natif en prime. À condition de taper ses reps à chaque série.
- **Clairement la pire pour** : le pratiquant avancé qui pilote au RPE (powerlifting, 5 × 5, blocs) : la fonction qui devrait le servir — la suggestion — ignore précisément la donnée qu'il saisit, et rien ne permet de périodiser.

---

### Partie 3 — Audit technique

#### Critique — conditionnels (configuration hors dépôt)

**CC1 — Escalade de tier si la migration v38 n'est pas appliquée.** Déduit.
- **Preuve** : la v38 elle-même décrit la faille : « depuis la console, un compte gratuit pouvait faire `update profiles set tier = 'vip'` » (`supabase_schema_v38_tables_fermees_au_client.sql:4-9`). La clé anon est publique (page de connexion) et le navigateur garde une session Supabase.
- **Ce que ressent l'utilisateur** : rien ; l'éditeur perd tout revenu PRO au profit de quiconque ouvre la console.
- **Correctif** : exécuter les deux requêtes de vérification en fin de v38 (§ 7) ; ajouter un test de démarrage qui interroge `pg_policies` via service_role et journalise une alerte si une règle existe.

**CC2 — Accès admin accordé sur un claim `email` non vérifié.** Déduit.
- **Preuve** : `routes/auth.py:113-120` copie `payload["email"]` en session sans regarder `app_metadata.provider` ni `email_verified` ; `routes/admin.py:37-51` compare cette adresse à `ADMIN_EMAILS`. Avec la clé anon publique, `supabase.auth.signUp({email: <adresse admin>})` obtient un jeton si le projet accepte l'inscription par e-mail **sans confirmation**.
- **Impact** : prise de la console : passer des comptes VIP, lire les e-mails newsletter, pousser une notification à tous.
- **Correctif** : n'accepter en admin qu'un jeton `provider == "google"` et `email_verified` ; mieux, une liste d'`user_id` plutôt que d'e-mails.

#### Importants (14)

| # | Constat (preuves) | Statut | Ce que ressent l'utilisateur | Correctif |
|---|---|---|---|---|
| I1 | **RPE saisi ignoré par la suggestion** : écrit en colonne (`core/seance_saisie.py:105`, `core/db_historique.py:203`), lu dans la remarque (`core/seance_historique.py:198`). | Reproduit R11 | « Vise 9 reps » après un échec à RPE 10 ; jamais « Monte » après une série facile. | Lire `r.get("RPE")` (repli `parse_rpe`) ; test qui passe par `save-exo`. |
| I2 | **« Série faite » sur un champ vide** replie la série sans rien écrire ; l'objectif n'est qu'un placeholder (`static/js/seance.js:425-435`, `templates/_seance_carte_exercice.html:240-242`). | Reproduit R2 | « J'ai validé mes 3 séries » — rien en base. | Pré-remplir la valeur (dernière fois / cible) ou valider le placeholder ; à défaut, refuser le repli. |
| I3 | **« Terminer » figé derrière la file** : rejeu sans délai (`static/js/offline.js:148-155`) attendu par la fin (`static/js/seance.js:910-911`). | Reproduit R1 | Bouton bloqué au sous-sol ; bilan et durée jamais envoyés. | `AbortController` au rejeu ; « Terminer » n'attend pas plus de 5 s puis met le bilan en file. |
| I4 | **Test dépendant du jour** (`tests/test_routes.py:807-815`). | Reproduit R10 | CI rouge le week-end et le lundi ; avec « Wait for CI », plus aucun déploiement ces jours-là. | Figer la date ou poser un planning cohérent avec l'écart. |
| I5 | **Catalogue tronqué par la fréquence** (`core/catalog.py:1088-1089`) et planning A-B-A figé (`:24-35`) contre des descriptions « A/B ». | Reproduit R3 | PPL à 2 j : pas de jambes ; Upper/Lower à 3 j : Lower B jamais. | Cycler les séances sur les jours (rotation), ne jamais en supprimer ; corriger les textes. |
| I6 | **Refaire l'onboarding efface les autres dossiers** (`routes/onboarding.py:180`). | Reproduit R4 | Un membre PRO perd « Salle », « Maison »… | `remplacer_programme_en_cours`, comme `change_program`. |
| I7 | **Doublons sur écritures croisées** : lire les id, insérer, supprimer, sans unicité (`core/db_historique.py:229-241`). Déclenché par une requête abandonnée à 8 s mais toujours en cours côté serveur, suivie de la série suivante. | Reproduit R9 | Volume, records et 1RM gonflés ; séries en double. | Index unique (user, date, séance, exercice, série) + upsert, ou RPC transactionnelle. |
| I8 | **Compteur « Séances x/y » faux** (`routes/accueil.py:314-315`). | Reproduit R5 | « 2/2 » après 3 séances ; « 3/9 » pour un multi-programmes. | Compter (date, séance) faits sur les séances planifiées de la semaine. |
| I9 | **Contexte du coach pauvre** : ni reps cibles, ni RPE, ni bilans, cardio en kilos (`routes/coach.py:112-175`), fonction supprimée décrite (`:54`). | Reproduit R7 | Conseils génériques sur la donnée qu'il a pourtant saisie. | Séparer le cardio, ajouter reps cibles, RPE moyens, derniers bilans. |
| I10 | **Promesses fausses sur la page PRO** (`templates/premium.html:110-111`, `:167`) et à l'onboarding (`templates/onboarding.html:477`). | Déduit | Il paie un « Badge VIP doré » qui n'existe pas ; un gratuit croit PPL réservé. | Aligner le texte sur le code ; ajouter le debrief. |
| I11 | **Serveur mono-processus** : 1 worker, 16 fils (`railway.json`) ; flux du coach et génération synchrone tiennent chacun un fil ; la justesse du cache en dépend (`core/db_base.py:106-112`). | Déduit | Pics : pages qui attendent un fil libre ; un redémarrage coupe tout le monde. | Génération en tâche de fond ; cache partagé (Redis, déjà prévu pour le limiteur) avant toute 2ᵉ instance. |
| I12 | **Renommer un exercice dans l'éditeur coupe son historique** (`routes/programme.py:190-310` ne touche pas `history`). | Déduit | « Première fois » sur un exercice qu'il fait depuis un an ; records perdus de vue. | Détecter le renommage et appeler `rename_exercise_rows`. |
| I13 | **Échecs encore avalés** : ajout de repas (`routes/nutrition.py:381-385`), retrait de cardio (`routes/seance_cardio.py:286-291`). | Déduit | Repas « ajouté » qui n'apparaît pas. | Message d'erreur et code 503. |
| I14 | **Couverture faible là où se jouent l'argent et les droits** : auth 34 %, admin 43 %, programme 48 %. | Mesuré | — | Tests des chemins CC2, I6, I12. |

#### Mineurs (16)

| # | Constat (preuves) | Impact | Correctif |
|---|---|---|---|
| M1 | Bilan écrasé par une 2ᵉ fin « Passer » (`routes/seance_fin.py:63-69`, `core/db_bilans.py:84-96`) — reproduit R6. | Note 5/5 et commentaire perdus. | N'écrire que les champs fournis. |
| M2 | Renommer une séance n'emporte pas `session_notes` (`routes/programme.py:416-417`) — reproduit R12. | Bilans orphelins. | `UPDATE session_notes` dans le renommage. |
| M3 | Semaines précédentes vides pour le poids du corps (`core/seance_historique.py:109-117`) — reproduit R8. | Pas d'historique visible pour pompes, tractions. | Filtrer sur `Reps > 0`. |
| M4 | Défi unique 10 000 kg (`core/challenges.py:73-76`). | Inatteignable pour un débutant, trivial pour un avancé. | Cible relative à ses 4 dernières semaines. |
| M5 | CSP bloquante sans `script-src` (`app.py:325-330`). | Une injection future s'exécuterait. | Passer la politique d'observation en bloquante, page par page. |
| M6 | AdMob : identifiants de test par défaut (`app.py:457-458`). | Aucun revenu si la variable manque. | Échouer bruyamment en production. |
| M7 | Webhook sans remboursement ni litige (`routes/billing.py:264-275`). | Un « à vie » remboursé reste PRO. | Traiter `charge.refunded`, `charge.dispute.created`. |
| M8 | Quota coach et générateur contournables en parallèle (`routes/coach.py:178-198`, `routes/generator.py:326-330`). | Coût API. | Incrément atomique côté SQL. |
| M9 | Reprise de séance au démarrage sur la date UTC (`templates/base.html:108`). | Ratée entre minuit et 2 h. | Date logique fournie par le serveur. |
| M10 | Reset « soft » sans confirmation serveur (`routes/gestion.py:422-464`), alors que le reset total en exige une (`:470`). | Historique effacé sur un POST. | Exiger `confirm=yes`. |
| M11 | Séries et séances non bornées dans l'éditeur (`routes/programme.py:230-235`). | Page inutilisable, blob gonflé. | Bornes comme à l'import (`routes/gestion.py:533`). |
| M12 | `static/promo-vip-poster.png` (1,1 Mo) référencé nulle part. | Poids du déploiement et du cache. | Supprimer. |
| M13 | Vidéo de 895 ko en lecture auto sur le mur et la page PRO (`templates/vip_wall.html:24`, `templates/premium.html:20`). | Données mobiles. | Lecture au tap, poster seul. |
| M14 | Funnel : l'étape « VIP » compte les VIP de tous les temps, les autres la fenêtre (`core/db_admin.py:211-226`). | Taux de conversion faux. | VIP activés dans la fenêtre (`vip_activated`). |
| M15 | Tonnage admin incluant le cardio (minutes × km) (`supabase_schema_v39_admin_stats.sql:19`). | Chiffre gonflé. | Exclure `exercice like 'CARDIO:%'`. |
| M16 | Commentaires périmés : « Les reps ne sont PAS stockées » (`core/catalog.py:7-8`), « sans rien effacer » (`routes/gestion.py:222`). | Induit en erreur le prochain lecteur. | Corriger. |

#### Synthèse par domaine demandé
- **Sécurité** : CC1, CC2, M5, M6. Webhook signé, service_role uniquement serveur, CSRF partout, secret cron en en-tête et comparaison à temps constant (`routes/push.py:25-38`) : corrects.
- **Intégrité des données** : I2, I3, I6, I7, M1, M2, I12. Croissance non bornée : `events` purgée à 13 mois **seulement si** le cron de relance tourne (`routes/push.py:111`) ; cache du service worker sans éviction entre deux déploiements.
- **Performance** : Q1 (requêtes), Q2 (poids), I11. Aucune compression HTTP côté app.
- **Qualité** : fichiers sous plafonds tenus par tests ; duplication résiduelle faible ; dépendances suivies par Dependabot (`.github/dependabot.yml`), `anthropic==0.39.0` encore épinglé ; I4, I14.

---

### Partie 4 — Améliorations et idées

#### A. Les 10 améliorations à impact maximal (triées par impact / effort)

| # | Problème | Correctif | Fichiers | Effort | Impact attendu · profil |
|---|---|---|---|---|---|
| 1 | RPE ignoré (I1) | Lire la colonne `RPE` dans `_recent_sessions_sets` ; test bout en bout | `core/seance_historique.py`, `tests/` | S | Suggestion enfin juste · avancé, intermédiaire |
| 2 | Test daté (I4) | Date figée dans le test | `tests/test_routes.py` | S | CI fiable 7 j/7 · développeur |
| 3 | Vérifications sécurité (CC1, CC2) | Exécuter les requêtes du § 7 ; admin = Google + `email_verified` ou liste d'`user_id` | `routes/auth.py`, `routes/admin.py` | S | Ferme deux portes critiques possibles |
| 4 | Placeholder piège (I2) | Pré-remplir reps et poids avec la dernière fois (sinon la cible) ; « Série faite » = 1 tap | `static/js/seance.js`, `templates/_seance_carte_exercice.html`, `core/seance_contexte.py` | S | Saisie au niveau Hevy · tous, surtout migrants |
| 5 | « Terminer » figé (I3) | Délai au rejeu ; fin non bloquante | `static/js/offline.js`, `static/js/seance.js`, test e2e | S | Sous-sol |
| 6 | Re-onboarding destructeur (I6) | `remplacer_programme_en_cours` | `routes/onboarding.py` | S | VIP multi-programmes |
| 7 | Promesses PRO (I10) | Texte aligné, debrief mis en avant | `templates/premium.html`, `templates/onboarding.html` | S | Conversion, risque légal |
| 8 | Compteur et coach (I8, I9) | Séances planifiées de la semaine ; contexte coach enrichi | `routes/accueil.py`, `routes/coach.py` | S-M | Débutant S3, VIP |
| 9 | Programmes amputés (I5) | Rotation réelle des séances sur les jours (A-B-A / B-A-B) | `core/catalog.py`, `routes/accueil.py`, `routes/seance.py` | M | Débutants (3 programmes gratuits sur 5 sont A/B) |
| 10 | Écritures non idempotentes (I7) | Index unique par série + upsert | migration v40, `core/db_historique.py` | M | Intégrité de toutes les statistiques |

#### B. 15 idées de fonctionnalités
« Inédit » = absent de Hevy, Strong et Fitbod **à ma connaissance** (non vérifiable d'ici, § 7).

| # | Idée | À qui | Pourquoi ça retient ou convertit | Complexité | Risque | Inédit |
|---|---|---|---|---|---|---|
| 1 | **Bilan → séance suivante** : « épaule qui tire » dans le bilan ; le coach propose la variante au prochain exercice concerné, un tap l'applique (calque du jour existant) | Tous | Le bilan devient utile ; argument PRO concret | M | Médical : rester dans le conseil d'exercice | Oui |
| 2 | **Debrief « Appliquer »** : le debrief pose les charges de la prochaine séance | PRO | Le coach agit, raison de rester au mois 3 | S-M | Bornes (+5 % max), annulable | Oui sous cette forme |
| 3 | **Touches de volume en salle** (natif) : volume + = valider la série, volume − = −1 rep | Une main, gants | Zéro regard sur l'écran | M | Conflit avec le son | Oui |
| 4 | **Photo de la machine → exercice** | Débutants | Lève l'angoisse du jour 1 | M | Erreur d'identification | Oui |
| 5 | **« Machine prise »** : un tap réordonne la séance pour passer à un exercice libre | Salles bondées | Moins d'abandon de séance | S | Faible | Oui |
| 6 | **Nutrition post-séance** liée aux plats de la semaine | PRO nutrition | Relie deux fonctions payantes | S-M | Faible | Oui (combinaison) |
| 7 | Import CSV Hevy / Strong | Migrants | Lève le premier frein à l'adoption | M | Formats variables | Non |
| 8 | Saisie vocale française (« cinq à cent ») | Salle | Mains libres | M | Bruit ambiant | Non |
| 9 | Récap du dimanche (push) : séances, tonnage, records, écart | Tous | Raconte la progression | S | Faible | Non |
| 10 | Décharge proposée (RPE en hausse, reps en baisse) | Intermédiaires, avancés | Évite plateau et abandon | M | Faux positifs | Non |
| 11 | Séries d'échauffement calculées (barre, 40 %, 60 %, 80 %) hors volume | Avancés | Indispensable en force | S-M | Faible | Non |
| 12 | Pack sous-sol : semaine entière gardée hors ligne + pastille « prêt » | Sous-sols | Transforme un défaut en promesse | S | Stockage | Non |
| 13 | Binôme de régularité (streak partagé) | Débutants | Responsabilité sociale, parrainage | M | Vie privée | Non |
| 14 | Défi relatif (+5 % de ton volume habituel) | Tous | Atteignable pour chacun | S | Faible | Non |
| 15 | Créneaux libres de l'agenda → rappel au bon moment | Actifs | Rappel pertinent | M | Permission agenda | Non |

#### C. Les 3 choses à supprimer
1. **Les verbes en double sur chaque carte** — « Enregistrer », « Recommencer cet exercice », « Réinitialiser les poids » (`templates/_seance_carte_exercice.html`), maintenant que « Série faite » écrit. Deux façons d'enregistrer, c'est deux modèles mentaux et l'écran le plus chargé de l'app.
2. **Le bloc « Récupération » en tête de séance** (`templates/seance_edit.html:78-79`, `core/seance_historique.py:141-163`) : un statut PRÊT / REPAR. calculé sur le seul nombre de jours, qui repousse le premier champ hors écran (Q3) sans rien changer à ce que l'utilisateur fait.
3. **Le « reset soft » et l'archive héritée** (`routes/gestion.py:422-464`, clés `_archive`, `_legacy_volume`, réinjectées dans les statistiques par `routes/progres.py:116-133`) : un mécanisme de l'époque Streamlit qui efface l'historique pour en garder un résumé dans le blob — dette et risque de perte, pour un besoin que l'export gratuit couvre.

#### D. Une seule action pour les 30 prochains jours
**Faire de « Série faite » un tap qui enregistre la bonne valeur, une seule fois, quel que soit le réseau** : valeurs pré-remplies réelles (I2), écriture idempotente par série (I7), fin de séance jamais bloquée (I3), et la suggestion qui lit enfin le RPE (I1, une ligne).
**Pourquoi** : c'est le seul geste que l'utilisateur répète vingt fois par séance, et tout le reste — suggestion, records, streak, défis, coach, debrief, donc la conversion — se nourrit de ce qu'il produit. Le 30/09, ce geste perdait des séances ; aujourd'hui il ne perd plus rien de ce qui est tapé, mais il demande plus d'effort que chez Hevy et il ment encore dans deux cas (placeholder, réseau faible). C'est aussi ce qui décide si l'intermédiaire venu de Hevy reste après sa première séance. Avant cela, dix minutes pour CC1 et CC2.

---

### 5. Suivi des constats du 30/09

**28 corrigés · 10 partiels · 0 laissés en l'état.**

| Repère (30/09) | Statut | Preuve dans le code |
|---|---|---|
| C1 Séries cochées effacées par « Terminer » | Corrigé | `static/js/seance.js:425-435`, `:892-915` ; `tests/e2e/test_seance_navigateur.py:125-152` |
| C2 L'essai ne peut pas acheter | Corrigé | `app.py:439-449`, `templates/premium.html:37-46`, `templates/plus.html:8-13` |
| C3 Suppression sans résiliation Stripe | Corrigé | `routes/gestion.py:489-500`, `core/stripe_client.py:399-419` |
| C4 XSS stockée console admin | Corrigé | `templates/admin.html:144-184` |
| I1 Poids/taille d'onboarding perdus | Corrigé | `templates/onboarding.html:411-412`, `routes/onboarding.py:136-158` |
| I2 GPS bloqué | Corrigé (comportement sur appareil invérifiable) | `app.py:366`, manifeste Android |
| I3 Semaine et streak faux | Corrigé | `routes/accueil.py:48-59`, `:283` |
| I4 Réseau faible | **Partiel** — nouveau blocage de « Terminer » (I3 ci-dessus) | `static/js/seance.js:46`, `static/service-worker.js:222-235` |
| I5 Skip sans confirmation | Corrigé | `routes/seance.py:459-468`, `static/js/seance.js:628-671` |
| I6 Cardio en séance écrasé | Corrigé | `routes/seance_cardio.py:258-269` |
| I7 Verrou optimiste entre fils | Corrigé | `core/db_programme.py:42-48` |
| I8 Cache par worker | Corrigé **par contrainte** (un seul processus) | `railway.json`, `core/db_base.py:106-112` |
| I9 Remplacement sans transaction | **Partiel** — ordre sûr, mais doublons (I7) | `core/db_historique.py:219-245` |
| I10 Webhook 200 sur échec | Corrigé | `routes/billing.py:276-283` |
| I11 Funnel faux | Corrigé | `core/analytics.py:19-31`, `routes/seance_fin.py:79-84`, `core/db_admin.py:13-25` |
| I12 Export payant, pages légales | Corrigé | `routes/gestion.py:550-596`, `templates/cgv.html`, `core/db_admin.py:341` |
| I13 Suggestion et repos à contresens | **Partiel** — fourchette et repos corrigés, RPE jamais lu (I1) | `core/seance_historique.py:198`, `:210-227` |
| I14 Relances mal ciblées | Corrigé | `core/reminders.py`, `core/push.py:94-106`, `routes/accueil.py:520-528`, `core/challenges.py:42-53` |
| I15 Coût d'un enregistrement, poids des pages | **Partiel** — 3 requêtes, mais 180 et 215 ko | mesures Q1, Q2 |
| I16 Adoption destructrice | **Partiel** — re-onboarding encore destructeur (I6) | `routes/onboarding.py:180` |
| I17 Pub « App Open » en séance | Corrigé (sauf avant la 1ʳᵉ série) | `MainApplication.java`, `static/js/seance.js:98-114` |
| I18 Tutoriel périmé | Corrigé | `static/js/tuto-seance.js:26-75` |
| I19 Vue lisible avec la clé anon | Corrigé dans le dépôt (application invérifiable) | `supabase_schema_v37_user_last_activity_droits.sql` |
| I20 Fiche admin cassée | Corrigé | `templates/admin.html:144-150` |
| I21 File bloquée ou purgée | Corrigé (rejets jamais revus) | `static/js/offline.js:142-177`, `:287-305` |
| I22 Fuite fournisseur au générateur | Corrigé | `routes/generator.py:377-389` |
| M1 supabase-js depuis un CDN | Corrigé | `templates/login.html:57` |
| M2 Exceptions renvoyées au client | Corrigé | `routes/auth.py:102-111` |
| M3 Déconnexion en GET | Corrigé | `routes/auth.py:132` |
| M4 Duplication, code mort | Corrigé | `routes/progres.py:105-112` |
| M5 `events` sans rétention | Corrigé si le cron tourne | `core/db_admin.py:127-133`, `routes/push.py:111` |
| M6 Lectures globales | Corrigé | `supabase_schema_v39_admin_stats.sql`, `core/db_admin.py:71-86` |
| M7 Rechargement après déploiement | **Partiel** — plus sur `/seance`, modale de nouveautés au passage suivant | `static/js/sw-register.js` |
| M8 « Commencer » vers une liste | Corrigé | `templates/accueil.html` (lien `mode=prefaite`) |
| M9 Styles inline, chevauchements | **Partiel** — 63 `style=`, e-mail toujours en tête | `templates/base.html:122-127` |
| M10 Dépendances figées | Corrigé | `.github/dependabot.yml` |
| M11 Fichiers volumineux, médias morts | **Partiel** — poster de 1,1 Mo non référencé | `static/promo-vip-poster.png` |
| M12 Textes | **Partiel** — « Soutiens le créateur » | `templates/premium.html:166` |

---

### 6. Écarts entre la doc et le code

| La doc affirme | Le code dit |
|---|---|
| `CONTEXT.md:11` — « gunicorn `-k gthread --threads 8` » | `railway.json` : `--workers 1 --threads 16` ; `CONTEXT.md:491` dit lui-même 16. |
| `CONTEXT.md:313` — export « gated VIP » | Export gratuit (`routes/gestion.py:550-556`) ; `CONTEXT.md:172` dit l'inverse de `:313`. |
| `CONTEXT.md:377` — dernières migrations v34-v36 | v37, v38, v39 existent et conditionnent la sécurité (`supabase_schema_v37…`, `v38…`, `v39…`). |
| `CONTEXT.md:422` — « neuf autres imports entre blueprints subsistent » | Cinq (`routes/gestion.py:519`, `routes/onboarding.py:199`, `routes/premium.py:15`, `routes/programme.py:263`, `routes/progres.py:415`). |
| `CONTEXT.md:498` — « le RPE est lu depuis le token `@RPE8` de la remarque » | Exact, et c'est le défaut : depuis la v34 le RPE est écrit dans la colonne `rpe` (`core/seance_saisie.py:105`, `core/db_historique.py:203`), jamais dans la remarque. |
| `CONTEXT.md:521` — « pytest (306) puis node (31) » ; `:380` « ≈ 870 tests » | 884 tests Python collectés, 100 JS. |
| `CONTEXT.md:10` — « network-first sur les pages » | Copie en cache servie après 3,5 s si elle existe (`static/service-worker.js:222-235`). |
| `CONTEXT.md:531` — base `v123` | `const CACHE_VERSION = "v127"` (`static/service-worker.js:6`). |
| `CONTEXT.md:541` — profils d'entraînement retirés | Le prompt du coach les décrit (`routes/coach.py:54`) ; la page PRO les vend (`templates/premium.html:111`). |
| `core/catalog.py:7-8` — « Les reps ne sont PAS stockées » | `build_program` les stocke (`core/catalog.py:1107-1111`). |
| `core/catalog.py:57`, `:89`, `:121`, `:573` — séances « alternées (A/B) » | Planning fixe A-B-A chaque semaine (`core/catalog.py:24-35`). |
| `templates/onboarding.html:462-467` — « amené directement dans l'éditeur » | Redirection vers l'accueil (`routes/onboarding.py:195`). |
| `templates/onboarding.html:477`, `templates/premium.html:110` — PPL et Upper/Lower réservés PRO | `ppl_deb_3j` et `upper_lower_4j` sont gratuits (`core/catalog.py:855-861`). |
| `templates/premium.html:167` — « Badge VIP doré » | Aucun badge distinct : `badge-pro` pour tous (`templates/base.html:123`). |
| `routes/gestion.py:222` — refaire l'onboarding « sans rien effacer » | Efface séances et dossiers des autres programmes (R4). |
| `static/js/tuto-seance.js:75` — « rien ne se perd » | Vrai pour les séries ; faux pour le bilan en réseau faible (R1). |

---

### 7. Non vérifiable depuis le dépôt

1. **Migrations v37, v38, v39 réellement appliquées — à vérifier en premier (CC1).** Dans l'éditeur SQL de Supabase :
   ```sql
   select schemaname, tablename, policyname from pg_policies where schemaname = 'public';
   select table_name, grantee from information_schema.role_table_grants
    where table_schema = 'public' and grantee in ('anon', 'authenticated');
   ```
   Les deux doivent renvoyer 0 ligne.
2. **Configuration Auth de Supabase (CC2)** : fournisseur e-mail activé ou non, confirmation d'e-mail obligatoire ou non, inscriptions ouvertes ou non.
3. **Railway** : nombre d'instances (la justesse du cache exige 1), option « Wait for CI », variables `ADMOB_BANNER_ID` / `ADMOB_INTERSTITIAL_ID`, `HIDE_NATIVE_BILLING`, `CRON_SECRET`, `REDIS_URL`, `SENTRY_DSN`, `ANTHROPIC_API_KEY` ; compression HTTP éventuelle en périphérie (l'app n'en fait pas).
4. **Tâches planifiées** appelant `/tasks/reminders` (chaque heure) et `/tasks/reactivation` : rien dans le dépôt ne les déclenche ; sans elles, ni rappels, ni relances, ni purge des `events`.
5. **Stripe** : événements abonnés au webhook, résiliation immédiate ou en fin de période dans le portail, remboursements.
6. **Comportement sur appareil** : invite de géolocalisation relayée par la webview Capacitor, notifications locales du repos, moment réel de la pub « App Open », démarrage à froid hors ligne (aucun `errorPath` dans `capacitor.config.json`).
7. **Volumétrie et latence réelles** Railway ↔ Supabase, qui fixent le coût réel des 5 à 7 requêtes d'un premier affichage.
8. **Concurrents** : fonctions et prix cités de mémoire (état 2025 : Hevy Pro ≈ 3 $/mois, Strong Pro ≈ 5 $/mois, Fitbod ≈ 16 $/mois ; valeur grisée validée d'un tap, supersets, import CSV chez Hevy/Strong). À revérifier ; les mentions « inédit » en dépendent.
9. **Distribution de l'APK** (Play Store ou installation manuelle), qui décide si `HIDE_NATIVE_BILLING` doit être posé.
10. **Politique d'Anthropic** sur l'usage des données d'API, citée par la politique de confidentialité.

---

### 8. Annexe — reproductions et mesures

**Environnement** : copie du dépôt hors dépôt, Python 3.11, `requirements.txt` + `requirements-dev.txt`, fausse base `tests/conftest.py`, serveur `run_local_fake.py`, Chromium headless (Playwright 1.60, alias vers le binaire installé) en 375 × 812, locale fr-FR. Date réelle : samedi 03/10/2026.

| Repère | Scénario | Résultat observé |
|---|---|---|
| R1 | Navigateur : `/seance/save-exo` ne répond plus ; une série validée part en file ; « Terminer » → « Enregistrer la séance » | File : 1. Après 30 s : bouton « Enregistrement… », toujours sur `/seance` |
| R2 | Navigateur, compte neuf : champ Reps vide (placeholder « 5 »), « Série faite » | Série repliée « 1 · — » ; **0 ligne** en base ; aucun message |
| R3 | `build_program` du catalogue à différentes fréquences | PPL 3 j @ 2 j : `Push, Pull` ; Upper/Lower 4 j @ 3 j : `Upper A, Lower A, Upper B` ; Full Body @ 3 j : `A, B, A` |
| R4 | Programme à deux dossiers (Salle, Maison) ; « Refaire l'onboarding » ; choix « Full Body Débutant » | Séances : `Full Body A, Full Body B` ; `_programmes` : absent ; badges conservés |
| R5 | Full Body A/B planifié L/Me/V, trois séances faites cette semaine, accueil | « SÉANCES 2/2 · VOLUME 1 440 kg cette semaine » |
| R6 | Fin de séance notée 5/5 + commentaire, puis seconde fin « Passer » | `(5, 'Super séance, PR au DC', 55)` → `(None, None, 62)` |
| R7 | `_dernieres_seances` / `_programme_detail` du coach | « CARDIO:Course 1s @5kg … (vol 790kg) » ; « Squat (5 séries) », sans reps ni repos |
| R8 | Semaines précédentes, pompes à 0 kg la semaine dernière | Pompes : `[]` ; développé couché : semaine trouvée |
| R9 | Deux `replace_exo_rows` du même exercice qui se croisent (2 puis 3 séries) | 5 lignes : séries 1 et 2 en double |
| R10 | `test_reactivation_nudge_after_inactivity` avec la date figée sur chaque jour du 28/09 au 04/10 | Échoue lundi, samedi, dimanche ; passe mardi-vendredi |
| R11 | `POST /seance/save-exo` : 3 × 8 à 100 kg, RPE 10, programme 8-12 ; suggestion suivante | Colonne `rpe` = 10 ; suggestion « Même charge, vise 9 reps » (`add_rep`) ; la règle avec le RPE donnerait « Consolide » (`rpe_high`) |
| R12 | Renommer « Push » en « Pecs/Épaules » | `history.seance` = « Pecs/Épaules » ; `session_notes.seance` = « Push » |
| Q1 | Requêtes Supabase par page, 2 617 séries (un an de PPL 3 j), froid / chaud | Accueil 7/1 · Séance (choix) 4/0 · Séance Push 5/1 · Progrès 7/1 · Programme 2/1 · Nutrition 4/2 · Coach 3/1 · Gestion 5/0 · « Série faite » 6/3 |
| Q2 | Poids HTML PRO / gratuit, et temps de rendu | Accueil 27/29 ko · Séance (5 exercices) 180/181 ko (21 ko compressé), ≈ 100 ms à chaud · Progrès 90/39 ko · Programme 215/202 ko · Nutrition 91/22 ko (+ vidéo 895 ko en gratuit) |
| Q3 | Position du premier champ de reps, 375 × 812 | Compte neuf : 836 px (page 2 414 px) ; avec historique : carte à 598 px, champ à 1 355 px (page 4 314 px pour 3 exercices) |
