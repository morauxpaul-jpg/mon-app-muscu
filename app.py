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
    .stTabs [data-baseweb="tab-list"] { background-color: rgba(255, 255, 255, 0.05) !important; border-radius: 12px; padding: 5px; }
    .stTabs [aria-selected="true"] { background-color: rgba(255, 255, 255, 0.9) !important; color: #0A1931 !important; border-radius: 8px; font-weight: bold; }
    .stExpander { background-color: rgba(10, 25, 49, 0.6) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 10px; margin-bottom: 10px; backdrop-filter: blur(5px); }
    div[data-testid="stMetricValue"] { font-size: 28px !important; color: #4A90E2 !important; font-weight: 800; text-shadow: 0 0 10px rgba(74, 144, 226, 0.5); }
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

# --- GESTION DU PROGRAMME ---
DEFAULT_PROG = {}
def load_prog():
    val = ws_prog.acell('A1').value
    if not val: return DEFAULT_PROG
    return json.loads(val)

def save_prog(prog_data):
    ws_prog.update_acell('A1', json.dumps(prog_data))

# --- GESTION DE L'HISTORIQUE (FIX DÉCIMALES) ---
def get_historique():
    data = ws_history.get_all_records()
    if not data:
        return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
    df = pd.DataFrame(data)
    # VERROU 1 : On force le Poids en décimal dès la lecture
    if "Poids" in df.columns:
        df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
    return df

def save_historique(df):
    ws_history.clear()
    # VERROU 2 : On s'assure que le Poids est bien un float avant l'envoi
    df["Poids"] = df["Poids"].astype(float)
    data = [df.columns.values.tolist()] + df.values.tolist()
    # VERROU 3 : USER_ENTERED pour que Sheets ne change pas le format
    ws_history.update(data, value_input_option='USER_ENTERED')

# Chargement
programme = load_prog()
df_history = get_historique()

col_logo_1, col_logo_2, col_logo_3 = st.columns([1, 2, 1])
with col_logo_2:
    st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Mes Progrès"])

# --- ONGLET 1 (TON CODE) ---
with tab1:
    st.subheader("Mes Séances")
    jours = list(programme.keys())
    for idx_jour, jour in enumerate(jours):
        exos = programme[jour]
        with st.expander(f"⚙️ {jour}"):
            if st.button("🗑️ Supprimer la séance", key=f"del_{jour}"):
                del programme[jour]; save_prog(programme); st.rerun()
            for i, exo in enumerate(exos):
                c1, c2 = st.columns([8, 2])
                c1.write(f"**{exo}**")
                if c2.button("🗑️", key=f"de_{jour}_{i}"):
                    exos.pop(i); save_prog(programme); st.rerun()
            nv = st.text_input("Ajouter un exo :", key=f"in_{jour}")
            if st.button("Ajouter", key=f"btn_{jour}") and nv:
                exos.append(nv); save_prog(programme); st.rerun()
    st.subheader("➕ Créer une séance")
    nvs = st.text_input("Nom séance")
    if st.button("Créer") and nvs:
        programme[nvs] = []; save_prog(programme); st.rerun()

# --- ONGLET 2 (FIXÉ POUR 10.0) ---
with tab2:
    if not programme: st.warning("Crée d'abord une séance !")
    else:
        c1, c2 = st.columns([2, 1])
        choix_seance = c1.selectbox("Séance :", list(programme.keys()), label_visibility="collapsed")
        sem_actuelle = c2.number_input("Semaine", min_value=1, value=1, label_visibility="collapsed")
        
        for exo in programme[choix_seance]:
            with st.expander(f"🔹 {exo}", expanded=True):
                data_sem = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle)]
                # On force les 0.0 ici aussi
                default_sets = data_sem[["Série", "Reps", "Poids", "Remarque"]].copy() if not data_sem.empty else pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]})
                
                edited_df = st.data_editor(
                    default_sets, 
                    num_rows="dynamic", 
                    key=f"grid_{exo}", 
                    use_container_width=True,
                    column_config={
                        "Poids": st.column_config.NumberColumn("Poids (kg)", format="%.1f", step=0.1)
                    }
                )
                
                if st.button(f"✅ Valider {exo}"):
                    valid = edited_df[(edited_df["Poids"] > 0) | (edited_df["Reps"] > 0)].copy()
                    # VERROU 4 : Forcer le float sur les nouvelles données avant le concat
                    valid["Poids"] = valid["Poids"].astype(float)
                    valid["Semaine"], valid["Séance"], valid["Exercice"] = sem_actuelle, choix_seance, exo
                    
                    mask = (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance) & (df_history["Exercice"] == exo)
                    new_df = pd.concat([df_history[~mask], valid], ignore_index=True)
                    # VERROU 5 : Forcer le float sur tout le tableau final
                    new_df["Poids"] = new_df["Poids"].astype(float)
                    save_historique(new_df)
                    st.success("Sauvegardé !"); st.rerun()

# --- ONGLET 3 ---
with tab3:
    if not df_history.empty:
        total_p = (df_history["Poids"] * df_history["Reps"]).sum()
        st.metric("Poids total cumulé", f"{int(total_p)} kg")
        sel_exo = st.selectbox("Exercice :", sorted(list(df_history["Exercice"].unique())))
        df_e = df_history[df_history["Exercice"] == sel_exo]
        st.line_chart(df_e.groupby("Semaine")["Poids"].max())
