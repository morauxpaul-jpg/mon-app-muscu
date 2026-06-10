# Muscu Tracker PRO — CONTEXT.md

## Architecture

PWA Flask (Python) avec Supabase (PostgreSQL) en backend, déployée sur Railway depuis `main`.
- **Framework** : Flask avec Blueprints + Flask-Limiter (rate limiting)
- **Frontend** : Jinja2 templates + Alpine.js + CSS custom (refonte UI dark minimal style Strong/Hevy)
- **Auth** : Supabase Google OAuth → bridge JWT → session Flask (cookie 30 jours)
- **Data** : Supabase tables (history, programs, profiles, onboarding, nutrition, coach_messages) via `service_role` key
- **PWA** : Service Worker (Network First), manifest.json, offline support
- **IA** : Coach via API Anthropic (Claude Haiku 4.5)

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
│   ├── cardio.html                # Saisie cardio
│   ├── nutrition.html             # Profil + journal repas
│   ├── arcade.html                # Mini-jeux canvas
│   ├── onboarding.html            # Questionnaire 4 étapes (Alpine)
│   ├── admin.html                 # Console admin
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

- **Tier** stocké dans `profiles.tier` ∈ {`free`, `vip`}. Lu et caché en session via `g.is_vip`.
- **Gating Free** : Coach IA (réservé VIP, 15 msg/jour), Export/Import, certains programmes du catalogue, stats avancées.
- **Mur VIP** : `templates/partials/vip_lock.html` (inline) ou `vip_wall.html` (plein écran).
- **Badge PRO** affiché dans la topbar pour les VIP.
- **Admin** (`ADMIN_EMAILS` env, séparateur virgule) peut basculer manuellement le tier d'un user via `/admin/set-tier`.

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
- Permission demandée après 5 s au premier login
- Rappel matin (jour d'entraînement, <14 h)
- Rappel soir (séance non faite, ≥18 h)
- Alerte streak en danger (≥19 h, streak > 2)
- Désactivable dans Gestion > Paramètres

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
- Routes : `/admin` (dashboard), `/admin/set-tier`, `/admin/user/<id>`, `/admin/reset-quota`
- Accès filtré par `ADMIN_EMAILS` env (404 sinon)

## Configuration

### Variables d'environnement
- `SUPABASE_URL` — URL du projet Supabase
- `SUPABASE_SERVICE_ROLE_KEY` — Clé service_role (jamais exposée au client)
- `FLASK_SECRET_KEY` — Secret pour signer les cookies de session (active aussi `SESSION_COOKIE_SECURE` en prod)
- `ANTHROPIC_API_KEY` — Clé API Claude pour le coach IA
- `ADMIN_EMAILS` — Liste séparée par virgules des emails admin

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
- **CACHE_VERSION** : `v87-2026-06-10-semaine-continue` (incrémenter à chaque déploiement, en tête de `pwa/static/service-worker.js`)

## Conventions UI / UX
- **Jamais** de `prompt()`, `confirm()`, `alert()` natifs — toujours modal in-app ou inline-confirm
- **Inline-confirm** doit rester dans la carte qui le déclenche (programme/séance)
- Page de plomberie (`/admin`, `/auth/debug`) : pas de nav bottom, retour explicite
