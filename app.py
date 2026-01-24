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
        background: 
            radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
            linear-gradient(180deg, #0A1931 0%, #000000 100%);
        background-attachment: fixed;
        background-size: cover;
        color: #E0E0E0;
        font-family: 'Helvetica', sans-serif;
    }
    .stTabs [data-baseweb="tab-list"] { 
        background-color: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(5px);
        border-radius: 12px;
        padding: 5px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stTabs [aria-selected="true"] { 
        background-color: rgba(255, 255, 255, 0.9) !important;
        color: #0A1931 !important;
        border-radius: 8px;
        font-weight: bold;
    }
    .stExpander {
        background-color: rgba(10, 25, 49, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 10px;
        margin-bottom: 10px;
        backdrop-filter: blur(5px);
    }
    .streamlit-expanderHeader { color: #FFFFFF !important; font-weight: 600; }
    div[data-testid="stMetricValue"] { 
        font-size: 28px !important; color: #4A90E2 !important;
        font-weight: 800; text-shadow: 0 0 10px rgba(74, 144, 226, 0.5);
    }
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
    if not val:
        save_prog(DEFAULT_PROG)
        return DEFAULT_PROG
    return json.loads(val)

def save_prog(prog_data):
    ws_prog.update_acell('A1', json.dumps(prog_data))

# --- GESTION DE L'HISTORIQUE ---
def get_historique():
    data = ws_history.get_all_records()
    if not data:
        return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
    df = pd.DataFrame(data)
    # On force la conversion en nombre décimal à la lecture
    if "Poids" in df.columns:
        df["Poids"] = pd.to_numeric(df["Poids"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
    return df

def save_historique(df):
    ws_history.clear()
    # On force le type float (décimal) avant l'envoi
    df["Poids"] = df["Poids"].astype(float)
    data = [df.columns.values.tolist()] + df.values.tolist()
    # On utilise USER_ENTERED pour que Sheets respecte le format envoyé
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
            c_up, c_down, c_del = st.columns([1, 1, 1])
            if c_up.button("⬆️ Monter", key=f"up_s_{jour}") and idx_jour > 0:
                jours[idx_jour], jours[idx_jour-1] = jours[idx_jour-1], jours[idx_jour]
                save_prog({k: programme[k] for k in jours}); st.rerun()
            if c_down.button("⬇️ Descendre", key=f"down_s_{jour}") and idx_jour < len(jours)-1:
                jours[idx_jour], jours[idx_jour+1] = jours[idx_jour+1], jours[idx_jour]
                save_prog({k: programme[k] for k in jours}); st.rerun()
            if c_del.button("🗑️", key=f"del_s_{jour}"):
                del programme[jour]; save_prog(programme); st.rerun()
            st.markdown("---")
            for i, exo in enumerate(exos):
                c1, c2, c3, c4 = st.columns([6, 1, 1, 1])
                c1.write(f"**{exo}**")
                if c2.button("⬆️", key=f"ue_{jour}_{i}"): 
                    exos[i], exos[i-1] = exos[i-1], exos[i]; save_prog(programme); st.rerun()
                if c4.button("🗑️", key=f"de_{jour}_{i}"): 
                    exos.pop(i); save_prog(programme); st.rerun()
            nv_exo = st.text_input("Nouvel exo :", key=f"add_{jour}")
            if st.button("Ajouter", key=f"badd_{jour}") and nv_exo:
                exos.append(nv_exo); save_prog(programme); st.rerun()

    st.subheader("➕ Créer une séance")
    nv_s = st.text_input("Nom séance")
    if st.button("Créer") and nv_s:
        programme[nv_s] = []; save_prog(programme); st.rerun()

# --- ONGLET 2 : ENTRAÎNEMENT (AVEC FORÇAGE 10.0) ---
with tab2:
    if not programme: st.warning("⚠️ Crée une séance !")
    else:
        c1, c2 = st.columns([2, 1])
        choix_seance = c1.selectbox("Séance :", list(programme.keys()))
        sem_actuelle = c2.number_input("Semaine", min_value=1, value=1)
        
        for exo in programme[choix_seance]:
            with st.expander(f"🔹 {exo}", expanded=True):
                # Données par défaut avec .0
                data_sem = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle)]
                default_sets = data_sem[["Série", "Reps", "Poids", "Remarque"]].copy() if not data_sem.empty else pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]})
                
                # CONFIGURATION POUR FORCER LE .0 (%.1f)
                edited_df = st.data_editor(
                    default_sets, 
                    num_rows="dynamic", 
                    key=f"grid_{exo}", 
                    use_container_width=True,
                    column_config={
                        "Poids": st.column_config.NumberColumn(
                            "Poids (kg)",
                            min_value=0.0,
                            step=0.1,
                            format="%.1f" # <--- FORCE L'AFFICHAGE DU .0
                        )
                    }
                )
                
                if st.button(f"✅ Valider {exo}"):
                    valid = edited_df[(edited_df["Poids"] > 0) | (edited_df["Reps"] > 0)].copy()
                    valid["Semaine"], valid["Séance"], valid["Exercice"] = sem_actuelle, choix_seance, exo
                    mask = (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance
