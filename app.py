import streamlit as st
import pandas as pd
import json
import gspread

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Musculation Tracker", layout="centered", page_icon="logo2.png")

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

# LOGIQUE DE COULEUR INTERACTIVE (TES RÈGLES)
def style_comparaison(row, hist_s1):
    prev_set = hist_s1[hist_s1["Série"] == row["Série"]]
    colors = ["", "", "", ""] # Série, Reps, Poids, Remarque
    
    if not prev_set.empty:
        pw = float(prev_set.iloc[0]["Poids"])
        pr = int(prev_set.iloc[0]["Reps"])
        cw = float(row["Poids"])
        cr = int(row["Reps"])
        
        # RÈGLE 1 : Plus lourd mais moins de reps -> Les deux verts
        if cw > pw and cr < pr:
            colors[1] = "background-color: #2e7d32; color: white;" 
            colors[2] = "background-color: #2e7d32; color: white;"
        # RÈGLE 2 : Même poids mais plus de reps -> Poids base, Reps vert
        elif cw == pw and cr > pr:
            colors[1] = "background-color: #2e7d32; color: white;"
        # RÈGLE 3 : Classique (Plus = Vert, Moins = Rouge)
        else:
            if cw > pw: colors[2] = "background-color: #2e7d32; color: white;"
            elif cw < pw and cw > 0: colors[2] = "background-color: #c62828; color: white;"
            
            if cr > pr: colors[1] = "background-color: #2e7d32; color: white;"
            elif cr < pr and cr > 0: colors[1] = "background-color: #c62828; color: white;"
            
    return colors

# --- CONNEXION & GESTION DONNÉES ---
@st.cache_resource
def get_google_sheets():
    creds = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(creds)
    sh = gc.open("Muscu_App")
    return sh.get_worksheet(0), sh.worksheet("Programme")

ws_h, ws_p = get_google_sheets()

def load_prog():
    v = ws_p.acell('A1').value
    return json.loads(v) if v else {}

def save_prog(d): ws_p.update_acell('A1', json.dumps(d))

def get_hist():
    data = ws_h.get_all_records()
    if not data: return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
    df = pd.DataFrame(data)
    df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
    return df

def save_hist(df):
    ws_h.clear()
    df["Poids"] = df["Poids"].astype(float)
    data = [df.columns.values.tolist()] + df.values.tolist()
    ws_h.update(data, value_input_option='USER_ENTERED')

# Init
prog = load_prog()
df_h = get_hist()

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Progrès"])

# --- ONGLET 1 : PROGRAMME ---
with tab1:
    st.subheader("Mes Séances")
    jours = list(prog.keys())
    for idx, j in enumerate(jours):
        with st.expander(f"⚙️ {j}"):
            c1, c2 = st.columns([1, 1])
            if c1.button("⬆️ Monter", key=f"up_{j}") and idx > 0:
                jours[idx], jours[idx-1] = jours[idx-1], jours[idx]; save_prog({k: prog[k] for k in jours}); st.rerun()
            if c2.button("🗑️ Supprimer", key=f"del_{j}"): del prog[j]; save_prog(prog); st.rerun()
            for i, ex in enumerate(prog[j]):
                col1, col2 = st.columns([8, 2])
                col1.write(f"**{ex}**")
                if col2.button("🗑️", key=f"de_{j}_{i}"): prog[j].pop(i); save_prog(prog); st.rerun()
            nv = st.text_input("Ajouter exo :", key=f"in_{j}")
            if st.button("Ajouter", key=f"bt_{j}") and nv: prog[j].append(nv); save_prog(prog); st.rerun()

