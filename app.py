import streamlit as st
import pandas as pd
import json
import os

# --- CONFIGURATION MOBILE ---
st.set_page_config(page_title="App Muscu", layout="centered", page_icon="💪")

# --- DESIGN MODERNE & MOBILE ---
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

# --- GESTION DES FICHIERS ---
PROG_FILE = "programme.json"
DATA_FILE = "historique.csv"

# Programme par défaut
DEFAULT_PROG = {
    "Lundi (Push 1)": ["Dips", "Développé incliné haltères", "Écartés poulie", "Elévation latérale", "Extension poulie"],
    "Mardi (Pull 1)": ["Traction", "Tirage Vertical", "Rowing machine", "Curl marteau"],
    "Jeudi (Push 2)": ["Développé couché", "Développé militaire", "Dips", "Extension corde"],
    "Vendredi (Pull 2)": ["Traction", "Tirage neutre", "Rowing", "Reverse fly", "Curl incliné"],
    "Samedi (Legs)": ["Presse à cuisse", "Leg curl", "Mollets", "Crunch"]
}

def load_data():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
        df.to_csv(DATA_FILE, index=False)
        return df
    return pd.read_csv(DATA_FILE)

def load_prog():
    if not os.path.exists(PROG_FILE):
        with open(PROG_FILE, "w", encoding='utf-8') as f:
            json.dump(DEFAULT_PROG, f)
        return DEFAULT_PROG
    with open(PROG_FILE, "r", encoding='utf-8') as f:
        return json.load(f)

programme = load_prog()
df_history = load_data()

st.title("💪 Suivi Training")

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Mes Progrès"])

# ==============================================================================
# ONGLET 1 : MON PROGRAMME & GESTION DES CYCLES
# ==============================================================================
with tab1:
    st.subheader("Mes Séances")
    
    # Gestion des exercices
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
    
    # --- GESTION DES DONNÉES (NOUVEAU CYCLE ET RESET) ---
    with st.expander("🛠️ Gestion des Cycles et Données"):
        st.write("Gère ton historique pour ne pas surcharger l'application au bout de plusieurs mois.")
        
        # FEATURE 1 : NOUVEAU CYCLE (Garde la dernière semaine)
        if not df_history.empty:
            max_semaine = df_history["Semaine"].max()
            st.info(f"Tu es actuellement à la **Semaine {max_semaine}**.")
            if st.button("🔄 Lancer un Nouveau Cycle (Garder S" + str(max_semaine) + " en S1)"):
                # On ne garde que les données de la dernière semaine
                df_new_cycle = df_history[df_history["Semaine"] == max_semaine].copy()
                # On renomme cette semaine en "Semaine 1"
                df_new_cycle["Semaine"] = 1
                # On sauvegarde
                df_new_cycle.to_csv(DATA_FILE, index=False)
                st.success("Nouveau cycle lancé ! Ta dernière semaine est maintenant la Semaine 1.")
                st.rerun()
                
        # FEATURE 2 : RESET TOTAL
        st.divider()
        st.warning("Action irréversible :")
        if st.button("🗑️ Effacer TOUTES les données (Remise à zéro)"):
            if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
            st.success("Toutes les données ont été effacées.")
            st.rerun()

# ==============================================================================
# ONGLET 2 : ENTRAÎNEMENT
# ==============================================================================
with tab2:
    c1, c2 = st.columns([2, 1])
    choix_seance = c1.selectbox("Séance du jour :", list(programme.keys()), label_visibility="collapsed")
    sem_actuelle = c2.number_input("Semaine N°", min_value=1, max_value=20, value=1, label_visibility="collapsed")
    
    st.markdown("---")
    
    for exo in programme[choix_seance]:
        with st.expander(f"🔹 {exo}", expanded=True):
            
            # Historique Semaine - 1
            hist_exo = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle - 1)]
            if not hist_exo.empty:
                st.caption(f"🎯 Semaine {sem_actuelle - 1} :")
                st.dataframe(hist_exo[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
            
            # Saisie
            st.caption("Aujourd'hui :")
            default_sets = pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]})
            edited_df = st.data_editor(default_sets, num_rows="dynamic", key=f"grid_{exo}", use_container_width=True)
            
            if st.button(f"✅ Valider {exo}"):
                valid_sets = edited_df[(edited_df["Poids"] > 0) | (edited_df["Reps"] > 0)].copy()
                valid_sets["Semaine"] = sem_actuelle
                valid_sets["Séance"] = choix_seance
                valid_sets["Exercice"] = exo
                
                mask = (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance) & (df_history["Exercice"] == exo)
                df_history = df_history[~mask]
                df_history = pd.concat([df_history, valid_sets], ignore_index=True)
                df_history.to_csv(DATA_FILE, index=False)
                st.success("Sauvegardé !")
                st.rerun()

# ==============================================================================
# ONGLET 3 : MES PROGRÈS (DASHBOARD)
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