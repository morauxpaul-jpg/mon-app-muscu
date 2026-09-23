# RAPPORT D'AUDIT — Muscu Tracker PRO

**Date** : 2026-09-21 · **Commit audité** : `5940de5` (branche `main`) · **Auditeur** : externe, lecture seule du dépôt.
**Périmètre** : `pwa/` (Flask, 21 blueprints/modules, 33 templates, 17 scripts JS, 124 tests), `android/` + `capacitor.config.json`, `docs/`, `CONTEXT.md`. Aucune exécution sur device, aucun accès à Supabase/Railway/Stripe (voir § 6). Trois bugs ont été **reproduits** sur la fausse base des tests (`tests/conftest.py`) avec des scripts jetables hors dépôt.

---

## Note globale : **4,5 / 10**

> Une app généreuse en fonctionnalités (coach IA, générateur, nutrition, défis, push, Stripe, parrainage) posée sur un modèle de données qui **perd silencieusement des séances** dans 9 des 20 programmes du catalogue — dont les 3 programmes débutants par défaut — et dont l'éditeur de programme **efface à chaque sauvegarde** les notes de séance, les exercices perso, les badges et le record de streak. Tant que la saisie n'est pas fiable, le reste est de la décoration.

| Bloc | Moyenne |
|---|---|
| Produit (onboarding, saisie, programme, progression, coach, générateur, nutrition, cardio) | 4,6 |
| Plateforme (offline, notifications, design, perf) | 4,3 |
| Technique (archi, données, sécurité, robustesse, tests) | 4,6 |
| Business (monétisation, rétention, accessibilité) | 4,3 |

---

## Sommaire

