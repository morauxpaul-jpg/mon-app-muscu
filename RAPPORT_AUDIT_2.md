# SECOND AUDIT — Muscu Tracker PRO

**Date** : 2026-09-24 · **Commit audité** : `5d27772` (branche `main`) · **Audit précédent** : `5940de5`, 2026-09-21, note globale **4,5/10**.
**Périmètre** : `pwa/` (19 blueprints, 20 modules `core/`, 31 gabarits, 19 scripts JS, 337 tests), `android/`, `capacitor.config.json`, `CONTEXT.md`.
**Conflit d'intérêt déclaré** : le code audité a été modifié par l'auteur de ce rapport entre les deux dates. Les constats ci-dessous sont donc volontairement plus sévères sur les parties récentes, et quatre défauts introduits ou laissés par ces modifications sont nommés (§ 3, repères **N1** à **N4**).

---

## Note globale : **6,4 / 10** (précédemment 4,5)

> Les trois pertes de données silencieuses sont réparées et vérifiées. La saisie ne recharge plus la page, le hors-ligne fonctionne vraiment, le coach répond en flux, l'accessibilité passe de l'inexistant au conforme. Ce qui n'a pas bougé : l'architecture. Le blob JSON fourre-tout a **encore grossi** (27 clés `_x` lues ou écrites), `routes/seance.py` fait 1 553 lignes, `/programme` pèse 304 ko de HTML avec 1 283 attributs `style=`, et l'accueil lit encore **tout** l'historique à chaque affichage. L'app est devenue fiable ; elle n'est pas devenue saine.

| Bloc | Avant | Après |
|---|---:|---:|
| Produit (onboarding, saisie, programme, progression, coach, générateur, nutrition, cardio) | 4,6 | **6,3** |
| Plateforme (offline, notifications, design, perf) | 4,3 | **6,5** |
| Technique (archi, données, sécurité, robustesse, tests) | 4,6 | **6,2** |
| Business (monétisation, rétention, accessibilité) | 4,3 | **6,7** |

---

## 0. Méthode

- Chaque constat cite `fichier:ligne`, chemins relatifs à `pwa/` sauf mention. Une affirmation sans source n'a pas sa place ici.
- Barème inchangé : 10 = état de l'art ; 8-9 = niveau Hevy/Strong, **justifié par des faits** ; 6-7 = correct mais un concurrent fait mieux ; 4-5 = utilisable mais faible ; 1-3 = cassé, absent ou contre-productif.
- **Quatre reproductions** exécutées contre `FakeSupabase` (scripts hors dépôt) :
  - **R1** — deux cardios « Course » le même jour : `lignes gardees : 1 | durees : ['45']`. La première séance est perdue.
  - **R2** — premier `GET /accueil` avec 12 semaines d'historique : **2 écritures** `save_prog` (badges, record de streak), puis 0 aux affichages suivants.
  - **R3** — `GET /accueil` : **7 requêtes Supabase**. `GET /progres` : 2.
  - **R4** — avec 500 séries en base, `/accueil` en lit **500** pour afficher un tableau de bord qui n'en montre que la semaine.
- Suites exécutées : `306 passed in 3.52s` (Python) et `31 tests JS passés` (Node).
- Les correctifs revendiqués ont été vérifiés dans le code, pas dans le changelog.

---

## Partie 1 — Notes par axe

