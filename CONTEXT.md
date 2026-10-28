# Muscu Tracker PRO — CONTEXT.md

## Architecture

PWA Flask (Python) avec Supabase (PostgreSQL) en backend, déployée sur Railway depuis `main`.
- **Framework** : Flask avec Blueprints + Flask-Limiter (rate limiting)
- **Frontend** : Jinja2 templates + Alpine.js **version CSP** + CSS custom (refonte UI dark minimal style Strong/Hevy). CSP **bloquante** sans `unsafe-inline` ni `unsafe-eval` pour les scripts (voir « Sécurité du navigateur (CSP) »)
- **Auth** : Supabase Google OAuth → bridge JWT → session Flask (cookie 30 jours)
- **Data** : Supabase tables (history, programs, profiles, onboarding, nutrition, aliments_perso, coach_messages, coach_conversations, session_notes, body_weight, push_subscriptions, events, reglages, calques_seance, etat_compte, photos_corps, amities, fil_seances, encouragements, defis, defis_participants) via `service_role` key. **Toutes les lectures de listes sont paginées** (`_fetch_all`) : PostgREST plafonne silencieusement à 1000 lignes.
- **PWA** : Service Worker (pages : réseau d'abord, mais une copie gardée est servie si le réseau ne répond pas en 3,5 s ; stale-while-revalidate sur `/static`), manifest.json, séance du jour pré-chargée pour l'usage hors-ligne
- **Serveur** : gunicorn `-k gthread --threads 16` (`railway.json`). Nombre de processus fixé par `pwa/gunicorn.conf.py` : `WEB_CONCURRENCY` n'est suivi **que si `REDIS_URL` est défini** (sinon 1, journal ERREUR et alerte /admin). Cache, verrous, quotas, tâches IA et plafond Open Food Facts passent par `core/partage.py` (Redis = commun à toutes les instances ; mémoire = une seule instance). **Sans Redis, garder aussi 1 réplique Railway.** Un appel IA lent ne gèle plus l'app pour tout le monde ; `ProxyFix` devant, sans quoi le rate-limit « 60/min par IP » comptait l'IP du proxy, donc tout le monde ensemble
- **IA** : Coach via API Anthropic (Claude Haiku 5.5, réglages communs dans `core/ia.py`), réponses diffusées en flux (SSE)
- **Coquille native** : Capacitor (`android/`, `capacitor.config.json` à la racine) — webview sur l'URL de prod + plugin AdMob. Pubs (Free uniquement, app native uniquement) : `pwa/static/js/ads.js`, IDs via env `ADMOB_BANNER_ID`/`ADMOB_INTERSTITIAL_ID` (`core/admob.py` : en production, identifiants absents ou de test = pubs **coupées**, journal CRITIQUE au démarrage et alerte dans /admin ; `ADMOB_TEST=1` pour les autoriser sciemment ; en local, IDs de test Google par défaut). Docs : `docs/CAPACITOR.md` + `docs/PLAY_STORE.md`. Login Google natif **branché côté code** (2026-06-15) : `login.html` détecte Capacitor → `@capgo/capacitor-social-login` (idToken + nonce) → `supabase.auth.signInWithIdToken` → `/auth/session` (OAuth webview interdit, 403 disallowed_useragent). **Le client OAuth Android de Google Cloud doit déclarer le nom de package EXACT et l'empreinte SHA-1 de la clé de signature.** Piège vécu : le client avait été créé le 2026-06-15 avec `com.muscutracker.app`, et le package a été renommé `com.muscutracker.fit` le lendemain (commit 45b6be5). La connexion native a donc échoué pendant trois mois avec un message illisible — Google refuse sans jamais afficher le sélecteur de compte. Empreinte actuelle (clé de release) : `E4:C0:D5:D4:6A:78:3C:3D:CA:6C:6B:C1:E7:28:5B:DE:00:A4:DF:EA`, à relire par `keytool -printcert -jarfile app-release.apk` après tout changement de clé. Une publication via Play App Signing ajoute une SECONDE empreinte (celle de Google) à déclarer en plus. L'identifiant Android n'est copié nulle part dans le code : c'est le client **web** (`GOOGLE_WEB_CLIENT_ID`) que l'app envoie ; il doit aussi figurer dans « Authorized Client IDs » du fournisseur Google côté Supabase.

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
│   ├── generate_exercise_art.py    # génère les images via l'API Gemini (reprenable, image de référence jointe ; clé en en-tête x-goog-api-key, ou ajoutée par le réseau de l'environnement cloud ; coût affiché après chaque image)
│   ├── import_exercise_art.py      # recadre, détouré, carre et convertit en WebP vers static/img/exercises/
│   └── dessiner_icone.py           # dessine icon-192/512.png (haltère vert #c8f031 sur noir) depuis sa géométrie
├── supabase_schema_v23.sql … v53  # Migrations SQL Supabase successives (nutrition, VIP, coach, stripe, events, referral, push, newsletter, … v40 repas par aliment, v41 index unique des séries, v42 exercise_id, v43 type_serie, v44 colonnes cardio, v45 table reglages, v46 table calques_seance, v47 table etat_compte, v48 durcissement, appliquée le 10/10/2026, v49 table aliments_perso, v50 photos_corps, v51 réglages des machines dans etat_compte, v52 amis : amities, fil_seances, encouragements, profiles.seances_masquees, v53 défis entre amis : defis, defis_participants)
├── supabase_schema_v32_prog_version_hist_index.sql  # programs.version (verrou optimiste) + index history(user_id,id)
├── supabase_schema_v33_body_weight.sql  # table body_weight (une pesée / jour / user)
├── supabase_schema_v34_session_notes.sql # history.session_id + history.rpe, index (user_id,date), table session_notes, push_subscriptions.last_reactivation_at
├── supabase_schema_v35_session_duration.sql # session_notes.duration_min
├── supabase_schema_v36_coach_memory.sql # profiles.coach_memory (note du coach entre conversations)
├── tests/                         # pytest — conftest = fake Supabase en mémoire (cd pwa && python -m pytest tests -q)
├── core/
│   ├── db.py                      # Façade de la couche données : la carte des dix modules db_* (aucun code)
│   ├── db_base.py                 # Connexion Supabase (service_role), cache LRU TTL 10 min (validité partagée), pagination PostgREST, use_client()
│   ├── reprise_base.py            # Lecture (GET/HEAD) coupée par Supabase (« ConnectionTerminated ») retentée une fois ; chronomètre chaque appel
│   ├── chrono.py                  # Temps passé en base et dans Redis par requête : en-tête Server-Timing, journal « lent : … » dès 800 ms
│   ├── schema.py                  # Colonnes attendues par le code (ATTENDU), vérifiées au démarrage : journal ERREUR + alerte /admin si la base est en retard
│   ├── db_historique.py           # Table history : lecture, écriture par clé de série, opérations ciblées
│   ├── db_etat.py                 # Table etat_compte (v47) : badges, défis, plats, cibles nutrition, compteurs ; superposé par get_prog, extrait par save_prog
│   ├── db_calques.py              # Table calques_seance (v46) : extras, brouillon libre, échanges, ordre, par séance+date
│   ├── db_reglages.py             # Table reglages (v45) : réglages par compte, repli sur l'ancien _settings du programme
│   ├── db_colonnes.py             # Colonnes facultatives de history (v42, v43, v44) : base en retard = lu et écrit sans
│   ├── db_historique_lots.py      # save_hist (sauvegarde, reset) et ajouter_lignes (import), par clé
│   ├── db_renommage.py            # Renommer séance / exercice dans l'historique, sans collision
│   ├── db_programme.py            # Blob programs.data : verrou optimiste, fusion 3 voies, corps vs données perso
│   ├── db_profil.py               # profiles : profil, onboarding, poids de corps
│   ├── db_nutrition.py            # nutrition : repas du jour (une ligne par aliment), sommes de macros, récents
│   ├── nutrition_cibles.py        # Cibles : protéines g/kg, cible du jour (entraînement / repos)
│   ├── nutrition_aliments.py      # Panier → lignes par aliment, correction de quantité, aliments récents
│   ├── nutrition_recettes.py      # Mes recettes (ingrédients, parts, poids cuit → valeurs pour 100 g) et aliments perso (étiquette)
│   ├── nutrition_rythme.py        # Rythme réel des pesées (6 semaines) face à l'objectif → cible proposée
│   ├── db_aliments.py             # Table aliments_perso (v49) : mes recettes et aliments
│   ├── db_photos.py               # Photos de progression (v50) : table photos_corps + dossier privé photos-corps (Storage)
│   ├── photos_corps.py            # Photos : angles, contrôles, écart « 8 semaines », poids du jour, avant / après, rappel 4 sem.
│   ├── rappel_photos.py           # Push « reprends tes photos » à 28, 56, 84 jours (PRO), dans le cron horaire
│   ├── poids_courbe.py            # Carte « Poids corporel » : dernière pesée, variation 30 j, courbe 90 j (sortie de routes/progres.py)
│   ├── db_bilans.py               # session_notes (v34) : bilans de séance
│   ├── db_amis.py                 # Amis (v52) : amitiés, fil des séances terminées, encouragements ; LA règle de visibilité appliquée à chaque lecture
│   ├── amis.py                    # Amis, calcul pur : code d'ami, ligne du fil (le permis seulement), classement, qui voit qui, cartes du fil
│   ├── amis_liens.py              # Amis : publier la séance terminée (/seance/finish), demande après l'inscription par un lien d'ami
│   ├── db_defis.py                # Défis entre amis (v53) : défis, participants, amis du créateur, séries des participants ; LA règle (participants, amis acceptés du créateur)
│   ├── defis.py                   # Défis, calcul pur : bornes, score depuis history (régularité, volume, progression), classement, égalités, annonce
│   ├── defis_liens.py             # Défis : ce que la page Amis (invitations, en cours, résultats du fil) et l'accueil affichent
│   ├── db_abonnement.py           # Tier PRO, Stripe, parrainage et VIP à durée limitée
│   ├── db_push.py                 # push_subscriptions, newsletter, relance des inactifs
│   ├── db_coach.py                # coach_messages / coach_conversations
│   ├── db_admin.py                # Stats globales, funnel, fiche user, suppression de compte
│   ├── strava_import.py           # Lecture de `activities.csv` (export Strava) : types, dates, unités, doublons
│   ├── data.py                    # Façade Flask (lit user_id depuis flask.g) + helpers nutrition/coach
│   ├── dates.py                   # Helpers dates (timezone Paris), DAYS_FR, MONTHS_FR
│   ├── muscu.py                   # Logique muscu (1RM, muscles, base_name, overload_suggestion)
│   ├── seance_semaine.py          # Semaine de programme, libellé du jour, séance réellement faite
│   ├── seance_historique.py       # Ce que l'historique dit d'un exercice : variante, record, suggestion
│   ├── seance_contexte.py         # Le dictionnaire que reçoit chaque carte d'exercice
│   ├── memoire_exo.py             # Ce que la carte rappelle de la fois d'avant : remarques, réglages de la machine (`_reglages_machines`)
│   ├── passes_seance.py           # Refaire une séance le même jour : « Push · 2 », séance du programme d'origine
│   ├── seance_calques.py          # Applique substituts et ordre des cartes ; purge des restes d'avant la v46 dans le blob
│   ├── seance_saisie.py           # Le formulaire devient des lignes d'historique + détection de record
│   ├── seance_cardio.py           # Unités cardio, et passage colonnes en base (v44) ↔ forme de l'app (Reps/Poids/Remarque)
│   ├── cardio_duree.py            # Durée cardio en minutes + secondes (lire_duree, format_duree, filtre duree_cardio)
│   ├── hist.py                    # Prédicats UNIQUES sur l'historique (is_perf, is_muscu_perf, is_session_marker, tonnage) — une seule définition de « séance faite »
│   ├── strength.py                # Standards de force relatifs au poids de corps (ratios par muscle × sexe, niveaux)
│   ├── exercise_stats.py          # Fiche par exercice : variantes, séances, records, séries, sparkline SVG
│   ├── reminders.py               # Rappel de séance à l'heure choisie (ciblage, payload, run_reminders)
│   ├── coach_memory.py            # Note persistante du coach sur l'utilisateur (700 car. max)
│   ├── coach_progression.py       # Contexte du coach : une ligne par exercice, ses 4 dernières séances datées
│   ├── debrief.py                 # Debrief de fin de séance : collecte des chiffres réels + rédaction IA
│   ├── openfoodfacts.py           # Produit emballé par code-barres (kJ→kcal, portion, cache mémoire)
│   ├── catalog.py                 # Catalogue de 20 programmes prédéfinis (5 gratuits)
│   ├── exercises_data.py          # Fiches exercices : matériel requis + substitutions
│   ├── foods_data.py              # Base de ~430 aliments courants (kcal/macros pour 100 g + portions) pour la recherche Nutrition
│   ├── body_map.py                # Polygones SVG du body map (d'après react-body-highlighter)
│   ├── challenges.py              # Défis hebdomadaires (un défi tournant, évalué depuis l'historique)
│   ├── push.py                    # Push web : config VAPID + envoi pywebpush (ttl, urgence), relance des inactifs
│   ├── push_repos.py              # Fin du repos envoyée par le serveur (écran éteint) : file + fil d'arrière-plan
│   ├── limiter.py                 # Instance Flask-Limiter partagée (60 req/min par IP, Redis si dispo)
│   ├── exercice_ids.py            # Identité stable des exercices : id au programme, exercise_id sur les séries, affichage sous le nom actuel
│   ├── partage.py                 # État commun aux instances : verrous, compteurs, générations de cache, valeurs (Redis si REDIS_URL, sinon mémoire ; repli mémoire si Redis tombe)
│   └── analytics.py               # Façade track(event,props) fire-and-forget + helper paywall() (funnel conversion)
├── routes/
│   ├── auth.py                    # Login Google, bridge JWT, logout, /auth/debug
│   ├── accueil.py                 # Dashboard (/accueil) — planning hebdo, streak, badges, défi, "Prochaine séance" (résumé : core/accueil_resume.py)
│   ├── seance.py                  # Séance du jour (saisie, skip, reset, finish + bilan, extras, cardio inline, suggestion de surcharge)
│   ├── seance_exo.py              # Ce qu'on retient d'un exercice depuis sa carte : repos (/seance/repos), réglages machine (/seance/reglages)
│   ├── programme.py               # CRUD programme + planning + import/export
│   ├── progres.py                 # Progression — body map, calendrier, volume, zoom mouvement, poids corporel (/progres/poids)
│   ├── gestion.py                 # Paramètres, settings, export/import, « Ranger mes exercices », reset total (le reset soft a été retiré en v47)
│   ├── onboarding.py              # Questionnaire post-login (recommend, submit)
│   ├── cardio.py                  # Saisie cardio (chrono + distance + cal + RPE) → table history
│   ├── nutrition.py               # Profil métabolique (Mifflin-St Jeor) + journal repas (recherche aliments, plats de la semaine, saisie rapide, composition) + carte « Ton rythme réel »
│   ├── nutrition_recettes.py      # Page « Mes recettes et aliments » : créer, corriger, supprimer (/nutrition/aliments)
│   ├── corps.py                   # Onglet « Corps » de Progrès (/progres/corps) : poids + photos (PRO), ajout, image, suppression
│   ├── coach.py                   # Chat IA (Claude Haiku 5.5) en flux SSE, réservé VIP, quota 15 msg/jour, mémoire entre conversations
│   ├── premium.py                 # Page de présentation des tiers (pré-paywall)
│   ├── billing.py                 # Stripe Checkout / webhook / portal (source de vérité du tier)
│   ├── generator.py               # Générateur de programme IA (VIP) — tâche de fond → JSON validé → save_prog
│   ├── push.py                    # Abonnement push (clé VAPID, subscribe/unsubscribe), fin du repos (/push/repos, /push/repos/annuler), /tasks/reactivation
│   ├── share.py                   # POST /share/track — compteur de partages de progression (analytics)
│   ├── parrainage.py              # Lien d'invitation + récompense VIP du parrain + apply_referral
│   ├── amis.py                    # Page Amis (/amis) : demandes par lien ou code, accepter, refuser, annuler, retirer, masquer, encourager
│   ├── defis.py                   # Défis entre amis (/amis/defis/…) : lancer, inviter, accepter, refuser, annuler
│   └── admin.py                   # Stats, gestion VIP, fiche user, funnel (gated par ADMIN_EMAILS env)
├── templates/
│   ├── base.html                  # Layout master (espace du haut, nav 4 onglets, scripts globaux, patch notes)
│   ├── _body_map_svg.html         # SVG carte musculaire (inclus dans progres)
│   ├── _programme_seance_card.html# Partial : carte séance dans /programme
│   ├── partials/vip_lock.html     # Cadenas / mur VIP réutilisable
│   ├── landing.html               # Page publique (/)
│   ├── login.html                 # Page login Google (web + natif Capacitor)
│   ├── bridge.html                # Bridge OAuth → session Flask
│   ├── accueil.html               # Dashboard
│   ├── seance_choix.html          # Choix de séance du jour
│   ├── seance_edit.html           # Saisie exercices (Alpine, chrono, RPE, inline history)
│   ├── programme.html             # Gestion programme + planning
│   ├── progres.html               # Progression (body map, calendrier, volume, standards de force)
│   ├── exercice.html              # Fiche d'un exercice : records, courbes, variantes, toutes les séances
│   ├── gestion.html               # Paramètres, export/import, reset, notifications, newsletter
│   ├── plus.html                  # Hub : Premium, Coach, Programme, Nutrition, Cardio, Gestion (aide du premier jour)
│   ├── premium.html               # Page de présentation des tiers
│   ├── billing_success.html       # Retour Stripe Checkout
│   ├── parrainage.html            # Page parrainage
│   ├── amis.html                  # Page Amis : invitation, demandes, défis, fil (séances et résultats des défis), ajouter, mes amis, « Masquer mes séances »
│   ├── _amis_defis.html / _defi_classement.html  # Défis (v53) : invitations, classements en direct, « Lancer un défi » ; le classement
│   ├── plaques.html               # Calculateur de plaques
│   ├── coach.html                 # Chat IA
│   ├── generator.html             # Générateur de programme IA (form + preview + adopter)
│   ├── cardio.html                # Saisie cardio
│   ├── nutrition.html             # Profil + journal repas + carte « Ton rythme réel »
│   ├── nutrition_aliments.html    # Mes recettes et aliments : liste, éditeur de recette, aliment perso
│   ├── onboarding.html            # Questionnaire 4 étapes (Alpine)
│   ├── admin.html / funnel.html   # Console admin + funnel de conversion (7/30/90j)
│   ├── faq.html / confidentialite.html  # Pages publiques (FAQ, politique de confidentialité)
│   ├── vip_wall.html              # Mur de blocage VIP plein écran
│   └── error.html                 # Page d'erreur
├── static/
│   ├── css/
│   │   ├── fonts.css              # Barlow + Barlow Condensed, servies par l'app (static/fonts, licence OFL)
│   │   ├── tokens.css             # Design tokens (couleurs, espacements, radius…) — style « Instrument »
│   │   ├── theme.css              # Variables, animations, composants globaux
│   │   ├── components.css         # Cards, stats, grids, boutons
│   │   ├── surfaces.css           # Habillage plat du style « Instrument » (chargé après components.css ; remplace glass.css)
│   │   ├── icons.css              # Tailles et couleurs d'icônes (.icon, .icon-sm, .icon-accent…)
│   │   ├── timer.css / rest-timer.css  # Chrono de repos (local à la séance / barre globale)
│   │   ├── tutorial.css           # Overlay tutoriel
│   │   └── a11y.css               # **Chargé en dernier** : cibles tactiles, cases à cocher, sélection de texte, masquage des tarifs en natif
│   ├── js/
│   │   ├── alpine.min.js / alpine-sort.min.js  # Alpine.js **version CSP** 3.17.4 + plugin sort, servis par l'app (empreintes npm vérifiées)
│   │   ├── alpine-composants.js   # Enregistre les composants Alpine, directive x-au-corps, magie $biblio (CSP)
│   │   ├── sw-register.js         # Enregistrement SW + auto-update
│   │   ├── offline.js             # Détection hors-ligne, queue localStorage, sync
│   │   ├── jour-seance.js         # Page de séance datée d'un jour à venir : rouverte pour aujourd'hui (en ligne) ou ramenée à aujourd'hui (hors ligne)
│   │   ├── push.js                # Abonnement push web (VAPID)
│   │   ├── install.js             # Expérience d'installation PWA (détection plateforme)
│   │   ├── ads.js                 # AdMob (app native + Free uniquement)
│   │   ├── rest-timer.js          # Chrono de repos global et persistant (barre injectée par base.html)
│   │   ├── share-card.js          # Carte de progression (canvas → PNG) + Web Share
│   │   ├── invitation.js          # Lien d'invitation : copier ou partager (Web Share) ; pages Parrainage et Amis
│   │   ├── defis.js               # Composant Alpine `defiForm` (« Lancer un défi » : l'exercice n'apparaît qu'en progression)
│   │   ├── tuto-engine.js         # Moteur de tutoriel partagé (spotlight + bulle)
│   │   ├── tutorial.js / tuto-seance.js  # Aide du premier jour : 1 bulle accueil, 3 en séance au fil des gestes
│   │   ├── ui-fx.js               # Effets UI (toasts, micro-animations)
│   │   ├── prefetch.js            # Prefetch des pages clés
│   │   ├── exercise-library.js    # Bibliothèque d'exercices (search/picker)
│   │   ├── seance.js              # Saisie de séance (extrait de seance_edit.html) : enregistrement JSON, file hors-ligne, records, réordonnancement
│   │   ├── exo-info.js            # Modale « fiche exercice » de la séance
│   │   ├── aliments-recherche.js  # Recherche d'aliments partagée (repas et recettes) : accents, œ/æ, rangs
│   │   ├── recettes.js            # Éditeur de recette (composant recetteForm)
│   │   └── barcode.js             # Scan de code-barres via BarcodeDetector (Nutrition), repli saisie manuelle
│   ├── img/
│   │   ├── icons.svg              # Sprite SVG (lucide-like) référencé via <use href="…#name"/>
│   │   └── exercises/             # Illustrations d'exercices : 101 WebP 400×400 (une par entrée du catalogue sauf « Copenhagen plank », qui garde son dessin au trait : abandonné le 18/10, plus de crédit Gemini ; 46 refaites ou créées le 14/10/2026 avec gemini-3-pro-image, référence squat.webp) + 18 anciens SVG plus affichés
│   ├── promo-vip-motion.mp4 / -poster.jpg # Vidéo de la page PRO (37 s, muette, style « Instrument », 14/10/2026) et son aperçu ; fabriquées par ../marketing/promo-vip/rendre.py, ne pas retoucher à la main
│   ├── changelog.json             # Notes de version (patch notes modal)
│   ├── service-worker.js          # SW : Network First, CACHE_VERSION = base ; le SHA du commit est ajouté par app.py
│   ├── manifest.json              # PWA manifest
│   └── icon-192.png / icon-512.png # Icônes app : haltère vert sur noir, style « Instrument » (14/10/2026), redessinées par tools/dessiner_icone.py
```

## Navigation (4 onglets)

1. **🏠 Accueil** (`/accueil`) — style « Instrument » (13/10, `core/accueil_resume.py`) : la date ; la prochaine séance en très grand (exercices, séries, premier exercice) et son bouton « Commencer » / « Faire maintenant » ; la semaine en barres (faite = vert, aujourd'hui = cadre blanc, prévue = gris avec l'initiale, manquée = pointillés orange, repos = trait bas) ; tuiles Poids (dernière pesée, pente sur 6 semaines par moindres carrés) et Kcal du jour (PRO ; volume de la semaine pour un compte gratuit) ; dernier record (dernière série qui bat la force estimée, Epley, d'un jour précédent ; les répétitions au poids du corps). Puis, à plat : progrès, défi, semaines d'affilée, chiffres de la semaine, partage, badges
2. **💪 Séance** (`/seance`) — Sélection séance du jour, saisie exercices, ajout cardio inline. **Choix** (style « Instrument », 13/10, `seance_choix.html`) : la date en petit avec l'état du jour (« · RÉALISÉE » en vert, « · MANQUÉE » en orange, « · À FAIRE »), la question en grand (« Quelle séance aujourd'hui ? », le nom de la séance un jour fait) ; une séance à rattraper encadrée d'orange ; les séances en lignes à filet (nom, jours, nombre d'exercices et les trois premiers) ; deux tuiles Séance libre et Cardio. **Fin** : carte « Séance terminée » + nom en grand + tuiles plates ; note de 1 (dure) à 5 (excellente) en cinq boutons numérotés, le choisi en blanc
3. **📈 Progrès** (`/progres`) — Calendrier mensuel (titre « OCTOBRE 2026 · 2 séances sur 6 prévues »), « Mes exercices · force estimée » (les 6 mouvements les plus travaillés : séances, dernière date, force estimée de la dernière séance ou ses répétitions au poids du corps, mini-barres des 6 dernières séances du même genre, la dernière en vert quand elle bat les précédentes — `exercise_stats.resume_mouvement`), body map (échelle de vert, plus de bleu), hall of fame, volume hebdo, poids
4. **📋 Plus** (`/plus`) → Premium · Coach IA · Programme · Nutrition · Cardio · Gestion · Tutoriel (l'Arcade a été retirée le 01/10/2026 : hors sujet, audit du 30/09)

## Système Free / VIP

- **Deux niveaux d'accès** (2026-06-14) :
  - `g.is_vip_full` = **PAYANT** (`tier == 'vip'`) → accès **complet** (Coach IA, Générateur IA, programmes PRO, multi-programmes, réimport).
  - `g.is_vip` = full **OU essai à durée limitée** (`vip_until > now()`, via `db.vip_until_active()`) → accès **restreint** : **Nutrition + stats détaillées seulement**. L'AFFICHAGE suit : l'essai voit « Essai PRO — encore X h », un badge ESSAI et les boutons d'achat (`is_trial`, `trial_left`), jamais « Tu es VIP » (audit du 30/09, C2).
  - `vip_until` = essai « découverte » (parrainage/promo, migration v29). Volontairement court + restreint pour ne pas cannibaliser l'achat (un essai complet permettrait de générer un programme et tout extraire en 1 j).
  - **Règle de gate** : features payantes → `getattr(g, "is_vip_full", False)` ; Nutrition + stats avancées (`progres`, profondeur d'historique `gestion`) → `getattr(g, "is_vip", False)`.
  - Les deux sont résolus + cachés en session par `before_request` (`is_vip`, `is_vip_full`), exposés aux templates par le context processor. `billing.success` pose les deux ; le webhook passe le `tier` → recalculé au TTL. **TTL asymétrique** (2026-06-14) : un VIP confirmé est re-vérifié toutes les `VIP_CACHE_TTL`=120 s, un FREE toutes les `FREE_RECHECK_TTL`=15 s — pour qu'un passage VIP (grant admin ou achat Stripe) se propage en quelques secondes à la session du user, même sur un autre appareil. La vérif d'existence du compte auth (API auth, plus coûteuse) passe toutes les `AUTH_CHECK_TTL`=600 s via `session['auth_check_ts']` (120 s avant le 10/10 : elle tombait sur presque chaque « Série faite », audit I-2).
- **Offre « équilibrée »** (2026-06-11) — Free = séances illimitées + progrès simple + 1 programme + cardio + **export de ses données** (gratuit depuis le 30/09, RGPD). VIP = Coach IA (15 msg/j), **Nutrition**, stats détaillées (body map/1RM/zoom), programmes PRO, multi-programmes, réimport.
- **Gating Free** : Coach IA, Nutrition, Import (l'export est gratuit), programmes PRO du catalogue, stats avancées, multi-programmes.
- **Onglet Plus** (style « Instrument », 13/10) : un bloc PRO (Membre PRO / Essai PRO / Passe en PRO), puis des listes à filets sans cartes : Entraînement (Programme, Cardio, Disques à charger, Nutrition), Coach (Coach IA, Générer un programme), Compte (Réglages et données, Inviter des amis « +3 jours PRO », FAQ). Fonctions PRO visibles avec badge et cadenas + `vip_wall`.
- **Mur VIP** : `templates/partials/vip_lock.html` (inline) ou `vip_wall.html` (plein écran).
- **Badge PRO / ESSAI**, e-mail et déconnexion : carte **COMPTE** en tête de Gestion. La barre du haut de chaque page a été retirée le 10/10 (audit m12 : bruit visuel, déconnexion accidentelle).
- **Admin** (`ADMIN_EMAILS` env, séparateur virgule) peut basculer manuellement le tier d'un user via `/admin/set-tier`.
- **Paiement Stripe** (`routes/billing.py`) : Checkout (prix inline `price_data`, pas d'ID à pré-créer) pour mensuel 4,99€ / annuel 39,99€ / lifetime 79,99€. Webhook `/billing/webhook` (public + CSRF-exempt, signé) = source de vérité du tier ; `/billing/success` active aussi le VIP en filet ; `/billing/portal` = gestion/annulation. Tarifs ET boutons absents du rendu dans l'app native (cf. « App native : parcours d'achat »). Env : `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`. Migration : `supabase_schema_v27_stripe.sql` (colonne `profiles.stripe_customer_id`).
- **Remboursements et litiges** (`core/stripe_remboursements.py`, vague 9 du 04/10) : `charge.refunded` total → gratuit, sauf abonnement encore actif (geste sur une mensualité) ; partiel → rien. `charge.dispute.created` → gratuit tout de suite ; `charge.dispute.closed` gagné → PRO rendu. Compte : `metadata.user_id`, sinon le client Stripe (relu sur le paiement pour un litige). Événements `vip_refunded`, `stripe_dispute`. **À abonner dans Stripe** : `charge.refunded`, `charge.dispute.created`, `charge.dispute.closed`.
- **Upgrades de plan** : `billing.detect_current_plan()` lit l'abonnement actif (mensuel/annuel/None) ; la page Premium propose les paliers supérieurs aux abonnés. À l'upgrade, l'ancien abonnement est **supersédé** (`metadata.superseded=1`) puis annulé — le webhook `subscription.deleted` ignore alors la rétrogradation (pas de perte de VIP ni de double facturation). Réutilise le même `customer` Stripe.

## Fonctionnalités clés

### Séance
- Timer de repos auto (configurable, déclenché par « Série faite ») ; le repos prescrit par le programme passe avant le dernier préréglage touché. 90 s ne comptent pas comme une prescription (`core/seance_contexte.py`) : l'éditeur les inscrit sur tout exercice sans durée, et la durée choisie dans la barre ne passait plus d'un exercice à l'autre (retour du 23/10). L'exercice qui a lancé le repos part avec l'état gardé du chrono (`rest_timer_state.cle`) : une durée choisie après un rechargement lui revient encore, via `window.retenirReposExo` (seance.js ; global, car rest-timer.js est chargé après seance.js). Safari recharge souvent la page au retour dans l'app : « enregistre une fois sur deux » (iPhone, 23/10)
- **Bip léger** en fin de repos (sine 600 Hz, ~80 ms, gain 0.04, généré via Web Audio API)
- Inline history (« Dernière fois : 80 kg × 8 ») : toujours la séance précédente, y compris dans la réponse de `/seance/save-exo` après chaque série (elle renvoyait les séries du jour, retour du 23/10)
- Pré-remplissage automatique des poids
- Progression indicator (« EXERCICE 3/7 »)
- Inline-confirm pour actions destructives (jamais `prompt()`/`confirm()`/`alert()`, jamais hors-carte)
- Ajout cardio dans la séance via `/seance/add-cardio`
- **Enregistrement sans rechargement** (`/seance/save-exo` répond en JSON si `Accept: application/json`) : la carte se met à jour sur place et la suivante s'ouvre. Le POST classique reste le repli sans JavaScript.
- **Record annoncé en direct** : `_pr_check()` compare la série à tout l'historique de l'exercice et renvoie le type de record (première fois / charge / reps / reps à charge égale) ; la carte l'affiche au moment où il tombe.
- **Bilan de séance** (`session_notes`, migrations v34/v35) : ressenti, commentaire, durée. `history.session_id` (uuid5 déterministe user|date|séance) relie les lignes d'une même séance.
- Une même séance peut être faite **deux fois dans la semaine** : les opérations ciblent la date exacte, plus la semaine (cf. « Semaine continue »).
- **Refaire la même séance** (retour du 14/10) : le lendemain, l'accueil propose toujours la séance prévue aujourd'hui, même faite la veille (le « rattrapage » ne compte que ce qui a été fait un jour où elle n'était pas prévue). Le jour même, « Refaire Push » sous « Voir la séance » ouvre une seconde passe nommée « Push · 2 » (puis « · 3 ») : séries, bilan et `session_id` à elle, la première intacte. `core/passes_seance.py` : `seance_de_base` (« Push · 2 » → « Push » pour les exercices, le repos et la cible), `prochaine_passe`. Aucune migration : c'est le nom de séance qui distingue les passes.
- **Durée de repos retenue par exercice** (14/10) : toucher une durée dans la barre du chrono l'enregistre pour l'exercice qui a lancé le repos (`rest_seconds` du programme, `POST /seance/repos`, 30–300 s, `routes/seance_exo.py`). Exercice absent du programme : gardée sur l'appareil (`localStorage.repos_par_exo`). La carte affiche la durée en vigueur.
- **Remarques de la fois d'avant** (14/10, `core/memoire_exo.derniere_remarque`) : sous « Dernière fois », les remarques de la dernière séance annotée de cet exercice, avant le jour affiché (même séance d'abord), sans « SKIP », « @RPE » ni mentions d'import. 300 caractères au plus.
- **Réglages de la machine** (14/10) : une ligne libre par exercice et équipement (« Siège 4 · goupille 7 »), 120 caractères, sous `_reglages_machines` : **dans l'état du compte depuis la v51** (colonne `etat_compte.reglages_machines`, audit du 18/10, m7), toujours lu et écrit par le programme grâce à `superposer` / `extraire` (survit aux changements de programme, part dans l'export). Clé : `exo_id`, sinon `n:` + nom normalisé, suivie de `~variante` hors « Standard ». `POST /seance/reglages` (JSON, ou formulaire rejoué par la file hors-ligne) ; texte vide = efface. Visible carte fermée.

### Cardio
- 10 activités (`routes/cardio.py`, `ACTIVITES_MAP`), avec MET pour estimation calories
- Stockage dans la même table `history` (Exercice = `CARDIO:Type`, Muscle = `Cardio`). **Depuis la v44**, en base : `duree_min`, `distance`, `calories`, `vitesse`, et `reps = poids = 0` (contrainte `history_cardio_colonnes_check`) ; la remarque ne garde que FC, inclinaison, RPE et la note. **Dans l'app**, rien ne change : `get_hist()` rend Reps = minutes, Poids = distance, Cal/Vit en remarque, plus les clés Duree/Distance/Calories/Vitesse. La conversion est dans `core/seance_cardio.py` (`vers_colonnes`, `depuis_colonnes`), appelée par `db_historique` seulement. Ce qui lit la table sans passer par l'app (cron, récap, relances) utilise `hist.perf_brute` et `db_colonnes.lire_avec_mesures`.
- **Durée en minutes et secondes** (06/10) : les deux formulaires ont un champ secondes (`duree_sec`) et le chrono garde les secondes. `duree_min` stocke des minutes décimales (25 min 30 s = 25.5). Dans l'app, `Duree` porte la durée exacte et `Reps` les minutes entières arrondies (jamais 0 pour un cardio fait). Affichage : filtre `duree_cardio` (« 25 min 30 s »). Code : `core/cardio_duree.py`.

### Nutrition
- Cibles (`core/nutrition_cibles.py`, vague 5 du 04/10) : BMR Mifflin-St Jeor, TDEE × facteur d'activité (5 niveaux), ±400 kcal selon l'objectif (Masse / Maintien / Sèche), cible manuelle prioritaire (`_nutrition.calories_custom`). **Protéines en g/kg** (1,8 ; 2,2 en sèche ; plafond 40 % des kcal), lipides 25 % (≥ 0,7 g/kg), glucides = le reste.
- **Cible du jour** (`cible_pour` / `cible_du_jour`) : jour d'entraînement (séance prévue au planning, ou faite ce jour-là) = plus de glucides, repos = moins ; écart total 15 % de la cible réparti selon le nombre de séances/semaine (planning, sinon moyenne des 4 dernières semaines) → **moyenne de la semaine inchangée**. Protéines et lipides fixes. Désactivable (`_nutrition.cycle = False`, case du profil ; `cycle_form` témoin). Utilisée par la page Nutrition ET la carte calories de l'accueil (qui affiche aussi les protéines du jour).
- Table Supabase `nutrition` : **une ligne par aliment** (panier « Aliments », `core/nutrition_aliments.py`) avec `grams` + `food` (valeurs pour 100 g, migration **v40**) ; les macros sont recalculées côté serveur depuis `food` (le navigateur envoie `items` = aliments + grammes, plus de totaux). Les repas saisis en bloc (saisie rapide, composition, plats de la semaine) restent une ligne de totaux. Sans v40 : écriture retentée sans ces colonnes (PGRST204), le repas est noté.
- `POST /nutrition/edit-meal` (corriger les grammes, macros recalculées), `POST /nutrition/copier` (« Reprendre … de la veille » pour un créneau vide aujourd'hui, rempli la veille), aliments **récents** (60 j, les plus fréquents d'abord, « comme la dernière fois ») en tête de recherche et proposés champ vide.
- **Produits du commerce par leur nom** : `GET /nutrition/recherche?q=` → `openfoodfacts.search` (bouton explicite, pas à chaque frappe ; Open Food Facts limite la recherche à 10/min/IP → plafond global 8/min + cache 12 h ; 503 « réessaie » au-delà).
- **Mes recettes et aliments** (12/10, `core/nutrition_recettes.py`, table `aliments_perso`, migration **v49**) : une recette = ingrédients pesés + nombre de parts (+ poids cuit facultatif) ; ses valeurs pour 100 g sont recalculées par le serveur, le navigateur ne fixe rien. Une recette **est un aliment** (`food` au format de `nutrition.food`, unité « 1 part ») : panier, correction de quantité et récents marchent tels quels. Aliment perso = l'étiquette, pour 100 g ou pour une portion (« 1 barre = 45 g »), calories déduites des macros si vides. Noms uniques par compte (casse ignorée), 200 au plus. Ils passent en tête de la recherche (`r = -2`, « Ma recette » / « Mon aliment ») ; un récent du même nom prend leurs valeurs actuelles (`rafraichir_recents`). Les repas déjà notés gardent leur copie : corriger une recette ne réécrit pas le passé. Page `/nutrition/aliments` (`routes/nutrition_recettes.py`) ; une saisie refusée rouvre l'éditeur avec ce qui a été tapé. Sans v49 : la page dit « bientôt », la nutrition marche comme avant, /admin signale la table. Export RGPD : clé `aliments_perso` ; effacée avec le compte.
- **Ton rythme réel** (12/10, `core/nutrition_rythme.py`) : pente des pesées sur 6 semaines (moindres carrés ; 3 pesées sur 14 jours au moins, sinon la carte dit ce qui manque) face à la fourchette de l'objectif (sèche −0,5 à −1 %/semaine, masse +0,25 à +0,5 %, maintien ±0,25 %). Hors fourchette : cible **proposée**, jamais appliquée seule — le plus petit pas qui ramène dans la fourchette (7 700 kcal/kg), arrondi à 50, plafonné à ±300 kcal/j, jamais sous le BMR. Le bouton (`POST /nutrition/cible/ajuster`) recalcule la proposition et n'applique que celle affichée ; il pose `calories_custom`, `ajuste_le`, `ajuste_de` dans `_nutrition` (etat_compte) et met `profiles.calories_cible` à jour. Puis 14 jours sans nouvelle proposition. Affichée le jour même seulement.
- **Scan de code-barres** (mode « Scanner » du formulaire de repas) : `BarcodeDetector` du navigateur (Chrome/Android, donc l'app native et la PWA Android), repli par saisie des chiffres ailleurs — aucun décodeur JavaScript embarqué. Le produit est cherché côté **serveur** (`GET /nutrition/barcode/<code>` → `core/openfoodfacts.py` → Open Food Facts) : l'IP et les scans de l'utilisateur ne sortent pas de l'app et le cache est mutualisé. Le produit rejoint le panier « Aliments », donc mêmes réglages de portion et même bouton d'ajout.
- Caméra : `Permissions-Policy: camera=(self)` (app.py) + `android.permission.CAMERA` dans le manifeste Android ; Capacitor demande la permission au premier scan.

### Coach IA
- Modèle : `claude-haiku-5-5` depuis le 25/10 (avant : Haiku 4.5), effort `low`, max **4000** tokens, réflexion comprise (500 coupaient les réponses en plein milieu ; 1 400 sous Haiku 4.5, sans réflexion)
- **Contexte des séances (retour du 26/10)** : le coach a écrit « pec deck 39 kg, contre 15,8 kg le 12/10 » (le 12/10 : 39 kg ; 15,8 kg était le pushdown du même jour, et le pec deck du 4/10). Les données étaient justes, rangées par séance. Désormais : bloc « PROGRESSION PAR EXERCICE » (`core/coach_progression.py`, 25 exercices, 4 séances chacun, dates ISO), règle « ne cite une charge, des reps ou une date que s'ils figurent tels quels », et « 14 DERNIÈRES SÉANCES » donne tous les exercices (coupé à 6 avant : le 7e n'arrivait jamais).
- **Passage à Haiku 5.5 (25/10)**, réglages dans `core/ia.py`. Le token coûte 10 fois moins (0,10 $ / 0,50 $ le million au lieu de 1 $ / 5 $). Le même texte compte environ 30 % de tokens en plus, et le modèle réfléchit avant de répondre, ce qui est facturé en sortie. Effort `low` pour le coach, le bilan et la mémoire, `medium` pour le générateur. Plafonds relevés pour laisser place à la réflexion : bilan 260 → 1 500, mémoire 250 → 1 500, programme 2 600 → 12 000, séance refaite 900 → 4 000. Un refus de sécurité (`stop_reason: "refusal"`, sans modèle de repli) ne compte pas dans le quota : le coach répond « Reformule-la » et efface le début déjà affiché (`retirer`), le générateur renvoie 422, le bilan et la mémoire ne changent rien. Chaque appel journalise « ia <route> : N tokens en entrée, M en sortie, fin=… » : c'est la mesure du coût réel.
- **Réponse en flux** : `/coach/ask` répond en Server-Sent Events (`stream_with_context`, `X-Accel-Buffering: no`) quand le client le demande ; le texte s'écrit au fur et à mesure au lieu de faire patienter plusieurs secondes. Repli JSON si le flux n'est pas accepté.
- **Mémoire entre conversations** (`core/coach_memory.py`, migration v36) : après quelques échanges, le coach réécrit une note de 700 caractères max sur l'utilisateur (blessures, contraintes, préférences) dans `profiles.coach_memory` ; elle est injectée dans les conversations suivantes. Sans la colonne, l'écriture échoue en silence et l'app fonctionne sans mémoire.
- Accès réservé VIP (mur `vip_wall.html` pour les free)
- Quota VIP : 15 msg/jour (champs `profiles.coach_quota_date` + `coach_quota_count`, reset auto à chaque nouveau jour) — protège le coût API. Le quota est **rendu** si la génération échoue.
- Historique persisté dans `coach_messages` / `coach_conversations`, effaçable via `/coach/clear`
- Le system prompt inclut le profil utilisateur, le programme, l'historique récent, la note de mémoire et la date du jour (sans elle, il comptait mal les jours depuis la dernière séance) ; consigne : pas d'emoji
- **Affichage des réponses** : directive `x-md` (`alpine-composants.js`), qui pose le HTML déjà échappé par `renderMd`. **Jamais `x-html`** : la version CSP d'Alpine le refuse et la bulle reste vide (panne du 10 au 14/10 ; `test_aucun_gabarit_n_utilise_x_html`). Entrée envoie, Maj+Entrée va à la ligne (`envoyerSiPret`)
- Les erreurs techniques ne remontent plus au client (avant : « Vérifie ANTHROPIC_API_KEY dans Railway »)

### Debrief de fin de séance
- Le coach est une page qu'il faut **penser** à ouvrir. Le debrief va au-devant, sur l'écran qui suit la séance : `/seance/finish` mémorise la séance en session, l'accueil affiche une carte qui appelle `POST /seance/debrief`.
- `core/debrief.py` : `collect_facts()` calcule volume, séries, reps, RPE moyen, records battus et comparaison avec la dernière séance du même nom ; l'IA **rédige** trois phrases à partir de ces chiffres, elle ne les invente pas (~250 tokens).
- PRO complet ; **un aperçu gratuit par semaine** (`prog._debrief_free`, fenêtre glissante de 4 semaines) sert de démonstration honnête. L'aperçu n'est consommé que si la génération aboutit.
- **Un texte par séance** (audit du 18/10, m3) : le debrief est gardé 3 jours dans `core/partage` (`debrief:<compte>:<date>:<séance>`) et rédigé sous verrou. Deux cartes ouvertes pour la même séance ne paient plus deux appels IA ni deux aperçus (production : trois debriefs pour une séance, deux à 2 s d'écart).
- La proposition est consommée une seule fois et **pas par le préchargement** de `prefetch.js` (garde `Sec-Fetch-Mode: navigate`) : sinon le survol du lien la brûlait avant que l'utilisateur la voie.

### Générateur de programme IA (VIP, 2026-06-14)
- **Route** `routes/generator.py` : `GET /generator` (form, VIP-gated via `paywall`), `POST /generator/generate` (prompt structuré → Claude Haiku 5.5, effort `medium`, `max_tokens=12000` → **JSON strict** → `parse_and_validate`), `POST /generator/apply` (re-validation + `save_prog`, même chemin sûr que l'import ; reps NON persistées, cf. semaine continue).
- **Tâche de fond** (`core/taches_ia.py`, vague 8 du 04/10) : `POST /generator/generate` et `POST /generator/seance` lancent l'appel IA dans un groupe de 3 fils dédié et attendent au plus 2 s (`ATTENTE_REQUETE`) : une erreur immédiate (clé absente, quota) ou une IA rapide répond directement ; sinon **202** `{statut: "encours", tache}`, et la page interroge `GET /generator/tache/<id>` toutes les 1,5 s. Un second tap rejoint la tâche en cours. La place de quota est rendue par la tâche à sa fin. L'appel tourne dans l'instance qui l'a lancé ; son état (en cours, résultat) est dans `core/partage.py`, donc lisible depuis n'importe quelle instance avec Redis (l'autre instance sonde toutes les 0,2 s). Sans Redis, mémoire du processus : après un redémarrage, 404 « relance-la », quota intact. Avec Redis, une instance morte en plein appel laisse une tâche « en cours » déclarée perdue à 150 s. Tâche > 150 s = 504. La page garde l'id dans `sessionStorage` (`gen_tache`) et reprend le suivi après un rechargement. Appel Anthropic borné à 90 s (`TIMEOUT_IA`). `run_local_fake.py` avec `FAUX_IA=lent` simule une IA de 3 s (tests navigateur).
- **`parse_and_validate(raw)`** = fonction **pure** (testée, `tests/test_generator.py`) : tolère les blocs ``` ```json ```, normalise les muscles (vers `MUSCLES` canoniques, défaut « Autre »), clamp sets 1–8, ≤6 séances / ≤12 exos, planning FR filtré + fallback cyclique.
- **Anti-coût** : quota 3/semaine glissante (7 j) / VIP via la table `events` (compte les `program_generated` des 7 derniers jours, `_gen_used_week`) + backstop Flask-Limiter `10/h` sur generate, `20/h` sur apply.
- **Prompt** : injecte la liste des exercices connus (`EXERCISES_INFO`) pour biaiser vers des exos illustrés + la liste des muscles canoniques.
- **Events** : `program_generator_viewed`, `program_generated`, `program_adopted` (nourrissent aussi le funnel). **Entrée UI** : carte « Générateur IA » dans le hub Plus (section Premium, cadenas si free).

- **Progression visible** pendant les 10-25 s d'attente (étape, temps écoulé, barre) — côté page, sans changement serveur.
- **Refaire une séance** (`POST /generator/seance`) : régénère une seule séance de l'aperçu, avec une consigne facultative ; prompt court (900 jetons), quota à part (10/jour, événements `seance_regenerated`), réservé PRO. `_lire_params` et `_appeler_ia` sont partagés avec la génération complète.
### Parrainage (croissance, 2026-06-14)
- **Boucle** : chaque user a un `profiles.referral_code` (stable, dérivé de l'user_id) → lien `/?ref=CODE`. Page **/parrainage** (hub Plus) : lien + copier + partager (Web Share) + compteur de filleuls/jours gagnés.
- **Capture** : la landing pose un cookie `pending_ref` (survit au round-trip OAuth). À l'onboarding du filleul, `parrainage.apply_referral` crédite **une seule fois** : parrain **+3 j essai**. **Le filleul ne reçoit plus rien à l'inscription (25/10)** : son jour offert posait `vip_until` avant sa première séance et lui fermait l'essai de 3 jours (`core/essai.py`, ouvert seulement à qui n'en a jamais eu). Il a désormais l'essai de tout le monde, après sa première séance (via `db.grant_vip_days` → `vip_until` cumulatif). L'essai = accès **restreint** (Nutrition + stats, cf. `is_vip_full`). Garde-fous : code valide, pas d'auto-parrainage, `referred_by` posé une seule fois. Le parrain passe en essai via la revalidation FREE (15 s). Récompense ajustable : `REFERRER_VIP_DAYS` dans `routes/parrainage.py` ; la page affiche `ESSAI_JOURS` pour le filleul.
- **Migration** : `supabase_schema_v29_referral.sql` (`profiles` += `referral_code` [unique], `referred_by`, `vip_until`). Helpers `db_abonnement.py` : `get_or_create_referral_code`, `get_user_by_referral_code`, `set_referred_by`, `grant_vip_days`, `count_referrals`, `get_referred_by`, `vip_until_active`. Events : `referral_shared`, `referral_signup`.
- ⚠ **En production depuis le 09/10/2026 seulement.** La v29 n'avait jamais été appliquée (audit du 06/10, E1) : avant cette date, aucun parrainage n'a crédité de jours et aucun essai n'a existé. Ce genre d'oubli est maintenant signalé au démarrage (`core/schema.py`).

### Amis (v52, 25/10/2026)
- **Choix du propriétaire** : « Amis + séances visibles », visibles des amis **acceptés** seulement, **gratuit pour tous** (levier d'acquisition). Entrée : Plus › Compte › Amis (`/amis`).
- **Ajouter** : le code d'ami est le code de parrainage (`profiles.referral_code`, 8 caractères). Lien d'ami `/?ref=CODE&ami=1` (copier ou partager, `static/js/invitation.js`, le même bloc que Parrainage). **Utiliser le code d'un autre ENVOIE une demande ; c'est le titulaire du code qui l'accepte** : un code trop partagé ne donne accès à rien sans son accord. Deux demandes croisées font une amitié. Déjà connecté, le lien mène à `/amis?code=…` qui propose la demande (rien n'est envoyé sans le geste). Pas connecté : la page publique pose `pending_ref` ET `pending_ami` ; un nouveau compte envoie la demande à la fin de l'onboarding (et passe par le parrainage) ; un compte déjà inscrit est mené de l'accueil à `/amis` après la connexion, une fois (cookie effacé à la première vraie visite, jamais par un préchargement).
- **Refuser, annuler, retirer** effacent la ligne d'`amities` : effet immédiat des deux côtés. 100 amis et demandes envoyées au plus.
- **Le fil** : `/seance/finish` écrit `fil_seances` (une ligne par séance, `session_id` = `history.session_id`) avec **seulement** nom, date, durée, tonnage et records battus (`core/amis.ligne_fil`, chiffres de `debrief.collect_facts`). Ni note, ni commentaire, ni poids du corps, ni photos, ni nutrition, ni coach : ces données ne sont pas dans la table. Une séance sans série n'entre pas ; terminer deux fois ne double pas ; une séance effacée (`delete_session_rows`) ou une remise à zéro sort du fil. Pas de reprise des séances d'avant la v52. Le fil montre 30 jours, 60 séances au plus, les miennes comprises.
- **Visibilité** (`core.amis.visibles`, appliquée dans `core/db_amis.py`) : amitié acceptée ET ami sans « Masquer mes séances » (`profiles.seances_masquees`). Masquer cache tout sans retirer l'amitié.
- **Encourager** (icône bras, pas d'emoji : règle du style « Instrument ») : un par personne et par séance (unicité en base), seulement sur la séance d'un ami visible ; sinon 404. Le compteur n'est montré qu'à l'auteur ; l'ami voit « Encouragé ».
- **Limites** (par compte) : demandes 20/h et 50/j, encouragements 60/h et 300/j.
- **Base** : tables fermées au navigateur comme depuis la v38 (RLS active, aucune règle, droits à `service_role` seul). Pas de règle « self » pour `authenticated` : elle rouvrirait la porte fermée par la v38 ; le serveur applique la règle. Index unique sur la paire `(least, greatest)`, encouragement lié à sa séance du fil (clé étrangère, cascade). Rejouée deux fois sur PostgreSQL 16 avec 18 essais (paire, soi-même, état, doublon d'encouragement, séance absente du fil, `anon`/`authenticated` refusés, cascades). **Appliquée le 25/10/2026** (02:38 UTC, `20261025023818 v52_amis`, accord du propriétaire) et vérifiée : 3 tables, RLS active sans règle, aucun droit pour `anon`/`authenticated`, droits à `service_role`, 18 contraintes, index de paire `(LEAST, GREATEST)`, `profiles.seances_masquees` booléen non nul à `false` (15 profils, 0 masqué), 0 ligne.
- **Sans la v52** : la page dit « Les amis arrivent bientôt », la fin de séance marche, /admin signale les tables.
- **Compte** : suppression = amitiés des deux côtés, fil, encouragements donnés et reçus (`delete_user_account`) ; export RGPD, clé `amis` (des autres comptes, seulement le prénom).
- Hors de cette version : notifications push d'encouragement. Les défis entre amis sont arrivés en v53 (section suivante).
- Tests : `tests/test_amis.py` (33), `tests/e2e/test_amis_navigateur.py` (deux comptes amis + un non-ami), `tests/js/test_invitation.js` (5).

### Défis entre amis (v53, 26/10/2026)
- **Choix du propriétaire** : « Défis entre amis », **gratuit pour tous**. Lancés depuis `/amis` (section « Défis », formulaire « Lancer un défi »). Le défi de la semaine (`core/challenges.py`, carte de l'accueil) reste tel quel.
- **Trois types**, calculés depuis `history` à chaque affichage (`core/defis.score`) : **régularité** = séances faites pendant le défi (un couple date + nom de séance avec une vraie série, cardio compris, la définition de `core/hist`) ; **volume** = kg × reps des séries de travail (ni cardio, ni échauffement) ; **progression** = hausse en % de la meilleure charge sur un exercice. Le mouvement compte quel que soit le matériel, à l'orthographe près (`noms_exercices.meme_mouvement` après `separer_variante`). L'exercice est choisi dans l'historique du créateur (`defis.exercices_proposes`), revérifié par le serveur.
- **Référence de la progression** : la meilleure charge (reps ≥ 1, charge > 0, hors échauffement) des **28 jours avant le début** (début − 28 j inclus → veille du début). Sans série chargée de l'exercice sur ces 28 jours (ou seulement à 0 kg) : « Pas de référence » ; avec une référence mais rien depuis le début : « Pas encore fait ». Dans les deux cas, pas de score : classé à part, sans rang, jamais gagnant. Arrondi à 0,1 % (« +6,2 % », « −5 % »).
- **Durées** 1, 2 ou 4 semaines ; **début** aujourd'hui, demain ou lundi prochain (`defis.bornes`, fin = début + 7 × semaines − 1, contrainte en base). Le jour se compte à l'heure de Paris (`logical_today_paris`).
- **Invitations** : seulement des **amis acceptés** du créateur (sinon rien n'est créé, `defi_pas_ami`), 10 participants au plus, créateur compris. On accepte ou refuse **jusqu'au jour du début inclus** (`peut_repondre`) ; ensuite l'invitation disparaît et le défi tourne avec ceux qui ont accepté. Refuser efface la ligne. Le créateur peut inviter d'autres amis jusqu'au début, et annuler un défi pas encore commencé (il disparaît pour tous). 10 défis pas finis par compte.
- **Classement** (`defis.classement`) : participants acceptés, meilleur score d'abord ; **égalité au chiffre affiché = rang partagé** (1, 1, 3). **Gagner demande un score strictement positif** ; tous les premiers gagnent ensemble (« Égalité entre Marc et toi : 2 séances chacun. »), personne sinon (« Pas de gagnant »). En direct sur `/amis` et sur l'accueil (carte « Défis entre amis » : 2 défis en cours au plus, les 3 premiers + soi ; invitations à régler). **À la fin**, la carte « Défi terminé » et son annonce entrent dans le fil, à la date de fin, pour 30 jours, chez les participants seulement.
- **Qui voit quoi** (`core/db_defis.lire_defis`) : un défi n'est lu qu'à partir des lignes de participant du compte (un non-participant ne voit rien). **Un défi réunit son créateur et SES amis acceptés** : un participant qui n'est plus l'ami accepté du créateur en sort (il ne le voit plus, les autres ne le voient plus classé). Les participants se voient entre eux (prénom et score), même s'ils ne sont pas amis entre eux. Seuls les chiffres du défi : nombre de séances, tonnage, % de progression. **Ami aux séances masquées** : classé avec son score, mais sans aucun détail (le « N séances » à côté du score n'est montré que pour soi et les non-masqués) ; ses séances restent hors du fil (v52). Les invités sans réponse ne sont nommés qu'au créateur.
- **Le score n'est jamais stocké** : aucune colonne de score ; une séance effacée sort du score (testé). Une lecture de `history` pour tous les défis affichés (`db_defis.lignes_des_defis`, par lots de 100 comptes, sans `type_serie` si la v43 manque). Accueil sans défi : une requête de plus.
- **Base** (`supabase_schema_v53_defis.sql`) : `defis` (createur, type, exercice, semaines, debut, fin) et `defis_participants` (defi_id, user_id, etat `invite`/`acceptee`, repondu_le), fermées au navigateur comme v38/v52 (RLS active, aucune règle, droits à `service_role` seul) ; contraintes : type, durée, fin selon la durée, exercice ssi progression, un compte par défi, acceptée = datée ; cascades sur le compte et sur le défi. Rejouée deux fois sur PostgreSQL 16 (`test_les_defis_v53_tiennent_leurs_regles_en_base`). **Appliquée le 26/10/2026** (23:12 UTC, `20261026231211 v53_defis`, accord du propriétaire) et vérifiée : 2 tables, 14 colonnes (celles d'`ATTENDU`), RLS active sans règle, droits à `service_role` seul (aucun pour `anon`/`authenticated`), 13 contraintes, 0 ligne.
- **Sans la v53** : la page dit « Les défis arrivent bientôt », l'accueil n'affiche rien, `/admin` signale les tables (`core/schema.ATTENDU`).
- **Compte** : suppression = défis lancés (avec leurs participants) et participations (`db_defis.effacer_defis_du_compte`, appelée par `delete_user_account`) ; export RGPD, clé `defis` (type, dates, ma réponse ; des autres, le prénom seulement, pas leur score).
- **Limites** (par compte) : lancer 10/h et 30/j, inviter 30/h et 100/j. Événements `defi_lance`, `defi_accepte`.
- Hors de cette version : notifications push (« ton ami t'a dépassé »), récompenses (badges, jours PRO).
- Tests : `tests/test_defis.py` (35), `tests/e2e/test_defis_navigateur.py` (deux amis, défi lancé, accepté, classement qui bouge après une séance, page Amis et accueil), `tests/test_migrations_postgres.py` (v53).

### Nudge de relance (rétention, 2026-06-14)
- **Banner de retour** sur l'accueil : un user avec un historique mais inactif depuis ≥ `REACTIVATION_DAYS`=3 j (jours depuis la dernière perf réelle muscu/cardio) est accueilli par « Content de te revoir ! Ça fait N jours — on reprend en douceur ? » + bouton **Reprendre** (→ /seance). Dismissible (sessionStorage `reac_hidden`). Jamais pour un compte sans historique.
- Event `reactivation_nudge_shown` ({days}), émis seulement sur vraie navigation (Sec-Fetch-Mode navigate). Logique dans `routes/accueil.py`.
- **Phase 2 — Push web** (2026-06-15) : notifications push (VAPID + pywebpush) pour relancer ceux qui ne rouvrent pas l'app.
  - **Abonnement universel** (free + PRO) : bouton « Activer les notifications » dans Gestion (`static/js/push.js` → `window.enablePush`), + ré-abonnement silencieux à chaque page si permission déjà accordée. SW : handlers `push` + `notificationclick` (unifié, lit `data.url`). Stockage : table `push_subscriptions` (migration v30).
  - **Endpoints** `routes/push.py` : `GET /push/config` (clé publique + `enabled`), `POST /push/subscribe`, `POST /push/unsubscribe`. `core/push.py` : `send_push(sub, payload)` via pywebpush (retour `ok`/`expired`/`error`/`unconfigured`).
  - **Envoi** : logique unique `core/push.py:run_reactivation_push(min_days=3, max_days=30)` (hors contexte requête) → cible les inactifs 3–30 j abonnés (`db.get_inactive_user_ids`), envoie, supprime les abonnements expirés (410/404), émet l'event `reactivation_push_sent`. Deux déclencheurs :
    - **Manuel** : `POST /admin/send-reactivation` (bouton admin, inline-confirm).
    - **Cron** (2026-06-15) : `POST /tasks/reactivation` (public, CSRF-exempt, sécurisé par `CRON_SECRET` via l'en-tête `X-Cron-Secret` (seulement), comparaison à temps constant, 401 sinon). Ou script standalone `pwa/cron_reactivation.py` (`python cron_reactivation.py`) pour un service cron Railway sans HTTP. Planifier 1×/jour.
  - **Env Railway requis** : `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` (base64url), `VAPID_SUBJECT` (`mailto:…`), `CRON_SECRET` (pour l'endpoint cron HTTP). iOS : push seulement si l'app est installée (écran d'accueil).

### Partage de progression (croissance, 2026-06-14)
- **Carte partageable** : bouton « Partager ma progression » sur l'accueil (tous les users). `static/js/share-card.js` génère côté client une image (canvas 1080×1080 : streak/tonnage/séances/exos + branding) puis la partage via l'**API Web Share** (`navigator.share({files})` si supporté → sinon texte+lien → sinon téléchargement PNG + copie du lien, avec toast). Données injectées via `<script type="application/json" id="share-data">` sur l'accueil ; lien = `location.origin` (robuste aux domaines custom).
- **Tracking** : `POST /share/track` (`routes/share.py`) → event `progress_shared` ({kind, method}). CSRF auto (header X-CSRFToken injecté par base.html).

### Upsell post-win (conversion, 2026-06-14)
- **Paywall au bon moment** : un compte **free** qui atteint `UPSELL_AFTER_SESSIONS`=3 séances distinctes voit, **une seule fois**, une modale d'invitation PRO sur l'accueil (l'écran qui suit sa séance milestone → motivation haute). Distinct de la carte « Passe en PRO » discrète toujours présente en bas d'accueil.
- Logique 100 % dans `routes/accueil.py` (pas de modif de `/seance/finish`) : flag durable `prog._upsell_seen` (méta programme, pas de migration). Event `upsell_shown` ({trigger:"post_workout", sessions}) — un `premium_viewed` qui suit = clic sur la modale (mesure de l'efficacité dans le funnel). Jamais affiché aux VIP.

### Hors-ligne et Android (vague 4)
- L'accueil fait garder les séances prévues des 7 jours qui viennent (rotation comprise), plus la page de choix d'aujourd'hui et demain : 10 pages au plus. Le bouton « Commencer » de l'accueil (`next_session.lien`, avec `&prevue=` quand la séance est celle de demain) figure tel quel dans la liste : sans cela, le dimanche soir hors réseau, le bouton menait à une page jamais gardée (audit du 18/10, m2). offline.js ne relance qu'une fois par jour ou quand la liste change ; le service worker les demande une à une (limite de 60 req/min/IP, souvent partagée en salle), retente une fois à 20 s, et répond par MessageChannel ; la pastille « Séances de la semaine prêtes hors-ligne » ne s'affiche que si toutes sont gardées.
- Android : drapeau `MTAds.setInSession(true)` dès l'ouverture de la page de séance (plus de pub plein écran avant la première série) ; reprise de séance au démarrage à froid comparée à la journée logique locale (bascule à 4 h), plus à la date UTC.
- Cache serveur : une remise en cache plus vieille que la dernière invalidation de la clé est refusée (core/db_base.py) ; `vider_cache()` pour tout purger.

### Essai PRO et bilan du mois
- L'essai (`vip_until`, `g.is_vip` sans `is_vip_full`) ouvre le coach (5 messages/jour, `ESSAI_QUOTA`) et le debrief après chaque séance, en plus de la nutrition et des stats ; le générateur et les programmes avancés restent à l'abonnement.
- **Essai de la première séance** (`core/essai.py`, 24/10, audit du 18/10 I-4) : un compte gratuit qui n'a jamais eu d'essai (`vip_until` vide) reçoit **3 jours** (`ESSAI_JOURS`) quand il termine une séance avec au moins une série (`/seance/finish`). Effet immédiat (session mise à jour : le debrief de l'écran suivant est le complet), carte « ESSAI PRO OFFERT » une fois sur l'accueil, event `trial_started` (`source: premiere_seance`). Un essai fini (parrainage compris) laisse sa date passée : il ne se rouvre pas. Avant, l'essai ne s'ouvrait que par parrainage : 0 essai, 0 paiement en production.
- Effectif depuis le 09/10/2026 seulement (v29, voir « Parrainage »).
- Page Plus, membre PRO : « Ce mois-ci avec PRO » (core/bilan_pro.py) — debriefs, messages au coach, programmes générés, séances refaites (événements sur 30 jours) et records battus (historique).

### Progression racontée et charge de départ
- Accueil, carte « Tes progrès » (core/progression.py) : meilleur des 2 dernières semaines vs meilleur de 3 à 8 semaines avant, par exercice ; charge, ou reps au poids du corps ; gains nets seulement (≥ 2,5 kg / ≥ 2 reps), les 2 plus forts en relatif.
- Séance, première fois sur un exercice (`conseil_depart`, core/muscu.py) : une méthode, pas un chiffre tiré du poids de corps — barre vide pour un mouvement à la barre, sinon RPE 6-7, réserve de reps au poids du corps. Tient sur la ligne « Première fois » (le premier champ doit rester dans le premier écran, test e2e).
- **Boutons − / +** (14/10, maquette B) : la série en cours montre la charge puis les reps, chacune entre un − et un + ; le chiffre reste un champ (`aria-label` « Poids série N » / « Répétitions série N » inchangés). `ajuster(s, champ, sens)` (`static/js/seance.js`) part de la valeur montrée : tapée, sinon grisée (objectif, charge proposée), comme « Série faite ». Reps ± 1. Charge : la charge d'à côté déjà soulevée sur l'exercice si elle est à un pas et demi au plus, sinon un pas de plus ; le pas est l'écart le plus fréquent entre deux charges voisines de l'historique (`core/seance_charges.echelle_charges`, envoyé dans `echelle` avec la carte et par `/seance/api/variant-history`), 2 kg aux haltères et 2,5 kg sans historique. Des `<div>` et pas des `<label>` autour : un label renvoie son clic au premier bouton qu'il contient. Une carte faite mais ouverte n'est plus grisée (`.exo-card.done.ouverte`).
- Mouvement à la barre jamais fait : le poids des séries part de 20 kg (`core.muscu.charge_de_depart`, appelée par `core/seance_contexte.py`), la barre vide que la carte conseille. « Série faite » était refusé au premier tap (audit du 06/10, profil 1). Désactivé avec le réglage « Pré-remplir les charges ».

### Semaine allégée (core/decharge.py)
- Proposée sur l'accueil quand, après ≥ 4 semaines d'affilée sans semaine déjà allégée, l'e1RM de la dernière semaine complète recule de ≥ 3 % sur plusieurs exercices et/ou le RPE moyen atteint 9 (deux signes, ou un recul sur ≥ 3 exercices).
- `POST /accueil/decharge` : `appliquer` pose `_decharge_semaine` (séries ÷ 2, charges suggérées et pré-remplies −10 %, pour les séances de cette semaine seulement), `ignorer` pose `_decharge_ignoree`, `annuler` retire. Clés personnelles du blob. Le coach est prévenu.

### Séries par muscle et par semaine (core/volume_muscle.py)
- Page Progrès, pour tous : séries faites cette semaine par muscle (principal 1, secondaires ½, hors cardio/SESSION/SKIP), face au repère 10-20 (6-16 pour les petits muscles), avec la semaine passée. La carte du corps PRO garde la part relative.

### Onglet « Corps » : poids et photos de progression (18/10/2026)
- **Progrès a deux onglets** (`templates/_progres_onglets.html`) : « Entraînement » (`/progres`, sans la carte du poids) et « Corps » (`/progres/corps`, `routes/corps.py`, `templates/corps.html`). Demande du propriétaire : Progrès était trop chargé, et « en ajoutant les photos on ne pense pas forcément à se peser » ; le poids et les photos sont donc au même endroit. La carte « Poids corporel » (`templates/_poids_carte.html`, calcul `core/poids_courbe.carte_poids`, inchangé) reste gratuite ; les photos sont PRO (aperçu verrouillé sinon). Une pesée revient sur `/progres/corps#poids` (ou `#photos` avec `retour=photos`). Liens vers le poids (accueil, nutrition) : `/progres/corps#poids`. L'ancienne adresse `/progres/photos` redirige vers `/progres/corps…#photos`.
- **Poids sous les photos** (choix du propriétaire) : la pesée du jour de la photo, sinon **la dernière d'avant, avec sa date** (« 91,2 kg (pesée du 16/10) », `photos_corps.pesee_pour`) ; rien n'est inventé dans la courbe. Si les deux photos comparées reprennent la même pesée, pas d'écart de poids affiché.
- **Invitation à se peser** (`photos_corps.pesee_manquante`) : une par date, pas par photo ; pour la photo la plus récente (7 jours au plus) sans pesée ce jour-là. Noter le poids (formulaire daté du jour des photos) ou « Garder la dernière pesée » (rien n'est écrit ; l'invitation se tait pour cette date sur cet appareil, `localStorage`).
- Photos : choix faits avec le propriétaire : sur le serveur, en privé ; face / profil / dos ; avant / après ; poids ; rappel toutes les 4 semaines.
- **Stockage** : table `photos_corps` (migration **v50** : date, angle, `chemin`, `miniature`, `octets` ; une photo par angle et par jour, en reprendre une la remplace) et dossier **privé** `photos-corps` de Supabase Storage, fichiers sous `<user_id>/`. Aucune règle pour le navigateur : seul le serveur (service_role) lit et écrit, et ne sert un fichier qu'après avoir retrouvé sa ligne chez le compte connecté (`core/db_photos.py`). 400 photos par compte, 2 Mo par fichier, JPEG seulement (`est_jpeg`).
- **Envoi** (`static/js/photos.js`) : la photo est redessinée dans un canevas avant l'envoi, 1 600 px au plus (JPEG 0,82) + miniature 400 px : elle perd ses métadonnées, donc la position GPS (test navigateur : un bloc EXIF « GPSLatitude » envoyé ne revient pas). `POST /progres/photos` (multipart, JSON en retour). **Le serveur ne fait plus confiance au canevas** (audit du 18/10, m12) : `core/photos_corps.sans_metadonnees` parcourt les segments du JPEG en Python pur (Pillow n'est pas en production) et retire APP1 (EXIF, XMP), APP13 (IPTC), les commentaires et l'index MPF, coupe tout ce qui suit la fin de l'image (seconde image MPF), garde le profil couleur ; un JPEG mal formé est refusé (400). Tests : `test_la_position_gps_ne_reste_pas_dans_la_photo`, `test_une_seconde_image_collee_apres_la_fin_part_aussi`, `test_un_jpeg_mal_forme_est_refuse`.
- **Lecture** : `GET /progres/photos/<id>/image[?mini=1][&telecharger=1]`, `Cache-Control: private, no-cache` + ETag (304 sans relire le fichier) : un autre compte ouvert ensuite sur le même téléphone ne peut pas revoir la photo depuis le cache. Ouvert au propriétaire même redevenu gratuit (télécharger, supprimer : l'export RGPD liste les photos avec ces liens). La page et l'ajout sont PRO (essai compris, `g.is_vip`).
- **Comparaison** par l'adresse (`/progres/corps?angle=face&avant=12&apres=40`), sans script : première et dernière photo de l'angle par défaut, « Avant / après · 8 semaines · −3,2 kg ».
- **Suppression** : fichiers d'abord, ligne ensuite (un fichier qui résiste garde la ligne : on peut réessayer). Suppression du compte : `supprimer_toutes_les_photos` en premier dans `delete_user_account`, **sans repli** : un fichier qui résiste arrête tout, sinon la ligne partirait avec le compte (clé étrangère) et la photo resterait sur le serveur sans rien qui la rattache.
- **Rappel** (`core/rappel_photos.py`, appelé par `/tasks/reminders` et `cron_reminders.py`) : compte PRO aujourd'hui (`comptes_pro`), notifications activées, dernière photo à 28, 56 ou 84 jours ; à son heure de rappel de séance (18 h par défaut). Sans état : une nouvelle photo remet le compte à zéro.
- Sans la v50 : l'onglet Corps garde le poids et dit « les photos arrivent bientôt », l'ajout répond 503, /admin signale la table.
- Après un ajout, la page se recharge même quand l'adresse de retour est la sienne au `#photos` près (`location.reload()`) : changer seulement le fragment ne fait que défiler, la nouvelle photo n'apparaissait pas (trouvé par le test navigateur, vu échouer avec l'ancien script).

### Progression
- **Calendrier mensuel** : cases colorées (vert plein = fait, pointillés orange = manqué, gris clair = à venir), navigation mois, taux d'assiduité, tolérance + rattrapage des séances ratées
- **Taux d'assiduité** : séances faites ÷ séances **échues** (passées, ou faites d'avance). Avant le 18/10, le dénominateur comptait tout le mois : le 1er, un mois parfait affichait 7 % (audit du 18/10, m1).
- **Volume par semaine** : graphique SVG verrouillé (8 dernières semaines)
- **Body map** : carte musculaire SVG interactive (polygones depuis `core/body_map.py`) avec % de standard
- **Standards de force relatifs au gabarit** (`core/strength.py`) : les paliers sont des multiples du poids de corps par muscle et par sexe (bornés 35–200 kg), pas des valeurs absolues — 60 kg au développé ne veut pas dire la même chose à 55 kg qu'à 95 kg. Repli absolu si le poids est inconnu.
- **Hall of Fame** : top 3 exercices par 1RM
- **Fiche par exercice** (`/progres/exercice?exo=…&variante=…&m=…&p=…`, `templates/exercice.html`, `core/exercise_stats.py`) : records, courbe par mesure (1RM estimé, charge, volume, répétitions) sur une période choisie, tendance, comparaison avec la période d'avant, records par répétitions, toutes les séances, table des RM (PRO). **Un équipement à la fois** (11/10) : la fiche s'ouvre sur l'équipement le plus pratiqué (pastilles en tête, `variante=tous` pour tout voir), comme Hevy et Strong — 40 kg aux haltères ne sont pas 40 kg à la barre. La liste « Suivre un exercice » de Progrès donne chaque mouvement une fois (avant : une ligne par équipement). Courbes en **SVG maison** — Plotly (≈3 Mo depuis un CDN) a été retiré. Détail : « Courbe de force » ci-dessous. **Style « Instrument »** (13/10) : la force estimée (1RM) en très grand avec, à droite, sa progression depuis la première séance (« +18 % depuis le 4 mai », vert si elle monte) ; trois cases Charge max / Volume max / Total (au poids du corps : Meilleure série en grand, puis Répétitions / Séances / Dernière) ; mesures en quatre boutons égaux (le choisi en blanc) ; courbe blanche, records en points verts. Filtre Jinja `jour_mois` (« 4 mai »).

### Streak
- Affiché en gros sur l'accueil avec icône flamme
- Paliers : 🥉 Bronze (4 sem), 🥈 Argent (8), 🥇 Or (12), 💎 Diamant (24)
- Record personnel : `etat_compte.record_serie` (v47), lu sous `prog["_streak_record"]`
- État « en danger » (orange + pulse) si séance du jour non faite

### Mode Offline
- Bandeau « Mode hors-ligne » affiché automatiquement
- Les formulaires de séance sont interceptés et stockés dans localStorage (écoute en phase **bulle** : en phase capture, une série était mise deux fois en file)
- Synchronisation **séquentielle** (`_sync` + `step()` récursif), avec toast typé. Une synchronisation demandée pendant qu'une autre tourne attend la même (« Terminer » sait quand elle finit).
- **Nouvel essai automatique** (11/10) : après un échec réseau, la file réessaie seule à 3 s, 6 s, 12 s… plafonnée à 30 s, et tout de suite quand l'app revient au premier plan (`visibilitychange`) ou que le réseau revient. Avant, elle n'attendait que le prochain chargement de page.
- Badge orange « X envoi(s) en attente » en bas à droite : seulement hors ligne ou après un échec réel (`essais > 0`), pas pendant la seconde où une série part
- **Séance d'un autre jour** (audit du 06/10, I-1) : la page de séance gardée pour un jour à venir s'ouvre pour AUJOURD'HUI. En ligne, `jour-seance.js` la rouvre avec `date=aujourd'hui&prevue=…` (bandeau « EN AVANCE ») ; hors ligne, il réécrit la date de la page avant que seance.js la lise. Le serveur refuse de son côté toute date postérieure à aujourd'hui (`save-exo`, `add-cardio`, `cardio/save` : 400 ; `finish` : retour à l'accueil sans bilan). La carte « Prochaine séance · Demain » mène à « Faire maintenant », daté d'aujourd'hui.
- **La séance du jour est pré-chargée** : le SW reçoit un message `PRECACHE` avec ses URLs, donc en sous-sol on ouvre sa séance au lieu d'être renvoyé sur une page d'erreur. `CACHE_VERSION` en tête de `static/service-worker.js`.

### Notifications
- **Universelles (free + PRO)** depuis 2026-06-15 : la case « Notifications de rappel & relances » dans Gestion n'est plus réservée au VIP (rétention = on veut surtout faire revenir les gratuits). Un seul contrôle : cocher la case demande la permission ET abonne au push (`handleNotifToggle` → `window.enablePush`).
- Rappels **locaux** : retirés le 30/09 (ils ne se déclenchaient jamais — script exécuté avant le chargement de notifications.js, audit R4 — et n'auraient prévenu que quelqu'un qui regarde déjà l'app). Seuls les rappels serveur (core/reminders.py) existent.
- **Rappel de séance à l'heure choisie** (`core/reminders.py`) : réglage `reglages.reminder_hour` (6→22 h, 0 = aucun) dans Gestion. `POST /tasks/reminders` (même secret `CRON_SECRET`) est appelé **toutes les heures** par un cron externe et ne notifie que les comptes dont l'heure correspond ET qui ont une séance prévue non faite. Script équivalent : `pwa/cron_reminders.py`.
- Relances **push** de réactivation (inactifs 3–30 j) : cf. section « Push web » plus haut. Au plus 3 relances par arrêt, espacées d'au moins 4 jours (`push_subscriptions.last_reactivation_at` / `reactivation_count`, migration v34) ; une relance antérieure à la dernière séance appartient à un arrêt terminé et ne compte plus (audit du 30/09, I14).
- Désactivable dans Gestion > Paramètres.

### Récap de la semaine (core/recap.py)
- Le dimanche à 19 h, le cron horaire des rappels (`/tasks/reminders`, `cron_reminders.py`) envoie un push : séances faites, volume, écart avec la semaine d'avant, prochaine séance prévue (rotation comprise). Hors de ce créneau, l'appel ne fait rien.
- Seulement à qui s'est entraîné dans la semaine et a les notifications ; coupable dans Gestion (`reglages.recap_hebdo`, vrai par défaut). Lecture groupée : `history_between_for_users` par lots de 100 comptes.

### Pré-lancement : sélection texte + chrono notif natif (2026-06-16)
- **Texte non sélectionnable** : `theme.css` pose `user-select:none` + `-webkit-touch-callout:none` sur `body` (supprime le menu « Rechercher sur le web » au clic long en webview Android). Réactivé sur `input/textarea/select/[contenteditable]/.selectable`. Déployé par Railway → corrige l'app native **sans rebuild**.
- **Notif de fin de repos fiable** : le chrono (`seance_edit.html`) planifiait la notif via un `setTimeout` dans le service worker → tué en arrière-plan = notif parfois manquante. Ajout de `@capacitor/local-notifications` (plugin natif) : en app native, la notif est planifiée par l'**OS** (`LocalNotifications.schedule({at})`, fiable même app fermée) ; le SW reste le fallback web. Cancel sur fin/skip (SW + natif). **Nécessite rebuild AAB.** Permission via `requestPermissions()`.
- **Fin du repos écran éteint, sur le web** (14/10, `core/push_repos.py`) : dans l'app installée depuis Chrome, les minuteurs du téléphone (page, service worker) gèlent avec l'écran. À chaque repos, `rest-timer.js` annonce `POST /push/repos {endpoint, dans, nom, url}` (fetch keepalive) ; le serveur relit l'abonnement en base (ses appareils seulement), et un fil d'arrière-plan envoie le push à l'heure : `Urgency: high`, durée de vie 120 s, tag `rest-timer`. Un nouveau repos remplace le précédent (sans annulation envoyée avant : elle pourrait arriver après) ; « Passer » et la fin de séance appellent `/push/repos/annuler`. Jeton dans `core/partage.py` : une annulation reçue par une autre instance est respectée. Au plus 15 min. Le service worker affiche la notification en vibrant ; app à l'écran, il l'affiche sans bruit puis la retire (Chrome exige une notification par push). Sans abonnement push (notifications refusées) ou en app native : rien n'est envoyé.
- **Compte à rebours vivant dans la barre de notification** (app native, 2026-09-24) : comme le minuteur de l'Horloge, les chiffres défilent même app fermée. `RestTimerNotification.java` pose une notification `setUsesChronometer` + `setChronometerCountDown` avec une **échéance absolue** ; c'est le SYSTÈME qui anime le compteur. Donc **aucun service en premier plan** : rien de notre code ne tourne pendant le repos, le compteur reste juste même si Android tue le processus, zéro batterie, et rien à justifier auprès de Play. Pont `window.MTTimer.start(échéance, exercice)` / `.stop()` (MainActivity), appelé par `rest-timer.js` à chaque départ de repos et reposé à la reprise (`_adopt`). **Impossible sur le web** : aucune API ne permet de faire défiler une notification — c'est la seule fonction qui justifie encore la coquille native.

### Défis hebdo (rétention, 2026-06-16)
- `core/challenges.py` : un défi **tournant** choisi par l'index de semaine continu (`continuous_week`) → identique pour tous, change chaque lundi. Évalué **depuis l'historique normalisé** (clés Date/Séance/Exercice/Poids/Reps/Semaine), aucune donnée stockée pour l'évaluation. `weekly_challenge(hist, today, prog)` → dict {id, title, emoji, desc, current/target(+_fmt), pct, done}.
- Cycle actuel : séances / volume / nouvel exercice / 1 cardio / battre le volume de la semaine passée.
- **Cibles relatives** : le défi des séances vise les séances prévues de la semaine (planning + rotation) ; le volume, la moyenne des semaines actives parmi les 4 précédentes + 5 % (arrondi 500 kg, ou 10 reps au poids du corps). Repli sur 3 séances / 10 000 kg / 300 reps sans planning ni historique.
- **Accueil** (`routes/accueil.py`) : carte « Défi de la semaine » avec barre de progression. Validation consommée **uniquement sur vraie navigation** (pas prefetch) → incrémente `prog._challenges_won`, mémorise la semaine dans `prog._challenges_done`, émet l'event `challenge_completed`, affiche l'état « ✅ Défi validé ». Aucune migration.
- Suite : relance push « plus qu'1 séance pour valider », objectifs perso. Le classement entre amis existe depuis la v53 (« Défis entre amis »).

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
- **Gestion** : « Exporter tout » (historique, programme, profil, pesées, bilans, nutrition, coach) — **gratuit** (RGPD) ; la réimportation et l'export du programme seul sont PRO
- **Gestion** : « Importer » un fichier JSON (avec confirmation modale) — gated VIP
- **Programme** : export/import du programme
- **Page Programme** (style « Instrument », 13/10) : « Ma semaine » en sept cases (blanche avec le nom de la séance écrit à la verticale, un trait pour le repos) ; chaque case couvre son vrai menu `<select data-day>` rendu invisible : toucher la case ouvre le menu du téléphone, `x-model` et `syncPlanningSelects` sont inchangés. « Alterner » est un interrupteur (`role="switch"`). Programmes et séances en lignes à filet ; sous chaque séance « 3 exercices · 10 séries · pecs, épaules » (`resumeSeance`, `static/js/programme.js`, testé dans `tests/js/test_programme.js`) ; ajout de séance ou de programme dans un cadre en pointillés
- Format JSON, fichier nommé `muscu-tracker-backup-YYYY-MM-DD.json`

### Onboarding
- 4 étapes : Identité → Niveau → Objectif → Programme
- 20 programmes au catalogue (`core/catalog.py`), dont 5 gratuits, regroupés par niveau (débutant / intermédiaire / avancé)
- Cartes enrichies : icône, étoiles de difficulté, durée, muscles tags, badge Free/PRO
- Tooltips « ? » sur les niveaux, preview modale des séances avant choix
- Bouton retour fonctionnel à chaque étape

### Aide du premier jour (bulles, audit du 18/10, m9)
- **Quatre bulles au plus, chacune au moment où elle sert** (14 avant : 6 sur l'accueil pour présenter les onglets, 8 d'affilée avant la première série ; retours d'utilisateurs : app peu claire au premier abord).
- **Accueil** (`tutorial.js`, `/accueil` seulement) : une bulle sur le bouton de la carte « Prochaine séance » ; son bouton porte le même mot (« Commencer ») et **ouvre la séance**. Sans carte : une bulle centrée qui nomme les onglets. Clé `tutoSeen`.
- **Séance** (`tuto-seance.js`) : 1. à l'arrivée, la série en cours et « Série faite » ; 2. après la première série faite, le repos (bulle posée sur la barre du chrono) et la série suivante prête ; 3. après le premier exercice fini, « Exercice suivant » et « Terminer la séance ». `seance.js` émet `seance:serie-faite` et `seance:exercice-fini`. Clé `tutoSeanceSeen` : "1"/"2" = bulles vues, "true" = fini ou « Passer » touché. Arriver en séance pose aussi `tutoSeen`.
- Moteur (`tuto-engine.js`) : `onFinish(comment)` reçoit "bouton", "voile" ou "passer" ; `action` sur la dernière étape n'est lancée que par son bouton. Plus › Gestion : « Revoir l'aide de l'accueil / de la séance » efface la clé.
- Preuves : `tests/e2e/test_premier_jour.py` (parcours complet : 4 bulles, puis plus rien), `tests/js/test_tuto_seance.js` (ordre, exercice d'une série, « Passer », stockage refusé, relance).

### Catalogue de programmes (20, dont 5 gratuits)
- Plusieurs splits : Full Body, PPL, Upper/Lower, Bro Split, Home, etc.
- Gating Free / PRO selon le programme (les programmes avancés sont VIP)
- `build_program` garde **toutes** les séances du catalogue, quelle que soit la fréquence (on tronquait : un PPL sur 2 jours perdait Legs).

### Rotation des séances (`prog._rotation`, core/rotation.py)
- Liste des séances dans l'ordre du cycle. Les jours d'entraînement restent ceux de `_planning` (jour non vide) ; chaque jour prend la séance suivante du cycle, d'une semaine à l'autre : A/B sur Lun-Mer-Ven donne A B A, puis B A B.
- Posée par le catalogue quand le nombre de jours n'est pas un multiple du nombre de séances ; réglable sur la page Programme (case « Alterner les séances d'une semaine à l'autre »). Suit les renommages et suppressions, voyage avec l'export/import.
- Le rang d'un jour ne dépend que du calendrier (semaines depuis `_started_at`, le premier jour d'entraînement à partir de cette date ouvre le cycle), pas de l'historique : accueil, choix de séance, calendrier Progrès, rappel du soir et coach lisent tous `seance_prevue(prog, date)`. Ne jamais relire `_planning[jour]` directement pour savoir ce qui est prévu un jour donné.
- Sans `_rotation` valide (moins de deux séances existantes), comportement inchangé.

### Admin
- Routes : `/admin` (dashboard), `/admin/funnel` (conversion), `/admin/set-tier`, `/admin/user/<id>`, `/admin/reset-quota`
- Accès filtré par `ADMIN_EMAILS` env **et** connexion Google (404 sinon, `core/admin_acces.py`) : l'adresse vient du jeton Supabase, que d'autres méthodes de connexion peuvent produire. Le fournisseur est lu dans le jeton à `/auth/session` ; une session plus ancienne doit se reconnecter.

### Analytics produit / Funnel de conversion (2026-06-14)
- **Auto-hébergé sur Supabase** (table `events`, migration `supabase_schema_v28_events.sql`) — pas de tiers (PostHog/Mixpanel), donc pas de bannière de consentement ; écriture côté serveur en `service_role`.
- **Façade** : `core/analytics.py` → `track(event, props, user_id=, tier=)` **fire-and-forget** (n'échoue JAMAIS la requête, lit `g.user_id`/`g.is_vip` par défaut ; `user_id` explicite hors contexte requête = webhook Stripe). Helper `paywall(feature, status=200)` = loggue `paywall_viewed` puis rend `vip_wall.html` (centralise l'instrumentation des ~7 points de blocage VIP).
- **Events du funnel** : `onboarding_completed` (onboarding submit), `workout_finished` (séance finish), `premium_viewed` (page Premium vue par un free), `paywall_viewed` (helper `paywall`), `checkout_started` (billing checkout créé), `vip_activated` (dans `_activate_vip`, couvre success + webhook), `vip_refunded` / `stripe_dispute` (remboursement total, litige ouvert ou gagné), `coach_message` (coach/ask, après quota OK).
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
- `CSP_OBSERVER` — à `1`, la CSP complète repasse en observation (Report-Only) et seule la couche sûre bloque : le retour arrière si un blocage gênait en production. `CSP_DISABLED=1` retire toute CSP. (`CSP_ENFORCE` n'existe plus : la CSP bloque par défaut depuis le 10/10.)

### État du compte (table `etat_compte`, v47)
- Badges (`_badges`), record de série (`_streak_record`), défis (`_challenges_done`, `_challenges_won`), « upsell vu », quota de debrief gratuit (`_debrief_free`), semaine allégée (`_decharge_semaine`, `_decharge_ignoree`), plats de la semaine (`_meal_plan`), cibles nutrition perso (`_nutrition`) et, depuis la v51, réglages des machines (`_reglages_machines`) : **une ligne par compte, une colonne typée par donnée**, plus dans le blob.
- **Colonne arrivée après la v47** (`REPLI_PROGRAMME`) : tant qu'elle est NULL, le reste du programme fait foi et la première sauvegarde l'y range (sinon `superposer` effaçait les réglages d'un compte qui avait déjà sa ligne). **Fusion clé par clé** (`FUSION_PAR_CLE`) : deux requêtes qui notent deux machines gardent les deux, comme la fusion du programme. **Ordre de la v51** : partie 1 (colonne) AVANT le déploiement — une colonne absente passerait pour une table absente et tout l'état retomberait sur le programme ; partie 2 (copie puis retrait du programme) APRÈS.
- **Conversion à la frontière** (`core/db_etat.py`) : `get_prog` superpose ces valeurs sous leurs anciennes clés (les lecteurs ne changent pas) ; `save_prog` les extrait du programme et les range en table. Une écriture qui passe par le programme atterrit donc quand même dans la table. **L'état lu est copié** (`superposer` et `etat_lu`) : sans copie, une valeur modifiée en place (`liste.append`, `dict[clé] = …`) se comparait à elle-même et n'était jamais écrite dès que le compte avait sa ligne — en production du 06/10 au 18/10 : défi validé à chaque visite, aperçu gratuit du debrief jamais décompté, cible calorique perdue (audit du 18/10, C1). La fausse base des tests rend désormais des copies, comme PostgREST.
- **Concurrence** : `save_prog` n'écrit que les colonnes que la requête a changées depuis SA lecture (base gardée dans `g`, comme le programme), par-dessus la ligne relue fraîchement. A grave un badge, B enregistre ses plats avec un état lu avant : le badge reste (`tests/test_etat_compte.py`).
- **Base en retard** : table absente = tout reste dans le programme, table redemandée chaque minute. Sans ligne, un reste du blob fait foi et la première sauvegarde le range en table.
- Les lecteurs bruts (`lire_prog`, `list_all_programs`, crons) ne voient pas cet état : aucun n'en a besoin.

### Réglages utilisateur (table `reglages`, v45)
```python
# Valeurs par défaut : core/db_reglages.py:DEFAUTS (les mêmes en base)
{
    "auto_rest_timer": True,      # Chrono de repos à « Série faite »
    "auto_prefill_weight": True,  # Pré-remplir les charges de la dernière fois
    "show_rpe": True,             # Puces RPE dans le détail d'une série
    "show_overload_hint": True,   # Suggestion de surcharge
    "notifications": False,       # Rappels, relances et récap
    "reminder_hour": 18,          # Heure du rappel push (6-22, 0 = aucun)
    "recap_hebdo": True,          # Récap du dimanche
}
```
- **Depuis la v45**, une ligne par compte dans `reglages` (une colonne typée par réglage, pas de ligne = défauts), et plus dans `programs.data['_settings']`. Lecture `db.lire_reglages(uid, prog)` / façade `data.get_reglages(prog)` ; écriture `db.ecrire_reglages` / `data.save_reglages` ; crons : `db.reglages_pour(progs)`, une requête par lot de 100.
- **Base en retard** : table absente = lecture et écriture dans le blob comme avant, table redemandée chaque minute (`REESSAI`). Tant qu'un compte n'a pas de ligne, un reste de `_settings` dans son programme fait foi.
- **Retirés en v45** : « Replier automatiquement », « Afficher l'estimation 1RM », « Animations du thème » (vendu PRO) et « Semaines précédentes affichées ». Rien ne les lisait ; `tests/test_reglages.py` empêche leur retour sans usage.

### Semaine continue (migration 2026-06-10)
- `Semaine` est un **index continu** ancré au lundi 2024-01-01 (`core/dates.py:continuous_week`), recalculé **à la lecture** depuis `Date` dans `db.get_hist()` — la colonne `semaine` stockée (n° ISO legacy) n'est plus une source de vérité.
- Les opérations ciblées (`replace_exo_rows`, `delete_exo_rows`, `delete_session_rows`) ciblent la **date exacte** (`.eq("date", date_str)`) — ni la colonne `semaine`, ni une plage lun→dim. La plage effaçait la séance précédente dès qu'on refaisait la même séance dans la semaine, ce qui concernait 9 des 20 programmes du catalogue (dont les trois programmes débutants par défaut).
- Le n° affiché à l'utilisateur reste **relatif** au début du programme (`_display_week` / `_rel_week`).
- Raison : le n° ISO recommençait chaque année → collision des données au-delà d'un an, streak/« dernière fois » cassés au Nouvel An.

### Migrations Supabase
- Le code a **toujours un repli** quand une colonne manque (upsert sans la colonne, warning loggué). Depuis le 09/10, `core/schema.py` compare au démarrage la base à `ATTENDU` (une lecture par table) : colonne absente = journal ERREUR « schéma : colonnes absentes en base » et carte rouge dans /admin (revérifiée toutes les 10 min). Une migration ajoutée doit l'être aussi dans `ATTENDU` : `tests/test_schema.py` lit les fichiers SQL et le vérifie.
- Dernières : **v34** (session_id + rpe sur `history`, index `(user_id,date)`, table `session_notes`, `push_subscriptions.last_reactivation_at`), **v35** (`session_notes.duration_min`), **v36** (`profiles.coach_memory`), **v37** (vue `user_last_activity` réservée au serveur), **v38** (plus aucune règle ni droit côté navigateur : sans elle, un compte gratuit pouvait se passer `tier='vip'` depuis la console), **v39** (vue d'agrégats de la console admin). ⚠ v37-v39 conditionnent la sécurité : vérifier qu'elles sont appliquées (requêtes en fin de v38). Puis v40 à v47 (voir l'arborescence), toutes appliquées.
- **v29** (parrainage, essai) : appliquée le **09/10/2026** seulement, vérifiée par `information_schema`.
- **v00** (`supabase_schema_v00_base.sql`, 10/10/2026) : le socle d'origine (profiles, programs, history, onboarding, coach_messages, `handle_new_user` et son déclencheur), créé à la main dans Supabase avant la v23, reconstitué depuis la production. Inutile en production (tout y est) ; il permet de reconstruire une base vide. **La CI rejoue v00 puis v23 → v53 sur un PostgreSQL 17 neuf** (deux fois : chaque migration doit se rejouer), vérifie que chaque colonne de `core/schema.ATTENDU` existe et qu'une inscription crée encore profil et programme après la v48 (`tests/test_migrations_postgres.py`, lancé si `PG_TEST_URL` est défini ; décor Supabase minimal dans `tests/sql/supabase_minimal.sql`). Toute nouvelle migration doit garder le numéro unique et rester rejouable.
- **v25** (`supabase_schema_v25_vip.sql`) : restée hors de la production jusqu'au 10/10 (contrainte `profiles_tier_check` et index `profiles_tier_idx` absents, vu en comparant à la base rejouée). **Appliquée le 10/10/2026** (14:31 UTC, `20261010143152 v25_vip`) et vérifiée : contrainte et index présents, 15 profils inchangés (7 `free`, 8 `vip`).
- **Replis bruyants** (10/10) : chaque repli « colonne absente » de la couche données (profil, identité d'exercice, état, calques, réglages, nutrition, abonnement) appelle `core/schema.signaler(e, table)` : journal ERREUR une fois et carte rouge dans /admin, comme le contrôle du démarrage. Avant, ces replis ne disaient rien (audit 4.3).
- **v48** (`supabase_schema_v48_durcissement.sql`) : retire à `anon`/`authenticated` le droit d'appeler `handle_new_user()` (alerte Supabase 0028/0029) et efface `_profiles`/`_active_profile` des programmes. Rejouée sur un PostgreSQL 16 local (inscription intacte, idempotente). **Appliquée le 10/10/2026** (11:46 UTC) et vérifiée : plus aucun rôle n'a `execute` sur `handle_new_user()`, les alertes 0028/0029 ont disparu de `get_advisors`, 0 programme avec ces clés (9 nettoyés, version +1 chacun), déclencheur `on_auth_user_created` toujours actif.
- **v50** (`supabase_schema_v50_photos_corps.sql`, 18/10) : table `photos_corps` (une photo par angle et par jour, contrainte `photos_corps_un_par_angle_et_jour`), index `(user_id, date desc)`, fermée au navigateur, effacée avec le compte ; dossier Storage `photos-corps` privé, 2 Mo, `image/jpeg` (créé seulement si le schéma `storage` existe : la CI rejoue sur un PostgreSQL nu). Rejouée deux fois sur un PostgreSQL 16 local avec un faux schéma `storage` : dossier privé créé puis mis à jour, doublon du même jour refusé, angle inconnu refusé, `anon` et `authenticated` refusés, cascade à la suppression du compte. **Appliquée le 18/10/2026** (01:09 UTC, `20261018010915 v50_photos_corps`, accord du propriétaire) et vérifiée : 8 colonnes, RLS active sans politique, droits à `service_role` seul, 8 contraintes, dossier `photos-corps` privé (2 Mo, `image/jpeg`), aucune règle Storage sur ce dossier, 0 ligne.
- **v49** (`supabase_schema_v49_aliments_perso.sql`, 12/10) : table `aliments_perso` (nom, `food` pour 100 g, `recette` facultative), index `(user_id, updated_at desc)`, fermée au navigateur, effacée avec le compte (clé étrangère + `delete_user_account`). Rejouée deux fois sur un PostgreSQL 16 local : `service_role` écrit, `anon` et `authenticated` refusés, nom vide refusé, cascade à la suppression du compte. **Appliquée le 13/10/2026** (accord du propriétaire) et vérifiée : 7 colonnes, RLS active sans politique, droits à `service_role` seul, 0 ligne ; le contrôle du schéma au démarrage compte 17 tables.

### Tests (pwa/tests)
- `cd pwa && python -m pytest tests -q` — **1 894 tests** au 26/10/2026, défis compris (dont 59 tests navigateur dans `tests/e2e/`, Playwright + Chromium, ignorés s'ils manquent, et 6 sur un vrai PostgreSQL avec `PG_TEST_URL` ; la suite JS compte 169 tests). Le décor des tests navigateur (serveur, Chromium **à l'heure de Paris** : le jour de la séance vient du téléphone, un Chromium à l'heure UTC contredisait le serveur entre 4 h et 6 h) est dans `tests/e2e/conftest.py` ; `tests/e2e` est un paquet, sinon son `conftest` masquerait celui de `tests/`. Playwright : `wait_for_function` reçoit une **fonction** (`"() => …"`), une expression passerait par `eval`, que la CSP refuse. Le serveur des tests navigateur tourne avec `SANS_LIMITE=1` : sans cela, la limite de 60 requêtes par minute répondait 429 au milieu de la suite.
- **Fausse base stricte** (depuis le 09/10) : une colonne inconnue de `core/schema.ATTENDU` en lecture, filtre, tri ou écriture fait échouer la requête comme PostgREST (42703 / PGRST204). `db.schema_libre = True` la rend permissive pour un test qui simule une base en retard. **Aucune date écrite en dur** relative à « aujourd'hui » : un test daté devient rouge un jour donné (trois l'étaient, audit du 03/10), fausse base Supabase en mémoire (`conftest.py`, alignée sur PostgREST : les insertions renvoient les lignes écrites, PK uuid pour `coach_conversations`, **plafond `max-rows` à 1000 lignes** — sans ce plafond, aucun test ne peut repérer une lecture non paginée).
- **Stockage partagé** : `PARTAGE_TEST=fakeredis` (Redis simulé neuf par test) ou `PARTAGE_TEST=redis://…` (vrai serveur, vidé avant chaque test) rejoue toute la suite avec cache, verrous, quotas et tâches IA dans Redis. La CI le fait sur un service `redis:7-alpine` (étape « Tests Python sur Redis »).
- **Tests JavaScript** : `pwa/tests/js/` — lanceur maison sous Node nu (`node tests/js/run.js`), sans npm install ni jsdom ; `harness.js` fournit un DOM/localStorage/fetch minimal. Couvre la **file hors-ligne** (ordre d'envoi, reprise après échec, session expirée, double synchronisation, phase d'écoute). `tests/test_js.py` le branche sur pytest (ignoré si Node manque).
- Fichiers : `test_routes`, `test_db_prog`, `test_data_integrity` (pagination, corps du programme, même séance 2×/semaine), `test_seance_saisie` (enregistrement JSON, records), `test_progres_exercice` (fiche exercice, tendance, comparaison, records, standards relatifs), `test_ranger_exercices` (un mouvement, un nom ; Gestion → Ranger ; saisie), `test_offline_reminders` (file hors-ligne, rappels), `test_coach_stream` (SSE, mémoire), `test_debrief`, `test_assiduite` (taux d'assiduité en début, milieu et fin de mois), `test_entetes_robots` (HSTS, robots.txt, libellé de surcharge), `test_nutrition_barcode`, `test_nutrition_v5` (cibles, repas par aliment, recherche), `test_recettes` (recettes et aliments perso, page, sans v49), `test_rythme` (rythme des pesées, proposition, bouton), `test_auth_admin_chemins` (jeton, session, console admin), `test_partage` (deux instances sur un même Redis, panne de Redis, flux du coach ; `REDIS_TEST_URL` pour un vrai serveur), `test_identite_exercice` (identifiants, renommage oui/non, séance passée, base sans v42), `test_programme_chemins` (planning, séances, export/import), `test_accessibilite`, `test_app_native`, `test_challenges`, `test_foods`, `test_generator`, `test_overload`.
- Le paquet `supabase` local étant cassé, conftest stubbe `sys.modules["supabase"]` avant l'import de l'app.

### Calques du jour (table `calques_seance`, v46)
- **Depuis la v46**, une ligne par (compte, séance, date) et une colonne par calque : `extras` (exos ajoutés à la volée), `brouillon` (séance libre), `substituts` (échanges du jour), `ordre` (ordre des cartes). Une ligne vide n'est pas gardée. Chaque geste en séance écrit **sa ligne** (`data.modifier_calque`, sous verrou `partage`) au lieu de réécrire le programme entier. Fin de séance : `effacer_calques` + `purger_calques` (84 jours). Renommer une séance (`renommer_seance_calques`), reset total et suppression de compte suivent.
- **Base en retard** : table absente = lecture et écriture dans le blob comme avant, table redemandée chaque minute ; sans ligne, un reste de calque dans le blob s'affiche encore. Les paragraphes ci-dessous décrivent l'ancien stockage, dont la purge sert encore à ces restes.
- La v46 a aussi repris en table `session_notes` les bilans restés dans le blob (`_session_notes`, d'avant la v34) : la page de séance les relisait, mais l'export et le coach, qui ne lisent que la table, ne les voyaient pas.

#### Avant la v46 : dans le blob (`_extras`, `_libre_draft`, `_substituts`, `_seance_order`)
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
- `routes/accueil.py` importait `_display_week` depuis `routes/seance.py`. Il le prend maintenant dans `core/seance_semaine.py`. **Cinq autres imports entre blueprints subsistent** (mesurés le 03/10) ; le calcul cardio est sorti dans `core/cardio_activites.py`. `tests/test_couche_seance.py` fige la liste : elle ne peut plus grossir sans qu'un test tombe.
- Les noms gardent leur préfixe `_` : le déplacement a été fait sans en renommer un seul, pour que chaque corps de fonction reste comparable au caractère près à l'original (vérifié : 55 fonctions sur 55 identiques).

### Import Hevy / Strong (core/import_muscu.py, /gestion/import-muscu)
- Pour tout le monde (c'est ce qui permet de venir sans repartir de zéro). Même parcours que Strava : déposer le CSV, aperçu (rien n'est écrit), confirmer. Rien n'est jamais effacé.
- En-têtes comparés normalisés contre des alias ; séparateur `,` `;` ou tabulation ; dates ISO ou locales anglaises ; livres converties en kg (colonne `weight_lbs` ou `Weight Unit`). Échauffements (`set_type=warmup`, `Set Order=W`) et lignes sans reps (cardio, chrono) écartés et comptés.
- Noms anglais → catalogue via `resoudre` (table `_ANGLAIS` complétée) ; le matériel entre parenthèses devient la variante sauf s'il est déjà supposé par l'exercice (« Lat Pulldown (Cable) » → « Tirage vertical »). Un exercice inconnu garde son nom d'origine.
- Doublon = même jour + même nom de séance : réimporter le même fichier ne double rien. Écriture par paquets de séances entières (`ajouter_lignes`, lots de 500), donc jamais de séance à moitié écrite. Remarque « Import Hevy » / « Import Strong ».

### Une série = une ligne (migration v41, vague 7 du 04/10)
- Index unique `history_serie_unique` (user_id, date, seance, exercice, serie). `CLE_SERIE` dans `core/db_historique.py`. La migration refuse de s'appliquer s'il y a des doublons (au 04/10 : 1 136 lignes, 0 doublon).
- Écritures **par clé** (upsert `on_conflict=CLE_SERIE`) : `replace_exo_rows` met à jour sur place les séries qui gardent leur numéro et supprime le reste ; `save_hist` idem par lots ; `ajouter_lignes` (import) en `ignore_duplicates` — réimporter ne double rien et n'écrase pas une saisie ; `append_exo_rows` relit et réessaie une fois sur collision (autre instance). `_series_distinctes` renumérote les doublons de clé dans un même envoi (rien ne se perd).
- Sans l'index (erreur 42P10), repli automatique sur l'ancien chemin (insert puis suppression), `_unicite = False`.
- Renommages (`core/db_renommage.py`) : UPDATE groupé ; sur collision (23505), déplacement ligne à ligne avec le numéro de série suivant libre.
- La fausse base des tests applique le même index (`FakeQuery.UNIQUE`, insert tout-ou-rien, update annulé en bloc, `ignore_duplicates`).
- Éditeur : renommer un exercice qui a des séries ouvre « Est-ce le même exercice ? » (`POST /programme/exo/historique` : compter, puis `suivre: true` avec l'`id`). Oui = l'exercice garde son identifiant, ses séries anciennes le reçoivent (`core/db_identite.py`, sans réécrire leur nom) et les autres exemplaires du même exercice prennent le nouveau nom ; Non = l'éditeur retire l'`id`, un nouvel identifiant est calculé et l'historique reste à l'ancien nom. Sans la v42 ou sans `id` : les séries sont renommées comme avant.
- **Identité des exercices** (`core/exercice_ids.py`, vague 12 du 04/10) : chaque exercice du programme porte `id` (`e_` + 8 hex, calculé une fois depuis le nom, puis fixe ; même nom = même id ; un nom qui retombe sur l'id d'un exercice renommé prend `-2`). Attribué dès la lecture (`get_prog`, déterministe, sans écrire), gravé par `save_prog`, transmis à l'éditeur (`ui_state`) et à la séance (champ caché `exo_id`). Une série porte `history.exercise_id` = id + `~variante` (migration v42). `core.data.get_hist` affiche chaque série identifiée sous le nom ACTUEL de son exercice (`afficher_selon_programme`, lu via `lire_prog` pour ne pas toucher la base de fusion de `save_prog`). Les écritures de la séance ciblent par nom OU par identifiant (`_ids_cibles`) : réécrire une séance passée après un renommage ne double rien. Lignes antérieures à la v42 : lues par leur nom. Le composant de l'éditeur vit dans `static/js/programme.js`.

### Éditeur de programme : bornes et premier passage (point 4 de l'audit, 04/10)
- Bornes (`core/programme_entrees.py`, ré-exportées par `routes/programme.py`) : `MAX_SERIES` 20, `MAX_EXOS_PAR_SEANCE` 30, `MAX_SEANCES` 40, noms d'exercice ≤ 80, de séance ≤ 60. Appliquées dans `_exo_entry` (toutes les écritures y passent), `/programme/state`, `/programme/import`, `/programme/seance/new` (`?seance=trop`), `/programme/exo/add` (`?exo=trop`), `/programme/exo/update`. L'éditeur les reçoit (`var BORNES`) et borne aussi côté client (`bornerSeries`), avec un message plutôt qu'une troncature muette.
- Onboarding « Créer mon propre programme » (`programme_id=custom`) → `/programme?nouveau=1` : carte « Construis ton programme » (3 étapes), au lieu de l'accueil.
- `/gestion/reset-total` exige `confirm=yes` ; sinon `?reset=confirm`, rien n'est effacé. Le « reset soft » (archive de l'historique dans `_archive`/`_legacy_volume`, réinjectée dans Progrès) a été **retiré en v47** : aucun compte ne s'en servait, l'export gratuit couvre le besoin.

### Supersets (`superset: true` sur un exercice du programme)
- « Enchaîner avec le suivant » : case dans l'éditeur de programme, conservée par `_exo_entry` (booléen strict). `_build_all_exo_contexts` nomme le partenaire des deux côtés (`superset_avec`, `superset_de`).
- En séance : cartes reliées par un liseré ; après une série du premier exercice, pas de chrono, la carte du second s'ouvre ; après une série du second, chrono puis retour au premier (`allerAuPartenaire`, static/js/seance.js).

### Échauffement (core.muscu.series_echauffement)
- Rampe affichée, repliée, sur la carte d'exercice : barre vide (mouvements à la barre), 40/60/80 %, 90 % au-delà de 100 kg, arrondi 2,5 kg, vers la charge suggérée sinon la plus lourde de la dernière fois. Seuil 30 kg. La rampe affichée ne s'enregistre pas d'elle-même ; une série cochée « échauffement » s'enregistre à part depuis la v43 (voir plus bas), hors volume, records et suggestion.

### Import Strava (core/strava_import.py, /cardio/import)
- **Par le fichier, pas par l'API.** Depuis juin 2026 l'API « Standard » de Strava exige un abonnement actif (11,99 $/mois) ; l'export de ses propres données reste gratuit. Bâtir sur l'API, c'était bâtir quelque chose qui s'éteint le jour où l'abonnement s'arrête — et il fallait manipuler un client_secret.
- `activities.csv` n'est pas un fichier propre. Trois précautions, chacune contre un piège réel : les **en-têtes changent avec la langue** du compte (on compare des noms normalisés à des alias, jamais une position de colonne) ; la **date est au format local** (plusieurs formes essayées, les illisibles comptées) ; le **séparateur** est une virgule ou un point-virgule.
- **L'unité de distance se déduit de la vitesse qu'elle implique**, elle ne se suppose pas : 5 000 pour une heure de course, c'est des mètres ; 5, des kilomètres. Se tromper multiplierait — ou diviserait — tout un historique par mille sans que rien ne le signale.
- **Rien n'est écrit avant l'aperçu.** `/cardio/import` (POST) lit et montre ; `/cardio/import/confirmer` écrit. Le contenu revient par le formulaire et est **revalidé entièrement** (date, activité dans la liste, durée et distance bornées) : une ligne trafiquée n'a pas à devenir une ligne d'historique.
- Dédoublonnage sur (date, activité, durée ± 2 min). La durée entre dans la comparaison parce que **deux footings le même jour sont deux séances** — l'app les distingue déjà, l'import ne doit pas les confondre. Relancer le même fichier ne double donc rien.
- La musculation Strava est écartée (l'app la suit ailleurs) mais **annoncée** : un import muet sur ce qu'il laisse de côté oblige à tout recompter à la main.
- `tests/test_strava_import.py` (52 tests).

### Suivi GPS (static/js/gps-track.js)
- `GpsTrack.creerSuivi()` accumule la distance à partir des positions du navigateur. Module autonome, sans DOM : `tests/js/test_gps_track.js` (18) l'exerce sous Node en lui poussant des positions à la main.
- **Limite assumée et écrite à l'écran** : le navigateur ne donne des positions que tant que la page est visible. Écran éteint ou app en arrière-plan, Android suspend la page. Le suivi prend donc un `wakeLock` écran (comme le chrono de repos) et **compte** les interruptions.
- Trois filtres, chacun contre une façon d'inventer des mètres : précision > 25 m (position floue), déplacement < 6 m (tremblement à l'arrêt — le point de référence n'est PAS mis à jour, sinon le bruit s'accumulerait), vitesse > 12 m/s (recalage).
- L'avertissement se déclenche sur **UN** silence ≥ 60 s, jamais sur leur somme : un téléphone en économie d'énergie relève toutes les 35 s, la somme grimpe à plusieurs minutes sans qu'un mètre soit perdu, et l'avertissement resterait allumé en permanence. La somme ne distingue pas « lent mais régulier » de « quelques vrais trous » ; la durée du pire trou, si.
- La distance GPS alimente le champ distance, donc la vitesse se déduit toute seule (cf. `completer_mesures`).

### Cardio : durée, distance, vitesse (core/seance_cardio.py)
- **Deux valeurs sur trois suffisent.** `completer_mesures(activite, duree, distance, vitesse)` déduit celle qui manque, dans les deux sens. Une valeur saisie prime toujours : si l'utilisateur donne les deux, on ne corrige rien. La durée n'est jamais déduite — c'est elle qui identifie la séance.
- Trois défauts trouvés en mesurant : la vitesse calculée dans le formulaire de séance était **affichée en suggestion et jamais enregistrée** ; la page `/cardio` **n'avait aucun champ vitesse** alors que l'écran de séance en a un ; et la règle de conversion se devinait à partir du **libellé** de l'unité (`indexOf("km/h")`), si bien que « Allure (min/500m) » ne tombait dans aucun cas et que l'allure du rameur ne se calculait jamais, en silence.
- `UNITES_CARDIO` est la **seule** table : `/cardio` la reçoit dans son gabarit, l'écran de séance dans `#seance-config`. `static/js/seance.js` en gardait une copie en dur ; un test interdit son retour. La règle y est **nommée** (`par_heure`, `m_par_min`, `par_min`, ou vide) au lieu d'être devinée.
- `tests/test_cardio_mesures.py` (31) et `tests/js/test_cardio_mesures.js` (10) tiennent l'ensemble, dont l'arrivée effective en base par les deux routes.
- Le harnais JS sait maintenant servir une configuration : `createEnv({ json: {"seance-config": {…}} })`.

### Saisie d'une série (templates/seance_edit.html + static/js/seance.js)
- Le tableau `.sets-table` de six colonnes donnait, **mesuré à 375 px** : Reps 67, Poids 70, RPE **25** (un `<select>`), Remarque 87. Les deux champs qu'on remplit à chaque série se partageaient la largeur avec trois autres choses.
- Une série remplie se replie désormais en une ligne (`.serie-faite`, touchable pour corriger) et seule la courante reste ouverte (`.serie-encours`), avec deux champs de **133 px** et un bouton de **277 px**. RPE et remarque se déplient à la demande.
- **C'est de la mise en page.** `serializedSets()` envoie toujours toutes les séries avec les mêmes quatre champs, et chaque « Série faite » l'envoie (envoi partiel). `faits` et `optionsDe` sont de l'état d'affichage. Un test JS vérifie que marquer une série faite ne change pas d'un octet ce qui part en base.
- Un seul comportement bouge : le chrono de repos démarrait sur le `change` d'un champ, il démarre sur « Série faite ». `onSetFilled` reste appelé par les deux chemins et ne se déclenche qu'une fois par série.
- `tests/js/test_saisie_serie.js` (16 tests) tient l'ensemble, dont le recalcul des index après `removeSet` — sans lui, retirer une série en rouvrait une autre.
- Le mode isométrique (`isIso`, gainage) garde son propre chrono, intouché.
- **Charge recopiée (09/10)** : « Série faite » recopie la charge dans la série suivante si elle est encore vide, comme chez Strong. Jamais depuis ni vers un échauffement.
- **Terminer sans série (09/10)** : si aucune série n'est remplie et aucun cardio enregistré (`window.seanceVide()`), la fenêtre de fin dit « Terminer sans série ? » et prévient que la séance ne comptera pas, au lieu de « Séance terminée 💪 ». Tests : `tests/js/test_petits_correctifs.js`.

### Noms d'exercices : un mouvement, un nom ; l'équipement à côté (11/10, retour d'usage)
- **La règle** (`core/noms_exercices.py`) : le nom dit le mouvement, l'équipement va entre parenthèses (« Développé incliné (Haltères) »), comme l'affichent Hevy et Strong. Les séries étaient déjà stockées ainsi ; manquait une règle pour le NOM. Retour du 11/10 : Progrès listait « Développé decliné (Barre) », « Développé décliné barre (Barre) » et « Développer décliné » comme trois exercices.
- `sortir_materiel` : le dernier mot, s'il est un matériel (barre, haltère(s), poulie, machine, lesté), va dans l'équipement quand le reste est un mouvement connu (bibliothèque `static/js/exercise-library.js`, fiches, autres noms de l'utilisateur) ; dit deux fois (« … barre (Barre) »), il sort aussi. Il reste quand il fait le nom (« Écarté machine », « Reverse fly machine » : « Écarté » seul n'est rien), quand il contredit l'équipement (« Tirage horizontal poulie (Machine) ») et pour « Extension triceps haltère » (le mot dit « au-dessus de la tête », `_MATERIEL_FAIT_LE_MOUVEMENT`).
- `meme_mouvement` : même nom aux accents, espaces, pluriel, ordre des mots ou à une faute de frappe près. Jamais deux mots connus l'un pour l'autre (« adducteurs » / « abducteurs », que l'ancien outil proposait de fusionner), jamais deux fiches différentes (« Squat » / « Squats »), jamais deux prises. `meme_fiche` (même fiche d'exercice) n'est qu'un indice, proposé décoché, et pas quand la fiche a été trouvée parce que le nom contient plus de mots (« Squat sumo », « Mollets presse à cuisse »).
- **Gestion → « Ranger mes exercices »** (remplace « Doublons détectés » et « Aligner sur les noms de l'app », et `canoniser`) : `ranger()` groupe les noms de l'historique par mouvement ; le nom retenu est l'orthographe de la bibliothèque ou d'une fiche si l'un des noms en est une, sinon le plus utilisé — « Presse à cuisses » ne devient pas « Leg press ». Coché d'office : équipement, accents, pluriel, faute vers un nom de référence ; décoché : même fiche. Le serveur recalcule les propositions (le formulaire dit quoi, jamais vers quoi). Appliquer renomme l'historique, puis le programme et les exercices perso (`_ranger_programme`) — sinon la séance suivante réécrirait l'ancien nom. Le matériel sorti d'un nom du programme devient son `materiel`, et ses séries identifiées sans matériel le reçoivent (`donner_materiel`, `id~Barre`).
- **À la saisie** : un exercice qui ENTRE au programme (sans `id`) est rangé (`ranger_nouveaux` dans `/programme/state` et `/programme/exo/add` ; l'éditeur reçoit `noms` et l'affiche aussitôt, avec la pastille d'équipement). Jamais un exercice déjà là : changer son nom sans son historique couperait « dernière fois ». Aussi : exercice ajouté en séance (`/seance/add-extra`, l'extra garde `materiel`), exercice perso (Gestion). En séance, la carte d'un exercice sans historique part sur le `materiel` du programme (`_last_variant(…, defaut)`).
- Mesuré sur les 57 noms réels du propriétaire (lus en `select`) : 38 lignes dans Progrès sans rien faire (57 avant) ; 34 après « Ranger » (61 séries regroupées), 3 rapprochements laissés à son choix. Tests : `tests/test_ranger_exercices.py`, `tests/e2e/test_noms_exercices.py`.

### Courbe de force : période, tendance, records (11/10, audit axe 4, idée 4.2-4)
- **Période** (`p` = `1m`, `3m`, `6m`, `1a`, `tout` ; `3m` par défaut). Sans choix explicite, un exercice sans 2 séances sur 3 mois s'affiche sur tout l'historique. Les points sont placés **à leur date** (un trou de 3 semaines se voit). Toutes les séances de la période sont tracées (avant : les 20 dernières, à intervalles égaux).
- **Tendance** (`exercise_stats.tendance`) : droite des moindres carrés, à partir de 4 séances sur au moins 21 jours ; « stable » si elle bouge de moins de 2 % de la moyenne sur la période. Une valeur 3 fois plus grande ou plus petite que la médiane est une faute de frappe, écartée (au plus une séance sur dix). **Pas de Theil-Sen** : avec des valeurs qui se répètent (3 × 10 à 32 kg), la médiane des pentes tombait sur 0 (« stable » pour des dips passés de 10 à 24 reps, vrai historique). **Pas d'écart à une première droite** pour repérer les fautes : une faute sur la dernière séance tire la droite jusqu'à elle (+195 kg par mois).
- La droite est **coupée** aux bords du graphique ; l'axe va de la plus petite à la plus grande vraie valeur, écrites dans la marge de gauche (le haut et le bas de la zone tracée sont à 14 et 140 px : hauteur CSS = hauteur du `viewBox`).
- **Records** : un point bat tout ce qui précède, calculé sur tout l'historique avant de couper à la période (point doré). « Tes records par répétitions » : le plus lourd pour **au moins** 1, 3, 5, 8, 10, 12 reps, daté du premier jour ; une même série qui tient plusieurs lignes n'en occupe qu'une (« 1 à 10 »).
- **Comparaison** : la période contre celle d'avant, de même longueur (« 3 derniers mois contre les 3 mois d'avant ») : séances, 1RM estimé max, volume total. Rien pour « Tout ».
- **Poids du corps** = plus de la moitié des séances sans charge. Avant, la fiche suivait le 1RM en kg : dips à « 0 kg » partout, courbe plate ; tractions lestées une fois, courbe qui tombait à 0 à chaque séance sans lest. Avec la règle « jamais chargé », une séance de tractions à +10 kg sur 22 laissait la courbe en kg avec un seul point. Au poids du corps : mesures « Meilleure série » et « Répétitions », records et comparaison en répétitions, pas de tableau en kg. Une séance à 0 kg n'apparaît pas sur les courbes en kg.
- Nombres à la française : filtre Jinja `fr` (`exercise_stats.nombre_fr` : « 1 234,5 », « +1,4 », « −0,8 »).
- Vérifié sur un extrait du vrai historique du propriétaire (10 exercices, 393 séries, 6 mois, lu en `select`) : par exemple développé incliné +2,3 kg de 1RM par mois sur 6 mois, dips +4,8 reps par mois sur 3 mois. Tests : `tests/test_progres_exercice.py`.

### « Série faite » : le téléphone d'abord (11/10, audit I-2 / axe 12, idée 4.2-2)
- **La série est écrite dans la file du téléphone AVANT de partir** (`OfflineQueue.envoyer(url, champs, cle)`, `static/js/offline.js`), puis la file l'envoie (`Accept: application/json`). La carte n'envoie plus elle-même. Fermer l'app pendant l'envoi ne perd plus rien : tout repart au prochain lancement, depuis n'importe quelle page. Reproduit sur l'ancienne version : la série validée puis l'app fermée n'arrivait jamais en base.
- **La carte répond tout de suite** : « ✓ Gardé sur l'appareil, envoi en cours », carte verte et « Exercice suivant » après la dernière série (`_termineLocalement`, même règle que `_exo_completed` : une série suffit), puis « Enregistré » à la réponse. « Exercice suivant » ferme la carte et ouvre la suivante. Mesuré dans la page avec un serveur à 2 s : confirmation en 7 à 50 ms (avant : ~2 050 ms) ; l'enregistrement côté serveur, lui, prend toujours ~2 s, en arrière-plan.
- **Un seul expéditeur, dans l'ordre** : la version la plus récente d'un exercice remplace celle qui attendait (`cle` = clé du brouillon), et qui attendait l'ancienne attend la nouvelle. Un envoi échoué déjà dépassé par une version plus récente n'est pas rejoué.
- **Réponse tardive** : une série partie après coup (nouvel essai, réseau revenu, app relancée) prévient sa carte (`OfflineQueue.surReponse` → `_recuApresCoup` : record, volume, « Enregistré »). La page ne se recharge plus au retour du réseau.
- **Refus du serveur** (4xx hors 401/403/408/429) : mis de côté (`muscu_offline_rejets`), rendu à la carte (« Pas enregistré ») sans toast en double ; « Terminer » renverra la série.
- Preuves : `tests/e2e/test_serie_instantanee.py` (confirmation < 300 ms serveur muet, app fermée pendant l'envoi, renvoi seul au retour du réseau, ni badge ni message sur une série normale), `tests/js/test_offline.js` (« envoyer : … »).

### Une série saisie ne se perd plus (audit du 30/09, C1 + I4 + I5 + I9 + I18 + I21 + M7)
- **Valeur grisée (03/10)** : le champ Reps affiche l'objectif en gris (suggestion, sinon bas de la fourchette). « Série faite » sur un champ vide valide CETTE valeur, avec la charge suggérée, comme chez Hevy/Strong ; sans reps ni charge à proposer, la série reste ouverte avec un message. « Terminer » n'attend la file hors-ligne que 6 s (rejeu borné à 8 s) : le reste part derrière le bilan.
- **Retours du 04/10 (vague 13)** :
  - **Brouillon.** Il garde les séries VALIDÉES (`faits`). Une saisie seulement tapée revient dans son champ, à valider, au lieu d'une coche verte trompeuse. Le premier chiffre tapé marque la séance « en cours » (`aSaisi`), donc relancer l'app la rouvre.
  - **Repos.** Il part UNIQUEMENT à « Série faite » : plus de `@change` sur les champs. La notification reçoit le nom de l'exercice (`RestTimer.start(s, nom)`, gardé dans `_state.nom`) au lieu du premier de la page.
  - **Fin d'exercice.** Après la dernière série prévue, la carte reste ouverte avec « Exercice suivant », qui la referme.
  - **Défilement.** On défile vers l'exercice suivant après le repli de la carte (260 ms), sans dépasser sa cible.
  - **Affichage.** Le bandeau de record va dans `.exo-repere`, sur toute la largeur. Il allait dans la colonne des flèches, ce qui écrasait le titre. L'équipement est en tête de carte (`.exo-equipement`).
  - **Batterie.** Plus de `backdrop-filter` sur les cartes ni sur les barres fixes (en-tête, navigation, chrono) : fonds presque opaques à la place.
- **Séries d'échauffement (vague 14, migration v43)** : la case « Série d'échauffement » se trouve dans le panneau « RPE, remarque » ; elle n'apparaît que si la colonne `history.type_serie` existe (`echauffements_disponibles()`).
  - La série est enregistrée avec `type_serie = 'echauffement'`. `db.get_hist()` l'EXCLUT par défaut : records, suggestions, séries par muscle, volume, récap, coach l'ignorent d'office. Seules la carte de séance (`echauffements_du_jour`) et l'export la demandent (`echauffement=True`).
  - Le volume d'échauffement s'affiche à part (« +200 échauff. »).
  - Une série d'échauffement ne prend jamais la valeur grisée, et la marquer ajoute une case pour garder toutes les séries de travail prévues.
  - Sans la v43, un échauffement n'est jamais écrit comme une série de travail : il est écarté.
- **Cardio en colonnes (vague 15, migration v44)** : voir « Cardio » plus haut. Ordre de mise en production : déployer le code, exécuter la v44, **redémarrer le service web** (un processus qui a vu les colonnes absentes continue sans elles ; une écriture refusée par la contrainte le remet d'elle-même au nouveau format). Rejouée avant livraison sur un PostgreSQL 16 local avec les 25 lignes cardio de production : SQL et Python convertissent à l'identique, migration idempotente, tonnage admin de 87 185 à 500 sur ce jeu.
- **Remplace le point « C'est de la mise en page » ci-dessus.** « Série faite » ENREGISTRE : `save-exo` avec `partiel=1`, qui n'écrit que les séries remplies (les autres ne deviennent pas des SKIP en cours d'exercice). Avant, elle cochait en vert sans rien écrire, et « Terminer » effaçait les brouillons : trois séries cochées, séance terminée, zéro ligne en base.
- **« Enregistrer » a quitté la carte** (audit du 18/10, m8) : vert lui aussi, il doublait « Série faite ». Il reste un seul verbe plein par carte, plus « Skip » discret à droite ; le formulaire `save-exo` est gardé, masqué, ses champs servent à chaque envoi (`_form`). La route accepte toujours l'envoi complet (vides en SKIP). « Terminer » envoie d'abord ce qui n'est pas encore reçu (`_rev` ≠ `_revServeur`), vide la file si le réseau est là, et n'efface les brouillons qu'ensuite ; en cas de refus, la modale le dit et rien n'est effacé.
- **Retirer une série** (retour du 24/10, régression de m8) : « Enregistrer » renvoyait toute la carte, ce qui faisait les deux gestes ci-dessous. Désormais `removeSet` les fait lui-même. Si les séries restantes sont toutes faites, il appelle `_termineLocalement` : « Exercice suivant » apparaît, sans repli d'office (règle du 04/10). Si la série retirée était faite, il fait un envoi partiel. Quand il ne reste aucune série remplie, cet envoi porte `retire=1` et la route efface l'exercice du jour (`delete_exo_rows`). Sans ce drapeau, un envoi partiel vide ne touche toujours à rien. Tests : `tests/e2e/test_retirer_serie.py` et `tests/test_series_sures.py`.
- Réseau faible : délai de 8 s (`AbortController`), puis mise en file. 5xx / 408 / 429 / pas de réponse = file ; 4xx = refus affiché, brouillon gardé.
- File hors-ligne (`offline.js`) : une entrée par exercice (`cle`, la plus récente remplace l'ancienne ; `drop(cle)` après un envoi direct réussi), jeton CSRF de la page au rejeu, refus définitif mis de côté dans `muscu_offline_rejets` au lieu de bloquer la file, déconnexion avec envois en attente = avertissement puis second appui.
- `replace_exo_rows` insère avant d'effacer (par id). « Skip » sur des séries réelles : confirmation en ligne côté client, 409 côté serveur sans `confirme=1`.
- Le SW ne recharge plus la page à sa première installation, ni sur `/seance` lors d'une mise à jour.
- Tests : `tests/test_series_sures.py` (serveur), `tests/js/test_saisie_serie.js` + `test_offline.js`, et **`tests/e2e/test_seance_navigateur.py`** — la séance jouée dans Chromium via `run_local_fake.py` (`/test-vierge`, `/test-historique`) : en ligne, mode avion, réseau qui ne répond pas, Skip. S'ignore sans Playwright ; la CI installe Chromium.

### Quotas coach et générateur (core/quota.py)
- Vérifier et réserver d'un seul geste, sous verrou par utilisateur (`partage.verrou`, commun aux instances avec Redis). Coach : profil relu sous verrou avant d'incrémenter. Générateur : compte en base (événements) lu sous verrou + générations en cours (compteur partagé `encours:<nom>:<user>`, TTL 300 s : une réservation d'une instance tuée tombe seule) ; la réservation tombe à la fin de l'appel, réussi ou non.
- **Flux du coach** : au plus `COACH_FLUX_MAX` (défaut 6) réponses en flux simultanées **par instance** — chacune tient un des 16 fils. Au-delà : événement SSE `error` « réessaie dans quelques secondes », quota rendu.

### Compression HTTP (core/compression.py)
- gzip niveau 6 sur les réponses texte de 200 et ≥ 1 ko (HTML, CSS, JS, JSON, SVG), y compris les fichiers statiques. Jamais sur les flux (SSE du coach) ni sur une réponse déjà encodée. ETag rendu faible, `Vary: Accept-Encoding`. Hook déclaré AVANT les autres `after_request` pour s'exécuter en dernier. `COMPRESSION_DISABLED=1` coupe tout.
- Mesuré : /programme 216 → 28 ko, séance 126 → 20 ko, accueil 28 → 8 ko, seance.js 43 → 12 ko.

### Coût d'un affichage de /accueil
- Mesuré avec un an d'entraînement (1 872 séries) : **8 requêtes Supabase**, dont le **programme trois fois**. La page pouvait le sauvegarder **jusqu'à quatre fois** en un seul affichage (badges, record de streak, bandeau PRO, défi gagné), chacune relisant et réécrivant tout le blob sous verrou optimiste. Les quatre posent désormais un drapeau et **une seule écriture** les porte : 8 → 7 requêtes.
- `_compute_badges` ne persiste plus rien : elle calcule, la vue décide d'écrire. Une fonction de calcul qui sauvegarde était la raison pour laquelle l'une des quatre écritures passait inaperçue.
- `_normalize_hist` était la fonction la plus coûteuse de la page — et elle existait **en double**, la copie de `routes/accueil.py` ayant divergé sur le traitement d'un muscle vide. Une seule désormais, dans `core/seance_semaine.py`, et **mémoïsée par (exercice, muscle noté)** : `fix_muscle` peut passer 60 règles de mots-clés par ligne, pour une vingtaine de réponses distinctes. Mesuré : **68 ms → 1,2 ms** à 1 872 lignes, **196 ms → 2,3 ms** à 5 000, résultats identiques. Le gain grandit avec l'historique, ce qui est exactement la propriété qui manquait.
- `get_hist()` faisait `select("*")` : la table porte aussi `user_id`, `session_id` et `created_at`, deux UUID et un horodatage que le mappeur ne lit jamais. Restreint aux dix colonnes utiles — **51 % d'octets en moins** sur le fil (576 → 282 ko à 1 872 lignes). `rpe` n'existant qu'après la v34, un repli retombe sur la liste courte comme le fait déjà `_insert_history`.
- **La fausse base des tests projette désormais les colonnes demandées**, comme PostgREST. Elle les ignorait : restreindre un `select` n'aurait été vérifié nulle part, et un champ oublié serait passé au vert ici pour casser en production.
- Reste à traiter : `get_hist()` lit toujours **toutes les lignes** (2 pages PostgREST à 1 872) pour afficher une semaine. Le streak et les badges ont besoin de dates et d'agrégats, pas de lignes complètes — ce qui demande de stocker ces agrégats, donc une migration.
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
- TTL : **10 minutes** (profil aussi), LRU borné à 200 entrées (`_CACHE_MAX`), valeurs gardées par chaque instance. Avant le 10/10 : 60 s, si bien que pendant une séance (repos de 1 à 3 min) chaque « Série faite » relisait historique et programme en base (audit I-2 : 7 appels base par série, 2-3 depuis, `tests/test_cout_serie.py`). La validité partagée (ci-dessous) rend ce TTL sûr ; il doit rester bien sous `GENERATION_TTL` (1 h) de `core/partage.py`.
- **Validité partagée** (vague 11 du 04/10) : chaque écriture incrémente le numéro de génération de la clé (`partage.nouvelle_generation`, dans Redis avec `REDIS_URL`) ; une entrée n'est servie que si les numéros lus AVANT sa lecture en base n'ont pas bougé. Règle à la fois la cohérence entre instances et la course lecture lente / écriture (F1). `vider_cache()` avance la génération `*`.
- `_cache_modifier(clé, corriger)` : après « Série faite », invalide la clé partout et corrige la copie locale — gardée seulement si personne d'autre n'a écrit entre-temps (numéro avancé d'exactement 1).
- Redis en panne : le cache se coupe (aucune entrée servie) pendant 10 s, puis Redis est retenté ; verrous et compteurs retombent sur la mémoire.
- Clés : `hist:{user_id}`, `prog:{user_id}`, `profile:{user_id}`, `onboarding:{user_id}`

### Verrou optimiste sur `programs.data` (core/db_programme.py, migration v32)
- (30/09) Avec deux workers, chaque worker avait son cache et servait un historique périmé jusqu'à 60 s après une écriture faite sur l'autre (audit I8). D'où un seul processus sans Redis (`gunicorn.conf.py`), et la validité partagée du cache avec Redis (ci-dessus). Le cache est protégé par `_cache_lock`. La base du verrou optimiste vit dans `flask.g`, par requête (audit I7 : partagée par les threads, deux requêtes du même utilisateur se la volaient).
- Deux requêtes peuvent toujours partir du même blob (deux onglets, le cache) et s'écraser. `save_prog()` fait donc `update … eq(user_id).eq(version)` ; si 0 ligne touchée, relecture + `_merge_prog()` (fusion 3 voies par clé : seules NOS clés modifiées sont réappliquées sur la version DB), 3 tentatives, puis upsert brut loggué en `error`.
- Base de comparaison = dernier `get_prog()` du process (`_prog_base`). Sans lecture préalable ou sans colonne `version` (migration pas appliquée) → upsert comme avant.
- `_session_notes` (bilans de séance) : fenêtre glissante de 84 jours purgée à chaque `/seance/finish` (`routes/seance.py`), comme `_extras`/`_libre_draft`. Les bilans eux-mêmes sont dans la table `session_notes` depuis la v34 : cette purge ne touche que les restes de l'ancien emplacement.
- **`replace_program_body(old, body)`** + `PROG_BODY_KEYS` : l'autosave du programme envoie le corps (séances, planning, cardio…) et **conserve** toutes les autres clés personnelles (`_settings`, `_streak_record`, `_meal_plan`, `_challenges_won`…). Avant, une seule liste blanche recopiait 3 clés sur 11 : un autosave effaçait les réglages, le record de streak et les plats de la semaine. Toute clé personnelle reçue dans le corps est ignorée et loggée. Ces clés vivent maintenant en tables (`reglages` v45, `etat_compte` v47) : la règle protège ce qui reste dans le blob.

### Suggestion de surcharge (core/muscu.py → routes/seance.py)
- `overload_suggestion(last_sets, prev_sets, is_bw)` : double progression simplifiée. RPE moyen ≥ 9,5 → « Consolide » ; même charge partout ET (≥ 12 reps, ou ≥ 8 reps avec RPE ≤ 8, ou ≥ 8 reps deux séances de suite sans régression) → « Monte à X kg » (+2,5 kg ≥ 30 kg, +1 kg en dessous) ; sinon « Même charge, vise N+1 reps ». Le RPE vient de la colonne `rpe` (où la saisie l'écrit depuis la v34), repli sur l'ancien jeton `@RPE8` des remarques (`core/seance_historique._rpe_de`). Avant le 03/10, seul le jeton était lu : tout RPE saisi était ignoré.
- Affichée sous « Dernière fois » (bouton Appliquer = pré-remplit la charge sur les séries vides ; reps cibles en placeholder). Réglage `reglages.show_overload_hint` (Gestion). Recalculée par `/seance/api/variant-history`.

### Base d'aliments (core/foods_data.py → nutrition.html)
- `FOODS` (liste de dicts `{n, k, p, c, f, g, r, u}` : nom, kcal/prot/gluc/lip pour 100 g, catégorie, rang, portions `[[libellé, grammes]]`, ~430 entrées) est embarquée dans la page (`var FOODS`, avec `RECENTS` et `PERSO`) ; la recherche est côté client dans `static/js/aliments-recherche.js`, partagée par le repas et l'éditeur de recette (normalisation sans accents, « œ » → « oe » et « æ » → « ae » depuis le 12/10 — avant, « boeuf » ne trouvait aucun des 9 aliments au « bœuf », « oeuf » aucun œuf ; tous les mots doivent matcher, début de mot > milieu, mes aliments `r=-2`, récents `r=-1`, puis aliments simples puis plats/snacks `r=1`, un aliment « cru » après le cuit sauf si on tape « cru »).
- Mode « Aliments » (par défaut) du formulaire repas : panier `basket` (qty × portion) → `items` (JSON) → POST `/nutrition/add-meal` → une ligne par aliment. Pour ajouter un aliment : une ligne dans `FOODS_RAW` (une chaîne seule = titre de catégorie).

### Poids corporel (migration v33, routes/progres.py)
- Table `body_weight` (user_id, date, poids_kg), une pesée / jour (upsert `on_conflict=user_id,date`). Carte gratuite dans Progrès : courbe SVG 90 j, variation 30 j (couleur selon `objectif_nutrition`), min/max, saisie + suppression.
- Après chaque pesée/suppression, `_sync_profile_weight()` recopie la dernière pesée dans `profiles.poids_kg` et recalcule `tdee` / `calories_cible` (helpers de `routes/nutrition.py`). Le formulaire profil Nutrition crée aussi une pesée du jour. Export/import JSON : clé `poids`.

### Rate limiting (core/limiter.py)
- Default : 60 req/min par IP (Redis si `REDIS_URL` est une URL Redis — c'est le cas en production —, sinon mémoire du processus). `SANS_LIMITE=1` la coupe, pour `run_local_fake.py` seulement.
- Sur-limites ajoutées via `@limiter.limit(...)` sur les actions sensibles
- **Redis en panne** (24/10) : `in_memory_fallback_enabled` bascule le compteur sur la mémoire du processus à la première erreur (journal WARNING « Rate limit storage unreachable - falling back to in-memory storage »). Les mêmes limites s'appliquent, par processus. flask-limiter sonde Redis (`PING`) après 1, 2, 4, 8, 16, 32 s puis recommence : Redis revenu, il est repris en 32 s au plus (INFO « Rate limit storage recovered »). Client Redis du limiteur : `socket_connect_timeout` et `socket_timeout` à 0,5 s (`DELAI_REDIS`), **aucune nouvelle tentative** (celles de redis-py s'imbriquent : 1 tentative de plus = 4 × le délai). Coût d'une panne : 0,5 à 1 s sur la requête qui la découvre, puis 0,5 s sur une requête par sonde (9 requêtes lentes sur 344 en 70 s mesurées). Avant (constat du 23/10) : 2 s sur **chaque** page avec un Redis injoignable, blocage sans fin avec un Redis qui accepte la connexion sans répondre, et plus aucune limite (`swallow_errors`). `creer_limiteur(uri)` construit le limiteur de production ; `tests/test_limiteur_panne.py` l'éprouve contre un port fermé, une connexion qui n'aboutit pas, un serveur muet, et un relais coupé puis rouvert devant un vrai Redis (`REDIS_TEST_URL`, sinon `redis-server` local). Le journal de démarrage dit toujours « Rate limiter backend: redis (partagé) » : il décrit la configuration, pas l'état de Redis.

### Journaux et lenteur (09/10/2026)
- **Deux flux** (`app.py`) : INFO et DEBUG sur la sortie standard, WARNING et au-delà sur la sortie d'erreur. Railway étiquette « error » tout ce qui sort sur la sortie d'erreur : avant, chaque INFO y passait et une vraie erreur ne se filtrait plus (audit du 06/10, m5). `tests/test_journaux.py`.
- **Server-Timing** (`core/chrono.py`) : chaque réponse dit le temps passé en base (`base;dur=…;desc="N appels"`), dans Redis (`redis;…`) et au total. Lisible dans l'onglet Réseau du navigateur. Une requête de 800 ms ou plus écrit « lent : MÉTHODE CHEMIN … — base … ms (n requêtes), redis … ms (n appels), reste … ms » (INFO) : de quoi savoir où part le temps de « Série faite » en production (2 s le 06/10, I-2).
- **Coupure Supabase** (`core/reprise_base.py`) : une lecture (GET/HEAD) dont la connexion HTTP/2 est fermée par le serveur (`ConnectionTerminated`, la 503 du 05/10) est retentée une fois. Jamais une écriture : on ne sait pas si elle est passée. Le crochet est le client HTTP que postgrest se construit (`ClientAvecReprise`, substitué à `postgrest._sync.client.Client`). Avec supabase 2.8, c'était `postgrest.utils.SyncClient`, que 2.33 n'utilise plus : posé là, il ne voyait plus aucune requête, sans erreur (23/10). Le test de bout en bout laisse donc postgrest construire son client. Depuis 2.33, postgrest rejoue aussi lui-même une lecture qui reçoit 503 ou 520, jusqu'à 3 fois (attentes de 1, 2 puis 4 s).
- **Journaux de gunicorn** (10/10) : `gunicorn.conf.py` (`JournalScinde`) applique la même règle aux journaux de gunicorn lui-même (démarrage, arrêt des workers) : INFO sur la sortie standard, WARNING et au-delà sur la sortie d'erreur.
- **Paiements tracés** (`routes/billing.py`, 10/10) : un paiement Stripe réussi sans compte rattachable écrit l'événement `paiement_sans_compte` et un journal ERREUR (un client payait sans recevoir PRO, sans trace) ; une résiliation écrit `vip_resilie`.

### Sécurité du navigateur (CSP, audit du 06/10 m6, depuis le 10/10)
- **Bloquante** (`core/csp.py`) : `script-src 'self' 'nonce-…'` — les fichiers de `/static` s'exécutent, un `<script>` écrit dans un gabarit seulement s'il porte le jeton de CETTE réponse : `<script nonce="{{ csp_nonce() }}">` (neuf à chaque requête, `g.csp_nonce`). Pas de `unsafe-inline` ni de `unsafe-eval` pour les scripts. Les styles en ligne restent permis (`style-src 'unsafe-inline'`, des centaines de `style="…"`), Google Fonts aussi (`theme.css`). `connect-src` ajoute `SUPABASE_URL` (page de connexion).
- **Règles pour les gabarits** : aucun `onclick=`/`onchange=`… (aucun jeton ne les autorise : un écouteur `addEventListener` dans le script de la page, repéré par `id` ou `data-…`) ; les données pour le JS en `<script type="application/json" id="…">` lu par `JSON.parse`, plutôt qu'un `var X = …` écrit dans la page. `tests/test_csp.py` refuse un gabarit qui enfreint ces règles.
- **Alpine version CSP** (`@alpinejs/csp` 3.17.4 ; la 3.15.12 décodait `\u00e9` en « u00e9 », or `|tojson` encode ainsi les accents des `x-data`) : un attribut = **une seule expression**, sans `;`, fonction fléchée, `?.`, `??`, gabarit `` ` ``, `typeof`, `new`, expression régulière, ni globale (`Math`, `JSON`, `String`, `window`…). Tout geste en plusieurs temps devient une **méthode** du composant (`commencerRenommage()`, `basculerRepas(mt)`…). Une méthode appelée depuis un `x-data` imbriqué voit tout l'état fusionné via `this` (ex. `this.sname`, `this.newExo` dans `programmeApp`). Une valeur posée sur `window` est refusée même rendue par une méthode : en donner une copie (`RECENTS.slice()`, `Object.assign({}, BORNES)`).
- **`static/js/alpine-composants.js`** (chargé avant Alpine) : enregistre les composants (`Alpine.data`, liste `COMPOSANTS` ; un `x-data="nom"` ou `"nom(…)"` doit y figurer ou être enregistré par le script de sa page), la directive **`x-au-corps="ouvert"`** (sort une fenêtre vers `<body>` à l'ouverture, ex-`$watch(… appendChild …)`) et la magie **`$biblio`** (bibliothèque d'exercices : `groupes()`, `exos(groupe)`, `correspond(ex, recherche)`, `muscleDe(groupe, défaut)`).
- **Ne pas écrire `x-init="init()"`** à côté d'un composant qui a `init()` : Alpine l'appelle déjà. Le doublon (Programme, Cardio, Coach, Onboarding, Plaques jusqu'au 10/10) posait deux fois les écouteurs : quitter Programme après une modification envoyait la sauvegarde deux fois.
- **Rapports** : `report-uri /csp/rapport` (`routes/csp.py`, public, hors CSRF) ; chaque blocage arrive dans les journaux « CSP bloqué : directive (ressource) sur /page — fichier:ligne extrait », une fois par processus. **Retour arrière** sans déploiement : `CSP_OBSERVER=1` sur Railway.
- **Erreurs JavaScript** (audit du 18/10, I-2) : `static/js/erreurs.js`, chargé en tête de `base.html`, écoute `error` et `unhandledrejection` (Alpine relance ses erreurs d'expression : elles passent aussi) et poste `POST /erreurs/js` (`routes/csp.py`, comptes connectés, jeton CSRF, 20/min). Journal « Erreur JS (genre) sur /page — fichier:ligne : message », une fois par processus et 5 envois au plus par page, sans paramètres d'URL. Le coach était resté vide sept jours sans une trace côté serveur. Sentry est actif côté serveur depuis que `SENTRY_DSN` est défini sur Railway (journal de démarrage « Sentry actif (monitoring erreurs) »).
- **Autres en-têtes** : `Strict-Transport-Security: max-age=31536000` en production seulement (en local, HTTP casserait) ; `/robots.txt` (public) n'ouvre que l'accueil public, la FAQ et les pages légales (audit du 18/10, m6/m10).
- **Preuves** : `tests/test_csp.py` (en-têtes, jetons, gabarits, expressions) ; `tests/e2e/test_csp_navigateur.py` (22 pages × profils gratuit et PRO, plus admin et pages publiques, sans une erreur Alpine ni refus CSP ; un script injecté est bloqué ; bibliothèque, renommage, déplacement, fiche, repas, disques joués pour de vrai). **App native** (lu dans Capacitor Android 7.6.6, `Bridge.loadWebView` et `WebViewLocalServer.handleProxyRequest`) : le pont est injecté par `addDocumentStartJavaScript`, que la CSP de la page ne gouverne pas ; sur une WebView trop ancienne pour cela, Capacitor relaie la page en ne gardant **pas** nos en-têtes, donc sans CSP. À confirmer sur téléphone après déploiement : un blocage arriverait dans les journaux.

### Alertes Supabase acceptées : ne plus les relever en audit
`get_advisors` (sécurité) en renvoie deux qui sont **voulues ou sans objet**. Vérifiées le 28/10/2026 avec le propriétaire.
- **`auth_leaked_password_protection`** (WARN, « Leaked Password Protection Disabled », audit du 18/10 m5) : **sans objet**. La protection n'existe qu'à partir de l'offre Pro, et le projet est en offre gratuite (`get_organization` : plan `free`). L'interrupteur s'affiche dans le tableau de bord, mais il ne s'applique pas, donc l'alerte reste toujours. Surtout, **aucun mot de passe n'existe** : la connexion passe uniquement par Google (aucun appel de connexion par mot de passe dans `templates/`, `static/js/` ni `routes/auth.py`), et le propriétaire a désactivé le fournisseur Email dans Supabase Auth il y a longtemps. Ce dernier point est déclaré par le propriétaire : les outils MCP ne lisent pas ce réglage. À revoir seulement si une connexion par e-mail est ajoutée un jour.
- **`rls_enabled_no_policy`** (INFO, une ligne par table) : **voulu** depuis la v38. Les tables sont fermées au navigateur : RLS active, aucune règle, droits à `service_role` seul. Le serveur applique lui-même les règles d'accès. Ajouter une règle « self » pour `authenticated` rouvrirait la porte (voir Amis, v52).

## Thème — style « Instrument » (13/10/2026, choisi par le propriétaire sur maquettes)
L'ancien habillage « verre » (dégradés, flous, bleu électrique, pilules, libellés espacés) faisait « app générée par IA ». Remplacé par un style plat d'appareil de mesure :
- **Fond** noir `#000000` (`--bg-base`, repris par `theme-color` et le manifeste) ; blocs `#111111` (`--bg-surface`), blocs relevés `#1a1a1a` ; filets `#262626` / `#333333`. Ni dégradé, ni flou, ni ombre.
- **Une seule couleur vive** : vert citron `#c8f031` (`--accent`), texte **noir** dessus (`--on-accent`). Réservé aux actions principales, aux séries faites et aux records. Une sélection (onglet, filtre, jour choisi) est **blanche**, jamais verte. Orange `#ff9f43` pour « en retard / manqué » seulement (manquer n'est pas une faute : jamais de rouge) ; rouge `#ff5a4e` pour supprimer seulement.
- **Polices** servies par l'app (`static/fonts`, licence OFL, plus d'appel à Google Fonts) : **Barlow** pour le texte, **Barlow Condensed** pour les titres, libellés et chiffres. Titres de page en capitales, alignés à gauche ; libellés en capitales étroites, sans espacement de lettres.
- Coins à 4 px (`--radius-full` aussi : plus de pilules). « Retour » est un lien texte (`.lien-retour`), pas un bouton encadré. **Pas d'emoji dans l'interface** (gabarits et `static/js`) : icônes du sprite ; ✓ et ✕ restent (caractères de texte). Testé par `tests/test_style_instrument_3d.py`.
- **Médailles et PRO** : `--gold` vaut le vert (diamant PRO, trophées, premier), `--silver` le blanc, `--bronze` le gris. Plus de jaune or.
- **Interrupteur** : une case `role="switch"` prend l'allure d'un interrupteur (gris éteint, blanc allumé ; `surfaces.css`). Ligne de réglage : `.reglage` (texte à gauche, interrupteur à droite). Sert à Programme (« Alterner ») et aux Réglages (7 préférences). Les cases « Je comprends » des zones dangereuses restent des cases.
- **Carte de partage** (`static/js/share-card.js`) : fond noir, blocs #111, chiffres en Barlow Condensed (polices chargées avant de dessiner), le chiffre héros en vert.
- Icônes : sprite SVG `static/img/icons.svg` consommé via `<svg><use href="/static/img/icons.svg#name"/></svg>` ; `.icon-accent` prend la couleur du texte qui la porte.
- **Pages publiques** (14/10/2026) : la connexion (`login.html`) est centrée dans la hauteur, ouverte par l'haltère de l'icône de l'app (symbole `#logo` du sprite, même géométrie que `tools/dessiner_icone.py`, testé). La page publique (`landing.html`) montre un croquis SVG de l'accueil, dessiné à la main : **à redessiner si l'accueil change de forme** ; son bouton principal est plein, texte noir, comme « Continuer avec Google ».
- Nombres au format français (« 82,5 kg », `resume_series` dans `core/seance_historique.py`, filtre `|fr`).
- Contraste vérifié par calcul (`tests/test_accessibilite.py`) : texte sur les trois fonds, et noir sur vert.

## Intégration continue
- `.github/workflows/tests.yml` — à chaque push sur `main` et sur chaque PR : `pytest` (dont les tests navigateur, Chromium installé par la CI) puis `node tests/js/run.js`, sur **Python 3.11** comme en production. Une étape refuse de démarrer si `runtime.txt` et le workflow ne sont plus d'accord sur la version.
- Les dépendances sont installées depuis `requirements.txt` **tel quel** : une dépendance oubliée fait échouer la CI au lieu du serveur.
- La suite JS a **sa propre étape** : `tests/test_js.py` s'ignore quand Node est absent, et un test ignoré passerait pour un succès.
- **C'est une barrière** : « Wait for CI » est actif côté Railway (constaté à l'audit du 06/10) ; un commit sur `main` dont la CI échoue n'est pas déployé.

## Git
- **Travail par PR** depuis la PR #6 : une branche, une PR, fusion sur `main` ; Railway redéploie après la CI.
- Auteur : `morauxpaul-jpg <morauxpaul@users.noreply.github.com>`
- Flags requis : `-c user.name="morauxpaul-jpg" -c user.email="morauxpaul@users.noreply.github.com"`
- **CACHE_VERSION** : plus besoin de la bumper à chaque déploiement. La route `/service-worker.js` (`app.py`) suffixe la base (`v133` en tête de `pwa/static/service-worker.js`) avec les 8 premiers caractères de `RAILWAY_GIT_COMMIT_SHA` → chaque déploiement invalide le cache du SW automatiquement. Bumper la base uniquement pour forcer un refresh en local ou si l'APP_SHELL change.

## Conventions UI / UX
- **Jamais** de `prompt()`, `confirm()`, `alert()` natifs — toujours modal in-app ou inline-confirm
- **Inline-confirm** doit rester dans la carte qui le déclenche (programme/séance)
- Page de plomberie (`/admin`, `/auth/debug`) : pas de nav bottom, retour explicite


### Retiré le 01/10/2026 (audit du 30/09, partie 4-C)
- **Arcade** (mini-jeux, `/arcade`) : hors sujet ; sa place sur la landing revient au Coach IA.
- **Profils d'entraînement** (`_profiles`, `_active_profile`, `profile_id` des dossiers) : une hiérarchie profil → programme → séance pour un besoin que « un programme par lieu » couvre. Les routes `/programme/profile/*` n'existent plus ; les clés restent dans les blobs existants, ignorées (9 programmes au 06/10) ; effacées par la v48 le 10/10/2026.
- **Bouton « Séance manquée »** (`/seance/mark-missed`, lignes `SESSION`) : le calendrier déduit déjà une séance manquée. On n'en écrit plus ; les lignes `SESSION` déjà en base restent filtrées par `core.hist.is_session_marker`.

### Styles des gabarits (01/10/2026, audit M9)
- Les attributs `style="…"` fixes des gabarits sont sortis dans `static/css/styles-extraits.css` par `pwa/outils/extraire_styles.py` : une classe `s-xxxxxx` par valeur distincte (949 → 56 attributs ; 484 classes). Restent en ligne : les valeurs calculées par Jinja et `display:none` (des scripts lisent et changent `el.style.display`).
- Priorité : chaque règle porte `:not(#_s):not(#_s)` (poids de deux identifiants), pour garder la préséance qu'avait le style en ligne sur les feuilles de l'app ; un style posé par JavaScript reste en ligne et garde le dernier mot. Vérifié par captures avant/après, pixel à pixel, sur 38 pages et 6 états ouverts.
- Nouveau style dans un gabarit : de préférence une classe nommée dans `components.css` ; sinon relancer l'outil (idempotent). `tests/test_mineurs_audit.py` tient un cliquet (≤ 56) et vérifie que chaque classe générée a sa règle et sert.

### Découpages (01/10/2026, audit M11)
- `templates/seance_edit.html` (1 043 → 206 l.) : `_seance_carte_exercice.html` (attend `exo` et `exo_index`), `_seance_ajout_exercice.html`, `_seance_cardio.html`, `_seance_modale_info.html` ; son `<style>` est devenu `static/css/seance.css`.
- `static/css/components.css` (1 268 l.) → `components.css` + `components-seance.css` + `components-pages.css`, chargés dans cet ordre.
- `routes/seance.py` (969 → 680 l.) : blueprints `seance_fin` (`/seance/finish`, `/seance/debrief`) et `seance_cardio` (`/seance/add-cardio`, `/seance/delete-cardio`) ; `core/bilans_seance.py` (bilans), `core/navigation_seance.py` (retour à l'éditeur).
- `core/cardio_activites.py` : activités, MET, unités km, calories — sortis de `routes/cardio.py`, que quatre routes importaient (4 dépendances entre blueprints en moins).
- Garde-fous : aucun gabarit ni feuille > 900 lignes, aucune route > 850 (`tests/test_mineurs_audit.py`).
