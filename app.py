import streamlit as st
import pandas as pd
import json
import time
import gspread

# --- 1. CONFIGURATION PAGE ---
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

# --- 2. DESIGN ---
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

# --- FONCTIONS UTILES ---
def calc_1rm(weight, reps):
    if reps <= 0: return 0
    if reps == 1: return weight
    return weight * (36 / (37 - reps))

# --- 3. CONNEXION GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheets():
    credentials_dict = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(credentials_dict)
    sh = gc.open("Muscu_App")
    return sh.get_worksheet(0), sh.worksheet("Programme")

ws_history, ws_prog = get_google_sheets()

# --- 4. GESTION DU PROGRAMME ---
def load_prog():
    val = ws_prog.acell('A1').value
    return json.loads(val) if val else {}

def save_prog(prog_data):
    ws_prog.update_acell('A1', json.dumps(prog_data))

# --- 5. GESTION DE L'HISTORIQUE ---
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

# Chargement données
programme = load_prog()
df_history = get_historique()

# --- SIDEBAR (PARAMÈTRES) ---
with st.sidebar:
    st.header("⏲️ Chrono")
    activer_chrono = st.checkbox("Activer le repos auto", value=True)
    rest_time = st.slider("Secondes de repos", 30, 300, 90, 15)

# Logo
col_logo_1, col_logo_2, col_logo_3 = st.columns([1, 2, 1])
with col_logo_2: st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Mes Progrès"])

# --- ONGLET 1 : PROGRAMME ---
with tab1:
    st.subheader("Mes Séances")
    jours = list(programme.keys())
    for idx_jour, jour in enumerate(jours):
        with st.expander(f"⚙️ {jour}"):
            c_up, c_del = st.columns([1, 1])
            if c_up.button("⬆️ Monter", key=f"up_s_{jour}") and idx_jour > 0:
                jours[idx_jour], jours[idx_jour-1] = jours[idx_jour-1], jours[idx_jour]
                save_prog({k: programme[k] for k in jours}); st.rerun()
            if c_del.button("🗑️ Supprimer", key=f"del_s_{jour}"):
                del programme[jour]; save_prog(programme); st.rerun()
            for i, exo in enumerate(programme[jour]):
                c1, c2 = st.columns([8, 2])
                c1.write(f"**{exo}**")
                if c2.button("🗑️", key=f"de_{jour}_{i}"):
                    programme[jour].pop(i); save_prog(programme); st.rerun()
            nv = st.text_input("Ajouter exo :", key=f"in_{jour}")
            if st.button("Ajouter", key=f"btn_{jour}") and nv:
                programme[jour].append(nv); save_prog(programme); st.rerun()
    nvs = st.text_input("Nom séance")
    if st.button("Créer séance") and nvs:
        programme[nvs] = []; save_prog(programme); st.rerun()

