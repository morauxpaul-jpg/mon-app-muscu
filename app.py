import streamlit as st
import pandas as pd
import json
import os
import gspread

# --- CONFIGURATION MOBILE ---
st.set_page_config(page_title="Musculation Tracker", layout="centered", page_icon="logo2.png")

# --- FIX POUR L'ICÔNE SUR MOBILE ---
# Remplace 'TON_PSEUDO' et 'TON_REPO' par tes vrais noms GitHub
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
    /* Configuration du fond de l'application */
    .stApp {
        /* On superpose un halo lumineux blanc (radial) sur un dégradé sombre (linéaire) */
        background: 
            radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
            linear-gradient(180deg, #0A1931 0%, #000000 100%);
        background-attachment: fixed;
        background-size: cover;
        color: #E0E0E0;
        font-family: 'Helvetica', sans-serif;
    }
    
    /* Transparence pour les onglets pour qu'ils se fondent dans le décor */
    .stTabs [data-baseweb="tab-list"] { 
        background-color: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(5px); /* Petit effet de flou derrière les onglets */
        border-radius: 12px;
        padding: 5px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* Style des onglets sélectionnés (blanc pour le contraste) */
    .stTabs [aria-selected="true"] { 
        background-color: rgba(255, 255, 255, 0.9) !important;
        color: #0A1931 !important; /* Texte bleu foncé sur fond blanc */
        border-radius: 8px;
        font-weight: bold;
    }
    
    /* Effet de transparence sur les menus déroulants (Expanders) */
    .stExpander {
        background-color: rgba(10, 25, 49, 0.6) !important; /* Bleu nuit très transparent */
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 10px;
        margin-bottom: 10px;
        backdrop-filter: blur(5px);
    }
    
    /* Titres des expanders en blanc */
    .streamlit-expanderHeader {
        color: #FFFFFF !important;
        font-weight: 600;
    }

    /* Style des métriques (chiffres clés) en blanc/bleu clair */
    div[data-testid="stMetricValue"] { 
        font-size: 28px !important; 
        color: #4A90E2 !important; /* Bleu clair lumineux pour les chiffres */
        font-weight: 800;
        text-shadow: 0 0 10px rgba(74, 144, 226, 0.5); /* Petit effet néon */
    }
    div[data-testid="stMetricLabel"] {
        color: #B0B0B0 !important;
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

# --- GESTION DU PROGRAMME (VIDE PAR DÉFAUT) ---
DEFAULT_PROG = {} # <-- C'est ici que l'appli démarre vide !

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
    return pd.DataFrame(data)

def save_historique(df):
    ws_history.clear()
    ws_history.update([df.columns.values.tolist()] + df.values.tolist())

# Chargement des données
programme = load_prog()
df_history = get_historique()

col_logo_1, col_logo_2, col_logo_3 = st.columns([1, 2, 1])
with col_logo_2:
    st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Mes Progrès"])

# ==============================================================================
# ONGLET 1 : MON PROGRAMME (CRÉATION ET TRI DES SÉANCES)
# ==============================================================================
with tab1:
    st.subheader("Mes Séances")
    
    jours = list(programme.keys())
    
    if not jours:
        st.info("Ton programme est vide. Crée ta première séance ci-dessous !")

    # Affichage et gestion des séances
    for idx_jour, jour in enumerate(jours):
        exos = programme[jour]
        with st.expander(f"⚙️ {jour}", expanded=False):
            
            # --- OUTILS POUR DÉPLACER/SUPPRIMER LA SÉANCE ---
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
            
            # --- GESTION DES EXERCICES ---
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

    st.markdown("---")
    
    # --- CRÉATION D'UNE NOUVELLE SÉANCE ---
    st.subheader("➕ Créer une séance")
    c_new_s, c_btn_s = st.columns([3, 1])
    nv_seance = c_new_s.text_input("Nom de la séance", label_visibility="collapsed", placeholder="Ex: Push, Fullbody...")
    if c_btn_s.button("Créer") and nv_seance and nv_seance not in programme:
        programme[nv_seance] = []
        save_prog(programme)
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
            st.success("Toutes les données ont été effacées.")
            st.rerun()

# ==============================================================================
# ONGLET 2 : ENTRAÎNEMENT
# ==============================================================================
with tab2:
    if not programme:
        st.warning("⚠️ Va d'abord dans l'onglet 'Programme' pour créer ta première séance !")
    else:
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
                    save_historique(new_df)
                    st.success("Sauvegardé sur Google Sheets ! ☁️")
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