| # | Axe | Avant | Après | En une phrase |
|---|---|---:|---:|---|
| 1 | Onboarding | 6 | **6** | Choix désormais accessibles au clavier, mais toujours Google-only et toujours **aucune question sur le poids** — dont dépendent maintenant les standards de force. |
| 2 | Saisie de séance | 4 | **7** | Plus de rechargement, record annoncé au moment où il tombe, deux séances du même nom coexistent ; reste un tableau de 6 colonnes sur 375 px. |
| 3 | Programme et planning | 4 | **6** | L'autosave ne détruit plus rien et les reps sont enfin stockées ; la page fait 304 ko et le planning reste hebdomadaire. |
| 4 | Progression et statistiques | 5 | **7** | Fiche par exercice, standards relatifs au gabarit, Plotly retiré ; mais le gabarit n'est demandé nulle part. |
| 5 | Coach IA | 5 | **7** | Flux SSE, 1 400 tokens, mémoire entre conversations ; le message d'erreur de configuration nomme encore la variable d'environnement. |
| 6 | Générateur de programme IA | 4 | **6** | Reps et repos conservés, métadonnées préservées ; toujours 10-25 s d'attente sans le moindre retour visuel. |
| 7 | Nutrition | 5 | **6** | Scan de code-barres branché sur Open Food Facts ; la base locale reste 1 000× plus petite que Yazio. |
| 8 | Cardio | 3 | **5** | Deux séances par semaine coexistent enfin, mais **deux le même jour s'écrasent encore** (R1). |
| 9 | Mode hors-ligne | 3 | **7** | Séance du jour pré-chargée, saisie marquée faite immédiatement, file rejouée dans l'ordre et testée. |
| 10 | Notifications et relances | 4 | **7** | Rappel à l'heure choisie, relance plafonnée à une tous les 27 jours ; le cron horaire reste à câbler hors du dépôt. |
| 11 | Design et cohérence UI | 6 | **6** | 883 `style=` dans les sources, 1 283 dans `/programme` rendu, e-mail en haut de chaque page : rien n'a bougé. |
| 12 | Performance ressentie | 4 | **6** | La saisie ne recharge plus, les workers ne gèlent plus ; l'accueil fait toujours 7 requêtes et lit l'historique entier pour afficher une semaine. |
| 13 | Architecture du code | 5 | **5** | Un gros gabarit dégraissé, une liste blanche unifiée — mais le blob s'est épaissi et `seance.py` dépasse 1 550 lignes. |
| 14 | Modèle de données | 3 | **5** | `session_id`, colonne `rpe`, ciblage par date ; cardio toujours encodé en chaînes magiques, noms d'exercices toujours clés étrangères. |
| 15 | Sécurité | 6 | **7** | ProxyFix, clé de session obligatoire en prod, désabonnement scopé, import validé ; restent des identifiants AdMob de test par défaut. |
| 16 | Robustesse et gestion d'erreurs | 4 | **7** | Pagination, écriture avant suppression, replis sur colonnes absentes, plafond PostgREST simulé dans les tests. |
| 17 | Tests | 5 | **7** | 337 tests en 3,5 s, fausse base fidèle à PostgREST, garde-fous vérifiés par mutation — mais **aucune intégration continue** : rien ne les exécute avant un déploiement. |
| 18 | Monétisation et paywall | 5 | **6** | Le parcours d'achat natif fonctionne et s'éteint par variable d'environnement ; tarifs et punition du gratuit inchangés. |
| 19 | Boucle de rétention | 5 | **7** | Record célébré, poids du corps compté, rappel à l'heure, debrief après séance ; toujours aucune dimension sociale. |
| 20 | Accessibilité | 3 | **7** | Trois niveaux de texte à 4,5:1 (calculé et testé), cibles à 44 px, vrais boutons radio, chaque champ nommé. |

### Justifications

**1. Onboarding — 6/10** (inchangé)
Les sept choix sont passés de `<div @click>` à de vrais `<input type="radio">` sous étiquette (`templates/onboarding.html:229-292`), avec `role="radiogroup"` et anneau de focus — navigation aux flèches, annonce « 2 sur 3 » par la synthèse vocale. C'est un vrai gain, invisible pour la majorité.
Ce qui plombe la note : le formulaire ne demande que `prenom`, `age`, `sexe`, `niveau`, `frequence`, `objectif`, `equipement`. **Ni poids ni taille.** Or `core/strength.py:60-74` bascule sur des seuils absolus (`_ABSOLUTE`, ligne 43) quand le poids est inconnu — c'est-à-dire pour **tout nouvel utilisateur**. Le reproche du premier audit (« un rouge à vie pour les gabarits légers ») a été corrigé dans le calcul mais pas dans la collecte : la fonctionnalité existe et ne s'active jamais toute seule. Ajouter deux champs à l'étape 1 coûte dix minutes.

