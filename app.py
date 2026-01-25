import streamlit as st
import pandas as pd
import json
import gspread

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Muscu Tracker PRO", layout="centered", page_icon="logo.png")

if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()

# --- CSS : LOOK NÉON ---
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

# --- FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    if reps <= 0: return 0
    return weight * (1 + reps / 30)

def style_comparaison(row, hist_prev):
    if hist_prev is None or hist_prev.empty: return ["", "", "", ""]
    prev_set = hist_prev[hist_prev["Série"] == row["Série"]]
    v, r, o = "background-color: rgba(46,125,50,0.4);", "background-color: rgba(198,40,40,0.4);", "background-color: rgba(255,152,0,0.4);"
    colors = ["", "", "", ""] 
    if not prev_set.empty:
        pw, pr = float(prev_set.iloc[0]["Poids"]), int(prev_set.iloc[0]["Reps"])
        cw, cr = float(row["Poids"]), int(row["Reps"])
        p_1rm, c_1rm = calc_1rm(pw, pr), calc_1rm(cw, cr)
        if c_1rm > p_1rm and cw < pw: colors[1], colors[2] = o, o
        elif cw > pw: colors[1], colors[2] = v, v
        elif cw < pw: colors[1], colors[2] = r, r
        elif cw == pw:
            if cr > pr: colors[1] = v
            elif cr < pr: colors[1] = r
    return colors

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
    # Migration auto si ancien format (liste de strings -> liste d'objets)
    for s in prog:
        if prog[s] and isinstance(prog[s][0], str):
            prog[s] = [{"name": name, "sets": 3} for name in prog[s]]
except: prog = {}

# Logo
col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
with col_l2: st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Progrès"])

# --- TAB 1 : PROGRAMME (AVEC CHOIX DU NOMBRE DE SÉRIES) ---
with tab1:
    st.subheader("Mes Séances")
    jours = list(prog.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"⚙️ {j}"):
            c1, c2 = st.columns(2)
            if c1.button(f"⬆️ Monter {j}", key=f"up_s_{j}"):
                if idx_j > 0:
                    jours[idx_j], jours[idx_j-1] = jours[idx_j-1], jours[idx_j]
                    save_prog({k: prog[k] for k in jours}); st.rerun()
            if c2.button(f"🗑️ Supprimer {j}", key=f"del_s_{j}"):
                del prog[j]; save_prog(prog); st.rerun()
            
            st.divider()
            for i, ex_obj in enumerate(prog[j]):
                # On gère l'affichage selon le format (objet ou string pour compatibilité)
                name = ex_obj["name"] if isinstance(ex_obj, dict) else ex_obj
                nb_sets = ex_obj["sets"] if isinstance(ex_obj, dict) else 3

                col1, col2, col3, col4, col5 = st.columns([4, 2, 1, 1, 1])
                col1.write(f"**{name}**")
                
                # Input pour changer le nombre de séries
                new_sets = col2.number_input("Séries", min_value=1, max_value=10, value=nb_sets, key=f"sets_{j}_{i}")
                if new_sets != nb_sets:
                    prog[j][i]["sets"] = new_sets
                    save_prog(prog); st.rerun()

                if col3.button("⬆️", key=f"ue_{j}_{i}") and i > 0:
                    prog[j][i], prog[j][i-1] = prog[j][i-1], prog[j][i]
                    save_prog(prog); st.rerun()
                if col4.button("⬇️", key=f"de_{j}_{i}") and i < len(prog[j])-1:
                    prog[j][i], prog[j][i+1] = prog[j][i+1], prog[j][i]
                    save_prog(prog); st.rerun()
                if col5.button("🗑️", key=f"rm_{j}_{i}"):
                    prog[j].pop(i); save_prog(prog); st.rerun()
            
            c_n1, c_n2 = st.columns([3, 1])
            nv_exo = c_n1.text_input("Nouvel exo", key=f"in_{j}")
            nv_sets = c_n2.number_input("Séries", 1, 10, 3, key=f"in_s_{j}")
            if st.button("Ajouter", key=f"bt_{j}") and nv_exo:
                prog[j].append({"name": nv_exo, "sets": nv_sets})
                save_prog(prog); st.rerun()
    
    st.divider()
    nvs = st.text_input("➕ Créer séance")
    if st.button("Créer") and nvs:
        prog[nvs] = []; save_prog(prog); st.rerun()

