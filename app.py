import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime, timedelta
import plotly.graph_objects as go
import streamlit.components.v1 as components

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="MUSCU TRACKER PRO", layout="wide", page_icon="logo.png")

if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()
if 'active_quests' not in st.session_state:
    st.session_state.active_quests = {}
if 'completed_quests' not in st.session_state:
    st.session_state.completed_quests = []
if 'quest_notifications' not in st.session_state:
    st.session_state.quest_notifications = []

# --- 2. CSS : DESIGN NÉO-BRUTALISM TECH + ART DÉCO CYBER ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Orbitron:wght@400;700;900&family=Space+Mono:wght@400;700&display=swap');
    
    :root {
        --primary: #00FFA3;
        --secondary: #FF006E;
        --accent: #FFD60A;
        --dark: #0A0E27;
        --darker: #050815;
        --surface: #1A1F3A;
        --text: #E8EDF4;
        --border: #2D3651;
    }
    
    .stApp {
        background: var(--darker);
        background-image: 
            radial-gradient(circle at 10% 20%, rgba(0, 255, 163, 0.05) 0%, transparent 40%),
            radial-gradient(circle at 90% 80%, rgba(255, 0, 110, 0.05) 0%, transparent 40%),
            repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255, 255, 255, 0.01) 2px, rgba(255, 255, 255, 0.01) 4px);
        color: var(--text);
        font-family: 'Space Mono', monospace;
    }
    
    /* HEADER MEGA */
    .mega-header {
        text-align: center;
        padding: 40px 20px 20px;
        background: linear-gradient(180deg, var(--darker) 0%, transparent 100%);
        border-bottom: 3px solid var(--primary);
        position: relative;
        overflow: hidden;
    }
    
    .mega-header::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: repeating-linear-gradient(90deg, transparent, transparent 50px, rgba(0, 255, 163, 0.03) 50px, rgba(0, 255, 163, 0.03) 51px);
        pointer-events: none;
    }
    
    .mega-title {
        font-family: 'Orbitron', sans-serif;
        font-size: clamp(2rem, 5vw, 4rem);
        font-weight: 900;
        letter-spacing: 0.15em;
        color: var(--primary);
        text-shadow: 
            0 0 20px rgba(0, 255, 163, 0.5),
            0 0 40px rgba(0, 255, 163, 0.3),
            3px 3px 0 var(--secondary);
        margin: 0;
        animation: glitchTitle 3s infinite;
        position: relative;
        z-index: 1;
    }
    
    @keyframes glitchTitle {
        0%, 90%, 100% { transform: translate(0); }
        92% { transform: translate(-2px, 2px); }
        94% { transform: translate(2px, -2px); }
    }
    
    .mega-subtitle {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 1.2rem;
        letter-spacing: 0.3em;
        color: var(--accent);
        margin-top: 10px;
        text-transform: uppercase;
    }
    
    /* STATS BAR */
    .stats-bar {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 20px;
        margin: 30px 0;
        padding: 0 20px;
    }
    
    .stat-card {
        background: var(--surface);
        border: 2px solid var(--border);
        border-radius: 0;
        padding: 20px;
        position: relative;
        overflow: hidden;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .stat-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0;
        width: 100%;
        height: 3px;
        background: linear-gradient(90deg, var(--primary), var(--secondary));
        transform: scaleX(0);
        transform-origin: left;
        transition: transform 0.3s;
    }
    
    .stat-card:hover {
        border-color: var(--primary);
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(0, 255, 163, 0.2);
    }
    
    .stat-card:hover::before {
        transform: scaleX(1);
    }
    
    .stat-label {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 0.9rem;
        letter-spacing: 0.2em;
        color: var(--accent);
        margin-bottom: 8px;
        text-transform: uppercase;
    }
    
    .stat-value {
        font-family: 'Orbitron', sans-serif;
        font-size: 2.5rem;
        font-weight: 900;
        color: var(--primary);
        line-height: 1;
        text-shadow: 0 0 10px rgba(0, 255, 163, 0.3);
    }
    
    .stat-unit {
        font-size: 1rem;
        color: var(--text);
        opacity: 0.7;
        margin-left: 5px;
    }
    
    /* QUEST SYSTEM */
    .quest-panel {
        background: linear-gradient(135deg, var(--surface) 0%, var(--dark) 100%);
        border: 2px solid var(--primary);
        border-radius: 0;
        padding: 25px;
        margin: 20px 0;
        position: relative;
        overflow: hidden;
    }
    
    .quest-panel::before {
        content: '⚡';
        position: absolute;
        top: 10px;
        right: 10px;
        font-size: 3rem;
        opacity: 0.1;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 0.1; transform: scale(1); }
        50% { opacity: 0.2; transform: scale(1.1); }
    }
    
    .quest-header {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 2rem;
        letter-spacing: 0.2em;
        color: var(--accent);
        margin-bottom: 20px;
        text-transform: uppercase;
        border-bottom: 2px solid var(--border);
        padding-bottom: 10px;
    }
    
    .quest-item {
        background: rgba(255, 255, 255, 0.03);
        border-left: 4px solid var(--secondary);
        padding: 15px;
        margin-bottom: 15px;
        transition: all 0.3s;
        position: relative;
    }
    
    .quest-item:hover {
        background: rgba(255, 255, 255, 0.06);
        border-left-color: var(--primary);
        transform: translateX(5px);
    }
    
    .quest-item.completed {
        border-left-color: var(--primary);
        opacity: 0.6;
    }
    
    .quest-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--primary);
        margin-bottom: 8px;
    }
    
    .quest-desc {
        font-size: 0.9rem;
        color: var(--text);
        opacity: 0.8;
        margin-bottom: 10px;
    }
    
    .quest-reward {
        font-family: 'Bebas Neue', sans-serif;
        color: var(--accent);
        font-size: 0.95rem;
        letter-spacing: 0.1em;
    }
    
    .quest-progress {
        width: 100%;
        height: 8px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 4px;
        overflow: hidden;
        margin-top: 10px;
    }
    
    .quest-progress-fill {
        height: 100%;
        background: linear-gradient(90deg, var(--secondary), var(--primary));
        transition: width 0.5s ease-out;
        box-shadow: 0 0 10px var(--primary);
    }
    
    /* TABS */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: var(--surface);
        border-bottom: 3px solid var(--border);
        padding: 0;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 1.2rem;
        letter-spacing: 0.15em;
        padding: 20px 30px;
        color: var(--text);
        background: transparent;
        border: none;
        border-bottom: 3px solid transparent;
        transition: all 0.3s;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255, 255, 255, 0.05);
        color: var(--primary);
    }
    
    .stTabs [aria-selected="true"] {
        background: var(--dark) !important;
        color: var(--primary) !important;
        border-bottom-color: var(--primary) !important;
    }
    
    /* EXPANDER */
    .stExpander {
        background: var(--surface) !important;
        border: 2px solid var(--border) !important;
        border-radius: 0 !important;
        margin-bottom: 15px !important;
    }
    
    .stExpander:hover {
        border-color: var(--primary) !important;
    }
    
    details[open] > summary {
        border-bottom: 2px solid var(--border);
        padding-bottom: 15px;
        margin-bottom: 15px;
    }
    
    summary {
        font-family: 'Orbitron', sans-serif !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        color: var(--primary) !important;
        letter-spacing: 0.1em;
    }
    
    /* BUTTONS */
    .stButton > button {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 1.1rem;
        letter-spacing: 0.15em;
        padding: 12px 30px;
        background: var(--primary);
        color: var(--darker);
        border: none;
        border-radius: 0;
        font-weight: 700;
        transition: all 0.3s;
        text-transform: uppercase;
        position: relative;
        overflow: hidden;
    }
    
    .stButton > button::before {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 0;
        height: 0;
        background: var(--secondary);
        border-radius: 50%;
        transform: translate(-50%, -50%);
        transition: width 0.6s, height 0.6s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 20px rgba(0, 255, 163, 0.4);
    }
    
    .stButton > button:hover::before {
        width: 300px;
        height: 300px;
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* METRICS */
    [data-testid="stMetricValue"] {
        font-family: 'Orbitron', sans-serif;
        font-size: 2rem !important;
        font-weight: 900 !important;
        color: var(--primary) !important;
        text-shadow: 0 0 10px rgba(0, 255, 163, 0.3);
    }
    
    [data-testid="stMetricLabel"] {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 0.9rem !important;
        letter-spacing: 0.2em;
        color: var(--accent) !important;
        text-transform: uppercase;
    }
    
    /* DATA EDITOR */
    .stDataFrame {
        border: 2px solid var(--border) !important;
        border-radius: 0 !important;
    }
    
    /* NOTIFICATION */
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, var(--secondary), var(--primary));
        color: white;
        padding: 20px 30px;
        border-radius: 0;
        border: 2px solid var(--primary);
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        animation: slideIn 0.5s ease-out;
        z-index: 9999;
    }
    
    @keyframes slideIn {
        from { transform: translateX(400px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    /* RANK LADDER */
    .rank-ladder {
        display: flex;
        justify-content: space-around;
        align-items: center;
        background: var(--surface);
        border: 2px solid var(--border);
        padding: 30px 20px;
        margin: 30px 0;
        position: relative;
    }
    
    .rank-step {
        text-align: center;
        flex: 1;
        opacity: 0.4;
        transition: all 0.3s;
        position: relative;
    }
    
    .rank-step::after {
        content: '→';
        position: absolute;
        right: -20px;
        top: 50%;
        transform: translateY(-50%);
        font-size: 2rem;
        color: var(--border);
    }
    
    .rank-step:last-child::after {
        display: none;
    }
    
    .rank-step.active {
        opacity: 1;
        transform: scale(1.2);
    }
    
    .rank-step.active .rank-icon {
        color: var(--primary);
        text-shadow: 0 0 20px var(--primary);
        animation: bounce 1s infinite;
    }
    
    @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-10px); }
    }
    
    .rank-step.completed {
        opacity: 0.7;
    }
    
    .rank-step.completed .rank-icon {
        color: var(--primary);
    }
    
    .rank-icon {
        font-size: 3rem;
        display: block;
        margin-bottom: 10px;
        transition: all 0.3s;
    }
    
    .rank-name {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 0.9rem;
        letter-spacing: 0.15em;
        color: var(--text);
    }
    
    /* XP BAR */
    .xp-container {
        margin-top: 20px;
    }
    
    .xp-bar-bg {
        width: 100%;
        height: 20px;
        background: rgba(255, 255, 255, 0.1);
        border: 2px solid var(--border);
        overflow: hidden;
        position: relative;
    }
    
    .xp-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, var(--secondary), var(--primary));
        box-shadow: 0 0 20px var(--primary);
        transition: width 1s ease-out;
        position: relative;
        overflow: hidden;
    }
    
    .xp-bar-fill::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
        animation: shimmer 2s infinite;
    }
    
    @keyframes shimmer {
        to { left: 100%; }
    }
    
    .xp-text {
        display: flex;
        justify-content: space-between;
        margin-top: 10px;
        font-family: 'Space Mono', monospace;
        font-size: 0.9rem;
    }
    
    /* RECOVERY CARDS */
    .recovery-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 15px;
        margin: 20px 0;
    }
    
    .recovery-card {
        background: var(--surface);
        border: 2px solid var(--border);
        padding: 15px;
        text-align: center;
        transition: all 0.3s;
    }
    
    .recovery-card:hover {
        border-color: var(--primary);
        transform: translateY(-5px);
    }
    
    .recovery-muscle {
        font-family: 'Bebas Neue', sans-serif;
        font-size: 1rem;
        letter-spacing: 0.15em;
        color: var(--accent);
        margin-bottom: 10px;
    }
    
    .recovery-status {
        font-family: 'Orbitron', sans-serif;
        font-size: 0.8rem;
        font-weight: 700;
        padding: 5px 10px;
        border-radius: 0;
    }
    
    .status-ready {
        background: var(--primary);
        color: var(--darker);
    }
    
    .status-recovering {
        background: var(--accent);
        color: var(--darker);
    }
    
    .status-tired {
        background: var(--secondary);
        color: white;
    }
    
    /* PODIUM */
    .podium-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
        margin: 30px 0;
    }
    
    .podium-card {
        background: var(--surface);
        border: 2px solid var(--border);
        padding: 25px;
        text-align: center;
        position: relative;
        transition: all 0.3s;
    }
    
    .podium-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 5px;
        background: linear-gradient(90deg, transparent, var(--primary), transparent);
    }
    
    .podium-gold::before {
        background: linear-gradient(90deg, transparent, #FFD700, transparent);
    }
    
    .podium-silver::before {
        background: linear-gradient(90deg, transparent, #C0C0C0, transparent);
    }
    
    .podium-bronze::before {
        background: linear-gradient(90deg, transparent, #CD7F32, transparent);
    }
    
    .podium-card:hover {
        transform: scale(1.05);
        box-shadow: 0 10px 30px rgba(0, 255, 163, 0.2);
    }
    
    .podium-rank {
        font-size: 3rem;
        margin-bottom: 10px;
    }
    
    .podium-exercise {
        font-family: 'Orbitron', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--primary);
        margin-bottom: 10px;
    }
    
    .podium-value {
        font-family: 'Orbitron', sans-serif;
        font-size: 2rem;
        font-weight: 900;
        color: var(--accent);
    }
    
    /* SCROLLBAR */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--darker);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--primary);
        border: 2px solid var(--darker);
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--secondary);
    }
    
    /* INPUT FIELDS */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > select {
        background: var(--surface) !important;
        border: 2px solid var(--border) !important;
        border-radius: 0 !important;
        color: var(--text) !important;
        font-family: 'Space Mono', monospace !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stSelectbox > div > div > select:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 10px rgba(0, 255, 163, 0.3) !important;
    }
    
    /* HEADINGS */
    h1, h2, h3 {
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 900 !important;
        letter-spacing: 0.1em !important;
        color: var(--primary) !important;
        text-transform: uppercase;
    }
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
    v, r = "background-color: rgba(0, 255, 163, 0.2); color: #00FFA3;", "background-color: rgba(255, 0, 110, 0.2); color: #FF006E;"
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

