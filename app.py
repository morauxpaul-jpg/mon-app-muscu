import streamlit as st
import pandas as pd
import json
import gspread

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Muscu Tracker PRO", layout="centered", page_icon="logo.png")

# --- 2. CSS LOOK NÉON ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                    linear-gradient(180deg, #0A1931 0%, #000000 100%);
        background-attachment: fixed; background-size: cover;
        color: #E0E0E0;
    }
    div[data-testid="stMetricValue"] { color: #4A90E2 !important; text-shadow: 0 0 10px rgba(74, 144, 226, 0.8) !important; }
    .stExpander { background-color: rgba(10, 25, 49, 0.6) !important; border-radius: 10px; backdrop-filter: blur(5px); }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS ---
def calc_1rm(weight, reps):
    return weight * (1 + reps / 30) if reps > 0 else 0

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

# Init Data
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
    st.subheader("Configuration des séances")
    for j in list(prog.keys()):
        with st.expander(f"⚙️ {j}"):
            for i, ex in enumerate(prog[j]):
                c1, c2, c3 = st.columns([5, 2, 1])
                c1.write(f"**{ex['name']}**")
                ex['sets'] = c2.number_input("Séries", 1, 12, ex['sets'], key=f"s_{j}_{i}")
                if c3.button("🗑️", key=f"d_{j}_{i}"): 
                    prog[j].pop(i)
                    ws_p.update_acell('A1', json.dumps(prog))
                    st.rerun()
            
            c_add1, c_add2 = st.columns([3, 1])
            ni = c_add1.text_input("Nouvel exo", key=f"ni_{j}")
            ns = c_add2.number_input("Sets", 1, 12, 3, key=f"ns_{j}")
            if st.button("Ajouter l'exercice", key=f"ba_{j}") and ni:
                prog[j].append({"name": ni, "sets": ns})
                ws_p.update_acell('A1', json.dumps(prog))
                st.rerun()
    
    st.divider()
    nvs = st.text_input("➕ Créer une nouvelle séance")
    if st.button("Créer la séance") and nvs:
        prog[nvs] = []
        ws_p.update_acell('A1', json.dumps(prog))
        st.rerun()

# --- TAB 2 : MA SÉANCE (RETOUR AU FORMAT SIMPLE) ---
with tab2:
    if prog:
        choix_s = st.selectbox("Séance :", list(prog.keys()))
        col_c, col_s = st.columns(2)
        c_act = col_c.number_input("Cycle", 1, 100, int(df_h["Cycle"].max() if not df_h.empty else 1))
        s_act = col_s.number_input("Semaine", 1, 10, 1)

        for ex_obj in prog[choix_s]:
            exo, p_sets = ex_obj["name"], ex_obj["sets"]
            st.markdown(f"### 🔹 {exo}")
            
            with st.expander(f"Détails & Saisie : {exo}", expanded=True):
                # 1. HISTORIQUE (Exclure session actuelle, max 2 sessions passées)
                f_h = df_h[df_h["Exercice"] == exo]
                h_only = f_h[~((f_h["Cycle"] == c_act) & (f_h["Semaine"] == s_act))].sort_values(["Cycle", "Semaine"], ascending=False)
                last_sessions = h_only[["Cycle", "Semaine"]].drop_duplicates().head(2)

                if not last_sessions.empty:
                    st.caption("🔍 Historique (Dernières séances) :")
                    for _, r_s in last_sessions.iterrows():
                        cp, sp = r_s["Cycle"], r_s["Semaine"]
                        st.write(f"**Cycle {cp} - Semaine {sp}**")
                        st.dataframe(h_only[(h_only["Cycle"] == cp) & (h_only["Semaine"] == sp)][["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)

                # 2. SESSION EN COURS (L'ÉDITEUR UNIQUEMENT)
                curr = f_h[(f_h["Cycle"] == c_act) & (f_h["Semaine"] == s_act)]

                df_ed = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                if not curr.empty:
                    for _, r in curr.iterrows():
                        if r["Série"] <= p_sets: 
                            df_ed.loc[df_ed["Série"] == r["Série"], ["Reps", "Poids", "Remarque"]] = [r["Reps"], r["Poids"], r["Remarque"]]
                
                ed = st.data_editor(df_ed, num_rows="fixed", key=f"ed_{exo}_{s_act}_{c_act}", use_container_width=True,
                                    column_config={"Série": st.column_config.NumberColumn(disabled=True), "Poids": st.column_config.NumberColumn(format="%g")})
                
                if st.button(f"✅ Valider {exo}", key=f"val_{exo}"):
                    v = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                    v["Cycle"], v["Semaine"], v["Séance"], v["Exercice"] = c_act, s_act, choix_s, exo
                    # Nettoyer l'existant avant de sauver
                    mask = (df_h["Cycle"] == c_act) & (df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo)
                    save_hist(pd.concat([df_h[~mask], v], ignore_index=True))
                    st.rerun()

# --- TAB 3 : PROGRÈS (FIX CORPS DE POIDS) ---
with tab3:
    if not df_h.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Volume Total", f"{int((df_h['Poids'] * df_h['Reps']).sum())} kg")
        col2.metric("Cycle Actuel", int(df_h["Cycle"].max()))
        col3.metric("Semaine", s_act)
        
        st.divider()
        sel = st.selectbox("Sélectionne un exercice :", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel].copy()
        
        # FIX : On accepte les perfs si Reps > 0 (pour Dips/Tractions à 0kg)
        df_records = df_e[(df_e["Poids"] > 0) | (df_e["Reps"] > 0)].copy()
        
        if not df_records.empty:
            best = df_records.sort_values(["Poids", "Reps"], ascending=False).iloc[0]
            st.success(f"🏆 Record : **{best['Poids']} kg x {int(best['Reps'])}** (1RM théorique: {calc_1rm(best['Poids'], best['Reps']):.1f} kg)")
            
            # Graphique : Poids max par séance
            c_data = df_records.groupby(["Cycle", "Semaine"])["Poids"].max().reset_index()
            c_data["Point"] = "C" + c_data["Cycle"].astype(str) + "-S" + c_data["Semaine"].astype(str)
            st.line_chart(c_data.set_index("Point")["Poids"])
        else:
            st.info("ℹ️ Aucune performance enregistrée (Reps à 0).")
        
        st.dataframe(df_e.sort_values(["Cycle", "Semaine"], ascending=False), hide_index=True)
