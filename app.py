import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Musculation Tracker", layout="centered", page_icon="logo.png")

if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()

# --- CSS : DESIGN NÉON & TRANSLUCIDE ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                    linear-gradient(180deg, #0A1931 0%, #000000 100%);
        background-attachment: fixed; background-size: cover;
        color: #E0E0E0; font-family: 'Helvetica', sans-serif;
    }
    .stTabs [data-baseweb="tab-list"] { background-color: rgba(255, 255, 255, 0.05) !important; border-radius: 12px; }
    .stTabs [aria-selected="true"] { background-color: rgba(255, 255, 255, 0.9) !important; color: #0A1931 !important; border-radius: 8px; font-weight: bold; }
    div[data-testid="stMetricValue"] { 
        font-size: 32px !important; color: #4A90E2 !important; font-weight: 800; 
        text-shadow: 0 0 15px rgba(74, 144, 226, 0.8) !important; 
    }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def calc_ratio(weight, reps):
    if reps <= 0: return 0
    return weight * (1 + reps / 30)

def style_comparaison(row, hist_prev):
    if hist_prev.empty or "Série" not in hist_prev.columns:
        return ["", "", "", "", ""] # Ajout d'une case vide pour la colonne Date
    prev_set = hist_prev[hist_prev["Série"] == row["Série"]]
    v, r, o = "background-color: rgba(46,125,50,0.4);", "background-color: rgba(198,40,40,0.4);", "background-color: rgba(255,152,0,0.4);"
    colors = ["", "", "", "", ""] 
    if not prev_set.empty:
        pw, pr = float(prev_set.iloc[0]["Poids"]), int(prev_set.iloc[0]["Reps"])
        cw, cr = float(row["Poids"]), int(row["Reps"])
        if calc_ratio(cw, cr) > calc_ratio(pw, pr) and cw < pw: colors[2], colors[3] = o, o
        elif cw > pw: colors[2], colors[3] = v, v
        elif cw < pw: colors[2], colors[3] = r, r
        elif cw == pw:
            if cr > pr: colors[2] = v
            elif cr < pr: colors[2] = r
    return colors

# --- CONNEXION & DATA ---
@st.cache_resource
def get_google_sheets():
    creds = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(creds)
    sh = gc.open("Muscu_App")
    return sh.get_worksheet(0), sh.worksheet("Programme")

ws_h, ws_p = get_google_sheets()

def get_hist():
    data = ws_h.get_all_records()
    if not data: return pd.DataFrame(columns=["Date", "Cycle", "Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
    df = pd.DataFrame(data)
    if "Date" not in df.columns: df.insert(0, "Date", "")
    if "Cycle" not in df.columns: df["Cycle"] = 1
    df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
    return df

def save_hist(df):
    ws_h.clear()
    data = [df.columns.values.tolist()] + df.values.tolist()
    ws_h.update(data, value_input_option='USER_ENTERED')

# Init
df_h = get_hist()
prog = json.loads(ws_p.acell('A1').value or "{}")

col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
with col_l2: st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Progrès"])

# --- ONGLET 2 : MA SÉANCE (Capture de la Date) ---
with tab2:
    if not prog: st.warning("Crée une séance !")
    else:
        c1, c2, c3 = st.columns([2, 1, 1])
        choix_s = c1.selectbox("Séance :", list(prog.keys()))
        cycle_act = c2.number_input("Cycle", min_value=1, value=int(df_h["Cycle"].max() if not df_h.empty else 1))
        sem_in = c3.number_input("Sem", min_value=1, max_value=10, value=1)
        sem_stk = 0 if sem_in == 10 else sem_in

        for exo in prog[choix_s]:
            with st.expander(f"🔹 {exo}", expanded=True):
                # Comparaison dynamique
                t_sem, t_cyc = (0, cycle_act - 1) if sem_stk == 1 else (sem_stk - 1, cycle_act)
                h_prev = df_h[(df_h["Exercice"] == exo) & (df_h["Semaine"] == t_sem) & (df_h["Cycle"] == t_cyc)]
                
                curr = df_h[(df_h["Exercice"] == exo) & (df_h["Semaine"] == sem_stk) & (df_h["Cycle"] == cycle_act)]

                if not curr.empty and exo not in st.session_state.editing_exo:
                    st.dataframe(curr[["Date", "Série", "Reps", "Poids", "Remarque"]].style.format({"Poids": "{:g}"}).apply(style_comparaison, axis=1, hist_prev=h_prev), hide_index=True, use_container_width=True)
                    if st.button(f"🔄 Modifier", key=f"ed_{exo}"): st.session_state.editing_exo.add(exo); st.rerun()
                else:
                    df_ed = pd.concat([curr[["Série", "Reps", "Poids", "Remarque"]], pd.DataFrame({"Série": [int(curr["Série"].max()+1 if not curr.empty else 1)], "Reps": [0], "Poids": [0.0], "Remarque": [""]})], ignore_index=True)
                    ed = st.data_editor(df_ed, num_rows="dynamic", key=f"e_{exo}", use_container_width=True)
                    
                    if st.button(f"✅ Valider {exo}", key=f"v_{exo}"):
                        v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                        v["Date"] = datetime.now().strftime("%d/%m/%Y") # DATE AUTOMATIQUE
                        v["Cycle"], v["Semaine"], v["Séance"], v["Exercice"] = cycle_act, sem_stk, choix_s, exo
                        mask = (df_h["Semaine"] == sem_stk) & (df_h["Cycle"] == cycle_act) & (df_h["Séance"] == choix_s) & (df_h["Exercice"] == exo)
                        save_hist(pd.concat([df_h[~mask], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo); st.rerun()

# --- ONGLET 3 : PROGRÈS (Graphique par Date) ---
with tab3:
    if not df_h.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Volume Total", f"{int((df_h['Poids'] * df_h['Reps']).sum())} kg")
        col2.metric("Cycle Actuel", int(df_h["Cycle"].max()))
        col3.metric("Dernière S.", f"S{sem_stk}")
        
        st.divider()
        sel_exo = st.selectbox("Zoom Exercice :", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel_exo].copy()
        
        if not df_e.empty:
            # Graphique avec Date en axe X
            st.caption("📈 Évolution temporelle (JJ/MM/AA)")
            # On regroupe par date pour avoir le poids max de la journée
            chart_data = df_e.groupby("Date")["Poids"].max()
            st.line_chart(chart_data)
            
            st.dataframe(df_e[["Date", "Cycle", "Semaine", "Série", "Reps", "Poids"]].sort_values(by=["Cycle", "Semaine"], ascending=False), hide_index=True)
