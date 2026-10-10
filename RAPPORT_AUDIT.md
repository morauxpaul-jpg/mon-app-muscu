# RAPPORT D'AUDIT — Muscu Tracker PRO

## Mise à jour du 10/10/2026 — v48 appliquée, réponses du propriétaire · note inchangée : **6,6 / 10**

| Repère | Statut | Preuve |
|---|---|---|
| m1, m3 | **Corrigé en production** : v48 appliquée le 10/10 à 11:46 UTC (accord explicite du propriétaire) | `list_migrations` : `20261010114603 v48_durcissement` ; SQL : `execute` sur `handle_new_user()` = false pour `anon`, `authenticated`, `public` ; 0 programme avec `_profiles`/`_active_profile` (9 avant), somme de leurs versions 318 → 327 ; déclencheur `on_auth_user_created` actif ; `get_advisors` : alertes 0028/0029 disparues |
| I-5 0 activation PRO | **Pas un défaut** : les 3 paiements commencés étaient des essais du propriétaire (dit le 10/10) | déclaration du propriétaire |
| m4 Variables Railway avec espaces | **Corrigé** par le propriétaire | `describe-service` : `SUPABASE_URL` et `SUPABASE_ANON_KEY` sans espace ; redéploiement du 10/10 à 11:44 UTC réussi |
| m2 Mots de passe fuités | **Reste ouvert**, à trancher par le propriétaire. Le seul compte e-mail est le sien, et il a aussi Google ; l'app ne propose que Google. La protection Supabase est réservée à l'offre Pro | `auth.identities` : google 15, email 1 ; `templates/login.html` (Google seulement) |

Inscription après la v48 : PostgreSQL ne vérifie le droit `execute` d'une fonction de déclencheur qu'à la création du déclencheur ; rejoué en local. La prochaine inscription réelle le confirmera en production (ligne `profiles` créée).

## Suivi du 09/10/2026 — corrections sur la branche de la PR #36 · note inchangée : **6,6 / 10**

**Ce qui change en production** : seulement la **v29**, appliquée le 09/10 à 21:55 UTC (`list_migrations` : `20261009215501 v29_referral`) et vérifiée (`information_schema` : `referral_code`, `referred_by`, `vip_until` présentes). Tout le reste est du code sur la branche `claude/nifty-hawking-0natha`, **ni fusionné ni déployé**. La note n'est pas relevée : elle le sera après déploiement, sur preuves en production.

| Repère | Statut | Preuve |
|---|---|---|
| C1 v29 absente | **Corrigé en production** (v29) ; contrôle du schéma au démarrage sur la branche (`core/schema.py`, journal ERREUR + carte /admin) | SQL ci-dessus ; `tests/test_schema.py` (17 tests) |
| I-1 Séance d'un autre jour | Sur la branche : la carte « Demain » ouvre la séance **d'aujourd'hui** (« Faire maintenant », bandeau « EN AVANCE ») ; page gardée hors ligne ramenée à aujourd'hui (`static/js/jour-seance.js`) ; dates futures refusées par `save-exo`, `add-cardio`, `cardio/save`, `finish` | `tests/test_seance_a_venir.py` (13), `tests/js/test_jour_seance.js` (6), test navigateur `test_la_seance_de_demain_senregistre_aujourdhui` |
| I-2 Latence ×2,4 | **Pas corrigé** : cause non isolable hors production. Mesure ajoutée : en-tête `Server-Timing` (base / redis / total) et journal « lent : … » dès 800 ms (`core/chrono.py`) | `tests/test_reprise_base.py` (partie mesure) |
| I-3 Coupure de connexion | Sur la branche : une **lecture** coupée (`ConnectionTerminated`…) est retentée une fois ; jamais une écriture (`core/reprise_base.py`) | `tests/test_reprise_base.py` (16 au total), dont un passage par le vrai client PostgREST |
| I-4 Tests aveugles au schéma | Sur la branche : la fausse base refuse une colonne inconnue comme PostgREST (42703 / PGRST204). Elle a trouvé 5 fichiers de tests qui écrivaient `series` au lieu de `serie` | `tests/conftest.py`, `tests/test_schema.py` |
| I-5 0 activation PRO | **Non traité** : demande l'accès Stripe | — |
| m1 `handle_new_user()` exécutable | **v48 écrite, pas appliquée** (attend ton accord). Rejouée sur un PostgreSQL 16 local : droit retiré, inscription intacte, idempotente | `pwa/supabase_schema_v48_durcissement.sql` |
| m3 `_profiles` dans 9 programmes | Même v48 (version du programme incrémentée) | idem |
| m2, m4 | **À faire par toi** (Supabase Auth ; noms des variables Railway) | — |
| m5 Journaux « error » | Sur la branche : INFO sur la sortie standard, WARNING+ sur la sortie d'erreur | `tests/test_journaux.py` ; processus réel : INFO sur stdout, ERROR et CRITICAL sur stderr |
| m8 « Séance terminée 💪 » à vide | Sur la branche : « Terminer sans série ? » + avertissement | `tests/js/test_petits_correctifs.js` |
| m9 Tutoriel | Sur la branche : la dernière bulle désigne la carte « Prochaine séance », qui ouvre la séance dès aujourd'hui | relu dans `static/js/tutorial.js` |
| m10 Barre vide non pré-remplie | Sur la branche : 20 kg pré-remplis la première fois sur un mouvement à la barre ; la charge passe aussi à la série suivante vide | `tests/test_premiere_seance.py` (6), `tests/js/test_petits_correctifs.js`, test navigateur `test_premiere_fois_a_la_barre_…` |
| m11 Doc en retard | Sur la branche : `CONTEXT.md` corrigé (10 écarts de Z.5) et complété | diff de la PR |
| m6, m7, m12 | Non traités | — |

**Trouvé en route** : les tests navigateur finissaient en **429** (trop de requêtes) au 17e test : tous viennent de la même adresse et la limite est de 60 par minute. Le serveur de test tourne désormais sans limite (`SANS_LIMITE=1`, `run_local_fake.py` seulement).

**Tests au 09/10** : 1 349 tests Python passent (dont 25 navigateur), les mêmes sur Redis simulé (`PARTAGE_TEST=fakeredis`, 1 324 hors navigateur), et 127 tests JS. Les tests de la charge de 20 kg et de la recopie ont été vus **échouer** sans leur correctif.

---

## Audit complet du 06/10/2026 (après-midi) · commit `8916176` · **6,6 / 10** (132 / 20)

