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

## Login Google natif (code en place — reste la config Google + le build)

Google **interdit** son OAuth dans les webviews intégrées (erreur
`403 disallowed_useragent`). Le flux web (supabase-js → accounts.google.com)
marche en Chrome/PWA mais **PAS dans l'app Capacitor**.

**Côté code (fait, 2026-06-15)** : `templates/login.html` détecte l'app native
(`Capacitor.isNativePlatform()`) et bascule sur le **Google Sign-In natif** via
le plugin `@capgo/capacitor-social-login` :
`SocialLogin.initialize({ google: { webClientId } })` → `SocialLogin.login(...)`
(avec nonce SHA-256) → `supabase.auth.signInWithIdToken({ provider:'google', token, nonce })`
→ POST `/auth/session` (même bridge JWT que le web). Sur le web, `Capacitor` est
absent → flux OAuth classique inchangé. Aucun changement backend (le JWT Supabase
est validé comme avant).

**Reste à faire (config + build, côté toi)** :
1. **Google Cloud Console** :
   - récupérer l'**ID client OAuth Web** existant (celui déjà utilisé par
     Supabase) → le poser sur Railway dans `GOOGLE_WEB_CLIENT_ID` ;
   - créer un **ID client OAuth Android** : type Android, package
     `com.muscutracker.app`, empreinte **SHA-1** de la keystore de signature
     (debug pour tester, release pour publier — `keytool -list -v -keystore …`).
2. **Supabase** → Auth → Providers → Google : vérifier que le client Web est
   bien le « Authorized Client ID » (sinon l'idToken sera rejeté).
3. **Build** : `npm install` (récupère le plugin) → `npx cap sync android` →
   tester sur téléphone. Le plugin lit `GOOGLE_WEB_CLIENT_ID` au runtime (servi
   par Flask), donc rien à hardcoder dans la coquille.

⚠️ Tant que `GOOGLE_WEB_CLIENT_ID` n'est pas posé **et** que l'ID client Android
n'existe pas dans Google Cloud, le bouton natif affichera une erreur — ne pas
publier avant d'avoir testé la connexion sur un vrai téléphone.

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
- [ ] `GOOGLE_WEB_CLIENT_ID` posé sur Railway + ID client OAuth Android créé (SHA-1)
- [ ] Login Google natif testé sur téléphone (le code est en place, cf. section)
- [ ] Compte AdMob créé, app déclarée → remplacer l'APPLICATION_ID du manifest
- [ ] Blocs d'annonces créés → `ADMOB_BANNER_ID` / `ADMOB_INTERSTITIAL_ID`
      sur Railway
- [ ] AdMob : déclarer l'app dans Play Console liée (app-ads.txt si demandé)
- [ ] Tester le parcours pub : fin de séance → interstitiel ; bandeau présent
      sur l'accueil en Free, absent en VIP
