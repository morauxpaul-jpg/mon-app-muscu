# Muscu Tracker PRO — CONTEXT.md

## Architecture

PWA Flask (Python) avec Supabase (PostgreSQL) en backend, déployée sur Railway depuis `main`.
- **Framework** : Flask avec Blueprints + Flask-Limiter (rate limiting)
- **Frontend** : Jinja2 templates + Alpine.js + CSS custom (refonte UI dark minimal style Strong/Hevy)
- **Auth** : Supabase Google OAuth → bridge JWT → session Flask (cookie 30 jours)
- **Data** : Supabase tables (history, programs, profiles, onboarding, nutrition, coach_messages) via `service_role` key
- **PWA** : Service Worker (Network First), manifest.json, offline support
- **IA** : Coach via API Anthropic (Claude Haiku 4.5)
- **Coquille native** : Capacitor (`android/`, `capacitor.config.json` à la racine) — webview sur l'URL de prod + plugin AdMob. Pubs (Free uniquement, app native uniquement) : `pwa/static/js/ads.js`, IDs via env `ADMOB_BANNER_ID`/`ADMOB_INTERSTITIAL_ID`. Docs : `docs/CAPACITOR.md` + `docs/PLAY_STORE.md`. Login Google natif **branché côté code** (2026-06-15) : `login.html` détecte Capacitor → `@capgo/capacitor-social-login` (idToken + nonce) → `supabase.auth.signInWithIdToken` → `/auth/session` (OAuth webview interdit, 403 disallowed_useragent). Reste à faire côté toi : env `GOOGLE_WEB_CLIENT_ID` + ID client OAuth Android (SHA-1) dans Google Cloud + test sur téléphone (voir CAPACITOR.md).

## Structure des fichiers

