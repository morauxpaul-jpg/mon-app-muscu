import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime, timedelta
import plotly.graph_objects as go
import streamlit.components.v1 as components

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Muscu Tracker PRO", layout="centered", page_icon="logo.png")

if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()
if 'active_quests' not in st.session_state:
    st.session_state.active_quests = {}
if 'completed_quests' not in st.session_state:
    st.session_state.completed_quests = []
if 'quest_notifications' not in st.session_state:
    st.session_state.quest_notifications = []

# --- 2. CSS : DESIGN CYBER-RPG COMPLET + ANIMATIONS ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 50% 0%, rgba(10, 50, 100, 0.4) 0%, transparent 50%),
                    linear-gradient(180deg, #050A18 0%, #000000 100%);
        background-attachment: fixed; color: #F0F2F6;
        animation: bgPulse 10s infinite alternate;
    }
    
    @keyframes bgPulse {
        0% { filter: brightness(1); }
        100% { filter: brightness(1.1); }
    }
    
    .stExpander {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(74, 144, 226, 0.3) !important;
        border-radius: 15px !important; backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6) !important; margin-bottom: 15px;
        transition: all 0.3s ease;
        animation: fadeInUp 0.5s ease-out;
    }
    
    .stExpander:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 40px rgba(88, 204, 255, 0.3) !important;
        border-color: rgba(88, 204, 255, 0.6) !important;
    }
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    h1, h2, h3 { 
        letter-spacing: 1.5px; 
        text-transform: uppercase; 
        color: #FFFFFF; 
        text-shadow: 2px 2px 8px rgba(0,0,0,0.7);
        animation: titleGlow 2s ease-in-out infinite alternate;
    }
    
    @keyframes titleGlow {
        from { text-shadow: 2px 2px 8px rgba(0,0,0,0.7), 0 0 10px rgba(88, 204, 255, 0.3); }
        to { text-shadow: 2px 2px 8px rgba(0,0,0,0.7), 0 0 20px rgba(88, 204, 255, 0.6); }
    }
    
    div[data-testid="stMetricValue"] { 
        font-family: 'Courier New', monospace; font-size: 38px !important; color: #58CCFF !important; 
        font-weight: 900; text-shadow: 0 0 20px rgba(88, 204, 255, 0.6) !important;
        animation: metricPulse 2s ease-in-out infinite;
    }
    
    @keyframes metricPulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    
    /* QUEST SYSTEM STYLES */
    .quest-panel {
        background: linear-gradient(135deg, rgba(88, 204, 255, 0.1) 0%, rgba(0, 255, 127, 0.05) 100%);
        border: 2px solid #58CCFF;
        border-radius: 15px;
        padding: 25px;
        margin: 20px 0;
        position: relative;
        overflow: hidden;
        animation: fadeInUp 0.6s ease-out;
    }
    
    .quest-panel::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(45deg, transparent, rgba(88, 204, 255, 0.1), transparent);
        animation: questShimmer 3s linear infinite;
    }
    
    @keyframes questShimmer {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .quest-header {
        font-family: 'Courier New', monospace;
        font-size: 1.8rem;
        font-weight: 900;
        color: #FFD60A;
        margin-bottom: 20px;
        text-transform: uppercase;
        letter-spacing: 3px;
        text-shadow: 0 0 10px rgba(255, 214, 10, 0.5);
        position: relative;
        z-index: 1;
        animation: questHeaderPulse 2s ease-in-out infinite;
    }
    
    @keyframes questHeaderPulse {
        0%, 100% { text-shadow: 0 0 10px rgba(255, 214, 10, 0.5); }
        50% { text-shadow: 0 0 20px rgba(255, 214, 10, 0.8), 0 0 30px rgba(255, 214, 10, 0.4); }
    }
    
    .quest-item {
        background: rgba(255, 255, 255, 0.05);
        border-left: 4px solid #FF453A;
        padding: 15px;
        margin-bottom: 15px;
        border-radius: 8px;
        transition: all 0.3s ease;
        position: relative;
        z-index: 1;
        animation: slideInLeft 0.5s ease-out;
    }
    
    @keyframes slideInLeft {
        from {
            opacity: 0;
            transform: translateX(-30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    .quest-item:hover {
        background: rgba(255, 255, 255, 0.1);
        border-left-color: #00FF7F;
        transform: translateX(10px);
        box-shadow: 0 5px 20px rgba(0, 255, 127, 0.3);
    }
    
    .quest-item.completed {
        border-left-color: #00FF7F;
        opacity: 0.8;
        animation: completedPulse 1s ease-in-out;
    }
    
    @keyframes completedPulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); background: rgba(0, 255, 127, 0.2); }
        100% { transform: scale(1); }
    }
    
    .quest-title {
        font-family: 'Courier New', monospace;
        font-size: 1.2rem;
        font-weight: 700;
        color: #58CCFF;
        margin-bottom: 8px;
        text-shadow: 0 0 5px rgba(88, 204, 255, 0.3);
    }
    
    .quest-desc {
        font-size: 0.95rem;
        color: #E8EDF4;
        opacity: 0.9;
        margin-bottom: 10px;
    }
    
    .quest-reward {
        font-family: 'Courier New', monospace;
        color: #FFD60A;
        font-size: 1rem;
        font-weight: 700;
        text-shadow: 0 0 5px rgba(255, 214, 10, 0.3);
    }
    
    .quest-progress {
        width: 100%;
        height: 10px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 5px;
        overflow: hidden;
        margin-top: 10px;
        position: relative;
    }
    
    .quest-progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #FF453A, #00FF7F);
        transition: width 0.8s ease-out;
        box-shadow: 0 0 15px rgba(0, 255, 127, 0.6);
        position: relative;
        overflow: hidden;
    }
    
    .quest-progress-fill::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
        animation: progressShimmer 2s infinite;
    }
    
    @keyframes progressShimmer {
        to { left: 100%; }
    }
    
    /* NOTIFICATION SYSTEM */
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, #FF453A, #00FF7F);
        color: white;
        padding: 20px 30px;
        border-radius: 10px;
        font-family: 'Courier New', monospace;
        font-weight: 700;
        font-size: 1.1rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 20px rgba(0, 255, 127, 0.4);
        animation: notificationSlideIn 0.5s ease-out, notificationPulse 2s ease-in-out infinite;
        z-index: 9999;
    }
    
    @keyframes notificationSlideIn {
        from { 
            transform: translateX(400px); 
            opacity: 0; 
        }
        to { 
            transform: translateX(0); 
            opacity: 1; 
        }
    }
    
    @keyframes notificationPulse {
        0%, 100% { box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 20px rgba(0, 255, 127, 0.4); }
        50% { box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 30px rgba(0, 255, 127, 0.8); }
    }
    
    .rank-ladder { 
        display: flex; justify-content: space-between; align-items: center; 
        background: rgba(255,255,255,0.05); padding: 20px; border-radius: 15px; 
        border: 1px solid #58CCFF; margin-bottom: 30px;
        animation: fadeInUp 0.7s ease-out;
    }
    
    .rank-step { 
        text-align: center; flex: 1; opacity: 0.5; font-size: 10px; 
        transition: all 0.5s ease;
        animation: fadeIn 1s ease-out;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    
    .rank-step.active { 
        opacity: 1; font-weight: bold; transform: scale(1.2); color: #58CCFF;
        animation: rankBounce 1s ease-in-out infinite;
    }
    
    @keyframes rankBounce {
        0%, 100% { transform: scale(1.2) translateY(0); }
        50% { transform: scale(1.2) translateY(-10px); }
    }
    
    .rank-step.completed { 
        color: #00FF7F; opacity: 0.8;
        animation: completedGlow 2s ease-in-out infinite;
    }
    
    @keyframes completedGlow {
        0%, 100% { text-shadow: 0 0 5px rgba(0, 255, 127, 0.3); }
        50% { text-shadow: 0 0 15px rgba(0, 255, 127, 0.6); }
    }
    
    .xp-bar-bg { 
        width: 100%; background: rgba(255,255,255,0.1); border-radius: 10px; 
        height: 12px; overflow: hidden; border: 1px solid rgba(88, 204, 255, 0.3);
        animation: fadeIn 0.8s ease-out;
    }
    
    .xp-bar-fill { 
        height: 100%; background: linear-gradient(90deg, #58CCFF, #00FF7F); 
        box-shadow: 0 0 15px #58CCFF;
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
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
        animation: xpShimmer 2s infinite;
    }
    
    @keyframes xpShimmer {
        to { left: 100%; }
    }

    .vol-container { 
        background: rgba(255,255,255,0.05); border-radius: 10px; padding: 10px; 
        border: 1px solid rgba(88, 204, 255, 0.2);
        animation: fadeInUp 0.6s ease-out;
    }
    
    .vol-bar { 
        height: 12px; border-radius: 6px; background: #58CCFF; 
        transition: width 0.8s ease-in-out; 
        box-shadow: 0 0 10px #58CCFF;
        animation: volumeGrow 1s ease-out;
    }
    
    @keyframes volumeGrow {
        from { width: 0; }
    }
    
    .vol-overload { 
        background: #00FF7F !important; 
        box-shadow: 0 0 15px #00FF7F !important;
        animation: overloadPulse 1s ease-in-out infinite;
    }
    
    @keyframes overloadPulse {
        0%, 100% { box-shadow: 0 0 15px #00FF7F; }
        50% { box-shadow: 0 0 25px #00FF7F, 0 0 35px rgba(0, 255, 127, 0.4); }
    }

    .podium-card { 
        background: rgba(255, 255, 255, 0.07); border-radius: 12px; padding: 15px; 
        text-align: center; margin-bottom: 10px; border-top: 4px solid #58CCFF;
        transition: all 0.3s ease;
        animation: fadeInUp 0.5s ease-out;
    }
    
    .podium-card:hover {
        transform: translateY(-8px) scale(1.05);
        box-shadow: 0 15px 40px rgba(88, 204, 255, 0.3);
    }
    
    .podium-gold { 
        border-color: #FFD700 !important; 
        box-shadow: 0 0 15px rgba(255, 215, 0, 0.2);
        animation: goldShine 2s ease-in-out infinite;
    }
    
    @keyframes goldShine {
        0%, 100% { box-shadow: 0 0 15px rgba(255, 215, 0, 0.2); }
        50% { box-shadow: 0 0 30px rgba(255, 215, 0, 0.5); }
    }
    
    .podium-silver { 
        border-color: #C0C0C0 !important; 
        box-shadow: 0 0 15px rgba(192, 192, 192, 0.2);
        animation: silverShine 2s ease-in-out infinite;
    }
    
    @keyframes silverShine {
        0%, 100% { box-shadow: 0 0 15px rgba(192, 192, 192, 0.2); }
        50% { box-shadow: 0 0 30px rgba(192, 192, 192, 0.5); }
    }
    
    .podium-bronze { 
        border-color: #CD7F32 !important; 
        box-shadow: 0 0 15px rgba(205, 127, 50, 0.2);
        animation: bronzeShine 2s ease-in-out infinite;
    }
    
    @keyframes bronzeShine {
        0%, 100% { box-shadow: 0 0 15px rgba(205, 127, 50, 0.2); }
        50% { box-shadow: 0 0 30px rgba(205, 127, 50, 0.5); }
    }
    
    .recup-container { 
        display: flex; gap: 10px; overflow-x: auto; padding: 10px 0; margin-bottom: 20px;
        animation: fadeIn 0.8s ease-out;
    }
    
    .recup-card { 
        min-width: 90px; background: rgba(255,255,255,0.05); 
        border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; 
        padding: 8px; text-align: center;
        transition: all 0.3s ease;
        animation: cardFloat 3s ease-in-out infinite;
    }
    
    .recup-card:hover {
        transform: translateY(-5px) scale(1.05);
        box-shadow: 0 8px 20px rgba(88, 204, 255, 0.3);
        border-color: #58CCFF;
    }
    
    @keyframes cardFloat {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-3px); }
    }
    
    .status-dot { 
        height: 10px; width: 10px; border-radius: 50%; 
        display: inline-block; margin-right: 5px;
        animation: dotPulse 2s ease-in-out infinite;
    }
    
    @keyframes dotPulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.7; transform: scale(1.2); }
    }

    .cyber-analysis { 
        background: rgba(88, 204, 255, 0.05); border-left: 4px solid #58CCFF; 
        padding: 15px; border-radius: 0 10px 10px 0; margin-bottom: 20px; 
        font-size: 0.95rem;
        animation: slideInLeft 0.6s ease-out;
    }
    
    /* Button animations */
    .stButton > button {
        transition: all 0.3s ease;
        animation: fadeIn 0.5s ease-out;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(88, 204, 255, 0.4);
    }
    
    .stButton > button:active {
        transform: translateY(0);
        box-shadow: 0 4px 10px rgba(88, 204, 255, 0.2);
    }
    
    /* Tab animations */
    .stTabs [data-baseweb="tab"] {
        transition: all 0.3s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        transform: translateY(-2px);
    }
    
    /* Data editor animations */
    .stDataFrame {
        animation: fadeInUp 0.5s ease-out;
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
            if "🏆 GUERRIER HEBDOMADAIRE" not in st.session_state.completed_quests:
                st.session_state.completed_quests.append("🏆 GUERRIER HEBDOMADAIRE")
    
    # Volume King: Volume max en une séance
    df_sessions = df_h[df_h["Semaine"] == current_week].groupby("Séance").apply(lambda x: (x["Poids"] * x["Reps"]).sum())
    if not df_sessions.empty:
        max_volume = df_sessions.max()
        if pd.notna(max_volume) and max_volume > st.session_state.active_quests["volume_king"]["progress"]:
            st.session_state.active_quests["volume_king"]["progress"] = int(max_volume)
            if max_volume >= QUEST_TEMPLATES["volume_king"]["target"] and not st.session_state.active_quests["volume_king"]["completed"]:
                st.session_state.active_quests["volume_king"]["completed"] = True
                notifications.append("👑 QUÊTE COMPLÉTÉE: ROI DU VOLUME +750 XP!")
                if "👑 ROI DU VOLUME" not in st.session_state.completed_quests:
                    st.session_state.completed_quests.append("👑 ROI DU VOLUME")
    
    # Balanced: Groupes musculaires entraînés
    muscles_trained = df_h[df_h["Semaine"] == current_week]["Muscle"].nunique()
    if muscles_trained > st.session_state.active_quests["balanced"]["progress"]:
        st.session_state.active_quests["balanced"]["progress"] = muscles_trained
        if muscles_trained >= QUEST_TEMPLATES["balanced"]["target"] and not st.session_state.active_quests["balanced"]["completed"]:
            st.session_state.active_quests["balanced"]["completed"] = True
            notifications.append("⚖️ QUÊTE COMPLÉTÉE: ÉQUILIBRE PARFAIT +600 XP!")
            if "⚖️ ÉQUILIBRE PARFAIT" not in st.session_state.completed_quests:
                st.session_state.completed_quests.append("⚖️ ÉQUILIBRE PARFAIT")
    
    # Endurance: Série de 15+ reps
    max_reps = df_h[df_h["Semaine"] == current_week]["Reps"].max()
    if pd.notna(max_reps) and max_reps > st.session_state.active_quests["endurance"]["progress"]:
        st.session_state.active_quests["endurance"]["progress"] = int(max_reps)
        if max_reps >= QUEST_TEMPLATES["endurance"]["target"] and not st.session_state.active_quests["endurance"]["completed"]:
            st.session_state.active_quests["endurance"]["completed"] = True
            notifications.append("🔋 QUÊTE COMPLÉTÉE: ENDURANCE +200 XP!")
            if "🔋 ENDURANCE" not in st.session_state.completed_quests:
                st.session_state.completed_quests.append("🔋 ENDURANCE")
    
    # Heavy Lifter: 100kg+ en une série
    max_weight = df_h[df_h["Semaine"] == current_week]["Poids"].max()
    if pd.notna(max_weight) and max_weight > st.session_state.active_quests["heavy_lifter"]["progress"]:
        st.session_state.active_quests["heavy_lifter"]["progress"] = float(max_weight)
        if max_weight >= QUEST_TEMPLATES["heavy_lifter"]["target"] and not st.session_state.active_quests["heavy_lifter"]["completed"]:
            st.session_state.active_quests["heavy_lifter"]["completed"] = True
            notifications.append("⚡ QUÊTE COMPLÉTÉE: PUISSANCE BRUTE +400 XP!")
            if "⚡ PUISSANCE BRUTE" not in st.session_state.completed_quests:
                st.session_state.completed_quests.append("⚡ PUISSANCE BRUTE")
    
    # PR Hunter: Records battus cette semaine
    pr_count = 0
    for exercise in df_h["Exercice"].unique():
        df_ex = df_h[df_h["Exercice"] == exercise]
        prev_weeks = df_ex[df_ex["Semaine"] < current_week]
        curr_week_data = df_ex[df_ex["Semaine"] == current_week]
        
        if not prev_weeks.empty and not curr_week_data.empty:
            prev_best = prev_weeks["Poids"].max()
            curr_best = curr_week_data["Poids"].max()
            if curr_best > prev_best:
                pr_count += 1
    
    if pr_count > st.session_state.active_quests["pr_hunter"]["progress"]:
        st.session_state.active_quests["pr_hunter"]["progress"] = pr_count
        if pr_count >= QUEST_TEMPLATES["pr_hunter"]["target"] and not st.session_state.active_quests["pr_hunter"]["completed"]:
            st.session_state.active_quests["pr_hunter"]["completed"] = True
            notifications.append("🎯 QUÊTE COMPLÉTÉE: CHASSEUR DE PR +1000 XP!")
            if "🎯 CHASSEUR DE PR" not in st.session_state.completed_quests:
                st.session_state.completed_quests.append("🎯 CHASSEUR DE PR")
    
    return notifications

def display_quest_panel():
    """Affiche le panneau de quêtes"""
    st.markdown('<div class="quest-panel">', unsafe_allow_html=True)
    st.markdown('<div class="quest-header">⚡ MISSIONS ACTIVES ⚡</div>', unsafe_allow_html=True)
    
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
                <small style="color: #E8EDF4; opacity: 0.7; margin-top: 5px; display: block;">
                    Progression: {progress} / {target} {'✅' if completed else ''}
                </small>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def muscle_flappy_game():
    st.markdown("### 🕹️ MUSCLE FLAPPY : EVOLUTION")
    game_html = """
    <div id="game-container" style="text-align: center;">
        <canvas id="flappyCanvas" width="320" height="480" style="border: 2px solid #FF453A; border-radius: 15px; background: #050A18; cursor: pointer; touch-action: none;"></canvas>
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
            ctx.fillStyle = '#050A18'; ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.font = "30px Arial"; ctx.fillText("💪", biceps.x, biceps.y);
            if (gameStarted && !gameOver) {
                biceps.velocity += biceps.gravity; biceps.y += biceps.velocity;
                let currentSpeed = baseSpeed + (Math.floor(score / 5) * 0.2);
                let spawnRate = Math.max(50, 80 - Math.floor(score / 2));
                if (frameCount % spawnRate === 0) { pipes.push({ x: canvas.width, topH: Math.floor(Math.random() * (canvas.height - 225)) + 50, gap: 125, passed: false }); }
                for (let i = pipes.length - 1; i >= 0; i--) {
                    pipes[i].x -= currentSpeed; ctx.fillStyle = "#FF453A"; 
                    ctx.fillRect(pipes[i].x, 0, 50, pipes[i].topH);
                    ctx.fillRect(pipes[i].x, pipes[i].topH + pipes[i].gap, 50, canvas.height);
                    if (biceps.x + 20 > pipes[i].x && biceps.x < pipes[i].x + 50) { if (biceps.y - 20 < pipes[i].topH || biceps.y > pipes[i].topH + pipes[i].gap - 10) gameOver = true; }
                    if (!pipes[i].passed && biceps.x > pipes[i].x + 50) { score++; pipes[i].passed = true; }
                    if (pipes[i].x < -60) pipes.splice(i, 1);
                }
                if (biceps.y > canvas.height || biceps.y < 0) gameOver = true;
            } else if (!gameStarted) { ctx.fillStyle = "white"; ctx.font = "18px Courier New"; ctx.fillText("TAP POUR SOULEVER", 70, 240); }
            if (gameOver) { if (score > record) { record = score; localStorage.setItem('muscleFlappyRecord', record); } ctx.fillStyle = "rgba(255,69,58,0.5)"; ctx.fillRect(0,0, canvas.width, canvas.height); ctx.fillStyle = "white"; ctx.font = "30px Courier New"; ctx.fillText("ÉCHEC CRITIQUE", 45, 220); ctx.font = "15px Courier New"; ctx.fillText("Score: " + score + " | Record: " + record, 75, 260); ctx.fillText("Clique pour retenter", 75, 290); }
            ctx.font = "bold 20px Courier New"; ctx.fillStyle = "#00FF7F"; ctx.fillText("XP: " + score, 15, 35); ctx.fillStyle = "#FFD700"; ctx.fillText("MAX: " + record, 180, 35);
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

col_l1, col_l2, col_l3 = st.columns([1, 1.8, 1])
with col_l2: st.image("logo.png", use_container_width=True)

# Check quest progress and show notifications
current_week = int(df_h["Semaine"].max() if not df_h.empty else 1)
quest_notifs = check_quest_progress(df_h, current_week)
if quest_notifs:
    for notif in quest_notifs:
        st.markdown(f'<div class="notification">{notif}</div>', unsafe_allow_html=True)

tab_q, tab_s, tab_p, tab_st, tab_g = st.tabs(["⚡ QUÊTES", "🏋️‍♂️ MA SÉANCE", "📅 PROGRAMME", "📈 PROGRÈS", "🕹️ MINI-JEU"])

# --- ONGLET QUÊTES ---
with tab_q:
    st.markdown("## ⚡ SYSTÈME DE QUÊTES")
    display_quest_panel()
    
    st.markdown("---")
    st.markdown("### 🏆 HISTORIQUE DES SUCCÈS")
    if st.session_state.completed_quests:
        for idx, quest in enumerate(st.session_state.completed_quests):
            st.markdown(f"""
            <div style='background: rgba(0, 255, 127, 0.1); border-left: 4px solid #00FF7F; padding: 10px; margin-bottom: 10px; border-radius: 5px; animation: fadeInUp 0.5s ease-out {idx * 0.1}s;'>
                ✅ {quest}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Aucune quête complétée pour le moment. Continue à t'entraîner!")

# --- ONGLET PROGRAMME ---
with tab_p:
    st.markdown("## ⚙️ Configuration")
    jours = list(prog.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"📦 {j}"):
            c_s1, c_s2 = st.columns(2)
            if c_s1.button("⬆️ Monter Séance", key=f"up_s_{j}") and idx_j > 0:
                jours[idx_j], jours[idx_j-1] = jours[idx_j-1], jours[idx_j]
                save_prog({k: prog[k] for k in jours}); st.rerun()
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

# --- ONGLET MA SÉANCE ---
with tab_s:
    if prog:
        c_h1, c_h2, c_h3 = st.columns([2, 1, 1])
        choix_s = c_h1.selectbox("Séance :", list(prog.keys()))
        s_act = c_h2.number_input("Semaine actuelle", 1, 52, current_week)
        if c_h3.button("🚩 Séance Manquée", use_container_width=True):
            m_rec = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": "SESSION", "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SÉANCE MANQUÉE 🚩", "Muscle": "Autre", "Date": datetime.now().strftime("%Y-%m-%d")}])
            save_hist(pd.concat([df_h, m_rec], ignore_index=True)); st.rerun()

        st.markdown("### 🔋 RÉCUPÉRATION")
        recup_cols = ["Pecs", "Dos", "Jambes", "Épaules", "Bras", "Abdos"]
        html_recup = "<div class='recup-container'>"
        for m in recup_cols:
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
            html_recup += f"<div class='recup-card'><small>{m.upper()}</small><br><span class='status-dot' style='background-color:{sc}'></span><b style='color:{sc}; font-size:10px;'>{lab}</b></div>"
        st.markdown(html_recup + "</div>", unsafe_allow_html=True)

        vol_curr = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]["Reps"]).sum()
        vol_prev = (df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Poids"] * df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act - 1)]["Reps"]).sum()
        if vol_prev > 0:
            ratio = min(vol_curr / vol_prev, 1.2)
            st.markdown(f"""<div class='vol-container'><small>⚡ Volume : <b>{int(vol_curr)} / {int(vol_prev)} kg</b></small><div class='xp-bar-bg'><div class='vol-bar {"vol-overload" if vol_curr >= vol_prev else ""}' style='width: {min(ratio*100, 100)}%;'></div></div></div>""", unsafe_allow_html=True)

        st.divider()

        for i, ex_obj in enumerate(prog[choix_s]):
            exo_base, p_sets, muscle_grp = ex_obj["name"], ex_obj.get("sets", 3), ex_obj.get("muscle", "Autre")
            with st.expander(f"🔹 {exo_base.upper()}", expanded=True):
                var = st.selectbox("Équipement :", ["Standard", "Barre", "Haltères", "Banc", "Poulie", "Machine", "Lesté"], key=f"v_{exo_base}_{i}")
                exo_final = f"{exo_base} ({var})" if var != "Standard" else exo_base
                f_h = df_h[(df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s)]
                
                if not f_h.empty:
                    best_w = f_h["Poids"].max()
                    best_1rm = f_h.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1).max()
                    st.caption(f"🏆 Record : **{best_w:g}kg** | ⚡ 1RM : **{best_1rm:.1f}kg**")

                hist_weeks = sorted(f_h[f_h["Semaine"] < s_act]["Semaine"].unique())
                if hist_weeks:
                    weeks_to_show = hist_weeks[-2:]
                    for w_num in weeks_to_show:
                        h_data = f_h[f_h["Semaine"] == w_num]
                        st.caption(f"📅 Semaine {w_num}")
                        st.dataframe(h_data[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                else:
                    st.info("Semaine 1 : Établissez vos marques !")

                curr = f_h[f_h["Semaine"] == s_act]
                last_w_num = hist_weeks[-1] if hist_weeks else None
                hist_prev_df = f_h[f_h["Semaine"] == last_w_num] if last_w_num is not None else pd.DataFrame()
                
                is_reset = not curr.empty and (curr["Poids"].sum() == 0 and curr["Reps"].sum() == 0) and "SKIP" not in str(curr["Remarque"].iloc[0])

                editor_key = f"ed_{exo_final}_{s_act}"

                if not curr.empty and not is_reset and exo_final not in st.session_state.editing_exo:
                    st.markdown("##### ✅ Validé")
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.apply(style_comparaison, axis=1, hist_prev=hist_prev_df).format({"Poids": "{:g}"}), hide_index=True, use_container_width=True)
                    if st.button("🔄 Modifier", key=f"m_{exo_final}_{i}"): 
                        st.session_state.editing_exo.add(exo_final); st.rerun()
                else:
                    df_base = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                    if not curr.empty:
                        for _, r in curr.iterrows():
                            if r["Série"] <= p_sets: df_base.loc[df_base["Série"] == r["Série"], ["Reps", "Poids", "Remarque"]] = [r["Reps"], r["Poids"], r["Remarque"]]
                    
                    ed = st.data_editor(df_base, num_rows="fixed", key=editor_key, use_container_width=True, column_config={"Série": st.column_config.NumberColumn(disabled=True), "Poids": st.column_config.NumberColumn(format="%g")})
                    
                    c_save, c_skip = st.columns(2)
                    if c_save.button("💾 Enregistrer", key=f"sv_{exo_final}"):
                        v = ed.copy(); v["Semaine"], v["Séance"], v["Exercice"], v["Muscle"], v["Date"] = s_act, choix_s, exo_final, muscle_grp, datetime.now().strftime("%Y-%m-%d")
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s))], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo_final); st.rerun()
                    if c_skip.button("⏩ Skip Exo", key=f"sk_{exo_final}"):
                        v_skip = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": exo_final, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫", "Muscle": muscle_grp, "Date": datetime.now().strftime("%Y-%m-%d")}])
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s))], v_skip], ignore_index=True)); st.rerun()