**Commit audité** : `8916176` (tête de `main`, CI verte, déployé sur Railway le 06/10 à 14:02 UTC). Le code applicatif est celui de `b09989a` (PR #34) ; `8916176` n'ajoute que le rapport précédent.
**Note précédente** : 6,9 (138 / 20), même code. **Historique** : 4,9 (30/09) → 5,6 (03/10) → 6,5 → 6,7 → 6,8 → 6,8 → 6,9 (04/10) → 6,9 (05/10, trois mises à jour) → 6,9 (06/10, deux mises à jour) → **6,6** (06/10, cet audit).
**Auditeur** : audit indépendant des corrections, lecture seule partout (aucune écriture en base, aucune migration, aucun déploiement, rien poussé sur `main`).

> **Verdict.** Le code n'a pas régressé : 1 270 tests Python, 23 tests navigateur et 113 tests JS passent, sur les sept jours de la semaine, avec 85 % de couverture. La note baisse parce que cet audit a confronté l'app à la **production**, ce que les précédents n'avaient fait que pour les migrations récentes. Quatre constats : (1) **la migration v29 n'a jamais été appliquée** — l'essai PRO et le parrainage n'existent pas en production, alors que l'onglet Plus promet à chaque utilisateur des jours PRO pour un ami invité ; (2) **aucun paiement n'a jamais été enregistré** (0 activation PRO depuis le 14/06, pour 3 paiements commencés) ; (3) **« Série faite » met 2 s côté serveur** (0,85 s le 29/09) ; (4) la carte « Prochaine séance · Demain » fait **enregistrer une séance à la date du lendemain**, ce qui est arrivé en vrai le 04/10. Aucune donnée n'est perdue, tout se corrige vite, mais le barème note ce qui est prouvé : 6,6.

| Bloc | 30/09 | 03/10 | 06/10 (précédent) | **Aujourd'hui** | Écart |
|---|---:|---:|---:|---:|---:|
| Produit (axes 1 à 8) | 5,0 | 5,4 | 6,9 | **6,8** | −0,1 |
| Plateforme (axes 9 à 12) | 4,8 | 5,5 | 6,8 | **6,5** | −0,3 |
| Technique (axes 13 à 17) | 5,0 | 5,6 | 7,0 | **6,6** | −0,4 |
| Business (axes 18 à 20) | 4,7 | 6,0 | 7,0 | **6,3** | −0,7 |
| **Global (20 axes)** | 4,9 | 5,6 | 6,9 | **6,6** | **−0,3** |

**Constats de cet audit** : 1 critique · 5 importants · 12 mineurs, chacun avec sa reproduction (annexe Z). Des 45 constats suivis des audits précédents (I1-I14, M1-M16, F1-F5, U1-U10), 39 sont corrigés et tenus par les tests, 3 ne sont corrigés que dans le code, sans preuve en production (I11 sur un seul processus, I12 et U4 sans aucune série réelle depuis), 1 est ouvert (M5), 1 non reproduit (U5) et 1 reste à mesurer sur le téléphone (U7).

### Lexique minimal

- **Production** : l'app réelle, sur Railway (le serveur) et Supabase (la base de données).
- **Migration** : un script qui modifie la structure de la base (ajoute une colonne, une table). Le code la suppose appliquée ; si elle ne l'est pas, ce qui en dépend ne marche pas.
- **Fausse base** : la base simulée en mémoire qu'utilisent les tests ; elle ne vérifie pas que les colonnes existent.
- **Médiane** : la valeur du milieu ; la moitié des mesures est au-dessus, l'autre en dessous.
- **Cron** : un service externe qui appelle l'app à heure fixe (ici, toutes les heures) pour envoyer rappels et relances.
- **RLS** : verrou de la base qui empêche un navigateur de lire les tables directement.

---

### Z.0 Corrections de l'audit précédent (règle 6)

| # | Ce que disait l'audit précédent | Ce qui est vrai | Preuve | Gravité |
|---|---|---|---|---|
| E1 | Profil « Essai » noté 6/10 ; monétisation notée 7 grâce à « l'essai qui montre coach et debrief » ; parrainage décrit comme fonctionnel (CONTEXT.md, § Parrainage). | **La migration v29 n'est pas en base** : `profiles` n'a ni `vip_until`, ni `referral_code`, ni `referred_by`. Aucun essai n'a jamais pu exister en production, et le parrainage ne crédite rien. Les audits du 03 au 06/10 ont vérifié v37 à v47 en base, jamais v29. | SQL Z.4-a et Z.4-b ; reproduction RB | **Majeure** : deux notes surévaluées (monétisation, profil essai) |
| E2 | « Le blob ne garde plus que des clés de programme (`_planning`, `_programmes`, `_profiles`, …) » (§ A.1, v47). | `_profiles` (9 programmes) et `_active_profile` (9) sont les restes d'une fonction **retirée le 01/10** ; aucun code ne les lit. | SQL Z.4-c ; `grep` Z.5 | Mineure |
| E3 | « Les dernières séries de musculation datent du 04/10, avant la v42 » (§ A.6). | 9 séries ont été écrites **après** la migration v42 (17:14:44 UTC) mais **avant** que le code v42 soit en ligne (ancien déploiement retiré à 17:21:13 UTC). Conclusion inchangée : pas de bug, aucune série réelle avec identifiant. | SQL Z.4-d ; déploiements Railway Z.6 | Précision |
| E4 | « Cron horaire : non vérifiable » (§ A.6). | **Vérifié** : cron-job.org appelle `/tasks/reminders` toutes les heures ; 39 appels sur les 39 dernières heures, tous en 200. | Journaux HTTP Railway Z.6 | Levée d'une réserve |
| E5 | « Redis ajouté et branché… journal relu après le redémarrage du 05/10 » (§ A.6). | Redis est actif depuis le **04/10 à 13:58 UTC** (journal « partage: stockage redis »), avec une interruption de 12 min le 05/10 (07:02-07:15 UTC, démarrage en « stockage memoire »). | Journaux de déploiement Z.6 | Précision |
| E6 | Instruction d'audit : `cd pwa && pip install -r requirements.txt -r requirements-dev.txt`. | Les deux fichiers sont **à la racine** du dépôt ; la commande échoue telle quelle. | `ls` Z.1 | Doc |

---

### Z.1 Méthode et exécution

- **Environnement** : Python 3.11 (comme `runtime.txt`, dans un environnement isolé), Node 22, dépendances installées depuis la racine. Chromium préinstallé en version 1194, alors que Playwright 1.60 attend la 1223 : les tests navigateur se sont d'abord **ignorés** (23 « skipped »), puis ont tourné via un alias vers le binaire installé (hors dépôt).
- **Résultats** :

| Commande | Résultat | Avant (06/10) |
|---|---|---|
| `python -c "import app"` sans aucune variable | OK (journal CRITICAL « FLASK_SECRET_KEY absente — clé de DEV », stockage mémoire, 1 processus) | OK |
| `python -m pytest tests -q --ignore=tests/e2e` | **1 270 passés** en 33 s | 1 270 |
| `pytest --cov=core --cov=routes` | **85 %** (9 506 lignes, 1 461 non couvertes) | 81 % (mesuré sur `345334c`) |
| `python -m pytest tests/e2e` | **23 passés** en 100 s (avec l'alias Chromium) | 23 |
| `node tests/js/run.js` | **113 passés** | 113 |
| Suite figée sur chaque jour du lundi 05/10 au dimanche 11/10 | **1 270 passés × 7** ; date vue par l'app vérifiée (`2026-10-10`, `2026-10-11`) | verte |
| CI GitHub « Tests » sur `8916176` | **succès** (run 181, 06/10 13:57 UTC) | succès |

- **Parcours navigateur** : serveur local sur fausse base (`run_local_fake.py`) + un décor par profil daté d'aujourd'hui, Chromium 375 × 812, locale fr-FR ; 43 captures. Scripts hors dépôt.
- **Production, lecture seule** : Supabase (`list_tables`, `list_migrations`, `get_advisors`, 14 requêtes `select`), Railway (service, variables par nom, déploiements, journaux de 48 h, journaux HTTP, latences sur 7 jours), GitHub Actions.
- **Barème** : 10 = état de l'art · 8-9 = niveau Hevy/Strong **prouvé** · 6-7 = correct, un concurrent fait mieux · 4-5 = utilisable mais faible · 1-3 = cassé ou absent.

---

### Z.2 Vérifications en production (chiffres réels)

**1. Schéma**
- 14 tables, **RLS active sur les 14**, **0 règle** (`pg_policies`), **0 droit** `anon`/`authenticated` (`information_schema.role_table_grants`) — dont `history`, `programs`, `reglages`, `calques_seance`, `etat_compte`, `session_notes`, `nutrition`, `profiles`.
- Vues `user_last_activity` et `admin_history_stats` : `security_invoker=true`.
- Index `history_serie_unique (user_id, date, seance, exercice, serie)` : présent.
- Contraintes v43 (`history_type_serie_check`) et v44 (`history_cardio_colonnes_check`) : présentes ; contraintes v45-v47 aussi (heure de rappel, types JSON, compteurs ≥ 0).
- Historique Supabase des migrations : v40 à v47 seulement (les précédentes passées à la main).
- **Colonnes attendues par le code, migration par migration (v23 → v44)** : 31 présentes sur 34. **Manquent les 3 colonnes de la v29** (`referral_code`, `referred_by`, `vip_until`).

**2. `programs.data`** — 15 programmes, 25,9 ko au total (4,1 ko au plus). Clés `_x` : `_planning` 14, `_started_at` 14, `_origin` 10, `_active_profile` 9, `_profiles` 9, `_programmes` 8, `_seance_prog` 8, `_equipement` 6, `_equipment_details` 6, `_name` 5, `_rotation` 1. Plus aucune clé d'état (`_settings`, `_badges`, `_extras`, `_archive`…). **Résidus** : `_profiles` et `_active_profile` (fonction retirée le 01/10, lues nulle part). 257 exercices dans les programmes, 33 avec un `id` gravé (1 programme) — le code calcule l'identifiant à la lecture, ce n'est pas un obstacle.

**3. Séries réelles depuis la v42** — 1 169 lignes au total ; **0 avec `exercise_id`, 0 avec `type_serie`**. Dernière série de musculation : 04/10 à 17:18:29 UTC, écrite par l'ancien code (voir E3). Aucune séance de musculation depuis : **pas de bug à reproduire**, mais pas de preuve non plus.

**4. Cardio** — 2 lignes réelles au format v44, toutes deux avec `reps = poids = 0` : vélo du 04/10 (10 min, 2,47 km, 115 kcal, 14,82 km/h) et vélo du 05/10 (9 min, 2,26 km, 103 kcal, 15,07 km/h). **Aucune durée décimale** encore : la PR #34 est en ligne depuis le 06/10 à 14:02 UTC et aucun cardio n'a été saisi depuis.

**5. Cohérence** — 0 doublon de série ; 0 ligne orpheline dans les 14 tables (aucune ligne d'un compte supprimé) ; 0 bilan sans séance ; 0 `etat_compte` sans programme ; 0 message de coach sans conversation ; 0 série sans `session_id`. 193 lignes « 0 rep × 0 kg » (séries passées, par conception) et 2 vieilles lignes `SESSION`. **Anomalie** : 2 séries « Push 1 » **datées du 05/10 écrites le 04/10 à 15:57 UTC** (17:57 à Paris), copies des deux premières séries du 04/10 → bug I-1 ci-dessous.

**6. Usage (chiffres bruts)** — 15 comptes (14 Google, 1 e-mail) ; **dernière inscription le 01/07** ; 0 inscription en 30 jours. Comptes avec une séance : **2 sur 7 jours, 2 sur 30 jours**. Séances : 6 sur 7 jours, 18 sur 30 jours (16 de musculation) ; par semaine depuis le 10/08 : 2, 3, 4, 5, 2, 6, 4, 4, 2. Événements sur 30 jours : 13 séances terminées, 4 debriefs, 1 programme généré, 0 message au coach (10 depuis juin), 17 rappels, 29 relances, 3 défis validés, 20 pages PRO vues, 2 paiements commencés. **Essais PRO démarrés : impossible (colonne absente). Paiements convertis : 0 `vip_activated` depuis le 14/06** (3 `checkout_started` pour 2 comptes ; 2 clients Stripe). 8 profils ont `tier = 'vip'`, aucun avec un événement d'activation.

**7. Railway** — service `web`, 1 réplique (europe-west4), dernier déploiement `e38cc588` (commit `8916176`) réussi le 06/10 à 14:02 UTC ; « Wait for CI » actif (`checkSuites: true` ; les PR #24 et #25 avaient été ignorées sur CI rouge). Journal de démarrage : gunicorn « gthread », **1 processus**, Redis pour le limiteur et l'état partagé. **`WEB_CONCURRENCY` : absente** des variables (21 noms listés). Erreurs sur 48 h : **3 078 requêtes, 1 réponse 5xx** (`/seance` en 503 le 05/10 à 06:26 UTC, cause : `ConnectionTerminated` vers Supabase) et 1 avertissement Open Food Facts (produit inconnu, 404). Les journaux INFO sortent tous étiquetés « error » (sortie d'erreur).

**8. Alertes Supabase** (`get_advisors`)

| Alerte | Niveau | Classement |
|---|---|---|
| `rls_enabled_no_policy` × 14 | INFO | **Voulu** : tables fermées au navigateur (v38) |
| `handle_new_user()` exécutable par `anon` et `authenticated` (SECURITY DEFINER) | WARN | **Mineur** : c'est un déclencheur (`returns trigger`), qui refuse un appel direct ; à fermer quand même (`revoke execute`) |
| Protection contre les mots de passe fuités désactivée | WARN | **Mineur** : un compte e-mail existe (09/04) ; si l'inscription par e-mail est ouverte, l'activer ou fermer l'e-mail |
| `profiles_stripe_customer_idx`, `history_session_idx` jamais utilisés | INFO | **Négligeable** (peu de trafic) |

---

### Partie 1 — Les 20 axes

| # | Axe | 03/10 | 06/10 (préc.) | **Aujourd'hui** | Écart | En une phrase |
|---|---|---:|---:|---:|---:|---|
| 1 | Onboarding | 5 | 7 | **6** | −1 | Quatre étapes claires, mais un jour sans séance prévue, la seule action proposée ouvre la séance de demain. |
| 2 | Saisie de séance | 5 | 7 | **7** | 0 | Un tap coche, lance le repos et enregistre en arrière-plan ; mais une séance future s'enregistre sans garde. |
| 3 | Programme et planning | 5 | 7 | **7** | 0 | Rotation, éditeur borné, supersets ; la « prochaine séance » ignore l'envie de s'entraîner aujourd'hui. |
| 4 | Progression et statistiques | 6 | 7 | **7** | 0 | Progrès racontés, séries par muscle, streak ; graphiques moins riches que Strong. |
| 5 | Coach IA | 6 | 7 | **7** | 0 | Contexte riche et testé ; 0 message réel en 30 jours, et l'ouverture « à l'essai » n'existe pas en production. |
| 6 | Générateur IA | 5 | 7 | **7** | 0 | Tâche de fond fiable (testée) ; 1 génération réelle en 30 jours. |
| 7 | Nutrition | 5 | 7 | **7** | 0 | Repas par aliment, cibles reliées aux séances ; 21 lignes en base, pas de recettes ni de cible adaptative. |
| 8 | Cardio | 6 | 6 | **6** | 0 | Colonnes v44 constatées sur 2 vrais cardios ; pas encore de durée en secondes réelle, pas de zones cardiaques. |
| 9 | Hors-ligne | 5 | 7 | **7** | 0 | Rejoué en mode avion : rien ne se perd, « Terminer » rend la main en 7,6 s. |
| 10 | Notifications et relances | 6 | 7 | **7** | 0 | Cron enfin prouvé (39 appels sur 39 h) ; 3 abonnés push seulement, effet non mesuré. |
| 11 | Design et cohérence UI | 5 | 6 | **6** | 0 | Belles cartes illustrées ; e-mail en tête de chaque page et quatre verbes par carte. |
| 12 | Performance ressentie | 6 | 7 | **6** | −1 | Pages légères, mais en production « Série faite » prend 2 s côté serveur et l'accueil 1,2 à 1,8 s. |
| 13 | Architecture du code | 6 | 7 | **7** | 0 | Modules petits et testés ; replis silencieux qui cachent une migration oubliée. |
| 14 | Modèle de données | 4 | 7 | **7** | 0 | Propre et vérifié en base ; la preuve demandée pour 8 (une série avec identifiant) n'existe toujours pas. |
| 15 | Sécurité | 6 | 7 | **7** | 0 | Base fermée au navigateur, webhook signé, admin Google ; CSP permissive, deux alertes Supabase mineures. |
| 16 | Robustesse | 6 | 7 | **6** | −1 | Une seule 5xx en 48 h, mais aucune nouvelle tentative sur coupure, et une colonne manquante passe inaperçue des mois. |
| 17 | Tests | 6 | 7 | **6** | −1 | 1 406 tests verts et 85 % de couverture, mais la fausse base a laissé passer une fonction morte en production. |
| 18 | Monétisation et paywall | 5 | 7 | **5** | −2 | Paiement et paywall en place, mais 0 activation enregistrée et un essai qui n'existe pas. |
| 19 | Rétention | 6 | 7 | **7** | 0 | Rappels, relances, défis et récap tournent vraiment ; 2 comptes actifs, aucune dimension sociale. |
| 20 | Accessibilité | 7 | 7 | **7** | 0 | Contrastes, cibles et noms accessibles testés ; jamais essayé avec un vrai lecteur d'écran. |

Total **132 / 20 = 6,6**. Produit 54/8 = 6,75 · Plateforme 26/4 = 6,5 · Technique 33/5 = 6,6 · Business 19/3 = 6,33.

#### Détail, preuves et écart

**1. Onboarding — 6 (−1)**
- **Pour** : 4 étapes avec retour, poids et taille utilisés ; 7 programmes proposés dont 3 marqués « Recommandé » (capture `03_onboarding_programmes`) ; aperçu des séances avant de choisir ; validation en 0,4 s ; tutoriel de 6 bulles.
- **Contre** : un mardi, après un programme lundi-mercredi-vendredi, l'accueil n'offre que « Prochaine séance · Full Body A · Demain · 07/10 » (`routes/accueil.py:390-395`). Le toucher ouvre `/seance?…&date=2026-10-07` avec le bandeau **« RATTRAPAGE · Mercredi 07/10/2026 »** (`routes/seance.py:291`, `templates/seance_edit.html:11-16`), et les séries s'enregistrent à la date du lendemain (reproduction RA, constaté en production, § Z.2-5). La dernière bulle du tutoriel dit « Lance ta première séance » ; son bouton « Commencer » reste sur l'accueil. La carte d'exercice conseille « barre vide (20 kg) » mais laisse le poids vide : « Série faite » est alors refusée (« Indique tes répétitions et ta charge », `static/js/seance.js:498-509`, capture `09`). Connexion Google seule.
- **Écart** : l'audit précédent l'avait **surévalué** — le parcours du jour 1 n'avait pas été joué un jour sans séance prévue, soit 4 jours sur 7 pour un programme à 3 séances.
- **Pour 8** : un jour 1 qui mène à une vraie séance d'aujourd'hui en un tap (charge de départ pré-remplie), prouvé sur au moins 5 inscriptions réelles terminant leur première séance le jour même.

**2. Saisie de séance — 7 (=)**
- **Pour** : « Série faite » est optimiste — la série se coche, le chrono part, l'envoi suit (`static/js/seance.js:514-523`) ; avec un historique, la charge est pré-remplie (« Même charge, vise 7 reps », 70 kg, capture `19`) ; échauffement à part, supersets ; 37 enregistrements réels le 04/10, tous réussis, 0 doublon en base.
- **Contre** : une date future est acceptée sans garde (`core/seance_saisie.py:22-27`, I-1) ; quatre verbes sur chaque carte (`templates/_seance_carte_exercice.html:325`, `:374`, `:385`) ; « Séance terminée 💪 » proposé alors que rien n'a été enregistré (capture `10`) ; le message d'erreur recouvre « Enregistrer » et « Skip » (capture `09`) ; le RPE n'a jamais été saisi en usage réel (32 lignes du 04/10, `rpe` vide).
- **Pour 8** : 10 séances réelles sans accroc rapporté, aucune série à une mauvaise date, et le temps entre deux « Série faite » mesuré au niveau de Strong (une frappe + un tap).

**3. Programme et planning — 7 (=)**
- **Pour** : rotation A/B réelle (`core/rotation.py`), éditeur borné, renommage qui garde l'historique (v42), supersets.
- **Contre** : la carte « Prochaine séance » vise toujours le prochain jour planifié, jamais « fais-la aujourd'hui » ; pas de blocs ni de % d'e1RM ; 0 superset dans les 13 programmes de production (fonction inutilisée).
- **Pour 8** : séance du jour à la demande (« faire la prochaine maintenant »), blocs ou cycles simples, et au moins un utilisateur réel qui s'en sert.

**4. Progression et statistiques — 7 (=)**
- **Pour** : « Tes progrès » sur l'accueil (« Développé militaire : +7,5 kg en 3 semaines », capture `12`), séries par muscle face aux repères (capture `13`), calendrier, streak et paliers.
- **Contre** : pas de courbe d'e1RM avec tendance ni de comparaison entre périodes comme chez Strong ; carte du corps réservée au PRO.
- **Pour 8** : courbe e1RM par exercice avec tendance et records datés, vérifiée sur un vrai historique de plus de 3 mois.

**5. Coach IA — 7 (=)**
- **Pour** : contexte complet (RPE, prescription, bilans, cardio à part) tenu par `tests/test_coach_contexte.py` ; quota atomique ; réponses en flux.
- **Contre** : 10 messages réels depuis juin, **0 sur 30 jours** ; « ouvert à l'essai (5 messages/jour) » impossible en production (v29) ; qualité des réponses non mesurée.
- **Pour 8** : usage réel récurrent (au moins un PRO payant qui l'utilise chaque semaine) et un retour qualitatif documenté.

**6. Générateur IA — 7 (=)**
- **Pour** : tâche de fond, reprise après rechargement (test navigateur), « Refaire cette séance ».
- **Contre** : 8 générations et 2 adoptions depuis juin, 1 génération en 30 jours ; aucune évaluation des programmes produits.
- **Pour 8** : un programme généré suivi 4 semaines par un vrai utilisateur, avec ses progrès visibles.

**7. Nutrition — 7 (=)**
- **Pour** : repas par aliment, ~430 aliments, Open Food Facts côté serveur, cibles reliées aux jours d'entraînement (capture `33`).
- **Contre** : 21 lignes de repas en base au total ; pas de recettes, d'aliments perso, ni de cible qui s'ajuste au poids réel (MacroFactor le fait) ; recherche Open Food Facts jamais exercée d'ici (réseau).
- **Pour 8** : aliments perso et recettes, tendance hebdomadaire, cible adaptative, et 2 semaines de saisie réelle.

**8. Cardio — 6 (=)**
- **Pour** : format v44 constaté sur les 2 cardios réels (`reps = poids = 0`, mesures dans leurs colonnes) ; durée en minutes et secondes (PR #34) ; import Strava.
- **Contre** : aucune durée décimale encore en base ; GPS seulement écran allumé ; pas de zones cardiaques ni Health Connect.
- **Pour 7** : un cardio réel avec secondes en base et le suivi GPS écran éteint (service natif) ; **pour 8** : zones cardiaques via Health Connect.

**9. Hors-ligne — 7 (=)**
- **Pour** : rejoué dans Chromium (P9) : pastille « Séances de la semaine prêtes hors-ligne », séance rouverte en mode avion, série en file, « Terminer » rend la main en 7,6 s, retour du réseau → 461 → 462 lignes en base.
- **Contre** : jamais vérifié dans une vraie salle en sous-sol ; dépend du service worker (la webview Android charge le site distant).
- **Pour 8** : une séance complète faite réellement sans réseau, synchronisée sans perte, constatée en base.

**10. Notifications et relances — 7 (=)**
- **Pour** : **cron prouvé** — `POST /tasks/reminders` par cron-job.org toutes les heures, 39 appels sur 39 h, tous en 200 ; sur 30 jours : 17 rappels, 29 relances ; récap du dimanche envoyé le 04/10 (« sent=1 errors=0 »).
- **Contre** : 3 abonnements push au total ; aucun effet mesuré (retour dans les 24 h après un rappel).
- **Écart** : la preuve lève la principale réserve, pas assez pour 8 sans mesure d'effet.
- **Pour 8** : taux de séances faites dans les 24 h suivant un rappel, mesuré sur au moins 20 abonnés.

**11. Design et cohérence UI — 6 (=)**
- **Pour** : cartes illustrées, thème sombre cohérent, bandeaux clairs (hors-ligne, file d'attente).
- **Contre** : e-mail et déconnexion en tête de chaque page (toutes les captures ; signalé le 30/09 et le 03/10) ; carte d'exercice chargée ; la barre du bas reste visible pendant l'onboarding (capture `03`) ; 60 `style="` bruts dans les gabarits (le cliquet du test, mesuré autrement, passe à ≤ 56).
- **Pour 7** : en-tête allégé, un seul verbe par carte ; **pour 8** : une revue visuelle de toutes les pages avec des utilisateurs, sans incohérence relevée.

**12. Performance ressentie — 6 (−1)**
- **Pour** : HTML compressé léger (séance 21,8 ko, accueil 8,3 ko, programme 24,1 ko) ; accueil à **6 requêtes** à froid en régime normal (7 le 03/10 ; 9 la toute première fois, quand les badges s'écrivent) ; « Série faite » ne fait pas attendre l'écran.
- **Contre (mesuré en production)** : `/seance/save-exo` **1,42 à 2,95 s, médiane ≈ 2,0 s** sur les 37 appels du 04/10, contre **0,54 à 1,20 s, médiane 0,85 s** sur les 5 appels du 29/09 ; `/accueil` médiane 1,20 à 1,77 s par jour du 04 au 06/10, contre 0,20 à 0,79 s du 01 au 03/10. Cause non établie (Redis actif depuis le 04/10 13:58 UTC et beaucoup de code changé le même jour ; traçage Railway désactivé). Un seul processus.
- **Écart** : **surévalué** auparavant faute de mesure de production.
- **Pour 7** : retrouver une médiane < 1 s ; **pour 8** : < 300 ms et une saisie qui ne dépend plus du serveur (stockage local d'abord).

**13. Architecture du code — 7 (=)**
- **Pour** : 69 modules `core/` (13 345 lignes), plafond de 400 lignes par module de données tenu par test ; couche données sans cycle ; état partagé Redis/mémoire.
- **Contre** : 5 imports entre blueprints (`routes/programme.py:311`, `routes/onboarding.py:210`, `routes/gestion.py:448`, `routes/premium.py:15`, `routes/progres.py:394`) ; `routes/programme.py` à 849 lignes pour un plafond de 850 ; replis silencieux sur colonne absente (voir 16).
- **Pour 8** : un contrôle de schéma au démarrage et zéro import entre blueprints.

**14. Modèle de données — 7 (=)**
- **Pour** : v41 à v47 vérifiées en base (index unique, contraintes, 3 tables typées fermées) ; 0 doublon, 0 orphelin.
- **Contre** : la condition posée pour 8 n'est pas remplie (0 série avec `exercise_id` ou `type_serie`) ; schéma de production en retard sur le code (v29) ; 2 clés mortes dans 9 programmes.
- **Pour 8** : une séance réelle qui écrit `exercise_id` et `type_serie`, et un schéma de production égal à celui que le code attend.

**15. Sécurité — 7 (=)**
- **Pour** : RLS sur 14 tables sans règle ni droit client ; webhook Stripe signé (`routes/billing.py:244-255`) ; admin réservé à une connexion Google (`core/admin_acces.py`) ; CSRF partout sauf 4 chemins signés ou à secret (`app.py:274`) ; aucun secret dans le dépôt (`git grep`).
- **Contre** : CSP avec `'unsafe-inline' 'unsafe-eval'` (`app.py:352`, M5) ; alertes Supabase (déclencheur appelable, mots de passe fuités) ; configuration Auth non lisible d'ici (un compte e-mail existe).
- **Pour 8** : CSP sans `unsafe-eval` (version CSP d'Alpine), alertes Supabase à zéro, et un test d'intrusion simple documenté.

**16. Robustesse — 6 (−1)**
- **Pour** : 1 seule 5xx sur 3 078 requêtes en 48 h ; panne de Redis prévue et testée ; fin de séance bornée ; quota rendu si l'IA échoue.
- **Contre** : (a) une colonne absente est journalisée puis ignorée (`core/db_abonnement.py:96-112`, `core/db_profil.py:42-58`) : la v29 manque depuis juin sans aucune alerte ; (b) **aucune nouvelle tentative** sur coupure de connexion : le 05/10 à 06:26 UTC, `/seance` a répondu 503 et l'accueil s'est affiché vide (`core/db_base.py:34-50`, `routes/seance.py:54-58`, reproduction RC) ; (c) une date future est acceptée (I-1).
- **Écart** : **surévalué** — l'audit n'avait pas comparé le schéma de production au code.
- **Pour 7** : contrôle de schéma au démarrage + une nouvelle tentative ; **pour 8** : 30 jours sans 5xx en production.

**17. Tests — 6 (−1)**
- **Pour** : 1 270 + 23 + 113 tests, verts 7 jours sur 7 ; couverture 85 % (81 %).
- **Contre** : la fausse base l'écrit elle-même : « Ce que ça n'attrape PAS : un nom de colonne qui n'existe pas en base » (`tests/conftest.py:67`). Résultat : l'essai et le parrainage passent tous leurs tests (`tests/test_essai_pro.py`, `tests/test_essai_et_bilan_pro.py`) alors qu'ils sont impossibles en production ; aucun test ne joue un jour sans séance prévue (I-1) ; aucun test contre un vrai PostgreSQL en CI.
- **Écart** : un défaut réel, durable, invisible aux tests.
- **Pour 7** : CI avec un PostgreSQL qui applique v23 → v47 ; **pour 8** : en plus, un test qui vérifie que chaque colonne lue par le code existe, et des parcours navigateur sur les 7 jours.

**18. Monétisation et paywall — 5 (−2)**
- **Pour** : Checkout Stripe et webhook signé avec remboursements et litiges ; page PRO honnête ; invitation PRO après la 10ᵉ séance (capture `12`) ; tarifs masquables dans l'app native.
- **Contre** : **0 `vip_activated` depuis le 14/06** pour 3 paiements commencés ; les 8 profils PRO n'ont aucun événement d'activation (accordés à la main ? invérifiable) ; l'essai n'existe pas en production ; le parrainage (« Gagnez des jours PRO à deux », `templates/plus.html:54`) ne crédite rien.
- **Écart** : **surévalué** (essai jamais vérifié en base) et conversion désormais mesurée : zéro.
- **Pour 7** : v29 appliquée et un essai réel suivi jusqu'à la fin ; **pour 8** : au moins un paiement réel abouti, et un taux de conversion de l'essai mesuré.

**19. Rétention — 7 (=)**
- **Pour** : mécanismes vérifiés en production sur 30 jours (17 rappels, 29 relances, 3 défis validés, récap).
- **Contre** : 2 comptes actifs sur 15 (7 et 30 jours), 0 inscription depuis le 01/07 ; aucune dimension sociale, et le seul mécanisme à deux (parrainage) est mort. Échantillon trop petit pour mesurer une rétention.
- **Pour 8** : rétention J7/J30 mesurée sur au moins 20 inscrits, et un mécanisme social (binôme ou streak partagé).

**20. Accessibilité — 7 (=)**
- **Pour** : `tests/test_accessibilite.py` (9 pages, contrastes, noms accessibles), cibles de 44 px, `prefers-reduced-motion`.
- **Contre** : jamais essayé avec TalkBack ; le message d'erreur de « Série faite » recouvre des boutons.
- **Pour 8** : une séance complète faite au lecteur d'écran (TalkBack), sans blocage.

---

### Partie 2 — Les 9 parcours (joués dans Chromium, 375 × 812)

| # | Profil | 06/10 (préc.) | **Aujourd'hui** | Ce qui marche ✅ | Ce qui coince ⚠️ |
|---|---|---:|---:|---|---|
| 1 | Débutant jour 1 | 7 | **6** | Onboarding en 4 étapes, programme recommandé, tutoriel, conseil de charge de départ | Un jour sans séance prévue : « Prochaine séance · Demain » → séance datée du lendemain, bandeau « RATTRAPAGE » ; « Commencer » du tutoriel ne lance rien ; 20 kg conseillés mais pas pré-remplis → « Série faite » refusée ; « Séance terminée 💪 » sur une séance vide |
| 2 | Débutant semaine 3 | 7 | **7** | Accueil : « +7,5 kg en 3 semaines », défi 1/3, streak 4 semaines, séries par muscle | Invitation PRO plein écran à la 10ᵉ séance ; pas de récap visuel du mois pour un gratuit |
| 3 | Intermédiaire (import Hevy) | 7 | **7** | CSV Hevy : 2 séances, 5 séries, échauffement écarté, noms traduits (« Bench Press (Barbell) → Développé couché »), 5 lignes en base | Pas de séries dégressives ; import par fichier seulement |
| 4 | Avancé | 6 | **6** | Charge pré-remplie, « Même charge, vise 7 reps », échauffement 4 séries, superset | Pas de blocs ni de % d'e1RM ; RPE jamais utilisé en vrai |
| 5 | Gratuit | 7 | **6** | Séances, progrès simples, cardio, import, export gratuits ; murs PRO clairs | « Inviter des amis — Gagnez des jours PRO à deux » promis dans Plus, **rien n'est crédité en production** |
| 6 | Essai restreint | 6 | **2** | Fonctionne sur la fausse base (badge ESSAI, « encore 19 h », coach 0/5) | **N'existe pas en production** : la colonne `vip_until` est absente, aucun essai ne peut démarrer |
| 7 | PRO payant | 7 | **7** | Coach, générateur, nutrition détaillée, « Ce mois-ci avec PRO » | 0 paiement abouti enregistré : parcours jamais vécu par un vrai payant |
| 8 | App Android (webview) | 6 | **6** | Séance réelle du 04/10 sur Android 16 : 37 envois, tous réussis ; compte à rebours natif | Webview du site distant ; tarifs visibles (normal hors Play Store) ; 2 s par enregistrement côté serveur |
| 9 | Salle sans réseau | 7 | **7** | Mode avion : séance ouverte, série en file, « Terminer » en 7,6 s, synchro au retour | Jamais prouvé dans une vraie salle |

Moyenne des parcours : 54 / 9 = 6,0 (préc. 6,7).

---

### Partie 3 — Audit technique

#### Critique

**C1 — Migration v29 absente : essai PRO et parrainage morts en production.**
- **Reproduction** : SQL Z.4-a (`vip_until`, `referral_code`, `referred_by` absents) ; RB (base aussi stricte que la production) → `/parrainage` affiche un lien et « 1 jour d'essai PRO… et toi 3 jours », le code n'est jamais enregistré, `apply_referral` renvoie `False`, aucun `vip_until` posé. Journaux attendus : `get_or_create_referral_code read FAILED … 42703`.
- **Impact** : chaque utilisateur voit une promesse fausse (onglet Plus, page Parrainage) ; 2 liens déjà partagés (`referral_shared` = 2) ; le levier de conversion par l'essai n'a jamais existé.
- **Correction** : appliquer `supabase_schema_v29_referral.sql` (avec ton accord) et ajouter au démarrage un contrôle qui compare les colonnes attendues à la base et alerte `/admin`. **Effort S.**

#### Importants

| # | Constat | Reproduction | Impact | Correction | Effort |
|---|---|---|---|---|---|
| I-1 | **Séance d'un autre jour enregistrable**, et l'accueil y mène : « Prochaine séance · Demain » ouvre la séance datée du lendemain avec un bandeau « RATTRAPAGE » (`routes/accueil.py:390-395`, `routes/seance.py:73-75`, `:291`, `core/seance_saisie.py:22-27`). | RA (test) + navigateur (captures `42`, `43`) + production : 2 séries « Push 1 » du 05/10 écrites le 04/10 à 17:57 | Séries à la mauvaise date ; le lendemain, la séance apparaît déjà faite ; calendrier et streak faussés | La carte propose « Faire maintenant » (date du jour) ; le serveur refuse une date future ; bandeau « En avance » sinon | S |
| I-2 | **Latence d'enregistrement ×2,4** : `/seance/save-exo` médiane 0,85 s (29/09) → ≈ 2,0 s (04/10) ; accueil 0,2-0,8 s → 1,2-1,8 s. | Journaux HTTP Railway (Z.6) | Batterie et données ; « Terminer » attend les envois ; sous réseau faible, le délai de 8 s est mangé par le serveur | Activer le traçage, chronométrer Redis et Supabase par étape, regrouper les allers-retours | M |
| I-3 | **Aucune nouvelle tentative sur coupure de connexion** à la base (`core/db_base.py:34-50`). | RC + production 05/10 06:26 UTC (`ConnectionTerminated` → `/seance` 503, accueil vide) | Page d'erreur à la première ouverture du matin | Retenter une fois les lectures sur erreur de transport | S |
| I-4 | **Les tests ne voient pas le schéma** : fausse base sans colonnes (`tests/conftest.py:67`) et replis silencieux (`core/db_profil.py:42-58`). | C1 est passée inaperçue avec 1 270 tests verts | Toute migration oubliée reste invisible | PostgreSQL en CI avec toutes les migrations ; test « chaque colonne lue existe » | M |
| I-5 | **0 activation PRO enregistrée** depuis le 14/06 pour 3 paiements commencés (2 comptes). | SQL Z.4-e | Soit aucun paiement n'a abouti, soit l'activation ne laisse pas de trace : invérifiable sans Stripe | Comparer le tableau de bord Stripe aux événements ; alerte si un paiement n'active rien | S |

#### Mineurs

| # | Constat | Preuve | Impact | Correction | Effort |
|---|---|---|---|---|---|
| m1 | `handle_new_user()` (SECURITY DEFINER) exécutable par `anon` et `authenticated` | `get_advisors` ; SQL Z.4-f | Faible (déclencheur) | `revoke execute … from anon, authenticated` | S |
| m2 | Protection des mots de passe fuités désactivée ; 1 compte e-mail existe | `get_advisors` ; SQL Z.4-g | Faible si l'inscription e-mail est fermée (invérifiable) | Fermer le fournisseur e-mail ou activer la protection | S |
| m3 | Clés mortes `_profiles` / `_active_profile` dans 9 programmes | SQL Z.4-c ; `grep` vide | Aucun, dette | Nettoyage idempotent | S |
| m4 | Variables Railway nommées avec espaces (`SUPABASE_URL  `, `SUPABASE_ANON_KEY  `) | `describe-service` | Compensé par `_env` (`core/db_base.py:69-81`), fragile | Renommer les variables | S |
| m5 | Journaux INFO étiquetés « error » sur Railway | Journaux Z.6 | Impossible de filtrer les vraies erreurs | Journaux applicatifs sur la sortie standard | S |
| m6 | CSP `unsafe-inline` + `unsafe-eval` (M5 du 03/10) | `app.py:352` | Une future injection s'exécuterait | Version CSP d'Alpine.js | M |
| m7 | Message d'erreur de « Série faite » recouvrant « Enregistrer » / « Skip » | capture `09` | Gêne d'usage | Toast au-dessus de la barre d'actions | S |
| m8 | « Séance terminée 💪 » proposé pour une séance vide | capture `10` | Bilan sans séance possible | Message « Aucune série enregistrée » | S |
| m9 | Tutoriel : « Lance ta première séance → Commencer » reste sur l'accueil | P1 (notes) | Promesse non tenue au jour 1 | Ouvrir la séance du jour | S |
| m10 | « Barre vide (20 kg) » conseillée mais non pré-remplie | capture `08` | Une frappe de plus, refus au premier tap | Pré-remplir 20 kg pour un mouvement à la barre | S |
| m11 | Écarts doc/code (CONTEXT.md, Z.5) | voir ci-dessous | Induit en erreur | Mise à jour | S |
| m12 | e-mail + déconnexion en tête de chaque page (M9 du 30/09, toujours là) | toutes les captures | Bruit visuel, déconnexion accidentelle | Les déplacer dans Gestion | S |

#### Synthèse par sujet
- **Sécurité** : auth Google + pont JWT ; admin Google uniquement ; CSRF partout sauf `/auth/session`, `/billing/webhook` (signé), `/tasks/*` (secret à temps constant) ; CSP faible (m6) ; quotas atomiques (`core/quota.py`) ; webhooks Stripe signés et traitant remboursements/litiges ; aucun secret dans le dépôt ; variables lues par nom seulement.
- **Intégrité** : écritures par clé (index unique), 0 doublon ; verrous Redis ; cache invalidé par génération ; Redis en panne → repli mémoire (testé) ; mais dates futures acceptées (I-1) et colonnes manquantes ignorées (C1).
- **Performance** : 6 requêtes base pour l'accueil à froid, 3 pour « Série faite », 0 N+1 relevé ; poids compressés 7-24 ko ; latence de production en hausse (I-2).
- **Dette** : 69 modules `core/`, 19 blueprints, 5 imports entre blueprints, `routes/programme.py` à 1 ligne de son plafond, code mort (`_profiles`), doc en retard.

#### Écarts doc/code (CONTEXT.md)

| La doc dit | La réalité |
|---|---|
| `:250-251` parrainage et `:277-278` essai décrits comme actifs | v29 absente en production |
| `:433-434` « Dernières migrations : v34 … v39 » | v47 ; et v29 jamais appliquée |
| `:437` « ≈ 915 tests … 10 navigateur … JS 106 » | 1 270 Python, 23 navigateur, 113 JS |
| `:513` échauffement « jamais enregistré » | Enregistré à part depuis la v43 (`:555`) |
| `:608` « `_session_notes` … purgée à chaque /seance/finish » | Bilans en table depuis la v34, reste du blob repris en v46 |
| `:609` `replace_program_body` conserve `_settings`, `_streak_record`, `_meal_plan` | Ces clés vivent en tables depuis v45-v47 |
| `:624` limiteur « mémoire process » | Redis en production (« Rate limiter backend: redis ») |
| `:638` « Railway déploie depuis main sans attendre » | « Wait for CI » actif |
| `:641-642` « Branche unique main, pas de branches de feature » | Travail par PR depuis la #6 |
| `:645` `CACHE_VERSION` base `v127` | `v132` (`static/service-worker.js:6`) |

#### Suivi des constats précédents

| Repère | Statut au 06/10 (cet audit) | Preuve |
|---|---|---|
| I1 RPE ignoré | Corrigé | `tests/test_rpe_suggestion.py` vert |
| I2 « Série faite » sur champ vide | Corrigé (refus explicite sans charge proposée) | capture `09`, tests JS |
| I3 « Terminer » figé | Corrigé | P9 : 7,6 s en mode avion |
| I4 Test dépendant du jour | Corrigé | suite verte 7 jours |
| I5 Catalogue tronqué | Corrigé | `tests/test_rotation.py` |
| I6 Onboarding destructeur | Corrigé | `tests/test_onboarding.py` |
| I7 Doublons | Corrigé **et prouvé en production** | 0 doublon (SQL) |
| I8 Compteur faux | Corrigé | capture `12` (« 1/3 ») |
| I9 Coach pauvre | Corrigé | `tests/test_coach_contexte.py` |
| I10 Promesses PRO | Corrigé pour la page PRO ; **nouvelle promesse fausse** : parrainage (C1) | `templates/plus.html:54` |
| I11 Mono-processus | Corrigé dans le code ; production : 1 processus, `WEB_CONCURRENCY` absente | journal de démarrage |
| I12 Renommage | Corrigé dans le code ; jamais exercé en production | 0 `exercise_id` |
| I13 Échecs avalés | Corrigé | `tests/test_integrite_0310.py` |
| I14 Couverture | Corrigé (auth 90 %, admin 89 %, programme 84 %) | rapport de couverture |
| M1-M4, M6-M16 | Corrigés (tests verts) | suite complète |
| M5 CSP | **Ouvert** | `app.py:352` |
| F1-F5 | Corrigés ; F5 confirmé (0 bilan sans séance) | SQL Z.4 |
| U1-U3, U6, U8-U10 | Corrigés (tests navigateur) | e2e 23/23 |
| U4 Échauffement | Fait ; **0 échauffement réel** en base | SQL |
| U5 Revalider 3 séries | Non reproduit | — |
| U7 Batterie | À mesurer sur le téléphone | — |

---

### Partie 4 — Améliorations

#### 4.1 Les 10 améliorations à impact maximal (impact / effort)

| # | Amélioration | Effort | Impact | Axes |
|---|---|---|---|---|
| 1 | Appliquer la v29 et contrôler le schéma au démarrage (alerte `/admin`) | S | Fort : essai et parrainage existent, promesses tenues | 16, 18, 19 |
| 2 | « Faire maintenant » sur la carte Prochaine séance + refus serveur des dates futures | S | Fort : jour 1 juste, données justes | 1, 2, 3 |
| 3 | Une nouvelle tentative sur coupure de connexion | S | Moyen : plus de 503 au réveil | 16 |
| 4 | Charge de départ pré-remplie et « Commencer » qui ouvre la séance | S | Moyen : premier tap qui marche | 1, 2 |
| 5 | Rapprocher Stripe et les événements ; alerte si un paiement n'active rien | S | Fort : savoir si l'app encaisse | 18 |
| 6 | Tracer et ramener « Série faite » sous 500 ms | M | Fort : batterie, fluidité, sous-sol | 12 |
| 7 | PostgreSQL réel en CI avec toutes les migrations | M | Fort : plus de dérive invisible | 17, 16 |
| 8 | Fermer les deux alertes Supabase | S | Faible | 15 |
| 9 | Nettoyer `_profiles`/`_active_profile` et mettre CONTEXT.md à jour | S | Faible | 13, 14 |
| 10 | Séries dégressives et blocs pour l'avancé | L | Moyen, sur un public précis | 3, 4 |

#### 4.2 Quinze idées face à Hevy, Strong, MyFitnessPal, MacroFactor et Strava
Fonctions des concurrents citées **de mémoire**, non vérifiables d'ici (Partie 5).

| # | Idée | Face à | Pourquoi |
|---|---|---|---|
| 1 | Séance vide démarrée d'un tap, à tout moment | Hevy, Strong | Le jour 1 ne dépend plus du planning |
| 2 | Saisie enregistrée d'abord sur le téléphone, synchronisée ensuite | Strong | Instantané, sous-sol natif, moins de batterie |
| 3 | Séries dégressives et rest-pause | Hevy | Attendu par l'intermédiaire |
| 4 | Courbe d'e1RM avec tendance par exercice | Strong | Lecture de progression |
| 5 | Échauffement et disques calculés dans la carte | Strong | Le calculateur existe déjà, à intégrer |
| 6 | Routine partagée par lien | Hevy | Acquisition gratuite |
| 7 | Binôme : streak commun avec un ami | Hevy (social) | Seule dimension sociale manquante |
| 8 | Health Connect (poids, pas, FC) | Strava, Strong | Données sans saisie |
| 9 | Application montre (Wear OS) pour valider une série | Hevy, Strong | Téléphone au vestiaire |
| 10 | Dépense énergétique adaptative (TDEE recalculé sur le poids réel) | MacroFactor | Nutrition au niveau 8 |
| 11 | Recettes et aliments perso | MyFitnessPal | Fidélise la saisie |
| 12 | Repas en photo → aliments (IA) | MyFitnessPal | Saisie rapide |
| 13 | Défi cardio du mois (distance cumulée) | Strava | Rétention cardio |
| 14 | Bilan du mois partageable en image | Strava | Viral, existe déjà pour PRO |
| 15 | Le bilan de séance ajuste la suivante (« épaule qui tire » → variante proposée) | — | Inédit à ma connaissance |

#### 4.3 Trois choses à supprimer
1. **Les verbes en double sur chaque carte** (« Réinitialiser les poids », « Recommencer cet exercice », `templates/_seance_carte_exercice.html:374`, `:385`) : « Série faite » enregistre déjà.
2. **L'e-mail et le bouton de déconnexion en tête de chaque page** : leur place est dans Gestion.
3. **Les replis silencieux sur colonne absente** (`core/db_profil.py:42-58`, `core/db_abonnement.py:96-176`) : ils ont caché la v29 pendant des mois ; une alerte au démarrage vaut mieux.

#### 4.4 Ce qui manque pour atteindre 8/10
La note globale de 8 demande que la plupart des axes passent à 8 **avec preuve**. Condition exacte, axe par axe :

| Axe | Note | Condition exacte pour 8 |
|---|---:|---|
| 1 Onboarding | 6 | Jour 1 → séance d'aujourd'hui en un tap, charge pré-remplie, prouvé sur 5 vraies inscriptions |
| 2 Saisie | 7 | 10 séances réelles sans accroc, 0 série mal datée, saisie au rythme de Strong |
| 3 Programme | 7 | Séance à la demande + blocs, utilisés par un vrai utilisateur |
| 4 Progression | 7 | Courbe e1RM avec tendance sur 3 mois réels |
| 5 Coach | 7 | Usage hebdomadaire par un PRO payant + retour qualitatif |
| 6 Générateur | 7 | Un programme généré suivi 4 semaines, progrès visibles |
| 7 Nutrition | 7 | Aliments perso, recettes, cible adaptative, 2 semaines de saisie réelle |
| 8 Cardio | 6 | Secondes réelles en base, GPS écran éteint, zones cardiaques |
| 9 Hors-ligne | 7 | Une séance réelle complète sans réseau, synchronisée sans perte |
| 10 Notifications | 7 | Effet mesuré : séances dans les 24 h après rappel, sur 20 abonnés |
| 11 Design | 6 | En-tête allégé, un verbe par carte, revue visuelle avec utilisateurs |
| 12 Performance | 6 | « Série faite » < 300 ms en production, saisie locale d'abord |
| 13 Architecture | 7 | Contrôle de schéma au démarrage, 0 import entre blueprints |
| 14 Données | 7 | Une vraie série avec `exercise_id` et `type_serie`, schéma = code |
| 15 Sécurité | 7 | CSP sans `unsafe-eval`, 0 alerte Supabase |
| 16 Robustesse | 6 | Contrôle de schéma, nouvelle tentative, 30 jours sans 5xx |
| 17 Tests | 6 | PostgreSQL en CI + test des colonnes + parcours sur 7 jours |
| 18 Monétisation | 5 | v29, un essai réel, un paiement réel abouti, conversion mesurée |
| 19 Rétention | 7 | J7/J30 mesurés sur 20 inscrits + un mécanisme social |
| 20 Accessibilité | 7 | Une séance complète avec TalkBack |

#### 4.5 Une seule action pour les 30 prochains jours
**Faire coïncider la production avec ce que l'app promet** : appliquer la v29 et ajouter un contrôle qui compare, au démarrage, les colonnes attendues par le code à celles de la base (alerte `/admin` et journal), puis rejouer chaque promesse visible sur la vraie app (essai, parrainage, séance du jour, paiement).
**Pourquoi** : c'est un effort S qui débloque trois axes (robustesse, monétisation, tests), rend vraie une promesse affichée à chaque utilisateur, et empêche la prochaine migration oubliée de durer des mois. Tant que le code et la base divergent en silence, aucune autre note ne peut être *prouvée*.

---

### Partie 5 — Non vérifiable d'ici

1. **Stripe** : si les 3 paiements commencés ont abouti, quels événements le webhook reçoit, d'où viennent les 8 profils PRO.
2. **Configuration Auth Supabase** : fournisseur e-mail ouvert ou non, confirmation exigée.
3. **Valeurs des variables** (lues par nom seulement) : validité de `ANTHROPIC_API_KEY`, `CRON_SECRET`, identifiants AdMob.
4. **Cause de la hausse de latence** (traçage Railway désactivé).
5. **Sur le téléphone** : batterie (U7), notifications réellement affichées, connexion Google native, affichage AdMob, comportement de la webview hors réseau.
6. **Usage réel** : satisfaction, rétention statistique (2 comptes actifs), qualité des réponses du coach et des programmes générés.
7. **Open Food Facts** : recherche par nom (réseau de l'audit).
8. **Concurrents** : fonctions et prix cités de mémoire.
9. **Une vraie salle en sous-sol** (seul le mode avion simulé a été joué).

---

### Annexe Z — Reproductions, commandes, requêtes et mesures

#### Z.3 Reproductions (scripts hors dépôt, lancés depuis `pwa/` avec `PYTHONPATH=tests python -m pytest <fichier> -s`)
Sortie réelle :
```
[RA] aujourd'hui = 2026-10-06 | liens « prochaine séance » : ['/seance?mode=prefaite&name=Push&date=2026-10-07']
[RA] réponse 200 | lignes en base : [('2026-10-07', 'Push', 10, 60.0)]
[RB] /parrainage : lien affiché = True | promesse '3 jours' : True | texte : Ton ami reçoit 1 jour d'essai PRO à l'inscription, et toi 3 jours
[RB] code relu en base : None
[RB] apply_referral -> False | profils avec vip_until : []
[RC] 1re requête après coupure : 503 | requêtes encore en échec : 0
[RC] 2e requête (connexion neuve) : 200
3 passed in 0.90s
```
- **RA** : programme dont le seul jour planifié est demain ; GET `/accueil` → lien de la carte ; POST `/seance/save-exo` avec cette date → ligne datée de demain. Navigateur : bandeau « RATTRAPAGE · Mercredi 07/10/2026 » un mardi 06/10.
- **RB** : la fausse base est rendue stricte (toute requête sur `profiles` citant une colonne v29 lève `42703 column … does not exist`, comme PostgREST) ; GET `/parrainage`, puis `apply_referral("u-filleul-0002", code)`.
- **RC** : la première requête lève `ConnectionTerminated` (même nom qu'en production), la suivante passe.
- **P1 navigateur** : « premier champ de saisie à 595 px (écran 812 px) » ; « après "Série faite" sans rien taper : lignes en base = [] » (message « Indique tes répétitions et ta charge »).
- **P3 navigateur** : « Fichier Hevy, 6 lignes lues · 1 série d'échauffement écartée · Bench Press (Barbell) → Développé couché » ; 5 lignes importées.
- **P9 navigateur** : « séance rouverte en mode avion : True » ; « "Terminer" hors-ligne : URL /accueil après 7.6s » ; « lignes en base avant/après retour du réseau : 461 → 462 ».

#### Z.4 Requêtes SQL (Supabase, `select` uniquement)
- **a. Colonnes attendues** : jointure de 34 couples (migration, table, colonne) extraits des fichiers `supabase_schema_v23…v44` avec `information_schema.columns` → 31 `present = true`, 3 `false` : `29 profiles referral_code`, `29 profiles referred_by`, `29 profiles vip_until`.
- **b.** `select count(*) from profiles where vip_until is not null` → `ERROR: 42703: column "vip_until" does not exist`.
- **c.** `select k, count(*) from (select jsonb_object_keys(data) k from programs) x where k like '\_%' group by k` → `_active_profile 9, _equipement 6, _equipment_details 6, _name 5, _origin 10, _planning 14, _profiles 9, _programmes 8, _rotation 1, _seance_prog 8, _started_at 14`.
- **d.** Séries depuis la v42 : `total 1169, avec_exercise_id 0, avec_type_serie 0, ecrites_depuis_v42 10, muscu_ecrites_depuis_v42 9, derniere_muscu 2026-10-04 17:18:29 UTC` ; détail ligne à ligne : 2 séries « Push 1 » `date = 2026-10-05` avec `created_at` 2026-10-04 15:57:11 et 16:00:03 UTC.
- **e.** Événements : `vip_activated` absent sur toute la table (premier événement 2026-06-14) ; `checkout_started` 3 (2 comptes) ; `tier = 'vip'` 8 ; `stripe_customer_id` renseigné 2.
- **f.** `handle_new_user` : `returns trigger`, `security_definer true`, `anon_exec true`, `auth_exec true`, déclencheur `on_auth_user_created`.
- **g.** `auth.users` par fournisseur : google 14, email 1 (09/04) ; dernière création 2026-07-01.
- **h.** Cohérence : `doublons_cle_serie 0`, `*_sans_compte 0` sur 13 tables, `etat_sans_programme 0`, `bilans_sans_seance 0`, `series_sans_session_id 0`, `series_vides_0_0 193`, `lignes_session_legacy 2`.
- **i.** Usage : `comptes_auth 15, inscrits_30j 0, actifs_seance_7j 2, actifs_seance_30j 2, seances_7j 6, seances_30j 18, seances_muscu_30j 16`.

#### Z.5 Code
- `git grep` de motifs de secrets (`sk_live_`, `whsec_`, jetons JWT, clés Google) : seulement une fausse clé dans `tests/test_illustrations.py:580`.
- `grep "_active_profile\|_profiles"` dans `core/`, `routes/`, `app.py`, gabarits et JS : **aucun résultat**.
- Requêtes base par page (fausse base, compte de 461 séries, cache froid / chaud) : accueil 9 / 3 la première fois puis **6** / 3 ; séance (choix) 4 / 1 ; séance Push 6 / 3 ; progrès 6 / 1 ; programme 4 / 1 ; nutrition 7 / 3 ; cardio 1 / 0 ; gestion 5 / 1 ; coach 3 / 1 ; « Série faite » 3.
- Poids HTML brut / compressé : accueil 28,8 / 8,3 ko ; séance Push 159,5 / 21,8 ko ; progrès 90,7 / 18,6 ko ; programme 201,7 / 24,1 ko ; nutrition 115,1 / 22,6 ko ; gestion 41,8 / 11,3 ko ; JavaScript total 266 ko non compressé.

#### Z.6 Railway
- Déploiement PR #22 créé le 04/10 à 17:17:09 UTC ; déploiement précédent retiré à 17:21:13 UTC.
- Démarrage du 06/10 14:02 UTC : `Using worker: gthread` · `Rate limiter backend: redis (partagé)` · `partage: stockage redis, 1 processus`. Le 05/10 07:02 UTC : `stockage memoire`, puis redis à 07:15.
- 48 h : 3 078 requêtes, 1 erreur 5xx ; `2026-10-05 06:26:22 routes.seance ERROR seance() DB failed: <ConnectionTerminated error_code:9 …>` et `/seance` 503 à la même seconde.
- `/tasks/reminders` : `POST … 200`, une fois par heure du 05/10 00:00 au 06/10 14:00 UTC (39 appels), user-agent cron-job.org, 0,69 à 1,59 s.
- `/seance/save-exo` le 04/10 (37 appels, ms) : 1777, 2596, 1881, 2811, 1502, 1904, 2080, 1540, 1427, 2193, 2403, 1591, 1573, 2575, 2095, 2950, 2339, 1552, 2001, 1562, 2574, 1433, 1578, 2330, 2277, 2189, 2009, 2681, 2583, 1419, 2387, 1506, 1548, 1444, 2548, 1520, 1420. Le 29/09 (5 appels) : 799, 540, 1111, 1197, 848.
- `/accueil`, médiane par jour (ms) : 29/09 1129 · 30/09 364 · 01/10 790 · 03/10 199 · 04/10 1274 · 05/10 1202 · 06/10 1768. `/seance` médiane sur 7 jours : 234-237 ms.

---

# Mises à jour précédentes (conservées telles quelles)

## Rapport précédent — 6,9/10 (06/10/2026, après les PR #33 et #34, commit `b09989a`)

**Mise à jour** : 06/10/2026 (après les PR #33 et #34 : état du compte sorti de `programs.data`, v47, reset soft retiré ; durée du cardio en secondes) · **Commit audité** : `b09989a` (tête de `main` après les PR #6 à #34, CI verte, déployé) · **Audit initial** : 03/10/2026 sur `6126f95` (5,6/10). Mises à jour précédentes : 04/10 — 6,5 (`d2362f9`), 6,7 (`c4528b3`), 6,8 (`ee13985`), 6,8 (`158d1e0`), 6,9 (`67b346f`, 137 / 20) ; 05/10 — 6,9 (`345334c`, 138 / 20, après les PR #22 à #24), 6,9 (`0144587`, après la PR #27), 6,9 (`6fcc9f6`, après la PR #29) ; 06/10 — 6,9 (`201199a`, après la PR #31).
**Historique** : 30/09/2026, `ac44673`, 4,9/10. Les versions précédentes de ce fichier restent dans l'historique git ; `RAPPORT_AUDIT_2.md` n'a pas été touché.

---

## Note globale : **6,9 / 10** (138 / 20 · 04/10 : 6,5, 6,7, 6,8, 6,8, 6,85 · 03/10 : 5,6 · 30/09 : 4,9)

> Les trois défauts qui faisaient de l'app un carnet « qui note juste mais raisonne faux » sont corrigés et prouvés par des tests : le RPE saisi pilote la suggestion, « Série faite » valide la valeur affichée en un tap, et la fin de séance ne se bloque plus au sous-sol. Les programmes ne sont plus amputés (rotation A/B réelle), refaire l'onboarding ne détruit plus rien, et l'app a rattrapé l'essentiel de ce qui manquait face à Hevy/Strong : import de leur historique, supersets, échauffement, séries par muscle et par semaine, semaine allégée proposée. Depuis, la nutrition — seul axe resté à 5 — est passée à des repas détaillés aliment par aliment, avec des cibles reliées au poids et aux jours d'entraînement (PR #10), et les petits trous visibles sont bouchés : « Créer mon propre programme » ouvre l'éditeur, l'éditeur est borné, vider l'historique se confirme (PR #11). Enfin, une série ne peut plus exister en double en base (index unique v41, écritures par clé) et renommer un exercice propose d'emmener son historique (PR #13) ; la génération IA ne tient plus de fil du serveur (PR #14). Les revenus ne fuient plus : un remboursement total ou un litige bancaire retire PRO (rendu si le litige est gagné), et la production n'affiche jamais de pub de test en silence (PR #16). Les chemins de connexion, d'admin et du programme sont testés à 84-91 %, ce qui a révélé et corrigé deux façons de laisser une séance fantôme dans le planning (PR #17). Enfin, le cache, les verrous, les quotas et les tâches IA ne vivent plus seulement dans la mémoire d'un processus : avec Redis, l'app peut tourner sur plusieurs instances sans servir de donnée périmée, et la CI rejoue toute la suite sur un vrai Redis (PR #19). Un exercice a maintenant un identifiant qui survit aux renommages (PR #22, v42) et une série peut être marquée d'échauffement, hors records et volume de travail (PR #24, v43). Surtout, **la première séance réelle du propriétaire, sur Android, a révélé dix problèmes que 1 185 tests n'avaient pas vus** (§ A.4 bis) : affichage cassé en portrait dès qu'un record tombait, saisie non validée perdue en quittant l'app, chrono qui partait seul et notifiait le mauvais exercice, carte refermée d'office, défilement trop loin. Huit sont corrigés (PR #23), un n'a pas pu être reproduit, un portait sur la batterie et reste à mesurer sur le téléphone. **6,9, et ce n'est pas encore 8.** Seul le modèle de données monte (6 → 7). Ce retour confirme ce que le barème dit : un niveau Hevy/Strong se *prouve* à l'usage, pas en CI. Le 05/10, la PR #27 a fermé les trois derniers mineurs retenus (funnel VIP compté sur la fenêtre, tonnage admin sans le cardio, commentaires périmés) et rangé le cardio dans ses propres colonnes (v44, appliquée) : la base refuse désormais des minutes dans `reps` et des kilomètres dans `poids`, et le tonnage admin a perdu 86 685 « kg » qui venaient du cardio. **La note ne bouge pas (6,9)** : ce travail est invisible à l'écran et le modèle de données garde son blob `programs.data` fourre-tout. Redis est branché en production (un seul processus pour l'instant). Puis la PR #29 a sorti les réglages du blob (table `reglages`, v45, appliquée) ; en les déplaçant, **quatre réglages de la page Gestion se sont révélés sans aucun effet**, dont un vendu comme avantage PRO : ils sont retirés (§ A.4, F4). Le 06/10, la PR #31 en a sorti les calques du jour (table `calques_seance`, v46, appliquée) : ajouter, échanger ou réordonner un exercice en séance n'écrit plus que sa ligne, au lieu de relire et réécrire le programme entier. Au passage, **18 bilans de séance restés dans l'ancien stockage étaient invisibles pour l'export RGPD et pour le coach** (§ A.4, F5) : ils ont rejoint leur table. Puis la PR #33 a sorti le reste (table `etat_compte`, v47, appliquée) : badges, record de série, défis, semaine allégée, plats de la semaine, cibles nutrition perso. Elle a aussi supprimé le « reset soft » et son archive, l'une des trois choses à supprimer du 03/10. **`programs.data` ne contient plus que le programme** : séances, planning, rotation, dossiers, équipement. La PR #34 répond à un retour d'usage : la durée du cardio se saisit en minutes et secondes, et le chrono ne tronque plus 25:59 en 25. Il manque encore tout chiffre d'usage (rétention, conversion). **6,9, toujours** : aucun axe n'atteint 8 ; dix-huit sont à 7, deux à 6. Le modèle de données remplit maintenant la condition que ce rapport posait, mais 8 veut dire *prouvé* : aucune série réelle n'a encore été écrite avec son identifiant d'exercice (§ A.4 sexies).

**Avertissement de méthode** : cette mise à jour est faite par le même agent qui a écrit les corrections. Le risque de complaisance est réel ; pour le contenir, chaque note qui monte s'appuie sur un test ou une mesure cités plus bas, et les constats non traités restent ouverts, même mineurs.

| Bloc | 30/09 | 03/10 | 04/10 (6,5) | 04/10 (6,7) | après #13-#14 (6,8) | après #16-#17 (6,8) | après #19 (6,9) | après #22-#24 (6,9) | après #27 (6,9) | après #29 (6,9) | après #31 (6,9) | après #33-#34 (6,9) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Produit (onboarding, saisie, programme, progression, coach, générateur, nutrition, cardio) | 5,0 | 5,4 | 6,4 | 6,8 | 6,9 | 6,9 | 6,9 | 6,9 | 6,9 | 6,9 | 6,9 | **6,9** |
| Plateforme (hors-ligne, notifications, design, performance) | 4,8 | 5,5 | 6,8 | 6,8 | 6,8 | 6,8 | 6,8 | 6,8 | 6,8 | 6,8 | 6,8 | **6,8** |
| Technique (architecture, données, sécurité, robustesse, tests) | 5,0 | 5,6 | 6,4 | 6,4 | 6,6 | 6,6 | 6,8 | 7,0 | 7,0 | 7,0 | 7,0 | **7,0** |
| Business (monétisation, rétention, accessibilité) | 4,7 | 6,0 | 6,7 | 6,7 | 6,7 | 7,0 | 7,0 | 7,0 | 7,0 | 7,0 | 7,0 | **7,0** |

**Constats du 03/10** : 2 critiques conditionnels **clos** · 14 importants : **14 corrigés** (I11 actif en production avec Redis, sur un seul processus) · 16 mineurs : **15 corrigés**, 1 ouvert et non retenu (M5). **5 nouveaux défauts** trouvés et corrigés pendant les corrections (cache, séances fantômes dans le planning, réglages sans effet, bilans absents de l'export, § A.4). **10 retours d'usage réel** le 04/10 : 8 corrigés, 1 non reproduit, 1 à mesurer (§ A.4 bis).

---

## Sommaire

A. [Mise à jour du 04/10](#a-mise-à-jour-du-0410) (dernière révision après les PR #33 et #34, le 06/10)
  - A.1 Méthode · A.2 Notes par axe · A.3 Parcours par profil · A.4 Statut des constats · A.4 bis Usage réel · A.4 ter PR #27 · A.4 quater PR #29 · A.4 quinquies PR #31 · A.4 sexies PR #33-#34 · A.5 Ce qui manque pour 8 · A.6 Non vérifiable
B. [Audit du 03/10 — détail conservé (état avant corrections)](#b-audit-du-0310--détail-conservé)
  - 0. Méthode · Parties 1 à 4 · 5. Suivi du 30/09 · 6. Écarts doc/code · 7. Non vérifiable · 8. Annexe

---

## A. Mise à jour du 04/10

### A.1 Méthode

- **Code** : lecture de `main` après la PR #24 (64 modules `core/`, 19 blueprints, 37 gabarits) ; diff complet des PR #6 à #24 relu.
- **Exécution** (sur `345334c`) : `pytest` **1 192 passés** en mémoire, et la même suite rejouée avec cache, verrous, quotas et tâches IA dans Redis — simulé et vrai serveur local, 1 174 passés avec les tests dédiés au vrai Redis ; la CI la rejoue sur `redis:7-alpine` ; tests navigateur (Chromium, 375 × 812) **23 passés** (dont repas détaillé, renommage qui garde l'identifiant, génération suivie jusqu'au programme, saisie reprise à la relance, carte ouverte après la dernière série, échauffement enregistré à part) ; suite JS **113 passés** ; couverture de lignes Python **81 %** (03/10 : 71 %) — connexion 91 %, admin 89 %, programme 84 %, paiement 76 %, état partagé 91 %. Gunicorn lancé localement : 2 processus avec `REDIS_URL` et `WEB_CONCURRENCY=2`, 1 seul sans Redis (alerte journalisée). La fausse base des tests applique désormais l'index unique de production. Suite Python rejouée date figée sur chacun des 7 jours de la semaine (matin du 04/10) : verte.
- **Reproductions** : chacune des reproductions corrigées du 03/10 (R1 à R12) est rejouée par un test du dépôt (par exemple `tests/test_rpe_suggestion.py` pour R11, `tests/e2e/test_seance_navigateur.py` pour R1 et R2, `tests/test_rotation.py` pour R3, `tests/test_ecritures_croisees.py` pour R9).
- **Mesures** : premier champ de saisie à **519 px** du haut sur un compte neuf (03/10 : 836 px) ; poids réseau compressé — Programme 216 → 28 ko, séance 126 → 20 ko, accueil 28 → 8 ko.
- **Base de production** : migrations v37, v38, v39 vérifiées le 03/10 par le connecteur Supabase (lecture seule) : aucune règle RLS côté client, aucun droit `anon`/`authenticated`, vues en `security_invoker`, RLS actif sur les 11 tables. Migration **v40** (`nutrition.grams`, `nutrition.food`, contrainte `nutrition_grams_check`) appliquée le 04/10 avec l'accord du propriétaire, colonnes et contrainte relues en base. Migration **v41** (index unique `history_serie_unique`) appliquée le 04/10 avec son accord, après vérification en lecture seule : 1 136 lignes, 0 doublon ; index relu en base. Le site n'étant pas joignable d'ici, la fenêtre entre l'index et le déploiement de la PR #13 n'a pu être surveillée que par les journaux Supabase (aucun refus d'unicité relevé). Les PR #16, #17 et #19 n'apportent aucune migration. Migrations **v42** (`history.exercise_id` + index partiel) et **v43** (`history.type_serie` + contrainte) appliquées le 04/10 avec l'accord du propriétaire, relues en base, aucune ligne réécrite. Au 05/10, aucune série n'a encore été enregistrée depuis leur déploiement : identifiants et échauffements restent à constater sur une vraie séance. Migration **v44** (colonnes cardio `duree_min`, `distance`, `calories`, `vitesse`, contrainte `history_cardio_colonnes_check`, vues `user_last_activity` et `admin_history_stats`) appliquée le 05/10 avec l'accord du propriétaire, **après** le déploiement du code de la PR #27, puis service web redémarré. Avant : rejouée deux fois sur un PostgreSQL 16 local avec les 25 lignes cardio de production (SQL et Python identiques, idempotente). Après, relu en base : 25 lignes cardio, 0 avec des minutes ou des km dans `reps`/`poids`, 24 calories et 8 vitesses passées en colonnes, plus aucun « Cal: »/« Vit: » numérique en remarque, aucun droit `anon`/`authenticated` sur les vues ; tonnage admin 394 009 → 307 324. Migration **v45** (table `reglages`) appliquée le 05/10 avec l'accord du propriétaire, après le déploiement de la PR #29 (aucun redémarrage requis : la table est redemandée chaque minute). Avant : les deux blobs `_settings` de production relus, identiques à ceux du rejeu local (PostgreSQL 16, 5 profils dont valeurs invalides et heures hors bornes : 0 écart avec le code, idempotente). Après, relu en base : 2 lignes, chacune fidèle à son ancien réglage (heure 15 h et pré-remplissage coupé conservés pour l'un, heure par défaut pour l'autre), plus aucun programme portant `_settings`, versions incrémentées une fois, RLS actif sans règle, aucun droit `anon`/`authenticated` ; journaux du démarrage sans erreur. Migration **v46** (table `calques_seance`, reprise des bilans) appliquée le 06/10 avec l'accord du propriétaire, après le déploiement de la PR #31. Avant : rejouée deux fois sur un PostgreSQL 16 local avec les calques et bilans réels (idempotente, une ligne déjà en table gagne), puis l'état de production relu identique. Application : le connecteur Supabase a dépassé son délai sur le bloc entier (rien d'écrit, vérifié), la migration a donc été passée en trois étapes idempotentes, avec une vérification en base après chacune. Après, relu en base : 4 calques repris (le brouillon du 11 juin, au-delà de 84 jours, écarté), 23 bilans (5 + 18), aucun bilan du blob laissé de côté, plus aucun programme portant ces cinq clés, versions incrémentées une fois, RLS actif sans règle, aucun droit `anon`/`authenticated` ; journaux du service sans erreur. L'entrée `v46_calques_seance` de l'historique Supabase ne contient que la création de la table (les données sont passées par des requêtes à part) ; le fichier du dépôt reste la référence complète. Migration **v47** (table `etat_compte`) appliquée le 06/10 avec l'accord du propriétaire, après le déploiement de la PR #33. Avant : rejouée sur un PostgreSQL 16 local avec les formes de production (0 écart avec le code, idempotente), puis l'état de production relevé (5 programmes concernés). Elle a été appliquée en trois étapes : création de la table, recopie, nettoyage du blob. Après, relu en base : 5 lignes, chacune identique au relevé (badges, défis, record, plats, cibles nutrition) ; plus aucun programme portant ces clés, `_archive` ou `_legacy_volume` ; versions incrémentées une fois ; RLS actif sans règle ; aucun droit `anon`/`authenticated`. Le blob ne garde plus que des clés de programme (`_planning`, `_programmes`, `_profiles`, `_seance_prog`, `_rotation`, équipement, origine).
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
| 8 | Cardio | 4 | 6 | **6** | Durée, distance, calories et vitesse dans leurs colonnes (v44, constaté sur un vrai cardio le 05/10) ; une journée de cardio seul compte pour le rappel et la relance ; durée en minutes et secondes, chrono qui garde les secondes (PR #34). GPS seulement écran allumé, pas de zones cardiaques, Strava seulement par import CSV. |
| 9 | Mode hors-ligne | 4 | 5 | **7** | « Terminer » borné à 6 s, rejeu borné à 8 s, semaine entière gardée avec pastille ; prouvé en mode avion (test navigateur). |
| 10 | Notifications et relances | 5 | 6 | **7** | Récap du dimanche ajouté, rappels suivant la rotation ; tout dépend d'un cron externe, invérifiable d'ici. |
| 11 | Design et cohérence UI | 5 | 5 | **6** | Écran de séance allégé, équipement en tête de carte, en-tête qui ne casse plus en portrait (il cassait dès qu'un record tombait, vu en usage réel) ; 61 `style=` en ligne, cohérence inégale entre pages. |
| 12 | Performance ressentie | 5 | 6 | **7** | Compression gzip (pages 4 à 8 fois plus légères), vidéo PRO chargée seulement au tap (895 ko épargnés), flux du coach plafonnés à 6 par instance, plus de flou GPU sur les cartes et les barres fixes (batterie, effet non mesuré) ; Redis branché en production (état partagé actif), mais toujours un seul processus (`WEB_CONCURRENCY` non défini). |
| 13 | Architecture du code | 6 | 6 | **7** | Modules isolés, plafonds de taille tenus par tests, état partagé entre instances (`core/partage.py`, Redis ou mémoire, repli si Redis tombe) ; le blob `programs.data` a perdu ses réglages (v45), ses calques (v46) et l'état du compte (v47) : il ne contient plus que le programme. |
| 14 | Modèle de données | 4 | 4 | **7** | Une série = une ligne (index unique), écritures idempotentes, identifiant d'exercice stable qui survit aux renommages (v42), type de série dans sa colonne (v43), cardio dans ses propres colonnes, verrouillé par une contrainte (v44), réglages dans leur table typée (v45), calques du jour une ligne par séance et par date (v46), état du compte dans sa table typée (v47), repas par aliment ; le blob ne porte plus que le programme. Identifiant d'exercice et type de série jamais encore vus sur une vraie séance. |
| 15 | Sécurité | 5 | 6 | **7** | Admin réservé à une connexion Google, v37-v39 vérifiées en base, quotas non contournables ; CSP sans `script-src` stricte. |
| 16 | Robustesse et gestion d'erreurs | 4 | 6 | **7** | Échecs signalés, fin de séance bornée, quota rendu si l'IA échoue, cache cohérent après écriture même entre instances, Redis en panne sans casse. |
| 17 | Tests | 6 | 6 | **7** | 1 270 + 23 navigateur + 113 JS, 81 % de couverture, suite rejouée sur un vrai Redis en CI ; tout tourne sur une fausse base (v44 à v47 rejouées à la main sur un vrai Postgres, pas en CI), et une seule séance réelle a trouvé dix défauts qu'ils ne voyaient pas. |
| 18 | Monétisation et paywall | 4 | 5 | **7** | Page PRO honnête, essai qui montre coach et debrief, remboursement et litige retirent PRO (webhook abonné aux trois événements), vrais identifiants AdMob, funnel juste sur sa fenêtre (M14) ; achat Android qui peut sortir de l'app, conversion jamais mesurée. |
| 19 | Boucle de rétention | 4 | 6 | **7** | Défi relatif, récap du dimanche, progression racontée, semaine allégée ; aucune dimension sociale. |
| 20 | Accessibilité | 6 | 7 | **7** | Inchangé. |

Moyenne : **6,9** (138 / 20, inchangée après les PR #27, #29 et #31). Étapes : 6,5 (130 / 20), puis 6,7 (133 / 20) avec l'onboarding (6 → 7) et la nutrition (5 → 7), puis 6,8 (135 / 20) avec le modèle de données (5 → 6) et le générateur (6 → 7), puis 136 / 20 avec la monétisation (6 → 7), 137 / 20 avec l'architecture (6 → 7), enfin **138 / 20** avec le modèle de données (6 → 7). Ni la saisie ni le design ne montent malgré les corrections du 04/10 : ce qu'elles réparent, c'est ce que l'usage réel a trouvé cassé. Les tests restent à 7 malgré I14 clos : 8 demanderait des tests contre une vraie base et plus de parcours navigateur. **Après la PR #27, aucun axe ne monte**, et c'est voulu : le modèle de données reste à 7 tant que `programs.data` mélange programme, réglages et calques ; le cardio reste à 6, rien n'ayant changé pour l'utilisateur ; le funnel juste ne vaut pas une conversion mesurée. **Après la PR #29, toujours rien** : le blob a perdu une famille de clés sur quatre, le modèle de données reste à 7 ; retirer des réglages qui ne faisaient rien rend Gestion honnête, mais n'ajoute aucune fonction. **Après la PR #31, toujours rien** : deux familles de clés sur quatre sont sorties, le modèle de données reste à 7 tant que défis, badges et plats vivent dans le blob ; la robustesse ne monte pas pour des conflits d'écriture que personne n'a vus en usage réel. **Après les PR #33 et #34, toujours rien.** Le blob ne porte plus que le programme, ce qui levait la dernière réserve écrite sur le modèle de données. Pourtant, il reste à 7 : le barème demande une preuve, et les deux colonnes qui font l'essentiel de son progrès (identifiant d'exercice v42, type de série v43) n'ont encore reçu aucune série réelle. Le cardio reste à 6 : saisir les secondes corrige une gêne d'usage, mais n'ajoute ni zones cardiaques ni suivi en arrière-plan.

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

**F5 — 18 bilans de séance absents de l'export et du coach.** Les bilans écrits avant la table `session_notes` (v34) étaient restés dans le blob. La page de séance les relisait en repli, mais l'export des données (RGPD) et le coach ne lisent que la table : pour eux, ces 18 notes et commentaires n'existaient pas. Trouvé en mesurant le blob avant la PR #31 ; la v46 les a repris en table (une ligne déjà présente gagne).

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

### A.4 quinquies PR #31 (06/10) : les calques du jour sortent de `programs.data`

- **Table `calques_seance` (v46)** : une ligne par compte, séance et date, une colonne par calque (exercices ajoutés, brouillon de séance libre, échanges du jour, ordre des cartes) ; une ligne vide n'est pas gardée ; fermée au navigateur et effacée avec le compte.
- **Chaque geste en séance écrit sa ligne**, sous verrou, au lieu de relire et réécrire le programme entier et de passer par son verrou optimiste. La fin de séance, la purge à 84 jours, le renommage d'une séance et le reset total suivent.
- **F5** : voir § A.4.
- **Mise en production sans fenêtre** : même règle que la v45 (table absente = programme comme avant, table redemandée chaque minute, un reste du blob s'affiche tant qu'une séance n'a pas de ligne).
- 20 tests (`tests/test_calques_table.py`), écrits en échec avant le code.

### A.4 sexies PR #33 et #34 (06/10) : l'état du compte sort du blob, le cardio prend les secondes

- **Table `etat_compte` (v47)** : une ligne par compte, une colonne typée par donnée (badges, record de série, défis faits et gagnés, « upsell vu », debrief gratuit, semaine allégée appliquée ou ignorée, plats de la semaine, cibles nutrition perso), compteurs ≥ 0 et types vérifiés par la base ; fermée au navigateur et effacée avec le compte. Les lecteurs n'ont pas changé : la conversion se fait à la frontière (`core/db_etat.py`).
- **Pas d'écrasement entre requêtes** : seules les colonnes qu'une requête a changées depuis sa lecture sont écrites, par-dessus la ligne relue en base. Un badge gagné pendant qu'un autre onglet enregistre les plats de la semaine reste acquis (même règle que le verrou optimiste du programme). Ce défaut a été trouvé par les tests pendant l'écriture de la PR, avant toute mise en production.
- **Reset soft supprimé** (§ B, Partie 4, C.3) : route, carte de Gestion et archive réinjectée dans Progrès ; aucun compte ne s'en servait (aucune `_archive` en production). Le reset total reste.
- **Mise en production sans fenêtre** : même règle que v45 et v46. Migration appliquée en trois étapes (table, recopie, nettoyage du blob) avec une vérification en base après chacune (§ A.1).
- **Cardio en secondes (PR #34)**, retour du propriétaire : un champ secondes à côté des minutes dans les deux formulaires, et le chrono remplit les deux. `duree_min` étant numérique depuis la v44, aucune migration : 25 min 30 s s'enregistre 25.5, et vitesse, distance et calories se calculent sur la durée exacte. Les écrans qui lisent les minutes entières ne changent pas.
- Tests : 19 pour l'état du compte (`tests/test_etat_compte.py`), 6 pour les secondes (`tests/test_cardio_secondes.py`), écrits en échec avant le code.

### A.5 Ce qui manque pour atteindre 8

Par impact décroissant :

Faits le 04/10 : la nutrition (PR #10), les petits trous visibles (PR #11), l'unicité des séries et le suivi des renommages (PR #13), la génération IA en tâche de fond (PR #14), les revenus (PR #16 : M6, M7, M12, M13), les tests de connexion, d'admin et du programme (PR #17 : I14), l'état partagé entre instances (PR #19 : I11), l'identifiant d'exercice (PR #22), les retours d'usage réel (PR #23), les séries d'échauffement (PR #24). Le 05/10 : les mineurs M14 à M16 et le cardio en colonnes (PR #27, v44), puis les réglages (PR #29, v45) et les calques du jour (PR #31, v46) sortis du blob. Le 06/10 : l'état du compte (PR #33, v47), ce qui vide le blob de tout ce qui n'est pas le programme, et la durée du cardio en secondes (PR #34).

1. **Usage réel répété** : d'autres séances du propriétaire (et d'autres utilisateurs) pour vérifier U5, mesurer U7, et constater en base les identifiants, les échauffements et le cardio au nouveau format. C'est ce qui sépare « testé » de « prouvé ».
2. **Modèle de données, de 7 à 8** : la sortie du blob est **terminée** (v44 à v47). Il reste la preuve : une séance réelle doit écrire `exercise_id` et `type_serie` en base, et ce constat suffit à faire passer l'axe à 8.
3. **Nutrition, pour passer de 7 à 8** : recettes et aliments personnels, tendance de la semaine, cible qui s'ajuste au poids réel.
4. **Rétention sociale** : binôme de régularité ou streak partagé.
5. **Preuve d'usage chiffrée** : le barème exige un niveau *prouvé* ; il faudra des chiffres réels (rétention J7/J30, conversion de l'essai) que le dépôt ne contient pas.
6. **Mineurs** : tous fermés sauf M5 (CSP stricte), écarté tant qu'Alpine.js impose `unsafe-eval`.

### A.6 Non vérifiable depuis le dépôt (au 06/10)

- **Cron horaire** (`/tasks/reminders` ou `cron_reminders.py`) : rappels, récap du dimanche et purge des événements en dépendent.
- **Railway** : Redis ajouté et branché (`REDIS_URL` sur web, même région europe-west4) ; le journal « partage: stockage redis, 1 processus » a été relu par le connecteur après le redémarrage du 05/10. 1 réplique et `WEB_CONCURRENCY` non défini, d'après le propriétaire. Option « Wait for CI » active : le déploiement de la PR #27 a attendu la CI de `main`. Le site lui-même n'est pas joignable depuis l'environnement d'audit.
- **Variables** : identifiants AdMob réels posés (éditeur `ca-app-pub-3523578671547864`, aucune alerte au démarrage, d'après le propriétaire) ; `CRON_SECRET` et `ANTHROPIC_API_KEY` non vérifiés.
- **Stripe** : webhook abonné à `charge.refunded`, `charge.dispute.created` et `charge.dispute.closed` (confirmé par le propriétaire, invérifiable d'ici). Aucun remboursement ni litige réel n'a encore exercé ce chemin.
- **Usage réel** : rétention, conversion, satisfaction. Un seul retour de séance à ce jour (§ A.4 bis).
- **Sur le téléphone** : l'effet du retrait du flou sur la batterie (Paramètres → Batterie), et les premières séries écrites avec `exercise_id` et `type_serie` (aucune au 06/10 : les dernières séries de musculation datent du 04/10, avant la v42). Le premier cardio au format v44 est **constaté** : vélo du 05/10, 9 min, 2,26 km, 103 kcal, vitesse 15,07 km/h déduite et enregistrée, `reps` et `poids` à 0. Le premier cardio avec secondes reste à voir.
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
3. **Fait le 06/10 (PR #33).** **Le « reset soft » et l'archive héritée** (`routes/gestion.py:422-464`, clés `_archive`, `_legacy_volume`, réinjectées dans les statistiques par `routes/progres.py:116-133`) : un mécanisme de l'époque Streamlit qui efface l'historique pour en garder un résumé dans le blob — dette et risque de perte, pour un besoin que l'export gratuit couvre.

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
