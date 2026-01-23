import streamlit as st
import pandas as pd
import json
import os
import gspread

# --- CONFIGURATION MOBILE ---
st.set_page_config(page_title="App Muscu", layout="centered", page_icon="💪")

# --- DESIGN MODERNE ---
st.markdown("""
<style>
    .stApp { background-color: #0E0E0E; color: #E0E0E0; font-family: 'Helvetica', sans-serif; }
    h1, h2, h3 { color: #ffffff !important; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] { background-color: #1A1A1A; border-radius: 12px; padding: 5px; }
    .stTabs [data-baseweb="tab"] { color: #888; font-size: 16px; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #2D63ED !important; color: white !important; border-radius: 8px;}
    div[data-testid="stMetricValue"] { font-size: 28px !important; color: #2D63ED !important; font-weight: 800; }
</style>
""", unsafe_allow_html=True)

# --- CONNEXION GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    # Récupération de la clé secrète stockée dans Streamlit
    credentials_dict = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(credentials_dict)
    # Ouverture du fichier "Muscu_App"
    return gc.open("Muscu_App").sheet1

worksheet = get_google_sheet()

# --- GESTION DES DONNÉES ---
PROG_FILE = "programme.json"

DEFAULT_PROG = {
    "Lundi (Push 1)": ["Dips", "Développé incliné haltères", "Écartés poulie", "Elévation latérale", "Extension poulie"],
    "Mardi (Pull 1)": ["Traction", "Tirage Vertical", "Rowing machine", "Curl marteau"],
    "Jeudi (Push 2)": ["Développé couché", "Développé militaire", "Dips", "Extension corde"],
    "Vendredi (Pull 2)": ["Traction", "Tirage neutre", "Rowing", "Reverse fly", "Curl incliné"],
    "Samedi (Legs)": ["Presse à cuisse", "Leg curl", "Mollets", "Crunch"]
}

def load_prog():
    if not os.path.exists(PROG_FILE):
        with open(PROG_FILE, "w", encoding='utf-8') as f: json.dump(DEFAULT_PROG, f)
        return DEFAULT_PROG
    with open(PROG_FILE, "r", encoding='utf-8') as f: return json.load(f)

def get_historique():
    data = worksheet.get_all_records()
    if not data:
        return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
    return pd.DataFrame(data)

def save_historique(df):
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

programme = load_prog()
df_history = get_historique()

st.title("💪 Suivi Training")

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Mes Progrès"])

# ==============================================================================
# ONGLET 1 : MON PROGRAMME & GESTION DES CYCLES
# ==============================================================================
with tab1:
    st.subheader("Mes Séances")
    for jour, exos in programme.items():
        with st.expander(f"⚙️ {jour}", expanded=False):
            for i, exo in enumerate(exos):
                c1, c2, c3, c4 = st.columns([6, 1, 1, 1])
                c1.write(f"**{exo}**")
                if c2.button("⬆️", key=f"up_{jour}_{i}") and i > 0:
                    exos[i], exos[i-1] = exos[i-1], exos[i]
                    with open(PROG_FILE, "w", encoding='utf-8') as f: json.dump(programme, f)
                    st.rerun()
                if c3.button("⬇️", key=f"down_{jour}_{i}") and i < len(exos)-1:
                    exos[i], exos[i+1] = exos[i+1], exos[i]
                    with open(PROG_FILE, "w", encoding='utf-8') as f: json.dump(programme, f)
                    st.rerun()
                if c4.button("🗑️", key=f"del_{jour}_{i}"):
                    exos.pop(i)
                    with open(PROG_FILE, "w", encoding='utf-8') as f: json.dump(programme, f)
                    st.rerun()
            nv_exo = st.text_input("Ajouter un exo :", key=f"add_{jour}", label_visibility="collapsed", placeholder="+ Nouvel exercice")
            if st.button("Ajouter", key=f"btn_add_{jour}") and nv_exo:
                exos.append(nv_exo)
                with open(PROG_FILE, "w", encoding='utf-8') as f: json.dump(programme, f)
                st.rerun()

    st.markdown("---")
    with st.expander("🛠️ Gestion des Cycles et Données"):
        if not df_history.empty:
            max_semaine = df_history["Semaine"].max()
            st.info(f"Semaine actuelle : {max_semaine}")
            if st.button("🔄 Lancer un Nouveau Cycle (Garder S" + str(max_semaine) + " en S1)"):
                df_new_cycle = df_history[df_history["Semaine"] == max_semaine].copy()
                df_new_cycle["Semaine"] = 1
                save_historique(df_new_cycle)
                st.success("Nouveau cycle lancé !")
                st.rerun()
        if st.button("🗑️ Effacer TOUTES les données"):
            empty_df = pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
            save_historique(empty_df)
            st.success("Toutes les données ont été effacées de Google Sheets.")
            st.rerun()

