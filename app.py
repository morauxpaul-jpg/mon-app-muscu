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

# --- 2. CSS : DESIGN CYBER-RPG COMPLET ---
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
    
    /* SYSTÈME DE RANGS JEU VIDÉO */
    .rank-ladder {
        display: flex; justify-content: space-between; align-items: center;
        background: rgba(255,255,255,0.05); padding: 20px; border-radius: 15px;
        border: 1px solid #58CCFF; margin-bottom: 30px; position: relative;
    }
    .rank-step { text-align: center; flex: 1; opacity: 0.5; font-size: 10px; transition: 0.3s; }
    .rank-step.active { opacity: 1; font-weight: bold; transform: scale(1.1); color: #58CCFF; }
    .rank-step.completed { color: #00FF7F; opacity: 0.8; }
    .xp-container { width: 100%; margin: 10px 0; }
    .xp-bar-bg { width: 100%; background: rgba(255,255,255,0.1); border-radius: 10px; height: 12px; overflow: hidden; border: 1px solid rgba(88, 204, 255, 0.3); }
    .xp-bar-fill { height: 100%; background: linear-gradient(90deg, #58CCFF, #00FF7F); box-shadow: 0 0 15px #58CCFF; }

    /* VOLUME BAR */
    .vol-container { background: rgba(255,255,255,0.05); border-radius: 10px; padding: 12px; margin-top: 10px; border: 1px solid rgba(88, 204, 255, 0.3); }
    .vol-bar-bg { width: 100%; background: rgba(255,255,255,0.1); border-radius: 6px; height: 14px; overflow: hidden; margin-top: 8px; }
    .vol-bar-fill { height: 100%; border-radius: 6px; background: #58CCFF; transition: width 0.8s ease-in-out; }
    .vol-overload { background: #00FF7F !important; box-shadow: 0 0 20px #00FF7F !important; }

    /* PODIUM COULEURS */
    .podium-card { background: rgba(255, 255, 255, 0.07); border-radius: 12px; padding: 15px; text-align: center; margin-bottom: 10px; border-top: 4px solid #58CCFF; }
    .podium-gold { border-color: #FFD700 !important; box-shadow: 0 0 15px rgba(255, 215, 0, 0.2); }
    .podium-silver { border-color: #C0C0C0 !important; box-shadow: 0 0 15px rgba(192, 192, 192, 0.2); }
    .podium-bronze { border-color: #CD7F32 !important; box-shadow: 0 0 15px rgba(205, 127, 50, 0.2); }
    
    .cyber-analysis { background: rgba(88, 204, 255, 0.05); border-left: 4px solid #58CCFF; padding: 15px; border-radius: 0 10px 10px 0; margin-bottom: 20px; font-size: 0.95rem; }
</style>
""", unsafe_allow_html=True)

# --- 3. FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    return weight * (1 + reps / 30) if reps > 0 else 0

def get_rep_estimations(one_rm):
    """Calcule le poids estimé pour différents nombres de répétitions."""
    return {r: round(one_rm * pct, 1) for r, pct in {1: 1.0, 3: 0.94, 5: 0.89, 8: 0.81, 10: 0.75, 12: 0.71}.items()}

def get_base_name(full_name):
    return full_name.split("(")[0].strip() if "(" in full_name else full_name

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

# --- 4. CONNEXION ---
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

def save_prog(prog_dict):
    ws_p.update_acell('A1', json.dumps(prog_dict))

df_h = get_hist()
prog_raw = ws_p.acell('A1').value if ws_p else "{}"
try:
    prog = json.loads(prog_raw)
    for s in prog:
        for exo in prog[s]:
            if "muscle" not in exo: exo["muscle"] = "Autre"
except: prog = {}

muscle_mapping = {ex["name"]: ex.get("muscle", "Autre") for s in prog for ex in prog[s]}
df_h["Muscle"] = df_h["Exercice"].apply(get_base_name).map(muscle_mapping).fillna(df_h["Muscle"]).replace("", "Autre")

col_logo1, col_logo2, col_logo3 = st.columns([1, 1.8, 1])
with col_logo2: st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 PROGRAMME", "🏋️‍♂️ MA SÉANCE", "📈 PROGRÈS"])

# --- TAB 1 : PROGRAMME ---
with tab1:
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
                ex['sets'] = c2.number_input("Sets", 1, 15, ex.get('sets', 3), key=f"p_s_{j}_{i}")
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
    nvs = st.text_input("➕ Créer séance")
    if st.button("🎯 Valider") and nvs: prog[nvs] = []; save_prog(prog); st.rerun()

# --- TAB 2 : MA SÉANCE ---
with tab2:
    if prog:
        c_h1, c_h2 = st.columns([3, 1])
        choix_s = c_h1.selectbox("Séance :", list(prog.keys()))
        s_act = c_h2.number_input("Semaine", 1, 52, int(df_h["Semaine"].max() if not df_h.empty else 1))
        
        vol_curr = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Reps"]).sum()
        vol_prev = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Reps"]).sum()
        if vol_prev > 0:
            ratio = min(vol_curr / vol_prev, 1.0)
            st.markdown(f"""<div class='vol-container'><small>⚡ Volume : <b>{int(vol_curr)} / {int(vol_prev)} kg</b></small><div class='vol-bar-bg'><div class='vol-bar-fill {"vol-overload" if vol_curr >= vol_prev else ""}' style='width: {ratio*100}%;'></div></div></div>""", unsafe_allow_html=True)

        for i, ex_obj in enumerate(prog[choix_s]):
            exo_base, p_sets, muscle_grp = ex_obj["name"], ex_obj.get("sets", 3), ex_obj.get("muscle", "Autre")
            with st.expander(f"🔹 {exo_base.upper()}", expanded=True):
                var = st.selectbox("Équipement :", ["Standard", "Barre", "Haltères", "Banc", "Poulie", "Machine", "Lesté"], key=f"v_{exo_base}_{i}")
                exo_final = f"{exo_base} ({var})" if var != "Standard" else exo_base
                f_h = df_h[(df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s)]
                
                # HISTORIQUE VERTICAL STRICT
                if s_act > 1:
                    if s_act > 2:
                        h2 = f_h[f_h["Semaine"] == s_act - 2]
                        if not h2.empty:
                            st.caption("📅 Semaine S-2")
                            st.dataframe(h2[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                    h1 = f_h[f_h["Semaine"] == s_act - 1]
                    if not h1.empty:
                        st.caption("📅 Semaine S-1")
                        st.dataframe(h1[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                else:
                    st.info("Semaine 1 : Établissez vos marques !")

                curr = f_h[f_h["Semaine"] == s_act]
                h_prev = f_h[f_h["Semaine"] == s_act - 1] if s_act > 1 else pd.DataFrame()

                if not curr.empty and exo_final not in st.session_state.editing_exo:
                    st.markdown("##### ✅ Validé")
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.apply(style_comparaison, axis=1, hist_prev=h_prev).format({"Poids": "{:g}"}), hide_index=True, use_container_width=True)
                    if st.button(f"🔄 Modifier {exo_base}", key=f"m_{exo_final}_{i}"): st.session_state.editing_exo.add(exo_final); st.rerun()
                else:
                    df_ed = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                    if not curr.empty:
                        for _, r in curr.iterrows():
                            if r["Série"] <= p_sets: df_ed.loc[df_ed["Série"] == r["Série"], ["Reps", "Poids", "Remarque"]] = [r["Reps"], r["Poids"], r["Remarque"]]
                    ed = st.data_editor(df_ed, num_rows="fixed", key=f"ed_{exo_final}_{s_act}", use_container_width=True, column_config={"Série": st.column_config.NumberColumn(disabled=True), "Poids": st.column_config.NumberColumn(format="%g")})
                    
                    c_v, c_sk = st.columns(2)
                    if c_v.button(f"💾 Enregistrer", key=f"sv_{exo_final}"):
                        v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                        v["Semaine"], v["Séance"], v["Exercice"], v["Muscle"], v["Date"] = s_act, choix_s, exo_final, muscle_grp, datetime.now().strftime("%Y-%m-%d")
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s))], v], ignore_index=True))
                        if not v.empty and not h_prev.empty:
                            if max(v.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)) > max(h_prev.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)):
                                st.balloons()
                        st.session_state.editing_exo.discard(exo_final); st.rerun()
                    if c_sk.button(f"⏩ Skip Exo", key=f"sk_{exo_final}"):
                        sk = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": exo_final, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫", "Muscle": muscle_grp, "Date": datetime.now().strftime("%Y-%m-%d")}])
                        save_hist(pd.concat([df_h, sk], ignore_index=True)); st.rerun()

# --- TAB 3 : PROGRÈS ---
with tab3:
    if not df_h.empty:
        # LOGIQUE XP & RANKS
        v_tot = int((df_h['Poids'] * df_h['Reps']).sum())
        paliers = [0, 5000, 25000, 75000, 200000, 500000]
        noms = ["RECRUE NÉON", "CYBER-SOLDAT", "ÉLITE DE CHROME", "TITAN D'ACIER", "LÉGENDE CYBER", "DIEU DU FER"]
        idx = next((i for i, p in enumerate(paliers[::-1]) if v_tot >= p), 0)
        idx = len(paliers) - 1 - idx
        prev_r, curr_r, next_r = (noms[idx-1] if idx > 0 else "DÉBUT"), noms[idx], (noms[idx+1] if idx < len(noms)-1 else "MAX")
        next_p = paliers[idx+1] if idx < len(paliers)-1 else paliers[-1]
        xp_ratio = min((v_tot - paliers[idx]) / (next_p - paliers[idx]), 1.0) if next_p > paliers[idx] else 1.0
        
        st.markdown(f"""
        <div style='text-align: center; margin-bottom: 5px;'><small style='color:#58CCFF;'>Séquence de Carrière</small></div>
        <div class='rank-ladder'>
            <div class='rank-step completed'><small>PASSÉ</small><br>{prev_r}</div>
            <div style='font-size: 20px; color: #58CCFF;'>➡️</div>
            <div class='rank-step active'><small>ACTUEL</small><br><span style='font-size:18px;'>{curr_r}</span></div>
            <div style='font-size: 20px; color: #58CCFF;'>➡️</div>
            <div class='rank-step'><small>PROCHAIN</small><br>{next_r}</div>
        </div>
        <div class='xp-container'>
            <div class='xp-bar-bg'><div class='xp-bar-fill' style='width:{xp_ratio*100}%;'></div></div>
            <div style='display:flex; justify-content: space-between;'>
                <small style='color:#00FF7F;'>{v_tot:,} kg</small>
                <small style='color:#58CCFF;'>Objectif : {next_p:,} kg</small>
            </div>
        </div>
        """.replace(',', ' '), unsafe_allow_html=True)

        st.markdown("### 🕸️ Radar d'Équilibre Cyber")
        standards = {"Jambes": 150, "Dos": 120, "Pecs": 100, "Épaules": 75, "Bras": 50, "Abdos": 40}
        df_p = df_h[df_h["Reps"] > 0].copy()
        df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        scores, labels = [], list(standards.keys())
        for m in labels:
            m_max = df_p[df_p["Muscle"] == m]["1RM"].max() if not df_p[df_p["Muscle"] == m].empty else 0
            scores.append(min((m_max / standards[m]) * 100, 110))
        
        fig_r = go.Figure(data=go.Scatterpolar(r=scores + [scores[0]], theta=labels + [labels[0]], fill='toself', line=dict(color='#58CCFF', width=3), fillcolor='rgba(88, 204, 255, 0.2)'))
        fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 110], showticklabels=False, gridcolor="rgba(255,255,255,0.1)"), angularaxis=dict(color="white")), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=40, r=40, t=20, b=20), height=350)
        st.plotly_chart(fig_r, use_container_width=True, config={'displayModeBar': False})

        # --- ANALYSE DYNAMIQUE ---
        if any(s > 0 for s in scores):
            top_m = labels[scores.index(max(scores))]
            # Trouver le vrai point faible (hors jambes à 0)
            valid_scores = [(s, labels[idx]) for idx, s in enumerate(scores) if s > 0 and labels[idx] != "Jambes"]
            
            if valid_scores:
                min_val, low_m = min(valid_scores, key=lambda x: x[0])
                gap = max(scores) - min_val
                lvl = "Faible" if gap < 15 else ("Moyen" if gap < 30 else "Élevé")
                msg = f"🛡️ Analyseur de Profil : Ton profil est dominé par tes {top_m}. Ton vrai point faible actuel se situe au niveau de tes {low_m}. Le déséquilibre global est jugé {lvl}."
            else:
                msg = f"🛡️ Analyseur de Profil : Ton profil est dominé par tes {top_m}."
            
            if scores[labels.index("Jambes")] == 0:
                msg += " Il faudra penser à les travailler un jour..."
            st.markdown(f"<div class='cyber-analysis'>{msg}</div>", unsafe_allow_html=True)

        c1, c2 = st.columns(2); c1.metric("VOL. TOTAL", f"{v_tot:,} kg".replace(',', ' ')); c2.metric("SEMAINE MAX", int(df_h["Semaine"].max()))
        
        # PODIUM HALL OF FAME (Restauration Couleurs)
        st.markdown("### 🏅 Hall of Fame")
        m_filt = st.multiselect("Filtrer par muscle :", labels + ["Autre"], default=labels + ["Autre"])
        df_p_filt = df_p[df_p["Muscle"].isin(m_filt)]
        if not df_p_filt.empty:
            podium = df_p_filt.groupby("Exercice").agg({"1RM": "max"}).sort_values(by="1RM", ascending=False).head(3)
            p_cols = st.columns(3); meds, clss = ["🥇 OR", "🥈 ARGENT", "🥉 BRONZE"], ["podium-gold", "podium-silver", "podium-bronze"]
            for idx, (ex_n, row) in enumerate(podium.iterrows()):
                with p_cols[idx]: st.markdown(f"<div class='podium-card {clss[idx]}'><small>{meds[idx]}</small><br><b>{ex_n}</b><br><span style='color:#58CCFF; font-size:22px;'>{row['1RM']:.1f}kg</span></div>", unsafe_allow_html=True)
        
        # ZOOM MOUVEMENT (Restauration Estimations)
        st.divider()
        sel_e = st.selectbox("🎯 Zoom mouvement :", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel_e].copy(); df_rec = df_e[(df_e["Poids"] > 0) | (df_e["Reps"] > 0)].copy()
        if not df_rec.empty:
            best = df_rec.sort_values(["Poids", "Reps"], ascending=False).iloc[0]; one_rm = calc_1rm(best['Poids'], best['Reps'])
            c1r, c2r = st.columns(2); c1r.success(f"🏆 RECORD RÉEL\n\n**{best['Poids']}kg x {int(best['Reps'])}**"); c2r.info(f"⚡ 1RM ESTIMÉ\n\n**{one_rm:.1f} kg**")
            
            with st.expander("📊 Estimation Rep Max (Charges de travail)"):
                ests = get_rep_estimations(one_rm); cols = st.columns(len(ests))
                for idx, (r, p) in enumerate(ests.items()): cols[idx].metric(f"{r} Reps", f"{p}kg")
                
            fig_l = go.Figure(); c_dat = df_rec.groupby("Semaine")["Poids"].max().reset_index()
            fig_l.add_trace(go.Scatter(x=c_dat["Semaine"], y=c_dat["Poids"], mode='lines+markers', line=dict(color='#58CCFF', width=3), marker=dict(size=10, color='#00FF7F')))
            fig_l.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=10, b=0), height=300)
            st.plotly_chart(fig_l, use_container_width=True, config={'displayModeBar': False})
        st.dataframe(df_e[["Semaine", "Série", "Reps", "Poids", "Remarque", "Muscle"]].sort_values("Semaine", ascending=False), hide_index=True)
