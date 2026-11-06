# Sauvegarde de la base — mode d'emploi

Audit du 04/11, B3 : l'offre Supabase gratuite ne sauvegarde rien. Depuis cette
PR, GitHub copie la base **chaque nuit à 02:17 UTC** (workflow « Sauvegarde »,
`.github/workflows/sauvegarde.yml`, script `pwa/tools/sauvegarde_base.py`).

## Ce qui se passe chaque nuit

1. **Copie, en lecture seule**, de la base de production :
   - tout le schéma `public` (séries, programmes, réglages, nutrition, amis…) avec ses droits ;
   - les comptes : `auth.users` et `auth.identities` (le lien entre un compte Google et ses données).
   Une seule photo de la base pour tout : un compte créé pendant la copie n'y entre pas à moitié.
2. **Restauration d'essai** sur un PostgreSQL 17 **vide**, démarré pour l'occasion, puis
   comparaison du nombre de lignes, table par table. Si une seule table diffère, ou si la
   restauration échoue, le workflow échoue et GitHub envoie un e-mail.
3. **Chiffrement** avec `age`, pour ta clé publique. Seule ta clé privée rouvre l'archive.
4. **Archive gardée 14 jours** dans l'exécution du workflow (onglet Actions → Sauvegarde →
   une exécution → « Artifacts »), puis effacée automatiquement par GitHub.

Le dépôt est public : **n'importe quel compte GitHub peut télécharger l'archive**, mais pas la lire.
Le journal ne contient rien de la base, seulement le nombre de tables et de lignes.

## Ce qui n'est PAS sauvegardé

- **Les photos de progression** (10 fichiers, 2,3 Mo au 05/11/2026). Elles sont dans le stockage
  de fichiers de Supabase, que `pg_dump` ne copie pas (et que l'offre Pro ne sauvegarde pas non
  plus). Les sauver demanderait la clé serveur de Supabase dans GitHub : tâche séparée, à décider.
- **Les sessions de connexion** : après une restauration, chacun se reconnecte avec Google.
- Les réglages de Supabase eux-mêmes (fournisseur Google, URL de redirection) : à refaire à la main
  sur un nouveau projet.

## Mise en place (une fois, par toi)

Tant que ces trois réglages manquent, le workflow échoue avec le message
« À créer dans GitHub : … ». Je n'ai et n'aurai jamais leurs valeurs.

### 1. Ta paire de clés

Sur ton PC Windows :

1. Télécharge `age` : <https://github.com/FiloSottile/age/releases> → le fichier
   `age-v…-windows-amd64.zip`. Décompresse-le.
2. Dans ce dossier, ouvre PowerShell et tape :
   ```
   .\age-keygen.exe -o cle-sauvegarde-muscu.txt
   ```
   Il affiche `Public key: age1…` : c'est ta **clé publique** (elle n'est pas secrète).
3. Le fichier `cle-sauvegarde-muscu.txt` contient ta **clé privée**. Garde-le **hors de GitHub**,
   en deux endroits (gestionnaire de mots de passe + clé USB, par exemple).
   **Le perdre, c'est perdre toutes les sauvegardes** : personne ne pourra les ouvrir.

### 2. La clé publique dans GitHub

GitHub → le dépôt → Settings → Secrets and variables → Actions → onglet **Variables** →
New repository variable :
- Name : `SAUVEGARDE_CLE_AGE`
- Value : la ligne `age1…` affichée à l'étape 1.

### 3. L'adresse de la base dans GitHub

1. Supabase → le projet → bouton **Connect** (en haut) → **Session pooler** → copie l'adresse
   (`postgresql://postgres.pagrkndckkxlbmaasssl:[YOUR-PASSWORD]@aws-…pooler.supabase.com:5432/postgres`).
   Pas l'adresse « Direct connection » : GitHub ne la joint pas (IPv6 seulement).
