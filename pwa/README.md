# Muscu Tracker PRO — PWA

Version PWA (Flask) en cours de migration depuis le Streamlit d'origine (`../app.py` sur `main`).
Les deux apps tournent en parallèle sur le **même Google Sheet** `Muscu_App`.

## Lancer en local

```bash
cd pwa
pip install -r requirements.txt
# Option A : fichier credentials.json à la racine de /pwa/
# Option B : variable d'env GOOGLE_CREDENTIALS (JSON complet)
# Option C : les variables GCP_* existantes (compat Render Streamlit)
python app.py
```

Puis ouvre http://localhost:5000.

## Générer les icônes PWA

```bash
pip install pillow
python generate_icons.py
```

## Déploiement Render

- `Procfile` → `gunicorn app:app`
- Variable d'env à définir : `GOOGLE_CREDENTIALS` (le JSON du service account en une seule valeur).

## État de la migration

- [x] **Commit 1** : squelette + layout de base (nav, thème CSS, manifest, SW)
- [ ] Commit 2 : accueil
- [ ] Commit 3 : séance
- [ ] Commit 4 : programme
- [ ] Commit 5 : progrès
- [ ] Commit 6 : gestion
- [ ] Commit 7 : arcade
