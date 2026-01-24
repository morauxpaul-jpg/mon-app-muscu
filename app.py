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
    # FORCE LE POIDS EN DÉCIMAL (FLOAT) AU CHARGEMENT
    if "Poids" in df.columns:
        df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0)
    return df

def save_historique(df):
    ws_history.clear()
    # On s'assure que les colonnes sont dans le bon ordre avant de sauvegarder
    cols = ["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"]
    df = df[cols]
    ws_history.update([df.columns.values.tolist()] + df.values.tolist())

# Chargement initial
programme = load_prog()
df_history = get_historique()

col_logo_1, col_logo_2, col_logo_3 = st.columns([1, 2, 1])
with col_logo_2:
    st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Mes Progrès"])

# --- ONGLET 1 : PROGRAMME ---
with tab1:
    st.subheader("Mes Séances")
    jours = list(programme.keys())
    if not jours: st.info("Ton programme est vide. Crée ta première séance ci-dessous !")

    for idx_jour, jour in enumerate(jours):
        exos = programme[jour]
        with st.expander(f"⚙️ {jour}", expanded=False):
            c_up, c_down, c_del = st.columns([1, 1, 1])
            if c_up.button("⬆️ Monter", key=f"up_s_{jour}") and idx_jour > 0:
                jours[idx_jour], jours[idx_jour-1] = jours[idx_jour-1], jours[idx_jour]
                save_prog({k: programme[k] for k in jours})
                st.rerun()
            if c_down.button("⬇️ Descendre", key=f"down_s_{jour}") and idx_jour < len(jours)-1:
                jours[idx_jour], jours[idx_jour+1] = jours[idx_jour+1], jours[idx_jour]
                save_prog({k: programme[k] for k in jours})
                st.rerun()
            if c_del.button("🗑️ Supprimer", key=f"del_s_{jour}"):
                del programme[jour]
                save_prog(programme)
                st.rerun()
            
            st.markdown("---")
            for i, exo in enumerate(exos):
                c1, c2, c3, c4 = st.columns([6, 1, 1, 1])
                c1.write(f"**{exo}**")
                if c2.button("⬆️", key=f"up_e_{jour}_{i}") and i > 0:
                    exos[i], exos[i-1] = exos[i-1], exos[i]
                    save_prog(programme)
                    st.rerun()
                if c3.button("⬇️", key=f"down_e_{jour}_{i}") and i < len(exos)-1:
                    exos[i], exos[i+1] = exos[i+1], exos[i]
                    save_prog(programme)
                    st.rerun()
                if c4.button("🗑️", key=f"del_e_{jour}_{i}"):
                    exos.pop(i)
                    save_prog(programme)
                    st.rerun()
            nv_exo = st.text_input("Ajouter un exo :", key=f"add_e_{jour}", label_visibility="collapsed", placeholder="+ Nouvel exercice")
            if st.button("Ajouter l'exo", key=f"btn_add_e_{jour}") and nv_exo:
                exos.append(nv_exo)
                save_prog(programme)
                st.rerun()

    st.subheader("➕ Créer une séance")
    c_new_s, c_btn_s = st.columns([3, 1])
    nv_seance = c_new_s.text_input("Nom de la séance", label_visibility="collapsed", placeholder="Ex: Push...")
    if c_btn_s.button("Créer") and nv_seance and nv_seance not in programme:
        programme[nv_seance] = []
        save_prog(programme)
        st.rerun()

# --- ONGLET 2 : ENTRAÎNEMENT (FIX DÉCIMALES) ---
with tab2:
    if not programme: st.warning("⚠️ Crée d'abord une séance !")
    else:
        c1, c2 = st.columns([2, 1])
        choix_seance = c1.selectbox("Séance :", list(programme.keys()), label_visibility="collapsed")
        sem_actuelle = c2.number_input("Semaine N°", min_value=1, value=1, label_visibility="collapsed")
        
        for exo in programme[choix_seance]:
            with st.expander(f"🔹 {exo}", expanded=True):
                # Affichage historique
                h1 = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle - 1)]
                if not h1.empty:
                    st.caption("Semaine précédente :")
                    st.dataframe(h1[["Série", "Reps", "Poids"]], hide_index=True, use_container_width=True)
                
                # Données actuelles
                data_sem = df_history[(df_history["Exercice"] == exo) & (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance)]
                if not data_sem.empty:
                    default_sets = data_sem[["Série", "Reps", "Poids", "Remarque"]].copy()
                else:
                    default_sets = pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]})
                
                # CONFIGURATION POUR LES DÉCIMALES ET L'AFFICHAGE PROPRE
                edited_df = st.data_editor(
                    default_sets, 
                    num_rows="dynamic", 
                    key=f"grid_{exo}", 
                    use_container_width=True,
                    column_config={
                        "Poids": st.column_config.NumberColumn(
                            "Poids (kg)",
                            min_value=0.0,
                            step=0.05,
                            format="%g" # Affiche 10 si rond, 10.5 si besoin
                        )
                    }
                )
                
                if st.button(f"✅ Valider {exo}"):
                    valid = edited_df[(edited_df["Poids"] > 0) | (edited_df["Reps"] > 0)].copy()
                    # On s'assure que la colonne Poids est bien au format décimal avant concat
                    valid["Poids"] = valid["Poids"].astype(float)
                    valid["Semaine"], valid["Séance"], valid["Exercice"] = sem_actuelle, choix_seance, exo
                    
                    mask = (df_history["Semaine"] == sem_actuelle) & (df_history["Séance"] == choix_seance) & (df_history["Exercice"] == exo)
                    new_df = pd.concat([df_history[~mask], valid], ignore_index=True)
                    save_historique(new_df)
                    st.success("Sauvegardé ! ☁️")
                    st.rerun()

# --- ONGLET 3 : PROGRÈS ---
with tab3:
    if not df_history.empty:
        selected_exo = st.selectbox("Exercice :", sorted(list(df_history["Exercice"].unique())))
        df_exo = df_history[df_history["Exercice"] == selected_exo]
        if not df_exo.empty:
            st.line_chart(df_exo.groupby("Semaine")["Poids"].max())
            st.dataframe(df_exo[["Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Semaine", "Série"], ascending=[False, True]), use_container_width=True, hide_index=True)