**2. Saisie de séance — 4 → 7/10**
`routes/seance.py:1036` répond en JSON quand le client l'accepte ; `static/js/seance.js:403-436` met la carte à jour, la referme et ouvre la suivante. Plus de POST + 302 + rendu de 108 ko par exercice. `_pr_check` (`routes/seance.py:1039`) compare la série à tout l'historique et renvoie le type de record — première fois, charge, reps, reps à charge égale — affiché au moment où il tombe. Le ciblage par date exacte (`core/db.py:489`) fait coexister deux séances du même nom dans la semaine, ce qui concernait 9 des 20 programmes du catalogue.
Ce qui manque pour 8 : le tableau de séries fait toujours **6 colonnes** (`templates/seance_edit.html:339-344` : Sér., Reps, Poids, RPE, Remarque, ×) sur un écran de 375 px. Hevy affiche un exercice à la fois. C'est le dernier vrai reproche sur l'écran le plus utilisé de l'app.

**3. Programme et planning — 4 → 6/10**
`replace_program_body` (`core/db.py`, liste `PROG_BODY_KEYS`) part de l'ancien blob et ne remplace que les clés métier : les bilans, exos perso, badges, record de streak et plats de la semaine survivent à l'autosave, à l'import, au changement de programme et à l'adoption IA. Les reps et le repos sont stockés (`_reps_hint`).
Ce qui bloque : `/programme` rend **304 ko de HTML** contenant **1 283 attributs `style=`** (mesuré). Le planning reste indexé par jour de semaine, donc inapte à un programme en cycle de 5 jours. Et `routes/programme.py:212` écrit toujours dans un GET.

**4. Progression et statistiques — 5 → 7/10**
`/progres/exercice` + `core/exercise_stats.py` donnent enfin l'historique complet d'un mouvement : records, courbes par métrique, variantes, toutes les séances. Plotly (≈3 Mo depuis un CDN) a disparu au profit de SVG calculé côté serveur, et de la CSP (`app.py`).
Le plafond est le même qu'à l'axe 1 : les standards relatifs ne servent qu'à ceux qui ont renseigné leur poids ailleurs.

**5. Coach IA — 5 → 7/10**
Réponse en flux SSE, 1 400 tokens au lieu de 500, mémoire de 700 caractères entre conversations (`core/coach_memory.py`, migration v36 appliquée).
**Reste** : `routes/coach.py:457` et `routes/generator.py:358` renvoient encore « ANTHROPIC_API_KEY manquante » **à l'utilisateur**. C'est exactement le reproche du premier audit, corrigé sur le chemin de génération et oublié sur le chemin de configuration. Le quota n'est toujours pas atomique.

**6. Générateur de programme IA — 4 → 6/10**
Les reps générées sont conservées et les métadonnées préservées. Mais l'appel reste **synchrone dans la requête** : 2 600 tokens, 10-25 s, sans streaming ni indicateur de progression. Le passage à `gthread --threads 8` empêche que ça gèle les autres ; ça ne fait rien pour celui qui attend.

**7. Nutrition — 5 → 6/10**
Le scan de code-barres (`core/openfoodfacts.py`, `static/js/barcode.js`) fait l'appel côté serveur — l'IP et les scans ne sortent pas de l'app — avec conversion kJ→kcal, portion de l'emballage et cache mémoire. 25 tests.
La base locale reste à 270 aliments, l'historique nutritionnel ne remonte pas au-delà de la semaine affichée, et rien n'exporte.

**8. Cardio — 3 → 5/10**
Deux courses dans la semaine coexistent désormais. **Mais deux le même jour ne coexistent pas** : `routes/cardio.py:205` appelle `replace_exo_rows(date, seance, "CARDIO:Course", …)` et la seconde remplace la première — reproduit (**R1**, une seule ligne conservée, 45 min). Un footing le matin et un vélo le soir passent (activités différentes) ; deux footings non. Toujours pas de chrono live, pas de GPS, aucun import Strava.

**9. Mode hors-ligne — 3 → 7/10**
La séance du jour est pré-chargée par message `PRECACHE` au service worker ; hors ligne, la saisie marque la carte faite, la referme et ouvre la suivante (`static/js/seance.js:391-409`) au lieu de ne rien montrer ; la file est rejouée **séquentiellement** et s'arrête au premier échec sans perdre la suite. 13 tests JS couvrent ces cas, dont la session expirée qui ne doit pas consommer la série.
Le plafond : en natif, l'app reste une webview sur une URL distante. Railway indisponible = écran blanc, quel que soit le cache.

