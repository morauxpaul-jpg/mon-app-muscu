# Muscu Tracker PRO — CONTEXT.md

## Architecture

PWA Flask (Python) avec Supabase (PostgreSQL) en backend, déployée sur Railway depuis `main`.
- **Framework** : Flask avec Blueprints + Flask-Limiter (rate limiting)
- **Frontend** : Jinja2 templates + Alpine.js + CSS custom (refonte UI dark minimal style Strong/Hevy)
- **Auth** : Supabase Google OAuth → bridge JWT → session Flask (cookie 30 jours)
- **Data** : Supabase tables (history, programs, profiles, onboarding, nutrition, coach_messages, coach_conversations, session_notes, body_weight, push_subscriptions, events) via `service_role` key. **Toutes les lectures de listes sont paginées** (`_fetch_all`) : PostgREST plafonne silencieusement à 1000 lignes.
- **PWA** : Service Worker (network-first sur les pages, stale-while-revalidate sur `/static`), manifest.json, séance du jour pré-chargée pour l'usage hors-ligne
- **Serveur** : gunicorn `-k gthread --threads 8` (`railway.json`) — un appel IA lent ne gèle plus l'app pour tout le monde ; `ProxyFix` devant, sans quoi le rate-limit « 60/min par IP » comptait l'IP du proxy, donc tout le monde ensemble
- **IA** : Coach via API Anthropic (Claude Haiku 4.5), réponses diffusées en flux (SSE)
- **Coquille native** : Capacitor (`android/`, `capacitor.config.json` à la racine) — webview sur l'URL de prod + plugin AdMob. Pubs (Free uniquement, app native uniquement) : `pwa/static/js/ads.js`, IDs via env `ADMOB_BANNER_ID`/`ADMOB_INTERSTITIAL_ID`. Docs : `docs/CAPACITOR.md` + `docs/PLAY_STORE.md`. Login Google natif **branché côté code** (2026-06-15) : `login.html` détecte Capacitor → `@capgo/capacitor-social-login` (idToken + nonce) → `supabase.auth.signInWithIdToken` → `/auth/session` (OAuth webview interdit, 403 disallowed_useragent). **Le client OAuth Android de Google Cloud doit déclarer le nom de package EXACT et l'empreinte SHA-1 de la clé de signature.** Piège vécu : le client avait été créé le 2026-06-15 avec `com.muscutracker.app`, et le package a été renommé `com.muscutracker.fit` le lendemain (commit 45b6be5). La connexion native a donc échoué pendant trois mois avec un message illisible — Google refuse sans jamais afficher le sélecteur de compte. Empreinte actuelle (clé de release) : `E4:C0:D5:D4:6A:78:3C:3D:CA:6C:6B:C1:E7:28:5B:DE:00:A4:DF:EA`, à relire par `keytool -printcert -jarfile app-release.apk` après tout changement de clé. Une publication via Play App Signing ajoute une SECONDE empreinte (celle de Google) à déclarer en plus. L'identifiant Android n'est copié nulle part dans le code : c'est le client **web** (`GOOGLE_WEB_CLIENT_ID`) que l'app envoie ; il doit aussi figurer dans « Authorized Client IDs » du fournisseur Google côté Supabase.

## Structure des fichiers