```
pwa/
├── app.py                         # Flask app, blueprints, auth gate (g.user_id, g.is_vip), landing
├── compress_icon.py               # Script utilitaire (compression PNG)
├── generate_icons.py              # Script de génération des icônes app
├── rebuild_program_from_history.py# Script de reconstruction d'un programme depuis l'historique
├── supabase_schema_v23.sql        # Schémas SQL Supabase (versions successives)
├── supabase_schema_v24.sql
├── supabase_schema_v25_vip.sql    # Ajout colonnes tier/quota VIP
├── core/
│   ├── db.py                      # Accès Supabase (service_role), cache mémoire TTL 60s
│   ├── data.py                    # Façade Flask (lit user_id depuis flask.g) + helpers nutrition/coach
│   ├── dates.py                   # Helpers dates (timezone Paris), DAYS_FR, MONTHS_FR
│   ├── muscu.py                   # Logique muscu (1RM, muscles, base_name)
│   ├── catalog.py                 # Catalogue de 19 programmes prédéfinis (onboarding)
│   ├── exercises_data.py          # Fiches exercices : matériel requis + substitutions
│   ├── body_map.py                # Polygones SVG du body map (d'après react-body-highlighter)
│   ├── limiter.py                 # Instance Flask-Limiter partagée (60 req/min par IP)
│   ├── analytics.py               # Façade track(event,props) fire-and-forget + helper paywall() (funnel conversion)
│   └── sheets.py                  # Connexion Google Sheets (compat ancien backend Streamlit)
├── routes/
│   ├── auth.py                    # Login Google, bridge JWT, logout, /auth/debug
│   ├── accueil.py                 # Dashboard (/accueil) — planning hebdo, streak, "Prochaine séance"
│   ├── seance.py                  # Séance du jour (saisie, skip, reset, finish, ajout cardio inline)
│   ├── programme.py               # CRUD programme + profils + planning + import/export
│   ├── progres.py                 # Progression — body map, calendrier, volume, zoom mouvement
│   ├── gestion.py                 # Paramètres, settings, export/import, reset soft/total
│   ├── arcade.py                  # Mini-jeux
│   ├── onboarding.py              # Questionnaire post-login (recommend, submit)
│   ├── cardio.py                  # Saisie cardio (chrono + distance + cal + RPE) → table history
│   ├── nutrition.py               # Profil métabolique (Mifflin-St Jeor) + journal repas
│   ├── coach.py                   # Chat IA (Claude Haiku 4.5), réservé VIP, quota 15 msg/jour
│   ├── premium.py                 # Page de présentation des tiers (pré-paywall)
│   ├── generator.py               # Générateur de programme IA (VIP) — Claude → JSON validé → save_prog
│   ├── share.py                   # POST /share/track — compteur de partages de progression (analytics)
│   ├── parrainage.py              # Lien d'invitation + récompense VIP (parrain/filleul) + apply_referral
│   └── admin.py                   # Stats, gestion VIP, fiche user (gated par ADMIN_EMAILS env)
├── templates/
│   ├── base.html                  # Layout master (topbar, nav 4 onglets, scripts globaux)
│   ├── _icons.html                # (inclus si présent) sprite SVG
│   ├── _body_map_svg.html         # SVG carte musculaire (inclus dans progres)
│   ├── _programme_seance_card.html# Partial : carte séance dans /programme
│   ├── partials/
│   │   └── vip_lock.html          # Cadenas / mur VIP réutilisable
│   ├── landing.html               # Page publique (/)
│   ├── login.html                 # Page login Google
│   ├── bridge.html                # Bridge OAuth → session Flask
│   ├── accueil.html               # Dashboard
│   ├── seance_choix.html          # Choix de séance du jour
│   ├── seance_edit.html           # Saisie exercices (Alpine, timer, inline history)
│   ├── programme.html             # Gestion programme + profils + planning
│   ├── progres.html               # Progression (body map, calendrier, volume, zoom)
│   ├── gestion.html               # Paramètres, export/import, reset, notifications
│   ├── plus.html                  # Hub : Premium, Coach, Programme, Nutrition, Cardio, Arcade, Gestion, Tutoriel
│   ├── premium.html               # Page de présentation des tiers
│   ├── coach.html                 # Chat IA
│   ├── generator.html             # Générateur de programme IA (form + preview + adopter)
│   ├── cardio.html                # Saisie cardio
│   ├── nutrition.html             # Profil + journal repas
│   ├── arcade.html                # Mini-jeux canvas
│   ├── onboarding.html            # Questionnaire 4 étapes (Alpine)
│   ├── admin.html                 # Console admin
│   ├── funnel.html                # Funnel de conversion admin (étapes + déperdition, 7/30/90j)
│   ├── vip_wall.html              # Mur de blocage VIP plein écran
│   └── error.html                 # Page d'erreur
├── static/
│   ├── css/
│   │   ├── tokens.css             # Design tokens (couleurs, espacements, radius…)
│   │   ├── theme.css              # Variables, animations, composants globaux
│   │   ├── components.css         # Cards, stats, grids, boutons
│   │   ├── icons.css              # Tailles et couleurs d'icônes (.icon, .icon-sm, .icon-accent…)
│   │   ├── timer.css              # Styles spécifiques au chrono de repos
│   │   └── tutorial.css           # Overlay tutoriel
│   ├── js/
│   │   ├── alpine.min.js          # Alpine.js bundlé localement
│   │   ├── sw-register.js         # Enregistrement SW + auto-update
│   │   ├── offline.js             # Détection hors-ligne, queue localStorage, sync
│   │   ├── notifications.js       # Rappels quotidiens (API Notification)
│   │   ├── tutorial.js            # Tutoriel spotlight interactif
│   │   ├── tuto-seance.js         # Tutoriel saisie de séance (1ère ouverture)
│   │   ├── ui-fx.js               # Effets UI (toasts, micro-animations)
│   │   ├── prefetch.js            # Prefetch des pages clés
│   │   └── exercise-library.js    # Bibliothèque d'exercices (search/picker)
│   ├── img/
│   │   ├── icons.svg              # Sprite SVG (lucide-like) référencé via <use href="…#name"/>
│   │   └── exercises/             # 18 SVG illustrations exercices
│   ├── changelog.json             # Notes de version (patch notes modal)
│   ├── service-worker.js          # SW : Network First, CACHE_VERSION en tête de fichier
│   ├── manifest.json              # PWA manifest
│   ├── manifest.webmanifest       # Variante webmanifest
│   ├── icon-192.png               # Icône app 192×192
│   └── icon-512.png               # Icône app 512×512
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
- **Paiement Stripe** (`routes/billing.py`) : Checkout (prix inline `price_data`, pas d'ID à pré-créer) pour mensuel 4,99€ / annuel 39,99€ / lifetime 79,99€. Webhook `/billing/webhook` (public + CSRF-exempt, signé) = source de vérité du tier ; `/billing/success` active aussi le VIP en filet ; `/billing/portal` = gestion/annulation. Boutons masqués dans l'app native (règle stores, détection Capacitor). Env : `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`. Migration : `supabase_schema_v27_stripe.sql` (colonne `profiles.stripe_customer_id`).
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

### Cardio
- Activités : Course, Vélo, Rameur, Natation, Corde, HIIT, Marche (avec MET pour estimation calories)
- Stockage dans la même table `history` (Exercice = `CARDIO:Type`, Reps = minutes, Poids = km, Remarque = `FC:… | Cal:… | RPE:…`, Muscle = `Cardio`)

### Nutrition
- Profil métabolique : BMR Mifflin-St Jeor, TDEE × facteur d'activité (5 niveaux : sédentaire → athlète)
- Objectif calorique ajusté selon objectif (Masse / Maintien / Sèche), macros recommandés en %
- Table Supabase `nutrition` : un repas par ligne (date, meal_type, macros, note)

### Coach IA
- Modèle : `claude-haiku-4-5-20251001`, max 500 tokens
- Accès réservé VIP (mur `vip_wall.html` pour les free)
- Quota VIP : 15 msg/jour (champs `profiles.coach_quota_date` + `coach_quota_count`, reset auto à chaque nouveau jour) — protège le coût API
- Historique conversation persisté dans `coach_messages`, effaçable via `/coach/clear`
- Le system prompt inclut le profil utilisateur, le programme, et l'historique récent

### Générateur de programme IA (VIP, 2026-06-14)
- **Route** `routes/generator.py` : `GET /generator` (form, VIP-gated via `paywall`), `POST /generator/generate` (prompt structuré → Claude Haiku 4.5, `max_tokens=2600` → **JSON strict** → `parse_and_validate`), `POST /generator/apply` (re-validation + `save_prog`, même chemin sûr que l'import ; reps NON persistées, cf. semaine continue).
- **`parse_and_validate(raw)`** = fonction **pure** (testée, `tests/test_generator.py`) : tolère les blocs ``` ```json ```, normalise les muscles (vers `MUSCLES` canoniques, défaut « Autre »), clamp sets 1–8, ≤6 séances / ≤12 exos, planning FR filtré + fallback cyclique.
- **Anti-coût** : quota 3/semaine glissante (7 j) / VIP via la table `events` (compte les `program_generated` des 7 derniers jours, `_gen_used_week`) + backstop Flask-Limiter `10/h` sur generate, `20/h` sur apply.
- **Prompt** : injecte la liste des exercices connus (`EXERCISES_INFO`) pour biaiser vers des exos illustrés + la liste des muscles canoniques.
- **Events** : `program_generator_viewed`, `program_generated`, `program_adopted` (nourrissent aussi le funnel). **Entrée UI** : carte « Générateur IA » dans le hub Plus (section Premium, cadenas si free).