# --- ONGLET 2 : SÉANCE ---
with tab2:
    if not prog: st.warning("Crée une séance !")
    else:
        choix_s = st.selectbox("Séance :", list(prog.keys()), label_visibility="collapsed")
        sem = st.number_input("Semaine N°", min_value=1, value=1)
        
        for exo in prog[choix_s]:
            with st.expander(f"🔹 {exo}", expanded=True):
                h1 = df_h[(df_h["Exercice"] == exo) & (df_h["Semaine"] == sem - 1) & (df_h["Séance"] == choix_s)]
                if not h1.empty:
                    st.caption(f"🔍 Hier (S{sem-1}) :")
                    # FIX DÉCIMALES ICI
                    st.dataframe(h1[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                
                curr = df_h[(df_h["Exercice"] == exo) & (df_h["Semaine"] == sem) & (df_h["Séance"] == choix_s)]
                if not curr.empty:
                    st.caption(f"✅ Performance S{sem} (Comparée à S{sem-1}) :")
                    # FIX DÉCIMALES + COULEURS
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.format({"Poids": "{:g}"}).apply(style_comparaison, axis=1, hist_s1=h1), 
                                 hide_index=True, use_container_width=True)
                    if st.button(f"🔄 Modifier {exo}", key=f"mod_{exo}"):
                        m = (df_h["Semaine"] == sem) & (df_h["Séance"] == choix_s) & (df_h["Exercice"] == exo)
                        save_hist(df_h[~m]); st.rerun()
                else:
                    df_def = pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]})
                    edited = st.data_editor(df_def, num_rows="dynamic", key=f"ed_{exo}", use_container_width=True, 
                                            column_config={"Poids": st.column_config.NumberColumn("Poids", format="%g", step=0.1)})
                    
                    c_v, c_s = st.columns(2)
                    if c_v.button(f"✅ Valider {exo}", key=f"v_{exo}"):
                        v = edited[(edited["Poids"] > 0) | (edited["Reps"] > 0)].copy()
                        v["Semaine"], v["Séance"], v["Exercice"] = sem, choix_s, exo
                        save_hist(pd.concat([df_h, v], ignore_index=True)); st.rerun()
                    if c_s.button(f"🚫 Pas de séance", key=f"sk_{exo}"):
                        sk = pd.DataFrame({"Semaine": [sem], "Séance": [choix_s], "Exercice": [exo], "Série": [1], "Reps": [0], "Poids": [0.0], "Remarque": ["MANQUÉE ❌"]})
                        save_hist(pd.concat([df_h, sk], ignore_index=True)); st.rerun()

# --- ONGLET 3 : PROGRÈS (RESTAURÉ) ---
with tab3:
    if df_h.empty: st.info("Fais ton premier entraînement !")
    else:
        st.subheader("📊 Résumé Global")
        col1, col2, col3 = st.columns(3)
        total_p = (df_h["Poids"] * df_h["Reps"]).sum()
        max_sem = df_h["Semaine"].max()
        nb_reelles = len(df_h[df_h["Poids"] > 0].groupby(["Semaine", "Séance"]))
        col1.metric("Semaine Max", f"S{max_sem}")
        col2.metric("Poids total", f"{int(total_p)} kg")
        col3.metric("Nb Séances", nb_reelles)
        st.markdown("---")
        
        sel_exo = st.selectbox("Choisis un exercice :", sorted(list(df_h["Exercice"].unique())))
        df_exo = df_h[df_h["Exercice"] == sel_exo].copy()
        
        if not df_exo.empty:
            df_valide = df_exo[df_exo["Poids"] > 0]
            if not df_valide.empty:
                # Calcul Record & 1RM
                best_set = df_valide.sort_values(by=["Poids", "Reps"], ascending=False).iloc[0]
                df_valide["1RM"] = df_valide.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
                
                c_rec, c_1rm = st.columns(2)
                c_rec.success(f"🏆 Record : **{best_set['Poids']} kg x {int(best_set['Reps'])}**")
                c_1rm.info(f"💪 Force (1RM) : **{round(df_valide['1RM'].max(), 1)} kg**")
                
                st.caption("📈 Évolution des charges (Poids Max) :")
                st.line_chart(df_exo.groupby("Semaine")["Poids"].max())
            
            with st.expander("Historique complet"):
                st.dataframe(df_exo[["Semaine", "Séance", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Semaine", "Série"], ascending=[False, True]), hide_index=True, use_container_width=True)
