# Muscu Tracker PRO — CONTEXT.md

## Architecture

PWA Flask (Python) avec Supabase (PostgreSQL) en backend.
- **Framework** : Flask avec Blueprints
- **Frontend** : Jinja2 templates + Alpine.js + CSS custom (thème cyber/RPG dark + bleu néon)
- **Auth** : Supabase Google OAuth → bridge JWT → session Flask
- **Data** : Supabase tables (history, programs, profiles, onboarding) via `service_role` key
- **PWA** : Service Worker (Network First), manifest.json, offline support

## Structure des fichiers

```
pwa/
├── app.py                    # Flask app, blueprints, auth gate, landing, /plus
├── core/
│   ├── db.py                 # Accès Supabase (service_role), cache mémoire TTL 60s
│   ├── data.py               # Façade Flask (lit user_id depuis flask.g)
│   ├── dates.py              # Helpers dates (timezone Paris)
│   ├── muscu.py              # Logique muscu (1RM, muscles, base_name)
│   ├── catalog.py            # Catalogue programmes prédéfinis (onboarding)
│   └── exercises_data.py     # Fiches info exercices (muscles, exécution, conseils)
├── routes/
│   ├── auth.py               # Login, bridge JWT, logout
│   ├── accueil.py            # Dashboard (/accueil), planning hebdo, streak
│   ├── seance.py             # Séance du jour (/seance, /seance/edit/...)
│   ├── programme.py          # CRUD programme (/programme)
│   ├── progres.py            # Progression (/progres), body map, calendrier, volume
│   ├── gestion.py            # Paramètres, export/import, reset (/gestion)
│   ├── arcade.py             # Mini-jeux (/arcade)
│   └── onboarding.py         # Questionnaire post-login (/onboarding)
├── templates/
│   ├── base.html             # Layout master (nav 4 onglets, topbar, scripts)
│   ├── landing.html          # Page publique à / (non connecté)
│   ├── accueil.html          # Dashboard
│   ├── seance_choix.html     # Choix de séance du jour
│   ├── seance_edit.html      # Saisie exercices (Alpine.js, timer, inline history)
│   ├── programme.html        # Gestion programme
│   ├── progres.html          # Progression (body map, calendrier, volume, zoom)
│   ├── gestion.html          # Paramètres, export/import, reset, notifications
│   ├── plus.html             # Hub : Programme, Arcade, Gestion, Tutoriel
│   ├── arcade.html           # 3 mini-jeux canvas
│   ├── onboarding.html       # Questionnaire 4 étapes (Alpine.js)
│   ├── login.html            # Page login Google
│   ├── bridge.html           # Bridge OAuth → session Flask
│   └── _body_map_svg.html    # SVG carte musculaire (inclus dans progres)
├── static/
│   ├── css/
│   │   ├── theme.css         # Variables CSS, animations, composants globaux
│   │   ├── components.css    # Cards, stats, grids, boutons
│   │   └── tutorial.css      # Overlay tutoriel
│   ├── js/
│   │   ├── alpine.min.js     # Alpine.js bundlé localement
│   │   ├── sw-register.js    # Enregistrement SW + auto-update
│   │   ├── offline.js        # Détection hors-ligne, queue localStorage, sync
│   │   ├── notifications.js  # Rappels quotidiens (API Notification)
│   │   ├── tutorial.js       # Tutoriel spotlight interactif (6 étapes)
│   │   └── tuto-seance.js    # Tutoriel saisie de séance (6 étapes, 1ère ouverture)
│   ├── changelog.json        # Notes de version (patch notes modal)
│   ├── service-worker.js     # SW : Network First, cache v16, notifications
│   ├── manifest.json         # PWA manifest
│   └── icon.png              # Icône app
```

## Navigation (4 onglets)

1. **🏠 Accueil** (`/accueil`) — Dashboard, planning semaine, streak avec paliers, stats
2. **💪 Séance** (`/seance`) — Sélection séance du jour, saisie exercices
3. **📈 Progrès** (`/progres`) — Calendrier mensuel, volume hebdo, body map, hall of fame, zoom
4. **📋 Plus** (`/plus`) → Programme, Arcade, Gestion, Tutoriel

## Fonctionnalités clés

### Séance
- Timer de repos auto (configurable, se déclenche après saisie reps+poids)
- Inline history ("Dernière fois : 80kg × 8")
- Pré-remplissage automatique des poids
- Progression indicator ("EXERCICE 3/7")
- Modales de confirmation pour actions destructives

### Progression
- **Calendrier mensuel** : cases colorées (vert=fait, rouge=manqué, bleu=à venir), navigation mois, taux d'assiduité
- **Volume par semaine** : graphique SVG (8 dernières semaines)
- **Body map** : carte musculaire SVG interactive avec % de standard
- **Hall of Fame** : top 3 exercices par 1RM
- **Zoom mouvement** : évolution par semaine (Plotly)

### Streak
- Affiché en gros sur l'accueil avec icône flamme
- Paliers : 🥉 Bronze (4 sem), 🥈 Argent (8), 🥇 Or (12), 💎 Diamant (24)
- Record personnel sauvegardé dans `prog._streak_record`
- État "en danger" (orange + pulse) si séance du jour non faite

### Mode Offline
- Bandeau "Mode hors-ligne" affiché automatiquement
- Les formulaires de séance sont interceptés et stockés dans localStorage
- Synchronisation automatique au retour de la connexion avec toast
- Badge orange "X action(s) en attente" en bas à droite
- Pages principales en cache SW (accueil, séance)

### Notifications
- Permission demandée après 5s au premier login
- Rappel matin (jour d'entraînement, <14h)
- Rappel soir (séance non faite, ≥18h)
- Alerte streak en danger (≥19h, streak > 2)
- Désactivable dans Gestion > Paramètres

### Export / Import
- **Gestion** : "Exporter tout" (historique + programme + profil) ou "Programme seul"
- **Gestion** : "Importer" un fichier JSON (avec confirmation modale)
- **Programme** : export/import du programme (déjà existant)
- Format JSON, fichier nommé `muscu-tracker-backup-YYYY-MM-DD.json`

### Onboarding
- 4 étapes : Identité → Niveau → Objectif → Programme
- Cartes programmes enrichies : icône, étoiles de difficulté, durée, muscles tags
- Explications débutant sous chaque programme
- Tooltips "?" sur les niveaux
- Preview modale des séances avant choix
- Bouton retour fonctionnel à chaque étape

## Configuration

### Variables d'environnement
- `SUPABASE_URL` — URL du projet Supabase
- `SUPABASE_SERVICE_ROLE_KEY` — Clé service_role (jamais exposée au client)
- `FLASK_SECRET_KEY` — Secret pour signer les cookies de session

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

### Cache mémoire (core/db.py)
- TTL : 60 secondes
- Invalidé immédiatement après chaque save_prog() et save_hist()
- Clés : `hist:{user_id}`, `prog:{user_id}`

## Thème
- Background : `#050A18` (dark navy)
- Accent : `#58CCFF` (bleu néon)
- Success : `#00FF7F` (vert néon)
- Danger : `#FF453A` (rouge)
- Gold : `#FFD700`
- Font : système (sans-serif)

## Git
- Branche : `pwa-migration`
- Auteur : `morauxpaul-jpg <morauxpaul@users.noreply.github.com>`
- Flags requis : `-c user.name="morauxpaul-jpg" -c user.email="morauxpaul@users.noreply.github.com"`
- CACHE_VERSION : v18 (incrémenter à chaque déploiement)
