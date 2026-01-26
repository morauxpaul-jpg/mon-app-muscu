import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime

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
        text-shadow: 0 0 15px rgba(74, 144, 226, 0.8), 0 0 5px rgba(74, 144, 226, 0.5) !important; 
    }
    .stExpander { background-color: rgba(10, 25, 49, 0.6) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 10px; backdrop-filter: blur(5px); }
    .podium-card { background: rgba(255, 255, 255, 0.07); border-radius: 12px; padding: 15px; border-top: 3px solid #4A90E2; text-align: center; }
    .pr-alert { color: #00FF7F; font-weight: bold; text-shadow: 0 0 10px #00FF7F; padding: 10px; border: 1px solid #00FF7F; border-radius: 5px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    if reps <= 0: return 0
    return weight * (1 + reps / 30)

def get_rep_estimations(one_rm):
    percentages = {1: 1.0, 3: 0.94, 5: 0.89, 8: 0.81, 10: 0.75, 12: 0.71}
    return {rep: round(one_rm * pct, 1) for rep, pct in percentages.items()}

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
        if not data: return pd.DataFrame(columns=["Cycle", "Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque", "Muscle", "Date"])
        df = pd.DataFrame(data)
        df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
        df["Reps"] = pd.to_numeric(df["Reps"], errors='coerce').fillna(0).astype(int)
        df["Semaine"] = pd.to_numeric(df["Semaine"], errors='coerce').fillna(1).astype(int)
        df["Cycle"] = pd.to_numeric(df["Cycle"], errors='coerce').fillna(1).astype(int)
        return df
    except: return pd.DataFrame(columns=["Cycle", "Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque", "Muscle", "Date"])

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
            prog[s] = [{"name": name, "sets": 3, "muscle": "Autre"} for name in prog[s]]
        for exo in prog[s]:
            if "muscle" not in exo: exo["muscle"] = "Autre"
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
                name = ex_obj["name"]; nb_sets = ex_obj["sets"]; muscle = ex_obj["muscle"]
                c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 1.5, 0.8, 0.8, 0.8])
                c1.write(f"**{name}**")
                new_s = c2.number_input("Séries", 1, 15, nb_sets, key=f"s_{j}_{i}")
                new_m = c3.selectbox("Muscle", ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"], index=["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"].index(muscle), key=f"m_{j}_{i}")
                
                if new_s != nb_sets or new_m != muscle:
                    prog[j][i]["sets"], prog[j][i]["muscle"] = new_s, new_m
                    save_prog(prog); st.rerun()
                
                if c4.button("⬆️", key=f"ue_{j}_{i}"):
                    if i > 0: prog[j][i], prog[j][i-1] = prog[j][i-1], prog[j][i]; save_prog(prog); st.rerun()
                if c5.button("⬇️", key=f"de_{j}_{i}"):
                    if i < len(prog[j])-1: prog[j][i], prog[j][i+1] = prog[j][i+1], prog[j][i]; save_prog(prog); st.rerun()
                if c6.button("🗑️", key=f"rm_{j}_{i}"):
                    prog[j].pop(i); save_prog(prog); st.rerun()
            
            st.divider()
            cx, cm, cs = st.columns([3, 2, 1])
            ni = cx.text_input("Ajouter exo", key=f"ni_{j}")
            nm = cm.selectbox("Groupe", ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"], key=f"nm_{j}")
            ns = cs.number_input("Sets", 1, 15, 3, key=f"ns_{j}")
            if st.button("Ajouter", key=f"ba_{j}") and ni:
                prog[j].append({"name": ni, "sets": ns, "muscle": nm}); save_prog(prog); st.rerun()
    st.divider()
    nvs = st.text_input("➕ Créer séance")
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
            exo = ex_obj["name"]; p_sets = ex_obj["sets"]; muscle_grp = ex_obj["muscle"]
            col_name, col_u, col_d = st.columns([8, 1, 1])
            col_name.markdown(f"### 🔹 {exo}")
            
            if col_u.button("⬆️", key=f"u_{exo}_{i}"):
                if i > 0: prog[choix_s][i], prog[choix_s][i-1] = prog[choix_s][i-1], prog[choix_s][i]; save_prog(prog); st.rerun()
            if col_d.button("⬇️", key=f"d_{exo}_{i}"):
                if i < len(prog[choix_s])-1: prog[choix_s][i], prog[choix_s][i+1] = prog[choix_s][i+1], prog[choix_s][i]; save_prog(prog); st.rerun()

            with st.expander(f"Saisie : {exo}", expanded=True):
                full_exo_h = df_h[df_h["Exercice"] == exo]
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
                    
                    # --- CHECK PR ALERT ---
                    if not v_rows.empty:
                        new_1rm = max(v_rows.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1))
                        old_1rm = 0
                        if not full_exo_h.empty:
                            old_1rm = max(full_exo_h.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1))
                        if new_1rm > old_1rm and old_1rm > 0:
                            st.balloons()
                            st.markdown(f"<div class='pr-alert'>🔥 NEW PERSONAL RECORD UNLOCKED : {round(new_1rm, 1)} kg ! 🔥</div>", unsafe_allow_html=True)

                    v_rows["Cycle"], v_rows["Semaine"], v_rows["Séance"], v_rows["Exercice"] = cycle_act, sem_stk, choix_s, exo
                    v_rows["Muscle"], v_rows["Date"] = muscle_grp, datetime.now().strftime("%Y-%m-%d")
                    mask = (df_h["Semaine"] == sem_stk) & (df_h["Cycle"] == cycle_act) & (df_h["Séance"] == choix_s) & (df_h["Exercice"] == exo)
                    save_hist(pd.concat([df_h[~mask], v_rows], ignore_index=True)); st.rerun()

