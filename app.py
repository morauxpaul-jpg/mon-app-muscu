import streamlit as st
import pandas as pd
import json
import gspread

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Musculation Tracker", layout="centered", page_icon="logo.png")

if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()

# --- CSS : DESIGN & EFFET LUMINEUX (NÉON) ---
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
    .stExpander { background-color: rgba(10, 25, 49, 0.6) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 10px; margin-bottom: 10px; backdrop-filter: blur(5px); }
    
    /* EFFET NÉON SUR LES METRICS */
    div[data-testid="stMetricValue"] { 
        font-size: 32px !important; 
        color: #4A90E2 !important; 
        font-weight: 800; 
        text-shadow: 0 0 15px rgba(74, 144, 226, 0.8), 0 0 5px rgba(74, 144, 226, 0.5) !important; 
    }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    if reps <= 0: return 0
    # Formule de Brzycki
    return weight * (1 + reps / 30)

def style_comparaison(row, hist_s1):
    if hist_s1.empty or "Série" not in hist_s1.columns:
        return ["", "", "", ""]
    prev_set = hist_s1[hist_s1["Série"] == row["Série"]]
    v = "background-color: rgba(46, 125, 50, 0.4); color: white;" # Vert
    r = "background-color: rgba(198, 40, 40, 0.4); color: white;" # Rouge
    o = "background-color: rgba(255, 152, 0, 0.4); color: white;" # Orange
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
    creds = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(creds)
    sh = gc.open("Muscu_App")
    return sh.get_worksheet(0), sh.worksheet("Programme")

ws_h, ws_p = get_google_sheets()

def get_hist():
    data = ws_h.get_all_records()
    if not data: return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
    df = pd.DataFrame(data)
    df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
    return df

def save_hist(df):
    ws_h.clear()
    data = [df.columns.values.tolist()] + df.values.tolist()
    ws_h.update(data, value_input_option='USER_ENTERED')

# --- CHARGEMENT ---
df_h = get_hist()
prog = json.loads(ws_p.acell('A1').value or "{}")

# LOGO
col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
with col_l2: st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Progrès"])

# --- ONGLET 1 : PROGRAMME ---
with tab1:
    for jour, exos in prog.items():
        with st.expander(f"⚙️ {jour}"):
            for i, exo in enumerate(exos):
                c1, c2 = st.columns([8, 2])
                c1.write(f"**{exo}**")
                if c2.button("🗑️", key=f"d_{jour}_{i}"):
                    exos.pop(i); ws_p.update_acell('A1', json.dumps(prog)); st.rerun()
            nv = st.text_input("Ajouter exo", key=f"n_{jour}")
            if st.button("Valider", key=f"b_{jour}") and nv:
                exos.append(nv); ws_p.update_acell('A1', json.dumps(prog)); st.rerun()

# --- ONGLET 2 : MA SÉANCE ---
with tab2:
    if not prog: st.warning("Crée une séance !")
    else:
        c_t1, c_t2 = st.columns([2, 1])
        choix_s = c_t1.selectbox("Séance :", list(prog.keys()))
        sem = c_t2.number_input("Semaine", min_value=1, value=1)
        
        if st.button("🚫 Skip Séance Entière", use_container_width=True):
            sk = [{"Semaine": sem, "Séance": choix_s, "Exercice": e, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "Loupé ❌"} for e in prog[choix_s]]
            save_hist(pd.concat([df_h, pd.DataFrame(sk)], ignore_index=True)); st.rerun()

        for exo in prog[choix_s]:
            with st.expander(f"🔹 {exo}", expanded=True):
                full_h = df_h[(df_h["Exercice"] == exo) & (df_h["Séance"] == choix_s) & (df_h["Semaine"] < sem)].sort_values(by="Semaine", ascending=False)
                last_w = full_h["Semaine"].unique()[:2]
                
                if len(last_w) > 0:
                    for w in last_w:
                        st.write(f"**S{w}**")
                        st.dataframe(full_h[full_h["Semaine"] == w][["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                
                curr = df_h[(df_h["Exercice"] == exo) & (df_h["Semaine"] == sem) & (df_h["Séance"] == choix_s)]
                h_s1 = full_h[full_h["Semaine"] == last_w[0]] if len(last_w) > 0 else pd.DataFrame()

                if not curr.empty and exo not in st.session_state.editing_exo:
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.format({"Poids": "{:g}"}).apply(style_comparaison, axis=1, hist_s1=h_s1), hide_index=True, use_container_width=True)
                    if st.button(f"🔄 Modifier / Ajouter", key=f"ed_{exo}"): st.session_state.editing_exo.add(exo); st.rerun()
                else:
                    df_ed = pd.concat([curr[["Série", "Reps", "Poids", "Remarque"]], pd.DataFrame({"Série": [int(curr["Série"].max()+1 if not curr.empty else 1)], "Reps": [0], "Poids": [0.0], "Remarque": [""]})], ignore_index=True)
                    ed = st.data_editor(df_ed, num_rows="dynamic", key=f"e_{exo}", use_container_width=True, column_config={"Poids": st.column_config.NumberColumn(format="%g")})
                    c_v, c_s = st.columns(2)
                    if c_v.button(f"✅ Valider {exo}", key=f"v_{exo}"):
                        v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                        v["Semaine"], v["Séance"], v["Exercice"] = sem, choix_s, exo
                        mask = (df_h["Semaine"] == sem) & (df_h["Séance"] == choix_s) & (df_h["Exercice"] == exo)
                        save_hist(pd.concat([df_h[~mask], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo); st.rerun()
                    if c_s.button(f"🚫 Skip Exo", key=f"sk_{exo}"):
                        sk = pd.DataFrame([{"Semaine": sem, "Séance": choix_s, "Exercice": exo, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫"}])
                        save_hist(pd.concat([df_h, sk], ignore_index=True)); st.rerun()

# --- ONGLET 3 : PROGRÈS (EFFET LUMINEUX & 1RM) ---
with tab3:
    if not df_h.empty:
        col1, col2, col3 = st.columns(3)
        # Calcul du volume total sur les lignes valides
        vol_total = (df_h["Poids"] * df_h["Reps"]).sum()
        nb_seances = len(df_h[df_h["Poids"] > 0].groupby(["Semaine", "Séance"]))
        
        col1.metric("Volume Total", f"{int(vol_total)} kg")
        col2.metric("Séances", nb_seances)
        col3.metric("Max Semaine", f"S{df_h['Semaine'].max()}")
        
        st.divider()
        
        sel_exo = st.selectbox("Zoom Exercice :", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel_exo].copy()
        
        if not df_e.empty:
            df_v = df_e[df_e["Poids"] > 0]
            if not df_v.empty:
                # Calcul Record et 1RM
                max_row = df_v.sort_values(by=["Poids", "Reps"], ascending=False).iloc[0]
                df_v["1RM"] = df_v.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
                max_1rm = df_v["1RM"].max()
                
                c_r1, c_r2 = st.columns(2)
                c_r1.success(f"🏆 Record : **{max_row['Poids']} kg x {int(max_row['Reps'])}**")
                c_r2.info(f"💪 Force Pure (1RM) : **{round(max_1rm, 1)} kg**")
                
                st.line_chart(df_e.groupby("Semaine")["Poids"].max())
            
            st.dataframe(df_e[["Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values(by="Semaine", ascending=False), hide_index=True)