### Parrainage (croissance, 2026-06-14)
- **Boucle** : chaque user a un `profiles.referral_code` (stable, dérivé de l'user_id) → lien `/?ref=CODE`. Page **/parrainage** (hub Plus) : lien + copier + partager (Web Share) + compteur de filleuls/jours gagnés.
- **Capture** : la landing pose un cookie `pending_ref` (survit au round-trip OAuth). À l'onboarding du filleul, `parrainage.apply_referral` crédite **une seule fois** : filleul **+1 j essai**, parrain **+3 j essai** (via `db.grant_vip_days` → `vip_until` cumulatif). L'essai = accès **restreint** (Nutrition + stats, cf. `is_vip_full`). Garde-fous : code valide, pas d'auto-parrainage, `referred_by` posé une seule fois. Le filleul passe en essai immédiatement (`session.pop('is_vip'/'is_vip_full')`) ; le parrain via la revalidation FREE (15 s). Récompenses ajustables : `REFERRER_VIP_DAYS` / `REFEREE_VIP_DAYS` dans `routes/parrainage.py`.
- **Migration** : `supabase_schema_v29_referral.sql` (`profiles` += `referral_code` [unique], `referred_by`, `vip_until`). Helpers `db.py` : `get_or_create_referral_code`, `get_user_by_referral_code`, `set_referred_by`, `grant_vip_days`, `count_referrals`, `get_referred_by`, `vip_until_active`. Events : `referral_shared`, `referral_signup`.

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
- **Hall of Fame** : top 3 exercices par 1RM
- **Zoom mouvement** : évolution par semaine (Plotly)

### Streak
- Affiché en gros sur l'accueil avec icône flamme
- Paliers : 🥉 Bronze (4 sem), 🥈 Argent (8), 🥇 Or (12), 💎 Diamant (24)
- Record personnel sauvegardé dans `prog._streak_record`
- État « en danger » (orange + pulse) si séance du jour non faite

### Mode Offline
- Bandeau « Mode hors-ligne » affiché automatiquement
- Les formulaires de séance sont interceptés et stockés dans localStorage
- Synchronisation automatique au retour de la connexion avec toast
- Badge orange « X action(s) en attente » en bas à droite
- Pages principales en cache SW (accueil, séance)

### Notifications
- **Universelles (free + PRO)** depuis 2026-06-15 : la case « Notifications de rappel & relances » dans Gestion n'est plus réservée au VIP (rétention = on veut surtout faire revenir les gratuits). Un seul contrôle : cocher la case demande la permission ET abonne au push (`handleNotifToggle` → `window.enablePush`).
- Rappels **locaux** (notifications.js) : matin (jour d'entraînement, <14 h), soir (séance non faite, ≥18 h), streak en danger (≥19 h, streak > 2). Ne se déclenchent que si l'app est ouverte.
- Relances **push** (app fermée) : cf. section « Push web » plus haut.
- Désactivable dans Gestion > Paramètres.

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
- `GOOGLE_WEB_CLIENT_ID` — ID client OAuth Web Google (PUBLIC), requis par le login natif Capacitor (`login.html` → `@capgo/capacitor-social-login`). Inutile sur le web.

### Settings utilisateur (`prog._settings`)
```python
{
    "auto_collapse": True,      # Replier exercices terminés
    "show_1rm": True,           # Afficher estimation 1RM
    "theme_animations": True,   # Animations CSS
    "auto_rest_timer": True,    # Chrono repos auto
    "show_previous_weeks": 2,   # Semaines d'historique affichées
    "notifications": False,     # Rappels de séance
}
```

### Semaine continue (migration 2026-06-10)
- `Semaine` est un **index continu** ancré au lundi 2024-01-01 (`core/dates.py:continuous_week`), recalculé **à la lecture** depuis `Date` dans `db.get_hist()` — la colonne `semaine` stockée (n° ISO legacy) n'est plus une source de vérité.
- Les opérations ciblées (`replace_exo_rows`, `delete_exo_rows`, `delete_session_rows`) ciblent la semaine par **plage de dates lun→dim** dérivée du paramètre `date_str` — jamais par la colonne `semaine`.
- Le n° affiché à l'utilisateur reste **relatif** au début du programme (`_display_week` / `_rel_week`).
- Raison : le n° ISO recommençait chaque année → collision des données au-delà d'un an, streak/« dernière fois » cassés au Nouvel An.

### Tests (pwa/tests)
- `cd pwa && python -m pytest tests -q` — fake Supabase en mémoire (conftest), couvre passage d'année, remplacement de séries, suppression de compte, validation import.
- Le paquet `supabase` local étant cassé, conftest stubbe `sys.modules["supabase"]` avant l'import de l'app.

### Cache mémoire (core/db.py)
- TTL : 60 secondes
- Invalidé immédiatement après chaque `save_prog()` et `save_hist()`
- Clés : `hist:{user_id}`, `prog:{user_id}`, `profile:{user_id}`

### Rate limiting (core/limiter.py)
- Default : 60 req/min par IP (mémoire process)
- Sur-limites ajoutées via `@limiter.limit(...)` sur les actions sensibles

## Thème (refonte UI dark minimal — style Strong / Hevy)
- Background : `#111318` (dark slate, défini via `theme-color`)
- Tokens dans `static/css/tokens.css` (palette, espacements, radius)
- Accent : bleu doux ; Gold pour VIP ; rouge pour danger
- Icônes : sprite SVG `static/img/icons.svg` consommé via `<svg><use href="/static/img/icons.svg#name"/></svg>`
- Font : système (sans-serif)

## Git
- **Branche unique** : `main` — tout commit/push se fait ici, Railway redéploie automatiquement
- **Pas de branches de feature**
- Auteur : `morauxpaul-jpg <morauxpaul@users.noreply.github.com>`
- Flags requis : `-c user.name="morauxpaul-jpg" -c user.email="morauxpaul@users.noreply.github.com"`
- **CACHE_VERSION** : `v112-2026-06-15-notifs-universelles` (incrémenter à chaque déploiement, en tête de `pwa/static/service-worker.js`)

## Conventions UI / UX
- **Jamais** de `prompt()`, `confirm()`, `alert()` natifs — toujours modal in-app ou inline-confirm
- **Inline-confirm** doit rester dans la carte qui le déclenche (programme/séance)
- Page de plomberie (`/admin`, `/auth/debug`) : pas de nav bottom, retour explicite
