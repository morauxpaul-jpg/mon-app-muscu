import streamlit as st
import pandas as pd
import json
import gspread

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Muscu Tracker PRO", layout="centered", page_icon="logo.png")

if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()

# --- 2. CSS : LOOK NÉON & DESIGN ---
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
    .podium-card { background: rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 15px; border-left: 5px solid #4A90E2; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    if reps <= 0: return 0
    # Formule de Brzycki
    return weight * (1 + reps / 30)

# --- CONNEXION ---
@st.cache_resource
def get_google_sheets():
    try:
        creds = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open("Muscu_App")
        return sh.get_worksheet(0), sh.worksheet("Programme")
    except: return None, None

ws_h, ws_p = get_google_sheets()

def get_hist():
    try:
        data = ws_h.get_all_records()
        if not data: return pd.DataFrame(columns=["Cycle", "Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
        df = pd.DataFrame(data)
        df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
        df["Reps"] = pd.to_numeric(df["Reps"], errors='coerce').fillna(0).astype(int)
        df["Semaine"] = pd.to_numeric(df["Semaine"], errors='coerce').fillna(1).astype(int)
        return df
    except: return pd.DataFrame(columns=["Cycle", "Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])

def save_hist(df):
    df_clean = df.copy().fillna("")
    ws_h.clear()
    data = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
    ws_h.update(data, value_input_option='USER_ENTERED')

def save_prog(prog_dict):
    ws_p.update_acell('A1', json.dumps(prog_dict))

# Load Data
df_h = get_hist()
prog_raw = ws_p.acell('A1').value if ws_p else "{}"
try: 
    prog = json.loads(prog_raw) 
    for s in prog:
        if prog[s] and isinstance(prog[s][0], str):
            prog[s] = [{"name": name, "sets": 3} for name in prog[s]]
except: prog = {}

# Logo
col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
with col_l2: st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Progrès"])

# --- TAB 1 : PROGRAMME ---
with tab1:
    jours = list(prog.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"⚙️ {j}"):
            for i, ex_obj in enumerate(prog[j]):
                name = ex_obj["name"]; nb_sets = ex_obj["sets"]
                c1, c2, c3, c4, c5 = st.columns([4, 2, 1, 1, 1])
                c1.write(f"**{name}**")
                new_s = c2.number_input("Séries", 1, 10, nb_sets, key=f"s_{j}_{i}")
                if new_s != nb_sets:
                    prog[j][i]["sets"] = new_s
                    save_prog(prog); st.rerun()
                if c3.button("⬆️", key=f"ue_{j}_{i}"):
                    if i > 0: prog[j][i], prog[j][i-1] = prog[j][i-1], prog[j][i]; save_prog(prog); st.rerun()
                if c4.button("⬇️", key=f"de_{j}_{i}"):
                    if i < len(prog[j])-1: prog[j][i], prog[j][i+1] = prog[j][i+1], prog[j][i]; save_prog(prog); st.rerun()
                if c5.button("🗑️", key=f"rm_{j}_{i}"):
                    prog[j].pop(i); save_prog(prog); st.rerun()
            cx, cs = st.columns([3, 1])
            ni = cx.text_input("Nouvel exo", key=f"ni_{j}")
            ns = cs.number_input("Sets", 1, 10, 3, key=f"ns_{j}")
            if st.button("Ajouter", key=f"ba_{j}") and ni:
                prog[j].append({"name": ni, "sets": ns}); save_prog(prog); st.rerun()
    st.divider()
    nvs = st.text_input("➕ Nom de séance")
    if st.button("Créer séance") and nvs:
        prog[nvs] = []; save_prog(prog); st.rerun()

# --- TAB 2 : MA SÉANCE ---
with tab2:
    if not prog: st.warning("Crée une séance dans le programme.")
    else:
        col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
        choix_s = col_s1.selectbox("Séance :", list(prog.keys()))
        cycle_act = col_s2.number_input("Cycle", 1, 100, int(df_h["Cycle"].max() if not df_h.empty else 1))
        sem_in = col_s3.number_input("Semaine", 1, 10, 1)
        sem_stk = 0 if sem_in == 10 else sem_in

        for i, ex_obj in enumerate(prog[choix_s]):
            exo = ex_obj["name"]; p_sets = ex_obj["sets"]
            col_name, col_u, col_d = st.columns([8, 1, 1])
            col_name.markdown(f"### 🔹 {exo}") # Pas de mention des séries ici
            
            if col_u.button("⬆️", key=f"u_{exo}_{i}"):
                if i > 0: prog[choix_s][i], prog[choix_s][i-1] = prog[choix_s][i-1], prog[choix_s][i]; save_prog(prog); st.rerun()
            if col_d.button("⬇️", key=f"d_{exo}_{i}"):
                if i < len(prog[choix_s])-1: prog[choix_s][i], prog[choix_s][i+1] = prog[choix_s][i+1], prog[choix_s][i]; save_prog(prog); st.rerun()

            with st.expander(f"Saisie : {exo}", expanded=True):
                full_exo_h = df_h[(df_h["Exercice"] == exo) & (df_h["Séance"] == choix_s)]
                curr = full_exo_h[(full_exo_h["Semaine"] == sem_stk) & (full_exo_h["Cycle"] == cycle_act)]
                df_fixed = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                if not curr.empty:
                    for idx, row in curr.iterrows():
                        if row["Série"] <= p_sets:
                            df_fixed.loc[df_fixed["Série"] == row["Série"], ["Reps", "Poids", "Remarque"]] = [row["Reps"], row["Poids"], row["Remarque"]]

                ed = st.data_editor(df_fixed, num_rows="fixed", key=f"ed_{exo}_{sem_stk}", use_container_width=True, 
                                    column_config={"Série": st.column_config.NumberColumn(disabled=True), "Poids": st.column_config.NumberColumn(format="%g")})
                
                c_v, c_s = st.columns(2)
                if c_v.button(f"✅ Valider {exo}", key=f"val_{exo}"):
                    v_rows = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                    v_rows["Cycle"], v_rows["Semaine"], v_rows["Séance"], v_rows["Exercice"] = cycle_act, sem_stk, choix_s, exo
                    mask = (df_h["Semaine"] == sem_stk) & (df_h["Cycle"] == cycle_act) & (df_h["Séance"] == choix_s) & (df_h["Exercice"] == exo)
                    save_hist(pd.concat([df_h[~mask], v_rows], ignore_index=True)); st.rerun()

# --- TAB 3 : PROGRÈS ---
with tab3:
    if not df_h.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Volume Total", f"{int((df_h['Poids'] * df_h['Reps']).sum())} kg")
        col2.metric("Cycle Actuel", int(df_h["Cycle"].max()))
        # FIX SEMAINE : Prend la semaine max de l'historique
        col3.metric("Semaine Max", int(df_h["Semaine"].replace(0, 10).max()))
        
        st.divider()
        
        # --- SECTION PODIUM ---
        st.subheader("🏆 Podium de Force (Top 1RM)")
        df_podium = df_h[df_h["Poids"] >= 0].copy()
        df_podium["1RM"] = df_podium.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        # On garde le meilleur 1RM par exercice
        best_perfs = df_podium.groupby("Exercice").agg({"1RM": "max", "Poids": "max", "Reps": "max"}).sort_values(by="1RM", ascending=False).head(3)
        
        p_cols = st.columns(3)
        icons = ["🥇", "🥈", "🥉"]
        for idx, (exo_name, row) in enumerate(best_perfs.iterrows()):
            with p_cols[idx]:
                st.markdown(f"""<div class='podium-card'>
                <b>{icons[idx]} {exo_name}</b><br>
                {row['1RM']:.1f} kg (théorique)<br>
                <small>Record: {row['Poids']:.1f}kg x {int(row['Reps'])}</small>
                </div>""", unsafe_allow_html=True)

        st.divider()
        
        sel = st.selectbox("Zoom sur un exercice :", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel].copy()
        if not df_e.empty:
            df_v = df_e[(df_e["Poids"] > 0) | (df_e["Reps"] > 0)].copy()
            if not df_v.empty:
                max_s = df_v.sort_values(by=["Poids", "Reps"], ascending=False).iloc[0]
                st.info(f"Record Actuel : **{max_s['Poids']} kg x {int(max_s['Reps'])}**")
                c_data = df_v.groupby(["Cycle", "Semaine"])["Poids"].max().reset_index()
                c_data["Point"] = "C" + c_data["Cycle"].astype(str) + "-S" + c_data["Semaine"].astype(str)
                st.line_chart(c_data.set_index("Point")["Poids"])
            st.dataframe(df_e[["Cycle", "Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Cycle", "Semaine"], ascending=False), hide_index=True)
