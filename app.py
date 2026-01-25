import streamlit as st
import pandas as pd
import json
import gspread

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Muscu Tracker PRO", layout="centered", page_icon="logo.png")

# Initialisation du mode édition pour éviter le double affichage
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
    """Applique le code couleur strict : Rouge si moins bien, Vert si mieux."""
    if hist_prev is None or hist_prev.empty: return ["", "", "", ""]
    prev_set = hist_prev[hist_prev["Série"] == row["Série"]]
    v = "background-color: rgba(46, 125, 50, 0.45); color: white;" 
    r = "background-color: rgba(198, 40, 40, 0.45); color: white;"
    colors = ["", "", "", ""] 
    
    if not prev_set.empty:
        pw, pr = float(prev_set.iloc[0]["Poids"]), int(prev_set.iloc[0]["Reps"])
        cw, cr = float(row["Poids"]), int(row["Reps"])
        
        if cw < pw:
            colors[1], colors[2] = r, r # Moins de poids -> Tout rouge
        elif cw > pw:
            colors[1], colors[2] = v, v # Plus de poids -> Tout vert
        elif cw == pw:
            if cr > pr: colors[1] = v # Plus de reps -> Reps vert
            elif cr < pr: colors[1] = r # Moins de reps -> Reps rouge
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
        if not data: return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
        df = pd.DataFrame(data)
        df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
        df["Reps"] = pd.to_numeric(df["Reps"], errors='coerce').fillna(0).astype(int)
        df["Semaine"] = pd.to_numeric(df["Semaine"], errors='coerce').fillna(1).astype(int)
        return df
    except: return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])

def save_hist(df):
    df_clean = df.copy().fillna("")
    ws_h.clear()
    ws_h.update([df_clean.columns.values.tolist()] + df_clean.values.tolist(), value_input_option='USER_ENTERED')

# --- CHARGEMENT DES DONNÉES ---
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

# --- TAB 1 : PROGRAMME (RÉORGANISATION RESTAURÉE) ---
with tab1:
    st.subheader("Configuration des séances")
    jours = list(prog.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"⚙️ {j}"):
            c_s1, c_s2, c_s3 = st.columns([1, 1, 1])
            if c_s1.button("⬆️", key=f"up_s_{j}") and idx_j > 0:
                jours[idx_j], jours[idx_j-1] = jours[idx_j-1], jours[idx_j]
                ws_p.update_acell('A1', json.dumps({k: prog[k] for k in jours})); st.rerun()
            if c_s2.button("⬇️", key=f"dw_s_{j}") and idx_j < len(jours)-1:
                jours[idx_j], jours[idx_j+1] = jours[idx_j+1], jours[idx_j]
                ws_p.update_acell('A1', json.dumps({k: prog[k] for k in jours})); st.rerun()
            if c_s3.button("🗑️", key=f"del_s_{j}"):
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
    nvs = st.text_input("➕ Créer une séance")
    if st.button("Valider la création") and nvs:
        prog[nvs] = []; ws_p.update_acell('A1', json.dumps(prog)); st.rerun()

# --- TAB 2 : MA SÉANCE (FIX DOUBLE AFFICHAGE & HISTO) ---
with tab2:
    if prog:
        choix_s = st.selectbox("Séance :", list(prog.keys()))
        s_act = st.number_input("Semaine actuelle", 1, 52, int(df_h["Semaine"].max() if not df_h.empty else 1))

        if st.button("🚫 Marquer SÉANCE LOUPÉE", use_container_width=True):
            sk_rows = [{"Semaine": s_act, "Séance": choix_s, "Exercice": e["name"], "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "Loupée ❌"} for e in prog[choix_s]]
            save_hist(pd.concat([df_h, pd.DataFrame(sk_rows)], ignore_index=True)); st.rerun()

        for i, ex_obj in enumerate(prog[choix_s]):
            exo, p_sets = ex_obj["name"], ex_obj["sets"]
            st.markdown(f"### 🔹 {exo}")
            
            with st.expander(f"Détails & Saisie : {exo}", expanded=True):
                # 1. HISTORIQUE FILTRÉ (Strictement < semaine actuelle & même séance)
                full_exo_h = df_h[(df_h["Exercice"] == exo) & (df_h["Séance"] == choix_s)]
                h_only = full_exo_h[full_exo_h["Semaine"] < s_act].sort_values("Semaine", ascending=False)
                last_s_unique = h_only["Semaine"].unique()[:2]

                if len(last_s_unique) > 0:
                    st.caption("🔍 Historique (2 séances précédentes) :")
                    for sp in last_s_unique:
                        st.write(f"**Semaine {sp}**")
                        st.dataframe(h_only[h_only["Semaine"] == sp][["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)

                # 2. GESTION DU DOUBLE AFFICHAGE (MUTUELLEMENT EXCLUSIF)
                curr = full_exo_h[full_exo_h["Semaine"] == s_act]
                h_prev = h_only[h_only["Semaine"] == last_s_unique[0]] if len(last_s_unique) > 0 else pd.DataFrame()

                # Si déjà validé et PAS en train de modifier -> Affiche seulement le résumé coloré
                if not curr.empty and exo not in st.session_state.editing_exo:
                    st.caption("📈 Progression pour cette séance :")
                    st.dataframe(
                        curr[["Série", "Reps", "Poids", "Remarque"]]
                        .style.apply(style_comparaison, axis=1, hist_prev=h_prev)
                        .format({"Poids": "{:g}"}),
                        hide_index=True, use_container_width=True
                    )
                    if st.button(f"🔄 Modifier {exo}", key=f"mod_{exo}"):
                        st.session_state.editing_exo.add(exo); st.rerun()
                
                # Sinon -> Affiche l'éditeur
                else:
                    df_ed = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                    if not curr.empty:
                        for _, r in curr.iterrows():
                            if r["Série"] <= p_sets: df_ed.loc[df_ed["Série"] == r["Série"], ["Reps", "Poids", "Remarque"]] = [r["Reps"], r["Poids"], r["Remarque"]]
                    
                    ed = st.data_editor(df_ed, num_rows="fixed", key=f"ed_{exo}_{s_act}_{choix_s}", use_container_width=True,
                                        column_config={"Série": st.column_config.NumberColumn(disabled=True), "Poids": st.column_config.NumberColumn(format="%g")})
                    
                    c_v, c_sk = st.columns(2)
                    if c_v.button(f"✅ Valider {exo}", key=f"v_{exo}"):
                        v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                        v["Semaine"], v["Séance"], v["Exercice"] = s_act, choix_s, exo
                        mask = (df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo) & (df_h["Séance"] == choix_s)
                        save_hist(pd.concat([df_h[~mask], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo); st.rerun()
                    
                    if c_sk.button(f"🚫 Skip Exo", key=f"sk_{exo}"):
                        sk = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": exo, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫"}])
                        save_hist(pd.concat([df_h, sk], ignore_index=True)); st.rerun()

# --- TAB 3 : PROGRÈS (FIX BODYWEIGHT) ---
with tab3:
    if not df_h.empty:
        col1, col2 = st.columns(2)
        col1.metric("Volume Total", f"{int((df_h['Poids'] * df_h['Reps']).sum())} kg")
        col2.metric("Semaine Max", int(df_h["Semaine"].max()))
        
        st.subheader("🏆 Podium de Force")
        # Fix : On accepte Reps > 0 même si Poids = 0 pour les Dips/Tractions
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
            st.line_chart(df_rec.groupby("Semaine")["Poids"].max())
        st.dataframe(df_e[["Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values("Semaine", ascending=False), hide_index=True)