2. Remplace `[YOUR-PASSWORD]` par le mot de passe de la base. Si tu ne l'as plus : Supabase →
   Project Settings → Database → *Reset database password*. L'app n'utilise pas ce mot de passe
   (elle passe par la clé `service_role`), mais c'est un changement en production : à toi de voir.
3. GitHub → Settings → Secrets and variables → Actions → onglet **Secrets** →
   New repository secret :
   - Name : `SUPABASE_DB_URL`
   - Value : l'adresse complète.

### 4. Premier essai

GitHub → Actions → **Sauvegarde** → *Run workflow*. Attendre le rond vert (2 à 3 minutes).
Le journal de l'étape « Restauration d'essai » doit dire :
`Restauration d'essai réussie : N tables, M lignes, toutes retrouvées.`

Puis vérifie une fois que **ta** clé ouvre bien l'archive : télécharge l'artefact (un `.zip`),
décompresse-le, puis dans PowerShell, dans le dossier de `age` :
```
.\age.exe -d -i cle-sauvegarde-muscu.txt -o sauvegarde.tar C:\chemin\sauvegarde-AAAA-MM-JJ.tar.age
tar -xf sauvegarde.tar
```
Tu dois voir `manifeste.json` (date et nombre de lignes par table), `public.dump` et `comptes.dump`.

## Restaurer

### Essai sur un PostgreSQL vide (ce que fait le workflow chaque nuit)

Avec un PostgreSQL 17 vide et les outils `pg_restore` / `psql` 17 :
```
SAUVEGARDE_CIBLE=postgresql://postgres:motdepasse@localhost:5432/postgres \
  python pwa/tools/sauvegarde_base.py verifier dossier-decompresse
```
Le script refuse toute adresse Supabase et toute base qui contient déjà des tables.

### Après une perte réelle, sur un nouveau projet Supabase

**Non essayé sur un vrai projet Supabase** (seulement sur PostgreSQL vide, chaque nuit). À faire
avec une session Claude, mode élevé, et ton accord explicite pour chaque écriture :
1. Créer le projet (région `eu-west-1`), noter son adresse « Session pooler ».
2. Les comptes d'abord, lignes seulement (le nouveau projet a déjà la table `auth.users`) :
   `pg_restore --data-only --dbname=NOUVELLE_ADRESSE comptes.dump`
3. Puis `public`, sans recréer le schéma qui existe déjà :
   `pg_restore --list public.dump | findstr /v /c:"SCHEMA - public" > liste.txt`, puis
   `pg_restore --use-list=liste.txt --dbname=NOUVELLE_ADRESSE public.dump`
4. Le déclencheur d'inscription (`on_auth_user_created`, qui crée profil et programme d'un nouveau
   compte) : l'étape 2 n'a remis que des lignes. Le reposer depuis `comptes.dump` :
   `pg_restore --list comptes.dump | findstr /c:"TRIGGER" > declencheur.txt`, puis
   `pg_restore --use-list=declencheur.txt --dbname=NOUVELLE_ADRESSE comptes.dump`.
5. Recopier dans Railway la nouvelle `SUPABASE_URL` et les nouvelles clés, refaire le fournisseur
   Google dans Supabase, redéployer.

## À savoir

- **Pause après 60 jours** : GitHub arrête les tâches planifiées d'un dépôt public sans activité
  pendant 60 jours, et prévient par e-mail. Un commit, ou un clic sur « Enable workflow », relance.
- **E-mail en cas d'échec** : GitHub l'envoie à l'auteur du dernier changement de l'horaire
  (`cron`) du workflow. Vérifier que les notifications Actions sont actives :
  GitHub → Settings (du compte) → Notifications → Actions.
- **Le secret donne tous les droits sur la base** (mot de passe `postgres`). Le script ne fait que
  lire. Pour aller plus loin : un rôle Postgres en lecture seule dédié à la sauvegarde. C'est une
  écriture en production, donc une tâche séparée, avec ton accord.
- **Taille** : 16 Mo de base au 05/11/2026 ; l'archive chiffrée est plus petite (copie compressée).
