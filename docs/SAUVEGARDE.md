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
   **`age-v…-windows-amd64.zip`**. Pas `darwin` (Mac) ni `linux` : ils n'ont pas de `.exe`.
   Décompresse-le : `age.exe` et `age-keygen.exe` sont dans le sous-dossier **`age`**.
2. Ouvre PowerShell **dans ce sous-dossier** (par exemple
   `cd C:\Users\…\age-v1.3.2-windows-amd64\age`, puis `dir` doit lister `age.exe`) et tape :
   ```
   .\age-keygen.exe -o cle-sauvegarde-muscu.txt
   ```
   Il affiche `Public key: age1…` : c'est ta **clé publique** (elle n'est pas secrète).
   L'avertissement « writing secret key to a world-readable file » concerne Linux et Mac :
   sans objet sous Windows.
3. Le fichier `cle-sauvegarde-muscu.txt` contient ta **clé privée**. Garde-le **hors de GitHub**,
   en deux endroits (gestionnaire de mots de passe + clé USB, par exemple). Un dossier
   `Documents` synchronisé avec OneDrive l'envoie aussi dans ce nuage.
   **Le perdre, c'est perdre toutes les sauvegardes** : personne ne pourra les ouvrir.
   Ne le montre à personne, Claude compris.

### 2. La clé publique dans GitHub

GitHub → le dépôt → Settings → Secrets and variables → Actions → onglet **Variables** →
New repository variable :
- Name : `SAUVEGARDE_CLE_AGE`
- Value : la ligne `age1…` affichée à l'étape 1.

### 3. L'adresse de la base dans GitHub

1. Supabase → le projet → bouton **Connect** (en haut) → onglet **Direct** (« Connection
   string ») → méthode **Session pooler**. Lien direct :
   <https://supabase.com/dashboard/project/pagrkndckkxlbmaasssl?showConnect=true&method=session>.
   La bonne adresse commence par `postgresql://postgres.pagrkndckkxlbmaasssl:` (un point après
   `postgres`) et contient `pooler.supabase.com:5432` (port **5432**). Pas `db.…supabase.co`
   (connexion directe, IPv6 seulement : GitHub ne la joint pas), ni le port 6543 (mode
   « Transaction »).
2. Remplace **tout** `[YOUR-PASSWORD]`, **crochets compris**, par le mot de passe de la base :
   `…pagrkndckkxlbmaasssl:[YOUR-PASSWORD]@aws-…` devient `…pagrkndckkxlbmaasssl:MotDePasse@aws-…`,
   sans espace. Supabase ne réaffiche jamais ce mot de passe : si tu ne l'as plus, Supabase →
   Database → Settings (<https://supabase.com/dashboard/project/pagrkndckkxlbmaasssl/database/settings>)
   → *Reset database password* → *Generate a password*, et le copier dans ton gestionnaire de mots
   de passe **avant** de valider. Lettres et chiffres seulement si tu le choisis toi-même : `@ : / # ? %`
   cassent l'adresse. L'app n'utilise pas ce mot de passe (aucune adresse de base dans le code ;
   elle passe par `SUPABASE_URL` et `SUPABASE_SERVICE_ROLE_KEY`), mais c'est un changement en
   production : à toi de voir.
3. GitHub → Settings → Secrets and variables → Actions → onglet **Secrets** →
   New repository secret :
   - Name : `SUPABASE_DB_URL`
   - Value : l'adresse complète.

### 4. Premier essai

GitHub → Actions → **Sauvegarde** → *Run workflow*. Attendre le rond vert (2 à 3 minutes).
Le journal de l'étape « Restauration d'essai » doit dire :
`Restauration d'essai réussie : N tables, M lignes, toutes retrouvées.`

Puis vérifie une fois que **ta** clé ouvre bien l'archive :
1. Sur la page de l'exécution (Actions → Sauvegarde → l'exécution, la plus récente en haut),
   **tout en bas**, section **Artifacts** : clique sur `sauvegarde-N`. Un `.zip` se télécharge.
2. Décompresse-le **dans le dossier de `age.exe`** : il donne un dossier `sauvegarde-N` qui
   contient `sauvegarde-AAAA-MM-JJ.tar.age`.
3. Dans PowerShell, dans le dossier de `age.exe`, avec le vrai nom du dossier et du fichier :
   ```
   .\age.exe -d -i cle-sauvegarde-muscu.txt -o sauvegarde.tar .\sauvegarde-1\sauvegarde-2026-11-06.tar.age
   tar -xf sauvegarde.tar
   ```
   Les deux commandes n'affichent rien quand tout va bien.
4. Tu dois voir `manifeste.json` (date, version du serveur, nombre de lignes par table : à ouvrir
   avec le Bloc-notes), `public.dump` et `comptes.dump`.
5. **Supprime ensuite** `sauvegarde.tar`, `manifeste.json`, `public.dump` et `comptes.dump` : ils
   contiennent la base **en clair**.

**Fait le 06/11/2026** : exécution n° 1 (`workflow_dispatch`), « Copie faite : 23 tables, 2329 lignes
en tout », « Restauration d'essai réussie : 23 tables, 2329 lignes, toutes retrouvées », archive
de 184 552 octets, ouverte par le propriétaire avec sa clé (manifeste : serveur 17.6, 1 323 séries,
15 comptes).

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