# --- ONGLET 2 : ENTRAÎNEMENT ---
with tab2:
    if not programme: st.warning("⚠️ Crée une séance !")
    else:
        choix_seance = st.selectbox("Séance :", list(programme.keys()), label_visibility="collapsed")
        sem_actuelle = st.number_input("Semaine N°", min_value=1, value=1)
        
        for exo in programme[choix_seance]:
            with st.expander(f"🔹 {exo}", expanded=True):
                # 1. Historique S-1 (Filtre précis par séance)
                h1 = df_history[(df_history["Exercice"] == exo) & 
                                (df_history["Semaine"] == sem_actuelle - 1) & 
                                (df_history["Séance"] == choix_seance)]
                
                vol_h1 = (h1["Poids"] * h1["Reps"]).sum()
                if not h1.empty:
                    st.caption(f"🔍 S-1 : {int(vol_h1)} kg total")
                    st.dataframe(h1[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                
                # 2. Préparation des lignes de saisie (Logique du fix)
                data_sem = df_history[(df_history["Exercice"] == exo) & 
                                      (df_history["Semaine"] == sem_actuelle) & 
                                      (df_history["Séance"] == choix_seance)]
                
                if not data_sem.empty:
                    # On affiche les séries déjà faites + une ligne vide pour la suivante
                    existing = data_sem[["Série", "Reps", "Poids", "Remarque"]].copy()
                    next_num = int(existing["Série"].max() + 1)
                    new_line = pd.DataFrame({"Série": [next_num], "Reps": [0], "Poids": [0.0], "Remarque": [""]})
                    default_sets = pd.concat([existing, new_line], ignore_index=True)
                else:
                    # Si rien n'est fait, on propose 3 séries par défaut
                    default_sets = pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]})
                
                # Éditeur de tableau
                st.caption("✍️ Saisie des séries (clique sur Valider après chaque série pour le chrono)")
                edited_df = st.data_editor(default_sets, num_rows="dynamic", key=f"grid_{exo}", use_container_width=True, 
                                           column_config={"Poids": st.column_config.NumberColumn("Poids", format="%g", step=0.1)})
                
                c_val, c_skip = st.columns(2)
                if c_val.button(f"✅ Valider {exo}"):
                    # On ne garde que les lignes avec des données réelles
                    valid = edited_df[(edited_df["Poids"] > 0) | (edited_df["Reps"] > 0)].copy()
                    valid["Semaine"], valid["Séance"], valid["Exercice"] = sem_actuelle, choix_seance, exo
                    
                    # Remplacement dans l'historique global
                    mask = (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance) & (df_history["Exercice"] == exo)
                    new_df = pd.concat([df_history[~mask], valid], ignore_index=True)
                    save_historique(new_df)
                    
                    # Gestion Chrono
                    if activer_chrono:
                        st.success(f"Sauvegardé ! Repos : {rest_time}s")
                        t_placeholder = st.empty()
                        for t in range(rest_time, 0, -1):
                            t_placeholder.metric("⏳ Temps restant", f"{t}s")
                            time.sleep(1)
                        t_placeholder.success("💥 Allez, série suivante !")
                    
                    st.rerun()
                
                if c_skip.button(f"🚫 Pas de séance aujourd'hui", key=f"skip_{exo}"):
                    skip_row = pd.DataFrame({"Semaine": [sem_actuelle], "Séance": [choix_seance], "Exercice": [exo], "Série": [1], "Reps": [0], "Poids": [0.0], "Remarque": ["SÉANCE MANQUÉE ❌"]})
                    mask = (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance) & (df_history["Exercice"] == exo)
                    save_historique(pd.concat([df_history[~mask], skip_row], ignore_index=True)); st.rerun()

# --- ONGLET 3 : PROGRÈS ---
with tab3:
    if df_history.empty: st.info("Fais ton premier entraînement !")
    else:
        col1, col2, col3 = st.columns(3)
        df_real = df_history[df_history["Poids"] > 0]
        col1.metric("Volume total", f"{int((df_history['Poids'] * df_history['Reps']).sum())} kg")
        col2.metric("Nb Séances", len(df_real.groupby(["Semaine", "Séance"])))
        col3.metric("Semaine Max", f"S{df_history['Semaine'].max()}")
        
        st.divider()
        sel_exo = st.selectbox("Analyse Exercice :", sorted(df_history["Exercice"].unique()))
        df_exo = df_history[df_history["Exercice"] == sel_exo].copy()
        
        if not df_exo.empty:
            df_valide = df_exo[df_exo["Poids"] > 0]
            if not df_valide.empty:
                max_charge = df_valide["Poids"].max()
                df_valide["1RM"] = df_valide.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
                
                c_rec, c_1rm = st.columns(2)
                c_rec.success(f"🏆 Record : **{max_charge} kg**")
                c_1rm.info(f"💪 Force (1RM) : **{round(df_valide['1RM'].max(), 1)} kg**")
                
                st.caption("📈 Évolution des charges (Poids Max) :")
                st.line_chart(df_exo.groupby("Semaine")["Poids"].max())
            
            with st.expander("Historique complet"):
                st.dataframe(df_exo[["Semaine", "Séance", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Semaine", "Série"], ascending=[False, True]), hide_index=True, use_container_width=True)
