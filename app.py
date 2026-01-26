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
        text-shadow: 0 0 15px rgba(74, 144, 226, 0.8), 0 0 5px rgba(74, 144, 226, 0.5) !important; 
    }
    .stExpander { background-color: rgba(10, 25, 49, 0.6) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 10px; backdrop-filter: blur(5px); }
    .podium-card { background: rgba(255, 255, 255, 0.07); border-radius: 12px; padding: 15px; border-top: 3px solid #4A90E2; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    if reps <= 0: return 0
    return weight * (1 + reps / 30)

def style_comparaison(row, hist_prev):
    if hist_prev is None or hist_prev.empty: return ["", "", "", ""]
    prev_set = hist_prev[hist_prev["Série"] == row["Série"]]
    v, r = "background-color: rgba(46, 125, 50, 0.45); color: white;", "background-color: rgba(198, 40, 40, 0.45); color: white;"
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
    ws_h.update([df_clean.columns.values.tolist()] + df_clean.values.tolist(), value_input_option='USER_ENTERED')

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

# --- TAB 1 : PROGRAMME (RÉORGANISATION SÉANCES) ---
with tab1:
    st.subheader("Configuration des séances")
    jours = list(prog.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"⚙️ {j}"):
            c_s1, c_s2, c_s3 = st.columns([1, 1, 2])
            if c_s1.button("⬆️ Monter", key=f"up_session_{j}") and idx_j > 0:
                jours[idx_j], jours[idx_j-1] = jours[idx_j-1], jours[idx_j]
                save_prog({k: prog[k] for k in jours}); st.rerun()
            if c_s2.button("⬇️ Descendre", key=f"dw_session_{j}") and idx_j < len(jours)-1:
                jours[idx_j], jours[idx_j+1] = jours[idx_j+1], jours[idx_j]
                save_prog({k: prog[k] for k in jours}); st.rerun()
            if c_s3.button("🗑️ Supprimer Séance", key=f"del_session_{j}"):
                del prog[j]; save_prog(prog); st.rerun()
            
            st.divider()
            for i, ex_obj in enumerate(prog[j]):
                name = ex_obj["name"]; nb_sets = ex_obj["sets"]
                c1, c2, c3, c4, c5 = st.columns([4, 2, 1, 1, 1])
                c1.write(f"**{name}**")
                new_s = c2.number_input("Séries", 1, 15, nb_sets, key=f"s_{j}_{i}")
                if new_s != nb_sets:
                    prog[j][i]["sets"] = new_s
                    save_prog(prog); st.rerun()
                if c3.button("⬆️", key=f"ue_{j}_{i}"):
                    if i > 0: prog[j][i], prog[j][i-1] = prog[j][i-1], prog[j][i]; save_prog(prog); st.rerun()
                if c4.button("⬇️", key=f"de_{j}_{i}"):
                    if i < len(prog[j])-1: prog[j][i], prog[j][i+1] = prog[j][i+1], prog[j][i]; save_prog(prog); st.rerun()
                if c5.button("🗑️", key=f"rm_{j}_{i}"):
                    prog[j].pop(i); save_prog(prog); st.rerun()
            ni = st.text_input("Ajouter exo", key=f"ni_{j}")
            ns = st.number_input("Sets", 1, 15, 3, key=f"ns_{j}")
            if st.button("Ajouter", key=f"ba_{j}") and ni:
                prog[j].append({"name": ni, "sets": ns}); save_prog(prog); st.rerun()
    nvs = st.text_input("➕ Créer séance")
    if st.button("Créer séance") and nvs:
        prog[nvs] = []; save_prog(prog); st.rerun()

# --- TAB 2 : MA SÉANCE (FIX DOUBLE AFFICHAGE & HISTO) ---
with tab2:
    if not prog: st.warning("Crée une séance dans le programme.")
    else:
        col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
        choix_s = col_s1.selectbox("Séance :", list(prog.keys()))
        cycle_act = col_s2.number_input("Cycle", 1, 100, int(df_h["Cycle"].max() if not df_h.empty else 1))
        sem_in = col_s3.number_input("Semaine", 1, 10, 1)
        sem_stk = 0 if sem_in == 10 else sem_in

        if st.button("🚫 Séance Loupée ❌", use_container_width=True):
            sk_rows = [{"Cycle": cycle_act, "Semaine": sem_stk, "Séance": choix_s, "Exercice": e["name"], "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "Loupée ❌"} for e in prog[choix_s]]
            save_hist(pd.concat([df_h, pd.DataFrame(sk_rows)], ignore_index=True)); st.rerun()

        for i, ex_obj in enumerate(prog[choix_s]):
            exo_base, p_sets = ex_obj["name"], ex_obj["sets"]
            st.markdown(f"### 🔹 {exo_base}")
            
            with st.expander(f"Saisie : {exo_base}", expanded=True):
                # VARIANTE (AVEC POULIE)
                var = st.selectbox("Équipement :", ["Standard", "Barre", "Haltères", "Poulie", "Machine", "Lesté"], key=f"var_{exo_base}_{i}")
                exo_final = f"{exo_base} ({var})" if var != "Standard" else exo_base

                # 1. HISTORIQUE 2 SEMAINES (GROUPÉ POUR N'AVOIR QU'UN SEUL TABLEAU)
                f_h = df_h[(df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s)]
                cond_hist = (f_h["Cycle"] < cycle_act) | ((f_h["Cycle"] == cycle_act) & (f_h["Semaine"] < sem_stk))
                h_only = f_h[cond_hist].sort_values(["Cycle", "Semaine"], ascending=False)
                last_s = h_only[["Cycle", "Semaine"]].drop_duplicates().head(2)

                if not last_s.empty:
                    st.caption(f"🔍 Historique pour la variante : **{var}**")
                    df_h_display = pd.concat([h_only[(h_only["Cycle"] == r["Cycle"]) & (h_only["Semaine"] == r["Semaine"])] for _, r in last_s.iterrows()])
                    st.dataframe(df_h_display[["Cycle", "Semaine", "Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)

                # 2. GESTION DU DOUBLE AFFICHAGE (MUTUELLEMENT EXCLUSIF)
                curr = f_h[(f_h["Semaine"] == sem_stk) & (f_h["Cycle"] == cycle_act)]
                h_prev = h_only[(h_only["Cycle"] == last_s.iloc[0]["Cycle"]) & (h_only["Semaine"] == last_s.iloc[0]["Semaine"])] if not last_s.empty else pd.DataFrame()

                if not curr.empty and exo_final not in st.session_state.editing_exo:
                    st.caption("✅ Validé pour cette séance (Couleurs comparées à S-1) :")
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.apply(style_comparaison, axis=1, hist_prev=h_prev).format({"Poids": "{:g}"}), hide_index=True, use_container_width=True)
                    if st.button(f"🔄 Modifier {exo_base}", key=f"mod_{exo_final}_{i}"):
                        st.session_state.editing_exo.add(exo_final); st.rerun()
                else:
                    df_fixed = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                    if not curr.empty:
                        for _, row in curr.iterrows():
                            if row["Série"] <= p_sets: df_fixed.loc[df_fixed["Série"] == row["Série"], ["Reps", "Poids", "Remarque"]] = [row["Reps"], row["Poids"], row["Remarque"]]

                    ed = st.data_editor(df_fixed, num_rows="fixed", key=f"ed_{exo_final}_{sem_stk}_{cycle_act}", use_container_width=True, 
                                        column_config={"Série": st.column_config.NumberColumn(disabled=True), "Poids": st.column_config.NumberColumn(format="%g")})
                    
                    c_v, c_sk = st.columns(2)
                    if c_v.button(f"✅ Valider {exo_base}", key=f"val_{exo_final}_{i}"):
                        v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                        v["Cycle"], v["Semaine"], v["Séance"], v["Exercice"] = cycle_act, sem_stk, choix_s, exo_final
                        mask = (df_h["Semaine"] == sem_stk) & (df_h["Cycle"] == cycle_act) & (df_h["Séance"] == choix_s) & (df_h["Exercice"] == exo_final)
                        save_hist(pd.concat([df_h[~mask], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo_final); st.rerun()
                    
                    if c_sk.button(f"🚫 Skip Exo", key=f"sk_{exo_final}_{i}"):
                        sk = pd.DataFrame([{"Cycle": cycle_act, "Semaine": sem_stk, "Séance": choix_s, "Exercice": exo_final, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫"}])
                        save_hist(pd.concat([df_h, sk], ignore_index=True)); st.rerun()

# --- TAB 3 : PROGRÈS ---
with tab3:
    if not df_h.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Volume Total", f"{int((df_h['Poids'] * df_h['Reps']).sum())} kg")
        col2.metric("Cycle Actuel", int(df_h["Cycle"].max()))
        col3.metric("Semaine Max", int(df_h["Semaine"].replace(0, 10).max()))
        
        st.divider()
        st.subheader("🏆 Podium de Force")
        df_p = df_h[df_h["Reps"] > 0].copy()
        df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        podium = df_p.groupby("Exercice").agg({"1RM": "max", "Poids": "max", "Reps": "max"}).sort_values(by="1RM", ascending=False).head(3)
        p_cols = st.columns(3)
        medals = ["🥇", "🥈", "🥉"]
        for idx, (ex_n, row) in enumerate(podium.iterrows()):
            with p_cols[idx]:
                st.markdown(f"<div class='podium-card'><b>{medals[idx]} {ex_n}</b><br><span style='color:#4A90E2; font-size:20px;'>{row['1RM']:.1f} kg</span><br><small>{row['Poids']:.1f}kg x {int(row['Reps'])}</small></div>", unsafe_allow_html=True)

        st.divider()
        sel = st.selectbox("Zoom sur un exercice :", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel].copy()
        df_rec = df_e[(df_e["Poids"] > 0) | (df_e["Reps"] > 0)].copy()
        if not df_rec.empty:
            best = df_rec.sort_values(["Poids", "Reps"], ascending=False).iloc[0]
            st.success(f"🏆 Record : **{best['Poids']} kg x {int(best['Reps'])}** (1RM: {calc_1rm(best['Poids'], best['Reps']):.1f} kg)")
            c_chart = df_rec.groupby(["Cycle", "Semaine"])["Poids"].max().reset_index()
            c_chart["Point"] = "C" + c_chart["Cycle"].astype(str) + "-S" + c_chart["Semaine"].astype(str)
            st.line_chart(c_chart.set_index("Point")["Poids"])
        st.dataframe(df_e[["Cycle", "Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Cycle", "Semaine"], ascending=False), hide_index=True)
