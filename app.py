import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Musculation Tracker",
    page_icon="logo.jpg",
    layout="centered"
)

# --- DESIGN SOMBRE & LUMINEUX ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                    linear-gradient(180deg, #0A1931 0%, #000000 100%);
        background-attachment: fixed;
        color: #E0E0E0;
    }
    .stTabs [data-baseweb="tab-list"] { 
        background-color: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(5px);
        border-radius: 12px;
    }
    .stExpander {
        background-color: rgba(10, 25, 49, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- CONNEXION GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    # Remplace par le nom EXACT de ton fichier Google Sheets
    sh = client.open("Muscu_App") 
    return sh.worksheet("Historique"), sh.worksheet("Programme")

ws_hist, ws_prog = get_google_sheets()

# --- CHARGEMENT DES DONNÉES ---
df_programme = pd.DataFrame(ws_prog.get_all_records())

# --- INTERFACE ---
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image("logo.jpg", use_container_width=True)

# Sélection de la séance
seances_disponibles = df_programme['Séance'].unique()
seance_choisie = st.selectbox("Choisir la séance :", seances_disponibles)

# Filtrer les exercices pour cette séance
exercices_du_jour = df_programme[df_programme['Séance'] == seance_choisie]

# Formulaire de saisie
with st.form("workout_form"):
    st.write(f"### 🗓️ {datetime.now().strftime('%d/%m/%Y')}")
    
    all_data = [] # Pour stocker ce qu'on va sauvegarder
    
    for _, row in exercices_du_jour.iterrows():
        exo = row['Exercice']
        nb_series = int(row['Séries']) # Ici on utilise ta colonne Séries !
        
        with st.expander(f"💪 {exo} ({nb_series} séries prévues)"):
            for i in range(1, nb_series + 1):
                c1, c2, c3 = st.columns([1, 2, 2])
                c1.write(f"S{i}")
                poids = c2.number_input(f"Poids (kg)", key=f"p_{exo}_{i}", step=0.5)
                reps = c3.number_input(f"Reps", key=f"r_{exo}_{i}", step=1)
                all_data.append([datetime.now().strftime('%Y-%m-%d'), seance_choisie, exo, i, poids, reps])

    submit = st.form_submit_button("Enregistrer la séance ✅")

if submit:
    # Filtrer pour n'envoyer que les séries remplies (poids ou reps > 0)
    data_to_save = [d for d in all_data if d[4] > 0 or d[5] > 0]
    if data_to_save:
        ws_hist.append_rows(data_to_save)
        st.success("Séance enregistrée dans Google Sheets ! 🔥")
    else:
        st.warning("Remplis au moins une série avant d'enregistrer.")
