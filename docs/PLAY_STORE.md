# Publier Muscu Tracker sur le Play Store

> **Mise à jour 2026-06** : la stratégie est passée de TWA à **Capacitor**
> (coquille native, nécessaire pour les pubs AdMob) — voir
> `docs/CAPACITOR.md` pour générer l'AAB. La section 2 (PWABuilder) est
> conservée pour référence mais n'est plus le chemin retenu. Tout le reste
> (Play Console, fiche, déclarations) reste valable, avec une déclaration en
> plus : **« L'application contient des annonces » = OUI**.

## 1. Compte Play Console (à faire une fois)

- https://play.google.com/console → compte développeur **personnel** (25 $ une
  fois, vérification d'identité sous 1 à 3 jours).

## 2. Générer le package Android avec PWABuilder

1. https://www.pwabuilder.com → entrer l'URL de prod → **Package for stores →
   Android**.
2. Options :
   - **Package ID** : `com.muscutracker.fit` (doit correspondre à la variable
     `TWA_PACKAGE_NAME` sur Railway — c'est la valeur par défaut du code).
   - **App name** : Muscu Tracker.
   - **Signing key** : laisser PWABuilder en générer une.
3. Télécharger le zip. Il contient :
   - `*.aab` → à uploader sur Play Console ;
   - `signing.keystore` + `signing-key-info.txt` → **À SAUVEGARDER
     PRÉCIEUSEMENT** (hors du repo git !). Perdre la keystore = impossible de
     mettre à jour l'app.

## 3. Créer l'app dans Play Console

- Créer l'application (français, app, gratuite).
- **Production → Créer une release** → uploader le `.aab`. Accepter la
  « signature d'application par Google Play » (recommandé).

## 4. Lier le domaine (supprime la barre d'URL Chrome)

1. Play Console → **Configuration → Signature de l'application** → copier
   l'**empreinte SHA-256** du « certificat de la clé de signature
   d'application ».
2. Railway → variables du service web :
   - `TWA_SHA256_FINGERPRINT` = l'empreinte copiée (on peut en mettre
     plusieurs, séparées par des virgules — utile pour ajouter aussi celle de
     la clé d'upload pendant les tests).
   - `TWA_PACKAGE_NAME` = `com.muscutracker.fit` (optionnel, c'est le défaut).
3. Vérifier : `https://<domaine>/.well-known/assetlinks.json` doit répondre un
   JSON avec l'empreinte. Test officiel :
   https://developers.google.com/digital-asset-links/tools/generator

## 5. Fiche Play Store

- **Captures d'écran** : minimum 2 (téléphone). Prendre accueil, séance,
  progrès — en mode PWA installée pour ne pas montrer la barre du navigateur.
- **Icône** 512×512 (déjà dans `pwa/static/icon-512.png`).
- **Bannière (feature graphic)** 1024×500 à créer.
- Titre (30 car.), description courte (80), description longue (4000).

## 6. Déclarations obligatoires

- **Politique de confidentialité** : `https://<domaine>/confidentialite`.
- **Suppression de compte** (Règles → Suppression de compte) : déclarer que
  l'app permet la suppression in-app (Gestion → Supprimer mon compte) et
  donner l'URL web : `https://<domaine>/confidentialite` (section 6, droits).
- **Sécurité des données (Data safety)** :
  - Données collectées : adresse e-mail ; infos personnelles (prénom, âge,
    sexe, poids, taille) ; santé et forme (séances, nutrition) ; messages
    (chat coach IA).
  - Toutes chiffrées en transit (HTTPS) ; suppression possible par
    l'utilisateur ; aucune donnée partagée avec des tiers à des fins pub ;
    pas de publicité.
- **Classification du contenu** : questionnaire → tout public.

## 7. Lancement

- D'abord **Tests internes** (ajouter ton email de testeur) : vérifier
  l'installation, l'absence de barre d'URL, le login Google, les
  notifications.
- Puis promouvoir la release en **Production**. Première review Google :
  quelques jours.

## Mises à jour futures

Le contenu de l'app vient du serveur : un déploiement Railway met à jour
l'app pour tout le monde, **sans repasser par le Play Store**. Une nouvelle
release Play n'est nécessaire que si le wrapper change (icône, splash,
nom de package, permissions).
