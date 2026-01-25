import streamlit as st
import pandas as pd
import json
import gspread

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Musculation Tracker", layout="centered", page_icon="logo.png")

# Initialisation du mode édition dans la mémoire de l'app
if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()

# --- CSS : DESIGN ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                    linear-gradient(180deg, #0A1931 0%, #000000 100%);
        background-attachment: fixed; background-size: cover;
        color: #E0E0E0; font-family: 'Helvetica', sans-serif;
    }
    .stTabs [data-baseweb="tab-list"] { background-color: rgba(255, 255, 255, 0.05) !important; border-radius: 12px; }
    .stTabs [aria-selected="true"] { background-color: rgba(255, 255, 255, 0.9) !important; color: #0A1931 !important; border-radius: 8px; font-weight: bold; }
    .stExpander { background-color: rgba(10, 25, 49, 0.6) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 10px; margin-bottom: 10px; backdrop-filter: blur(5px); }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    if reps <= 0: return 0
    return weight * (1 + reps / 30)

def style_comparaison(row, hist_s1):
    prev_set = hist_s1[hist_s1["Série"] == row["Série"]]
    v = "background-color: rgba(46, 125, 50, 0.4); color: white;" # Vert translucide
    r = "background-color: rgba(198, 40, 40, 0.4); color: white;" # Rouge translucide
    o = "background-color: rgba(255, 152, 0, 0.4); color: white;" # Orange translucide
    colors = ["", "", "", ""] 
    if not prev_set.empty:
        pw, pr = float(prev_set.iloc[0]["Poids"]), int(prev_set.iloc[0]["Reps"])
        cw, cr = float(row["Poids"]), int(row["Reps"])
        p_1rm, c_1rm = calc_1rm(pw, pr), calc_1rm(cw, cr)
        if c_1rm > p_1rm and cw < pw: colors[1], colors[2] = o, o
        elif cw > pw: colors[1], colors[2] = v, v
        elif cw < pw: colors[1], colors[2] = r, r
        elif cw == pw:
            if cr > pr: colors[1] = v
            elif cr < pr: colors[1] = r
    return colors

# --- CONNEXION ---
@st.cache_resource
def get_google_sheets():
    creds = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(creds)
    sh = gc.open("Muscu_App")
    return sh.get_worksheet(0), sh.worksheet("Programme")

ws_h, ws_p = get_google_sheets()

def get_hist():
    data = ws_h.get_all_records()
    if not data: return pd.DataFrame(columns=["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque"])
    df = pd.DataFrame(data)
    df["Poids"] = pd.to_numeric(df["Poids"], errors='coerce').fillna(0.0).astype(float)
    return df

def save_hist(df):
    ws_h.clear()
    data = [df.columns.values.tolist()] + df.values.tolist()
    ws_h.update(data, value_input_option='USER_ENTERED')

# --- CHARGEMENT ---
df_h = get_hist()
prog = json.loads(ws_p.acell('A1').value or "{}")

# LOGO FIXE
col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
with col_l2:
    st.image("logo.png", use_container_width=True)

tab1, tab2, tab3 = st.tabs(["📅 Programme", "🏋️‍♂️ Ma Séance", "📈 Progrès"])

# --- ONGLET 1 : PROGRAMME ---
with tab1:
    for jour, exos in prog.items():
        with st.expander(f"⚙️ {jour}"):
            for i, exo in enumerate(exos):
                c1, c2 = st.columns([8, 2])
                c1.write(f"**{exo}**")
                if c2.button("🗑️", key=f"d_{jour}_{i}"):
                    exos.pop(i); ws_p.update_acell('A1', json.dumps(prog)); st.rerun()
            nv = st.text_input("Nouvel exo", key=f"n_{jour}")
            if st.button("Ajouter", key=f"b_{jour}") and nv:
                exos.append(nv); ws_p.update_acell('A1', json.dumps(prog)); st.rerun()

# --- ONGLET 2 : MA SÉANCE ---
with tab2:
    if not prog: st.warning("Crée une séance !")
    else:
        choix_s = st.selectbox("Séance :", list(prog.keys()))
        sem = st.number_input("Semaine", min_value=1, value=1)
        
        for exo in prog[choix_s]:
            with st.expander(f"🔹 {exo}", expanded=True):
                h1 = df_h[(df_h["Exercice"] == exo) & (df_h["Semaine"] == sem - 1) & (df_h["Séance"] == choix_s)]
                curr = df_h[(df_h["Exercice"] == exo) & (df_h["Semaine"] == sem) & (df_h["Séance"] == choix_s)]
                
                # S'il y a des données et qu'on n'est pas en train de modifier
                if not curr.empty and exo not in st.session_state.editing_exo:
                    st.caption("✅ Résultat (Visual Tracker) :")
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.format({"Poids": "{:g}"}).apply(style_comparaison, axis=1, hist_s1=h1), 
                                 hide_index=True, use_container_width=True)
                    
                    if st.button(f"🔄 Modifier / Ajouter une série", key=f"btn_edit_{exo}"):
                        st.session_state.editing_exo.add(exo)
                        st.rerun()
                
                # Sinon, on affiche l'éditeur
                else:
                    if not curr.empty:
                        # On pré-remplit avec l'existant + une ligne vide pour la suite
                        existing = curr[["Série", "Reps", "Poids", "Remarque"]].copy()
                        next_s = int(existing["Série"].max() + 1)
                        new_row = pd.DataFrame({"Série": [next_s], "Reps": [0], "Poids": [0.0], "Remarque": [""]})
                        df_to_edit = pd.concat([existing, new_row], ignore_index=True)
                    else:
                        df_to_edit = pd.DataFrame({"Série": [1], "Reps": [0], "Poids": [0.0], "Remarque": [""]})

                    ed = st.data_editor(df_to_edit, num_rows="dynamic", key=f"e_{exo}", use_container_width=True, 
                                        column_config={"Poids": st.column_config.NumberColumn(format="%g")})
                    
                    if st.button(f"✅ Valider {exo}", key=f"v_{exo}"):
                        valid = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                        valid["Semaine"], valid["Séance"], valid["Exercice"] = sem, choix_s, exo
                        
                        # Mise à jour de l'historique sans tout supprimer
                        mask = (df_h["Semaine"] == sem) & (df_h["Séance"] == choix_s) & (df_h["Exercice"] == exo)
                        df_final = pd.concat([df_h[~mask], valid], ignore_index=True)
                        save_hist(df_final)
                        
                        # On quitte le mode édition pour cet exercice
                        if exo in st.session_state.editing_exo:
                            st.session_state.editing_exo.remove(exo)
                        st.rerun()

# --- ONGLET 3 : PROGRÈS ---
with tab3:
    if not df_h.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Volume total", f"{int((df_h['Poids'] * df_h['Reps']).sum())} kg")
        col2.metric("Nb Séances", len(df_h[df_h["Poids"] > 0].groupby(["Semaine", "Séance"])))
        col3.metric("Semaine Max", f"S{df_h['Semaine'].max()}")
        
        sel_exo = st.selectbox("Exercice :", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel_exo].copy()
        if not df_e.empty:
            df_v = df_e[df_e["Poids"] > 0]
            if not df_v.empty:
                max_set = df_v.sort_values(by=["Poids", "Reps"], ascending=False).iloc[0]
                st.success(f"🏆 Record : **{max_set['Poids']} kg x {int(max_set['Reps'])}**")
                st.line_chart(df_e.groupby("Semaine")["Poids"].max())
            st.dataframe(df_e[["Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values(by="Semaine", ascending=False), hide_index=True)
