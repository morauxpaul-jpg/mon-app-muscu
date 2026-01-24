import streamlit as st
import pandas as pd
import json
import os
import gspread

# --- CONFIGURATION MOBILE ---
st.set_page_config(page_title="Musculation Tracker", layout="centered", page_icon="logo2.png")

# --- FIX POUR L'ICÔNE SUR MOBILE ---
logo_url = "https://raw.githubusercontent.com/morauxpaul-jpg/mon-app-muscu/main/logo.jpg"
st.markdown(f"""
    <head>
        <link rel="apple-touch-icon" href="{logo_url}">
        <link rel="icon" sizes="192x192" href="{logo_url}">
        <link rel="icon" sizes="512x512" href="{logo_url}">
    </head>
""", unsafe_allow_html=True)

# --- DESIGN MODERNE (TON STYLE) ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                    linear-gradient(180deg, #0A1931 0%, #000000 100%);
        background-attachment: fixed; background-size: cover;
        color: #E0E0E0; font-family: 'Helvetica', sans-serif;
    }
    .stTabs [data-baseweb="tab-list"] { background-color: rgba(255, 255, 255, 0.05) !important; border-radius: 12px; }
    .stTabs [aria-selected="true"] { background-color: rgba(255, 255, 255, 0.9) !important; color: #0A1931 !important; border-radius: 8px; font-weight: bold; }
    .stExpander { background-color: rgba(10, 25, 49, 0.6) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 10px; backdrop-filter: blur(5px); }
</style>
""", unsafe_allow_html=True)

# --- CONNEXION GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheets():
    credentials_dict = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(credentials_dict)
    sh = gc.open("Muscu_App")
    return sh.get_worksheet(0), sh.worksheet("Programme")

ws_history, ws_prog = get_google_sheets()

# --- GESTION DU PROGRAMME (JSON EN A1) ---
DEFAULT_PROG = {}
def load_prog():
    val = ws_prog.acell('A1').value
    if not val: return DEFAULT_PROG
    return json.loads(val)

def save_prog(prog_data):
    ws_prog.update_acell('A1', json.dumps(prog_data))

# --- GESTION DE L'HISTORIQUE ---
def get_historique():
    data = ws_history.get_all_records()
    if not data:
        return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
    df = pd.DataFrame(data)
    # On s'assure que la colonne Poids est bien traitée comme un nombre décimal
    if "Poids" in df.columns:
        df["Poids"] = pd.to_numeric(df["Poids"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
    return df

def save_historique(df):
    ws_history.clear()
    # On remplace les NaN par vide pour ne pas faire planter l'update
    df_clean = df.fillna("")
    data = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
    # L'option 'USER_ENTERED' force Google Sheets à interpréter les points comme des décimales
    ws_history.update(data, value_input_option='USER_ENTERED')

# Chargement
programme = load_prog()
df_history = get_historique()

col_logo_1, col_logo_2, col_logo_3 = st.columns([1, 2, 1])
with col_logo_2:
    st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Mes Progrès"])

# --- ONGLET 1 : PROGRAMME (TON CODE) ---
with tab1:
    st.subheader("Mes Séances")
    jours = list(programme.keys())
    if not jours: st.info("Ton programme est vide.")
    for idx_jour, jour in enumerate(jours):
        exos = programme[jour]
        with st.expander(f"⚙️ {jour}"):
            # (Tes boutons monter/descendre/supprimer ici...)
            st.markdown("---")
            for i, exo in enumerate(exos):
                st.write(f"**{exo}**") # Raccourci pour l'exemple
            nv_exo = st.text_input("Ajouter un exo :", key=f"add_{jour}")
            if st.button("Ajouter", key=f"btn_{jour}") and nv_exo:
                exos.append(nv_exo); save_prog(programme); st.rerun()

# --- ONGLET 2 : ENTRAÎNEMENT (AVEC FIX DÉCIMALES) ---
with tab2:
    if not programme: st.warning("Crée d'abord une séance !")
    else:
        c1, c2 = st.columns([2, 1])
        choix_seance = c1.selectbox("Séance :", list(programme.keys()))
        sem_actuelle = c2.number_input("Semaine", min_value=1, value=1)
        
        for exo in programme[choix_seance]:
            with st.expander(f"🔹 {exo}", expanded=True):
                data_sem = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle)]
                if not data_sem.empty:
                    default_sets = data_sem[["Série", "Reps", "Poids", "Remarque"]].copy()
                else:
                    default_sets = pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]})
                
                # CONFIGURATION DU TABLEAU POUR LES VIRGULES
                edited_df = st.data_editor(
                    default_sets, 
                    num_rows="dynamic", 
                    key=f"grid_{exo}", 
                    use_container_width=True,
                    column_config={
                        "Poids": st.column_config.NumberColumn("Poids (kg)", format="%g", step=0.05)
                    }
                )
                
                if st.button(f"✅ Valider {exo}"):
                    valid = edited_df[(edited_df["Poids"] > 0) | (edited_df["Reps"] > 0)].copy()
                    valid["Semaine"], valid["Séance"], valid["Exercice"] = sem_actuelle, choix_seance, exo
                    mask = (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance) & (df_history["Exercice"] == exo)
                    new_df = pd.concat([df_history[~mask], valid], ignore_index=True)
                    save_historique(new_df)
                    st.success("Sauvegardé !"); st.rerun()

# --- ONGLET 3 : PROGRÈS (TON CODE) ---
with tab3:
    if not df_history.empty:
        selected_exo = st.selectbox("Exercice :", sorted(list(df_history["Exercice"].unique())))
        df_exo = df_history[df_history["Exercice"] == selected_exo]
        st.line_chart(df_exo.groupby("Semaine")["Poids"].max())