# --- 4. QUEST SYSTEM ---
QUEST_TEMPLATES = {
    "weekly_warrior": {
        "title": "🔥 GUERRIER HEBDOMADAIRE",
        "description": "Complète 4 séances cette semaine",
        "reward": "+500 XP",
        "type": "weekly",
        "target": 4,
        "icon": "🏆"
    },
    "volume_king": {
        "title": "👑 ROI DU VOLUME",
        "description": "Atteins 10,000kg de volume total en une séance",
        "reward": "+750 XP",
        "type": "session",
        "target": 10000,
        "icon": "💪"
    },
    "consistency": {
        "title": "⚡ CONSISTANCE",
        "description": "Entraîne-toi 3 jours d'affilée",
        "reward": "+300 XP",
        "type": "streak",
        "target": 3,
        "icon": "🔥"
    },
    "pr_hunter": {
        "title": "🎯 CHASSEUR DE PR",
        "description": "Bats 3 records personnels cette semaine",
        "reward": "+1000 XP",
        "type": "weekly",
        "target": 3,
        "icon": "⚡"
    },
    "balanced": {
        "title": "⚖️ ÉQUILIBRE PARFAIT",
        "description": "Entraîne tous les groupes musculaires cette semaine",
        "reward": "+600 XP",
        "type": "weekly",
        "target": 6,
        "icon": "🎭"
    },
    "endurance": {
        "title": "🔋 ENDURANCE",
        "description": "Fais une série de 15+ reps",
        "reward": "+200 XP",
        "type": "session",
        "target": 15,
        "icon": "⚡"
    },
    "heavy_lifter": {
        "title": "⚡ PUISSANCE BRUTE",
        "description": "Soulève 100kg+ en une série",
        "reward": "+400 XP",
        "type": "session",
        "target": 100,
        "icon": "💥"
    }
}