**10. Notifications et relances — 4 → 7/10**
Rappel à l'heure choisie (`core/reminders.py`, réglage `reminder_hour` 6-22 h), ciblant uniquement ceux qui ont une séance prévue non faite. La relance des inactifs est plafonnée à une tous les 27 jours (`push_subscriptions.last_reactivation_at`, migration v34) au lieu d'une par jour pendant 27 jours.
Ce qui reste hors du dépôt : le cron horaire doit être câblé chez un tiers. Non vérifiable ici.

**11. Design et cohérence UI — 6/10** (inchangé)
Aucun travail de fond n'a été fait sur cet axe et ça se voit : **883** attributs `style=` dans les gabarits (931 avant), l'e-mail complet de l'utilisateur en haut de **chaque** page (`templates/base.html:119`), 76 emoji utilisés comme contenu (dont 30 dans l'onboarding), 11 déclarations sous 12 px. Le contraste s'est amélioré, mais c'est l'axe 20.

**12. Performance ressentie — 4 → 6/10**
Gains réels : plus de rechargement à la saisie, `gunicorn -k gthread --threads 8` (`railway.json`), lecture paginée (`core/db.py:35-51`), profil et onboarding mis en cache.
Ce qui reste, mesuré : **7 requêtes Supabase** pour un `GET /accueil` (**R3**), **500 lignes lues** pour afficher une semaine (**R4**), `core/analytics.py:28-33` qui écrit l'event **dans la requête**, et `/programme` à 304 ko.

**13. Architecture du code — 5/10** (inchangé)
Au crédit : `seance_edit.html` passe de 1 445 à **847** lignes (le JS est sorti dans `static/js/seance.js`), et les cinq listes blanches divergentes sont devenues une seule fonction.
Au débit, et c'est plus lourd : le blob JSON fourre-tout compte **27 clés `_x`** lues ou écrites (`prog["_x"]` / `prog.get("_x")`), contre « 25+ » au premier audit — `_debrief_free` et `_session_notes` s'y sont ajoutées ; `routes/seance.py` a dépassé **1 553 lignes** (le premier audit y citait déjà des lignes au-delà de 1 190) ; `MUSCLE_LIST` est toujours dupliqué dans **4** fichiers (`routes/seance.py`, `programme.py`, `gestion.py`, `generator.py`) ; `core/db.py` fait 1 653 lignes. Les six phases ont ajouté des fonctionnalités à une structure qu'elles n'ont pas assainie.

**14. Modèle de données — 3 → 5/10**
`history.session_id` (uuid5 déterministe sur user|date|séance) et `history.rpe` existent (migration v34), les opérations ciblent la date exacte, les bilans ont leur table.
Mais le cardio reste encodé en chaînes magiques `CARDIO:Type`, testées par `startswith` **6 fois dans 3 fichiers** (`routes/gestion.py:157`, `progres.py:492,499`, `seance.py:443`) et construites dans un quatrième (`cardio.py:189`) ; le nom d'exercice reste la clé étrangère de fait ; et le `session_id` est calculé mais rien ne lit encore par lui.

