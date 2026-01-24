import streamlit as st
import pandas as pd
import json
import time
import gspread

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Musculation Tracker", layout="centered", page_icon="logo2.png") [cite: 1]

# --- FIX POUR L'ICÔNE SUR MOBILE ---
logo_url = "https://raw.githubusercontent.com/morauxpaul-jpg/mon-app-muscu/main/logo.jpg" [cite: 1]
st.markdown(f"""
    <head>
        <link rel="apple-touch-icon" href="{logo_url}">
        <link rel="icon" sizes="192x192" href="{logo_url}">
        <link rel="icon" sizes="512x512" href="{logo_url}">
    </head>
""", unsafe_allow_html=True) [cite: 1]

# --- 2. DESIGN ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                    linear-gradient(180deg, #0A1931 0%, #000000 100%); [cite: 2]
        background-attachment: fixed; background-size: cover; [cite: 3]
        color: #E0E0E0; font-family: 'Helvetica', sans-serif; [cite: 3]
    }
    .stTabs [data-baseweb="tab-list"] { background-color: rgba(255, 255, 255, 0.05) !important; backdrop-filter: blur(5px); border-radius: 12px; padding: 5px; } [cite: 4, 5]
    .stTabs [aria-selected="true"] { background-color: rgba(255, 255, 255, 0.9) !important; color: #0A1931 !important; border-radius: 8px; font-weight: bold; } [cite: 6, 7]
    .stExpander { background-color: rgba(10, 25, 49, 0.6) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 10px; margin-bottom: 10px; backdrop-filter: blur(5px); } [cite: 8, 9]
    div[data-testid="stMetricValue"] { font-size: 28px !important; color: #4A90E2 !important; font-weight: 800; text-shadow: 0 0 10px rgba(74, 144, 226, 0.5); } [cite: 11, 12]
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS UTILES ---
def calc_1rm(weight, reps): [cite: 32]
    if reps <= 1: return weight
    return weight * (36 / (37 - reps))

# --- CONNEXION GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheets(): [cite: 13]
    credentials_dict = dict(st.secrets["gcp_service_account"]) [cite: 13]
    gc = gspread.service_account_from_dict(credentials_dict) [cite: 13]
    sh = gc.open("Muscu_App") [cite: 13]
    return sh.get_worksheet(0), sh.worksheet("Programme") [cite: 13]

ws_history, ws_prog = get_google_sheets() [cite: 13]

# --- GESTION DU PROGRAMME ---
def load_prog(): [cite: 13]
    val = ws_prog.acell('A1').value [cite: 13]
    return json.loads(val) if val else {} [cite: 13]

def save_prog(prog_data): [cite: 13]
    ws_prog.update_acell('A1', json.dumps(prog_data)) [cite: 13]

# --- GESTION DE L'HISTORIQUE ---
def get_historique(): [cite: 14]
    data = ws_history.get_all_records() [cite: 14]
    if not data: return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"]) [cite: 14]
    df = pd.DataFrame(data) [cite: 14]
    df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float) [cite: 14]
    return df [cite: 14]

def save_historique(df): [cite: 14]
    ws_history.clear() [cite: 14]
    df["Poids"] = df["Poids"].astype(float) [cite: 14]
    data = [df.columns.values.tolist()] + df.values.tolist() [cite: 14]
    ws_history.update(data, value_input_option='USER_ENTERED') [cite: 14]

# Chargement données
programme = load_prog() [cite: 14]
df_history = get_historique() [cite: 14]

# --- SIDEBAR POUR LE TIMER ---
with st.sidebar:
    st.header("⏲️ Paramètres")
    rest_time = st.slider("Temps de repos (sec)", 30, 300, 90, 15)

# Logo
col_logo_1, col_logo_2, col_logo_3 = st.columns([1, 2, 1]) [cite: 14]
with col_logo_2: st.image("logo.png", use_container_width=True) [cite: 14]

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Mes Progrès"]) [cite: 14]

# --- ONGLET 1 : PROGRAMME ---
with tab1:
    st.subheader("Mes Séances") [cite: 14]
    jours = list(programme.keys()) [cite: 15]
    for idx_jour, jour in enumerate(jours): [cite: 16]
        with st.expander(f"⚙️ {jour}"): [cite: 16]
            c_up, c_down, c_del = st.columns([1, 1, 1]) [cite: 17]
            if c_up.button("⬆️", key=f"up_s_{jour}") and idx_jour > 0: [cite: 17]
                jours[idx_jour], jours[idx_jour-1] = jours[idx_jour-1], jours[idx_jour] [cite: 17]
                save_prog({k: programme[k] for k in jours}); st.rerun() [cite: 17]
            if c_del.button("🗑️", key=f"del_s_{jour}"): [cite: 18, 19]
                del programme[jour]; save_prog(programme); st.rerun() [cite: 18, 19]
            for i, exo in enumerate(programme[jour]): [cite: 20]
                c1, c2 = st.columns([8, 2]) [cite: 20]
                c1.write(f"**{exo}**") [cite: 20]
                if c2.button("🗑️", key=f"de_{jour}_{i}"): [cite: 22]
                    programme[jour].pop(i); save_prog(programme); st.rerun() [cite: 22]
            nv = st.text_input("Ajouter exo :", key=f"in_{jour}") [cite: 22]
            if st.button("Ajouter", key=f"btn_{jour}") and nv: [cite: 23]
                programme[jour].append(nv); save_prog(programme); st.rerun() [cite: 23]
    st.subheader("➕ Créer une séance") [cite: 24]
    nvs = st.text_input("Nom séance") [cite: 24]
    if st.button("Créer") and nvs: [cite: 24]
        programme[nvs] = []; save_prog(programme); st.rerun() [cite: 24]

# --- ONGLET 2 : ENTRAÎNEMENT (AVEC TIMER AUTO) ---
with tab2:
    if not programme: st.warning("⚠️ Crée une séance !") [cite: 27]
    else:
        choix_seance = st.selectbox("Séance :", list(programme.keys()), label_visibility="collapsed") [cite: 27]
        sem_actuelle = st.number_input("Semaine N°", min_value=1, value=1) [cite: 27]
        
        for exo in programme[choix_seance]:
            with st.expander(f"🔹 {exo}", expanded=True): [cite: 27]
                # Historique S-1
                h1 = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle - 1) & (df_history["Séance"] == choix_seance)] [cite: 28, 31]
                if not h1.empty:
                    st.caption("🔍 Historique S-1 :") [cite: 28]
                    st.dataframe(h1[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True) [cite: 30]
                
                # Saisie
                data_sem = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance)] [cite: 31]
                default_sets = data_sem[["Série", "Reps", "Poids", "Remarque"]].copy() if not data_sem.empty else pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]}) [cite: 31, 32]
                
                edited_df = st.data_editor(default_sets, num_rows="dynamic", key=f"grid_{exo}", use_container_width=True, column_config={"Poids": st.column_config.NumberColumn("Poids", format="%g", step=0.1)}) [cite: 32]
                
                c_val, c_skip = st.columns(2)
                if c_val.button(f"✅ Valider {exo}"): [cite: 32]
                    valid = edited_df[(edited_df["Poids"] > 0) | (edited_df["Reps"] > 0)].copy() [cite: 32, 33]
                    valid["Semaine"], valid["Séance"], valid["Exercice"] = sem_actuelle, choix_seance, exo [cite: 33, 34]
                    mask = (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance) & (df_history["Exercice"] == exo) [cite: 33, 34]
                    save_historique(pd.concat([df_history[~mask], valid], ignore_index=True)) [cite: 34]
                    
                    # --- LANCEMENT DU CHRONO ---
                    st.success(f"Série validée ! Repos : {rest_time}s") [cite: 35]
                    t_placeholder = st.empty()
                    for t in range(rest_time, 0, -1):
                        t_placeholder.metric("⏳ Temps restant", f"{t}s")
                        time.sleep(1)
                    t_placeholder.success("💥 Allez, série suivante !")
                    st.rerun()
                
                if c_skip.button(f"🚫 Sauter", key=f"skip_{exo}"): [cite: 33]
                    skip_row = pd.DataFrame({"Semaine": [sem_actuelle], "Séance": [choix_seance], "Exercice": [exo], "Série": [1], "Reps": [0], "Poids": [0.0], "Remarque": ["SÉANCE MANQUÉE ❌"]}) [cite: 33, 34]
                    mask = (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance) & (df_history["Exercice"] == exo) [cite: 34]
                    save_historique(pd.concat([df_history[~mask], skip_row], ignore_index=True)); st.rerun() [cite: 34, 35]