```
pwa/
├── app.py                         # Flask app, blueprints, auth gate (g.user_id, g.is_vip), landing, /service-worker.js (CACHE_VERSION + SHA du commit)
├── run_local_fake.py              # App en local sur fausse DB (FakeSupabase des tests) + /test-seed — voir « Preview local »
├── cron_reactivation.py           # Cron CLI de relance push des inactifs
├── cron_reminders.py              # Cron CLI du rappel de séance à l'heure choisie (à lancer toutes les heures)
├── capture_screens.py / capture_assets.py  # Captures PNG (fiche store, motion design) via le serveur fake
├── compress_icon.py / generate_icons.py / rebuild_program_from_history.py  # Scripts utilitaires (non commités pour partie)
├── tools/                          # Outils de développement (hors chemin d'exécution de l'app)
│   ├── build_exercise_prompts.py   # écrit exercise_prompts.json : 1 prompt d'illustration par exercice
│   ├── generate_exercise_art.py    # génère les images via l'API Gemini (reprenable, image de référence jointe)
│   └── import_exercise_art.py      # recadre, détouré, carre et convertit en WebP vers static/img/exercises/
├── supabase_schema_v23.sql … v31  # Migrations SQL Supabase successives (nutrition, VIP, coach, stripe, events, referral, push, newsletter)
├── supabase_schema_v32_prog_version_hist_index.sql  # programs.version (verrou optimiste) + index history(user_id,id)
├── supabase_schema_v33_body_weight.sql  # table body_weight (une pesée / jour / user)
├── supabase_schema_v34_session_notes.sql # history.session_id + history.rpe, index (user_id,date), table session_notes, push_subscriptions.last_reactivation_at
├── supabase_schema_v35_session_duration.sql # session_notes.duration_min
├── supabase_schema_v36_coach_memory.sql # profiles.coach_memory (note du coach entre conversations)
├── tests/                         # pytest — conftest = fake Supabase en mémoire (cd pwa && python -m pytest tests -q)
├── core/
│   ├── db.py                      # Façade de la couche données : la carte des dix modules db_* (aucun code)
│   ├── db_base.py                 # Connexion Supabase (service_role), cache LRU TTL 60s, pagination PostgREST, use_client()
│   ├── db_historique.py           # Table history : lecture, écriture, opérations ciblées, renommages
│   ├── db_programme.py            # Blob programs.data : verrou optimiste, fusion 3 voies, corps vs données perso
│   ├── db_profil.py               # profiles : profil, onboarding, poids de corps
│   ├── db_nutrition.py            # nutrition : repas du jour et sommes de macros
│   ├── db_bilans.py               # session_notes (v34) : bilans de séance
│   ├── db_abonnement.py           # Tier PRO, Stripe, parrainage et VIP à durée limitée
│   ├── db_push.py                 # push_subscriptions, newsletter, relance des inactifs
│   ├── db_coach.py                # coach_messages / coach_conversations
│   ├── db_admin.py                # Stats globales, funnel, fiche user, suppression de compte
│   ├── data.py                    # Façade Flask (lit user_id depuis flask.g) + helpers nutrition/coach
│   ├── dates.py                   # Helpers dates (timezone Paris), DAYS_FR, MONTHS_FR
│   ├── muscu.py                   # Logique muscu (1RM, muscles, base_name, overload_suggestion)
│   ├── seance_semaine.py          # Semaine de programme, libellé du jour, séance réellement faite
│   ├── seance_historique.py       # Ce que l'historique dit d'un exercice : variante, record, suggestion
│   ├── seance_contexte.py         # Le dictionnaire que reçoit chaque carte d'exercice
│   ├── seance_calques.py          # Substituts, extras, brouillon libre, ordre des cartes (par séance+date)
│   ├── seance_saisie.py           # Le formulaire devient des lignes d'historique + détection de record
│   ├── seance_cardio.py           # Lecture/écriture du format « CARDIO:Type » dans la remarque
│   ├── hist.py                    # Prédicats UNIQUES sur l'historique (is_perf, is_muscu_perf, is_session_marker, tonnage) — une seule définition de « séance faite »
│   ├── strength.py                # Standards de force relatifs au poids de corps (ratios par muscle × sexe, niveaux)
│   ├── exercise_stats.py          # Fiche par exercice : variantes, séances, records, séries, sparkline SVG
│   ├── reminders.py               # Rappel de séance à l'heure choisie (ciblage, payload, run_reminders)
│   ├── coach_memory.py            # Note persistante du coach sur l'utilisateur (700 car. max)
│   ├── debrief.py                 # Debrief de fin de séance : collecte des chiffres réels + rédaction IA
│   ├── openfoodfacts.py           # Produit emballé par code-barres (kJ→kcal, portion, cache mémoire)
│   ├── catalog.py                 # Catalogue de 19 programmes prédéfinis (onboarding)
│   ├── exercises_data.py          # Fiches exercices : matériel requis + substitutions
│   ├── foods_data.py              # Base de ~270 aliments courants (kcal/macros pour 100 g + portions) pour la recherche Nutrition
│   ├── body_map.py                # Polygones SVG du body map (d'après react-body-highlighter)
│   ├── challenges.py              # Défis hebdomadaires (un défi tournant, évalué depuis l'historique)
│   ├── push.py                    # Push web : config VAPID + envoi pywebpush, relance des inactifs
│   ├── limiter.py                 # Instance Flask-Limiter partagée (60 req/min par IP, Redis si dispo)
│   └── analytics.py               # Façade track(event,props) fire-and-forget + helper paywall() (funnel conversion)
├── routes/
│   ├── auth.py                    # Login Google, bridge JWT, logout, /auth/debug
│   ├── accueil.py                 # Dashboard (/accueil) — planning hebdo, streak, badges, défi, "Prochaine séance"
│   ├── seance.py                  # Séance du jour (saisie, skip, reset, finish + bilan, extras, cardio inline, suggestion de surcharge)
│   ├── programme.py               # CRUD programme + profils + planning + import/export
│   ├── progres.py                 # Progression — body map, calendrier, volume, zoom mouvement, poids corporel (/progres/poids)
│   ├── gestion.py                 # Paramètres, settings, export/import, fusion doublons, reset soft/total
│   ├── arcade.py                  # Mini-jeux
│   ├── onboarding.py              # Questionnaire post-login (recommend, submit)
│   ├── cardio.py                  # Saisie cardio (chrono + distance + cal + RPE) → table history
│   ├── nutrition.py               # Profil métabolique (Mifflin-St Jeor) + journal repas (recherche aliments, plats de la semaine, saisie rapide, composition)
│   ├── coach.py                   # Chat IA (Claude Haiku 4.5) en flux SSE, réservé VIP, quota 15 msg/jour, mémoire entre conversations
│   ├── premium.py                 # Page de présentation des tiers (pré-paywall)
│   ├── billing.py                 # Stripe Checkout / webhook / portal (source de vérité du tier)
│   ├── generator.py               # Générateur de programme IA (VIP) — Claude → JSON validé → save_prog
│   ├── push.py                    # Abonnement push (clé VAPID, subscribe/unsubscribe), /tasks/reactivation
│   ├── share.py                   # POST /share/track — compteur de partages de progression (analytics)
│   ├── parrainage.py              # Lien d'invitation + récompense VIP (parrain/filleul) + apply_referral
│   └── admin.py                   # Stats, gestion VIP, fiche user, funnel (gated par ADMIN_EMAILS env)
├── templates/
│   ├── base.html                  # Layout master (topbar, nav 4 onglets, scripts globaux, patch notes)
│   ├── _body_map_svg.html         # SVG carte musculaire (inclus dans progres)
│   ├── _programme_seance_card.html# Partial : carte séance dans /programme
│   ├── partials/vip_lock.html     # Cadenas / mur VIP réutilisable
│   ├── landing.html               # Page publique (/)
│   ├── login.html                 # Page login Google (web + natif Capacitor)
│   ├── bridge.html                # Bridge OAuth → session Flask
│   ├── accueil.html               # Dashboard
│   ├── seance_choix.html          # Choix de séance du jour
│   ├── seance_edit.html           # Saisie exercices (Alpine, chrono, RPE, inline history)
│   ├── programme.html             # Gestion programme + profils + planning
│   ├── progres.html               # Progression (body map, calendrier, volume, standards de force)
│   ├── exercice.html              # Fiche d'un exercice : records, courbes, variantes, toutes les séances
│   ├── gestion.html               # Paramètres, export/import, reset, notifications, newsletter
│   ├── plus.html                  # Hub : Premium, Coach, Programme, Nutrition, Cardio, Arcade, Gestion, Tutoriel
│   ├── premium.html               # Page de présentation des tiers
│   ├── billing_success.html       # Retour Stripe Checkout
│   ├── parrainage.html            # Page parrainage
│   ├── plaques.html               # Calculateur de plaques
│   ├── coach.html                 # Chat IA
│   ├── generator.html             # Générateur de programme IA (form + preview + adopter)
│   ├── cardio.html                # Saisie cardio
│   ├── nutrition.html             # Profil + journal repas
│   ├── arcade.html                # Mini-jeux canvas
│   ├── onboarding.html            # Questionnaire 4 étapes (Alpine)
│   ├── admin.html / funnel.html   # Console admin + funnel de conversion (7/30/90j)
│   ├── faq.html / confidentialite.html  # Pages publiques (FAQ, politique de confidentialité)
│   ├── vip_wall.html              # Mur de blocage VIP plein écran
│   └── error.html                 # Page d'erreur
├── static/
│   ├── css/
│   │   ├── tokens.css             # Design tokens (couleurs, espacements, radius…)
│   │   ├── theme.css              # Variables, animations, composants globaux
│   │   ├── components.css         # Cards, stats, grids, boutons
│   │   ├── glass.css              # Liquid glass (chargé après components.css)
│   │   ├── icons.css              # Tailles et couleurs d'icônes (.icon, .icon-sm, .icon-accent…)
│   │   ├── timer.css / rest-timer.css  # Chrono de repos (local à la séance / barre globale)
│   │   ├── tutorial.css           # Overlay tutoriel
│   │   └── a11y.css               # **Chargé en dernier** : cibles tactiles, cases à cocher, sélection de texte, masquage des tarifs en natif
│   ├── js/
│   │   ├── alpine.min.js / alpine-sort.min.js  # Alpine.js + plugin sort bundlés localement
│   │   ├── sw-register.js         # Enregistrement SW + auto-update
│   │   ├── offline.js             # Détection hors-ligne, queue localStorage, sync
│   │   ├── notifications.js       # Rappels quotidiens (API Notification)
│   │   ├── push.js                # Abonnement push web (VAPID)
│   │   ├── install.js             # Expérience d'installation PWA (détection plateforme)
│   │   ├── ads.js                 # AdMob (app native + Free uniquement)
│   │   ├── rest-timer.js          # Chrono de repos global et persistant (barre injectée par base.html)
│   │   ├── share-card.js          # Carte de progression (canvas → PNG) + Web Share
│   │   ├── tuto-engine.js         # Moteur de tutoriel partagé (spotlight + bulle)
│   │   ├── tutorial.js / tuto-seance.js  # Tutoriels accueil / saisie de séance
│   │   ├── ui-fx.js               # Effets UI (toasts, micro-animations)
│   │   ├── prefetch.js            # Prefetch des pages clés
│   │   ├── exercise-library.js    # Bibliothèque d'exercices (search/picker)
│   │   ├── seance.js              # Saisie de séance (extrait de seance_edit.html) : enregistrement JSON, file hors-ligne, records, réordonnancement
│   │   ├── exo-info.js            # Modale « fiche exercice » de la séance
│   │   └── barcode.js             # Scan de code-barres via BarcodeDetector (Nutrition), repli saisie manuelle
│   ├── img/
│   │   ├── icons.svg              # Sprite SVG (lucide-like) référencé via <use href="…#name"/>
│   │   └── exercises/             # SVG illustrations exercices
│   ├── promo/, promo-vip*.mp4/.png # Assets marketing (fiche store, vidéo VIP)
│   ├── changelog.json             # Notes de version (patch notes modal)
│   ├── service-worker.js          # SW : Network First, CACHE_VERSION = base ; le SHA du commit est ajouté par app.py
│   ├── manifest.json              # PWA manifest
│   └── icon-192.png / icon-512.png # Icônes app
```

## Navigation (4 onglets)

1. **🏠 Accueil** (`/accueil`) — Dashboard, planning semaine compact, streak, carte « Prochaine séance » cliquable, stats
2. **💪 Séance** (`/seance`) — Sélection séance du jour, saisie exercices, ajout cardio inline
3. **📈 Progrès** (`/progres`) — Calendrier mensuel, volume hebdo, body map, hall of fame, zoom mouvement
4. **📋 Plus** (`/plus`) → Premium · Coach IA · Programme · Nutrition · Cardio · Arcade · Gestion · Tutoriel

## Système Free / VIP