def check_quest_progress(df_h, current_week):
    """Vérifie la progression des quêtes"""
    notifications = []
    
    # Initialiser les quêtes actives si nécessaire
    if not st.session_state.active_quests:
        st.session_state.active_quests = {
            "weekly_warrior": {"progress": 0, "completed": False},
            "volume_king": {"progress": 0, "completed": False},
            "consistency": {"progress": 0, "completed": False},
            "pr_hunter": {"progress": 0, "completed": False},
            "balanced": {"progress": 0, "completed": False},
            "endurance": {"progress": 0, "completed": False},
            "heavy_lifter": {"progress": 0, "completed": False}
        }
    
    # Weekly Warrior: Séances complétées cette semaine
    sessions_this_week = df_h[df_h["Semaine"] == current_week]["Séance"].nunique()
    if sessions_this_week > st.session_state.active_quests["weekly_warrior"]["progress"]:
        st.session_state.active_quests["weekly_warrior"]["progress"] = sessions_this_week
        if sessions_this_week >= QUEST_TEMPLATES["weekly_warrior"]["target"] and not st.session_state.active_quests["weekly_warrior"]["completed"]:
            st.session_state.active_quests["weekly_warrior"]["completed"] = True
            notifications.append("🏆 QUÊTE COMPLÉTÉE: GUERRIER HEBDOMADAIRE +500 XP!")
    
    # Volume King: Volume max en une séance
    df_sessions = df_h[df_h["Semaine"] == current_week].groupby("Séance").apply(lambda x: (x["Poids"] * x["Reps"]).sum()).max()
    if pd.notna(df_sessions) and df_sessions > st.session_state.active_quests["volume_king"]["progress"]:
        st.session_state.active_quests["volume_king"]["progress"] = int(df_sessions)
        if df_sessions >= QUEST_TEMPLATES["volume_king"]["target"] and not st.session_state.active_quests["volume_king"]["completed"]:
            st.session_state.active_quests["volume_king"]["completed"] = True
            notifications.append("👑 QUÊTE COMPLÉTÉE: ROI DU VOLUME +750 XP!")
    
    # Balanced: Groupes musculaires entraînés
    muscles_trained = df_h[df_h["Semaine"] == current_week]["Muscle"].nunique()
    if muscles_trained > st.session_state.active_quests["balanced"]["progress"]:
        st.session_state.active_quests["balanced"]["progress"] = muscles_trained
        if muscles_trained >= QUEST_TEMPLATES["balanced"]["target"] and not st.session_state.active_quests["balanced"]["completed"]:
            st.session_state.active_quests["balanced"]["completed"] = True
            notifications.append("⚖️ QUÊTE COMPLÉTÉE: ÉQUILIBRE PARFAIT +600 XP!")
    
    # Endurance: Série de 15+ reps
    max_reps = df_h[df_h["Semaine"] == current_week]["Reps"].max()
    if pd.notna(max_reps) and max_reps > st.session_state.active_quests["endurance"]["progress"]:
        st.session_state.active_quests["endurance"]["progress"] = int(max_reps)
        if max_reps >= QUEST_TEMPLATES["endurance"]["target"] and not st.session_state.active_quests["endurance"]["completed"]:
            st.session_state.active_quests["endurance"]["completed"] = True
            notifications.append("🔋 QUÊTE COMPLÉTÉE: ENDURANCE +200 XP!")
    
    # Heavy Lifter: 100kg+ en une série
    max_weight = df_h[df_h["Semaine"] == current_week]["Poids"].max()
    if pd.notna(max_weight) and max_weight > st.session_state.active_quests["heavy_lifter"]["progress"]:
        st.session_state.active_quests["heavy_lifter"]["progress"] = float(max_weight)
        if max_weight >= QUEST_TEMPLATES["heavy_lifter"]["target"] and not st.session_state.active_quests["heavy_lifter"]["completed"]:
            st.session_state.active_quests["heavy_lifter"]["completed"] = True
            notifications.append("⚡ QUÊTE COMPLÉTÉE: PUISSANCE BRUTE +400 XP!")
    
    return notifications