# --- ONGLET 3 : PROGRÈS ---
with tab3:
    if df_history.empty: st.info("Fais ton premier entraînement !") [cite: 35]
    else:
        col1, col2, col3 = st.columns(3) [cite: 35]
        df_real = df_history[df_history["Poids"] > 0] [cite: 36]
        col1.metric("Volume total", f"{int((df_history['Poids'] * df_history['Reps']).sum())} kg") [cite: 36]
        col2.metric("Nb Séances", len(df_real.groupby(["Semaine", "Séance"]))) [cite: 36]
        col3.metric("Semaine Max", f"S{df_history['Semaine'].max()}") [cite: 35]
        
        st.divider()
        sel_exo = st.selectbox("Analyse Exercice :", sorted(df_history["Exercice"].unique())) [cite: 36]
        df_exo = df_history[df_history["Exercice"] == sel_exo].copy() [cite: 36]
        
        if not df_exo.empty:
            df_valide = df_exo[df_exo["Poids"] > 0] [cite: 37]
            if not df_valide.empty:
                max_charge = df_valide["Poids"].max() [cite: 37]
                df_valide["1RM"] = df_valide.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
                
                c_rec, c_1rm = st.columns(2)
                c_rec.success(f"🏆 Record : **{max_charge} kg**") [cite: 37]
                c_1rm.info(f"💪 Force (1RM) : **{round(df_valide['1RM'].max(), 1)} kg**")
                
                st.caption("📈 Évolution des charges :") [cite: 37]
                st.line_chart(df_exo.groupby("Semaine")["Poids"].max()) [cite: 37]
            
            with st.expander("Historique complet"): [cite: 37]
                st.dataframe(df_exo[["Semaine", "Séance", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Semaine", "Série"], ascending=[False, True]), hide_index=True, use_container_width=True) [cite: 38]
