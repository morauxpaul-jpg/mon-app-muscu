# Coquille native Capacitor (Android → Play Store, iOS plus tard)

## Architecture

La coquille (`android/`, config `capacitor.config.json`) est une app Android
native minimale dont la webview charge **l'URL de prod Railway**. Le code
applicatif reste 100 % dans `pwa/` : un déploiement Railway met à jour l'app
chez tout le monde sans repasser par le Play Store.

Ce que la coquille apporte par rapport à la PWA :
- **AdMob** (bandeaux + interstitiels vidéo) pour les comptes Free ;
- présence sur le Play Store (et l'App Store plus tard, même coquille) ;
- à terme : push natives (FCM), Play Billing pour le Premium.

## Pubs (déjà câblées côté web)

- `pwa/static/js/ads.js` : ne fait RIEN sur le web/PWA. Dans l'app native,
  pour les comptes Free uniquement :
  - bandeau sur Accueil / Progrès / Plus (jamais pendant la séance) ;
  - interstitiel à l'arrivée sur l'accueil après « Terminer la séance »,
    max 1 toutes les 4 h.
- IDs d'annonces (variables Railway, sinon IDs de TEST Google) :
  - `ADMOB_BANNER_ID` — bloc « bannière » AdMob ;
  - `ADMOB_INTERSTITIAL_ID` — bloc « interstitiel ».
- ID d'application AdMob (différent !) : dans
  `android/app/src/main/AndroidManifest.xml` (meta-data
  `com.google.android.gms.ads.APPLICATION_ID`) — actuellement l'ID de test,
  à remplacer avant la prod.

## ⚠️ Bloquant connu : login Google dans la webview

Google **interdit** son OAuth dans les webviews intégrées (erreur
`403 disallowed_useragent`). Le flux actuel (supabase-js → accounts.google.com
dans la page) fonctionnera dans Chrome/PWA mais **PAS dans l'app Capacitor**.

Solution prévue (étape suivante) : connexion Google **native** dans la
coquille → `supabase.auth.signInWithIdToken({ provider: 'google', token })`.
Prérequis côté Google Cloud Console : créer un client OAuth **Android**
(package `com.muscutracker.app` + SHA-1 de la clé) et réutiliser le client
Web existant. Tant que ce n'est pas fait, l'app native ne permet pas de se
connecter — ne pas publier avant.

## Ce qu'il faut sur le PC pour compiler

1. **Android Studio** (https://developer.android.com/studio) — installe aussi
   le SDK et Java.
2. `npm install` à la racine du repo (déjà fait une fois).

## Workflow de build

```bash
# 1. Mettre l'URL de prod dans capacitor.config.json → server.url
# 2. Synchroniser la config/plugins vers le projet Android :
npx cap sync android
# 3. Ouvrir dans Android Studio :
npx cap open android
# 4. Tester sur un téléphone branché (Run ▶), puis générer l'AAB :
#    Build → Generate Signed Bundle / APK → Android App Bundle
#    (créer une keystore au premier build — LA SAUVEGARDER hors du repo)
```

L'AAB s'uploade ensuite sur Play Console — voir `docs/PLAY_STORE.md` pour la
fiche, les déclarations (confidentialité, suppression de compte, data safety,
et désormais : « contient des publicités » = OUI).

## Checklist avant publication

- [ ] `capacitor.config.json` → `server.url` = domaine de prod
- [ ] Login Google natif branché et testé sur téléphone (cf. bloquant)
- [ ] Compte AdMob créé, app déclarée → remplacer l'APPLICATION_ID du manifest
- [ ] Blocs d'annonces créés → `ADMOB_BANNER_ID` / `ADMOB_INTERSTITIAL_ID`
      sur Railway
- [ ] AdMob : déclarer l'app dans Play Console liée (app-ads.txt si demandé)
- [ ] Tester le parcours pub : fin de séance → interstitiel ; bandeau présent
      sur l'accueil en Free, absent en VIP