def display_quest_panel():
    """Affiche le panneau de quêtes"""
    st.markdown('<div class="quest-panel">', unsafe_allow_html=True)
    st.markdown('<div class="quest-header">⚡ MISSIONS ACTIVES</div>', unsafe_allow_html=True)
    
    for quest_id, quest_data in QUEST_TEMPLATES.items():
        if quest_id in st.session_state.active_quests:
            progress = st.session_state.active_quests[quest_id]["progress"]
            target = quest_data["target"]
            completed = st.session_state.active_quests[quest_id]["completed"]
            progress_pct = min((progress / target) * 100, 100)
            
            quest_class = "quest-item completed" if completed else "quest-item"
            
            st.markdown(f"""
            <div class="{quest_class}">
                <div class="quest-title">{quest_data["icon"]} {quest_data["title"]}</div>
                <div class="quest-desc">{quest_data["description"]}</div>
                <div class="quest-reward">Récompense: {quest_data["reward"]}</div>
                <div class="quest-progress">
                    <div class="quest-progress-fill" style="width: {progress_pct}%"></div>
                </div>
                <small style="color: var(--text); opacity: 0.7; margin-top: 5px; display: block;">
                    Progression: {progress} / {target} {'✅' if completed else ''}
                </small>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def muscle_flappy_game():
    st.markdown("### 🕹️ MUSCLE FLAPPY : ÉVOLUTION")
    game_html = """
    <div id="game-container" style="text-align: center;">
        <canvas id="flappyCanvas" width="320" height="480" style="border: 2px solid var(--secondary); background: var(--darker); cursor: pointer; touch-action: none;"></canvas>
    </div>
    <script>
        const canvas = document.getElementById('flappyCanvas');
        const ctx = canvas.getContext('2d');
        let biceps = { x: 50, y: 150, w: 30, h: 30, gravity: 0.35, velocity: 0, lift: -6 };
        let pipes = []; let frameCount = 0; let score = 0; 
        let gameOver = false; let gameStarted = false;
        let baseSpeed = 3.5;
        let record = localStorage.getItem('muscleFlappyRecord') || 0;
        function reset() { biceps.y = 150; biceps.velocity = 0; pipes = []; score = 0; frameCount = 0; gameOver = false; gameStarted = false; baseSpeed = 3.5; }
        function handleAction(e) { e.preventDefault(); if (gameOver) { reset(); } else if (!gameStarted) { gameStarted = true; biceps.velocity = biceps.lift; } else { biceps.velocity = biceps.lift; } }
        canvas.addEventListener('mousedown', handleAction);
        canvas.addEventListener('touchstart', handleAction, {passive: false});
        function draw() {
            ctx.fillStyle = '#050815'; ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.font = "30px Arial"; ctx.fillText("💪", biceps.x, biceps.y);
            if (gameStarted && !gameOver) {
                biceps.velocity += biceps.gravity; biceps.y += biceps.velocity;
                let currentSpeed = baseSpeed + (Math.floor(score / 5) * 0.2);
                let spawnRate = Math.max(50, 80 - Math.floor(score / 2));
                if (frameCount % spawnRate === 0) { pipes.push({ x: canvas.width, topH: Math.floor(Math.random() * (canvas.height - 225)) + 50, gap: 125, passed: false }); }
                for (let i = pipes.length - 1; i >= 0; i--) {
                    pipes[i].x -= currentSpeed; ctx.fillStyle = "#FF006E"; 
                    ctx.fillRect(pipes[i].x, 0, 50, pipes[i].topH);
                    ctx.fillRect(pipes[i].x, pipes[i].topH + pipes[i].gap, 50, canvas.height);
                    if (biceps.x + 20 > pipes[i].x && biceps.x < pipes[i].x + 50) { if (biceps.y - 20 < pipes[i].topH || biceps.y > pipes[i].topH + pipes[i].gap - 10) gameOver = true; }
                    if (!pipes[i].passed && biceps.x > pipes[i].x + 50) { score++; pipes[i].passed = true; }
                    if (pipes[i].x < -60) pipes.splice(i, 1);
                }
                if (biceps.y > canvas.height || biceps.y < 0) gameOver = true;
            } else if (!gameStarted) { ctx.fillStyle = "white"; ctx.font = "18px monospace"; ctx.fillText("TAP POUR SOULEVER", 70, 240); }
            if (gameOver) { if (score > record) { record = score; localStorage.setItem('muscleFlappyRecord', record); } ctx.fillStyle = "rgba(255,0,110,0.5)"; ctx.fillRect(0,0, canvas.width, canvas.height); ctx.fillStyle = "white"; ctx.font = "30px monospace"; ctx.fillText("ÉCHEC CRITIQUE", 45, 220); ctx.font = "15px monospace"; ctx.fillText("Score: " + score + " | Record: " + record, 75, 260); ctx.fillText("Clique pour retenter", 75, 290); }
            ctx.font = "bold 20px monospace"; ctx.fillStyle = "#00FFA3"; ctx.fillText("XP: " + score, 15, 35); ctx.fillStyle = "#FFD60A"; ctx.fillText("MAX: " + record, 180, 35);
            frameCount++; requestAnimationFrame(draw);
        }
        draw();
    </script>
    """
    components.html(game_html, height=520)

# --- 5. CONNEXION ---
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
try: prog = json.loads(prog_raw)
except: prog = {}

muscle_mapping = {ex["name"]: ex.get("muscle", "Autre") for s in prog for ex in prog[s]}
df_h["Muscle"] = df_h["Exercice"].apply(get_base_name).map(muscle_mapping).fillna(df_h["Muscle"]).replace("", "Autre")

# --- 6. HEADER ---
st.markdown("""
<div class="mega-header">
    <h1 class="mega-title">MUSCU TRACKER</h1>
    <div class="mega-subtitle">Pro Edition v2.0</div>
</div>
""", unsafe_allow_html=True)

# --- 7. STATS BAR ---
v_tot = int((df_h['Poids'] * df_h['Reps']).sum()) if not df_h.empty else 0
total_workouts = df_h["Séance"].nunique() if not df_h.empty else 0
current_week = int(df_h["Semaine"].max() if not df_h.empty else 1)
max_1rm = df_h.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1).max() if not df_h.empty else 0

# Check quest progress
quest_notifs = check_quest_progress(df_h, current_week)
if quest_notifs:
    for notif in quest_notifs:
        st.markdown(f'<div class="notification">{notif}</div>', unsafe_allow_html=True)

st.markdown(f"""
<div class="stats-bar">
    <div class="stat-card">
        <div class="stat-label">💪 Volume Total</div>
        <div class="stat-value">{v_tot:,}<span class="stat-unit">kg</span></div>
    </div>
    <div class="stat-card">
        <div class="stat-label">🏋️ Séances</div>
        <div class="stat-value">{total_workouts}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">📅 Semaine</div>
        <div class="stat-value">{current_week}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">⚡ Max 1RM</div>
        <div class="stat-value">{max_1rm:.0f}<span class="stat-unit">kg</span></div>
    </div>
</div>
""".replace(',', ' '), unsafe_allow_html=True)

# --- 8. TABS ---
tab_q, tab_s, tab_p, tab_st, tab_g = st.tabs(["⚡ QUÊTES", "🏋️ SÉANCE", "⚙️ PROGRAMME", "📊 STATS", "🕹️ JEU"])

# --- ONGLET QUÊTES ---
with tab_q:
    display_quest_panel()
    
    st.markdown("### 🏆 HISTORIQUE DES SUCCÈS")
    if st.session_state.completed_quests:
        for quest in st.session_state.completed_quests:
            st.success(f"✅ {quest}")
    else:
        st.info("Aucune quête complétée pour le moment. Continue à t'entraîner!")

# --- ONGLET MA SÉANCE ---
with tab_s:
    if prog:
        col1, col2, col3 = st.columns([2, 1, 1])
        choix_s = col1.selectbox("📋 SÉLECTIONNE TA SÉANCE", list(prog.keys()))
        s_act = col2.number_input("📅 SEMAINE", 1, 52, current_week)
        if col3.button("🚩 SKIP SÉANCE", use_container_width=True):
            m_rec = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": "SESSION", "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SÉANCE MANQUÉE 🚩", "Muscle": "Autre", "Date": datetime.now().strftime("%Y-%m-%d")}])
            save_hist(pd.concat([df_h, m_rec], ignore_index=True))
            st.rerun()

        st.markdown("### 🔋 STATUT DE RÉCUPÉRATION")
        recup_cols = ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos"]
        html_recup = "<div class='recovery-grid'>"
        for m in recup_cols:
            trained_this_week = df_h[(df_h["Muscle"] == m) & (df_h["Semaine"] == s_act)]
            status_class, status_label = "status-ready", "PRÊT"
            if not trained_this_week.empty:
                last_d = trained_this_week["Date"].max()
                if pd.notna(last_d) and last_d != "":
                    try:
                        diff = (datetime.now() - datetime.strptime(last_d, "%Y-%m-%d")).days
                        if diff < 1: status_class, status_label = "status-tired", "FATIGUÉ"
                        elif diff < 2: status_class, status_label = "status-recovering", "RÉCUP"
                    except: pass
            html_recup += f"""
            <div class='recovery-card'>
                <div class='recovery-muscle'>{m.upper()}</div>
                <div class='recovery-status {status_class}'>{status_label}</div>
            </div>
            """
        st.markdown(html_recup + "</div>", unsafe_allow_html=True)

        st.divider()

        # Volume tracking
        vol_curr = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Reps"]).sum()
        vol_prev = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Reps"]).sum()
        
        if vol_prev > 0:
            ratio = min(vol_curr / vol_prev, 1.2)
            bar_color = "var(--primary)" if vol_curr >= vol_prev else "var(--secondary)"
            st.markdown(f"""
            <div style='background: var(--surface); border: 2px solid var(--border); padding: 15px; margin-bottom: 20px;'>
                <div style='font-family: "Bebas Neue", sans-serif; letter-spacing: 0.15em; color: var(--accent); margin-bottom: 10px;'>
                    📊 VOLUME DE SÉANCE: {int(vol_curr)}kg / {int(vol_prev)}kg
                </div>
                <div class='xp-bar-bg'>
                    <div class='xp-bar-fill' style='width: {min(ratio*100, 100)}%; background: {bar_color};'></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Exercices
        for i, ex_obj in enumerate(prog[choix_s]):
            exo_base, p_sets, muscle_grp = ex_obj["name"], ex_obj.get("sets", 3), ex_obj.get("muscle", "Autre")
            with st.expander(f"🔹 {exo_base.upper()}", expanded=False):
                var = st.selectbox("⚙️ Équipement", ["Standard", "Barre", "Haltères", "Banc", "Poulie", "Machine", "Lesté"], key=f"v_{exo_base}_{i}")
                exo_final = f"{exo_base} ({var})" if var != "Standard" else exo_base
                f_h = df_h[(df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s)]
                
                if not f_h.empty:
                    best_w = f_h["Poids"].max()
                    best_1rm = f_h.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1).max()
                    col_r1, col_r2 = st.columns(2)
                    col_r1.metric("🏆 RECORD", f"{best_w:g}kg")
                    col_r2.metric("⚡ 1RM", f"{best_1rm:.1f}kg")

                hist_weeks = sorted(f_h[f_h["Semaine"] < s_act]["Semaine"].unique())
                if hist_weeks:
                    weeks_to_show = hist_weeks[-2:]
                    for w_num in weeks_to_show:
                        h_data = f_h[f_h["Semaine"] == w_num]
                        st.caption(f"📅 Semaine {w_num}")
                        st.dataframe(h_data[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                else:
                    st.info("Première session ! Établis tes marques de référence.")

                curr = f_h[f_h["Semaine"] == s_act]
                last_w_num = hist_weeks[-1] if hist_weeks else None
                hist_prev_df = f_h[f_h["Semaine"] == last_w_num] if last_w_num is not None else pd.DataFrame()
                
                is_reset = not curr.empty and (curr["Poids"].sum() == 0 and curr["Reps"].sum() == 0) and "SKIP" not in str(curr["Remarque"].iloc[0])

                editor_key = f"ed_{exo_final}_{s_act}"

                if not curr.empty and not is_reset and exo_final not in st.session_state.editing_exo:
                    st.markdown("##### ✅ VALIDÉ")
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.apply(style_comparaison, axis=1, hist_prev=hist_prev_df).format({"Poids": "{:g}"}), hide_index=True, use_container_width=True)
                    if st.button("🔄 MODIFIER", key=f"m_{exo_final}_{i}"): 
                        st.session_state.editing_exo.add(exo_final)
                        st.rerun()
                else:
                    df_base = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                    if not curr.empty:
                        for _, r in curr.iterrows():
                            if r["Série"] <= p_sets: 
                                df_base.loc[df_base["Série"] == r["Série"], ["Reps", "Poids", "Remarque"]] = [r["Reps"], r["Poids"], r["Remarque"]]
                    
                    ed = st.data_editor(df_base, num_rows="fixed", key=editor_key, use_container_width=True, column_config={"Série": st.column_config.NumberColumn(disabled=True), "Poids": st.column_config.NumberColumn(format="%g")})
                    
                    col_save, col_skip = st.columns(2)
                    if col_save.button("💾 SAUVEGARDER", key=f"sv_{exo_final}"):
                        v = ed.copy()
                        v["Semaine"], v["Séance"], v["Exercice"], v["Muscle"], v["Date"] = s_act, choix_s, exo_final, muscle_grp, datetime.now().strftime("%Y-%m-%d")
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s))], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo_final)
                        st.rerun()
                    if col_skip.button("⏩ SKIP", key=f"sk_{exo_final}"):
                        v_skip = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": exo_final, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫", "Muscle": muscle_grp, "Date": datetime.now().strftime("%Y-%m-%d")}])
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s))], v_skip], ignore_index=True))
                        st.rerun()

