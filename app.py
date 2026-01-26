
import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Muscu Tracker PRO", layout="centered", page_icon="logo.png")

if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()

# --- 2. CSS : DESIGN CYBER-MODERNE (CRÉATIVITÉ MAX) ---
st.markdown("""
<style>
    /* FOND DYNAMIQUE */
    .stApp {
        background: radial-gradient(circle at 50% 0%, rgba(10, 50, 100, 0.4) 0%, transparent 50%),
                    linear-gradient(180deg, #050A18 0%, #000000 100%);
        background-attachment: fixed;
        color: #F0F2F6;
    }
    
    /* GLASSMORPHISM SUR LES BLOCS */
    .stExpander {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(74, 144, 226, 0.3) !important;
        border-radius: 15px !important;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
        margin-bottom: 15px;
    }
    
    /* EFFET NÉON SUR LES TITRES & METRICS */
    div[data-testid="stMetricValue"] { 
        font-family: 'Courier New', monospace;
        font-size: 38px !important; color: #58CCFF !important; font-weight: 900; 
        text-shadow: 0 0 20px rgba(88, 204, 255, 0.6) !important; 
    }
    
    h1, h2, h3 {
        letter-spacing: 1px;
        text-transform: uppercase;
        color: #FFFFFF;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
    }

    /* BOUTONS STYLISÉS */
    .stButton>button {
        border-radius: 8px !important;
        border: 1px solid rgba(74, 144, 226, 0.4) !important;
        background: rgba(10, 25, 50, 0.6) !important;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        border-color: #58CCFF !important;
        box-shadow: 0 0 10px rgba(88, 204, 255, 0.4);
        transform: translateY(-2px);
    }
    
    /* PODIUM CARDS */
    .podium-gold { border-top: 4px solid #FFD700 !important; background: rgba(255, 215, 0, 0.05) !important; }
    .podium-silver { border-top: 4px solid #C0C0C0 !important; background: rgba(192, 192, 192, 0.05) !important; }
    .podium-bronze { border-top: 4px solid #CD7F32 !important; background: rgba(205, 127, 50, 0.05) !important; }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    if reps <= 0: return 0
    return weight * (1 + reps / 30)

def style_comparaison(row, hist_prev):
    if hist_prev is None or hist_prev.empty: return ["", "", "", ""]
    prev_set = hist_prev[hist_prev["Série"] == row["Série"]]
    # Couleurs plus vibrantes pour le design
    v = "background-color: rgba(0, 255, 127, 0.25); color: #00FF7F; border-left: 3px solid #00FF7F;" 
    r = "background-color: rgba(255, 69, 58, 0.25); color: #FF453A; border-left: 3px solid #FF453A;"
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
        df["Semaine"] = pd.to_numeric(df["Semaine"], errors='coerce').fillna(1).astype(int)
        df["Cycle"] = pd.to_numeric(df["Cycle"], errors='coerce').fillna(1).astype(int)
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

# Logo centré
col_l1, col_l2, col_l3 = st.columns([1, 1.8, 1])
with col_l2: st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 PROGRAMME", "🏋️‍♂️ MA SÉANCE", "📈 PROGRÈS"])

# --- TAB 1 : PROGRAMME ---
with tab1:
    st.markdown("## ⚙️ Configuration du programme")
    jours = list(prog.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"📦 {j}"):
            c_s1, c_s2, c_s3 = st.columns([1, 1, 2])
            if c_s1.button("⬆️ Monter", key=f"up_s_{j}") and idx_j > 0:
                jours[idx_j], jours[idx_j-1] = jours[idx_j-1], jours[idx_j]
                save_prog({k: prog[k] for k in jours}); st.rerun()
            if c_s2.button("⬇️ Descendre", key=f"dw_s_{j}") and idx_j < len(jours)-1:
                jours[idx_j], jours[idx_j+1] = jours[idx_j+1], jours[idx_j]
                save_prog({k: prog[k] for k in jours}); st.rerun()
            if c_s3.button("🗑️ Supprimer Séance", key=f"del_s_{j}"):
                del prog[j]; save_prog(prog); st.rerun()
            
            st.divider()
            for i, ex_obj in enumerate(prog[j]):
                name = ex_obj["name"]; nb_sets = ex_obj["sets"]
                c1, c2, c3, c4, c5 = st.columns([4, 2, 0.8, 0.8, 0.8])
                c1.write(f"**{name}**")
                new_s = c2.number_input("Sets", 1, 15, nb_sets, key=f"p_s_{j}_{i}")
                if new_s != nb_sets:
                    prog[j][i]["sets"] = new_s
                    save_prog(prog); st.rerun()
                if c3.button("⬆️", key=f"ue_{j}_{i}"):
                    if i > 0: prog[j][i], prog[j][i-1] = prog[j][i-1], prog[j][i]; save_prog(prog); st.rerun()
                if c4.button("⬇️", key=f"de_{j}_{i}"):
                    if i < len(prog[j])-1: prog[j][i], prog[j][i+1] = prog[j][i+1], prog[j][i]; save_prog(prog); st.rerun()
                if c5.button("🗑️", key=f"rm_{j}_{i}"):
                    prog[j].pop(i); save_prog(prog); st.rerun()
            
            st.markdown("---")
            cx, cs = st.columns([3, 1])
            ni = cx.text_input("Nouvel exercice", key=f"ni_{j}", placeholder="Ex: Développé couché")
            ns = cs.number_input("Séries", 1, 15, 3, key=f"ns_{j}")
            if st.button("➕ Ajouter l'exercice", key=f"ba_{j}") and ni:
                prog[j].append({"name": ni, "sets": ns}); save_prog(prog); st.rerun()
    
    st.markdown("### 🆕 Nouvelle Session")
    nvs = st.text_input("Nom de la séance (ex: Pull 2)")
    if st.button("🎯 Créer la séance") and nvs:
        prog[nvs] = []; save_prog(prog); st.rerun()

# --- TAB 2 : MA SÉANCE ---
with tab2:
    if not prog: st.warning("Crée une séance dans l'onglet programme.")
    else:
        # HEADER DE SÉANCE
        st.markdown("## ⚡ Session d'entraînement")
        c_header1, c_header2, c_header3 = st.columns([2, 1, 1])
        choix_s = c_header1.selectbox("Séance du jour :", list(prog.keys()))
        cycle_act = c_header2.number_input("Cycle", 1, 100, int(df_h["Cycle"].max() if not df_h.empty else 1))
        sem_in = c_header3.number_input("Semaine", 1, 10, 1)
        sem_stk = 0 if sem_in == 10 else sem_in

        if st.button("🚫 SÉANCE LOUPÉE (RESET TOUT)", use_container_width=True):
            sk_rows = [{"Cycle": cycle_act, "Semaine": sem_stk, "Séance": choix_s, "Exercice": e["name"], "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "Loupée ❌"} for e in prog[choix_s]]
            save_hist(pd.concat([df_h, pd.DataFrame(sk_rows)], ignore_index=True)); st.rerun()

        st.markdown("---")

        for i, ex_obj in enumerate(prog[choix_s]):
            exo_base, p_sets = ex_obj["name"], ex_obj["sets"]
            
            # CARD STYLE
            with st.expander(f"🔹 {exo_base.upper()}", expanded=True):
                c_v1, c_v2 = st.columns([2, 1])
                var = c_v1.selectbox("Matériel :", ["Standard", "Barre", "Haltères", "Poulie", "Machine", "Lesté"], key=f"v_{exo_base}_{i}")
                exo_final = f"{exo_base} ({var})" if var != "Standard" else exo_base
                
                # HISTORIQUE SÉCURISÉ
                f_h = df_h[(df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s)]
                cond_hist = (f_h["Cycle"] < cycle_act) | ((f_h["Cycle"] == cycle_act) & (f_h["Semaine"] < sem_stk))
                h_only = f_h[cond_hist].sort_values(["Cycle", "Semaine"], ascending=False)
                last_s = h_only[["Cycle", "Semaine"]].drop_duplicates().head(2)

                if not last_s.empty:
                    st.caption("🔍 Analyse des dernières séances :")
                    df_h_disp = pd.concat([h_only[(h_only["Cycle"] == r["Cycle"]) & (h_only["Semaine"] == r["Semaine"])] for _, r in last_s.iterrows()])
                    st.dataframe(df_h_disp[["Cycle", "Semaine", "Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)

                # DOUBLE AFFICHAGE FIX
                curr = f_h[(f_h["Semaine"] == sem_stk) & (f_h["Cycle"] == cycle_act)]
                h_prev = h_only[(h_only["Cycle"] == last_s.iloc[0]["Cycle"]) & (h_only["Semaine"] == last_s.iloc[0]["Semaine"])] if not last_s.empty else pd.DataFrame()

                if not curr.empty and exo_final not in st.session_state.editing_exo:
                    st.markdown("##### ✅ Validé pour cette séance")
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.apply(style_comparaison, axis=1, hist_prev=h_prev).format({"Poids": "{:g}"}), hide_index=True, use_container_width=True)
                    if st.button(f"🔄 Modifier", key=f"m_{exo_final}_{i}"):
                        st.session_state.editing_exo.add(exo_final); st.rerun()
                else:
                    df_fixed = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                    if not curr.empty:
                        for _, row in curr.iterrows():
                            if row["Série"] <= p_sets: df_fixed.loc[df_fixed["Série"] == row["Série"], ["Reps", "Poids", "Remarque"]] = [row["Reps"], row["Poids"], row["Remarque"]]

                    ed = st.data_editor(df_fixed, num_rows="fixed", key=f"ed_{exo_final}_{sem_stk}", use_container_width=True, 
                                        column_config={"Série": st.column_config.NumberColumn(disabled=True), "Poids": st.column_config.NumberColumn(format="%g")})
                    
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.button(f"💾 Valider l'exercice", key=f"sv_{exo_final}"):
                        v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                        v["Cycle"], v["Semaine"], v["Séance"], v["Exercice"] = cycle_act, sem_stk, choix_s, exo_final
                        mask = (df_h["Semaine"] == sem_stk) & (df_h["Cycle"] == cycle_act) & (df_h["Séance"] == choix_s) & (df_h["Exercice"] == exo_final)
                        save_hist(pd.concat([df_h[~mask], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo_final)
                        st.toast(f"Mouvement enregistré : {exo_base}", icon='💪')
                        st.rerun()
                    
                    if c_btn2.button(f"⏩ Skip Exo", key=f"sk_{exo_final}"):
                        sk = pd.DataFrame([{"Cycle": cycle_act, "Semaine": sem_stk, "Séance": choix_s, "Exercice": exo_final, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫"}])
                        save_hist(pd.concat([df_h, sk], ignore_index=True)); st.rerun()

# --- TAB 3 : PROGRÈS ---
with tab3:
    if not df_h.empty:
        # GLOW METRICS
        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("VOL. TOTAL", f"{int((df_h['Poids'] * df_h['Reps']).sum()):,} kg".replace(',', ' '))
        c_m2.metric("CYCLE", int(df_h["Cycle"].max()))
        c_m3.metric("SEMAINE", int(df_h["Semaine"].max()))
        
        st.markdown("### 🏅 Hall of Fame (Force Pure)")
        df_p = df_h[df_h["Reps"] > 0].copy()
        df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        podium = df_p.groupby("Exercice").agg({"1RM": "max", "Poids": "max", "Reps": "max"}).sort_values(by="1RM", ascending=False).head(3)
        
        p_cols = st.columns(3)
        medals = ["🥇 OR", "🥈 ARGENT", "🥉 BRONZE"]
        classes = ["podium-gold", "podium-silver", "podium-bronze"]
        for idx, (ex_n, row) in enumerate(podium.iterrows()):
            with p_cols[idx]:
                st.markdown(f"""<div class='podium-card {classes[idx]}'>
                    <small style='color:white;'>{medals[idx]}</small><br>
                    <b style='font-size:16px;'>{ex_n}</b><br>
                    <span style='color:#58CCFF; font-size:22px; font-weight:bold;'>{row['1RM']:.1f} kg</span><br>
                    <small>Détail: {row['Poids']:.1f}kg x {int(row['Reps'])}</small>
                </div>""", unsafe_allow_html=True)

        st.divider()
        sel = st.selectbox("🎯 Zoom sur un mouvement :", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel].copy()
        df_rec = df_e[(df_e["Poids"] > 0) | (df_e["Reps"] > 0)].copy()
        
        if not df_rec.empty:
            best = df_rec.sort_values(["Poids", "Reps"], ascending=False).iloc[0]
            c_res1, c_res2 = st.columns(2)
            c_res1.success(f"🏆 RECORD : **{best['Poids']} kg x {int(best['Reps'])}**")
            c_res2.info(f"⚡ 1RM : **{calc_1rm(best['Poids'], best['Reps']):.1f} kg**")
            
            # Graphique avec couleur personnalisée
            chart_data = df_rec.groupby(["Cycle", "Semaine"])["Poids"].max().reset_index()
            chart_data["Point"] = "C" + chart_data["Cycle"].astype(str) + "-S" + chart_data["Semaine"].astype(str)
            st.line_chart(chart_data.set_index("Point")["Poids"])
        
        st.markdown("##### 📝 Historique Complet")
        st.dataframe(df_e[["Cycle", "Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Cycle", "Semaine"], ascending=False), hide_index=True, use_container_width=True)
