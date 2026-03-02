# 💪 MUSCU TRACKER PRO

Application de tracking de musculation avec interface cyber-RPG et jeux intégrés.

## 🚀 Déploiement sur Railway

### Prérequis
- Compte Railway (gratuit) : https://railway.app
- Compte GitHub (gratuit)
- Credentials Google Service Account pour Google Sheets

### Étape 1 : Préparer GitHub

1. **Créer un nouveau repository sur GitHub**
   - Va sur https://github.com/new
   - Nom : `muscu-tracker-pro` (ou autre)
   - Visibility : Private (recommandé)
   - Ne pas initialiser avec README
   - Clique sur "Create repository"

2. **Upload tes fichiers sur GitHub**
   
   Option A - Via l'interface web :
   - Clique sur "uploading an existing file"
   - Drag & drop tous les fichiers :
     - app.py
     - requirements.txt
     - runtime.txt
     - Procfile
     - .gitignore
     - (PAS le fichier secrets.toml !)
   - Commit

   Option B - Via Git CLI :
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/TON-USERNAME/muscu-tracker-pro.git
   git push -u origin main
   ```

### Étape 2 : Déployer sur Railway

1. **Créer un compte Railway**
   - Va sur https://railway.app
   - Sign up with GitHub
   - Autorise Railway à accéder à ton GitHub

2. **Créer un nouveau projet**
   - Clique sur "New Project"
   - Sélectionne "Deploy from GitHub repo"
   - Choisis ton repository `muscu-tracker-pro`
   - Railway va détecter automatiquement que c'est une app Streamlit

3. **Configurer les variables d'environnement (SECRETS)**
   
   Railway va te demander d'ajouter les secrets Google Sheets :
   
   - Clique sur ton projet → Variables
   - Ajoute chaque champ du service account comme variable :
   
   ```
   GCP_TYPE = service_account
   GCP_PROJECT_ID = ton-project-id
   GCP_PRIVATE_KEY_ID = ton-private-key-id
   GCP_PRIVATE_KEY = -----BEGIN PRIVATE KEY-----\nTA_CLE\n-----END PRIVATE KEY-----\n
   GCP_CLIENT_EMAIL = ton-email@project.iam.gserviceaccount.com
   GCP_CLIENT_ID = ton-client-id
   GCP_AUTH_URI = https://accounts.google.com/o/oauth2/auth
   GCP_TOKEN_URI = https://oauth2.googleapis.com/token
   GCP_AUTH_PROVIDER_CERT = https://www.googleapis.com/oauth2/v1/certs
   GCP_CLIENT_CERT = https://www.googleapis.com/robot/v1/metadata/x509/...
   ```

   **IMPORTANT** : Pour `GCP_PRIVATE_KEY`, remplace les retours à la ligne par `\n`
   
   Exemple :
   ```
   -----BEGIN PRIVATE KEY-----
   MIIEvQIBADANBg...
   ...
   -----END PRIVATE KEY-----
   ```
   
   Devient :
   ```
   -----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg...\n...\n-----END PRIVATE KEY-----\n
   ```

4. **Modifier app.py pour lire les variables d'environnement**
   
   Remplace cette section dans app.py :
   ```python
   @st.cache_resource
   def get_gs():
       try:
           creds = dict(st.secrets["gcp_service_account"])
           gc = gspread.service_account_from_dict(creds)
   ```
   
   Par :
   ```python
   import os
   
   @st.cache_resource
   def get_gs():
       try:
           # Check if running on Railway (env vars) or locally (secrets.toml)
           if os.getenv('GCP_PROJECT_ID'):
               creds = {
                   "type": os.getenv('GCP_TYPE'),
                   "project_id": os.getenv('GCP_PROJECT_ID'),
                   "private_key_id": os.getenv('GCP_PRIVATE_KEY_ID'),
                   "private_key": os.getenv('GCP_PRIVATE_KEY'),
                   "client_email": os.getenv('GCP_CLIENT_EMAIL'),
                   "client_id": os.getenv('GCP_CLIENT_ID'),
                   "auth_uri": os.getenv('GCP_AUTH_URI'),
                   "token_uri": os.getenv('GCP_TOKEN_URI'),
                   "auth_provider_x509_cert_url": os.getenv('GCP_AUTH_PROVIDER_CERT'),
                   "client_x509_cert_url": os.getenv('GCP_CLIENT_CERT')
               }
           else:
               creds = dict(st.secrets["gcp_service_account"])
           
           gc = gspread.service_account_from_dict(creds)
   ```

5. **Railway va déployer automatiquement !**
   - Attends 2-3 minutes
   - Clique sur ton service → "View Logs" pour voir l'avancement
   - Une fois déployé, clique sur "Settings" → "Generate Domain"
   - Tu auras une URL comme : `https://ton-app.up.railway.app`

### Étape 3 : Tester et utiliser

1. Ouvre l'URL générée par Railway
2. L'app devrait se charger
3. Ajoute l'URL à l'écran d'accueil de ton téléphone (PWA)

## 📱 Installer comme une App (PWA)

### Sur iPhone (Safari)
1. Ouvre l'URL dans Safari
2. Appuie sur le bouton "Partager" (carré avec flèche)
3. Sélectionne "Sur l'écran d'accueil"
4. Donne un nom : "Muscu Tracker"
5. Appuie sur "Ajouter"

### Sur Android (Chrome)
1. Ouvre l'URL dans Chrome
2. Appuie sur les 3 points (menu)
3. Sélectionne "Installer l'application" ou "Ajouter à l'écran d'accueil"
4. Confirme

## 🔧 Maintenance

### Mettre à jour l'app
1. Modifie ton code localement
2. Push sur GitHub
3. Railway redéploiera automatiquement !

### Voir les logs
- Va sur Railway → ton projet → View Logs

### Monitorer l'usage
- Va sur Railway → ton projet → Usage
- Tu verras ta consommation en temps réel

## 💰 Coût estimé
- **Gratuit** si usage personnel (< 5$/mois)
- RAM: ~0.5-1$/mois
- Trafic: ~0.20-0.50$/mois
- **Total: ~1-2$/mois** (bien dans les 5$ offerts)

## 🆘 Troubleshooting

### L'app ne démarre pas
- Vérifie les logs dans Railway
- Vérifie que toutes les variables d'environnement sont correctes
- Vérifie que `GCP_PRIVATE_KEY` a bien les `\n`

### Erreur Google Sheets
- Vérifie que le Service Account a accès au Google Sheet
- Partage le sheet avec l'email du service account

### L'app se met en veille
- Sur Railway, va dans Settings → Sleep Mode → Désactive-le
- Ou upgrade vers le plan Hobby ($5/mois garanti sans veille)

## 📞 Support
Si tu as des problèmes, vérifie :
1. Les logs Railway
2. Les variables d'environnement
3. Les permissions Google Sheets
