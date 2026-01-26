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

# --- 2. CSS : DESIGN CYBER-PREMIUM ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 50% 0%, rgba(10, 50, 100, 0.4) 0%, transparent 50%),
                    linear-gradient(180deg, #050A18 0%, #000000 100%);
        background-attachment: fixed; color: #F0F2F6;
    }
    .stExpander {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(74, 144, 226, 0.3) !important;
        border-radius: 15px !important; backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6) !important; margin-bottom: 15px;
    }
    h1, h2, h3 { letter-spacing: 1.5px; text-transform: uppercase; color: #FFFFFF; text-shadow: 2px 2px 8px rgba(0,0,0,0.7); }
    div[data-testid="stMetricValue"] { 
        font-family: 'Courier New', monospace; font-size: 38px !important; color: #58CCFF !important; 
        font-weight: 900; text-shadow: 0 0 20px rgba(88, 204, 255, 0.6) !important; 
    }
    .stButton>button {
        border-radius: 8px !important; border: 1px solid rgba(74, 144, 226, 0.5) !important;
        background: rgba(10, 25, 50, 0.7) !important; color: #FFFFFF !important; transition: all 0.3s ease-out;
    }
    .stButton>button:hover { border-color: #58CCFF !important; box-shadow: 0 0 15px rgba(88, 204, 255, 0.5); transform: translateY(-2px); }
    .podium-card { background: rgba(255, 255, 255, 0.07); border-radius: 12px; padding: 15px; text-align: center; margin-bottom: 10px; border-top: 4px solid #58CCFF; }
    .podium-gold { border-color: #FFD700 !important; background: rgba(255, 215, 0, 0.05) !important; }
    .podium-silver { border-color: #C0C0C0 !important; background: rgba(192, 192, 192, 0.05) !important; }
    .podium-bronze { border-color: #CD7F32 !important; background: rgba(205, 127, 50, 0.05) !important; }
    .pr-alert { color: #00FF7F; font-weight: bold; text-shadow: 0 0 15px #00FF7F; padding: 15px; border: 2px solid #00FF7F; border-radius: 10px; text-align: center; background: rgba(0, 255, 127, 0.1); margin-bottom: 15px; }
    
    /* STYLE JAUGE VOLUME */
    .vol-container { background: rgba(255,255,255,0.05); border-radius: 10px; padding: 10px; margin-top: 10px; border: 1px solid rgba(88, 204, 255, 0.2); }
    .vol-bar { height: 12px; border-radius: 6px; background: #58CCFF; transition: width 0.5s ease-in-out; box-shadow: 0 0 10px #58CCFF; }
    .vol-overload { background: #00FF7F !important; box-shadow: 0 0 15px #00FF7F !important; }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    return weight * (1 + reps / 30) if reps > 0 else 0

def get_rep_estimations(one_rm):
    return {r: round(one_rm * pct, 1) for r, pct in {1: 1.0, 3: 0.94, 5: 0.89, 8: 0.81, 10: 0.75, 12: 0.71}.items()}

def get_base_name(full_name):
    if "(" in full_name: return full_name.split("(")[0].strip()
    return full_name

def style_comparaison(row, hist_prev):
    if hist_prev is None or hist_prev.empty: return ["", "", "", ""]
    prev_set = hist_prev[hist_prev["Série"] == row["Série"]]
    v, r = "background-color: rgba(0, 255, 127, 0.2); color: #00FF7F;", "background-color: rgba(255, 69, 58, 0.2); color: #FF453A;"
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
        df = pd.DataFrame(data)
        for col in ["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque", "Muscle", "Date"]:
            if col not in df.columns: df[col] = "" if col in ["Remarque", "Muscle", "Date", "Séance", "Exercice"] else 0
        df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
        df["Reps"] = pd.to_numeric(df["Reps"], errors='coerce').fillna(0).astype(int)
        df["Semaine"] = pd.to_numeric(df["Semaine"], errors='coerce').fillna(1).astype(int)
        return df
    except: return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque", "Muscle", "Date"])

def save_hist(df):
    df_clean = df.copy().fillna("")
    ws_h.clear()
    ws_h.update([df_clean.columns.values.tolist()] + df_clean.values.tolist(), value_input_option='USER_ENTERED')

def save_prog(prog_dict):
    ws_p.update_acell('A1', json.dumps(prog_dict))

# Load Data
df_h = get_hist()
prog_raw = ws_p.acell('A1').value if ws_p else "{}"
try:
    prog = json.loads(prog_raw)
    for s in prog:
        for exo in prog[s]:
            if "muscle" not in exo: exo["muscle"] = "Autre"
except: prog = {}

# Mapping Muscle Dynamique
muscle_mapping = {ex["name"]: ex.get("muscle", "Autre") for s in prog for ex in prog[s]}
df_h["Muscle"] = df_h["Exercice"].apply(get_base_name).map(muscle_mapping).fillna(df_h["Muscle"])
df_h["Muscle"] = df_h["Muscle"].replace("", "Autre")

# Logo centré
col_l1, col_l2, col_l3 = st.columns([1, 1.8, 1])
with col_l2: st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 PROGRAMME", "🏋️‍♂️ MA SÉANCE", "📈 PROGRÈS"])

# --- TAB 1 : PROGRAMME ---
with tab1:
    st.markdown("## ⚙️ Configuration")
    jours = list(prog.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"📦 {j}"):
            c_s1, c_s2 = st.columns(2)
            if c_s1.button("⬆️ Monter Séance", key=f"up_s_{j}") and idx_j > 0:
                jours[idx_j], jours[idx_j-1] = jours[idx_j-1], jours[idx_j]; save_prog({k: prog[k] for k in jours}); st.rerun()
            if c_s2.button("🗑️ Supprimer Séance", key=f"del_s_{j}"):
                del prog[j]; save_prog(prog); st.rerun()
            for i, ex in enumerate(prog[j]):
                c1, c2, c3, c4, c5, c6 = st.columns([3, 1.5, 1.5, 0.7, 0.7, 0.7])
                c1.write(f"**{ex['name']}**")
                ex['sets'] = c2.number_input("Sets", 1, 15, ex['sets'], key=f"p_s_{j}_{i}")
                ex['muscle'] = c3.selectbox("Muscle", ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"], index=["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"].index(ex.get("muscle", "Autre")), key=f"m_{j}_{i}")
                if c4.button("⬆️", key=f"ue_{j}_{i}"):
                    if i > 0: prog[j][i], prog[j][i-1] = prog[j][i-1], prog[j][i]; save_prog(prog); st.rerun()
                if c5.button("⬇️", key=f"de_{j}_{i}"):
                    if i < len(prog[j])-1: prog[j][i], prog[j][i+1] = prog[j][i+1], prog[j][i]; save_prog(prog); st.rerun()
                if c6.button("🗑️", key=f"rm_{j}_{i}"):
                    prog[j].pop(i); save_prog(prog); st.rerun()
            st.divider()
            cx, cm, cs = st.columns([3, 2, 1])
            ni, nm, ns = cx.text_input("Nouvel exo", key=f"ni_{j}"), cm.selectbox("Groupe", ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"], key=f"nm_{j}"), cs.number_input("Séries", 1, 15, 3, key=f"ns_{j}")
            if st.button("➕ Ajouter", key=f"ba_{j}") and ni:
                prog[j].append({"name": ni, "sets": ns, "muscle": nm}); save_prog(prog); st.rerun()
    nvs = st.text_input("➕ Nom nouvelle séance")
    if st.button("🎯 Créer séance") and nvs: prog[nvs] = []; save_prog(prog); st.rerun()

# --- TAB 2 : MA SÉANCE (AVEC JAUGE VOLUME) ---
with tab2:
    if prog:
        st.markdown("## ⚡ Ma Session")
        c_h1, c_h2 = st.columns([3, 1])
        choix_s = c_h1.selectbox("Séance :", list(prog.keys()))
        s_act = c_h2.number_input("Semaine actuelle", 1, 52, int(df_h["Semaine"].max() if not df_h.empty else 1))
        
        # CALCUL JAUGE VOLUME
        vol_curr = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Reps"]).sum()
        vol_prev = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Reps"]).sum()
        
        if vol_prev > 0:
            ratio = min(vol_curr / vol_prev, 1.2)
            color_class = "vol-overload" if ratio >= 1 else ""
            st.markdown(f"""
            <div class='vol-container'>
                <small>⚡ Progression Volume Session : {int(vol_curr)} / {int(vol_prev)} kg</small>
                <div style='width: 100%; background: rgba(255,255,255,0.1); border-radius: 6px; margin-top: 5px;'>
                    <div class='vol-bar {color_class}' style='width: {ratio*100}%;'></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        if st.button("🚫 SÉANCE LOUPÉE", use_container_width=True):
            sk = [{"Semaine": s_act, "Séance": choix_s, "Exercice": e["name"], "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "Loupée ❌", "Muscle": e.get("muscle", "Autre"), "Date": datetime.now().strftime("%Y-%m-%d")} for e in prog[choix_s]]
            save_hist(pd.concat([df_h, pd.DataFrame(sk)], ignore_index=True)); st.rerun()

        for i, ex_obj in enumerate(prog[choix_s]):
            exo_base, p_sets, muscle_grp = ex_obj["name"], ex_obj["sets"], ex_obj.get("muscle", "Autre")
            with st.expander(f"🔹 {exo_base.upper()}", expanded=True):
                var = st.selectbox("Équipement :", ["Standard", "Barre", "Haltères", "Banc", "Poulie", "Machine", "Lesté"], key=f"v_{exo_base}_{i}")
                exo_final = f"{exo_base} ({var})" if var != "Standard" else exo_base
                f_h = df_h[(df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s)]
                h_only = f_h[f_h["Semaine"] < s_act].sort_values("Semaine", ascending=False)
                last_s = h_only["Semaine"].unique()[:2]
                if len(last_s) > 0:
                    st.caption("🔍 Historique :")
                    st.dataframe(pd.concat([h_only[h_only["Semaine"] == s] for s in last_s])[["Semaine", "Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                
                curr = f_h[f_h["Semaine"] == s_act]
                if not curr.empty and exo_final not in st.session_state.editing_exo:
                    st.markdown("##### ✅ Validé")
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.apply(style_comparaison, axis=1, hist_prev=h_only[h_only["Semaine"] == last_s[0]] if len(last_s) > 0 else pd.DataFrame()).format({"Poids": "{:g}"}), hide_index=True, use_container_width=True)
                    if st.button(f"🔄 Modifier {exo_base}", key=f"m_{exo_final}_{i}"): st.session_state.editing_exo.add(exo_final); st.rerun()
                else:
                    df_ed = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                    if not curr.empty:
                        for _, r in curr.iterrows():
                            if r["Série"] <= p_sets: df_ed.loc[df_ed["Série"] == r["Série"], ["Reps", "Poids", "Remarque"]] = [r["Reps"], r["Poids"], r["Remarque"]]
                    ed = st.data_editor(df_ed, num_rows="fixed", key=f"ed_{exo_final}_{s_act}", use_container_width=True, column_config={"Série": st.column_config.NumberColumn(disabled=True), "Poids": st.column_config.NumberColumn(format="%g")})
                    if st.button(f"💾 Enregistrer {exo_base}", key=f"sv_{exo_final}"):
                        v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                        if not v.empty:
                            new_1rm, old_1rm = max(v.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)), max(f_h.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)) if not f_h.empty else 0
                            if new_1rm > old_1rm and old_1rm > 0: st.balloons(); st.markdown(f"<div class='pr-alert'>🚀 NEW RECORD : {round(new_1rm, 1)}kg !</div>", unsafe_allow_html=True)
                        v["Semaine"], v["Séance"], v["Exercice"], v["Muscle"], v["Date"] = s_act, choix_s, exo_final, muscle_grp, datetime.now().strftime("%Y-%m-%d")
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s))], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo_final); st.rerun()

# --- TAB 3 : PROGRÈS (AVEC RADAR DE FORCE) ---
with tab3:
    if not df_h.empty:
        st.markdown("### 🕸️ Radar d'Équilibre Cyber")
        
        # CALCUL SCORES RADAR (Normalisé par Standards Athlétiques)
        standards = {"Jambes": 150, "Dos": 120, "Pecs": 100, "Épaules": 75, "Bras": 50, "Abdos": 40}
        df_p = df_h[df_h["Reps"] > 0].copy()
        df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        
        scores = []
        labels = list(standards.keys())
        for m in labels:
            max_rm = df_p[df_p["Muscle"] == m]["1RM"].max() if not df_p[df_p["Muscle"] == m].empty else 0
            # Score de 0 à 100 (cap à 110 pour l'esthétique)
            score = min((max_rm / standards[m]) * 100, 110) if max_rm > 0 else 0
            scores.append(score)
            
        fig = go.Figure(data=go.Scatterpolar(
            r=scores + [scores[0]], theta=labels + [labels[0]], fill='toself',
            line=dict(color='#58CCFF', width=3), fillcolor='rgba(88, 204, 255, 0.2)',
            marker=dict(size=8, color='#58CCFF')
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 110], showticklabels=False, gridcolor="rgba(255,255,255,0.1)"),
                       angularaxis=dict(gridcolor="rgba(255,255,255,0.1)", color="white")),
            showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=40, r=40, t=20, b=20), height=350
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        c1, c2 = st.columns(2); c1.metric("VOL. TOTAL", f"{int((df_h['Poids'] * df_h['Reps']).sum()):,} kg".replace(',', ' ')); c2.metric("SEMAINE MAX", int(df_h["Semaine"].max()))
        
        st.markdown("### 🏅 Hall of Fame")
        m_filter = st.multiselect("Filtrer par muscle :", labels + ["Autre"], default=labels + ["Autre"])
        df_p_filt = df_p[df_p["Muscle"].isin(m_filter)]
        if not df_p_filt.empty:
            podium = df_p_filt.groupby("Exercice").agg({"1RM": "max"}).sort_values(by="1RM", ascending=False).head(3)
            p_cols = st.columns(3); meds, clss = ["🥇 OR", "🥈 ARGENT", "🥉 BRONZE"], ["podium-gold", "podium-silver", "podium-bronze"]
            for idx, (ex_n, row) in enumerate(podium.iterrows()):
                with p_cols[idx]: st.markdown(f"<div class='podium-card {clss[idx]}'><small>{meds[idx]}</small><br><b>{ex_n}</b><br><span style='color:#58CCFF; font-size:22px;'>{row['1RM']:.1f}kg</span></div>", unsafe_allow_html=True)
        
        st.divider(); sel = st.selectbox("🎯 Zoom mouvement :", sorted(df_h["Exercice"].unique
