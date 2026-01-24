import streamlit as st
import pandas as pd
import json
import os
import gspread

# --- 1. CONFIGURATION PAGE (C'est ici que l'erreur arrivait) ---
st.set_page_config(page_title="Musculation Tracker", layout="centered", page_icon="logo2.png") [cite: 1]

# --- FIX POUR L'ICÔNE SUR MOBILE ---
logo_url = "https://raw.githubusercontent.com/morauxpaul-jpg/mon-app-muscu/main/logo.jpg"
st.markdown(f"""
    <head>
        <link rel="apple-touch-icon" href="{logo_url}">
        <link rel="icon" sizes="192x192" href="{logo_url}">
        <link rel="icon" sizes="512x512" href="{logo_url}">
    </head>
""", unsafe_allow_html=True)

# --- 2. DESIGN (TON STYLE BLEU NUIT) ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                    linear-gradient(180deg, #0A1931 0%, #000000 100%);
        background-attachment: fixed; background-size: cover;
        color: #E0E0E0; font-family: 'Helvetica', sans-serif;
    }
    .stTabs [data-baseweb="tab-list"] { background-color: rgba(255, 255, 255, 0.05) !important; backdrop-filter: blur(5px); border-radius: 12px; } [cite: 3, 4]
    .stTabs [aria-selected="true"] { background-color: rgba(255, 255, 255, 0.9) !important; color: #0A1931 !important; border-radius: 8px; font-weight: bold; } [cite: 5, 6, 7]
    .stExpander { background-color: rgba(10, 25, 49, 0.6) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 10px; backdrop-filter: blur(5px); } [cite: 8, 9]
    div[data-testid="stMetricValue"] { color: #4A90E2 !important; font-weight: 800; text-shadow: 0 0 10px rgba(74, 144, 226, 0.5); } [cite: 11, 12]
</style>
""", unsafe_allow_html=True)

# --- 3. CONNEXION ---
@st.cache_resource
def get_google_sheets():
    credentials_dict = dict(st.secrets["gcp_service_account"]) [cite: 13]
    gc = gspread.service_account_from_dict(credentials_dict) [cite: 13]
    sh = gc.open("Muscu_App") [cite: 13]
    return sh.get_worksheet(0), sh.worksheet("Programme") [cite: 13]

ws_history, ws_prog = get_google_sheets()

# --- 4. GESTION PROGRAMME (JSON EN A1) ---
DEFAULT_PROG = {}
def load_prog():
    val = ws_prog.acell('A1').value [cite: 13]
    if not val: return DEFAULT_PROG [cite: 13]
    return json.loads(val) [cite: 13]

def save_prog(prog_data):
    ws_prog.update_acell('A1', json.dumps(prog_data)) [cite: 13]

# --- 5. GESTION HISTORIQUE (FIX DÉCIMALES) ---
def get_historique():
    data = ws_history.get_all_records() [cite: 14]
    if not data: return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"]) [cite: 14]
    df = pd.DataFrame(data) [cite: 14]
    if "Poids" in df.columns:
        df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
    return df

def save_historique(df):
    ws_history.clear() [cite: 14]
    df["Poids"] = df["Poids"].astype(float)
    data = [df.columns.values.tolist()] + df.values.tolist() [cite: 14]
    ws_history.update(data, value_input_option='USER_ENTERED') [cite: 14]

# Chargement données
programme = load_prog() [cite: 14]
df_history = get_historique() [cite: 14]

col_logo_1, col_logo_2, col_logo_3 = st.columns([1, 2, 1]) [cite: 14]
with col_logo_2: st.image("logo.png", use_container_width=True) [cite: 14]

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Mes Progrès"]) [cite: 14]

# ================= ONGLET 1 : PROGRAMME (TON CODE INITIAL) =================
with tab1:
    st.subheader("Mes Séances")
    jours = list(programme.keys()) [cite: 15]
    if not jours: st.info("Programme vide.") [cite: 15, 16]
    for idx_jour, jour in enumerate(jours):
        exos = programme[jour]
        with st.expander(f"⚙️ {jour}"):
            c_up, c_down, c_del = st.columns([1, 1, 1]) [cite: 16]
            if c_up.button("⬆️ Monter", key=f"up_s_{jour}") and idx_jour > 0: [cite: 17]
                jours[idx_jour], jours[idx_jour-1] = jours[idx_jour-1], jours[idx_jour] [cite: 17]
                save_prog({k: programme[k] for k in jours}); st.rerun() [cite: 17]
            if c_down.button("⬇️ Descendre", key=f"down_s_{jour}") and idx_jour < len(jours)-1: [cite: 17]
                jours[idx_jour], jours[idx_jour+1] = jours[idx_jour+1], jours[idx_jour] [cite: 18]
                save_prog({k: programme[k] for k in jours}); st.rerun() [cite: 18]
            if c_del.button("🗑️ Supprimer", key=f"del_s_{jour}"): [cite: 18]
                del programme[jour]; save_prog(programme); st.rerun() [cite: 18]
            st.markdown("---")
            for i, exo in enumerate(exos):
                c1, c2, c3, c4 = st.columns([6, 1, 1, 1]) [cite: 20]
                c1.write(f"**{exo}**") [cite: 20]
                if c2.button("⬆️", key=f"ue_{jour}_{i}") and i > 0: [cite: 20]
                    exos[i], exos[i-1] = exos[i-1], exos[i]; save_prog(programme); st.rerun() [cite: 20, 21]
                if c4.button("🗑️", key=f"de_{jour}_{i}"): [cite: 22]
                    exos.pop(i); save_prog(programme); st.rerun() [cite: 22]
            nv = st.text_input("Ajouter exo :", key=f"in_{jour}", placeholder="+ Nouvel exo") [cite: 22]
            if st.button("Ajouter l'exo", key=f"btn_{jour}") and nv: [cite: 23]
                exos.append(nv); save_prog(programme); st.rerun() [cite: 23]

# ================= ONGLET 2 : ENTRAÎNEMENT (FIX VIRGULES) =================
with tab2:
    if not programme: st.warning("Crée d'abord une séance !") [cite: 27]
    else:
        c1, c2 = st.columns([2, 1]) [cite: 27]
        choix_seance = c1.selectbox("Séance :", list(programme.keys()), label_visibility="collapsed") [cite: 27]
        sem_actuelle = c2.number_input("Semaine N°", min_value=1, value=1, label_visibility="collapsed") [cite: 27]
        for exo in programme[choix_seance]:
            with st.expander(f"🔹 {exo}", expanded=True): [cite: 27]
                h1 = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle - 1)] [cite: 28]
                if not h1.empty:
                    st.caption("🔍 Historique S-1 :") [cite: 28]
                    st.dataframe(h1[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True) [cite: 30]
                data_sem = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance)] [cite: 31]
                default_sets = data_sem[["Série", "Reps", "Poids", "Remarque"]].copy() if not data_sem.empty else pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]}) [cite: 31, 32]
                edited_df = st.data_editor(default_sets, num_rows="dynamic", key=f"grid_{exo}", use_container_width=True, column_config={"Poids": st.column_config.NumberColumn("Poids", format="%g", step=0.1)}) [cite: 32]
                if st.button(f"✅ Valider {exo}"): [cite: 32]
                    valid = edited_df[(edited_df["Poids"] > 0) | (edited_df["Reps"] > 0)].copy() [cite: 32, 33]
                    valid["Semaine"], valid["Séance"], valid["Exercice"] = sem_actuelle, choix_seance, exo [cite: 33]
                    mask = (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance) & (df_history["Exercice"] == exo) [cite: 33, 34]
                    save_historique(pd.concat([df_history[~mask], valid], ignore_index=True)); st.success("Sauvegardé !"); st.rerun() [cite: 34, 35]

# ================= ONGLET 3 : PROGRÈS (RESTAURÉ À 100%) =================
with tab3:
    if df_history.empty: st.info("Fais ton premier entraînement !") [cite: 35]
    else:
        st.subheader("📊 Résumé Global") [cite: 35]
        col1, col2, col3 = st.columns(3) [cite: 35]
        total_poids = (df_history["Poids"] * df_history["Reps"]).sum() [cite: 35]
        max_semaine = df_history["Semaine"].max() [cite: 35]
        col1.metric("Semaine Max", f"S{max_semaine}") [cite: 35]
        col2.metric("Poids total", f"{int(total_poids)} kg") [cite: 36]
        col3.metric("Nb Séances", df_history["Séance"].nunique() * max_semaine) [cite: 36]
        st.markdown("---")
        st.subheader("🎯 Zoom par exercice") [cite: 36]
        exo_list = sorted(list(df_history["Exercice"].unique())) [cite: 36]
        selected_exo = st.selectbox("Choisis un exercice :", exo_list) [cite: 36]
        df_exo = df_history[df_history["Exercice"] == selected_exo].copy() [cite: 36]
        if not df_exo.empty:
            max_p = df_exo["Poids"].max() [cite: 36, 37]
            rec = df_exo[df_exo["Poids"] == max_p].iloc[0] [cite: 37]
            st.success(f"🏆 Record : **{rec['Poids']} kg x {rec['Reps']}** (S{rec['Semaine']})") [cite: 37]
            progression = df_exo.groupby("Semaine")["Poids"].max() [cite: 37]
            st.line_chart(progression) [cite: 37]
            with st.expander("Voir tout l'historique"): [cite: 37]
                st.dataframe(df_exo[["Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Semaine", "Série"], ascending=[False, True]), hide_index=True, use_container_width=True) [cite: 38]