# --- TAB 2 : MA SÉANCE (AVEC LIGNES PRÉ-REMPLIES) ---
with tab2:
    if not prog: st.warning("Crée une séance dans l'onglet Programme.")
    else:
        c1, c2, c3 = st.columns([2, 1, 1])
        choix_s = c1.selectbox("Séance :", list(prog.keys()))
        cycle_act = c2.number_input("Cycle", min_value=1, value=int(df_h["Cycle"].max() if not df_h.empty else 1))
        sem_in = c3.number_input("Semaine", min_value=1, max_value=10, value=1)
        sem_stk = 0 if sem_in == 10 else sem_in

        if st.button("🚫 Séance Loupée ❌", use_container_width=True):
            sk = [{"Cycle": cycle_act, "Semaine": sem_stk, "Séance": choix_s, "Exercice": e["name"], "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "Loupé ❌"} for e in prog[choix_s]]
            save_hist(pd.concat([df_h, pd.DataFrame(sk)], ignore_index=True)); st.rerun()

        for i, ex_obj in enumerate(prog[choix_s]):
            exo = ex_obj["name"]
            planned_sets = ex_obj["sets"]

            col_name, col_u, col_d = st.columns([8, 1, 1])
            col_name.markdown(f"### 🔹 {exo} ({planned_sets} séries)")
            
            # Déplacement pendant la séance
            if col_u.button("⬆️", key=f"mu_{exo}_{i}") and i > 0:
                prog[choix_s][i], prog[choix_s][i-1] = prog[choix_s][i-1], prog[choix_s][i]
                save_prog(prog); st.rerun()
            if col_d.button("⬇️", key=f"md_{exo}_{i}") and i < len(prog[choix_s])-1:
                prog[choix_s][i], prog[choix_s][i+1] = prog[choix_s][i+1], prog[choix_s][i]
                save_prog(prog); st.rerun()

            with st.expander(f"Détails : {exo}", expanded=True):
                full_exo_h = df_h[(df_h["Exercice"] == exo) & (df_h["Séance"] == choix_s)]
                t_sem, t_cyc = (0, cycle_act - 1) if sem_stk == 1 else (sem_stk - 1, cycle_act)
                h_prev = full_exo_h[(full_exo_h["Semaine"] == t_sem) & (full_exo_h["Cycle"] == t_cyc)]
                
                # Historique x2
                last_w = full_exo_h[full_exo_h["Semaine"] < (sem_stk if sem_stk != 0 else 11)]["Semaine"].unique()[:2]
                if len(last_w) > 0:
                    st.caption("🔍 Historique :")
                    for w in last_w:
                        st.dataframe(full_exo_h[full_exo_h["Semaine"] == w][["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)

                # DONNÉES ACTUELLES
                curr = full_exo_h[(full_exo_h["Semaine"] == sem_stk) & (full_exo_h["Cycle"] == cycle_act)]

                # CONSTRUCTION DU TABLEAU FIXE
                # On pré-remplit le tableau avec le nombre de séries choisi dans le programme
                if curr.empty:
                    df_display = pd.DataFrame({
                        "Série": range(1, planned_sets + 1),
                        "Reps": [0] * planned_sets,
                        "Poids": [0.0] * planned_sets,
                        "Remarque": [""] * planned_sets
                    })
                else:
                    # On fusionne les données saisies avec les lignes vides restantes pour atteindre planned_sets
                    df_display = curr[["Série", "Reps", "Poids", "Remarque"]].copy()
                    existing_sets = df_display["Série"].tolist()
                    for s in range(1, planned_sets + 1):
                        if s not in existing_sets:
                            df_display = pd.concat([df_display, pd.DataFrame({"Série": [s], "Reps": [0], "Poids": [0.0], "Remarque": [""]})], ignore_index=True)
                    df_display = df_display.sort_values("Série").reset_index(drop=True)

                # ÉDITEUR
                ed = st.data_editor(df_display, num_rows="fixed", key=f"e_{exo}_{sem_stk}", use_container_width=True, 
                                    column_config={"Série": st.column_config.NumberColumn(disabled=True), "Poids": st.column_config.NumberColumn(format="%g")})
                
                c_v, c_s = st.columns(2)
                if c_v.button(f"✅ Valider {exo}", key=f"v_{exo}"):
                    # On ne garde que les lignes où l'utilisateur a mis du poids ou des reps
                    valid_rows = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                    valid_rows["Cycle"], valid_rows["Semaine"], valid_rows["Séance"], valid_rows["Exercice"] = cycle_act, sem_stk, choix_s, exo
                    
                    # On nettoie l'ancien avant de sauver le nouveau
                    mask = (df_h["Semaine"] == sem_stk) & (df_h["Cycle"] == cycle_act) & (df_h["Séance"] == choix_s) & (df_h["Exercice"] == exo)
                    save_hist(pd.concat([df_h[~mask], valid_rows], ignore_index=True))
                    st.success(f"Sauvegardé ! ({exo})")
                    st.rerun()
                
                if c_s.button(f"🚫 Skip Exo", key=f"sk_{exo}"):
                    sk = pd.DataFrame([{"Cycle": cycle_act, "Semaine": sem_stk, "Séance": choix_s, "Exercice": exo, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫"}])
                    save_hist(pd.concat([df_h, sk], ignore_index=True)); st.rerun()

# --- TAB 3 : PROGRÈS ---
with tab3:
    if not df_h.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Volume", f"{int((df_h['Poids'] * df_h['Reps']).sum())} kg")
        col2.metric("Cycle", int(df_h["Cycle"].max()))
        col3.metric("Semaine", sem_in)
        st.divider()
        sel = st.selectbox("Exercice :", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel].copy()
        if not df_e.empty:
            df_v = df_e[df_e["Poids"] > 0]
            if not df_v.empty:
                max_s = df_v.sort_values(by=["Poids", "Reps"], ascending=False).iloc[0]
                st.success(f"🏆 Record : **{max_s['Poids']} kg x {int(max_s['Reps'])}** - 1RM : **{round(calc_1rm(max_s['Poids'], max_s['Reps']), 1)} kg**")
                chart_data = df_e.groupby(["Cycle", "Semaine"])["Poids"].max().reset_index()
                chart_data["Point"] = "C" + chart_data["Cycle"].astype(str) + "-S" + chart_data["Semaine"].astype(str)
                st.line_chart(chart_data.set_index("Point")["Poids"])
            st.dataframe(df_e[["Cycle", "Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Cycle", "Semaine"], ascending=False), hide_index=True)