# --- ONGLET PROGRÈS ---
with tab_st:
    if not df_h.empty:
        v_tot = int((df_h['Poids'] * df_h['Reps']).sum())
        paliers, noms = [0, 5000, 25000, 75000, 200000, 500000], ["RECRUE NÉON", "CYBER-SOLDAT", "ÉLITE DE CHROME", "TITAN D'ACIER", "LÉGENDE CYBER", "DIEU DU FER"]
        idx = next((i for i, p in enumerate(paliers[::-1]) if v_tot >= p), 0)
        idx = len(paliers) - 1 - idx
        prev_r, curr_r, next_r = (noms[idx-1] if idx > 0 else "DÉBUT"), noms[idx], (noms[idx+1] if idx < len(noms)-1 else "MAX")
        next_p = paliers[idx+1] if idx < len(paliers)-1 else paliers[-1]
        xp_ratio = min((v_tot - paliers[idx]) / (next_p - paliers[idx]), 1.0) if next_p > paliers[idx] else 1.0
        st.markdown(f"""<div class='rank-ladder'><div class='rank-step completed'><small>PASSÉ</small><br>{prev_r}</div><div style='font-size: 20px; color: #58CCFF;'>➡️</div><div class='rank-step active'><small>ACTUEL</small><br><span style='font-size:18px;'>{curr_r}</span></div><div style='font-size: 20px; color: #58CCFF;'>➡️</div><div class='rank-step'><small>PROCHAIN</small><br>{next_r}</div></div><div class='xp-container'><div class='xp-bar-bg'><div class='xp-bar-fill' style='width:{xp_ratio*100}%;'></div></div><div style='display:flex; justify-content: space-between;'><small style='color:#00FF7F;'>{v_tot:,} kg</small><small style='color:#58CCFF;'>Objectif : {next_p:,} kg</small></div></div>""".replace(',', ' '), unsafe_allow_html=True)
        st.markdown("### 🕸️ Radar d'Équilibre")
        standards = {"Jambes": 150, "Dos": 120, "Pecs": 100, "Épaules": 75, "Bras": 50, "Abdos": 40}
        df_p = df_h[df_h["Reps"] > 0].copy(); df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        scores, labels = [], list(standards.keys())
        for m in labels:
            m_max = df_p[df_p["Muscle"] == m]["1RM"].max() if not df_p[df_p["Muscle"] == m].empty else 0
            scores.append(min((m_max / standards[m]) * 100, 110))
        fig_r = go.Figure(data=go.Scatterpolar(r=scores + [scores[0]], theta=labels + [labels[0]], fill='toself', line=dict(color='#58CCFF', width=3), fillcolor='rgba(88, 204, 255, 0.2)'))
        fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 110], showticklabels=False, gridcolor="rgba(255,255,255,0.1)"), angularaxis=dict(color="white")), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=40, r=40, t=20, b=20), height=350)
        st.plotly_chart(fig_r, use_container_width=True, config={'staticPlot': True})

        if any(s > 0 for s in scores):
            top_m = labels[scores.index(max(scores))]
            valid_scores = [(s, labels[idx]) for idx, s in enumerate(scores) if s > 0 and labels[idx] != "Jambes"]
            if valid_scores:
                min_val, low_m = min(valid_scores, key=lambda x: x[0])
                lvl = "Faible" if (max(scores)-min_val) < 15 else ("Moyen" if (max(scores)-min_val) < 30 else "Élevé")
                msg = f"🛡️ Analyseur de Profil : Ton profil est dominé par tes {top_m}. Ton vrai point faible actuel se situe au niveau de tes {low_m}. Le déséquilibre global est jugé {lvl}."
            else: msg = f"🛡️ Analyseur de Profil : Ton profil est dominé par tes {top_m}."
            if scores[labels.index("Jambes")] == 0: msg += " Il faudra penser à les travailler un jour..."
            st.markdown(f"<div class='cyber-analysis'>{msg}</div>", unsafe_allow_html=True)
        st.markdown("### 🏅 Hall of Fame")
        m_filt = st.multiselect("Filtrer par muscle :", labels + ["Autre"], default=labels + ["Autre"])
        df_p_filt = df_p[df_p["Muscle"].isin(m_filt)]
        if not df_p_filt.empty:
            podium = df_p_filt.groupby("Exercice").agg({"1RM": "max"}).sort_values(by="1RM", ascending=False).head(3)
            p_cols = st.columns(3); meds, clss = ["🥇 OR", "🥈 ARGENT", "🥉 BRONZE"], ["podium-gold", "podium-silver", "podium-bronze"]
            for idx, (ex_n, row) in enumerate(podium.iterrows()):
                with p_cols[idx]: st.markdown(f"<div class='podium-card {clss[idx]}'><small>{meds[idx]}</small><br><b>{ex_n}</b><br><span style='color:#58CCFF; font-size:22px;'>{row['1RM']:.1f}kg</span></div>", unsafe_allow_html=True)
        
        st.divider(); sel_e = st.selectbox("🎯 Zoom mouvement :", sorted(df_h["Exercice"].unique()))
        df_e = df_h[df_h["Exercice"] == sel_e].copy(); df_rec = df_e[(df_e["Poids"] > 0) | (df_e["Reps"] > 0)].copy()
        if not df_rec.empty:
            best = df_rec.sort_values(["Poids", "Reps"], ascending=False).iloc[0]; one_rm = calc_1rm(best['Poids'], best['Reps'])
            c1r, c2r = st.columns(2)
            c1r.success(f"🏆 RECORD RÉEL\n\n**{best['Poids']}kg x {int(best['Reps'])}**")
            c2r.info(f"⚡ 1RM ESTIMÉ\n\n**{one_rm:.1f} kg**")
            with st.expander("📊 Estimation Rep Max"):
                ests = get_rep_estimations(one_rm); cols = st.columns(len(ests))
                for idx, (r, p) in enumerate(ests.items()): cols[idx].metric(f"{r} Reps", f"{p}kg")
            fig_l = go.Figure(); c_dat = df_rec.groupby("Semaine")["Poids"].max().reset_index()
            fig_l.add_trace(go.Scatter(x=c_dat["Semaine"], y=c_dat["Poids"], mode='markers+lines', line=dict(color='#58CCFF', width=3), marker=dict(size=10, color='#00FF7F')))
            fig_l.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=10, b=0), height=300)
            st.plotly_chart(fig_l, use_container_width=True, config={'staticPlot': True})
        st.dataframe(df_e[["Semaine", "Série", "Reps", "Poids", "Remarque", "Muscle"]].sort_values("Semaine", ascending=False), hide_index=True)

# --- ONGLET MINI-JEU ---
with tab_g:
    muscle_flappy_game()