**15. Sécurité — 6 → 7/10**
Corrigés : `ProxyFix` (le rate-limit comptait l'IP du proxy, donc tout le monde ensemble), refus de démarrer en prod sans `FLASK_SECRET_KEY`, exemption CSRF de la première requête supprimée, `/push/unsubscribe` scopé au propriétaire, secret cron accepté **uniquement** en en-tête, import JSON validé et assaini.
Restent : les identifiants AdMob de **test** comme valeurs par défaut (`app.py:427-428`) — en production sans variable, zéro revenu et violation des CGU ; `charge.refunded` et `charge.dispute.created` toujours non traités (un remboursement laisse l'accès à vie) ; et les deux messages nommant `ANTHROPIC_API_KEY`.

**16. Robustesse et gestion d'erreurs — 4 → 7/10**
`_fetch_all` pagine toutes les lectures de listes ; `save_hist` **insère avant de supprimer** et annule ses insertions en cas d'échec — l'historique n'est jamais vide en cours d'opération ; les colonnes ajoutées par les migrations ont un repli silencieux loggué. Le plafond `max-rows` de PostgREST est simulé dans la fausse base, ce qui permet à un test de repérer une lecture non paginée.
Le chemin `save_hist` reste en deux temps, donc non transactionnel.

**17. Tests — 5 → 7/10**
337 tests en 3,5 s. La fausse base reproduit des comportements réels de PostgREST (lignes renvoyées à l'insertion, clés uuid, plafond à 1 000 lignes), et cinq garde-fous ont été **vérifiés par mutation** : on réintroduit le défaut, le test tombe. Des tests portent sur des angles rarement couverts — accessibilité sur 9 pages, expressions Alpine invalides, règle CSS qui masquerait le parcours d'achat, code natif relu depuis Python.
Pourquoi pas 8 : **aucune intégration continue** (`.github/workflows` absent). Les tests ne protègent que celui qui pense à les lancer, et le déploiement part de `main` sans barrière. Par ailleurs le harnais JS ne couvre que 2 des 19 scripts, il n'y a pas de mesure de couverture, et la couche Java n'est testée que par recherche de chaînes.

**18. Monétisation et paywall — 5 → 6/10**
Le parcours natif fonctionne de bout en bout : tarifs rendus, `checkout.stripe.com` autorisé par la coquille, et un interrupteur `HIDE_NATIVE_BILLING` retire tout avant un dépôt sur le Play Store. Le point de risque signalé par le premier audit est traité.
Inchangés : 39,99 €/an contre 25-30 € chez Hevy et Strong, et surtout `routes/gestion.py:303-308` qui **force `auto_prefill_weight = False`** dès qu'un compte gratuit enregistre ses réglages. Punir la fonction la plus utilisée de l'app est le plus mauvais levier de conversion possible : ça ne fait pas payer, ça fait partir.

**19. Boucle de rétention — 5 → 7/10**
Le record est célébré au moment où il tombe ; les séances au poids du corps comptent enfin dans le streak, les compteurs et les défis ; le rappel arrive à l'heure choisie ; le debrief va au-devant de l'utilisateur sur l'écran qui suit la séance, avec un aperçu offert par semaine aux comptes gratuits.
Ce qui manque pour 8 : aucune dimension sociale, et un défi hebdomadaire identique pour tout le monde. Le parrainage relie déjà des comptes (`referred_by`) — un classement privé entre parrain et filleuls est à portée.

**20. Accessibilité — 3 → 7/10**
Les trois niveaux de texte passent 4,5:1 sur le fond de page comme sur le fond de carte, **calculé dans un test** et non estimé à l'œil. Les cibles tactiles atteignent 44 px, et là où la mise en page l'interdit, la surface sensible est étendue par pseudo-élément avec des dimensions prises sur des mesures réelles pour qu'aucune zone voisine ne se recouvre. Chaque contrôle des 9 pages principales a un nom annonçable, vérifié par un test qui refuse tout champ muet.
Ce qui reste : 11 déclarations sous 12 px, des emoji comme contenu porteur de sens, et `user-select: none` toujours sur `body` (relâché sur le contenu, pas sur l'ossature).

---

## Partie 2 — Parcours par profil

| # | Profil | Avant | Après | Ce qui a changé |
|---|---|---:|---:|---|
| 2.1 | Débutant complet, jour 1 | 6 | **7** | Choix accessibles, saisie sans rechargement, record célébré dès la première série. Toujours aucune question sur son poids. |
| 2.2 | Débutant, semaine 3 | 4 | **7** | Sa séance du vendredi n'efface plus celle du lundi — c'était le défaut qui touchait les 3 programmes débutants par défaut. Rappel à l'heure qu'il choisit. |
| 2.3 | Intermédiaire venant de Hevy/Strong | 3 | **5** | Fiche par exercice et records en direct comblent une partie de l'écart ; sans import CSV, il doit tout ressaisir, et le tableau 6 colonnes le fera repartir. |
| 2.4 | Avancé / « pro » | 3 | **4** | Reps et repos enfin prescrits, RPE en colonne dédiée ; mais toujours pas de blocs, pas de deload, pas de tempo. |
| 2.5 | Utilisateur FREE | 5 | **5** | Ses séances au poids du corps comptent enfin. Mais toucher ses réglages lui coupe toujours le pré-remplissage des charges (`gestion.py:303-308`). |
| 2.6 | Utilisateur en ESSAI restreint | 4 | **4** | Inchangé : il découvre Nutrition et les stats, pas le coach — l'essai ne fait pas essayer ce qui se vend. |
| 2.7 | VIP payant | 5 | **7** | Coach en flux avec mémoire, debrief après chaque séance, fiche exercice, scan code-barres. C'est le profil qui a le plus gagné. |
| 2.8 | Utilisateur de l'app native | 4 | **7** | Compte à rebours qui défile dans la barre de notification, scan, plus de pub s'il paie, achat possible. Reste une webview distante. |
| 2.9 | En salle sans réseau | 2 | **7** | Sa séance est pré-chargée, sa saisie est confirmée à l'écran, sa file repart dans l'ordre au retour du réseau. |

**2.9 mérite un mot** : c'est le parcours qui a le plus progressé (2 → 7) et le seul dont chaque étape est couverte par des tests automatisés. Il plafonne à 7 parce que l'app native reste une webview sur une URL distante : sans réseau **au démarrage à froid**, le cache du service worker sauve la séance, mais rien ne sauve un premier lancement.

---

## Partie 3 — Audit technique

### Défauts introduits ou laissés par les six phases (repères N)

| Gravité | Constat | Source | Conséquence |
|---|---|---|---|
| **N1 — IMPORTANT** | Deux cardios identiques le même jour : le second remplace le premier. Le ciblage est passé de la semaine à la date, ce qui a réduit le défaut sans le supprimer. Reproduit (**R1**). | `routes/cardio.py:205` ; `core/db.py:489` | Deux footings le même jour = un seul compté dans les stats et le calendrier. |
| **N2 — MINEUR** | Les messages de configuration du coach et du générateur nomment toujours la variable d'environnement à l'utilisateur. Le chemin de *génération* a été assaini en phase 5, pas le chemin de *configuration*. | `routes/coach.py:457` ; `routes/generator.py:358` | Fuite du fournisseur et de l'hébergeur si la clé vient à manquer. |
| **N3 — MINEUR** | Le blob programme compte 27 clés `_x`, contre « 25+ » au premier audit. Chaque phase y a déposé son état (`_debrief_free`, puis `_session_notes` avant sa migration en table) au lieu de créer une table d'emblée. | `core/db.py` (`PROG_BODY_KEYS`) | Un seul enregistrement JSONB porte réglages, badges, bilans, quotas et plats. Le verrou optimiste le protège ; il ne le range pas. |
| **N4 — MINEUR** | Les écritures de badges et de record de streak dans le `GET /accueil` ne sont **pas** protégées par le garde `is_navigation`, contrairement à l'upsell et au défi. Reproduit (**R2** : 2 écritures au premier affichage). | `routes/accueil.py:126-131` ; `:290-293` vs `:455`, `:501`, `:525` | `prefetch.js:40` déclenche un chargement au `touchstart` : effleurer le lien Accueil peut écrire en base. |

### Défauts du premier audit — état

| Gravité initiale | Constat | État |
|---|---|---|
| CRITIQUE | Même séance 2×/semaine écrasée | **ÉCRITURE corrigée, LECTURE non — voir l'erratum ci-dessous** |
| CRITIQUE | Autosave effaçant les métadonnées | **Corrigé** — `replace_program_body`, 5 tests de survie |
| CRITIQUE | Cardio : une séance par activité et par semaine | **Partiel** — voir N1 |
| CRITIQUE | Historique tronqué à 1 000 lignes | **Corrigé** — `_fetch_all` (`core/db.py:35-51`), plafond simulé dans la fausse base, 3 tests |
| CRITIQUE | Worker bloqué par les appels IA | **Corrigé** — `gthread --threads 8`, flux SSE pour le coach |
| IMPORTANT | `save_hist` non transactionnel | **Atténué** — insertion avant suppression, annulation des insertions |
| IMPORTANT | Poids du corps non compté | **Corrigé** — `core/hist.py`, prédicat unique |
| IMPORTANT | Écritures dans des GET | **Partiel** — voir N4 |
| IMPORTANT | Import JSON non validé | **Corrigé** — typage + assainissement |
| IMPORTANT | Pas de `ProxyFix` | **Corrigé** |
| IMPORTANT | Secrets d'infra dans les erreurs | **Partiel** — voir N2 |
| IMPORTANT | `FLASK_SECRET_KEY` facultative | **Corrigé** — refus de démarrer en prod |
| IMPORTANT | Relance push 27 jours d'affilée | **Corrigé** — migration v34 |
| IMPORTANT | Saisie = rechargement complet | **Corrigé** |
| MINEUR | `/push/unsubscribe` sans propriétaire | **Corrigé** |
| MINEUR | CSRF : première requête exemptée | **Corrigé** |
| MINEUR | Secret cron en `?token=` | **Corrigé** — en-tête uniquement |
| MINEUR | `_session_notes` purgées à 84 jours | **Corrigé** — table `session_notes` (v34/v35) |
| MINEUR | Quota coach non atomique | **Non corrigé** |
| MINEUR | `charge.refunded` non traité | **Non corrigé** |
| MINEUR | IDs AdMob de test par défaut | **Non corrigé** (`app.py:427-428`) |

**Bilan** : 15 corrigés, 3 partiels, 3 non corrigés, 4 nouveaux.

### Erratum (2026-09-26) — ce rapport s'est trompé

Ce rapport a conclu que « même séance 2×/semaine » était corrigé et a noté
l'axe 2 à **7/10** sur cette base. C'était faux : seule l'écriture l'était.

`_exo_curr_rows` (`routes/seance.py:119`) comparait encore la **semaine**.
Ouvrir « Push » le jeudi après l'avoir fait le lundi affichait donc la
séance du lundi déjà cochée, ses séries dedans, impossible à refaire —
signalé par l'utilisateur, pas par cet audit. Les données étaient saines,
l'écran mentait. Le correctif du premier audit nommait pourtant cette moitié
(« adapter `_exo_curr_rows`/`_exo_completed` pour comparer sur `Date` ») ;
elle n'avait pas été faite, et la vérification n'est pas allée plus loin que
le chemin d'écriture et le résultat des tests.

**Leçon méthodologique** : vérifier qu'une donnée est bien écrite ne dit rien
de ce que l'utilisateur voit. Les quatre reproductions de ce rapport portent
sur la base ; aucune n'ouvrait un écran.

Corrigé depuis (lecture par date dans toute la vue séance, « dernière fois »
groupée par date et non par semaine), avec 4 tests sur le rendu de la page
vérifiés par mutation. L'axe 2 reste à 7/10 : la note était juste, la
justification ne l'était pas.

---

## Partie 4 — Ce qu'il faut faire maintenant

### A. Les 5 corrections, par impact décroissant

| # | Problème | Correctif | Effort |
|---|---|---|---|
| 1 | Aucune intégration continue : rien n'exécute les 337 tests avant un déploiement | `.github/workflows/tests.yml` : `pytest` + `node tests/js/run.js` sur chaque push ; Railway ne déploie que si le job passe | **S** |
| 2 | Le gratuit perd le pré-remplissage des charges en touchant ses réglages | Retirer la restriction (`gestion.py:303-308`). Gater une fonction d'usage quotidien ne convertit pas, ça fait désinstaller | **S** |
| 3 | Ni poids ni taille demandés, alors que trois fonctionnalités en dépendent | Deux champs à l'étape 1 de l'onboarding, pré-remplissant `profiles` et la courbe de poids | **S** |
| 4 | Deux cardios identiques le même jour s'écrasent (N1) | Série incrémentale au lieu du remplacement, ou écriture par `session_id` | **S** |
| 5 | Badges et streak écrits pendant un GET, déclenchables par un simple effleurement (N4) | Les déplacer dans `/seance/finish`, ou à défaut les passer sous `is_navigation` comme leurs voisins | **S** |

### B. Les 3 chantiers de fond

1. **Sortir l'état du blob JSON.** 27 clés dans un seul JSONB, dont des quotas, des badges, des réglages et des plats de la semaine. Une table par domaine (`user_settings`, `user_state`) supprimerait le verrou optimiste, les fusions 3 voies et la moitié des tests de préservation. C'est le chantier qui débloque l'axe 13 et l'axe 14 d'un coup.
2. **Découper `routes/seance.py` (1 553 lignes) et `core/db.py` (1 653 lignes).** Ce sont les deux fichiers où chaque phase est venue ajouter, et ceux où la prochaine régression arrivera.
3. **Alléger `/programme`** : 304 ko et 1 283 `style=` pour une page d'édition. Classer les styles répétés du partial `_programme_seance_card.html` divise le poids par trois sans changer une ligne de logique.

### C. Les 3 choses à supprimer (inchangé depuis le premier audit)

1. **Arcade** — 550 lignes, jamais annoncée, non instrumentée, aucun lien avec la rétention.
2. **Les profils d'entraînement** — une indirection que ni Hevy ni Strong n'ont, gatée à 1 profil en gratuit, qui double les cas dans `save_state`.
3. **Les emoji comme contenu** — 76 occurrences, dont 30 dans l'onboarding, à côté d'un sprite SVG complet et cohérent.

### D. Une seule action pour les 30 prochains jours

**Mettre en place l'intégration continue.** Pas une fonctionnalité, pas un refactor : une barrière. Il y a aujourd'hui 337 tests rapides, cinq d'entre eux vérifiés par mutation, couvrant précisément les pertes de données qui ont motivé le premier audit — et rien ne les exécute avant qu'un commit parte en production. Le déploiement se fait depuis `main`, automatiquement, sans barrière.

Sur les trois derniers jours, quatre défauts ont atteint l'utilisateur avant d'être vus : une carte qui ne se chargeait jamais, un panneau qui ne s'ouvrait jamais, une option de cardio impossible à sélectionner, et des boutons d'achat masqués par une règle CSS oubliée. Aucun n'aurait été arrêté par les tests existants — mais chacun a donné lieu à un test **après coup**, et ce sont précisément ces tests-là que rien ne protège aujourd'hui.

Un fichier de quinze lignes. C'est le meilleur rapport entre l'effort et le risque évité de tout ce rapport.

---

## 5. Écarts entre la doc (CONTEXT.md) et le code

CONTEXT.md a été remis à jour le 2026-09-24 et décrit fidèlement l'état actuel. Trois écarts subsistent :

| Affirmation | Réalité |
|---|---|
| « 293 tests (dont 13 tests JavaScript) » (section Tests) | **306** Python et **31** JS au commit `5d27772`. Le compte a été dépassé par les commits suivants. |
| « `--text-disabled` reste bas exprès » (tokens.css) | Exact, mais le fichier ne dit pas que **11 déclarations sous 12 px** subsistent dans les gabarits. |
| Section « App native : parcours d'achat » | Décrit l'interrupteur, mais pas le fait que `checkout.stripe.com` doit figurer dans `allowNavigation` — sans quoi le parcours est mort en silence. À ajouter : c'est le genre d'oubli qui se paye deux mois plus tard. |

---

## 6. Non vérifiable depuis le dépôt

- **L'état réel de Supabase** : les migrations v32 à v36 sont déclarées appliquées, sans moyen de le confirmer ici. Le code a un repli sur colonne absente, donc **rien ne signale** une migration oubliée.
- **Le plafond `max-rows`** du projet Supabase : la pagination est en place quelle que soit sa valeur, mais la valeur elle-même n'est pas lisible ici.
- **Les crons externes** : `/tasks/reminders` doit être appelé toutes les heures et `/tasks/reactivation` une fois par jour, par un service tiers. Leur existence et leur régularité ne se vérifient pas dans le dépôt.
- **Les variables d'environnement Railway** : `ANTHROPIC_API_KEY`, `STRIPE_*`, `VAPID_*`, `ADMOB_*`, `CRON_SECRET`, `GOOGLE_WEB_CLIENT_ID`. Seule la dernière a pu être observée, par le rendu de la page de connexion en production.
- **Le comportement sur appareil réel** : le compte à rebours dans la barre de notification, le scan de code-barres et le paiement Stripe dans la webview ont été construits et testés unitairement, jamais observés sur un téléphone par l'auteur de ce rapport.
- **Le volume d'utilisateurs** : aucune donnée d'usage. Les jugements sur la rétention et la monétisation reposent sur le code et sur les pratiques du marché, pas sur des chiffres.
