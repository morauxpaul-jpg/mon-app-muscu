import streamlit as st
import pandas as pd
import json
import os
import gspread

# --- CONFIGURATION PAGE ---
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

# --- DESIGN MODERNE ---
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

# --- FONCTION CALCUL 1RM ---
def calc_1rm(weight, reps):
    if reps == 0: return 0
    if reps == 1: return weight
    return weight * (36 / (37 - reps))

# --- CONNEXION GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheets():
    credentials_dict = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(credentials_dict)
    sh = gc.open("Muscu_App")
    return sh.get_worksheet(0), sh.worksheet("Programme")

ws_history, ws_prog = get_google_sheets()

# --- GESTION DU PROGRAMME ---
def load_prog():
    val = ws_prog.acell('A1').value
    return json.loads(val) if val else {}

def save_prog(prog_data):
    ws_prog.update_acell('A1', json.dumps(prog_data))

# --- GESTION DE L'HISTORIQUE ---
def get_historique():
    data = ws_history.get_all_records()
    if not data: return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
    df = pd.DataFrame(data)
    df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
    return df

def save_historique(df):
    ws_history.clear()
    df["Poids"] = df["Poids"].astype(float)
    data = [df.columns.values.tolist()] + df.values.tolist()
    ws_history.update(data, value_input_option='USER_ENTERED')

# Chargement
programme = load_prog()
df_history = get_historique()

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Mes Progrès"])

# --- ONGLET 1 : PROGRAMME ---
with tab1:
    st.subheader("Mes Séances")
    jours = list(programme.keys())
    for idx, jour in enumerate(jours):
        with st.expander(f"⚙️ {jour}"):
            if st.button("🗑️ Supprimer séance", key=f"del_s_{jour}"):
                del programme[jour]; save_prog(programme); st.rerun()
            for i, exo in enumerate(programme[jour]):
                c1, c2 = st.columns([8, 2])
                c1.write(f"**{exo}**")
                if c2.button("🗑️", key=f"del_e_{jour}_{i}"):
                    programme[jour].pop(i); save_prog(programme); st.rerun()
            nv = st.text_input("Ajouter exo :", key=f"in_{jour}")
            if st.button("Ajouter", key=f"btn_{jour}") and nv:
                programme[jour].append(nv); save_prog(programme); st.rerun()
    nvs = st.text_input("Nouvelle Séance")
    if st.button("Créer séance") and nvs:
        programme[nvs] = []; save_prog(programme); st.rerun()

# --- ONGLET 2 : ENTRAÎNEMENT (VOLUME & PROGRESSION) ---
with tab2:
    if not programme: st.warning("Crée d'abord une séance !")
    else:
        c1, c2 = st.columns([2, 1])
        choix_s = c1.selectbox("Séance :", list(programme.keys()))
        sem = c2.number_input("Semaine", min_value=1, value=1)
        
        for exo in programme[choix_s]:
            with st.expander(f"🔹 {exo}", expanded=True):
                # Historique filtré
                h1 = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem - 1) & (df_history["Séance"] == choix_s)]
                vol_h1 = (h1["Poids"] * h1["Reps"]).sum()
                
                if not h1.empty:
                    st.caption(f"🔍 S-1 : {int(vol_h1)} kg total")
                    st.dataframe(h1[["Série", "Reps", "Poids"]], hide_index=True, use_container_width=True)
                
                # Saisie
                data_curr = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem) & (df_history["Séance"] == choix_s)]
                default = data_curr[["Série", "Reps", "Poids", "Remarque"]].copy() if not data_curr.empty else pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]})
                
                edited_df = st.data_editor(default, num_rows="dynamic", key=f"grid_{exo}", use_container_width=True, column_config={"Poids": st.column_config.NumberColumn("Poids", format="%g", step=0.1)})
                
                # Calcul Volume Actuel
                vol_curr = (edited_df["Poids"] * edited_df["Reps"]).sum()
                
                col_v, col_s = st.columns([1, 1])
                if col_v.button(f"✅ Valider {exo}"):
                    valid = edited_df[(edited_df["Poids"] > 0) | (edited_df["Reps"] > 0)].copy()
                    valid["Semaine"], valid["Séance"], valid["Exercice"] = sem, choix_s, exo
                    mask = (df_history["Semaine"] == sem) & (df_history["Séance"] == choix_s) & (df_history["Exercice"] == exo)
                    save_historique(pd.concat([df_history[~mask], valid], ignore_index=True))
                    
                    # SYSTEME DE PROGRESSION
                    diff = vol_curr - vol_h1
                    if sem > 1:
                        if diff > 0: st.toast(f"💪 Progression : +{int(diff)} kg de volume !", icon="🔥")
                        else: st.toast("Continue tes efforts !", icon="🏋️")
                    st.rerun()

                if col_s.button(f"🚫 Sauter", key=f"skip_{exo}"):
                    row = pd.DataFrame({"Semaine": [sem], "Séance": [choix_s], "Exercice": [exo], "Série": [1], "Reps": [0], "Poids": [0.0], "Remarque": ["SÉANCE MANQUÉE ❌"]})
                    mask = (df_history["Semaine"] == sem) & (df_history["Séance"] == choix_s) & (df_history["Exercice"] == exo)
                    save_historique(pd.concat([df_history[~mask], row], ignore_index=True)); st.rerun()

# --- ONGLET 3 : PROGRÈS (1RM & CHARTS) ---
with tab3:
    if df_history.empty: st.info("Aucune donnée.")
    else:
        st.subheader("📊 Résumé")
        # On calcule le 1RM pour chaque ligne
        df_history["1RM"] = df_history.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Volume total", f"{int((df_history['Poids'] * df_history['Reps']).sum())} kg")
        col2.metric("Max 1RM", f"{round(df_history['1RM'].max(), 1)} kg")
        col3.metric("Séances", len(df_history[df_history["Poids"] > 0].groupby(["Semaine", "Séance"])))
        
        st.divider()
        sel_exo = st.selectbox("Analyse Exercice :", sorted(df_history["Exercice"].unique()))
        df_e = df_history[df_history["Exercice"] == sel_exo]
        
        # Graphique 1RM
        st.caption("Progression du 1RM estimé (Force pure)")
        st.line_chart(df_e.groupby("Semaine")["1RM"].max())
        
        # Conseil de progression
        last_sem = df_e["Semaine"].max()
        last_perf = df_e[df_e["Semaine"] == last_sem]
        avg_reps = last_perf["Reps"].mean()
        
        if avg_reps >= 10: st.info(f"💡 Conseil : Tu fais beaucoup de reps ({int(avg_reps)}). Augmente de 1.25kg ou 2.5kg la semaine prochaine !")
        elif avg_reps > 0: st.info("💡 Conseil : Reste sur ce poids et essaye de gagner 1 rep par série.")
