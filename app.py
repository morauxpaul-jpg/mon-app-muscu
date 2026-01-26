import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Muscu Tracker PRO", layout="centered", page_icon="logo.png")

if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()

# --- 2. CSS : DESIGN CYBER-RPG INTERACTIF ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 50% 0%, rgba(10, 50, 100, 0.4) 0%, transparent 50%),
                    linear-gradient(180deg, #050A18 0%, #000000 100%);
        background-attachment: fixed; color: #F0F2F6;
    }
    
    /* INTERACTIVE RANK MAP */
    .career-map {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(15px);
        border: 1px solid rgba(88, 204, 255, 0.2);
        border-radius: 20px;
        padding: 20px;
        margin-bottom: 30px;
    }
    
    .rank-node {
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        transition: all 0.3s ease;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .rank-node.active {
        border: 2px solid #58CCFF;
        box-shadow: 0 0 20px rgba(88, 204, 255, 0.5);
        background: rgba(88, 204, 255, 0.1);
    }
    .rank-node.locked {
        filter: blur(2px) grayscale(100%);
        opacity: 0.4;
    }
    .rank-node.completed {
        border-color: #00FF7F;
        background: rgba(0, 255, 127, 0.05);
    }

    /* XP PROGRESS BAR */
    .xp-bar-container { width: 100%; margin: 20px 0; }
    .xp-bar-bg { background: rgba(255,255,255,0.1); height: 12px; border-radius: 6px; overflow: hidden; }
    .xp-bar-fill { height: 100%; background: linear-gradient(90deg, #58CCFF, #00FF7F); box-shadow: 0 0 15px #58CCFF; transition: width 1s ease; }

    /* VOLUME OVERDRIVE */
    .vol-overdrive { color: #00FF7F; font-weight: bold; text-shadow: 0 0 10px #00FF7F; animation: pulse 2s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }

    .stExpander { background: rgba(255, 255, 255, 0.02) !important; border: 1px solid rgba(88, 204, 255, 0.2) !important; border-radius: 15px !important; }
    .cyber-analysis { background: rgba(88, 204, 255, 0.07); border-left: 4px solid #58CCFF; padding: 15px; border-radius: 0 10px 10px 0; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS ---
def calc_1rm(weight, reps):
    return weight * (1 + reps / 30) if reps > 0 else 0

def get_base_name(full_name):
    return full_name.split("(")[0].strip() if "(" in full_name else full_name

def style_comparaison(row, hist_prev):
    if hist_prev is None or hist_prev.empty: return ["", "", "", ""]
    prev_set = hist_prev[hist_prev["Série"] == row["Série"]]
    v, r = "background-color: rgba(0, 255, 127, 0.15); color: #00FF7F;", "background-color: rgba(255, 69, 58, 0.15); color: #FF453A;"
    colors = ["", "", "", ""] 
    if not prev_set.empty:
        pw, pr = float(prev_set.iloc[0]["Poids"]), int(prev_set.iloc[0]["Reps"])
        cw, cr = float(row["Poids"]), int(row["Reps"])
        if cw < pw: colors[1], colors[2] = r, r
        elif cw > pw: colors[1], colors[2] = v, v
        elif cw == pw:
            if cr > pr: colors[1] = v
            elif cr < pr: colors[1] = r
    return colors

# --- DATA ---
@st.cache_resource
def get_gs():
    try:
        creds = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open("Muscu_App")
        return sh.get_worksheet(0), sh.worksheet("Programme")
    except: return None, None

ws_h, ws_p = get_gs()

def get_hist():
    try:
        data = ws_h.get_all_records()
        df = pd.DataFrame(data)
        for col in ["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque", "Muscle", "Date"]:
            if col not in df.columns: df[col] = "" if col in ["Remarque", "Muscle", "Date", "Séance", "Exercice"] else 0
        df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
        df["Reps"] = pd.to_numeric(df["Reps"], errors='coerce').fillna(0).astype(int)
        df["Semaine"] = pd.to_numeric(df["Semaine"], errors='coerce').fillna(1).astype(int)
        return df
    except: return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque", "Muscle", "Date"])

def save_hist(df):
    ws_h.clear()
    ws_h.update([df.copy().fillna("").columns.values.tolist()] + df.copy().fillna("").values.tolist(), value_input_option='USER_ENTERED')

df_h = get_hist()
prog_raw = ws_p.acell('A1').value if ws_p else "{}"
try: prog = json.loads(prog_raw)
except: prog = {}

muscle_mapping = {ex["name"]: ex.get("muscle", "Autre") for s in prog for ex in prog[s]}
df_h["Muscle"] = df_h["Exercice"].apply(get_base_name).map(muscle_mapping).fillna(df_h["Muscle"]).replace("", "Autre")

# UI Header
col_logo1, col_logo2, col_logo3 = st.columns([1, 1.8, 1])
with col_logo2: st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 PROGRAMME", "🏋️‍♂️ MA SÉANCE", "📈 PROGRÈS"])

# --- TAB 1 : PROGRAMME ---
with tab1:
    jours = list(prog.keys())
    for j in jours:
        with st.expander(f"📦 {j}"):
            for i, ex in enumerate(prog[j]):
                c1, c2, c3 = st.columns([3, 1.5, 0.5])
                c1.write(f"**{ex['name']}**")
                ex['muscle'] = c2.selectbox("Groupe", ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"], index=["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"].index(ex.get("muscle", "Autre")), key=f"m_{j}_{i}")
                if c3.button("🗑️", key=f"rm_{j}_{i}"):
                    prog[j].pop(i); ws_p.update_acell('A1', json.dumps(prog)); st.rerun()

# --- TAB 2 : MA SÉANCE (HISTORIQUE VERTICAL & SKIP) ---
with tab2:
    if prog:
        c_s1, c_s2 = st.columns([3, 1])
        choix_s = c_s1.selectbox("Sélection séance :", list(prog.keys()))
        s_act = c_s2.number_input("Semaine", 1, 52, int(df_h["Semaine"].max() if not df_h.empty else 1))
        
        # Volume Check
        vol_curr = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Reps"]).sum()
        vol_prev = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Reps"]).sum()
        if vol_prev > 0:
            if vol_curr >= vol_prev: st.markdown("<div class='vol-overdrive'>⚡ MODE OVERDRIVE ACTIVÉ : Volume supérieur à la semaine dernière !</div>", unsafe_allow_html=True)
            st.progress(min(vol_curr / vol_prev, 1.0))

        for i, ex_obj in enumerate(prog[choix_s]):
            exo_base, p_sets, muscle_grp = ex_obj["name"], ex_obj["sets"], ex_obj.get("muscle", "Autre")
            with st.expander(f"🔹 {exo_base.upper()}", expanded=True):
                var = st.selectbox("Équipement", ["Standard", "Barre", "Haltères", "Banc", "Poulie", "Machine", "Lesté"], key=f"v_{exo_base}_{i}")
                exo_final = f"{exo_base} ({var})" if var != "Standard" else exo_base
                f_h = df_h[df_h["Exercice"] == exo_final]

                # --- LOGIQUE HISTORIQUE VERTICAL ---
                if s_act == 2:
                    h1 = f_h[f_h["Semaine"] == 1]
                    if not h1.empty:
                        st.caption("📅 Semaine S-1")
                        st.dataframe(h1[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                elif s_act > 2:
                    h2 = f_h[f_h["Semaine"] == s_act - 2]
                    if not h2.empty:
                        st.caption("📅 Semaine S-2")
                        st.dataframe(h2[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                    h1 = f_h[f_h["Semaine"] == s_act - 1]
                    if not h1.empty:
                        st.caption("📅 Semaine S-1")
                        st.dataframe(h1[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)

                curr = f_h[f_h["Semaine"] == s_act]
                if not curr.empty and exo_final not in st.session_state.editing_exo:
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.apply(style_comparaison, axis=1, hist_prev=f_h[f_h["Semaine"] == s_act-1]), hide_index=True, use_container_width=True)
                    if st.button("🔄 Modifier", key=f"m_{exo_final}"): st.session_state.editing_exo.add(exo_final); st.rerun()
                else:
                    df_ed = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                    ed = st.data_editor(df_ed, num_rows="fixed", key=f"ed_{exo_final}", use_container_width=True)
                    c_v, c_sk = st.columns(2)
                    if c_v.button("💾 Enregistrer", key=f"sv_{exo_final}"):
                        v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                        v["Semaine"], v["Séance"], v["Exercice"], v["Muscle"], v["Date"] = s_act, choix_s, exo_final, muscle_grp, datetime.now().strftime("%Y-%m-%d")
                        mask = (df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final)
                        save_hist(pd.concat([df_h[~mask], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo_final); st.rerun()
                    if c_sk.button("⏩ Skip", key=f"sk_{exo_final}"):
                        sk = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": exo_final, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫", "Muscle": muscle_grp, "Date": datetime.now().strftime("%Y-%m-%d")}])
                        save_hist(pd.concat([df_h, sk], ignore_index=True)); st.rerun()

# --- TAB 3 : PROGRÈS (CAREER MAP INTERACTIVE) ---
with tab3:
    if not df_h.empty:
        vol_tot = int((df_h['Poids'] * df_h['Reps']).sum())
        paliers = [0, 5000, 25000, 75000, 200000, 500000]
        noms = ["RECRUE NÉON", "CYBER-SOLDAT", "ÉLITE DE CHROME", "TITAN D'ACIER", "LÉGENDE CYBER", "DIEU DU FER"]
        
        cur_idx = next((i for i, p in enumerate(paliers[::-1]) if vol_tot >= p), 0)
        cur_idx = len(paliers) - 1 - cur_idx

        st.markdown("### 🗺️ CARTE DE CARRIÈRE CYBERNÉTIQUE")
        
        # Sélecteur de rang interactif
        sel_r = st.select_slider("Inspecter les paliers :", options=noms, value=noms[cur_idx])
        idx_inspect = noms.index(sel_r)
        
        # Affichage visuel du rang inspecté
        status = "locked" if idx_inspect > cur_idx else ("active" if idx_inspect == cur_idx else "completed")
        st.markdown(f"""
        <div class='career-map'>
            <div class='rank-node {status}'>
                <small>PALIER {idx_inspect + 1}</small><br>
                <b style='font-size:22px; color:#58CCFF;'>{sel_r}</b><br>
                <p>Objectif : {paliers[idx_inspect]:,} kg cumulés</p>
                <div style='font-size:12px;'>Statut : {status.upper()}</div>
            </div>
            <div class='xp-bar-container'>
                <div class='xp-bar-bg'><div class='xp-bar-fill' style='width:{(vol_tot/paliers[idx_inspect+1 if idx_inspect < 5 else 5])*100 if idx_inspect == cur_idx else (100 if status == "completed" else 0)}%'></div></div>
                <center><small>{vol_tot:,} kg soulevés au total</small></center>
            </div>
        </div>
        """.replace(',', ' '), unsafe_allow_html=True)

        # Radar & Analyse
        st.markdown("### 🕸️ Radar d'Équilibre")
        standards = {"Jambes": 150, "Dos": 120, "Pecs": 100, "Épaules": 75, "Bras": 50, "Abdos": 40}
        df_p = df_h[df_h["Reps"] > 0].copy()
        df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        scores = [min((df_p[df_p["Muscle"] == m]["1RM"].max() / standards[m]) * 100, 110) if not df_p[df_p["Muscle"] == m].empty else 0 for m in standards.keys()]
        
        fig = go.Figure(data=go.Scatterpolar(r=scores + [scores[0]], theta=list(standards.keys()) + [list(standards.keys())[0]], fill='toself', line=dict(color='#58CCFF', width=3)))
        fig.update_layout(polar=dict(radialaxis=dict(visible=False, range=[0, 110])), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white", margin=dict(l=40, r=40, t=20, b=20), height=350)
        st.plotly_chart(fig, use_container_width=True)

        if any(s > 0 for s in scores):
            top_m = list(standards.keys())[scores.index(max(scores))]
            st.markdown(f"<div class='cyber-analysis'>🛡️ <b>Analyseur</b> : Ta force est actuellement dominée par tes {top_m}. Pour un équilibre cybernétique parfait, concentre-toi sur tes points les plus bas du radar.</div>", unsafe_allow_html=True)

        st.divider()
        sel_e = st.selectbox("🎯 Zoom mouvement :", sorted(df_h["Exercice"].unique()))
        df_rec = df_h[df_h["Exercice"] == sel_e].copy()
        if not df_rec.empty:
            st.line_chart(df_rec.groupby("Semaine")["Poids"].max())