# ==============================================================================
# ONGLET 2 : ENTRAÎNEMENT (SAUVEGARDE GOOGLE SHEETS)
# ==============================================================================
with tab2:
    c1, c2 = st.columns([2, 1])
    choix_seance = c1.selectbox("Séance du jour :", list(programme.keys()), label_visibility="collapsed")
    sem_actuelle = c2.number_input("Semaine N°", min_value=1, max_value=50, value=1, label_visibility="collapsed")
    st.markdown("---")
    for exo in programme[choix_seance]:
        with st.expander(f"🔹 {exo}", expanded=True):
            hist_s1 = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle - 1)]
            hist_s2 = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle - 2)]
            if not hist_s1.empty or not hist_s2.empty:
                st.caption("🔍 Historique récent :")
                if not hist_s2.empty:
                    st.markdown(f"**🗓️ Semaine {sem_actuelle - 2}**")
                    st.dataframe(hist_s2[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                if not hist_s1.empty:
                    st.markdown(f"**🗓️ Semaine {sem_actuelle - 1}**")
                    st.dataframe(hist_s1[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
            
            st.caption(f"✍️ Aujourd'hui (Semaine {sem_actuelle}) :")
            data_sem = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance)]
            if not data_sem.empty:
                default_sets = data_sem[["Série", "Reps", "Poids", "Remarque"]].copy()
            else:
                default_sets = pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]})
            
            edited_df = st.data_editor(default_sets, num_rows="dynamic", key=f"grid_{exo}", use_container_width=True)
            if st.button(f"✅ Valider {exo}"):
                valid_sets = edited_df[(edited_df["Poids"] > 0) | (edited_df["Reps"] > 0)].copy()
                valid_sets["Semaine"] = sem_actuelle
                valid_sets["Séance"] = choix_seance
                valid_sets["Exercice"] = exo
                mask = (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance) & (df_history["Exercice"] == exo)
                new_df = df_history[~mask]
                new_df = pd.concat([new_df, valid_sets], ignore_index=True)
                # SAUVEGARDE EN LIGNE
                save_historique(new_df)
                st.success("Sauvegardé sur ton Google Sheets ! ☁️")
                st.rerun()

# ==============================================================================
# ONGLET 3 : MES PROGRÈS
# ==============================================================================
with tab3:
    if df_history.empty:
        st.info("Fais ton premier entraînement pour voir tes statistiques ici !")
    else:
        st.subheader("📊 Résumé Global")
        col1, col2, col3 = st.columns(3)
        total_poids = (df_history["Poids"] * df_history["Reps"]).sum()
        max_semaine = df_history["Semaine"].max()
        col1.metric("Semaine Max", f"S{max_semaine}")
        col2.metric("Poids total", f"{int(total_poids)} kg")
        col3.metric("Nb Séances", df_history["Séance"].nunique() * max_semaine)
        st.markdown("---")
        st.subheader("🎯 Zoom par exercice")
        exo_list = sorted(list(df_history["Exercice"].unique()))
        selected_exo = st.selectbox("Choisis un exercice :", exo_list)
        df_exo = df_history[df_history["Exercice"] == selected_exo].copy()
        if not df_exo.empty:
            max_poids = df_exo["Poids"].max()
            meilleure_serie = df_exo[df_exo["Poids"] == max_poids].iloc[0]
            st.success(f"🏆 Record Actuel : **{int(meilleure_serie['Poids'])} kg x {meilleure_serie['Reps']}** (S{meilleure_serie['Semaine']})")
            st.caption("Progression de ton Poids Maximal par semaine :")
            progression = df_exo.groupby("Semaine")["Poids"].max()
            st.line_chart(progression)
            with st.expander("Voir tout l'historique"):
                df_clean = df_exo[["Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Semaine", "Série"], ascending=[False, True])
                st.dataframe(df_clean, use_container_width=True, hide_index=True)