# --- TAB 3 : PROGRÈS ---
with tab3:
    if not df_h.empty:
        # --- HEATMAP DE RÉGULARITÉ ---
        st.subheader("📅 Heatmap de Régularité")
        if "Date" in df_h.columns:
            activity = df_h[df_h["Date"] != ""].groupby("Date")["Séance"].nunique().reset_index()
            st.caption("Jours d'entraînement enregistrés :")
            # Simulation visuelle simple GitHub-style
            act_dates = set(activity["Date"])
            st.write(" ".join(["🟩" if datetime.now().strftime("%Y-%m-%d") == d else "⬜" for d in act_dates]))
            st.info(f"Tu as complété **{len(act_dates)}** jours d'entraînement au total.")

        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("Volume Total", f"{int((df_h['Poids'] * df_h['Reps']).sum())} kg")
        col2.metric("Cycle Actuel", int(df_h["Cycle"].max()))
        col3.metric("Semaine Max", int(df_h["Semaine"].replace(0, 10).max()))
        
        st.divider()
        st.subheader("🏆 Podium de Force")
        # FILTRE PAR MUSCLE
        muscle_filter = st.multiselect("Filtrer par muscle :", ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"], default=["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"])
        
        df_all_rm = df_h[(df_h["Poids"] >= 0) & (df_h["Muscle"].isin(muscle_filter))].copy()
        df_all_rm["1RM"] = df_all_rm.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        
        if not df_all_rm.empty:
            podium = df_all_rm.groupby("Exercice").agg({"1RM": "max", "Poids": "max", "Reps": "max"}).sort_values(by="1RM", ascending=False).head(3)
            p_cols = st.columns(3)
            medals = ["🥇", "🥈", "🥉"]
            for idx, (exo_n, row) in enumerate(podium.iterrows()):
                with p_cols[idx]:
                    st.markdown(f"<div class='podium-card'><b>{medals[idx]} {exo_n}</b><br><span style='color:#4A90E2; font-size:20px;'>{row['1RM']:.1f} kg</span><br><small>{row['Poids']:.1f}kg x {int(row['Reps'])}</small></div>", unsafe_allow_html=True)

        st.divider()
        sel_exo = st.selectbox("Zoom sur un exercice :", sorted(df_h["Exercice"].unique()))
        df_zoom = df_h[df_h["Exercice"] == sel_exo].copy()
        
        if not df_zoom.empty:
            df_valides = df_zoom[(df_zoom["Poids"] > 0) | (df_zoom["Reps"] > 0)].copy()
            if not df_valides.empty:
                best_row = df_valides.sort_values(by=["Poids", "Reps"], ascending=False).iloc[0]
                one_rm_val = calc_1rm(best_row['Poids'], best_row['Reps'])
                
                c_res1, c_res2 = st.columns(2)
                c_res1.success(f"🏆 Record : **{best_row['Poids']} kg x {int(best_row['Reps'])}**")
                c_res2.info(f"💪 Force (1RM) : **{round(one_rm_val, 1)} kg**")
                
                # --- ESTIMATIONS REP MAX ---
                with st.expander("📊 Estimations de charges (Rep Max)"):
                    estimations = get_rep_estimations(one_rm_val)
                    c_est = st.columns(len(estimations))
                    for idx, (r, p) in enumerate(estimations.items()):
                        c_est[idx].metric(f"{r} Reps", f"{p} kg")

                c_chart = df_valides.groupby(["Cycle", "Semaine"])["Poids"].max().reset_index()
                c_chart["Point"] = "C" + c_chart["Cycle"].astype(str) + "-S" + c_chart["Semaine"].astype(str)
                st.line_chart(c_chart.set_index("Point")["Poids"])
            
            st.dataframe(df_zoom[["Cycle", "Semaine", "Série", "Reps", "Poids", "Remarque", "Muscle"]].sort_values(by=["Cycle", "Semaine"], ascending=False), hide_index=True)
