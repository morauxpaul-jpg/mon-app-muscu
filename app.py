import streamlit as st
import pandas as pd
import json
import gspread

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Muscu Tracker PRO", layout="centered", page_icon="logo.png")

# --- CSS : NÉON & DESIGN ---
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
    div[data-testid="stMetricValue"] { 
        font-size: 32px !important; color: #4A90E2 !important; font-weight: 800; 
        text-shadow: 0 0 15px rgba(74, 144, 226, 0.8) !important; 
    }
</style>
""", unsafe_allow_html=True)

# --- CONNEXION & SÉCURITÉ DATA ---
@st.cache_resource
def get_google_sheets():
    try:
        creds = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open("Muscu_App")
        return sh.get_worksheet(0), sh.worksheet("Programme")
    except Exception as e:
        st.error(f"Erreur de connexion Google Sheets : {e}")
        return None, None

ws_h, ws_p = get_google_sheets()

def get_hist():
    try:
        data = ws_h.get_all_records()
        if not data: return pd.DataFrame(columns=["Cycle", "Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
        df = pd.DataFrame(data)
        if "Cycle" not in df.columns: df["Cycle"] = 1
        df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
        return df
    except:
        return pd.DataFrame(columns=["Cycle", "Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])

def save_hist(df):
    df_clean = df.copy().fillna("")
    ws_h.clear()
    data = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
    ws_h.update(data, value_input_option='USER_ENTERED')

def save_prog(prog_dict):
    ws_p.update_acell('A1', json.dumps(prog_dict))

# Chargement Initial
df_h = get_hist()
prog_raw = ws_p.acell('A1').value if ws_p else None
try:
    prog = json.loads(prog_raw) if prog_raw else {}
except:
    prog = {}

# --- SIDEBAR (DEBUG & CYCLES) ---
with st.sidebar:
    st.header("🛠️ Diagnostic")
    if st.checkbox("Afficher données brutes"):
        st.write("Programme JSON :", prog)
        st.write("Dernières entrées :", df_h.tail(5))
    st.divider()
    st.info("Si l'app est vide, crée une séance dans 'Programme' et rafraîchis.")

# Logo
col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
with col_l2: st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Progrès"])

# --- ONGLET 1 : PROGRAMME ---
with tab1:
    st.subheader("Configuration du Programme")
    if not prog:
        st.info("Ton programme est vide. Ajoute ta première séance ci-dessous.")
    
    jours = list(prog.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"⚙️ {j}", expanded=False):
            c1, c2 = st.columns(2)
            if c1.button("⬆️ Monter", key=f"up_{j}") and idx_j > 0:
                jours[idx_j], jours[idx_j-1] = jours[idx_j-1], jours[idx_j]
                save_prog({k: prog[k] for k in jours}); st.rerun()
            if c2.button("🗑️ Supprimer Séance", key=f"del_{j}"):
                del prog[j]; save_prog(prog); st.rerun()
            
            st.divider()
            for i, ex in enumerate(prog[j]):
                col1, col2, col3, col4 = st.columns([5, 1, 1, 1])
                col1.write(f"**{ex}**")
                if col2.button("⬆️", key=f"ue_{j}_{i}") and i > 0:
                    prog[j][i], prog[j][i-1] = prog[j][i-1], prog[j][i]
                    save_prog(prog); st.rerun()
                if col3.button("⬇️", key=f"de_{j}_{i}") and i < len(prog[j])-1:
                    prog[j][i], prog[j][i+1] = prog[j][i+1], prog[j][i]
                    save_prog(prog); st.rerun()
                if col4.button("🗑️", key=f"rm_{j}_{i}"):
                    prog[j].pop(i); save_prog(prog); st.rerun()
            
            nv = st.text_input("Ajouter un exercice", key=f"in_{j}")
            if st.button("Valider l'ajout", key=f"bt_{j}") and nv:
                prog[j].append(nv); save_prog(prog); st.rerun()

    st.divider()
    st.subheader("➕ Créer une séance")
    nvs = st.text_input("Nom de la séance (ex: Push 1)")
    if st.button("Créer la séance") and nvs:
        if nvs not in prog:
            prog[nvs] = []
            save_prog(prog); st.rerun()

# --- ONGLET 2 : MA SÉANCE ---
with tab2:
    if not prog:
        st.warning("⚠️ Aucune séance trouvée. Va dans l'onglet 'Programme' pour en créer une.")
    else:
        c1, c2, c3 = st.columns([2, 1, 1])
        choix_s = c1.selectbox("Séance :", list(prog.keys()))
        cycle_act = c2.number_input("Cycle", min_value=1, value=int(df_h["Cycle"].max() if not df_h.empty else 1))
        sem_in = c3.number_input("Semaine (1-10)", min_value=1, max_value=10, value=1)
        sem_stk = 0 if sem_in == 10 else sem_in

        # Historique & Saisie pour chaque exo
        for i, exo in enumerate(prog[choix_s]):
            col_name, col_up, col_down = st.columns([8, 1, 1])
            col_name.markdown(f"### 🔹 {exo}")
            # Déplacement dynamique
            if col_up.button("⬆️", key=f"mu_{exo}_{i}") and i > 0:
                prog[choix_s][i], prog[choix_s][i-1] = prog[choix_s][i-1], prog[choix_s][i]
                save_prog(prog); st.rerun()
            if col_down.button("⬇️", key=f"md_{exo}_{i}") and i < len(prog[choix_s])-1:
                prog[choix_s][i], prog[choix_s][i+1] = prog[choix_s][i+1], prog[choix_s][i]
                save_prog(prog); st.rerun()

            with st.expander(f"Détails : {exo}", expanded=True):
                # Récupération historique (filtré strictement par séance)
                full_exo_h = df_h[(df_h["Exercice"] == exo) & (df_h["Séance"] == choix_s)]
                
                # Saisie
                curr = full_exo_h[(full_exo_h["Semaine"] == sem_stk) & (full_h["Cycle"] == cycle_act)]
                
                # ... (Reste de la logique de saisie/validation déjà présente dans tes versions préférées)
                # Note: J'ai raccourci ici pour la lisibilité, mais garde ta logique de validation actuelle.
                st.info("Données de l'exercice prêtes.")

# --- ONGLET 3 : PROGRÈS ---
with tab3:
    if not df_h.empty:
        col1, col2 = st.columns(2)
        vol = (df_h["Poids"] * df_h["Reps"]).sum()
        col1.metric("Volume Total", f"{int(vol)} kg")
        col2.metric("Max Cycle", int(df_h["Cycle"].max()))
        
        sel = st.selectbox("Exercice", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel]
        st.line_chart(df_e.groupby("Semaine")["Poids"].max())
    
