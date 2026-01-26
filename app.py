import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime, timedelta
import plotly.graph_objects as go

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Muscu Tracker PRO", layout="centered", page_icon="logo.png")

if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()

# --- 2. CSS : DESIGN CYBER-RPG COMPLET ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 50% 0%, rgba(10, 50, 100, 0.4) 0%, transparent 50%),
                    linear-gradient(180deg, #050A18 0%, #000000 100%);
        background-attachment: fixed; color: #F0F2F6;
    }
    
    /* TIMELINE DE CARRIÈRE INTERACTIVE */
    .career-timeline {
        display: flex; overflow-x: auto; gap: 20px; padding: 25px 10px;
        scrollbar-width: none; -ms-overflow-style: none;
    }
    .career-timeline::-webkit-scrollbar { display: none; }
    
    .mission-card {
        min-width: 160px; padding: 20px; border-radius: 15px;
        background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(12px);
        border: 1px solid rgba(88, 204, 255, 0.2); text-align: center;
        transition: all 0.4s ease-out; position: relative;
    }
    .rank-active { 
        border: 2px solid #58CCFF !important; 
        box-shadow: 0 0 25px rgba(88, 204, 255, 0.5);
        background: rgba(88, 204, 255, 0.1) !important;
        transform: scale(1.08);
    }
    .rank-locked { opacity: 0.35; filter: blur(3px); }
    .rank-completed { border-color: #00FF7F !important; background: rgba(0, 255, 127, 0.05) !important; }

    /* XP BAR */
    .xp-status { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 11px; color: #58CCFF; }
    .xp-bar-bg { width: 100%; background: rgba(255,255,255,0.1); border-radius: 10px; height: 12px; overflow: hidden; margin-bottom: 20px; }
    .xp-bar-fill { height: 100%; background: linear-gradient(90deg, #58CCFF, #00FF7F); box-shadow: 0 0 15px #58CCFF; }

    /* PODIUM */
    .podium-card { background: rgba(255, 255, 255, 0.07); border-radius: 12px; padding: 15px; text-align: center; margin-bottom: 10px; border-top: 4px solid #58CCFF; }
    .podium-gold { border-color: #FFD700 !important; }
    .podium-silver { border-color: #C0C0C0 !important; }
    .podium-bronze { border-color: #CD7F32 !important; }

    /* UI ELEMENTS */
    .stExpander { background: rgba(255, 255, 255, 0.02) !important; border: 1px solid rgba(88, 204, 255, 0.2) !important; border-radius: 15px !important; }
    .cyber-analysis { background: rgba(88, 204, 255, 0.08); border-left: 4px solid #58CCFF; padding: 15px; border-radius: 0 10px 10px 0; margin-bottom: 25px; }
    .vol-overdrive { color: #00FF7F; text-shadow: 0 0 10px #00FF7F; font-weight: bold; margin-bottom: 10px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- 3. FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    return weight * (1 + reps / 30) if reps > 0 else 0

def get_rep_estimations(one_rm):
    return {r: round(one_rm * pct, 1) for r, pct in {1: 1.0, 3: 0.94, 5: 0.89, 8: 0.81, 10: 0.75, 12: 0.71}.items()}

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

# --- 4. CONNEXION ET DATA ---
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
        cols = ["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque", "Muscle", "Date"]
        for col in cols:
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

# MAPPING MUSCLE INTELLIGENT
muscle_mapping = {ex["name"]: ex.get("muscle", "Autre") for s in prog for ex in prog[s]}
df_h["Muscle"] = df_h["Exercice"].apply(get_base_name).map(muscle_mapping).fillna(df_h["Muscle"]).replace("", "Autre")

# --- SIDEBAR MAINTENANCE ---
with st.sidebar:
    st.title("🛡️ Système")
    if st.button("🗑️ Reset Calendrier"):
        df_h["Date"] = ""
        save_hist(df_h); st.rerun()

# --- HEADER ---
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
                ex['sets'] = c2.number_input("Séries", 1, 15, ex.get('sets', 3), key=f"p_s_{j}_{i}")
                ex['muscle'] = c2.selectbox("Muscle", ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"], index=["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"].index(ex.get("muscle", "Autre")), key=f"m_{j}_{i}")
                if c3.button("🗑️", key=f"rm_{j}_{i}"):
                    prog[j].pop(i); ws_p.update_acell('A1', json.dumps(prog)); st.rerun()
    nvs = st.text_input("➕ Nouvelle séance")
    if st.button("🎯 Valider") and nvs: prog[nvs] = []; ws_p.update_acell('A1', json.dumps(prog)); st.rerun()

# --- TAB 2 : MA SÉANCE ---
with tab2:
    if prog:
        c_s1, c_s2 = st.columns([3, 1])
        choix_s = c_s1.selectbox("Sélection séance :", list(prog.keys()))
        s_act = c_s2.number_input("Semaine", 1, 52, int(df_h["Semaine"].max() if not df_h.empty else 1))
        
        # Overdrive Check
        vol_curr = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Reps"]).sum()
        vol_prev = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Reps"]).sum()
        if vol_prev > 0 and vol_curr >= vol_prev: st.markdown("<div class='vol-overdrive'>🚀 MODE OVERDRIVE ACTIVÉ !</div>", unsafe_allow_html=True)

        for i, ex_obj in enumerate(prog[choix_s]):
            exo_base, p_sets, muscle_grp = ex_obj["name"], ex_obj["sets"], ex_obj.get("muscle", "Autre")
            with st.expander(f"🔹 {exo_base.upper()}", expanded=True):
                var = st.selectbox("Équipement", ["Standard", "Barre", "Haltères", "Banc", "Poulie", "Machine", "Lesté"], key=f"v_{exo_base}_{i}")
                exo_final = f"{exo_base} ({var})" if var != "Standard" else exo_base
                f_h = df_h[df_h["Exercice"] == exo_final]

                # HISTORIQUE VERTICAL STRICT
                if s_act > 1:
                    if s_act > 2:
                        h2 = f_h[f_h["Semaine"] == s_act - 2]
                        if not h2.empty:
                            st.caption(f"📅 Semaine S-2 ({s_act-2})")
                            st.dataframe(h2[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                    h1 = f_h[f_h["Semaine"] == s_act - 1]
                    if not h1.empty:
                        st.caption(f"📅 Semaine S-1 ({s_act-1})")
                        st.dataframe(h1[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)

                curr = f_h[f_h["Semaine"] == s_act]
                if not curr.empty and exo_final not in st.session_state.editing_exo:
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.apply(style_comparaison, axis=1, hist_prev=f_h[f_h["Semaine"] == s_act-1]), hide_index=True, use_container_width=True)
                    if st.button("🔄 Modifier", key=f"m_{exo_final}"): st.session_state.editing_exo.add(exo_final); st.rerun()
                else:
                    df_ed = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                    if not curr.empty:
                        for _, r in curr.iterrows():
                            if r["Série"] <= p_sets: df_ed.loc[df_ed["Série"] == r["Série"], ["Reps", "Poids", "Remarque"]] = [r["Reps"], r["Poids"], r["Remarque"]]
                    
                    ed = st.data_editor(df_ed, num_rows="fixed", key=f"ed_{exo_final}", use_container_width=True)
                    c_v, c_sk = st.columns(2)
                    if c_v.button("💾 Enregistrer", key=f"sv_{exo_final}"):
                        v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                        v["Semaine"], v["Séance"], v["Exercice"], v["Muscle"], v["Date"] = s_act, choix_s, exo_final, muscle_grp, datetime.now().strftime("%Y-%m-%d")
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final))], v], ignore_index=True))
                        if not v.empty and not f_h[f_h["Semaine"] < s_act].empty:
                            if max(v.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)) > max(f_h[f_h["Semaine"] < s_act].apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)):
                                st.balloons()
                        st.session_state.editing_exo.discard(exo_final); st.rerun()
                    if c_sk.button("⏩ Skip Exo", key=f"sk_{exo_final}"):
                        sk = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": exo_final, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫", "Muscle": muscle_grp, "Date": datetime.now().strftime("%Y-%m-%d")}])
                        save_hist(pd.concat([df_h, sk], ignore_index=True)); st.rerun()

# --- TAB 3 : PROGRÈS ---
with tab3:
    if not df_h.empty:
        # CAREER RANKS SYSTEM
        v_tot = int((df_h['Poids'] * df_h['Reps']).sum())
        paliers = [0, 5000, 25000, 75000, 200000, 500000]
        noms = ["RECRUE NÉON", "CYBER-SOLDAT", "ÉLITE DE CHROME", "TITAN D'ACIER", "LÉGENDE CYBER", "DIEU DU FER"]
        cur_idx = next((i for i, p in enumerate(paliers[::-1]) if v_tot >= p), 0)
        cur_idx = len(paliers) - 1 - cur_idx
        
        st.markdown("### 🧬 ÉVOLUTION DE CARRIÈRE")
        rank_html = "<div class='career-timeline'>"
        for i, n in enumerate(noms):
            status = "rank-locked"
            label = "VERROUILLÉ"
            if i < cur_idx: status, label = "rank-completed", "✓ VALIDÉ"
            elif i == cur_idx: status, label = "rank-active", "ACTIF"
            rank_html += f"<div class='mission-card {status}'><small>LVL {i+1}</small><br><b style='font-size:13px;'>{n}</b><br><small style='font-size:10px;'>{paliers[i]:,} kg</small><br><div style='margin-top:10px; font-size:10px; color:#58CCFF;'>{label}</div></div>"
        rank_html += "</div>"
        st.markdown(rank_html, unsafe_allow_html=True)
        
        next_p = paliers[cur_idx+1] if cur_idx < 5 else paliers[-1]
        ratio = min((v_tot - paliers[cur_idx]) / (next_p - paliers[cur_idx]), 1.0) if next_p > paliers[cur_idx] else 1.0
        st.markdown(f"<div class='xp-status'><span>STASE XP</span><span>CIBLE: {next_p:,} KG</span></div><div class='xp-bar-bg'><div class='xp-bar-fill' style='width:{ratio*100}%'></div></div><center><small>{v_tot:,} kg totalisés</small></center>".replace(',', ' '), unsafe_allow_html=True)

        # RADAR & ANALYSE
        st.markdown("### 🕸️ Radar d'Équilibre")
        standards = {"Jambes": 150, "Dos": 120, "Pecs": 100, "Épaules": 75, "Bras": 50, "Abdos": 40}
        df_p = df_h[df_h["Reps"] > 0].copy()
        df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        scores = [min((df_p[df_p["Muscle"] == m]["1RM"].max() / standards[m]) * 100, 110) if not df_p[df_p["Muscle"] == m].empty else 0 for m in standards.keys()]
        
        fig_r = go.Figure(data=go.Scatterpolar(r=scores + [scores[0]], theta=list(standards.keys()) + [list(standards.keys())[0]], fill='toself', line=dict(color='#58CCFF', width=3)))
        fig_r.update_layout(polar=dict(radialaxis=dict(visible=False, range=[0, 110])), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white", height=350)
        st.plotly_chart(fig_r, use_container_width=True, config={'displayModeBar': False})

        if any(s > 0 for s in scores):
            top_m = list(standards.keys())[scores.index(max(scores))]
            st.markdown(f"<div class='cyber-analysis'>🛡️ <b>Analyseur</b> : Ta force est actuellement dominée par tes {top_m}. Pour un équilibre cybernétique parfait, renforce les zones les plus réduites du radar.</div>", unsafe_allow_html=True)

        # PODIUM
        st.markdown("### 🏅 Hall of Fame")
        m_filt = st.multiselect("Filtrer muscle :", list(standards.keys()) + ["Autre"], default=list(standards.keys()) + ["Autre"])
        df_p_filt = df_p[df_p["Muscle"].isin(m_filt)]
        if not df_p_filt.empty:
            podium = df_p_filt.groupby("Exercice").agg({"1RM": "max"}).sort_values(by="1RM", ascending=False).head(3)
            p_cols = st.columns(3); meds, clss = ["🥇", "🥈", "🥉"], ["podium-gold", "podium-silver", "podium-bronze"]
            for idx, (ex_n, row) in enumerate(podium.iterrows()):
                with p_cols[idx]: st.markdown(f"<div class='podium-card {clss[idx]}'><small>{meds[idx]}</small><br><b>{ex_n}</b><br><span style='color:#58CCFF; font-size:22px;'>{row['1RM']:.1f}kg</span></div>", unsafe_allow_html=True)

        # ZOOM MOUVEMENT
        st.divider()
        sel_e = st.selectbox("🎯 Zoom mouvement :", sorted(df_h["Exercice"].unique()))
        df_rec = df_h[df_h["Exercice"] == sel_e].copy(); df_rec = df_rec[(df_rec["Poids"] > 0) | (df_rec["Reps"] > 0)]
        if not df_rec.empty:
            best = df_rec.sort_values(["Poids", "Reps"], ascending=False).iloc[0]; one_rm = calc_1rm(best['Poids'], best['Reps'])
            c1r, c2r = st.columns(2); c1r.success(f"🏆 RECORD RÉEL\n\n**{best['Poids']}kg x {int(best['Reps'])}**"); c2r.info(f"⚡ 1RM ESTIMÉ\n\n**{one_rm:.1f} kg**")
            fig_l = go.Figure(); c_dat = df_rec.groupby("Semaine")["Poids"].max().reset_index()
            fig_l.add_trace(go.Scatter(x=c_dat["Semaine"], y=c_dat["Poids"], mode='lines+markers', line=dict(color='#58CCFF', width=4), marker=dict(size=10, color='#00FF7F')))
            fig_l.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=10, b=0), height=300)
            st.plotly_chart(fig_l, use_container_width=True, config={'displayModeBar': False})
            with st.expander("📊 Estimation Rep Max"):
                ests = get_rep_estimations(one_rm); cols = st.columns(len(ests))
                for idx, (r, p) in enumerate(ests.items()): cols[idx].metric(f"{r} Reps", f"{p}kg")
        st.dataframe(df_h[df_h["Exercice"] == sel_e][["Semaine", "Série", "Reps", "Poids", "Remarque", "Muscle"]].sort_values("Semaine", ascending=False), hide_index=True)