0. [Méthode et conventions](#0-méthode-et-conventions)
1. [Partie 1 — Notes par axe](#partie-1--notes-par-axe)
2. [Partie 2 — Parcours par profil](#partie-2--parcours-par-profil)
3. [Partie 3 — Audit technique](#partie-3--audit-technique)
4. [Partie 4 — Améliorations et idées](#partie-4--améliorations-et-idées)
5. [Écarts entre la doc (CONTEXT.md) et le code](#5-écarts-entre-la-doc-contextmd-et-le-code)
6. [Non vérifiable depuis le dépôt](#6-non-vérifiable-depuis-le-dépôt)

---

## 0. Méthode et conventions

- Chaque constat cite `fichier:ligne` (chemins relatifs à `pwa/` sauf mention). Les lignes sont celles du commit `5940de5`.
- Barème strict : 10 = état de l'art ; 8-9 = niveau Hevy/Strong, justifié ; 6-7 = correct mais un concurrent fait mieux ; 4-5 = utilisable mais faible ; 1-3 = cassé/absent/contre-productif.
- Trois reproductions exécutées contre `FakeSupabase` (scripts hors dépôt, non commités) :
  - **R1** — sauvegarder « Squat » le lundi puis le vendredi dans « Full Body A » : il ne reste que les lignes du vendredi (`ROWS after Mon+Fri: 2, dates: ['2026-09-18']`).
  - **R2** — un `POST /programme/state` fait disparaître `_custom_exercises`, `_session_notes`, `_badges`, `_streak_record` du blob programme.
  - **R3** — après une séance poids-du-corps complète (Reps=15, Poids=0) : accueil = « 0 SEMAINE » de streak, « Commencer » toujours affiché, « En danger », Séances « 0/1 ».
- La suite de tests existante passe : `124 passed in 1.48s`. Aucun de ces trois cas n'y figure.

---

## Partie 1 — Notes par axe

### Tableau récapitulatif

| # | Axe | Note | En une phrase |
|---|---|---:|---|
| 1 | Onboarding | **6** | Flux 4 étapes propre avec recommandation, mais Google-only, aucun poids/taille demandé, et « custom » débouche sur un accueil vide sans CTA. |
| 2 | Saisie de séance | **4** | Chrono de repos persistant excellent, mais chaque exercice = POST + rechargement complet, tableau 6 colonnes sur 375 px, et perte de données si la séance est faite deux fois dans la semaine. |
| 3 | Programme et planning | **4** | Éditeur Alpine avec autosave et multi-profils, mais pas de reps/repos/tempo dans le modèle, planning par jour de semaine seulement, et l'autosave efface les métadonnées utilisateur. |
| 4 | Progression et statistiques | **5** | Calendrier, volume hebdo, courbe de poids, body map ; mais % body map sur des standards absolus (1RM pecs 140 kg = 100 %), zoom = max poids/semaine, pas de fiche exercice historique. |
| 5 | Coach IA | **5** | Contexte riche (programme + 14 séances + catalogue lié), mais Haiku, 500 tokens, pas de streaming, messages d'erreur qui parlent de Railway à l'utilisateur. |
| 6 | Générateur de programme IA | **4** | JSON validé et quota, mais les **reps générées sont jetées** à l'adoption, les métadonnées sont écrasées, et le planning généré peut retomber dans le bug de la séance dupliquée. |
| 7 | Nutrition | **5** | Mifflin-St Jeor, TDEE suivant la pesée, 269 aliments recherchables côté client, plats de la semaine ; mais pas de code-barres, base 1 000× plus petite que Yazio/MFP, pas d'historique long. |
| 8 | Cardio | **3** | Estimation MET + inclinaison, mais **une seule séance par activité et par semaine** (la 2ᵉ écrase la 1ʳᵉ), pas de chrono live, pas de GPS, pas d'import Strava/Health. |
| 9 | Mode hors-ligne | **3** | SW + file localStorage existent, mais une séance jamais ouverte en ligne retombe sur l'accueil, la saisie hors-ligne ne marque rien comme fait, et la coquille native est une webview distante. |
| 10 | Notifications et relances | **4** | Push VAPID en place, mais rappels « locaux » uniquement si l'app est ouverte, et relance des inactifs envoyée **tous les jours pendant 27 jours** sans dédoublonnage. |
| 11 | Design et cohérence UI | **6** | Tokens, sprite d'icônes, dark cohérent ; mais 931 `style=` inline, e-mail + « Déconnexion » sur chaque page, textes 10-11 px, mélange emoji/SVG. |
| 12 | Performance ressentie | **4** | Tout est full-page-reload, l'historique entier est rechargé et parcouru à chaque page, l'analytics est synchrone, et un appel LLM bloque le worker gunicorn. |
| 13 | Architecture du code | **5** | Découpage blueprints/core propre et façade `core.data` ; mais blob JSON fourre-tout (25+ clés `_x`) avec 5 listes blanches divergentes, écritures dans des GET, template de 1 445 lignes. |
| 14 | Modèle de données | **3** | Clé fonctionnelle (semaine, séance, exercice) qui interdit deux occurrences d'une séance par semaine ; RPE encodé dans une remarque ; cardio via chaînes magiques ; noms d'exercices comme clés étrangères. |
| 15 | Sécurité | **6** | CSRF, CSP en deux couches, JWT vérifié (HS256 + JWKS), Stripe signé, service_role côté serveur ; mais pas de ProxyFix, `/push/unsubscribe` sans contrôle de propriétaire, secrets d'infra dans les messages d'erreur. |
| 16 | Robustesse et gestion d'erreurs | **4** | Beaucoup de `try/except` et pages d'erreur dédiées ; mais pertes de données silencieuses, `save_hist` delete+insert non transactionnel, et aucune pagination Supabase. |
| 17 | Tests | **5** | 124 tests rapides sur une fausse DB, bonne couverture des routes et du billing ; mais aucun test sur les deux bugs critiques, zéro test JS/offline, fausse DB sans limite de lignes. |
| 18 | Monétisation et paywall | **5** | Stripe complet (mensuel/annuel/lifetime, upgrades, portail), upsell post-3ᵉ séance instrumenté ; mais l'app native affiche des prix sans bouton d'achat (risque Play), annuel au-dessus du marché, essai restreint incohérent. |
| 19 | Boucle de rétention | **5** | Streak, badges, défi hebdo, nudge, push, patch notes ; mais streak cassé pour le poids du corps, relance spam, aucun PR célébré en séance, aucune dimension sociale. |
| 20 | Accessibilité | **3** | `--text-3` à 35 % d'opacité sur fond sombre (≈ 2,3:1), tailles 10-11 px, cibles < 30 px, un seul `role=`, `user-select:none` sur `body`. |

### Justifications détaillées

**1. Onboarding — 6/10**
- Flux réel : login Google uniquement (`routes/auth.py:61-68`, `templates/login.html:129`), puis 4 étapes Alpine avec bulles « ? » sur les niveaux et preview des séances (`templates/onboarding.html:200-420`), recommandation scorée par fréquence/équipement/niveau/objectif (`core/catalog.py:962-1045`). C'est mieux que Strong (pas d'onboarding) et au niveau de Hevy.
- Manques : ni poids ni taille demandés (`routes/onboarding.py:235-251`) alors que Nutrition, badge « Costaud » (`routes/accueil.py:123-133`) et calories cardio (`routes/seance.py:1166-1168`) en dépendent ; « Bienvenue, guerrier » (`templates/onboarding.html:201`) après avoir proposé « Femme ». Choisir « Créer mon propre programme » redirige vers `/accueil` (`routes/onboarding.py:315`) où rien n'indique qu'il faut aller dans Programme (aucun état vide dans `templates/accueil.html`).
- Sur-sollicitation J1 : tutoriel 6 étapes (`static/js/tutorial.js:13-40`) + modale « Active les notifications » à ~3,6 s (`templates/base.html:268,324`) + éventuel patch notes, sans orchestration entre eux.

**2. Saisie de séance — 4/10**
- Points forts réels : chrono de repos global persistant en `localStorage` avec échéance absolue, notification OS via Capacitor ou SW (`static/js/rest-timer.js:1-20,165-215`), brouillon par exercice restauré au reload (`templates/seance_edit.html:1233-1256`), pré-remplissage des charges, suggestion de surcharge avec RPE (`core/muscu.py:137-211`), reconstruction depuis l'historique (`routes/seance.py:423-470`).
- Ergonomie salle : chaque exercice est un `<form method="post">` → redirection → rendu complet de la page (`templates/seance_edit.html:357-370`, `routes/seance.py:801-805`), avec restauration du scroll par `sessionStorage` (`:1426-1438`). Hevy/Strong valident une série sans quitter l'écran. Le tableau a 6 colonnes (Sér./Reps/Poids/RPE/Remarque/×) dans ~343 px (`:313-320`), bouton × en `padding:4px 8px` (`static/css/components.css:489-497`). Aucune durée de séance n'est mesurée (`routes/seance.py:1239-1278` n'enregistre ni début ni fin).
- Fiabilité : sauvegarder un exercice supprime ses lignes de **toute la semaine** pour cette séance (`core/db.py:345-364`) — reproduction R1. Un « Enregistrer » oublié = séries jamais persistées (le brouillon reste local).

**3. Programme et planning — 4/10**
- Le modèle d'exercice est `{name, sets, muscle}` (`routes/programme.py:281-289`) : pas de reps cibles (les `_reps_hint` du catalogue sont retirés à la construction, `core/catalog.py:1092-1102`), pas de repos par exercice (lu mais jamais écrit, `routes/seance.py:302`), pas de tempo, pas de supersets, pas de blocs/périodes.
- Le planning est un dict `jour → séance` (`routes/programme.py:32-36`) : impossible de faire un cycle A/B/A/B glissant indépendant des jours ; et `planning_for()` recycle la même séance sur plusieurs jours (`core/catalog.py:24-35`), ce qui déclenche R1 pour 9 programmes sur 20 (`fb_deb_3j`, `fb_deb_maison_3j`, `fb_pdc_3j`, `ppl_5j`, `ppl_6j`, `circuit_salle_3j`, `circuit_maison_3j`, `hiit_muscu_4j`, `force_5x5_3j`).
- L'autosave `/programme/state` reconstruit le blob à partir d'une liste blanche de 7 clés (`routes/programme.py:306-311`) : R2 prouve la perte de `_custom_exercises`, `_session_notes`, `_badges`, `_streak_record` (aussi `_challenges_*`, `_upsell_seen`, `_meal_plan`, `_equipment_details`, `_seance_order`). `GET /programme` écrit en base à chaque affichage (`:190`).

**4. Progression et statistiques — 5/10**
- Présent : calendrier mensuel avec rattrapage neutre (`routes/progres.py:643-701`), volume 8 semaines (`:709-719`), courbe de poids 90 j avec delta 30 j coloré selon l'objectif (`:331-380`), stats cardio (`:224-276`).
- Faible : le % body map compare le 1RM à un standard absolu par muscle (`MUSCLES["Pecs"]["std"]=140`, `routes/progres.py:24-39,136`) sans tenir compte du sexe ni du poids — une femme de 55 kg restera « rouge » à vie. Le zoom mouvement trace le **max de poids par semaine** (`:554-561`), pas d'e1RM, pas de volume par exercice, pas de liste « toutes mes séances de cet exercice » (ce que Hevy et Strong offrent gratuitement).
- Gating : body map, hall of fame, 1RM et table RM réservés `is_vip` (`:516-536,576-578`) ; le gratuit ne voit qu'un aperçu verrouillé.

**5. Coach IA — 5/10**
- Vrai différenciant : system prompt avec profil, programme détaillé, 14 dernières séances, catalogue et liens d'action `/programme?apply=ID` (`routes/coach.py:34-72,101-164`), conversations persistées (`core/db.py:903-965`), quota 15/j (`routes/coach.py:30,167-187`).
- Limites : `claude-haiku-4-5`, `MAX_TOKENS = 500` (`:31-32`) → réponses tronquées dès qu'on demande un plan ; pas de streaming (l'utilisateur regarde un spinner 3-8 s) ; pas de mémoire inter-conversations ; il ne connaît ni les RPE ni les bilans de séance (le résumé ne passe que séries/meilleur poids, `:129-164`).
- Fuite d'infra vers l'utilisateur final : « Vérifie ANTHROPIC_API_KEY dans Railway », « Ajoute du crédit sur console.anthropic.com » (`:403-411`).

**6. Générateur de programme IA — 4/10**
- Bon socle : `parse_and_validate` pure et testée (`routes/generator.py:112-197`, `tests/test_generator.py`), quota 3/semaine via `events` + limiter (`:34,283-300,319`).
- Le programme adopté perd ses reps (« On NE stocke pas les reps », `:412-414`) : l'utilisateur paye une génération et récupère des noms d'exercices + un nombre de séries, sans la prescription qui fait la valeur du programme. Même liste blanche que l'import → mêmes pertes que R2 (`:420-423`).
- Le planning généré peut mettre une même séance deux fois (le prompt autorise « un split cyclé », `:252`) → bug R1 sur un programme payant.

**7. Nutrition — 5/10**
- Calculs corrects (Mifflin-St Jeor, facteurs d'activité, splits macros, `routes/nutrition.py:27-56,119-122`), cible manuelle possible (`:125-131`), synchro TDEE ↔ dernière pesée (`routes/progres.py:387-407`), 269 aliments avec portions embarqués (36 Ko de JSON par rendu, `core/foods_data.py`), plats de la semaine importables (`routes/nutrition.py:66-116`).
- Absent par rapport au marché : scan code-barres, base ouverte (Open Food Facts), photos, historique > semaine (`sum_nutrition_range` n'est appelé que pour la semaine courante, `:247`), rappels de repas.
- Réservé `is_vip` (`:186-189,288-291`) — y compris l'essai restreint, ce qui en fait la seule vitrine de l'essai.

**8. Cardio — 3/10**
- Saisie manuelle (durée, distance, FC, inclinaison, RPE) avec estimation MET (`routes/cardio.py:23-35,77-95`).
- Cassé : `replace_exo_rows(date_str, "Cardio Course", "CARDIO:Course", rows)` (`routes/cardio.py:189-201`) supprime toutes les courses de la semaine avant d'insérer → **une seule course par semaine survit**. Idem en séance (`routes/seance.py:1191`).
- Rien de live (pas de chrono, malgré le mot « chrono » dans la docstring `:1`), pas d'import Strava/Garmin/Health Connect, pas de cartes.

**9. Mode hors-ligne — 3/10**
- Ce qui existe : SW network-first avec fallback cache (`static/service-worker.js:166-198`), file `localStorage` rejouée au retour réseau avec détection de session expirée (`static/js/offline.js:281-357`), brouillons locaux, chrono local.
- Ce qui casse (déroulé § Partie 2, profil « sous-sol ») : les URLs `/seance?mode=…&name=…&date=…` ne sont en cache que si déjà visitées ; sinon `c.match("/accueil")` (`service-worker.js:180`). Après un « Enregistrer » hors-ligne, la page ne se recharge pas : l'exercice n'apparaît jamais « fait », et le brouillon a été effacé par `prepareSave` (`templates/seance_edit.html:1333-1337`) avant l'interception. Le rejeu se fait en parallèle (`Promise.all`, `offline.js:320-350`) sans ordre. `controllerchange` recharge la page à chaud, en pleine séance (`static/js/sw-register.js:475-481`).
- La coquille Android charge l'URL de prod (`capacitor.config.json:5-6`) : sans réseau au démarrage à froid, c'est `www/index.html` « Connexion impossible » (sauf si le SW de la WebView répond — non vérifiable).

**10. Notifications et relances — 4/10**
- Infra push complète : VAPID, table `push_subscriptions`, `/push/*`, cron `/tasks/reactivation` avec secret à temps constant (`routes/push.py:25-87`, `core/push.py:379-420`).
- Les rappels « matin / soir / streak » ne se déclenchent que si la page est ouverte (`static/js/notifications.js:66-110`) : un rappel de séance quand on est déjà dans l'app ne sert à rien. Aucun push planifié côté serveur à l'heure de la séance prévue.
- La relance cible tous les inactifs 3-30 j **à chaque exécution** sans mémoriser l'envoi (`core/push.py:430-481` ; `get_inactive_user_ids` ne lit que `history`, `core/db.py:816-839`) : un cron quotidien = 27 notifications identiques « On reprend ? 💪 » d'affilée → désinstallation.

**11. Design et cohérence UI — 6/10**
- Système cohérent : tokens 4 niveaux de texte, accent, radius (`static/css/tokens.css`), sprite SVG unique, glass, `inline-confirm` partout (jamais de `confirm()` natif — vérifié par grep), états de chargement sur les boutons (`templates/seance_edit.html:1134-1142`).
- Dette : 931 attributs `style=` et 32 `onclick=` dans les templates ; barre du haut qui affiche l'**e-mail complet** et un bouton « Déconnexion » sur chaque écran (`templates/base.html:117-122`) — aucune app fitness ne fait ça ; mélange emoji (🔥💪👋) et icônes SVG dans les mêmes cartes (`templates/accueil.html:29,273`).
- Micro-typo : 10-11 px à plusieurs endroits (`templates/seance_edit.html:89,162`), labels `.stat-label` en `--text-3`.

**12. Performance ressentie — 4/10**
- Chaque action de séance = requête + redirect + rendu Jinja complet + re-exécution d'Alpine (`routes/seance.py:801-805`). `/accueil` charge l'historique complet (`core/db.py:108-146`, non paginé), `get_profile` et `get_onboarding` non cachés (`core/db.py:429-464`, `routes/accueil.py:228-231`), puis jusqu'à 4 écritures `save_prog` (badges, streak record, upsell, défi : `routes/accueil.py:139-145,305-309,472-479,515-525`) et des `track()` synchrones (`core/analytics.py:308`).
- Serveur : `gunicorn --bind … app:app` sans `-w` ni `--timeout` (`railway.json:7`) → 1 worker sync par défaut (à moins que `WEB_CONCURRENCY` soit posée sur Railway — non vérifiable). Un appel Claude de 5-20 s (`routes/generator.py:359-364`, `routes/coach.py:379-385`) **bloque tous les autres utilisateurs** pendant ce temps ; au-delà de 30 s, 502.
- Poids : vidéo 3,5 Mo autoplay sur chaque mur VIP (`templates/vip_wall.html:24-28`), 36 Ko de FOODS inline sur Nutrition, 10 Ko de polygones sur chaque page séance (`routes/seance.py:740`).

**13. Architecture du code — 5/10**
- Lisible : blueprints par domaine, `core/` sans Flask (sauf `data.py`/`analytics.py`), façade qui force `g.user_id` (`core/data.py:19-26`), fonctions pures testables (`overload_suggestion`, `parse_and_validate`, `weekly_challenge`).
- Le blob `programs.data` sert de base de données secondaire : 25+ clés `_x` recensées par grep (`_planning, _profiles, _origin, _extras, _active_profile, _started_at, _settings, _archive, _programmes, _name, _libre_draft, _legacy_volume, _custom_exercises, _cardio, _seance_prog, _session_notes, _meal_plan, _equipment_details, _upsell_seen, _streak_record, _seance_order, _nutrition, _equipement, _challenges_won, _challenges_done, _badges, _jours`). Cinq endroits reconstruisent ce blob avec des listes blanches **différentes** (`routes/programme.py:306-311`, `:621-624`, `:690-700`, `routes/generator.py:420-423`, `routes/onboarding.py:290-305`).
- Effets de bord dans des GET (`routes/programme.py:190`, `routes/seance.py:83-87`, `routes/accueil.py` ×4). `seance_edit.html` = 1 445 lignes dont ~750 de JS inline. `MUSCLE_LIST` dupliqué dans 4 fichiers (`routes/seance.py:25`, `routes/programme.py:26`, `routes/gestion.py:26`, `routes/generator.py:37`).

**14. Modèle de données — 3/10**
- `history` = une ligne par série avec `(user_id, semaine, seance, exercice, serie, reps, poids, remarque, muscle, date)` (`core/db.py:189-202`) ; **aucun identifiant de séance**. L'unité « une séance » est reconstruite par `(Date, Séance)` en lecture (`routes/accueil.py:88`) mais par **`(semaine, Séance, Exercice)` en écriture** (`core/db.py:345-364`). Cette asymétrie est la cause racine de R1 et du bug cardio.
- Le RPE vit dans `remarque` sous la forme `@RPE8` (`core/muscu.py:121-128`, `templates/seance_edit.html:1186-1194`) ; le cardio vit dans `history` avec `Exercice="CARDIO:Course"`, `Reps=minutes`, `Poids=km`, `Remarque="Cal:… | Vit:…"` (`routes/cardio.py:1-10`). Les exercices sont des chaînes libres : renommer = réécrire tout l'historique (`routes/gestion.py:229-258`).
- `programs.version` + fusion 3 voies (`core/db.py:253-331`) est une bonne défense, mais elle ne peut rien contre des routes qui **omettent** des clés (la fusion considère une clé absente comme « supprimée par nous », `:265-267`).

**15. Sécurité — 6/10**
- Solide : JWT Supabase vérifié avec `audience` et JWKS (`routes/auth.py:82-103`), service_role jamais exposé, tout filtré par `user_id` (`core/db.py` intégral), CSRF par jeton de session + header auto (`app.py:232-276`, `templates/base.html:30-63`), CSP bloquante minimale + report-only complète (`app.py:297-347`), Stripe `construct_event` obligatoire (`routes/billing.py:295-309`), admin par `ADMIN_EMAILS` avec 404 (`routes/admin.py:25-28`), suppression de compte complète (`core/db.py:1200-1230`). Gating VIP côté serveur cohérent (`is_vip_full` sur coach/générateur/export/programmes PRO, `is_vip` sur nutrition/stats) — non contournable côté client.
- Faiblesses : pas de `ProxyFix` → `request.remote_addr` = IP du proxy Railway pour le rate-limit (`core/limiter.py:271-277`) et `request.url_root` en `http://` pour les URLs Stripe (`routes/billing.py:55-56`) ; `/push/unsubscribe` supprime n'importe quel endpoint sans vérifier `user_id` (`routes/push.py:60-68`, `core/db.py:753-757`) ; première requête mutante d'une session sans `_csrf` acceptée (`app.py:264-268`) ; `?token=` accepté en query string pour le cron → secret dans les logs d'accès (`routes/push.py:35-36`) ; messages d'erreur coach/générateur qui décrivent l'infra (`routes/coach.py:403-411`).
- `FLASK_SECRET_KEY` absente → `"dev-insecure-change-me"` avec un simple log (`app.py:76-85`) : l'app démarre en prod avec des cookies forgeables.

**16. Robustesse et gestion d'erreurs — 4/10**
- Bien : pages d'erreur 400/404/413/429/500/503 humaines (`app.py:485-528`, `routes/seance.py:481-486`), rollback best-effort de `save_hist` (`core/db.py:166-184`), revert du quota coach si l'API échoue (`routes/coach.py:190-200`), dégradation gracieuse si Redis/VAPID/Stripe absents.
- Mal : `save_hist` = `delete` puis `insert` par lots de 500 sans transaction (`core/db.py:167-172`) — une coupure entre les deux laisse un historique vide jusqu'au rollback (qui peut échouer aussi). Aucune pagination sur `history` (`core/db.py:117-123`) : si le `max-rows` PostgREST du projet est resté à 1 000 (défaut Supabase), `rename`/`merge`/`reset-soft` (`routes/gestion.py:256,287,390`) réécrivent un historique **tronqué** — perte définitive au-delà de 1 000 séries (~4 mois à 3 séances/semaine). Non vérifiable, mais le code n'a aucune protection.
- Les trois bugs reproduits (R1, R2, R3) ne lèvent aucune erreur : l'utilisateur ne sait pas qu'il a perdu quelque chose.

**17. Tests — 5/10**
- 124 tests en 1,5 s, fausse Supabase requêtable (`tests/conftest.py`), couverture réelle du billing (webhooks, upgrades, StripeObject), CSRF, parrainage, cron, poids corporel, surcharge, générateur.
- Angles morts : aucun test « même séance deux fois dans la semaine » (le test `tests/test_routes.py:106-136` valide même l'écrasement comme comportement voulu), aucun test de préservation des clés `_x` après `/programme/state`, aucun test poids-du-corps sur l'accueil, aucun test JS (offline.js, rest-timer.js, exoBlock), aucun test de charge/pagination. La fausse DB ne simule ni `max-rows` ni la concurrence.

**18. Monétisation et paywall — 5/10**
- Complet côté web : 3 plans inline (`routes/billing.py:34-38`), upgrade avec `superseded` (`:131-152`), portail, webhook source de vérité, funnel admin (`core/db.py:1035-1123`), `paywall()` instrumenté (`core/analytics.py:313-322`), upsell one-shot après 3 séances (`routes/accueil.py:453-483`).
- Android : boutons d'achat masqués mais prix visibles (« À partir de 4,99€/mois », `templates/vip_wall.html:41` ; « 4,99€ », `templates/premium.html:74-75`) et CTA « Passer en PRO » qui mène à une page sans bouton (`:167-173`) → parcours mort **et** exposition à la politique Paiements de Google Play (mention de prix/achat hors Play Billing pour un bien numérique). Aucun « Restaurer mes achats » : un abonné web qui installe l'app Android est bien reconnu (session), mais un natif ne peut jamais devenir client.
- Pricing : 39,99 €/an contre ~25-30 € pour Hevy/Strong ; le gratuit perd le pré-remplissage des charges dès qu'il touche aux réglages (`routes/gestion.py:305-311`) — une punition arbitraire sur la fonction la plus utilisée.

**19. Boucle de rétention — 5/10**
- Mécaniques présentes : streak hebdo avec paliers, 8 badges, défi tournant identique pour tous (`core/challenges.py`), nudge « Content de te revoir », push, partage canvas, parrainage, patch notes.
- Cassé pour un segment entier : tout ce qui compte une séance « faite » sur l'accueil exige `Poids > 0` (`routes/accueil.py:285-288,292-295,315-320,349-354,464-466`) → R3 : le programme « Full Body Poids du Corps » (gratuit, recommandé pour « Poids du corps ») ne fera **jamais** monter le streak ni le compteur de séances.
- Aucune célébration de PR en séance (Hevy affiche le record battu en direct ; ici le record n'est visible qu'en dépliant la carte, `templates/seance_edit.html:236-248`), aucun ami/feed, relance push contre-productive (voir axe 10).

**20. Accessibilité — 3/10**
- Contraste : `--text-3: rgba(255,255,255,0.35)` (`static/css/tokens.css:39`) sur `#0a0a0f` ≈ 2,3:1, utilisé pour les en-têtes du tableau de séries, les labels de stats et les champs (`static/css/components.css:454-458`) ; `--text-2` à 0,55 ≈ 4:1 pour du texte < 14 px.
- Cibles : × de suppression de série (`components.css:489-497`), boutons `exo-info-btn` 22 px (`templates/seance_edit.html:11-28`), aucun `min-height: 44px` dans les CSS.
- Sémantique : 1 seul `role=` dans tous les templates, `<div class="opt" @click>` pour les choix d'onboarding sans `role="radio"` ni clavier (`templates/onboarding.html:209-213`), `user-select:none` sur `body` (`static/css/theme.css:33-35`), `prefers-reduced-motion` absent de `components.css` et `rest-timer.css`.

---

## Partie 2 — Parcours par profil

### 2.1 Débutant complet, jour 1 — **6/10**
**Parcours** : landing (`/`) → « Commencer — Connexion Google » (`templates/landing.html:216`) → OAuth → `/auth/bridge` → onboarding 4 étapes → programme recommandé « Full Body Débutant — Salle » (score fréquence 3 + salle + débutant, `core/catalog.py:990-1040`) → `/accueil` → tutoriel 6 étapes → modale notifications → onglet Séance → « Quelle séance aujourd'hui ? » → « Full Body A » → tuto séance (RPE expliqué : « 6 = facile, 8 = il restait 2 reps en réserve, 10 = échec », `static/js/tuto-seance.js:55-56`) → saisie → « Enregistrer » par exercice → « Terminer la séance » → bilan étoiles → accueil avec confettis.
Comprend-il quoi faire ? **Oui**, c'est le parcours le mieux travaillé de l'app. Le RPE est optionnel et expliqué ; le split est expliqué par carte (« 2 séances alternées (A/B) », `core/catalog.py:56`).
**3 frictions** :
1. Pas de compte sans Google (`routes/auth.py`) et rien pour tester avant de se connecter (pas de mode démo).
2. Trois overlays concurrents en 4 secondes (tutoriel, notifications, patch notes éventuels — `templates/base.html:165,268,324`).
3. Sur le tableau de séries, il doit comprendre que « Enregistrer » est **par exercice** et que fermer l'app sans l'avoir tapé ne sauve rien côté serveur (`templates/seance_edit.html:357-370`).
**Ce qui lui manque** : poids/taille dès l'onboarding, un mode « guidé » qui coche les séries une à une, des GIF/vidéos d'exécution (18 SVG statiques pour 87 fiches, `static/img/exercises/`).

### 2.2 Débutant, semaine 3 — **4/10**
**Ce qui le fait décrocher** : le **vendredi de la semaine 1**, il ouvre « Full Body A » (planifiée lundi **et** vendredi par `planning_for`, `core/catalog.py:24-35`) : toutes les cartes sont repliées « complété » avec les valeurs de lundi (`routes/seance.py:125-136,308-310`). Soit il « Recommence cet exercice » (supprime lundi, `:1003-1013`), soit il modifie et enregistre (écrase lundi, R1). Le lundi devient rouge « MANQUÉE » sur l'accueil (`routes/accueil.py:196-219`) alors qu'il a fait sa séance. Semaine 3, son historique a la moitié de ses séances et son calendrier lui dit qu'il rate une séance sur deux.
S'il est en « Poids du corps » : streak 0, Séances 0/3, « En danger » après chaque séance (R3).
**3 frictions** : (1) R1 ; (2) modale d'upsell à la 3ᵉ séance (`routes/accueil.py:18`) **puis** interstitiel vidéo à l'arrivée sur l'accueil si natif (`static/js/ads.js:89-129`) — deux interruptions au moment de la victoire ; (3) push « On reprend ? 💪 » tous les jours dès 3 jours d'absence (`core/push.py:430-481`).
**Reste-t-il ?** Pas avec des données incohérentes visibles sur l'accueil.

### 2.3 Intermédiaire venant de Hevy/Strong — **3/10**
**Ce qu'il perd en migrant** :
- Ses données : aucun import CSV Hevy/Strong ; l'import n'accepte que le format maison et est VIP (`routes/gestion.py:460-465`).
- La saisie par série sans rechargement, la durée de séance, les supersets, les reps cibles dans la routine (`routes/programme.py:281-289`), les notes par série historisées lisibles (le RPE est dans la remarque), le PR live.
- La bibliothèque : 87 fiches (`core/exercises_data.py`) contre 400+ avec animations chez Hevy ; 18 illustrations.
- Les stats gratuites : chez Hevy, e1RM/volume/best set par exercice sont gratuits ; ici body map/1RM/podium sont `is_vip` (`routes/progres.py:516-536`) et le zoom gratuit n'affiche que le max poids/semaine.
- Ses habitudes : PPL 5j/6j ou Upper/Lower en A/B glissant → R1 sur `ppl_5j`/`ppl_6j` ; impossible de faire « Push » deux fois par semaine sans renommer en « Push 1 / Push 2 ».
**3 frictions** : R1 sur son split, aucun import, historique visible limité à 2 semaines en gratuit (`routes/gestion.py:141,316-317`).
**Verdict** : il repart dans la semaine.

### 2.4 Avancé / « pro » — **3/10**
**Tient-elle la route ?** Non. Ce qu'il attend : périodisation par blocs, % 1RM ou RPE cible par série, e1RM par exercice dans le temps, tempo, RIR, séries d'échauffement distinguées, deload. Ce qu'il trouve : RPE par série (bien, `templates/seance_edit.html:328-337`), suggestion de double progression (bien, `core/muscu.py:137-211`), table RM Epley (`core/muscu.py:14-29`), et c'est tout. Le programme ne stocke aucune prescription ; le générateur jette les reps ; le zoom trace un max hebdo.
**3 frictions** : (1) pas de notion de bloc/cycle ni de semaine relative modifiable (`_started_at` figé) ; (2) exercice = chaîne libre → ses variantes (« Squat (Barre) » vs « Squat pause ») fragmentent tout (`routes/gestion.py:86-129` propose une fusion manuelle) ; (3) export de ses données réservé au payant (`routes/gestion.py:432`).
**Manque** : un modèle séance → série avec type (échauffement/travail/back-off), cible (reps/RPE/%), et un historique par exercice.

### 2.5 Utilisateur FREE — **5/10**
**Jusqu'où va-t-il ?** Loin : séances illimitées, 5 programmes gratuits (`core/catalog.py:854-860`), cardio, calendrier, volume, courbe de poids, défis, badges, chrono, suggestion de surcharge, plaques, partage. C'est un gratuit plus généreux que Strong (3 routines).
**Les murs** : Coach (`routes/coach.py:222-223`), Générateur (`routes/generator.py:306-307`), Nutrition (`routes/nutrition.py:189`), body map/1RM/podium (`routes/progres.py:516`), 15 programmes PRO (`routes/onboarding.py:287`, `routes/programme.py:662-663`), export/import (`routes/gestion.py:432,465`, `routes/programme.py:540,567`), > 1 programme / > 1 profil (`routes/programme.py:348-353,396-398`), historique > 2 semaines (`routes/gestion.py:316-317`), et — incompréhensible — pré-remplissage des charges et animations forcés à off dès qu'il enregistre ses réglages (`routes/gestion.py:305-311`).
**Tombent-ils au bon moment ?** Les murs par intention (Coach, Nutrition) oui, avec tagline ciblée (`templates/vip_wall.html:6-14`). L'export verrouillé, non : c'est ses données, et les stores comme le RGPD attendent une portabilité gratuite.
**Friction native** : bannière AdMob en `TOP_CENTER` (`static/js/ads.js:69`) au-dessus de la topbar sur accueil/progrès/plus.

### 2.6 Utilisateur en ESSAI restreint (`vip_until`) — **4/10**
**Cohérent ou frustrant ?** Frustrant. Il a le badge « PRO » dans la topbar (`templates/base.html:118` teste `is_vip`), la page Plus affiche « Membre PRO — Merci de ton soutien » (`templates/plus.html:8-16` teste `is_premium` = `is_vip`), mais Coach et Générateur restent cadenassés (`plus.html:58-68` testent `is_vip_full`) et le mur lui propose de « Passer en PRO » alors qu'il est « PRO ». La durée (1 jour pour le filleul, 3 par filleul pour le parrain, `routes/parrainage.py:22-23`) suffit à peine à remplir un profil nutrition. Le funnel admin ne distingue pas essai et payant (`core/db.py:1093-1098` compte `tier`).
**3 frictions** : incohérence badge/accès ; 24 h dont une nuit ; aucune fin d'essai annoncée (pas de compte à rebours, pas de mail, pas de push « ton essai se termine »).

### 2.7 VIP payant (4,99 €/mois) — **5/10**
**En a-t-il pour son argent ?** Au mois 1, oui : coach en français avec son contexte, nutrition, programmes PRO, body map. Au mois 3, ce qui justifie le réabonnement devrait être l'usage quotidien du coach et de la nutrition. Or : le coach est bridé (500 tokens, pas de mémoire), le générateur est limité à 3/semaine et perd les reps, la nutrition n'a ni code-barres ni historique, et les stats « avancées » n'évoluent pas (pas d'e1RM, standards absolus). Rien de nouveau n'est réservé au PRO dans le changelog des 6 dernières versions (`static/changelog.json` : aliments, poids, surcharge, plats, réordonnancement sont pour tous). Le payant subit aussi R1/R2.
**3 frictions** : quota coach 15/j visible mais pas de streaming ; générateur inutilisable pour itérer (3/semaine, `routes/generator.py:34`) ; rien ne différencie son accueil de celui d'un gratuit à part la carte calories.

### 2.8 Utilisateur de l'app native Android — **4/10**
**Écarts avec le web** : (1) WebView distante sur l'URL Railway (`capacitor.config.json:5-6`) : chaque déploiement change l'app sans passer par le store, et le SW peut recharger la page en pleine séance (`static/js/sw-register.js:475-481`) ; (2) pubs bannière + interstitiel post-séance pour le gratuit (`static/js/ads.js`), IDs de **test** Google par défaut si l'env n'est pas posée (`app.py:373-374`) ; (3) aucun achat possible, prix affichés, CTA vers une page morte (`templates/premium.html:167-173`, `vip_wall.html:38-42`) ; (4) login natif via `@capgo/capacitor-social-login` (`templates/login.html:65-115`) — bien ; (5) notification de fin de repos planifiée par l'OS (`static/js/rest-timer.js:165-215`) — mieux que le web ; (6) reprise de séance au démarrage à froid (`templates/base.html:82-110`) — bien pensé ; (7) `user-select:none` global pour la WebView (`static/css/theme.css:33-35`).
**3 frictions** : parcours d'achat mort ; risque de rejet Play (webview pure + mention de prix hors Play Billing) ; « Connexion impossible » au démarrage sans réseau.

### 2.9 En salle sans réseau (sous-sol) — **2/10**
**Étape par étape** :
1. Il ouvre l'app (PWA installée, réseau coupé). Le SW sert `/accueil` depuis le cache : accueil **d'hier** (network-first → fallback, `service-worker.js:169-183`). Bandeau orange « Mode hors-ligne » (`offline.js:234-247`).
2. Tap « Commencer » sur la prochaine séance → `/seance?date=…` : en cache si visitée récemment, sinon fallback `/accueil` → il **revient à l'accueil**, sans message.
3. S'il atteint le choix de séance, tap « Choisir Push » → `/seance?mode=prefaite&name=Push&date=2026-09-21` : jamais visitée aujourd'hui → fallback `/accueil`. **Boucle** : il ne peut pas ouvrir sa séance du jour.
4. Cas favorable : il avait ouvert la séance avant de descendre. Il saisit ses séries (brouillon local OK), le chrono tourne (local OK). Il tape « Enregistrer » : `offline.js:374-391` intercepte, toast « Sauvegardé hors-ligne », badge « 1 action en attente ». Mais `prepareSave` a déjà effacé le brouillon (`seance_edit.html:1335`) et la page ne se recharge pas : la carte reste dépliée, non « complétée », la barre « EXERCICE 0/6 » ne bouge pas. S'il change d'onglet et revient, la page vient du cache **sans ses séries** : il croit avoir tout perdu et ressaisit → doublons en file (rejoués en parallèle, dernier gagnant).
5. « Terminer la séance » → mis en file, pas de redirection, pas de bilan. Il ferme l'app.
6. Retour du réseau : rejeu `Promise.all` (`offline.js:320-350`), toast « N donnée(s) synchronisée(s) ». Si sa session Flask a expiré entre-temps, les items restent en file (bonne détection `landedOnAuth`, `:333-337`) mais rien ne l'invite à se reconnecter.
**Ce qui manque** : pré-cache de la séance du jour (URL calculable depuis le planning), rendu optimiste après mise en file, file rejouée en ordre, écran séance qui fonctionne sans serveur.

### Meilleure / pire du marché
- **Meilleure** : pour aucun profil aujourd'hui. Le plus proche d'un avantage réel : le **débutant francophone qui veut être guidé** — onboarding en français, catalogue commenté, coach IA en français qui connaît son programme, suggestion de charge, chrono robuste. Rien d'équivalent en français dans Hevy/Strong. Cet avantage est annulé tant que R1 frappe ses trois programmes par défaut.
- **Pire** : l'**intermédiaire venant de Hevy/Strong** (perd import, vitesse de saisie, stats gratuites, supersets, rep targets) et l'**utilisateur sans réseau** (l'app est inutilisable pour démarrer une séance). Le **débutant poids-du-corps** est un cas à part : il perd la seule boucle de rétention qui existe (streak/séances) sans jamais savoir pourquoi.

---

## Partie 3 — Audit technique

Légende : **CRITIQUE** = perte de données ou indisponibilité ; **IMPORTANT** = dégradation forte ou risque business ; **MINEUR** = à corriger sans urgence.

### 3.1 Intégrité des données

| Sév. | Constat | Source | Ce que ressent l'utilisateur | Correctif |
|---|---|---|---|---|
| **CRITIQUE** | Écriture d'un exercice = `DELETE` de toutes ses lignes de la **semaine** (lun→dim) pour cette séance, puis `INSERT`. Toute séance nommée à l'identique faite 2× dans la semaine écrase la 1ʳᵉ. 9/20 programmes du catalogue (3/5 gratuits, dont les 3 débutants) planifient une même séance 2× (`planning_for` cyclique). Reproduit (R1). | `core/db.py:345-364` ; `routes/seance.py:972,998,1191` ; `core/catalog.py:24-35` ; `tests/test_routes.py:106-136` (valide l'écrasement) | Vendredi, il ouvre sa séance et voit celle de lundi « déjà faite » ; s'il enregistre, lundi disparaît et devient « MANQUÉE » sur l'accueil et le calendrier. | Cibler par **date** (`.eq("date", date_str)`) au lieu de la plage de semaine, et adapter `_exo_curr_rows`/`_exo_completed` (`routes/seance.py:125-136`) pour comparer sur `Date`. Puis migration : ajouter `history.session_id` (uuid par (user, date, séance)) et écrire/lire par ce champ. Test : sauver la même séance lundi et vendredi, attendre 2 dates. |
| **CRITIQUE** | `/programme/state` (autosave de l'éditeur, appelé à chaque modification) reconstruit le blob avec une liste blanche de 7 clés : `_custom_exercises`, `_session_notes`, `_badges`, `_streak_record`, `_upsell_seen`, `_challenges_won/_done`, `_meal_plan`, `_equipment_details`, `_equipement`, `_seance_order`, `_jours` sont supprimés. Même défaut (listes différentes) dans l'import, le changement de programme et l'adoption IA. Reproduit (R2). | `routes/programme.py:306-311` ; `:621-624` ; `:690-700` ; `routes/generator.py:420-423` ; `templates/programme.html:657-682` | Après avoir renommé un exercice dans Programme : ses bilans de séance ont disparu, ses exos perso aussi, son record de streak est à 0, la modale d'upsell revient, le défi de la semaine se revalide (+1 au compteur), le filtre matériel ne s'applique plus. Sans aucun message. | Inverser la logique : partir de `old`, ne remplacer **que** les clés métier (séances, `_planning`, `_name`, `_programmes`, `_seance_prog`, `_cardio`) et conserver **toutes** les clés `_x` restantes. Centraliser dans `core/db.py` (`replace_program_body(old, new_body)`) et l'utiliser aux 5 endroits. Test : chaque clé `_x` connue survit à `/programme/state`, `/programme/import`, `/programme/change-program`, `/generator/apply`. |
| **CRITIQUE** | Cardio : `replace_exo_rows(date, "Cardio Course", "CARDIO:Course", …)` → une seule séance par activité et par semaine survit (idem cardio inline en séance). | `routes/cardio.py:189-201` ; `routes/seance.py:1178-1191` | Deux courses dans la semaine : la première disparaît de l'accueil, du calendrier et des stats cardio. | Même correctif que ci-dessus (ciblage par date, puis `session_id`). Pour deux cardios identiques le même jour : `Série` incrémentale au lieu de remplacement. |
| **CRITIQUE (conditionnel)** | `get_hist` charge tout `history` sans pagination ; PostgREST plafonne à `max-rows` (1 000 par défaut sur Supabase). `rename`/`merge`/`reset-soft` lisent l'historique puis `save_hist` = `DELETE` complet + `INSERT` du résultat. Si le plafond est actif, l'historique est **tronqué définitivement** à 1 000 séries. Non vérifiable (réglage projet). | `core/db.py:117-123` ; `:149-186` ; `routes/gestion.py:256,287,390` | Un utilisateur d'un an fusionne deux doublons dans Gestion : ses 8 premiers mois disparaissent. | `range()` paginé dans `get_hist` (boucle par 1 000) ; remplacer `save_hist` global par des `UPDATE … SET exercice=…` ciblés pour rename/merge ; garder `save_hist` uniquement pour l'import, avec un garde `len(rows) >= len(existing)`. Vérifier `max-rows` dans Supabase → API settings. |
| **IMPORTANT** | `save_hist` non transactionnel : `DELETE` puis `INSERT` par lots ; le rollback ré-insère avec les anciens `id` et peut échouer. | `core/db.py:166-184` | Import ou fusion interrompu = historique vide jusqu'au rollback ; s'il échoue, vide pour de bon. | Fonction SQL `rpc('replace_history', …)` transactionnelle, ou insérer d'abord avec un `batch_id` puis supprimer l'ancien. |
| **IMPORTANT** | Tout ce qui compte une séance « faite » sur l'accueil exige `Poids > 0` : streak, séances/semaine, `today_done`, prochaine séance, upsell. Les exos poids-du-corps (Pompes, Tractions, gainage) ont `Poids = 0`. Reproduit (R3). | `routes/accueil.py:285-288,292-295,315-320,349-354,464-466` ; `routes/seance.py:956` (`poids = 0.0 if is_bw`) | Programme « Full Body Poids du Corps » : streak à 0 pour toujours, « Commencer » et « En danger » affichés après la séance, badge « Première séance » via muscu jamais débloqué. | Utiliser partout le prédicat `_is_real_perf` (`routes/accueil.py:41-49`, déjà correct) au lieu de `Poids > 0`. Test R3. |
| **IMPORTANT** | Écritures dans des GET : `/programme` sauve à chaque affichage ; `/accueil` jusqu'à 4 `save_prog` ; `_display_week` écrit `_started_at` pendant le rendu de `/seance`. Avec le prefetch au `touchstart` (`prefetch.js`), ces écritures partent en arrière-plan. | `routes/programme.py:190` ; `routes/accueil.py:139-145,305-309,472-479,515-525` ; `routes/seance.py:83-87` | Conflits de version inutiles (fusions loguées), latence des pages, risque d'écraser une écriture concurrente de séance. | Déplacer badges/streak/défi dans `/seance/finish` (déjà le moment où l'état change) ; `/programme` en lecture pure (la migration `_ensure_*` ne sauve que si elle a réellement changé quelque chose). |
| **IMPORTANT** | Import JSON complet : `save_prog(prog_in)` sans validation du contenu (n'importe quel dict). Une séance dont la valeur n'est pas une liste fait planter `/gestion` (`len(prog[k])`) et `/seance`. | `routes/gestion.py:490-491` ; `:144` | Un VIP importe une sauvegarde éditée à la main : toutes les pages renvoient 500 jusqu'à intervention manuelle. | Valider avec le même nettoyeur que `/programme/state` ; refuser les clés inconnues ou les typer. |
| **MINEUR** | `_session_notes` purgées à 84 jours (`routes/seance.py:1215`) : les bilans (note /5 + commentaire) sont une donnée utilisateur, pas un cache. | `routes/seance.py:1215-1236` | « Où est passé mon commentaire de mars ? » | Table `session_notes` (user_id, date, seance, rating, comment) ou conservation illimitée. |
| **MINEUR** | Coach : quota lu puis incrémenté sans verrou (`select` → `upsert`). | `routes/coach.py:167-187` | Deux envois rapides passent le quota à 16/15. | `rpc` d'incrément atomique ou contrainte côté SQL. |

### 3.2 Sécurité

| Sév. | Constat | Source | Impact | Correctif |
|---|---|---|---|---|
| **IMPORTANT** | Pas de `werkzeug.middleware.proxy_fix.ProxyFix`. Derrière le proxy Railway, `request.remote_addr` = IP du proxy → le rate-limit `60/min` est **partagé par tous les utilisateurs** (par worker, mémoire) ; `request.url_root` est en `http://` pour `success_url`/`cancel_url`/`return_url` Stripe. Non vérifiable sans les logs (chercher des 429 « Tu cliques un peu trop vite » subis par plusieurs comptes). | `app.py` (absence) ; `core/limiter.py:271-277` ; `routes/billing.py:55-56,205-206,371` | 20 utilisateurs actifs = 429 aléatoires pour tout le monde ; anti-abus réel inexistant (l'attaquant partage le bucket… avec ses victimes). | `app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)` ; `REDIS_URL` pour un stockage partagé ; `PREFERRED_URL_SCHEME="https"`. |
| **IMPORTANT** | Messages d'erreur du coach/générateur adressés à l'opérateur mais affichés à l'utilisateur (« Vérifie ANTHROPIC_API_KEY dans Railway », « Ajoute du crédit sur console.anthropic.com », `Erreur Anthropic (TypeName) : <300 chars du message SDK>`). | `routes/coach.py:403-412` ; `routes/generator.py:371-378` | Fuite du fournisseur, de l'hébergeur et de détails internes ; image amateur au moment où le client paye. | Message générique + `logger.error` détaillé + Sentry. |
| **IMPORTANT** | `FLASK_SECRET_KEY` absente → clé `"dev-insecure-change-me"` avec un log critique, mais l'app démarre. | `app.py:76-85` | Un déploiement mal configuré rend tous les cookies de session forgeables (usurpation de n'importe quel `user_id`). | `raise RuntimeError` en prod (`RAILWAY_ENVIRONMENT` présent) si la clé manque. |
| **MINEUR** | `/push/unsubscribe` supprime par `endpoint` sans filtrer `user_id`. | `routes/push.py:60-68` ; `core/db.py:753-757` | Un utilisateur connaissant l'endpoint d'un autre (URL opaque, peu probable) le désabonne. | `.eq("user_id", g.user_id)` dans le delete. |
| **MINEUR** | CSRF : une session authentifiée sans `_csrf` voit sa **première** requête mutante acceptée. | `app.py:264-268` | Fenêtre théorique post-login (le token est créé au premier rendu de page ; `/auth/session` ne le crée pas). | Créer `_csrf` dans `set_session` (`routes/auth.py:124-127`) et supprimer l'exception. |
| **MINEUR** | Secret cron accepté en `?token=` → présent dans les logs d'accès Railway. | `routes/push.py:35-36` | Rotation nécessaire si les logs fuient. | N'accepter que l'en-tête. |
| **MINEUR** | Webhook : `charge.refunded` / `charge.dispute.created` non traités → un lifetime remboursé reste VIP. `invoice.payment_failed` non traité (attend `unpaid`). | `routes/billing.py:316-327` | Perte de revenu marginale ; pas d'alerte de carte expirée à l'utilisateur. | Ajouter les deux événements ; pousser une notif « paiement échoué ». |
| **MINEUR** | IDs AdMob de **test** par défaut si l'env est vide. | `app.py:373-374` | En prod sans env : pubs de test = 0 € et violation des CGU AdMob. | Ne charger `ads.js` que si l'env est définie. |
| **OK** | Gating VIP : tous les gates sont côté serveur (`is_vip_full` pour coach/générateur/export/programmes PRO/multi-profils ; `is_vip` pour nutrition/stats) ; le client ne peut pas les contourner ; le webhook exige la signature ; `success` vérifie `client_reference_id == g.user_id`. | `routes/coach.py:222,296` ; `routes/generator.py:306,321,401` ; `routes/gestion.py:432,465` ; `routes/programme.py:348,396,540,567,662` ; `routes/onboarding.py:287` ; `routes/nutrition.py:189,291` ; `routes/progres.py:516` ; `routes/billing.py:257,295-309` | — | — |

### 3.3 Performance

| Sév. | Constat | Source | Impact | Correctif |
|---|---|---|---|---|
| **CRITIQUE** | Worker gunicorn sync (défaut : 1 worker, timeout 30 s — sauf `WEB_CONCURRENCY` sur Railway, non vérifiable) + appels Anthropic **dans la requête** (coach 500 tokens ≈ 3-8 s, générateur 2 600 tokens ≈ 10-25 s). | `railway.json:7` ; `routes/coach.py:379-385` ; `routes/generator.py:359-364` | Pendant qu'un VIP génère un programme, **tous** les autres utilisateurs voient l'app figée ; au-delà de 30 s, 502 pour lui et les autres. | `gunicorn -k gthread --threads 8 -w 2 --timeout 90` au minimum ; streaming SSE pour le coach ; job asynchrone (thread + polling ou Supabase Edge Function) pour le générateur. |
| **IMPORTANT** | `/accueil` : `get_hist` (tout l'historique, cache 60 s par worker) + `get_prog` + `get_profile` (non caché) + `get_onboarding` (non caché malgré `session["onboarded"]`) + `sum_nutrition_day` + jusqu'à 4 `save_prog` + `track()` synchrones + `before_request` (`get_profile` toutes les 15 s pour un gratuit, `auth.admin.get_user_by_id` toutes les 120 s). ≈ 6-10 aller-retours Supabase par affichage. | `routes/accueil.py:228-231,431` ; `core/db.py:429-464` ; `app.py:157-188` ; `core/analytics.py:308` | 400-900 ms de TTFB perçus sur mobile avant même le rendu ; chaque « Enregistrer » en séance rejoue `get_hist` + normalisation + 2×N filtrages O(n). | Cacher `profile`/`onboarding` comme `hist`/`prog` (le doc dit que c'est fait, ce n'est pas le cas) ; `track()` dans un `ThreadPoolExecutor` ; ne charger que les 16 dernières semaines d'historique pour la séance. |
| **IMPORTANT** | Chaque action de séance = POST + 302 + rendu complet de `seance_edit.html` (1 445 lignes, `body_polygons` 10 Ko, `exo|tojson` par carte) + re-init Alpine + `fetch('/seance/api/variant-history')` par carte dont la variante diffère. | `routes/seance.py:801-805,712-741` ; `templates/seance_edit.html:183-190,1258-1289` | 1 à 2 s entre « Enregistrer » et la carte suivante, à chaque exercice, en salle. | `/seance/save-exo` en JSON (204) + mise à jour DOM côté Alpine (la logique `completed` est triviale) ; garder le POST classique en fallback no-JS. |
| **IMPORTANT** | Relance push : `select user_id, date, reps, poids` sur **toute** la table `history` (tous les utilisateurs), puis `select *` sur toute `push_subscriptions`. Admin stats : idem. Plafond `max-rows` probable → ciblage silencieusement faux au-delà de 1 000 lignes. | `core/db.py:816-856,972-1010` | Cron qui rate des cibles, page admin fausse, coût Supabase croissant avec l'usage. | Vue SQL `last_activity(user_id, last_date)` matérialisée ou `rpc` agrégé ; `get_admin_stats` via `rpc`. |
| **MINEUR** | Vidéo 3,5 Mo en autoplay sur chaque mur VIP ; 36 Ko FOODS inline ; `static/promo/` 4 Mo servis par Flask. | `templates/vip_wall.html:24-28` ; `routes/nutrition.py:21,282` | Paywall lent sur 4G, données mobiles consommées à chaque mur. | Poster seul + lecture au tap ; FOODS en `/static/foods.json` cacheable ; promo hors du dépôt applicatif. |
| **MINEUR** | Pas de `ETag`/`Cache-Control` long sur `/static` versionné ; le SW re-télécharge tout en network-first. | `static/service-worker.js:188-198` | Rechargements complets à chaque navigation. | Stale-while-revalidate pour `/static/*` (déjà annoncé dans le commentaire `service-worker.js:154` mais non implémenté). |

### 3.4 Qualité

| Sév. | Constat | Source | Impact | Correctif |
|---|---|---|---|---|
| **IMPORTANT** | Cinq listes blanches divergentes pour reconstruire `programs.data` ; 25+ clés `_x` sans registre. | `routes/programme.py:306-311,621-624,690-700` ; `routes/generator.py:420-423` ; `routes/onboarding.py:290-305` | Chaque nouvelle feature stockée dans le blob sera perdue par l'un des cinq chemins (c'est déjà arrivé 11 fois). | Registre `PROG_META_KEYS` dans `core/db.py` + helper unique. |
| **IMPORTANT** | `templates/seance_edit.html` : 1 445 lignes, ~750 de JS inline (exoBlock, cardioBlock, modales, drafts, iso-chrono). | `templates/seance_edit.html:700-1441` | Non testable, non minifié, non cacheable par le SW, `unsafe-inline` obligatoire dans la CSP. | Extraire `static/js/seance.js` ; passer les données via `<script type="application/json">` (déjà fait pour `share-data`). |
| **MINEUR** | Dépendances mortes : `python-dateutil` (aucun import), `Pillow` (uniquement `compress_icon.py`/`generate_icons.py`, scripts de dev). `core/data.is_premium` jamais appelée. `{% include "_icons.html" ignore missing %}` vise un fichier inexistant. | `requirements.txt:5-6` ; `core/data.py:166-173` ; `templates/base.html:114` | Image de build plus lourde ; code mort qui trompe la lecture. | Supprimer. |
| **MINEUR** | `MUSCLE_LIST` copié dans 4 modules ; `_normalize_hist` copié dans 3 routes ; `_is_real_perf` dans 2 ; `_parse_date` dans 3. | `routes/seance.py:25,35,47,97` ; `routes/accueil.py:27,41` ; `routes/programme.py:26` ; `routes/gestion.py:26` ; `routes/generator.py:37` ; `routes/progres.py:94` ; `routes/cardio.py:59` | Dérives déjà visibles (`accueil._is_real_perf` vs `seance._is_real_perf` identiques ; `challenges._is_real_muscu` différent). | `core/hist.py` unique. |
| **MINEUR** | `int(f["semaine"])` accepté du client et stocké (`history.semaine`) alors que la lecture le recalcule depuis la date. | `routes/seance.py:934,960` ; `core/db.py:131-133` | Colonne morte incohérente. | Calculer côté serveur, ou supprimer la colonne. |
| **MINEUR** | `arcade.html` (541 lignes de mini-jeux canvas) sans lien avec l'entraînement, jamais mentionné dans le changelog, non instrumenté. | `templates/arcade.html` ; `routes/arcade.py` | Surface de maintenance et de bug pour zéro rétention mesurée. | Voir Partie 4-C. |

---

## Partie 4 — Améliorations et idées

### A. Les 10 améliorations à impact maximal (triées impact/effort)

| # | Problème | Correctif | Fichiers | Effort | Impact attendu / profil |
|---|---|---|---|---|---|
| 1 | Même séance 2×/semaine = écrasement (R1) | Cibler `history` par `date` exacte au lieu de la semaine ; `_exo_curr_rows`/`_exo_completed`/`_reconstruct_history_exos` sur `Date` | `core/db.py:345-393`, `routes/seance.py:125-136,308,441-442,696-699`, test dédié | **S** | Arrête la perte de données pour 45 % des programmes ; débutants J1-S3, intermédiaires PPL, cardio. Prérequis à tout le reste. |
| 2 | Autosave programme efface les métadonnées (R2) | Helper unique qui part de `old` et ne remplace que les clés métier ; test de survie de chaque clé `_x` | `routes/programme.py:306-311,621-624,690-700`, `routes/generator.py:420-423`, `core/db.py` (helper) | **S** | Fin des bilans/exos perso/badges/streak perdus ; tous les profils. |
| 3 | Streak/séances à 0 pour le poids du corps (R3) | Remplacer `Poids > 0` par `_is_real_perf` | `routes/accueil.py:285-295,315-320,349-354,464-466` | **S** | Rétention du segment « Poids du corps » (1 programme gratuit sur 5). |
| 4 | LLM bloquant le worker | `gunicorn -k gthread --threads 8 --timeout 90` ; streaming SSE coach | `railway.json:7`, `routes/coach.py:293-445`, `templates/coach.html` | **S** (config) / **M** (streaming) | Plus de gel global ; coach perçu 3× plus rapide ; VIP. |
| 5 | Relance push quotidienne 27 jours | Mémoriser `last_reactivation_at` (table `push_subscriptions` ou `profiles`) ; règle J+3, J+7, J+14, stop | `core/push.py:430-481`, `core/db.py:816-856`, migration v34 | **S** | Moins de désinstallations ; gratuits en décrochage. |
| 6 | Saisie = rechargement par exercice | `save-exo`/`skip-exo` en `fetch` JSON, mise à jour de la carte (`completed`, barre, volume) sans reload ; fallback formulaire conservé | `routes/seance.py:930-1000`, `templates/seance_edit.html:357-383,1159-1337` | **M** | Saisie 3-5× plus rapide en salle ; tous les profils, surtout intermédiaires. |
| 7 | Hors-ligne inutilisable pour ouvrir une séance | Pré-cacher `/seance?mode=prefaite&name=<planning[j]>&date=<j>` pour aujourd'hui/demain au chargement de l'accueil ; rendu optimiste après mise en file ; rejeu séquentiel | `static/service-worker.js:9-37,166-184`, `static/js/offline.js:314-357,374-391`, `templates/accueil.html` | **M** | Passe le profil sous-sol de 2 à 6 ; salles en sous-sol = cas fréquent. |
| 8 | Générateur jette les reps ; programme sans cible | Stocker `reps` (chaîne « 8-12 ») et `rest_seconds` par exercice dans le programme ; afficher en placeholder de la table (la suggestion le fait déjà) | `routes/generator.py:412-414`, `routes/programme.py:281-289`, `core/catalog.py:1092-1102`, `templates/seance_edit.html:326` | **S** | Le programme (IA ou catalogue) redevient une prescription ; VIP et débutants. |
| 9 | Pagination + `save_hist` destructif | `get_hist` paginé ; rename/merge par `UPDATE` ciblé ; garde-fou sur `save_hist` | `core/db.py:108-186`, `routes/gestion.py:229-289` | **S** | Supprime un risque de perte totale pour les utilisateurs de longue date. |
| 10 | Parcours d'achat mort + prix affichés en natif | Masquer tout prix/CTA payant en natif (ou activer Google Play Billing via `@capacitor-community/in-app-purchases`) ; ajouter « Déjà abonné ? Connecte-toi avec le même compte Google » | `templates/premium.html:74-75,167-173`, `templates/vip_wall.html:38-42`, `templates/accueil.html:253-283`, `templates/plus.html:18-25` | **S** (masquage) / **L** (IAP) | Évite un rejet Play ; ouvre la monétisation native. |

### B. 15 idées de fonctionnalités (★ = n'existe chez aucun concurrent grand public)

| # | Idée | Pour qui | Pourquoi ça retient / convertit | Complexité | Risque |
|---|---|---|---|---|---|
| 1 | **Mode « séance guidée »** : un écran par exercice, une série à la fois, gros boutons ✓, le chrono s'enchaîne, swipe pour passer | Débutant, une main | Supprime le tableau 6 colonnes ; c'est ce que Hevy fait bien | M | Deux UI de saisie à maintenir |
| 2 | **Import CSV Hevy / Strong** (formats publics, mapping exercices avec fusion assistée existante) | Intermédiaire migrant | Seul moyen de convertir un utilisateur Hevy ; l'outil de fusion de doublons (`routes/gestion.py:86-129`) sert déjà | M | Qualité du mapping des noms EN→FR |
| 3 | **PR en direct** : à la saisie d'une série, badge « 🏆 Record » + haptic (le `record` est déjà dans le contexte de la carte) | Tous | Dopamine au bon moment, c'est le cœur de Hevy | S | Aucun |
| 4 | ★ **Coach qui agit** : le coach IA peut proposer un patch de programme (JSON) affiché en diff « Appliquer / Refuser », via le même `parse_and_validate` | VIP | Transforme le chat en outil ; justifie le mois 3 | M | Coût tokens ; validation stricte déjà en place |
| 5 | ★ **Debrief IA post-séance** : à « Terminer », 3 lignes générées (progression vs dernière fois, RPE moyen, conseil pour la prochaine) — 150 tokens, 1 appel | VIP (teaser gratuit 1×/semaine) | Valeur visible à chaque séance ; upsell naturel | S | Coût ≈ 0,001 € / séance |
| 6 | ★ **Plan de charge « hors ligne »** : l'app pré-calcule et met en cache la séance du jour complète (charges suggérées incluses) chaque soir | Sous-sol | Rend l'offline réellement fiable | M | Cohérence si le programme change entre-temps |
| 7 | **Rappel push à l'heure de la séance** (planifié côté serveur depuis `_planning` + heure préférée) | Débutant S3 | Le rappel qui fait revenir, plutôt que la relance après décrochage | M | Fuseau/heure préférée à collecter |
| 8 | **Body map relative** : % basé sur des standards par sexe et poids de corps (tables Symmetric Strength) au lieu de 140 kg fixes | Femmes, légers, tous | Rend la stat lisible et motivante ; supprime un « rouge à vie » | S | Sourcer les tables |
| 9 | ★ **Fusion automatique d'exercices « à la saisie »** : quand un nouveau nom ressemble à > 0,82 à un existant, proposer inline « tu voulais dire X ? » (réutilise `_same_exercise`) | Avancé, tous | Historique propre sans passer par Gestion | S | Faux positifs (déjà bornés) |
| 10 | **Fiche exercice = historique complet** : toutes les séries de cet exercice, e1RM et volume par semaine, meilleur set, gratuit | Intermédiaire, avancé | Parité minimale avec Hevy/Strong gratuit | M | Décision de gating |
| 11 | ★ **Défi entre parrain et filleuls** : classement hebdo privé (volume ou séances) entre les comptes reliés par `referred_by` | Gratuits | Boucle sociale minimale sans réseau social ; réutilise le parrainage | M | Vie privée : opt-in |
| 12 | **Semaines de deload et blocs** : un programme peut définir des blocs de N semaines avec cible reps/RPE par bloc ; la suggestion de surcharge en tient compte | Avancé | Seule façon de garder un avancé > 3 mois | L | Modèle de programme à étendre (prérequis A-8) |
| 13 | **Scan code-barres** (Open Food Facts, client-side via `BarcodeDetector`/ZXing) | VIP nutrition | Sans ça, Nutrition ne remplace pas Yazio | M | Qualité OFF variable |
| 14 | ★ **Export « carte de séance » partageable** par séance (pas seulement l'accueil) : exos, PR du jour, durée, note /5 | Tous | Partage au moment de la fierté ; acquisition | S | Aucun |
| 15 | **Durée de séance** (début = première série, fin = Terminer) + « densité » (kg/min) dans les stats | Tous | Métrique attendue partout ; alimente le debrief IA | S | Aucun |

### C. Les 3 choses à supprimer

1. **Arcade** (`templates/arcade.html` 541 lignes, `routes/arcade.py`, entrée `templates/plus.html:79-83`) — hors mission, jamais annoncée dans le changelog, non instrumentée, zéro lien avec la rétention. Chaque octet de canvas est un octet non consacré à la saisie.
2. **Les « profils d'entraînement »** (`routes/programme.py:83-119,377-460`, UI dans `programme.html`) — une couche d'indirection (profil → programmes → séances) que les concurrents n'ont pas, gatée VIP à 1 profil, qui complique `/seance` (`routes/seance.py:534-570`) et double le nombre de cas dans `save_state`. Un dossier de routines (Hevy) suffit.
3. **Les écritures dans les GET et les recalculs de badges/streak à chaque accueil** (`routes/accueil.py:139-145,305-309,472-479,515-525`, `routes/programme.py:190`, `routes/seance.py:83-87`) — les remplacer par un calcul à la fin de séance. C'est de la dette qui génère des conflits de version, ralentit l'accueil et rend le prefetch dangereux.

### D. Une seule action pour les 30 prochains jours

**Réparer la clé d'écriture de `history` (A-1) et le helper de reconstruction du programme (A-2), avec les tests R1/R2/R3 ajoutés à la suite.** Deux changements de taille S, aucune migration obligatoire pour la première étape (ciblage par `date`), qui suppriment les trois pertes de données silencieuses. Tant que ces bugs existent, chaque effort d'acquisition (parrainage, store, pubs) amène des utilisateurs vers une app qui perd leurs séances de lundi et leurs notes — et un utilisateur qui a perdu une séance ne revient pas, quel que soit le coach IA. Tout le reste de ce rapport (saisie sans reload, offline, streaming, pricing natif) vient après.

---

## 5. Écarts entre la doc (CONTEXT.md) et le code

| CONTEXT.md dit | Le code fait | Source |
|---|---|---|
| « Cache … Clés : `hist:{user_id}`, `prog:{user_id}`, `profile:{user_id}` » | Aucun cache profil : `get_profile` requête Supabase à chaque appel ; `clear_user_cache` ne connaît que `hist`/`prog`. | `core/db.py:97-102,429-438` |
| « 2 workers gunicorn × cache 60 s » (verrou optimiste) | `startCommand` sans `-w` : gunicorn démarre 1 worker sync par défaut (sauf `WEB_CONCURRENCY` côté Railway — non vérifiable). | `railway.json:7` |
| « Catalogue de programmes (19) » | 20 programmes dans `CATALOG`. | `core/catalog.py` (comptés) |
| « Background : `#111318` (défini via `theme-color`) » | `theme-color` et `background_color` = `#0a0a0f`. | `templates/base.html:6` ; `static/manifest.json:11-12` ; `capacitor.config.json:13` |
| « Cardio — Activités : Course, Vélo, Rameur, Natation, Corde, HIIT, Marche » | + Elliptique, Montée d'escaliers, Autre. | `routes/cardio.py:23-34` |
| « Settings utilisateur » : 6 clés listées | 9 clés (`auto_prefill_weight`, `show_rpe`, `show_overload_hint` en plus). | `routes/gestion.py:31-41` |
| « Onglet Plus → Premium · Coach IA · Programme · Nutrition · Cardio · Arcade · Gestion · Tutoriel » | Plus contient aussi Parrainage, Générateur IA, Calcul de plaques, FAQ ; le Tutoriel n'y est pas (il est dans Gestion). | `templates/plus.html:28-98` |
| « Auth : … vérifie le JWT avec SUPABASE_JWT_SECRET (HS256) » (docstring `routes/auth.py:10-11`) | HS256 **ou** ES256/RS256 via JWKS. | `routes/auth.py:82-103` |
| « `/auth/debug` … Réservé aux admins » | Réservé aux admins **et** désactivé sauf `DEBUG_ENDPOINT=1`. | `routes/auth.py:141-147` |
| « Free = … 1 programme » ; commentaire code « Limite 2 programmes pour les non-VIP » | Logique et message = 1 programme. Le commentaire est faux. | `routes/programme.py:345-353` |
| « Mode Offline : … Synchronisation automatique au retour de la connexion » | Vrai, mais aucune mention que les URLs de séance non visitées retombent sur `/accueil`, ni que la saisie hors-ligne ne marque pas l'exercice comme fait. | `static/service-worker.js:178-183` ; `static/js/offline.js:374-391` |
| « Rate limiting : 60 req/min par IP » | Par `remote_addr` sans ProxyFix → IP du proxy si Railway ne préserve pas l'IP source. | `core/limiter.py:271-277` |
| « Relance … Planifier 1×/jour » | Aucun garde-fou contre l'envoi quotidien répété au même utilisateur. | `core/push.py:430-481` |
| « SW : Network First » et commentaire « Stale-While-Revalidate pour navigations HTML » | Network-first partout ; pas de SWR. | `static/service-worker.js:154-198` |
| « Générateur … reps NON persistées, cf. semaine continue » | Vrai — mais la raison invoquée (semaine continue) n'a aucun rapport ; c'est une décision produit qui vide le générateur de sa valeur. | `routes/generator.py:412-414` |
| « Streak … État en danger si séance du jour non faite » | Uniquement du lundi au vendredi (`today.weekday() < 5`). | `routes/accueil.py:337` |
| `pwa/README.md`, `rebuild_program_from_history.py`, `generate_icons.py` sont listés dans la structure | Ils sont dans `.gitignore` (« non commités pour partie ») : la doc décrit des fichiers absents du dépôt. | `.gitignore:11-15` |

---

## 6. Non vérifiable depuis le dépôt

- **Réglage `max-rows` PostgREST** du projet Supabase (défaut 1 000). Détermine si le constat « CRITIQUE (conditionnel) » § 3.1 est actif. À lire dans Supabase → Settings → API.
- **Index réels** sur `history(user_id, date, seance, exercice)` et `events(user_id, event, created_at)` : seul `supabase_schema_v32_prog_version_hist_index.sql` ajoute `history(user_id, id)`. Les filtres par `date`/`seance`/`exercice` (`core/db.py:352-359`) et le comptage du quota générateur (`routes/generator.py:289-294`) n'ont pas d'index visible dans les migrations.
- **État d'application des migrations** v33 (`body_weight`) et présence des colonnes `version`, `stripe_customer_id`, `vip_until`, `newsletter_*`, `conversation_id` (le code prévoit des replis si elles manquent : `core/db.py:227-239,886-895`).
- **Variables Railway** : `WEB_CONCURRENCY` (nombre de workers), `REDIS_URL` (rate-limit partagé), `SENTRY_DSN`, `CSP_ENFORCE`, `ADMOB_*` (sinon IDs de test), `TWA_SHA256_FINGERPRINT`, `VAPID_*`, `CRON_SECRET`, `GOOGLE_WEB_CLIENT_ID`. `/auth/debug` (si `DEBUG_ENDPOINT=1`) en expose la présence.
- **Comportement du proxy Railway** vis-à-vis de `remote_addr` (impacte le rate-limit) et de `X-Forwarded-Proto` (impacte les URLs Stripe).
- **Service Worker dans la WebView Capacitor** au démarrage à froid sans réseau (fallback `www/index.html` ou cache SW).
- **Fiabilité réelle des notifications** de fin de repos sur device (Doze, OEM chinois), du `LocalNotifications.schedule` et du `setTimeout` dans le SW.
- **Statut Play Console / AdMob** (documentés « en cours » dans `docs/PLAY_STORE.md` et la mémoire projet) et la réaction du review Google à une WebView distante + mention de prix.
- **Volumes réels** : nombre d'utilisateurs, taille moyenne de `history`, taux de 429, latences — aucune métrique dans le dépôt en dehors du funnel `events`.
- **Coût API Anthropic** effectif par VIP (quotas codés : 15 msg × 500 tokens/j + 3 × 2 600 tokens/semaine).