- **Deux niveaux d'accès** (2026-06-14) :
  - `g.is_vip_full` = **PAYANT** (`tier == 'vip'`) → accès **complet** (Coach IA, Générateur IA, programmes PRO, multi-programmes/profils, export/import).
  - `g.is_vip` = full **OU essai à durée limitée** (`vip_until > now()`, via `db.vip_until_active()`) → accès **restreint** : **Nutrition + stats détaillées seulement**.
  - `vip_until` = essai « découverte » (parrainage/promo, migration v29). Volontairement court + restreint pour ne pas cannibaliser l'achat (un essai complet permettrait de générer un programme et tout extraire en 1 j).
  - **Règle de gate** : features payantes → `getattr(g, "is_vip_full", False)` ; Nutrition + stats avancées (`progres`, profondeur d'historique `gestion`) → `getattr(g, "is_vip", False)`.
  - Les deux sont résolus + cachés en session par `before_request` (`is_vip`, `is_vip_full`), exposés aux templates par le context processor. `billing.success` pose les deux ; le webhook passe le `tier` → recalculé au TTL. **TTL asymétrique** (2026-06-14) : un VIP confirmé est re-vérifié toutes les `VIP_CACHE_TTL`=120 s, un FREE toutes les `FREE_RECHECK_TTL`=15 s — pour qu'un passage VIP (grant admin ou achat Stripe) se propage en quelques secondes à la session du user, même sur un autre appareil. La vérif d'existence du compte auth (API auth, plus coûteuse) reste sur la cadence lente via `session['auth_check_ts']`.
- **Offre « équilibrée »** (2026-06-11) — Free = séances illimitées + progrès simple + 1 programme + cardio. VIP = Coach IA (15 msg/j), **Nutrition**, stats détaillées (body map/1RM/zoom), programmes PRO, multi-programmes/profils, export.
- **Gating Free** : Coach IA, Nutrition, Export/Import, programmes PRO du catalogue, stats avancées, multi-programmes/profils.
- **Onglet Plus** : sections épurées (Entraînement / Premium / Détente / Réglages) ; features VIP visibles avec cadenas + `vip_wall`. Incitation VIP douce sur l'accueil pour les gratuits (remplace le widget calories).
- **Mur VIP** : `templates/partials/vip_lock.html` (inline) ou `vip_wall.html` (plein écran).
- **Badge PRO** affiché dans la topbar pour les VIP.
- **Admin** (`ADMIN_EMAILS` env, séparateur virgule) peut basculer manuellement le tier d'un user via `/admin/set-tier`.
- **Paiement Stripe** (`routes/billing.py`) : Checkout (prix inline `price_data`, pas d'ID à pré-créer) pour mensuel 4,99€ / annuel 39,99€ / lifetime 79,99€. Webhook `/billing/webhook` (public + CSRF-exempt, signé) = source de vérité du tier ; `/billing/success` active aussi le VIP en filet ; `/billing/portal` = gestion/annulation. Tarifs ET boutons absents du rendu dans l'app native (cf. « App native : parcours d'achat »). Env : `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`. Migration : `supabase_schema_v27_stripe.sql` (colonne `profiles.stripe_customer_id`).
- **Upgrades de plan** : `billing.detect_current_plan()` lit l'abonnement actif (mensuel/annuel/None) ; la page Premium propose les paliers supérieurs aux abonnés. À l'upgrade, l'ancien abonnement est **supersédé** (`metadata.superseded=1`) puis annulé — le webhook `subscription.deleted` ignore alors la rétrogradation (pas de perte de VIP ni de double facturation). Réutilise le même `customer` Stripe.

## Fonctionnalités clés

### Séance
- Timer de repos auto (configurable, déclenché après saisie reps+poids)
- **Bip léger** en fin de repos (sine 600 Hz, ~80 ms, gain 0.04, généré via Web Audio API)
- Inline history (« Dernière fois : 80 kg × 8 »)
- Pré-remplissage automatique des poids
- Progression indicator (« EXERCICE 3/7 »)
- Inline-confirm pour actions destructives (jamais `prompt()`/`confirm()`/`alert()`, jamais hors-carte)
- Ajout cardio dans la séance via `/seance/add-cardio`
- **Enregistrement sans rechargement** (`/seance/save-exo` répond en JSON si `Accept: application/json`) : la carte se met à jour sur place et la suivante s'ouvre. Le POST classique reste le repli sans JavaScript.
- **Record annoncé en direct** : `_pr_check()` compare la série à tout l'historique de l'exercice et renvoie le type de record (première fois / charge / reps / reps à charge égale) ; la carte l'affiche au moment où il tombe.
- **Bilan de séance** (`session_notes`, migrations v34/v35) : ressenti, commentaire, durée. `history.session_id` (uuid5 déterministe user|date|séance) relie les lignes d'une même séance.
- Une même séance peut être faite **deux fois dans la semaine** : les opérations ciblent la date exacte, plus la semaine (cf. « Semaine continue »).

### Cardio
- Activités : Course, Vélo, Rameur, Natation, Corde, HIIT, Marche (avec MET pour estimation calories)
- Stockage dans la même table `history` (Exercice = `CARDIO:Type`, Reps = minutes, Poids = km, Remarque = `FC:… | Cal:… | RPE:…`, Muscle = `Cardio`)

### Nutrition
- Profil métabolique : BMR Mifflin-St Jeor, TDEE × facteur d'activité (5 niveaux : sédentaire → athlète)
- Objectif calorique ajusté selon objectif (Masse / Maintien / Sèche), macros recommandés en %
- Table Supabase `nutrition` : un repas par ligne (date, meal_type, macros, note)
- **Scan de code-barres** (mode « Scanner » du formulaire de repas) : `BarcodeDetector` du navigateur (Chrome/Android, donc l'app native et la PWA Android), repli par saisie des chiffres ailleurs — aucun décodeur JavaScript embarqué. Le produit est cherché côté **serveur** (`GET /nutrition/barcode/<code>` → `core/openfoodfacts.py` → Open Food Facts) : l'IP et les scans de l'utilisateur ne sortent pas de l'app et le cache est mutualisé. Le produit rejoint le panier « Aliments », donc mêmes réglages de portion et même bouton d'ajout.
- Caméra : `Permissions-Policy: camera=(self)` (app.py) + `android.permission.CAMERA` dans le manifeste Android ; Capacitor demande la permission au premier scan.

### Coach IA
- Modèle : `claude-haiku-4-5-20251001`, max **1400** tokens (500 coupait les réponses en plein milieu)
- **Réponse en flux** : `/coach/ask` répond en Server-Sent Events (`stream_with_context`, `X-Accel-Buffering: no`) quand le client le demande ; le texte s'écrit au fur et à mesure au lieu de faire patienter plusieurs secondes. Repli JSON si le flux n'est pas accepté.
- **Mémoire entre conversations** (`core/coach_memory.py`, migration v36) : après quelques échanges, le coach réécrit une note de 700 caractères max sur l'utilisateur (blessures, contraintes, préférences) dans `profiles.coach_memory` ; elle est injectée dans les conversations suivantes. Sans la colonne, l'écriture échoue en silence et l'app fonctionne sans mémoire.
- Accès réservé VIP (mur `vip_wall.html` pour les free)
- Quota VIP : 15 msg/jour (champs `profiles.coach_quota_date` + `coach_quota_count`, reset auto à chaque nouveau jour) — protège le coût API. Le quota est **rendu** si la génération échoue.
- Historique persisté dans `coach_messages` / `coach_conversations`, effaçable via `/coach/clear`
- Le system prompt inclut le profil utilisateur, le programme, l'historique récent et la note de mémoire
- Les erreurs techniques ne remontent plus au client (avant : « Vérifie ANTHROPIC_API_KEY dans Railway »)

### Debrief de fin de séance
- Le coach est une page qu'il faut **penser** à ouvrir. Le debrief va au-devant, sur l'écran qui suit la séance : `/seance/finish` mémorise la séance en session, l'accueil affiche une carte qui appelle `POST /seance/debrief`.
- `core/debrief.py` : `collect_facts()` calcule volume, séries, reps, RPE moyen, records battus et comparaison avec la dernière séance du même nom ; l'IA **rédige** trois phrases à partir de ces chiffres, elle ne les invente pas (~250 tokens).
- PRO complet ; **un aperçu gratuit par semaine** (`prog._debrief_free`, fenêtre glissante de 4 semaines) sert de démonstration honnête. L'aperçu n'est consommé que si la génération aboutit.
- La proposition est consommée une seule fois et **pas par le préchargement** de `prefetch.js` (garde `Sec-Fetch-Mode: navigate`) : sinon le survol du lien la brûlait avant que l'utilisateur la voie.

### Générateur de programme IA (VIP, 2026-06-14)
- **Route** `routes/generator.py` : `GET /generator` (form, VIP-gated via `paywall`), `POST /generator/generate` (prompt structuré → Claude Haiku 4.5, `max_tokens=2600` → **JSON strict** → `parse_and_validate`), `POST /generator/apply` (re-validation + `save_prog`, même chemin sûr que l'import ; reps NON persistées, cf. semaine continue).
- **`parse_and_validate(raw)`** = fonction **pure** (testée, `tests/test_generator.py`) : tolère les blocs ``` ```json ```, normalise les muscles (vers `MUSCLES` canoniques, défaut « Autre »), clamp sets 1–8, ≤6 séances / ≤12 exos, planning FR filtré + fallback cyclique.
- **Anti-coût** : quota 3/semaine glissante (7 j) / VIP via la table `events` (compte les `program_generated` des 7 derniers jours, `_gen_used_week`) + backstop Flask-Limiter `10/h` sur generate, `20/h` sur apply.
- **Prompt** : injecte la liste des exercices connus (`EXERCISES_INFO`) pour biaiser vers des exos illustrés + la liste des muscles canoniques.
- **Events** : `program_generator_viewed`, `program_generated`, `program_adopted` (nourrissent aussi le funnel). **Entrée UI** : carte « Générateur IA » dans le hub Plus (section Premium, cadenas si free).

### Parrainage (croissance, 2026-06-14)
- **Boucle** : chaque user a un `profiles.referral_code` (stable, dérivé de l'user_id) → lien `/?ref=CODE`. Page **/parrainage** (hub Plus) : lien + copier + partager (Web Share) + compteur de filleuls/jours gagnés.
- **Capture** : la landing pose un cookie `pending_ref` (survit au round-trip OAuth). À l'onboarding du filleul, `parrainage.apply_referral` crédite **une seule fois** : filleul **+1 j essai**, parrain **+3 j essai** (via `db.grant_vip_days` → `vip_until` cumulatif). L'essai = accès **restreint** (Nutrition + stats, cf. `is_vip_full`). Garde-fous : code valide, pas d'auto-parrainage, `referred_by` posé une seule fois. Le filleul passe en essai immédiatement (`session.pop('is_vip'/'is_vip_full')`) ; le parrain via la revalidation FREE (15 s). Récompenses ajustables : `REFERRER_VIP_DAYS` / `REFEREE_VIP_DAYS` dans `routes/parrainage.py`.
- **Migration** : `supabase_schema_v29_referral.sql` (`profiles` += `referral_code` [unique], `referred_by`, `vip_until`). Helpers `db_abonnement.py` : `get_or_create_referral_code`, `get_user_by_referral_code`, `set_referred_by`, `grant_vip_days`, `count_referrals`, `get_referred_by`, `vip_until_active`. Events : `referral_shared`, `referral_signup`.

### Nudge de relance (rétention, 2026-06-14)
- **Banner de retour** sur l'accueil : un user avec un historique mais inactif depuis ≥ `REACTIVATION_DAYS`=3 j (jours depuis la dernière perf réelle muscu/cardio) est accueilli par « Content de te revoir ! Ça fait N jours — on reprend en douceur ? » + bouton **Reprendre** (→ /seance). Dismissible (sessionStorage `reac_hidden`). Jamais pour un compte sans historique.
- Event `reactivation_nudge_shown` ({days}), émis seulement sur vraie navigation (Sec-Fetch-Mode navigate). Logique dans `routes/accueil.py`.
- **Phase 2 — Push web** (2026-06-15) : notifications push (VAPID + pywebpush) pour relancer ceux qui ne rouvrent pas l'app.
  - **Abonnement universel** (free + PRO) : bouton « Activer les notifications » dans Gestion (`static/js/push.js` → `window.enablePush`), + ré-abonnement silencieux à chaque page si permission déjà accordée. SW : handlers `push` + `notificationclick` (unifié, lit `data.url`). Stockage : table `push_subscriptions` (migration v30).
  - **Endpoints** `routes/push.py` : `GET /push/config` (clé publique + `enabled`), `POST /push/subscribe`, `POST /push/unsubscribe`. `core/push.py` : `send_push(sub, payload)` via pywebpush (retour `ok`/`expired`/`error`/`unconfigured`).
  - **Envoi** : logique unique `core/push.py:run_reactivation_push(min_days=3, max_days=30)` (hors contexte requête) → cible les inactifs 3–30 j abonnés (`db.get_inactive_user_ids`), envoie, supprime les abonnements expirés (410/404), émet l'event `reactivation_push_sent`. Deux déclencheurs :
    - **Manuel** : `POST /admin/send-reactivation` (bouton admin, inline-confirm).
    - **Cron** (2026-06-15) : `POST /tasks/reactivation` (public, CSRF-exempt, sécurisé par `CRON_SECRET` via en-tête `X-Cron-Secret` ou `?token=`, comparaison à temps constant, 401 sinon). Ou script standalone `pwa/cron_reactivation.py` (`python cron_reactivation.py`) pour un service cron Railway sans HTTP. Planifier 1×/jour.
  - **Env Railway requis** : `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` (base64url), `VAPID_SUBJECT` (`mailto:…`), `CRON_SECRET` (pour l'endpoint cron HTTP). iOS : push seulement si l'app est installée (écran d'accueil).

### Partage de progression (croissance, 2026-06-14)
- **Carte partageable** : bouton « Partager ma progression » sur l'accueil (tous les users). `static/js/share-card.js` génère côté client une image (canvas 1080×1080 : streak/tonnage/séances/exos + branding) puis la partage via l'**API Web Share** (`navigator.share({files})` si supporté → sinon texte+lien → sinon téléchargement PNG + copie du lien, avec toast). Données injectées via `<script type="application/json" id="share-data">` sur l'accueil ; lien = `location.origin` (robuste aux domaines custom).
- **Tracking** : `POST /share/track` (`routes/share.py`) → event `progress_shared` ({kind, method}). CSRF auto (header X-CSRFToken injecté par base.html).

### Upsell post-win (conversion, 2026-06-14)
- **Paywall au bon moment** : un compte **free** qui atteint `UPSELL_AFTER_SESSIONS`=3 séances distinctes voit, **une seule fois**, une modale d'invitation PRO sur l'accueil (l'écran qui suit sa séance milestone → motivation haute). Distinct de la carte « Passe en PRO » discrète toujours présente en bas d'accueil.
- Logique 100 % dans `routes/accueil.py` (pas de modif de `/seance/finish`) : flag durable `prog._upsell_seen` (méta programme, pas de migration). Event `upsell_shown` ({trigger:"post_workout", sessions}) — un `premium_viewed` qui suit = clic sur la modale (mesure de l'efficacité dans le funnel). Jamais affiché aux VIP.

### Progression
- **Calendrier mensuel** : cases colorées (vert=fait, rouge=manqué, bleu=à venir), navigation mois, taux d'assiduité, tolérance + rattrapage des séances ratées
- **Volume par semaine** : graphique SVG verrouillé (8 dernières semaines)
- **Body map** : carte musculaire SVG interactive (polygones depuis `core/body_map.py`) avec % de standard
- **Standards de force relatifs au gabarit** (`core/strength.py`) : les paliers sont des multiples du poids de corps par muscle et par sexe (bornés 35–200 kg), pas des valeurs absolues — 60 kg au développé ne veut pas dire la même chose à 55 kg qu'à 95 kg. Repli absolu si le poids est inconnu.
- **Hall of Fame** : top 3 exercices par 1RM
- **Fiche par exercice** (`/progres/exercice?nom=…`, `templates/exercice.html`, `core/exercise_stats.py`) : records, évolution par métrique (charge, volume, 1RM estimé), variantes, toutes les séances, table des RM (PRO). Courbes en **SVG maison** — Plotly (≈3 Mo depuis un CDN) a été retiré.

### Streak
- Affiché en gros sur l'accueil avec icône flamme
- Paliers : 🥉 Bronze (4 sem), 🥈 Argent (8), 🥇 Or (12), 💎 Diamant (24)
- Record personnel sauvegardé dans `prog._streak_record`
- État « en danger » (orange + pulse) si séance du jour non faite

### Mode Offline
- Bandeau « Mode hors-ligne » affiché automatiquement
- Les formulaires de séance sont interceptés et stockés dans localStorage (écoute en phase **bulle** : en phase capture, une série était mise deux fois en file)
- Synchronisation **séquentielle** au retour du réseau (`_syncing` + `step()` récursif), avec toast typé
- Badge orange « X action(s) en attente » en bas à droite
- **La séance du jour est pré-chargée** : le SW reçoit un message `PRECACHE` avec ses URLs, donc en sous-sol on ouvre sa séance au lieu d'être renvoyé sur une page d'erreur. `CACHE_VERSION` en tête de `static/service-worker.js`.

### Notifications
- **Universelles (free + PRO)** depuis 2026-06-15 : la case « Notifications de rappel & relances » dans Gestion n'est plus réservée au VIP (rétention = on veut surtout faire revenir les gratuits). Un seul contrôle : cocher la case demande la permission ET abonne au push (`handleNotifToggle` → `window.enablePush`).
- Rappels **locaux** (notifications.js) : matin (jour d'entraînement, <14 h), soir (séance non faite, ≥18 h), streak en danger (≥19 h, streak > 2). Ne se déclenchent que si l'app est ouverte.
- **Rappel de séance à l'heure choisie** (`core/reminders.py`) : réglage `_settings.reminder_hour` (6→22 h, 0 = aucun) dans Gestion. `POST /tasks/reminders` (même secret `CRON_SECRET`) est appelé **toutes les heures** par un cron externe et ne notifie que les comptes dont l'heure correspond ET qui ont une séance prévue non faite. Script équivalent : `pwa/cron_reminders.py`.
- Relances **push** de réactivation (inactifs 3–30 j) : cf. section « Push web » plus haut. Un envoi par utilisateur au maximum tous les 27 jours (`push_subscriptions.last_reactivation_at`, migration v34) — avant, un inactif recevait la même relance 27 jours d'affilée.
- Désactivable dans Gestion > Paramètres.

### Pré-lancement : sélection texte + chrono notif natif (2026-06-16)
- **Texte non sélectionnable** : `theme.css` pose `user-select:none` + `-webkit-touch-callout:none` sur `body` (supprime le menu « Rechercher sur le web » au clic long en webview Android). Réactivé sur `input/textarea/select/[contenteditable]/.selectable`. Déployé par Railway → corrige l'app native **sans rebuild**.
- **Notif de fin de repos fiable** : le chrono (`seance_edit.html`) planifiait la notif via un `setTimeout` dans le service worker → tué en arrière-plan = notif parfois manquante. Ajout de `@capacitor/local-notifications` (plugin natif) : en app native, la notif est planifiée par l'**OS** (`LocalNotifications.schedule({at})`, fiable même app fermée) ; le SW reste le fallback web. Cancel sur fin/skip (SW + natif). **Nécessite rebuild AAB.** Permission via `requestPermissions()`.
- **Compte à rebours vivant dans la barre de notification** (app native, 2026-09-24) : comme le minuteur de l'Horloge, les chiffres défilent même app fermée. `RestTimerNotification.java` pose une notification `setUsesChronometer` + `setChronometerCountDown` avec une **échéance absolue** ; c'est le SYSTÈME qui anime le compteur. Donc **aucun service en premier plan** : rien de notre code ne tourne pendant le repos, le compteur reste juste même si Android tue le processus, zéro batterie, et rien à justifier auprès de Play. Pont `window.MTTimer.start(échéance, exercice)` / `.stop()` (MainActivity), appelé par `rest-timer.js` à chaque départ de repos et reposé à la reprise (`_adopt`). **Impossible sur le web** : aucune API ne permet de faire défiler une notification — c'est la seule fonction qui justifie encore la coquille native.

### Défis hebdo (rétention, 2026-06-16)
- `core/challenges.py` : un défi **tournant** choisi par l'index de semaine continu (`continuous_week`) → identique pour tous, change chaque lundi. Évalué **depuis l'historique normalisé** (clés Date/Séance/Exercice/Poids/Reps/Semaine), aucune donnée stockée pour l'évaluation. `weekly_challenge(hist, today)` → dict {id, title, emoji, desc, current/target(+_fmt), pct, done}.
- Cycle actuel : 3 séances / 10 000 kg / nouvel exercice / 1 cardio / battre le volume de la semaine passée.
- **Accueil** (`routes/accueil.py`) : carte « Défi de la semaine » avec barre de progression. Validation consommée **uniquement sur vraie navigation** (pas prefetch) → incrémente `prog._challenges_won`, mémorise la semaine dans `prog._challenges_done`, émet l'event `challenge_completed`, affiche l'état « ✅ Défi validé ». Aucune migration.
- Suite : relance push « plus qu'1 séance pour valider », puis classement entre amis (parrainage) + objectifs perso.

### Newsletter e-mail (opt-in RGPD, 2026-06-15)
- **Consentement in-app** : case « Recevoir les nouveautés par e-mail » dans Gestion > Paramètres (universelle free + PRO). Stockée dans `profiles` (migration `supabase_schema_v31_newsletter.sql`) : `newsletter_opt_in` (bool), `newsletter_opt_in_at` (date du consentement = preuve RGPD), `newsletter_email` (e-mail du compte au moment de l'opt-in, pour l'export sans appeler l'API auth). Helpers `db.set_newsletter_optin` / `db.list_newsletter_emails` ; façade `data.set_newsletter_optin` ; enregistrée dans `gestion.update_settings` (best-effort).
- **Export** : `GET /admin/newsletter-emails` (réservé admin) → liste texte brut (un e-mail/ligne) à copier-coller dans l'outil d'emailing (**Brevo**). Lien depuis `/admin` (carte « Newsletter »).
- L'envoi des e-mails se fait **hors app** (Brevo) — l'app ne fait que collecter le consentement + fournir la liste. Les annonces *in-app* passent, elles, par le push (cf. relance).

### Accessibilité
- **Contraste** : les trois niveaux de texte (`--text-1/2/3` dans `tokens.css`) passent 4,5:1 (WCAG AA) sur le fond de page comme sur le fond de carte. `--text-3` était à 3,2:1 alors qu'il porte les en-têtes du tableau de séries et les libellés de stats — illisible en salle, luminosité baissée. `--text-disabled` reste bas exprès : un contrôle inactif n'est pas soumis au critère.
- **Cibles tactiles** (`static/css/a11y.css`, chargé en dernier donc sans `!important`) : boutons à 44 px, cases à cocher à 20 px, lignes de réglage à 44 px. Là où la mise en page l'interdit (tableau de séries, colonne monter/glisser/descendre), un pseudo-élément agrandit la surface sensible **sans toucher au visuel** ; les dimensions viennent de mesures réelles pour que deux zones voisines ne se recouvrent jamais.
- **Onboarding** : les choix sont de vrais `<input type=radio>` masqués sous l'étiquette (flèches directionnelles, annonce « 2 sur 3 »), plus des `<div @click>`.
- **Noms accessibles** : chaque contrôle a un nom annonçable (`for`/`id` quand l'étiquette existe, `aria-label` quand une boucle interdit un id unique). `tests/test_accessibilite.py` parcourt 9 pages et refuse tout contrôle muet, recalcule les contrastes, et refuse un bloc (`try { … }`) dans une directive Alpine — Alpine évalue une **expression**, un bloc lève SyntaxError en silence.
- Focus clavier visible (`:focus-visible`), lien d'évitement, `prefers-reduced-motion` global : déjà en place dans `theme.css`.

### App native : parcours d'achat
- Google Play interdit de vendre un bien numérique consommé dans l'app autrement que par Play Billing, et **un tarif affiché suffit** à tomber sous la règle. Mais cette règle ne lie que les apps **distribuées par Play** : l'APK étant installé à la main, le parcours d'achat y est visible.
- **Interrupteur `HIDE_NATIVE_BILLING`** (env, éteint par défaut) : à 1, tarifs et formulaires `/billing/*` disparaîssent du rendu natif. ⚠ **À poser sur Railway AVANT tout dépôt sur le Play Store**, sinon rejet à la revue. Les gabarits testent `hide_billing`, pas `is_native` : la condition porte sur la distribution, pas sur la plateforme.
- Détection **côté serveur** : la coquille Capacitor ajoute `MuscuTrackerApp/1` à son User-Agent (`capacitor.config.json` → `android.appendUserAgent`) ; `app.py:_is_native_app()` expose `is_native` aux gabarits, qui ne rendent alors ni tarif ni formulaire `/billing/*`. Le masquage JavaScript précédent laissait le prix dans le DOM et le temps d'apparaître.
- Filet pour une version installée sans le marqueur : `html.is-native .billing-only { display:none }` (classe posée très tôt par `base.html`).
- La page PRO explique au lieu de rester muette, et le mur de fonctionnalité dit « Voir ce que PRO apporte » plutôt que « Passer en PRO ». L'abonnement suit le compte Google : rien à « restaurer ». Le web et la PWA gardent tout le parcours.

### Export / Import
- **Gestion** : « Exporter tout » (historique + programme + profil) ou « Programme seul » — gated VIP
- **Gestion** : « Importer » un fichier JSON (avec confirmation modale) — gated VIP
- **Programme** : export/import du programme
- Format JSON, fichier nommé `muscu-tracker-backup-YYYY-MM-DD.json`

### Onboarding
- 4 étapes : Identité → Niveau → Objectif → Programme
- 19 programmes au catalogue (`core/catalog.py`), regroupés par niveau (débutant / intermédiaire / avancé)
- Cartes enrichies : icône, étoiles de difficulté, durée, muscles tags, badge Free/PRO
- Tooltips « ? » sur les niveaux, preview modale des séances avant choix
- Bouton retour fonctionnel à chaque étape

### Catalogue de programmes (19)
- Plusieurs splits : Full Body, PPL, Upper/Lower, Bro Split, Home, etc.
- Gating Free / PRO selon le programme (les programmes avancés sont VIP)

### Admin
- Routes : `/admin` (dashboard), `/admin/funnel` (conversion), `/admin/set-tier`, `/admin/user/<id>`, `/admin/reset-quota`
- Accès filtré par `ADMIN_EMAILS` env (404 sinon)

### Analytics produit / Funnel de conversion (2026-06-14)
- **Auto-hébergé sur Supabase** (table `events`, migration `supabase_schema_v28_events.sql`) — pas de tiers (PostHog/Mixpanel), donc pas de bannière de consentement ; écriture côté serveur en `service_role`.
- **Façade** : `core/analytics.py` → `track(event, props, user_id=, tier=)` **fire-and-forget** (n'échoue JAMAIS la requête, lit `g.user_id`/`g.is_vip` par défaut ; `user_id` explicite hors contexte requête = webhook Stripe). Helper `paywall(feature, status=200)` = loggue `paywall_viewed` puis rend `vip_wall.html` (centralise l'instrumentation des ~7 points de blocage VIP).
- **Events du funnel** : `onboarding_completed` (onboarding submit), `workout_finished` (séance finish), `premium_viewed` (page Premium vue par un free), `paywall_viewed` (helper `paywall`), `checkout_started` (billing checkout créé), `vip_activated` (dans `_activate_vip`, couvre success + webhook), `coach_message` (coach/ask, après quota OK).
- **Funnel** (`db.get_funnel_stats(days)`) : Inscrits (auth.users, fenêtre) → Onboarding → 1ʳᵉ séance → Offre vue → Checkout → VIP (profiles.tier). Distinct users par étape sur 7/30/90 j. Page `/admin/funnel` (lien depuis `/admin`) : barres, % du haut de funnel + conversion/déperdition vs étape précédente, + métrique annexe « Coach IA utilisé ».

## Configuration

### Variables d'environnement
- `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` — push web (relance des inactifs ; sans elles, le push est inactif et `/push/config` renvoie `enabled:false`)
- `CRON_SECRET` — secret protégeant l'endpoint cron `POST /tasks/reactivation` (relance push automatique). Sans lui, l'endpoint renvoie 401.
- `SUPABASE_URL` — URL du projet Supabase
- `SUPABASE_SERVICE_ROLE_KEY` — Clé service_role (jamais exposée au client)
- `FLASK_SECRET_KEY` — Secret pour signer les cookies de session (active aussi `SESSION_COOKIE_SECURE` en prod)
- `ANTHROPIC_API_KEY` — Clé API Claude pour le coach IA
- `ADMIN_EMAILS` — Liste séparée par virgules des emails admin
- `HIDE_NATIVE_BILLING` — à `1`, retire tarifs et boutons d'achat du rendu dans l'app native. Inutile tant que l'APK est installé à la main ; **obligatoire avant un dépôt sur le Play Store**.
- `GOOGLE_WEB_CLIENT_ID` — ID client OAuth Web Google (PUBLIC), requis par le login natif Capacitor (`login.html` → `@capgo/capacitor-social-login`). Inutile sur le web.

### Settings utilisateur (`prog._settings`)
```python
# Valeurs par défaut : routes/gestion.py:DEFAULT_SETTINGS
{
    "auto_collapse": True,        # Replier exercices terminés
    "show_1rm": True,             # Afficher estimation 1RM
    "theme_animations": True,     # Animations CSS
    "auto_rest_timer": True,      # Chrono repos auto
    "auto_prefill_weight": True,  # Pré-remplir les charges de la dernière fois
    "show_rpe": True,             # Colonne RPE dans le tableau de séries
    "show_overload_hint": True,   # Suggestion de surcharge
    "show_previous_weeks": 2,     # Semaines d'historique affichées
    "notifications": False,       # Rappels de séance
    "reminder_hour": 18,          # Heure du rappel push (6-22, 0 = aucun)
}
```

### Semaine continue (migration 2026-06-10)
- `Semaine` est un **index continu** ancré au lundi 2024-01-01 (`core/dates.py:continuous_week`), recalculé **à la lecture** depuis `Date` dans `db.get_hist()` — la colonne `semaine` stockée (n° ISO legacy) n'est plus une source de vérité.
- Les opérations ciblées (`replace_exo_rows`, `delete_exo_rows`, `delete_session_rows`) ciblent la **date exacte** (`.eq("date", date_str)`) — ni la colonne `semaine`, ni une plage lun→dim. La plage effaçait la séance précédente dès qu'on refaisait la même séance dans la semaine, ce qui concernait 9 des 20 programmes du catalogue (dont les trois programmes débutants par défaut).
- Le n° affiché à l'utilisateur reste **relatif** au début du programme (`_display_week` / `_rel_week`).
- Raison : le n° ISO recommençait chaque année → collision des données au-delà d'un an, streak/« dernière fois » cassés au Nouvel An.

### Migrations Supabase
- Le code a **toujours un repli** quand une colonne manque (upsert sans la colonne, warning loggué) : rien ne signale à l'exécution qu'une migration a été oubliée. Vérifier l'état réel par un `select exists(…)` sur `information_schema` dans le SQL Editor.
- Dernières : **v34** (session_id + rpe sur `history`, index `(user_id,date)`, table `session_notes`, `push_subscriptions.last_reactivation_at`), **v35** (`session_notes.duration_min`), **v36** (`profiles.coach_memory`).

### Tests (pwa/tests)
- `cd pwa && python -m pytest tests -q` — **293 tests** (dont 13 tests JavaScript), fausse base Supabase en mémoire (`conftest.py`, alignée sur PostgREST : les insertions renvoient les lignes écrites, PK uuid pour `coach_conversations`, **plafond `max-rows` à 1000 lignes** — sans ce plafond, aucun test ne peut repérer une lecture non paginée).
- **Tests JavaScript** : `pwa/tests/js/` — lanceur maison sous Node nu (`node tests/js/run.js`), sans npm install ni jsdom ; `harness.js` fournit un DOM/localStorage/fetch minimal. Couvre la **file hors-ligne** (ordre d'envoi, reprise après échec, session expirée, double synchronisation, phase d'écoute). `tests/test_js.py` le branche sur pytest (ignoré si Node manque).
- Fichiers : `test_routes`, `test_db_prog`, `test_data_integrity` (pagination, corps du programme, même séance 2×/semaine), `test_seance_saisie` (enregistrement JSON, records), `test_progres_exercice` (fiche exercice, standards relatifs), `test_offline_reminders` (file hors-ligne, rappels), `test_coach_stream` (SSE, mémoire), `test_debrief`, `test_nutrition_barcode`, `test_accessibilite`, `test_app_native`, `test_challenges`, `test_foods`, `test_generator`, `test_overload`.
- Le paquet `supabase` local étant cassé, conftest stubbe `sys.modules["supabase"]` avant l'import de l'app.

### Calques du jour dans le blob (`_extras`, `_libre_draft`, `_substituts`, `_seance_order`)
- Ces quatre clés rangent **une entrée par séance ET par date**. `/seance/finish` en nettoyait trois ; `_seance_order` était écrit et **jamais effacé**. Corrigé : même suppression que ses trois voisins.
- Mais effacer en fin de séance ne suffit pas : une séance **ouverte puis abandonnée** ne passe jamais par `finish`. Mesuré en production fin septembre, un `_extras` du 27 avril et un `_libre_draft` du 11 juin traînaient encore. `purger_les_calques(prog)` applique donc une fenêtre de 84 jours aux **quatre**, à chaque fin de séance.
- Limite assumée : la purge ne tourne qu'à `finish`. Quelqu'un qui n'en termine aucune ne la déclenche jamais — mais il n'y a pas d'autre point d'écriture naturel, et un nettoyage pendant un GET serait pire (cf. N4).
- `_purger_calque(prog, cle, today, jours)` sert aussi aux bilans : une seule règle à retenir. `tests/test_calques_bornes.py` la tient pour les quatre.

### Ce que le blob pèse vraiment (mesuré le 2026-09-28)
- **25,9 ko pour 15 programmes, soit 1,7 ko en moyenne.** Dont **15,9 ko de séances** — le programme lui-même, pas de la dette. Les ~10 ko de clés `_x` se répartissent sur 15 comptes.
- La plus grosse clé `_x` est `_planning` (1,8 ko cumulés, 197 o au pire). Aucune n'approche le kilo-octet par utilisateur.
- **Conclusion : le blob n'est pas un problème de taille.** Le sortir pour des raisons de performance ne se justifie pas par les chiffres. Les défauts qu'il a causés (écrasements silencieux) sont traités par le verrou optimiste et `replace_program_body`. Ce qui reste est un problème de *forme* — rien ne s'y interroge — pas de poids.
- Ce que la mesure a réellement trouvé : des calques de séances abandonnées vieux de cinq mois (voir ci-dessus). Petit en octets, réel en nature.

### Mesurer le blob avant d'en sortir quoi que ce soit
- **`/admin/blob`** (protégée par `ADMIN_EMAILS`, 404 sinon) donne le poids de chaque clé `_x`, le nombre d'entrées de chaque calque et leur plus vieille date. C'est le chemin à privilégier : la mesure se fait **là où vit la clé `service_role`**, chez l'hébergeur, au lieu de la rapatrier.
- `python tools/analyse_blob.py` (depuis `pwa/`) donne le même rapport en ligne de commande, si `SUPABASE_URL` et `SUPABASE_SERVICE_ROLE_KEY` sont dans l'environnement ; en variables **utilisateur** Windows, les passer par `$env:X = [Environment]::GetEnvironmentVariable('X','User')`.
- Le calcul vit dans `core/blob_stats.py` et ne touche ni à Flask ni à la base : on lui passe les blobs déjà lus. **Lecture seule** et **aucun contenu imprimé** — que des noms de clés, des tailles et des comptages, donc un rapport se colle sans y réfléchir. Les tests visent le vrai chemin de lecture (`list_all_program_blobs` et la vue `blob`), vérifient que la détection d'écriture voit réellement une écriture, et que la page ne laisse fuir ni nom de séance ni identifiant.
- Les 29 clés `_x` (27 au second audit) se répartissent en trois familles : **structurelles** (le programme lui-même : `_profiles`, `_programmes`, `_seance_prog`, `_custom_exercises`, `_cardio`), **bornées** (`_planning`, `_settings`, `_started_at`…) et **croissantes** (les calques, `_archive`, `_legacy_volume`, `_meal_plan`, les défis et badges). Seules les dernières justifient d'être sorties, et l'outil dit lesquelles pèsent vraiment.

### Poids de /programme (313 → 241 ko)
- Le détail des vingt programmes du catalogue (chaque séance, chaque exercice) était rendu **côté serveur** derrière un `x-show` : **88 ko, 28 % de la page**, en double du JSON `#catalog-data` qui portait déjà les mêmes données et que la page chargeait de toute façon. Il est rendu à l'ouverture par `detailSeances(id)`.
- Effet mesuré : **313 → 241 ko** et **1 280 → 406** attributs `style=`. Les styles répétés sont devenus des classes (`.catalog-detail*` dans `components.css`), rendu identique vérifié propriété par propriété dans le navigateur.
- `tests/test_poids_programme.py` tient un plafond de 260 ko et interdit le retour de la boucle Jinja.

### Variables CSS mortes
- `var(--x)` vers un token non défini **et sans repli** ne dessine rien : la déclaration entière devient invalide, sans erreur. `--border-subtle` est dans ce cas : **18 fois dans six gabarits, défini nulle part** — 244 bordures demandées et jamais dessinées sur la seule page /programme.
- Quatre autres tokens absents (`--bg-input`, `--sp-2`, `--sp-3`, `--border-strong`) portent tous un repli à chaque usage : eux s'affichent.
- `tests/test_variables_css.py` fige la liste : aucun nouveau token mort, et un token enfin défini doit en sortir.

### Découpage de la couche données (core/db*.py)
- `core/db.py` faisait 1 705 lignes et mélangeait dix sujets. Il est devenu une **façade sans code** : docstring, commentaires, imports. Les routes écrivent toujours `from core import db as core_db` et ne voient pas le découpage.
- Les dépendances entre modules forment un **arbre** : tous s'appuient sur `db_base` ; `db_abonnement`, `db_admin` et `db_push` lisent le profil ; `db_push` et `db_bilans` normalisent une date avec l'historique. Aucun cycle.
- Le client Supabase n'existe que dans `db_base`. Les tests et `run_local_fake.py` le remplacent par `use_client(faux)` et le relisent par `current_client()` — une affectation directe sur `core.db._client` ne serait plus lue, et `_client` n'est volontairement **pas** réexporté pour que la tentative échoue bruyamment.
- `tests/test_couche_donnees.py` tient ces propriétés : façade complète, façade sans code, plafond de 400 lignes par module, absence de cycle, client unique, carte à jour.

### Découpage de la séance (routes/seance.py → core/seance_*.py)
- `routes/seance.py` faisait **1 685 lignes**. Les deux tiers ne touchaient ni à Flask ni à la base : c'était du calcul rangé dans la couche HTTP, inexerçable sans monter une requête. **36 fonctions** (690 lignes) sont parties dans six modules `core/seance_*.py` ; il reste **930 lignes** de routes.
- Les six modules sont **purs** : on leur passe l'historique et le programme, ils rendent des dictionnaires. Aucun n'importe `flask`, `core.data`, `core.db` ni `core.limiter` — un test le vérifie module par module.
- `routes/accueil.py` importait `_display_week` depuis `routes/seance.py`. Il le prend maintenant dans `core/seance_semaine.py`. **Neuf autres imports entre blueprints subsistent** (mesurés), dont quatre vers `routes/cardio.py` — un module de calcul qui porte un chapeau de blueprint. `tests/test_couche_seance.py` fige la liste : elle ne peut plus grossir sans qu'un test tombe.
- Les noms gardent leur préfixe `_` : le déplacement a été fait sans en renommer un seul, pour que chaque corps de fonction reste comparable au caractère près à l'original (vérifié : 55 fonctions sur 55 identiques).

### Coût d'un affichage de /accueil
- Mesuré avec un an d'entraînement (1 872 séries) : **8 requêtes Supabase**, dont le **programme trois fois**. La page pouvait le sauvegarder **jusqu'à quatre fois** en un seul affichage (badges, record de streak, bandeau PRO, défi gagné), chacune relisant et réécrivant tout le blob sous verrou optimiste. Les quatre posent désormais un drapeau et **une seule écriture** les porte : 8 → 7 requêtes.
- `_compute_badges` ne persiste plus rien : elle calcule, la vue décide d'écrire. Une fonction de calcul qui sauvegarde était la raison pour laquelle l'une des quatre écritures passait inaperçue.
- Reste à traiter : `get_hist()` lit **tout** l'historique (1 872 lignes, 2 pages PostgREST) pour afficher une semaine. Le streak et les badges ont besoin de dates et d'agrégats, pas de lignes complètes.
- `tests/test_cout_accueil.py` tient le compte : une sauvegarde au plus, et ce qu'elle porte (badges, streak) n'est pas perdu.

### Quota de requêtes dans les tests
- Le limiteur est **process-wide** et compte par route : les 60 requêtes/minute de `/accueil` étaient partagées par TOUS les tests d'une exécution. Ajouter huit tests sur cette page a suffi à faire tomber **trois tests voisins** en 429 — un échec qui désigne le mauvais coupable.
- `conftest.quota_neuf` (autouse) remet le compteur à zéro avant chaque test. Le limiteur reste **activé** : un test qui veut vérifier qu'une route se bride envoie sa propre rafale. `tests/test_quota_des_tests.py` prouve l'isolation.

### Lecture paginée (core/db_base.py)
- PostgREST plafonne silencieusement les réponses à `max-rows` (1000). Un historique dépassant ce seuil était **tronqué sans erreur**, et une réécriture ultérieure figeait la troncature dans la base. Toutes les lectures de listes passent par `_fetch_all(build)`, qui enchaîne les pages via `.range()` jusqu'à épuisement.

### Prédicats d'historique (core/hist.py)
- `is_perf(row)` : au moins une répétition **ou** une charge. Le poids seul ne peut pas servir de critère — pompes, tractions et gainage sont à 0 kg, et toutes les vues qui exigeaient `Poids > 0` ignoraient purement et simplement les séances au poids du corps (streak, compteur de séances, défis).
- Une seule définition partagée par l'accueil, les progrès, les défis et le debrief : avant, chaque vue avait la sienne.

### Cache mémoire (core/db_base.py)
- TTL : 60 secondes, LRU borné à 200 entrées (`_CACHE_MAX`)
- Invalidé immédiatement après chaque `save_prog()` et `save_hist()`
- Clés : `hist:{user_id}`, `prog:{user_id}`, `profile:{user_id}`

### Verrou optimiste sur `programs.data` (core/db_programme.py, migration v32)
- 2 workers gunicorn × cache 60 s → deux requêtes peuvent partir du même blob et s'écraser. `save_prog()` fait donc `update … eq(user_id).eq(version)` ; si 0 ligne touchée, relecture + `_merge_prog()` (fusion 3 voies par clé : seules NOS clés modifiées sont réappliquées sur la version DB), 3 tentatives, puis upsert brut loggué en `error`.
- Base de comparaison = dernier `get_prog()` du process (`_prog_base`). Sans lecture préalable ou sans colonne `version` (migration pas appliquée) → upsert comme avant.
- `_session_notes` (bilans de séance) : fenêtre glissante de 84 jours purgée à chaque `/seance/finish` (`routes/seance.py`), comme `_extras`/`_libre_draft`.
- **`replace_program_body(old, body)`** + `PROG_BODY_KEYS` : l'autosave du programme envoie le corps (séances, planning, cardio…) et **conserve** toutes les autres clés personnelles (`_settings`, `_streak_record`, `_meal_plan`, `_challenges_won`…). Avant, une seule liste blanche recopiait 3 clés sur 11 : un autosave effaçait les réglages, le record de streak et les plats de la semaine. Toute clé personnelle reçue dans le corps est ignorée et loggée.

### Suggestion de surcharge (core/muscu.py → routes/seance.py)
- `overload_suggestion(last_sets, prev_sets, is_bw)` : double progression simplifiée. RPE moyen ≥ 9,5 → « Consolide » ; même charge partout ET (≥ 12 reps, ou ≥ 8 reps avec RPE ≤ 8, ou ≥ 8 reps deux séances de suite sans régression) → « Monte à X kg » (+2,5 kg ≥ 30 kg, +1 kg en dessous) ; sinon « Même charge, vise N+1 reps ». Le RPE est lu depuis le token `@RPE8` de la remarque.
- Affichée sous « Dernière fois » (bouton Appliquer = pré-remplit la charge sur les séries vides ; reps cibles en placeholder). Réglage `_settings.show_overload_hint` (Gestion). Recalculée par `/seance/api/variant-history`.

### Base d'aliments (core/foods_data.py → nutrition.html)
- `FOODS` (liste de dicts `{n, k, p, c, f, g, r, u}` : nom, kcal/prot/gluc/lip pour 100 g, catégorie, rang, portions `[[libellé, grammes]]`) est embarquée dans la page (`var FOODS = {{ foods|tojson }}`, ~27 Ko) ; la recherche est 100 % côté client (normalisation sans accents, tous les mots doivent matcher, début de mot > milieu, aliments simples avant plats/snacks `r=1`).
- Mode « Aliments » (par défaut) du formulaire repas : panier `basket` (qty × portion) → totaux → POST `/nutrition/add-meal` classique, note = « Banane 120 g, Riz blanc cuit 180 g ». Pour ajouter un aliment : une ligne dans `FOODS_RAW` (une chaîne seule = titre de catégorie).

### Poids corporel (migration v33, routes/progres.py)
- Table `body_weight` (user_id, date, poids_kg), une pesée / jour (upsert `on_conflict=user_id,date`). Carte gratuite dans Progrès : courbe SVG 90 j, variation 30 j (couleur selon `objectif_nutrition`), min/max, saisie + suppression.
- Après chaque pesée/suppression, `_sync_profile_weight()` recopie la dernière pesée dans `profiles.poids_kg` et recalcule `tdee` / `calories_cible` (helpers de `routes/nutrition.py`). Le formulaire profil Nutrition crée aussi une pesée du jour. Export/import JSON : clé `poids`.

### Rate limiting (core/limiter.py)
- Default : 60 req/min par IP (mémoire process)
- Sur-limites ajoutées via `@limiter.limit(...)` sur les actions sensibles

## Thème (refonte UI dark minimal — style Strong / Hevy)
- Background : `#0a0a0f` (`--bg-base`, repris par `theme-color` dans `base.html`)
- Tokens dans `static/css/tokens.css` (palette, espacements, radius)
- Accent : bleu doux ; Gold pour VIP ; rouge pour danger
- Icônes : sprite SVG `static/img/icons.svg` consommé via `<svg><use href="/static/img/icons.svg#name"/></svg>`
- Font : système (sans-serif)

## Intégration continue
- `.github/workflows/tests.yml` — à chaque push sur `main` et sur chaque PR : `pytest` (306) puis `node tests/js/run.js` (31), sur **Python 3.11** comme en production. Une étape refuse de démarrer si `runtime.txt` et le workflow ne sont plus d'accord sur la version.
- Les dépendances sont installées depuis `requirements.txt` **tel quel** : une dépendance oubliée fait échouer la CI au lieu du serveur.
- La suite JS a **sa propre étape** : `tests/test_js.py` s'ignore quand Node est absent, et un test ignoré passerait pour un succès.
- ⚠ **C'est un signal, pas encore une barrière.** Railway déploie depuis `main` sans attendre. Pour bloquer un déploiement quand la CI échoue : Railway → service → Settings → Source → **Wait for CI**.

## Git
- **Branche unique** : `main` — tout commit/push se fait ici, Railway redéploie automatiquement
- **Pas de branches de feature**
- Auteur : `morauxpaul-jpg <morauxpaul@users.noreply.github.com>`
- Flags requis : `-c user.name="morauxpaul-jpg" -c user.email="morauxpaul@users.noreply.github.com"`
- **CACHE_VERSION** : plus besoin de la bumper à chaque déploiement. La route `/service-worker.js` (`app.py`) suffixe la base (`v123` en tête de `pwa/static/service-worker.js`) avec les 8 premiers caractères de `RAILWAY_GIT_COMMIT_SHA` → chaque déploiement invalide le cache du SW automatiquement. Bumper la base uniquement pour forcer un refresh en local ou si l'APP_SHELL change.

## Conventions UI / UX
- **Jamais** de `prompt()`, `confirm()`, `alert()` natifs — toujours modal in-app ou inline-confirm
- **Inline-confirm** doit rester dans la carte qui le déclenche (programme/séance)
- Page de plomberie (`/admin`, `/auth/debug`) : pas de nav bottom, retour explicite
