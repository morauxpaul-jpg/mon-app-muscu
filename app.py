import streamlit as st
import pandas as pd
import json
import gspread

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Musculation Tracker", layout="centered", page_icon="logo.png")

if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()

# --- CSS : DESIGN & COULEURS ---
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
    .stButton button { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    if reps <= 0: return 0
    # Formule de Brzycki / Epley simplifiée
    return weight * (1 + reps / 30)

def style_comparaison(row, hist_s1):
    prev_set = hist_s1[hist_s1["Série"] == row["Série"]]
    v = "background-color: rgba(46, 125, 50, 0.4); color: white;" # Vert
    r = "background-color: rgba(198, 40, 40, 0.4); color: white;" # Rouge
    o = "background-color: rgba(255, 152, 0, 0.4); color: white;" # Orange
    
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
with col_l2: st.image("logo.png", use_container_width=True)

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
            nv = st.text_input("Nouvel exo", key=f"n_{jour}", placeholder="+ Ajouter exo")
            if st.button("Ajouter", key=f"b_{jour}") and nv:
                exos.append(nv); ws_p.update_acell('A1', json.dumps(prog)); st.rerun()

# --- ONGLET 2 : MA SÉANCE ---
with tab2:
    if not prog: st.warning("Crée une séance !")
    else:
        c1, c2 = st.columns([2, 1])
        choix_s = c1.selectbox("Séance :", list(prog.keys()))
        sem = c2.number_input("Semaine", min_value=1, value=1)
        
        # --- BOUTON SKIP SÉANCE ENTIÈRE ---
        if st.button("🚫 Marquer SÉANCE ENTIÈRE comme loupée", use_container_width=True):
            skipped_rows = []
            for e in prog[choix_s]:
                skipped_rows.append({"Semaine": sem, "Séance": choix_s, "Exercice": e, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SÉANCE LOUPÉE ❌"})
            
            # Nettoyage des anciennes entrées de cette séance/semaine pour éviter les doublons
            mask = (df_h["Semaine"] == sem) & (df_h["Séance"] == choix_s)
            new_df = pd.concat([df_h[~mask], pd.DataFrame(skipped_rows)], ignore_index=True)
            save_hist(new_df)
            st.success("Toute la séance a été marquée comme loupée.")
            st.rerun()

        st.divider()

        for exo in prog[choix_s]:
            with st.expander(f"🔹 {exo}", expanded=True):
                # 1. RÉCUPÉRATION DE L'HISTORIQUE DES 2 DERNIÈRES SÉANCES
                # On filtre par séance et exercice, et on prend les semaines inférieures à l'actuelle
                full_hist_exo = df_h[(df_h["Exercice"] == exo) & 
                                     (df_h["Séance"] == choix_s) & 
                                     (df_h["Semaine"] < sem)].sort_values(by="Semaine", ascending=False)
                
                last_weeks = full_hist_exo["Semaine"].unique()[:2] # On récupère les 2 derniers numéros de semaine
                
                if len(last_weeks) > 0:
                    st.caption("🔍 Historique des dernières séances :")
                    for w in last_weeks:
                        h_data = full_hist_exo[full_hist_exo["Semaine"] == w]
                        st.write(f"**Semaine {w}**")
                        st.dataframe(h_data[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                else:
                    st.caption("ℹ️ Aucune donnée historique pour cet exercice.")

                # 2. GESTION DE LA SAISIE ACTUELLE
                curr = df_h[(df_h["Exercice"] == exo) & (df_h["Semaine"] == sem) & (df_h["Séance"] == choix_s)]
                
                # Récupération du S-1 pour la comparaison de couleur
                h_s1 = full_hist_exo[full_hist_exo["Semaine"] == last_weeks[0]] if len(last_weeks) > 0 else pd.DataFrame()

                if not curr.empty and exo not in st.session_state.editing_exo:
                    st.caption(f"✅ Performance Actuelle (S{sem}) :")
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.format({"Poids": "{:g}"}).apply(style_comparaison, axis=1, hist_s1=h_s1), 
                                 hide_index=True, use_container_width=True)
                    
                    if st.button(f"🔄 Modifier / Ajouter", key=f"edit_{exo}"):
                        st.session_state.editing_exo.add(exo)
                        st.rerun()
                else:
                    if not curr.empty:
                        existing = curr[["Série", "Reps", "Poids", "Remarque"]].copy()
                        next_s = int(existing["Série"].max() + 1)
                        new_row = pd.DataFrame({"Série": [next_s], "Reps": [0], "Poids": [0.0], "Remarque": [""]})
                        df_to_edit = pd.concat([existing, new_row], ignore_index=True)
                    else:
                        df_to_edit = pd.DataFrame({"Série": [1, 2, 3], "Reps": [0,0,0], "Poids": [0.0,0.0,0.0], "Remarque": ["","",""]})

                    ed = st.data_editor(df_to_edit, num_rows="dynamic", key=f"e_{exo}", use_container_width=True, 
                                        column_config={"Poids": st.column_config.NumberColumn(format="%g")})
                    
                    c_val, c_skip_exo = st.columns(2)
                    
                    if c_val.button(f"✅ Valider {exo}", key=f"v_{exo}"):
                        valid = ed[(ed["Poids"] > 0) | (ed["Reps"] > 0)].copy()
                        valid["Semaine"], valid["Séance"], valid["Exercice"] = sem, choix_s, exo
                        mask = (df_h["Semaine"] == sem) & (df_h["Séance"] == choix_s) & (df_h["Exercice"] == exo)
                        save_hist(pd.concat([df_h[~mask], valid], ignore_index=True))
                        if exo in st.session_state.editing_exo: st.session_state.editing_exo.remove(exo)
                        st.rerun()

                    if c_skip_exo.button(f"🚫 Skip l'exo", key=f"skip_exo_{exo}"):
                        skip_row = pd.DataFrame([{"Semaine": sem, "Séance": choix_s, "Exercice": exo, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "EXO SKIP 🚫"}])
                        mask = (df_h["Semaine"] == sem) & (df_h["Séance"] == choix_s) & (df_h["Exercice"] == exo)
                        save_hist(pd.concat([df_h[~mask], skip_row], ignore_index=True))
                        if exo in st.session_state.editing_exo: st.session_state.editing_exo.remove(exo)
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
            st.dataframe(df_e[["Semaine", "Série", "Reps", "Poids", "Remarque"]].sort_values(by=["Semaine", "Série"], ascending=[False, True]), hide_index=True)
