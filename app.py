import streamlit as st
import pandas as pd
import json
import gspread

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Muscu Tracker PRO", layout="centered", page_icon="logo.png")

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
    .podium-card { background: rgba(255, 255, 255, 0.07); border-radius: 12px; padding: 15px; border-top: 3px solid #4A90E2; text-align: center; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    if reps <= 0: return 0
    return weight * (1 + reps / 30)

def style_comparaison(row, hist_prev):
    if hist_prev is None or hist_prev.empty: return ["", "", "", ""]
    prev_set = hist_prev[hist_prev["Série"] == row["Série"]]
    v = "background-color: rgba(46, 125, 50, 0.45); color: white;" 
    r = "background-color: rgba(198, 40, 40, 0.45); color: white;"
    colors = ["", "", "", ""] 
    if not prev_set.empty:
        pw, pr = float(prev_set.iloc[0]["Poids"]), int(prev_set.iloc[0]["Reps"])
        cw, cr = float(row["Poids"]), int(row["Reps"])
        if cw > pw or (cw == pw and cr > pr): colors[1], colors[2] = v, v
        elif cw < pw or (cw == pw and cr < pr): colors[1], colors[2] = r, r
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
        df["Reps"] = pd.to_numeric(df["Reps"], errors='coerce').fillna(0).astype(int)
        df["Cycle"] = pd.to_numeric(df["Cycle"], errors='coerce').fillna(1).astype(int)
        df["Semaine"] = pd.to_numeric(df["Semaine"], errors='coerce').fillna(1).astype(int)
        return df
    except: return pd.DataFrame(columns=["Cycle", "Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])

def save_hist(df):
    df_clean = df.copy().fillna("")
    ws_h.clear()
    ws_h.update([df_clean.columns.values.tolist()] + df_clean.values.tolist(), value_input_option='USER_ENTERED')

# --- CHARGEMENT ---
col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
with col_l2: st.image("logo.png", use_container_width=True)

df_h = get_hist()
prog_raw = ws_p.acell('A1').value if ws_p else "{}"
try:
    prog = json.loads(prog_raw)
    for s in prog:
        if prog[s] and isinstance(prog[s][0], str):
            prog[s] = [{"name": name, "sets": 3} for name in prog[s]]
except: prog = {}

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Progrès"])

# --- TAB 1 : PROGRAMME ---
with tab1:
    jours = list(prog.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"⚙️ {j}"):
            c_s1, c_s2 = st.columns(2)
            if c_s1.button(f"⬆️ Monter {j}", key=f"up_s_{j}") and idx_j > 0:
                jours[idx_j], jours[idx_j-1] = jours[idx_j-1], jours[idx_j]
                ws_p.update_acell('A1', json.dumps({k: prog[k] for k in jours})); st.rerun()
            if c_s2.button(f"🗑️ Supprimer {j}", key=f"del_s_{j}"):
                del prog[j]; ws_p.update_acell('A1', json.dumps(prog)); st.rerun()
            for i, ex in enumerate(prog[j]):
                c1, c2, c3, c4, c5 = st.columns([4, 2, 1, 1, 1])
                c1.write(f"**{ex['name']}**")
                ex['sets'] = c2.number_input("Séries", 1, 15, ex['sets'], key=f"p_s_{j}_{i}")
                if c3.button("⬆️", key=f"p_u_{j}_{i}") and i > 0:
                    prog[j][i], prog[j][i-1] = prog[j][i-1], prog[j][i]; ws_p.update_acell('A1', json.dumps(prog)); st.rerun()
                if c4.button("⬇️", key=f"p_d_{j}_{i}") and i < len(prog[j])-1:
                    prog[j][i], prog[j][i+1] = prog[j][i+1], prog[j][i]; ws_p.update_acell('A1', json.dumps(prog)); st.rerun()
                if c5.button("🗑️", key=f"p_r_{j}_{i}"):
                    prog[j].pop(i); ws_p.update_acell('A1', json.dumps(prog)); st.rerun()
            ni = st.text_input("Ajouter exo", key=f"ni_{j}")
            ns = st.number_input("Sets", 1, 15, 3, key=f"ns_{j}")
            if st.button("Ajouter", key=f"ba_{j}") and ni:
                prog[j].append({"name": ni, "sets": ns}); ws_p.update_acell('A1', json.dumps(prog)); st.rerun()
    nvs = st.text_input("➕ Nouvelle séance")
    if st.button("Créer") and nvs:
        prog[nvs] = []; ws_p.update_acell('A1', json.dumps(prog)); st.rerun()

# --- TAB 2 : MA SÉANCE (FIX HISTORIQUE) ---
with tab2:
    if prog:
        choix_s = st.selectbox("Séance :", list(prog.keys()))
        col_c, col_s = st.columns(2)
        c_act = col_c.number_input("Cycle", 1, 100, int(df_h["Cycle"].max() if not df_h.empty else 1))
        s_act = col_s.number_input("Semaine", 1, 10, 1)

        if st.button("🚫 Séance Loupée", use_container_width=True):
            sk_rows = [{"Cycle": c_act, "Semaine": s_act, "Séance": choix_s, "Exercice": e["name"], "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "Séance Loupée ❌"} for e in prog[choix_s]]
            save_hist(pd.concat([df_h, pd.DataFrame(sk_rows)], ignore_index=True)); st.rerun()

        for i, ex_obj in enumerate(prog[choix_s]):
            exo, p_sets = ex_obj["name"], ex_obj["sets"]
            st.markdown(f"### 🔹 {exo}")
            
            with st.expander(f"Saisie : {exo}", expanded=True):
                # 1. RÉCUPÉRATION HISTORIQUE STRICT (EXCLURE SÉANCE EN COURS)
                full_exo_h = df_h[(df_h["Exercice"] == exo) & (df_h["Séance"] == choix_s)]
                # Filtre temporel pour exclure la saisie actuelle de l'historique
                cond_hist = (full_exo_h["Cycle"] < c_act) | ((full_exo_h["Cycle"] == c_act) & (full_exo_h["Semaine"] < s_act))
                h_only = full_exo_h[cond_hist].sort_values(["Cycle", "Semaine"], ascending=False)
                last_s_unique = h_only[["Cycle", "Semaine"]].drop_duplicates().head(2)

                if not last_s_unique.empty:
                    st.caption("🔍 Historique (2 séances passées) :")
                    for _, r_s in last_s_unique.iterrows():
                        cp, sp = r_s["Cycle"], r_s["Semaine"]
                        st.write(f"**C{cp} - S{sp}**")
                        st.dataframe(h_only[(h_only["Cycle"] == cp) & (h_only["Semaine"] == sp)][["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)

                # 2. ÉDITEUR (SAISIE ACTUELLE)
                curr = full_exo_h[(full_exo_h["Cycle"] == c_act) & (full_exo_h["Semaine"] == s_act)]
                h_prev = h_only[(h_only["Cycle"] == last_s_unique.iloc[0]["Cycle"]) & (h_only["Semaine"] == last_s_unique.iloc[0]["Semaine"])] if not last_s_unique.empty else pd.DataFrame()

                df_ed = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                if not curr.empty:
                    for _, r in curr.iterrows():
                        if r["Série"] <= p_sets: df_ed.loc[df_ed["Série"] == r["Série"], ["Reps", "Poids", "Remarque"]] = [r["Reps"], r["Poids"], r["Remarque"]]
                
                # Applique le style SEULEMENT SI des données ont été entrées (pour éviter d'afficher l'éditeur coloré vide)
                ed_styled = df_ed.style.apply(style_comparaison, axis=1, hist_prev=h_prev) if not curr.empty else df_ed
                
                ed = st.data_editor(df_ed, num_rows="fixed", key=f"ed_{exo}_{s_act}_{c_act}_{choix_s}", use_container_width=True,
                                    column_config={"Série": st.column_config.NumberColumn(disabled=True), "Poids": st.column_config.NumberColumn(format="%g")})
                
                c_v, c_sk = st.columns(2)
                if c_v.button(f"✅ Valider {exo}", key=f"v_{exo}"):
                    v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                    v["Cycle"], v["Semaine"], v["Séance"], v["Exercice"] = c_act, s_act, choix_s, exo
                    mask = (df_h["Cycle"] == c_act) & (df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo) & (df_h["Séance"] == choix_s)
                    save_hist(pd.concat([df_h[~mask], v], ignore_index=True)); st.rerun()
                
                if c_sk.button(f"🚫 Skip Exo", key=f"sk_{exo}"):
                    sk = pd.DataFrame([{"Cycle": c_act, "Semaine": s_act, "Séance": choix_s, "Exercice": exo, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫"}])
                    save_hist(pd.concat([df_h, sk], ignore_index=True)); st.rerun()

# --- TAB 3 : PROGRÈS ---
with tab3:
    if not df_h.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Volume Total", f"{int((df_h['Poids'] * df_h['Reps']).sum())} kg")
        col2.metric("Cycle Actuel", int(df_h["Cycle"].max()))
        col3.metric("Semaine Max", int(df_h["Semaine"].max()))
        
        st.subheader("🏆 Podium de Force")
        df_p = df_h[df_h["Reps"] > 0].copy()
        df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        podium = df_p.groupby("Exercice").agg({"1RM": "max", "Poids": "max", "Reps": "max"}).sort_values(by="1RM", ascending=False).head(3)
        p_cols = st.columns(3)
        medals = ["🥇", "🥈", "🥉"]
        for idx, (ex_n, row) in enumerate(podium.iterrows()):
            with p_cols[idx]:
                st.markdown(f"<div class='podium-card'><b>{medals[idx]} {ex_n}</b><br><span style='color:#4A90E2; font-size:18px;'>{row['1RM']:.1f} kg</span><br><small>{row['Poids']:.1f}kg x {int(row['Reps'])}</small></div>", unsafe_allow_html=True)

        st.divider()
        sel = st.selectbox("Zoom sur un exercice :", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel].copy()
        df_rec = df_e[(df_e["Poids"] > 0) | (df_e["Reps"] > 0)].copy()
        if not df_rec.empty:
            best = df_rec.sort_values(["Poids", "Reps"], ascending=False).iloc[0]
            st.success(f"🏆 Record : **{best['Poids']} kg x {int(best['Reps'])}** (1RM: {calc_1rm(best['Poids'], best['Reps']):.1f} kg)")
            c_data = df_rec.groupby(["Cycle", "Semaine"])["Poids"].max().reset_index()
            c_data["Point"] = "C" + c_data["Cycle"].astype(str) + "-S" + c_data["Semaine"].astype(str)
            st.line_chart(c_data.set_index("Point")["Poids"])
        st.dataframe(df_e[["Cycle", "Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Cycle", "Semaine"], ascending=False), hide_index=True)
