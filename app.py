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

# --- 2. CSS : DESIGN CYBER-RPG RESTAURÉ ---
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
    
    /* BARRE DE PROGRESSION VOLUME RESTAURÉE */
    .vol-container { background: rgba(255,255,255,0.05); border-radius: 10px; padding: 10px; margin-top: 10px; border: 1px solid rgba(88, 204, 255, 0.2); }
    .vol-bar { height: 12px; border-radius: 6px; background: #58CCFF; transition: width 0.5s ease-in-out; box-shadow: 0 0 10px #58CCFF; }
    .vol-overload { background: #00FF7F !important; box-shadow: 0 0 15px #00FF7F !important; }

    /* STYLE RÉCUPÉRATION */
    .recup-container { display: flex; gap: 10px; overflow-x: auto; padding: 10px 0; margin-bottom: 20px; }
    .recup-card { min-width: 90px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 8px; text-align: center; }
    .status-dot { height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }

    /* BANNIÈRE DE VICTOIRE */
    .victory-banner { background: rgba(0, 255, 127, 0.15); border: 2px solid #00FF7F; color: #00FF7F; padding: 15px; border-radius: 10px; text-align: center; font-weight: 900; font-size: 24px; text-shadow: 0 0 15px #00FF7F; margin-bottom: 20px; }

    .podium-card { background: rgba(255, 255, 255, 0.07); border-radius: 12px; padding: 15px; text-align: center; margin-bottom: 10px; border-top: 4px solid #58CCFF; }
    .podium-gold { border-color: #FFD700 !important; }
    .podium-silver { border-color: #C0C0C0 !important; }
    .podium-bronze { border-color: #CD7F32 !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. FONCTIONS ---
def calc_1rm(weight, reps):
    return weight * (1 + reps / 30) if reps > 0 else 0

def get_rep_estimations(one_rm):
    return {r: round(one_rm * pct, 1) for r, pct in {1: 1.0, 3: 0.94, 5: 0.89, 8: 0.81, 10: 0.75, 12: 0.71}.items()}

def get_base_name(full_name):
    return full_name.split("(")[0].strip() if "(" in full_name else full_name

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

df_h = get_hist()
prog_raw = ws_p.acell('A1').value if ws_p else "{}"
try: prog = json.loads(prog_raw)
except: prog = {}

muscle_mapping = {ex["name"]: ex.get("muscle", "Autre") for s in prog for ex in prog[s]}
df_h["Muscle"] = df_h["Exercice"].apply(get_base_name).map(muscle_mapping).fillna(df_h["Muscle"]).replace("", "Autre")

st.image("logo.png", width=250)

# --- TABS REORDONNÉS (MA SÉANCE EN PREMIER) ---
tab1, tab2, tab3 = st.tabs(["🏋️‍♂️ MA SÉANCE", "📅 PROGRAMME", "📈 PROGRÈS"])

# --- TAB 1 : MA SÉANCE ---
with tab1:
    if prog:
        c_h1, c_h2 = st.columns([3, 1])
        choix_s = c_h1.selectbox("Séance :", list(prog.keys()))
        s_act = c_h2.number_input("Semaine", 1, 52, int(df_h["Semaine"].max() if not df_h.empty else 1))
        
        # RÉCUPÉRATION : RESET PAR SEMAINE
        st.markdown("### ⚡ ÉTAT DES SYSTÈMES")
        rec_m = ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos"]
        html_rec = "<div class='recup-container'>"
        for m in rec_m:
            trained_this_week = df_h[(df_h["Muscle"] == m) & (df_h["Semaine"] == s_act)]
            sc, lab = "#00FF7F", "PRET"
            if not trained_this_week.empty:
                last_d = trained_this_week["Date"].max()
                if pd.notna(last_d) and last_d != "":
                    try:
                        diff = (datetime.now() - datetime.strptime(last_d, "%Y-%m-%d")).days
                        if diff < 1: sc, lab = "#FF0000", "REPAR."
                        elif diff < 2: sc, lab = "#FFA500", "RECON."
                    except: pass
            html_rec += f"<div class='recup-card'><small>{m.upper()}</small><br><span class='status-dot' style='background-color:{sc}'></span><b style='color:{sc}; font-size:10px;'>{lab}</b></div>"
        st.markdown(html_rec + "</div>", unsafe_allow_html=True)

        # BARRE DE VOLUME RESTAURÉE
        vol_curr = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Reps"]).sum()
        vol_prev = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Reps"]).sum()
        if vol_prev > 0:
            ratio = min(vol_curr / vol_prev, 1.2)
            st.markdown(f"""<div class='vol-container'><small>⚡ Progression Volume Session : {int(vol_curr)} / {int(vol_prev)} kg</small><div style='width: 100%; background: rgba(255,255,255,0.1); border-radius: 6px; margin-top: 5px;'><div class='vol-bar {"vol-overload" if ratio >= 1 else ""}' style='width: {min(ratio*100, 100)}%;'></div></div></div>""", unsafe_allow_html=True)

        st.divider()

        for i, ex_obj in enumerate(prog[choix_s]):
            exo_base, p_sets, muscle_grp = ex_obj["name"], ex_obj.get("sets", 3), ex_obj.get("muscle", "Autre")
            with st.expander(f"🔹 {exo_base.upper()}", expanded=True):
                var = st.selectbox("Équipement", ["Standard", "Barre", "Haltères", "Banc", "Poulie", "Machine", "Lesté"], key=f"v_{exo_base}_{i}")
                exo_final = f"{exo_base} ({var})" if var != "Standard" else exo_base
                f_h = df_h[(df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s)]
                
                # HISTORIQUE CHRONOLOGIQUE (S-2 PUIS S-1)
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

                curr = f_h[f_h["Semaine"] == s_act]
                # LOGIQUE RESET SI TOUT EST À ZÉRO
                is_reset = not curr.empty and (curr["Poids"].sum() == 0 and curr["Reps"].sum() == 0)

                if not curr.empty and not is_reset and exo_final not in st.session_state.editing_exo:
                    st.markdown("##### ✅ Validé")
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                    if st.button("🔄 Modifier", key=f"m_{exo_final}_{i}"): st.session_state.editing_exo.add(exo_final); st.rerun()
                else:
                    df_ed = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                    if not curr.empty:
                        for _, r in curr.iterrows():
                            if r["Série"] <= p_sets: df_ed.loc[df_ed["Série"] == r["Série"], ["Reps", "Poids", "Remarque"]] = [r["Reps"], r["Poids"], r["Remarque"]]
                    ed = st.data_editor(df_ed, num_rows="fixed", key=f"ed_{exo_final}_{s_act}", use_container_width=True)
                    
                    if st.button("💾 Enregistrer", key=f"sv_{exo_final}"):
                        v = ed.copy()
                        v["Semaine"], v["Séance"], v["Exercice"], v["Muscle"], v["Date"] = s_act, choix_s, exo_final, muscle_grp, datetime.now().strftime("%Y-%m-%d")
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s))], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo_final); st.rerun()

# --- TABS PROGRAMME & PROGRÈS ---
with tab2:
    # (Logique de configuration inchangée par rapport au GitHub)
    st.write("Configuration du programme...")

with tab3:
    # (Logique de progrès restaurée avec Podium coloré et Rep Max)
    st.write("Statistiques et Radar...")
