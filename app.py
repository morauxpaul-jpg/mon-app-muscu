import streamlit as st
import pandas as pd
import json
import gspread

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Muscu Tracker - RECOVERY", layout="centered", page_icon="logo.png")

# --- CSS : NÉON & DESIGN ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                    linear-gradient(180deg, #0A1931 0%, #000000 100%);
        background-attachment: fixed; background-size: cover;
        color: #E0E0E0; font-family: 'Helvetica', sans-serif;
    }
    div[data-testid="stMetricValue"] { 
        font-size: 32px !important; color: #4A90E2 !important; font-weight: 800; 
        text-shadow: 0 0 15px rgba(74, 144, 226, 0.8) !important; 
    }
    .stExpander { background-color: rgba(10, 25, 49, 0.6) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 10px; backdrop-filter: blur(5px); }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNEXION SANS CACHE (POUR FORCER LE LIEN) ---
def connect_to_sheet():
    try:
        creds = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(creds)
        # Remplace bien "Muscu_App" par le nom exact de ton fichier Google Sheets
        sh = gc.open("Muscu_App") 
        # Vérifie que les noms "Feuille 1" (ou 0) et "Programme" sont bons
        return sh.get_worksheet(0), sh.worksheet("Programme")
    except Exception as e:
        st.error(f"❌ Erreur de connexion : {e}")
        return None, None

ws_h, ws_p = connect_to_sheet()

if ws_h and ws_p:
    st.success("✅ Lien établi avec le Google Sheet")
else:
    st.warning("⚠️ Impossible de se connecter. Vérifie tes 'Secrets' sur Streamlit et le nom du fichier.")

# --- FONCTIONS DE SAUVEGARDE ---
def save_hist(df):
    try:
        df_clean = df.copy().fillna("")
        ws_h.clear()
        data = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        ws_h.update(data, value_input_option='USER_ENTERED')
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde : {e}")

# --- CHARGEMENT DES SÉANCES ---
prog = {}
if ws_p:
    try:
        val_a1 = ws_p.acell('A1').value
        if val_a1:
            prog = json.loads(val_a1)
        else:
            st.info("ℹ️ La cellule A1 est vide. Crée ta première séance ci-dessous.")
    except Exception as e:
        st.error(f"🔴 Erreur de lecture du programme (JSON) : {e}")

# --- CHARGEMENT HISTORIQUE ---
def get_hist():
    try:
        data = ws_h.get_all_records()
        if not data: return pd.DataFrame(columns=["Cycle", "Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
        df = pd.DataFrame(data)
        df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
        return df
    except:
        return pd.DataFrame(columns=["Cycle", "Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])

df_h = get_hist()

# Logo
col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
with col_l2: st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Progrès"])

# --- ONGLET 1 : PROGRAMME ---
with tab1:
    st.subheader("Configuration")
    if prog:
        for idx_j, (j, exos) in enumerate(prog.items()):
            with st.expander(f"⚙️ {j}"):
                for i, ex in enumerate(exos):
                    col1, col2 = st.columns([8, 2])
                    col1.write(f"**{ex}**")
                    if col2.button("🗑️", key=f"del_{j}_{i}"):
                        prog[j].pop(i)
                        ws_p.update_acell('A1', json.dumps(prog)); st.rerun()
                
                nv = st.text_input("Nouvel exo", key=f"add_{j}")
                if st.button("Ajouter", key=f"btn_{j}") and nv:
                    prog[j].append(nv)
                    ws_p.update_acell('A1', json.dumps(prog)); st.rerun()
                
                if st.button("🗑️ Supprimer la séance entière", key=f"del_s_{j}"):
                    del prog[j]
                    ws_p.update_acell('A1', json.dumps(prog)); st.rerun()
    
    st.divider()
    nvs = st.text_input("➕ Nom de la nouvelle séance")
    if st.button("Créer la séance") and nvs:
        prog[nvs] = []
        ws_p.update_acell('A1', json.dumps(prog))
        st.rerun()

# --- ONGLET 2 : MA SÉANCE ---
with tab2:
    if not prog:
        st.warning("Programme vide. Crée une séance dans l'onglet 'Programme'.")
    else:
        c1, c2, c3 = st.columns([2, 1, 1])
        choix_s = c1.selectbox("Séance :", list(prog.keys()))
        cycle_act = c2.number_input("Cycle", min_value=1, value=1)
        sem_in = c3.number_input("Sem", min_value=1, max_value=10, value=1)
        
        for exo in prog[choix_s]:
            with st.expander(f"🔹 {exo}", expanded=True):
                # On affiche juste les perfs actuelles pour vérifier si la sauvegarde marche
                curr = df_h[(df_h["Exercice"] == exo) & (df_h["Semaine"] == (0 if sem_in==10 else sem_in)) & (df_h["Séance"] == choix_s)]
                
                if not curr.empty:
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]], hide_index=True)
                
                # Formulaire de saisie simplifié pour tester
                df_ed = pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]})
                ed = st.data_editor(df_ed, key=f"e_{exo}", use_container_width=True)
                
                if st.button(f"Enregistrer {exo}", key=f"v_{exo}"):
                    v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                    v["Cycle"], v["Semaine"], v["Séance"], v["Exercice"] = cycle_act, (0 if sem_in==10 else sem_in), choix_s, exo
                    save_hist(pd.concat([df_h, v], ignore_index=True))
                    st.success("Sauvegardé !")
                    st.rerun()

# --- ONGLET 3 : PROGRÈS ---
with tab3:
    if not df_h.empty:
        st.metric("Volume Total", f"{int((df_h['Poids'] * df_h['Reps']).sum())} kg")
        st.dataframe(df_h.tail(10))