# --- ONGLET PROGRAMME ---
with tab_p:
    st.markdown("## ⚙️ CONFIGURATION DU PROGRAMME")
    jours = list(prog.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"📦 {j}"):
            col_s1, col_s2 = st.columns(2)
            if col_s1.button("⬆️ MONTER", key=f"up_s_{j}") and idx_j > 0:
                jours[idx_j], jours[idx_j-1] = jours[idx_j-1], jours[idx_j]
                save_prog({k: prog[k] for k in jours})
                st.rerun()
            if col_s2.button("🗑️ SUPPRIMER", key=f"del_s_{j}"):
                del prog[j]
                save_prog(prog)
                st.rerun()
            
            for i, ex in enumerate(prog[j]):
                col1, col2, col3, col4, col5, col6 = st.columns([3, 1.5, 1.5, 0.7, 0.7, 0.7])
                col1.write(f"**{ex['name']}**")
                ex['sets'] = col2.number_input("Sets", 1, 15, ex.get('sets', 3), key=f"p_s_{j}_{i}")
                ex['muscle'] = col3.selectbox("Muscle", ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"], index=["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"].index(ex.get("muscle", "Autre")), key=f"m_{j}_{i}")
                if col4.button("⬆️", key=f"ue_{j}_{i}"):
                    if i > 0: 
                        prog[j][i], prog[j][i-1] = prog[j][i-1], prog[j][i]
                        save_prog(prog)
                        st.rerun()
                if col5.button("⬇️", key=f"de_{j}_{i}"):
                    if i < len(prog[j])-1: 
                        prog[j][i], prog[j][i+1] = prog[j][i+1], prog[j][i]
                        save_prog(prog)
                        st.rerun()
                if col6.button("🗑️", key=f"rm_{j}_{i}"):
                    prog[j].pop(i)
                    save_prog(prog)
                    st.rerun()
            
            st.divider()
            col_x, col_m, col_s = st.columns([3, 2, 1])
            ni = col_x.text_input("Nouvel exercice", key=f"ni_{j}")
            nm = col_m.selectbox("Groupe", ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos", "Autre"], key=f"nm_{j}")
            ns = col_s.number_input("Séries", 1, 15, 3, key=f"ns_{j}")
            if st.button("➕ AJOUTER", key=f"ba_{j}") and ni:
                prog[j].append({"name": ni, "sets": ns, "muscle": nm})
                save_prog(prog)
                st.rerun()
    
    nvs = st.text_input("➕ CRÉER UNE NOUVELLE SÉANCE")
    if st.button("🎯 CRÉER") and nvs:
        prog[nvs] = []
        save_prog(prog)
        st.rerun()

# --- ONGLET STATS ---
with tab_st:
    if not df_h.empty:
        # Rank System
        paliers = [0, 5000, 25000, 75000, 200000, 500000]
        noms = ["RECRUE", "SOLDAT", "ÉLITE", "TITAN", "LÉGENDE", "DIEU"]
        icons = ["🌱", "⚔️", "👑", "⚡", "🔥", "💎"]
        
        idx = next((i for i, p in enumerate(paliers[::-1]) if v_tot >= p), 0)
        idx = len(paliers) - 1 - idx
        
        next_p = paliers[idx+1] if idx < len(paliers)-1 else paliers[-1]
        xp_ratio = min((v_tot - paliers[idx]) / (next_p - paliers[idx]), 1.0) if next_p > paliers[idx] else 1.0
        
        st.markdown('<div class="rank-ladder">', unsafe_allow_html=True)
        for i, (nom, icon) in enumerate(zip(noms, icons)):
            rank_class = "rank-step"
            if i < idx:
                rank_class += " completed"
            elif i == idx:
                rank_class += " active"
            
            st.markdown(f"""
            <div class="{rank_class}">
                <div class="rank-icon">{icon}</div>
                <div class="rank-name">{nom}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="xp-container">
            <div class="xp-bar-bg">
                <div class="xp-bar-fill" style="width: {xp_ratio*100}%;"></div>
            </div>
            <div class="xp-text">
                <span style="color: var(--primary);">{v_tot:,} kg</span>
                <span style="color: var(--accent);">Objectif: {next_p:,} kg</span>
            </div>
        </div>
        """.replace(',', ' '), unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Radar Chart
        st.markdown("### 🕸️ ANALYSE D'ÉQUILIBRE")
        standards = {"Jambes": 150, "Dos": 120, "Pecs": 100, "Épaules": 75, "Bras": 50, "Abdos": 40}
        df_p = df_h[df_h["Reps"] > 0].copy()
        df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        scores, labels = [], list(standards.keys())
        
        for m in labels:
            m_max = df_p[df_p["Muscle"] == m]["1RM"].max() if not df_p[df_p["Muscle"] == m].empty else 0
            scores.append(min((m_max / standards[m]) * 100, 110))
        
        fig_r = go.Figure(data=go.Scatterpolar(
            r=scores + [scores[0]], 
            theta=labels + [labels[0]], 
            fill='toself',
            line=dict(color='#00FFA3', width=3),
            fillcolor='rgba(0, 255, 163, 0.2)'
        ))
        fig_r.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 110], showticklabels=False, gridcolor="rgba(255,255,255,0.1)"),
                angularaxis=dict(color="white")
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=40, r=40, t=20, b=20),
            height=400
        )
        st.plotly_chart(fig_r, use_container_width=True, config={'staticPlot': True})
        
        # Hall of Fame
        st.markdown("### 🏆 HALL OF FAME")
        m_filt = st.multiselect("Filtrer par muscle", labels + ["Autre"], default=labels + ["Autre"])
        df_p_filt = df_p[df_p["Muscle"].isin(m_filt)]
        
        if not df_p_filt.empty:
            podium = df_p_filt.groupby("Exercice").agg({"1RM": "max"}).sort_values(by="1RM", ascending=False).head(3)
            
            if len(podium) >= 1:
                medals = ["🥇", "🥈", "🥉"]
                classes = ["podium-gold", "podium-silver", "podium-bronze"]
                col_p1, col_p2, col_p3 = st.columns(3)
                cols = [col_p1, col_p2, col_p3]
                
                for idx, (ex_n, row) in enumerate(podium.iterrows()):
                    with cols[idx]:
                        st.markdown(f"""
                        <div class='podium-card {classes[idx]}'>
                            <div class='podium-rank'>{medals[idx]}</div>
                            <div class='podium-exercise'>{ex_n}</div>
                            <div class='podium-value'>{row['1RM']:.1f}kg</div>
                        </div>
                        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Exercise Deep Dive
        st.markdown("### 🎯 ANALYSE DÉTAILLÉE")
        sel_e = st.selectbox("Sélectionne un exercice", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel_e].copy()
        df_rec = df_e[(df_e["Poids"] > 0) | (df_e["Reps"] > 0)].copy()
        
        if not df_rec.empty:
            best = df_rec.sort_values(["Poids", "Reps"], ascending=False).iloc[0]
            one_rm = calc_1rm(best['Poids'], best['Reps'])
            
            col_1, col_2 = st.columns(2)
            col_1.metric("🏆 RECORD", f"{best['Poids']}kg x {int(best['Reps'])}")
            col_2.metric("⚡ 1RM ESTIMÉ", f"{one_rm:.1f}kg")
            
            with st.expander("📊 ESTIMATIONS REP MAX"):
                ests = get_rep_estimations(one_rm)
                cols = st.columns(len(ests))
                for idx, (r, p) in enumerate(ests.items()):
                    cols[idx].metric(f"{r} Reps", f"{p}kg")
            
            # Progress Chart
            c_dat = df_rec.groupby("Semaine")["Poids"].max().reset_index()
            fig_l = go.Figure()
            fig_l.add_trace(go.Scatter(
                x=c_dat["Semaine"], 
                y=c_dat["Poids"], 
                mode='markers+lines',
                line=dict(color='#00FFA3', width=3),
                marker=dict(size=10, color='#FFD60A')
            ))
            fig_l.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=0, r=0, t=10, b=0),
                height=300,
                xaxis=dict(gridcolor="rgba(255,255,255,0.1)", color="white"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.1)", color="white")
            )
            st.plotly_chart(fig_l, use_container_width=True, config={'staticPlot': True})
        
        st.dataframe(df_e[["Semaine", "Série", "Reps", "Poids", "Remarque", "Muscle"]].sort_values("Semaine", ascending=False), hide_index=True, use_container_width=True)

# --- ONGLET JEU ---
with tab_g:
    muscle_flappy_game()
