import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import plotly.graph_objects as go
import streamlit.components.v1 as components

# ── Fuseau horaire Europe/Paris (toutes les dates de l'app passent par là) ──
PARIS_TZ = ZoneInfo("Europe/Paris")
def now_paris():
    """Datetime maintenant en heure de Paris."""
    return datetime.now(PARIS_TZ)
def today_paris():
    """Date du jour en heure de Paris (date pure, sans heure)."""
    return now_paris().date()
def today_paris_str():
    """Date du jour Paris au format YYYY-MM-DD."""
    return today_paris().strftime("%Y-%m-%d")

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Muscu Tracker PRO", layout="centered", page_icon="💪")

# Initialiser les paramètres de l'app (SANS OPTIONS)
if 'settings' not in st.session_state:
    st.session_state.settings = {
        'auto_collapse': True,
        'show_1rm': True,
        'show_previous_weeks': 2,
        'theme_animations': True
    }

if 'editing_exo' not in st.session_state:
    st.session_state.editing_exo = set()

if 'view' not in st.session_state:
    st.session_state.view = 'accueil'

if 'mode_seance' not in st.session_state:
    st.session_state.mode_seance = None   # 'prefaite' | 'libre' | None

if 'seance_selectionnee' not in st.session_state:
    st.session_state.seance_selectionnee = None

if 'seance_libre_exos' not in st.session_state:
    st.session_state.seance_libre_exos = []   # [{"name":str,"muscle":str,"sets":int}]

if 'switch_to_seance' not in st.session_state:
    st.session_state.switch_to_seance = False

# Exos ajoutés à la volée à une séance pré-faite (variantes du même exo, etc.)
# Format : { "Nom Séance": [ {"name","muscle","sets"}, ... ] }
if 'extra_exos' not in st.session_state:
    st.session_state.extra_exos = {}

# Date cible d'une séance lancée depuis le calendrier accueil (rattrapage possible)
# Format : "YYYY-MM-DD" ou None (= utiliser today_paris)
if 'seance_target_date' not in st.session_state:
    st.session_state.seance_target_date = None

# --- 2. CSS : DESIGN CYBER-RPG MOBILE-FRIENDLY ---
animations_css = """
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }
    
    @keyframes glow {
        0%, 100% { box-shadow: 0 0 5px #58CCFF; }
        50% { box-shadow: 0 0 20px #58CCFF, 0 0 30px #58CCFF; }
    }
    
    @keyframes slideIn {
        from { transform: translateX(-20px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-10px); }
    }
""" if st.session_state.settings['theme_animations'] else ""

st.markdown(f"""
<style>
    {animations_css}
    
    /* Fix scroll horizontal et mobile */
    .main .block-container {{
        max-width: 100%;
        padding-left: 1rem;
        padding-right: 1rem;
    }}
    
    .main {{
        overflow-x: hidden !important;
    }}
    
    .stApp {{
        background: radial-gradient(circle at 50% 0%, rgba(10, 50, 100, 0.4) 0%, transparent 50%),
                    linear-gradient(180deg, #050A18 0%, #000000 100%);
        background-attachment: fixed; 
        color: #F0F2F6;
        overflow-x: hidden;
    }}
    
    .stExpander {{
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(74, 144, 226, 0.3) !important;
        border-radius: 15px !important; 
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6) !important; 
        margin-bottom: 15px;
        {'animation: slideIn 0.3s ease-out;' if st.session_state.settings['theme_animations'] else ''}
    }}
    
    h1, h2, h3 {{ 
        letter-spacing: 1.5px; 
        text-transform: uppercase; 
        color: #FFFFFF; 
        text-shadow: 2px 2px 8px rgba(0,0,0,0.7);
        {'animation: slideIn 0.5s ease-out;' if st.session_state.settings['theme_animations'] else ''}
    }}
    
    div[data-testid="stMetricValue"] {{ 
        font-family: 'Courier New', monospace; 
        font-size: 38px !important; 
        color: #58CCFF !important; 
        font-weight: 900; 
        text-shadow: 0 0 20px rgba(88, 204, 255, 0.6) !important;
        {'animation: pulse 2s infinite;' if st.session_state.settings['theme_animations'] else ''}
    }}
    
    .rank-ladder {{ 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        background: rgba(255,255,255,0.05); 
        padding: 15px; 
        border-radius: 15px; 
        border: 1px solid #58CCFF; 
        margin-bottom: 30px;
        {'animation: glow 3s infinite;' if st.session_state.settings['theme_animations'] else ''}
    }}
    
    .rank-step {{ 
        text-align: center; 
        flex: 1; 
        opacity: 0.5; 
        font-size: 9px; 
        transition: all 0.3s ease;
    }}
    
    .rank-step.active {{ 
        opacity: 1; 
        font-weight: bold; 
        transform: scale(1.15); 
        color: #58CCFF;
        {'animation: float 2s ease-in-out infinite;' if st.session_state.settings['theme_animations'] else ''}
    }}
    
    .rank-step.completed {{ color: #00FF7F; opacity: 0.8; }}
    
    .xp-bar-bg {{ 
        width: 100%; 
        background: rgba(255,255,255,0.1); 
        border-radius: 10px; 
        height: 12px; 
        overflow: hidden; 
        border: 1px solid rgba(88, 204, 255, 0.3); 
    }}
    
    .xp-bar-fill {{ 
        height: 100%; 
        background: linear-gradient(90deg, #58CCFF, #00FF7F); 
        box-shadow: 0 0 15px #58CCFF;
        transition: width 1s ease-out;
    }}

    .vol-container {{ 
        background: rgba(255,255,255,0.05); 
        border-radius: 10px; 
        padding: 10px; 
        border: 1px solid rgba(88, 204, 255, 0.2);
        {'animation: slideIn 0.5s ease-out;' if st.session_state.settings['theme_animations'] else ''}
    }}
    
    .vol-bar {{ 
        height: 12px; 
        border-radius: 6px; 
        background: #58CCFF; 
        transition: width 0.8s ease-in-out; 
        box-shadow: 0 0 10px #58CCFF; 
    }}
    
    .vol-overload {{ 
        background: #00FF7F !important; 
        box-shadow: 0 0 15px #00FF7F !important;
        {'animation: pulse 1.5s infinite;' if st.session_state.settings['theme_animations'] else ''}
    }}

    .podium-card {{ 
        background: rgba(255, 255, 255, 0.07); 
        border-radius: 12px; 
        padding: 15px; 
        text-align: center; 
        margin-bottom: 10px; 
        border-top: 4px solid #58CCFF;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }}
    
    .podium-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(88, 204, 255, 0.4);
    }}
    
    .podium-gold {{ 
        border-color: #FFD700 !important; 
        box-shadow: 0 0 15px rgba(255, 215, 0, 0.2);
        {'animation: glow 2s infinite;' if st.session_state.settings['theme_animations'] else ''}
    }}
    
    .podium-silver {{ 
        border-color: #C0C0C0 !important; 
        box-shadow: 0 0 15px rgba(192, 192, 192, 0.2); 
    }}
    
    .podium-bronze {{ 
        border-color: #CD7F32 !important; 
        box-shadow: 0 0 15px rgba(205, 127, 50, 0.2); 
    }}
    
    .recup-container {{ 
        display: flex; 
        gap: 10px; 
        overflow-x: auto; 
        padding: 10px 0; 
        margin-bottom: 20px; 
    }}
    
    .recup-card {{ 
        min-width: 85px; 
        background: rgba(255,255,255,0.05); 
        border: 1px solid rgba(255,255,255,0.1); 
        border-radius: 10px; 
        padding: 8px; 
        text-align: center;
        transition: transform 0.2s ease;
    }}
    
    .recup-card:hover {{
        transform: scale(1.05);
    }}
    
    .status-dot {{ 
        height: 10px; 
        width: 10px; 
        border-radius: 50%; 
        display: inline-block; 
        margin-right: 5px;
        {'animation: pulse 2s infinite;' if st.session_state.settings['theme_animations'] else ''}
    }}

    .cyber-analysis {{ 
        background: rgba(88, 204, 255, 0.05); 
        border-left: 4px solid #58CCFF; 
        padding: 15px; 
        border-radius: 0 10px 10px 0; 
        margin-bottom: 20px; 
        font-size: 0.9rem;
        {'animation: slideIn 0.6s ease-out;' if st.session_state.settings['theme_animations'] else ''}
    }}
    
    /* Mobile responsiveness */
    @media (max-width: 768px) {{
        .rank-step {{
            font-size: 7px;
        }}

        .recup-card {{
            min-width: 75px;
            padding: 6px;
        }}
    }}

    /* Navigation persistante */
    div[data-testid="stHorizontalBlock"]:has(button[data-testid^="stBaseButton"]:first-child) {{
        gap: 4px;
        margin-bottom: 8px;
    }}
    .nav-active button {{
        background: linear-gradient(135deg, #58CCFF, #0077AA) !important;
        border-color: #58CCFF !important;
        color: white !important;
        font-weight: bold !important;
    }}

    /* Bloquer le curseur de déplacement sur les data editors */
    [data-testid="stDataEditorResizable"] canvas,
    [data-testid="stDataFrame"] canvas {{
        cursor: default !important;
        user-drag: none !important;
        -webkit-user-drag: none !important;
    }}
</style>
""", unsafe_allow_html=True)

# Bloquer le drag des colonnes dans st.data_editor via JS
components.html("""
<script>
(function() {
    function blockColumnDrag() {
        var editors = window.parent.document.querySelectorAll('[data-testid="stDataEditorResizable"] canvas, [data-testid="stDataFrame"] canvas');
        editors.forEach(function(canvas) {
            if (!canvas._dragBlocked) {
                canvas._dragBlocked = true;
                canvas.addEventListener('mousedown', function(e) {
                    var rect = canvas.getBoundingClientRect();
                    var scaleY = canvas.height / rect.height;
                    var y = (e.clientY - rect.top) * scaleY;
                    if (y < 36 * scaleY) { e.stopImmediatePropagation(); }
                }, true);
                canvas.addEventListener('touchstart', function(e) {
                    var rect = canvas.getBoundingClientRect();
                    var scaleY = canvas.height / rect.height;
                    var touch = e.touches[0];
                    var y = (touch.clientY - rect.top) * scaleY;
                    if (y < 36 * scaleY) { e.stopImmediatePropagation(); }
                }, true);
            }
        });
    }
    var observer = new MutationObserver(blockColumnDrag);
    observer.observe(window.parent.document.body, { childList: true, subtree: true });
    blockColumnDrag();
})();
</script>
""", height=0)


# ============================================================
# 3. FONCTIONS TECHNIQUES (calculs muscu, helpers data)
# ============================================================

def calc_1rm(weight, reps):
    """Estimation Epley du 1RM (charge maxi théorique pour 1 répétition)."""
    return weight * (1 + reps / 30) if reps > 0 else 0

def get_rep_estimations(one_rm):
    """Renvoie un dict {n_reps: poids_estimé} basé sur le 1RM."""
    return {r: round(one_rm * pct, 1) for r, pct in {1: 1.0, 3: 0.94, 5: 0.89, 8: 0.81, 10: 0.75, 12: 0.71}.items()}

def get_base_name(full_name):
    """Retire la variante entre parenthèses : 'Développé couché (Barre)' -> 'Développé couché'."""
    return full_name.split("(")[0].strip() if "(" in full_name else full_name

def fix_muscle(exercice, muscle):
    """Corrige les valeurs de muscle legacy ('Bras', 'Jambes', 'Autre', NaN) via auto_muscles."""
    import pandas as _pd
    if _pd.isna(muscle) or str(muscle) in ("Bras", "Jambes", "Autre", "nan", ""):
        result = auto_muscles(get_base_name(str(exercice)))
        if result:
            return result
        return "Autre"
    return str(muscle)

def auto_muscles(name):
    """Retourne muscles comma-separated basé sur le nom d'exercice, ou None si inconnu."""
    n = name.lower()
    muscles = set()
    rules = [
        # POITRINE — pas de Triceps (muscle secondaire, pas primaire)
        (["écarté","fly","pec deck","butterfly","cable crossover","poulie croisée","crossover"], ["Pecs"]),
        (["dips"], ["Pecs"]),
        (["pompe","push-up","pushup","push up"], ["Pecs"]),
        (["développé couché","bench press","dc haltères","dc barre"], ["Pecs"]),
        (["développé incliné","di haltères","di barre"], ["Pecs"]),
        (["développé décliné","dd "], ["Pecs"]),
        (["développé"], ["Pecs"]),
        # DOS — pas de Biceps (muscle secondaire, pas primaire)
        (["traction","pull-up","pullup","chin-up","chinup","chin up"], ["Dos"]),
        (["tirage","lat machine","lat pull","lat pulldown"], ["Dos"]),
        (["rowing","row","t-bar","barre t"], ["Dos"]),
        (["pull-over","pullover"], ["Dos","Pecs"]),
        (["hyperextension","back extension","good morning"], ["Dos","Ischio-jambiers"]),
        (["soulevé de terre","deadlift","sdt","sumo"], ["Dos","Ischio-jambiers","Fessiers"]),
        # ÉPAULES — pas de Triceps
        (["développé militaire","overhead press","ohp","military press","press assis","press debout","shoulder press"], ["Épaules"]),
        (["arnold"], ["Épaules"]),
        (["élévation latérale","lateral raise","élévation lat"], ["Épaules"]),
        (["élévation frontale","front raise","élévation front"], ["Épaules"]),
        (["oiseau","reverse fly","rear delt","oiseau"], ["Épaules"]),
        (["face pull"], ["Épaules","Dos"]),
        (["shrug","haussement"], ["Épaules"]),
        (["upright row","tirage menton"], ["Épaules","Biceps"]),
        # BICEPS
        (["curl marteau","hammer curl","marteau"], ["Biceps"]),
        (["reverse curl","curl inversé"], ["Biceps"]),
        (["curl barre","curl haltère","curl poulie","curl concentré","curl incliné","curl scott","preacher curl","zottman"], ["Biceps"]),
        (["curl"], ["Biceps"]),
        (["biceps"], ["Biceps"]),
        # TRICEPS
        (["skull crusher","barre front","jm press","lying extension","extension nuque"], ["Triceps"]),
        (["pushdown","tirage poulie triceps","corde triceps","triceps poulie","poulie triceps"], ["Triceps"]),
        (["kick-back triceps","kickback triceps"], ["Triceps"]),
        (["extension triceps","triceps barre","extension haltère"], ["Triceps"]),
        (["triceps"], ["Triceps"]),
        # AVANT-BRAS
        (["poignet","wrist curl","avant-bras","forearm"], ["Avant-bras"]),
        # ABDOS
        (["crunch","sit-up","situp"], ["Abdos"]),
        (["gainage","planche","plank"], ["Abdos"]),
        (["relevé de jambe","leg raise","hanging leg","knee raise"], ["Abdos"]),
        (["rotation","twist","russian","oblique"], ["Abdos"]),
        (["abdos","abdominal","ab "], ["Abdos"]),
        (["roue abdos","wheel"], ["Abdos"]),
        # QUADRICEPS
        (["leg extension","extension cuisse","extension jambe"], ["Quadriceps"]),
        (["hack squat"], ["Quadriceps"]),
        (["split squat","bulgare","bulgarian"], ["Quadriceps","Fessiers","Ischio-jambiers"]),
        (["fente","lunge","walking lunge"], ["Quadriceps","Fessiers","Ischio-jambiers"]),
        (["leg press","presse à cuisse","presse cuisse","presse jambe"], ["Quadriceps","Fessiers"]),
        (["goblet"], ["Quadriceps","Fessiers"]),
        (["squat","back squat","front squat","box squat"], ["Quadriceps","Fessiers"]),
        (["presse"], ["Quadriceps","Fessiers"]),
        # ISCHIO-JAMBIERS
        (["leg curl","curl jambe","ischio","lying leg curl","seated leg curl","nordic"], ["Ischio-jambiers"]),
        (["rdl","romanian","roumain","soulevé jambe tendue","stiff leg"], ["Ischio-jambiers","Fessiers"]),
        # FESSIERS
        (["hip thrust","hip-thrust","hip extension"], ["Fessiers"]),
        (["abduction","écartement cuisse"], ["Fessiers"]),
        (["kickback","kick-back","donkey kick"], ["Fessiers","Ischio-jambiers"]),
        (["glute bridge","fessier","glute"], ["Fessiers"]),
        # MOLLETS
        (["mollet","calf raise","calves","talon","standing calf","seated calf"], ["Mollets"]),
    ]
    for keywords, ms in rules:
        if any(kw in n for kw in keywords):
            muscles.update(ms)
    return ",".join(sorted(muscles)) if muscles else None

def render_table(df, hist_prev=None):
    """Affiche un DataFrame comme tableau HTML statique (pas de glissement mobile)."""
    col_styles = {
        "Série":   "width:40px; text-align:center;",
        "Reps":    "width:44px; text-align:center;",
        "Poids":   "width:56px; text-align:center;",
        "Remarque":"text-align:left;",
        "Semaine": "width:60px; text-align:center;",
        "Muscle":  "text-align:left;",
    }
    th_base = "padding:6px 8px; color:#58CCFF; font-weight:600; border-bottom:1px solid rgba(88,204,255,0.2);"
    td_base = "padding:5px 8px; border-bottom:1px solid rgba(255,255,255,0.05);"
    html = "<div style='background:rgba(255,255,255,0.04); border-radius:10px; overflow:hidden; margin-bottom:8px;'>"
    html += "<table style='width:100%; border-collapse:collapse; font-size:13px;'><thead><tr>"
    for c in df.columns:
        cs = col_styles.get(c, "")
        html += f"<th style='{th_base}{cs}'>{c}</th>"
    html += "</tr></thead><tbody>"
    for _, row in df.iterrows():
        row_bg = ""
        if hist_prev is not None and not hist_prev.empty and "Série" in df.columns:
            prev = hist_prev[hist_prev["Série"] == row["Série"]]
            if not prev.empty:
                pw, cw = float(prev.iloc[0]["Poids"]), float(row["Poids"])
                pr, cr = int(prev.iloc[0]["Reps"]), int(row["Reps"])
                if cw > pw:   row_bg = "background:rgba(0,255,127,0.1);"
                elif cw < pw: row_bg = "background:rgba(255,69,58,0.1);"
                elif cr > pr: row_bg = "background:rgba(0,255,127,0.07);"
                elif cr < pr: row_bg = "background:rgba(255,69,58,0.07);"
        html += f"<tr style='{row_bg}'>"
        for c, v in zip(df.columns, row):
            cs = col_styles.get(c, "")
            cell = f"{v:g}" if isinstance(v, float) else str(v) if v is not None else ""
            html += f"<td style='{td_base}{cs}'>{cell}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)

# ============================================================
# 4. MINI-JEUX (Flappy & Rep Crusher) - canvas HTML+JS embarqués
# ============================================================

def muscle_flappy_game():
    st.markdown("### 💪 MUSCLE FLAPPY")
    
    game_html = """
    <div style="text-align: center; width: 100%; max-width: 400px; margin: 0 auto;">
        <canvas id="flappyCanvas" width="360" height="540" style="
            border: 2px solid #FF453A; 
            border-radius: 10px; 
            background: #050A18;
            width: 100%;
            height: auto;
            max-width: 360px;
            display: block;
            touch-action: none;
            -webkit-tap-highlight-color: transparent;
        "></canvas>
    </div>
    <script>
        const canvas = document.getElementById('flappyCanvas');
        const ctx = canvas.getContext('2d');
        
        canvas.style.touchAction = 'none';
        
        // Détecter mobile vs desktop
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        
        // Paramètres adaptatifs - GRAVITÉ TRÈS FAIBLE POUR FLOATER
        let biceps = { 
            x: 60, 
            y: 200, 
            w: 35, 
            h: 35, 
            gravity: isMobile ? 0.15 : 0.35,  // Gravité réduite pour flotter
            velocity: 0, 
            lift: isMobile ? -5.5 : -7.5,     // Saut ajusté
            maxVelocity: 8                     // Vitesse max réduite
        };
        
        let pipes = []; 
        let frameCount = 0; 
        let score = 0; 
        let gameOver = false; 
        let gameStarted = false;
        let baseSpeed = isMobile ? 1.2 : 2.5;  // Vitesse réduite
        let record = localStorage.getItem('muscleFlappyRecord') || 0;
        
        function reset() { 
            biceps.y = 200; 
            biceps.velocity = 0;
            pipes = []; 
            score = 0; 
            frameCount = 0;
            gameOver = false; 
            gameStarted = false; 
        }
        
        function handleAction(e) { 
            e.preventDefault(); 
            if (gameOver) { 
                reset(); 
            } else if (!gameStarted) { 
                gameStarted = true; 
                biceps.velocity = biceps.lift;
            } else { 
                biceps.velocity = biceps.lift;
            } 
        }
        
        canvas.addEventListener('mousedown', handleAction);
        canvas.addEventListener('touchstart', handleAction, {passive: false});
        canvas.addEventListener('touchend', (e) => e.preventDefault(), {passive: false});
        canvas.addEventListener('touchmove', (e) => e.preventDefault(), {passive: false});
        
        function draw() {
            ctx.fillStyle = '#050A18';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            ctx.font = "40px Arial";
            ctx.fillText("💪", biceps.x, biceps.y);
            
            if (gameStarted && !gameOver) {
                biceps.velocity += biceps.gravity;
                biceps.velocity = Math.min(biceps.velocity, biceps.maxVelocity);
                biceps.y += biceps.velocity;
                
                let currentSpeed = baseSpeed + (Math.floor(score / 20) * 0.1);  // Progression lente
                
                // Obstacles TRÈS ESPACÉS - AUGMENTÉ
                let spawnInterval = isMobile ? 220 : 280;  // Encore plus espacés
                if (frameCount % spawnInterval === 0) {
                    let gap = 220;  // Gap très large
                    let minTop = 100;
                    let maxTop = canvas.height - gap - 100;
                    let topH = Math.floor(Math.random() * (maxTop - minTop)) + minTop;
                    
                    pipes.push({ 
                        x: canvas.width, 
                        topH: topH, 
                        gap: gap, 
                        passed: false 
                    }); 
                }
                
                for (let i = pipes.length - 1; i >= 0; i--) {
                    pipes[i].x -= currentSpeed;
                    
                    ctx.fillStyle = "#FF453A";
                    ctx.fillRect(pipes[i].x, 0, 65, pipes[i].topH);
                    ctx.fillRect(pipes[i].x, pipes[i].topH + pipes[i].gap, 65, canvas.height);
                    
                    ctx.fillStyle = '#AA0000';
                    ctx.fillRect(pipes[i].x, pipes[i].topH - 25, 65, 25);
                    ctx.fillRect(pipes[i].x, pipes[i].topH + pipes[i].gap, 65, 25);
                    
                    // Collision fixée - hitbox plus précise (emoji ~30x30px)
                    let bLeft = biceps.x - 10;
                    let bRight = biceps.x + 20;
                    let bTop = biceps.y - 15;
                    let bBottom = biceps.y + 15;
                    
                    if (bRight > pipes[i].x && bLeft < pipes[i].x + 65) { 
                        if (bTop < pipes[i].topH || bBottom > pipes[i].topH + pipes[i].gap) {
                            gameOver = true;
                        }
                    }
                    
                    if (!pipes[i].passed && biceps.x > pipes[i].x + 65) { 
                        score++; 
                        pipes[i].passed = true;
                    }
                    
                    if (pipes[i].x < -80) pipes.splice(i, 1);
                }
                
                if (biceps.y > canvas.height - 20 || biceps.y < 20) {
                    gameOver = true;
                }
            } else if (!gameStarted) { 
                ctx.fillStyle = "white"; 
                ctx.font = "bold 22px Arial"; 
                ctx.fillText("MUSCLE FLAPPY", 100, 260);
                ctx.font = "16px Arial";
                ctx.fillText("Clique pour démarrer", 105, 300);
            }
            
            if (gameOver) { 
                if (score > record) { 
                    record = score; 
                    localStorage.setItem('muscleFlappyRecord', record); 
                } 
                ctx.fillStyle = "rgba(255,69,58,0.8)"; 
                ctx.fillRect(0,0, canvas.width, canvas.height); 
                ctx.fillStyle = "white"; 
                ctx.font = "bold 32px Arial";
                ctx.fillText("GAME OVER", 95, 250);
                ctx.font = "18px Arial";
                ctx.fillText("Score: " + score, 140, 300); 
                ctx.fillText("Record: " + record, 135, 330); 
                ctx.font = "15px Arial";
                ctx.fillText("Clique pour recommencer", 95, 380);
            }
            
            ctx.font = "bold 22px Arial"; 
            ctx.fillStyle = "#00FF7F";
            ctx.fillText("⚡ " + score, 25, 40);
            ctx.fillStyle = "#FFD700";
            ctx.fillText("🏆 " + record, 270, 40);
            
            frameCount++; 
            requestAnimationFrame(draw);
        }
        draw();
    </script>
    """
    components.html(game_html, height=580)

def rep_crusher_game():
    st.markdown("### 🏋️ REP CRUSHER")
    
    game_html = """
    <div style="text-align: center; width: 100%; max-width: 400px; margin: 0 auto;">
        <canvas id="repCanvas" width="360" height="540" style="
            border: 2px solid #00FF7F; 
            border-radius: 10px; 
            background: #050A18;
            width: 100%;
            height: auto;
            max-width: 360px;
            display: block;
            touch-action: none;
            -webkit-tap-highlight-color: transparent;
        "></canvas>
    </div>
    <script>
        const canvas2 = document.getElementById('repCanvas');
        const ctx2 = canvas2.getContext('2d');
        
        canvas2.style.touchAction = 'none';
        
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        
        let barbell = { x: 140, y: 470, w: 100, h: 12 };
        let plates = [];
        let score = 0;
        let combo = 0;
        let maxCombo = localStorage.getItem('repCrusherMaxCombo') || 0;
        let gameOver = false;
        let gameStarted = false;
        let frameCount = 0;
        let speed = isMobile ? 1 : 2;
        let mouseX = 180;
        
        const colors = ['#FF453A', '#00FF7F', '#58CCFF', '#FFD700', '#FF00FF', '#FFA500'];
        
        function reset() {
            barbell = { x: 140, y: 470, w: 100, h: 12 };
            plates = [];
            score = 0;
            combo = 0;
            gameOver = false;
            gameStarted = false;
            frameCount = 0;
            speed = isMobile ? 1 : 2;
        }
        
        function spawnPlate() {
            plates.push({
                x: Math.random() * (canvas2.width - 120) + 60,
                y: -40,
                w: 50,
                h: 35,
                color: colors[Math.floor(Math.random() * colors.length)],
                caught: false
            });
        }
        
        function handleMouseDown(e) {
            e.preventDefault();
            if (gameOver) {
                reset();
            } else if (!gameStarted) {
                gameStarted = true;
                spawnPlate();
            }
        }
        
        canvas2.addEventListener('mousedown', handleMouseDown);
        canvas2.addEventListener('touchstart', handleMouseDown, {passive: false});
        
        canvas2.addEventListener('mousemove', (e) => {
            if (gameStarted && !gameOver) {
                const rect = canvas2.getBoundingClientRect();
                mouseX = e.clientX - rect.left;
                barbell.x = mouseX - barbell.w / 2;
                barbell.x = Math.max(10, Math.min(barbell.x, canvas2.width - barbell.w - 10));
            }
        });
        
        canvas2.addEventListener('touchmove', (e) => {
            e.preventDefault();
            if (gameStarted && !gameOver) {
                const rect = canvas2.getBoundingClientRect();
                const touch = e.touches[0];
                mouseX = touch.clientX - rect.left;
                barbell.x = mouseX - barbell.w / 2;
                barbell.x = Math.max(10, Math.min(barbell.x, canvas2.width - barbell.w - 10));
            }
        }, {passive: false});
        
        function draw() {
            ctx2.fillStyle = '#050A18';
            ctx2.fillRect(0, 0, canvas2.width, canvas2.height);
            
            if (gameStarted && !gameOver) {
                speed = (isMobile ? 1 : 2) + (score / 25);
                
                if (frameCount % Math.max(45, 90 - score * 1.5) === 0) {
                    spawnPlate();
                }
                
                for (let i = plates.length - 1; i >= 0; i--) {
                    let plate = plates[i];
                    
                    if (!plate.caught) {
                        plate.y += speed;
                        
                        if (plate.y + plate.h > barbell.y && 
                            plate.y < barbell.y + barbell.h &&
                            plate.x + plate.w > barbell.x && 
                            plate.x < barbell.x + barbell.w) {
                            plate.caught = true;
                            score++;
                            combo++;
                            maxCombo = Math.max(combo, maxCombo);
                            localStorage.setItem('repCrusherMaxCombo', maxCombo);
                        }
                        
                        if (plate.y > canvas2.height) {
                            plates.splice(i, 1);
                            if (combo > 0) combo = 0;
                            if (score > 0) gameOver = true;
                            continue;
                        }
                    } else {
                        plate.y = barbell.y - plate.h - 2;
                        plate.x = barbell.x + barbell.w / 2 - plate.w / 2;
                    }
                    
                    ctx2.fillStyle = plate.color;
                    ctx2.fillRect(plate.x, plate.y, plate.w, plate.h);
                    
                    ctx2.fillStyle = 'rgba(0,0,0,0.3)';
                    ctx2.fillRect(plate.x + 6, plate.y + 6, plate.w - 12, plate.h - 12);
                    
                    ctx2.fillStyle = 'white';
                    ctx2.font = 'bold 14px Arial';
                    ctx2.fillText('20kg', plate.x + 10, plate.y + 22);
                }
                
                ctx2.fillStyle = '#00FF7F';
                ctx2.fillRect(barbell.x, barbell.y, barbell.w, barbell.h);
                
                ctx2.fillStyle = '#00AA00';
                ctx2.fillRect(barbell.x - 12, barbell.y - 8, 12, 28);
                ctx2.fillRect(barbell.x + barbell.w, barbell.y - 8, 12, 28);
                
                if (combo >= 3) {
                    ctx2.fillStyle = '#FFD700';
                    ctx2.font = 'bold 18px Arial';
                    ctx2.fillText('🔥 x' + combo, canvas2.width/2 - 30, 75);
                }
                
            } else if (!gameStarted) {
                ctx2.fillStyle = 'white';
                ctx2.font = 'bold 20px Arial';
                ctx2.fillText('REP CRUSHER', 110, 250);
                ctx2.font = '14px Arial';
                ctx2.fillText('Clique pour démarrer', 105, 290);
            }
            
            if (gameOver) {
                ctx2.fillStyle = 'rgba(255, 69, 58, 0.85)';
                ctx2.fillRect(0, 0, canvas2.width, canvas2.height);
                
                ctx2.fillStyle = 'white';
                ctx2.font = 'bold 28px Arial';
                ctx2.fillText('DISQUE RATÉ !', 90, 240);
                
                ctx2.font = '16px Arial';
                ctx2.fillText('Reps: ' + score, 145, 290);
                ctx2.fillText('Max Combo: ' + maxCombo, 120, 320);
                ctx2.font = '14px Arial';
                ctx2.fillText('Clique pour recommencer', 95, 370);
            }
            
            ctx2.font = 'bold 20px Arial';
            ctx2.fillStyle = '#00FF7F';
            ctx2.fillText('💪 ' + score, 20, 38);
            
            ctx2.fillStyle = '#FFD700';
            ctx2.fillText('🔥 ' + combo, 20, 63);
            
            ctx2.fillStyle = '#58CCFF';
            ctx2.fillText('🏆 ' + maxCombo, 270, 38);
            
            frameCount++;
            requestAnimationFrame(draw);
        }
        draw();
    </script>
    """
    components.html(game_html, height=580)


# ============================================================
# 5. CARTE DU CORPS INTERACTIVE (SVG anatomique colorisé selon 1RM)
# ============================================================

def body_map_section(df_p):
    MUSCLES = {
        "Pecs":            {"std": 140, "zid_f": "z-pecs",    "zid_b": None},
        "Dos":             {"std": 160, "zid_f": None,         "zid_b": "z-dos"},
        "Épaules":         {"std": 90,  "zid_f": "z-epaules",  "zid_b": "z-epaules-b"},
        "Biceps":          {"std": 60,  "zid_f": "z-biceps",   "zid_b": None},
        "Triceps":         {"std": 70,  "zid_f": None,         "zid_b": "z-triceps"},
        "Avant-bras":      {"std": 45,  "zid_f": "z-avbras",   "zid_b": "z-avbras-b"},
        "Abdos":           {"std": 60,  "zid_f": "z-abdos",    "zid_b": None},
        "Quadriceps":      {"std": 180, "zid_f": "z-quad",     "zid_b": None},
        "Ischio-jambiers": {"std": 110, "zid_f": None,         "zid_b": "z-ischio"},
        "Fessiers":        {"std": 140, "zid_f": None,         "zid_b": "z-fessiers"},
        "Mollets":         {"std": 110, "zid_f": "z-mollets",  "zid_b": "z-mollets-b"},
        "Bras":            {"std": 60,  "zid_f": "z-biceps",   "zid_b": None},
        "Jambes":          {"std": 180, "zid_f": "z-quad",     "zid_b": None},
    }
    DISPLAY_MUSCLES = [m for m in MUSCLES if m not in ("Bras", "Jambes")]

    def get_col(pct):
        if pct == 0:    return "#1a2a3a"
        elif pct < 40:  return "#FF453A"
        elif pct < 70:  return "#FF9F0A"
        elif pct < 95:  return "#58CCFF"
        else:           return "#00FF7F"

    def sid(m):
        return m.lower().replace("é","e").replace("è","e").replace("ê","e").replace("à","a").replace("â","a").replace("î","i").replace("-","").replace(" ","")

    def muscle_df(m):
        if df_p.empty: return pd.DataFrame()
        return df_p[df_p["Muscle"].str.contains(m, regex=False, na=False)]

    sc = {}
    for m, info in MUSCLES.items():
        md = muscle_df(m)
        rm = md["1RM"].max() if not md.empty else 0
        pct = min((rm / info["std"]) * 100, 120) if info["std"] > 0 else 0
        sc[m] = {"pct": pct, "col": get_col(pct), "rm": rm, "std": info["std"]}

    def mf(m, pfx):
        return f"url(#{pfx}{sid(m)})" if sc[m]["pct"] > 0 else "#1a2a3a"
    def mop(m):
        return "0.92" if sc[m]["pct"] > 0 else "0.12"

    def make_grads(pfx):
        g = ""
        for m in DISPLAY_MUSCLES:
            c = sc[m]["col"]
            if sc[m]["pct"] > 0:
                g += (f'<radialGradient id="{pfx}{sid(m)}" cx="50%" cy="32%" r="62%">'
                      f'<stop offset="0%" stop-color="{c}" stop-opacity="1"/>'
                      f'<stop offset="50%" stop-color="{c}" stop-opacity="0.7"/>'
                      f'<stop offset="100%" stop-color="{c}" stop-opacity="0.06"/>'
                      f'</radialGradient>')
        return g

    grads_f = make_grads("gf")
    grads_b = make_grads("gb")

    muscle_data = {}
    for m in DISPLAY_MUSCLES:
        md = muscle_df(m)
        best_w, best_r = 0, 0
        last_sessions, exos, evo = [], [], []
        if not md.empty:
            md_v = md[md["Reps"] > 0].copy()
            if not md_v.empty:
                best_idx = md_v.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1).idxmax()
                best_w = float(md_v.loc[best_idx, "Poids"])
                best_r = int(md_v.loc[best_idx, "Reps"])
                for wk in sorted(md_v["Semaine"].unique(), reverse=True)[:4]:
                    wk_d = md_v[md_v["Semaine"] == wk]
                    br = wk_d.loc[wk_d["Poids"].idxmax()]
                    last_sessions.append({"s": int(wk), "w": float(br["Poids"]), "r": int(br["Reps"])})
                for exo_name, grp in md_v.groupby("Exercice"):
                    bi = grp.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1).idxmax()
                    br2 = grp.loc[bi]
                    exos.append({"name": str(exo_name), "w": float(br2["Poids"]), "r": int(br2["Reps"])})
                exos = sorted(exos, key=lambda e: e["w"] * (1 + e["r"] / 30), reverse=True)[:4]
                for wk2, grp2 in md_v.groupby("Semaine"):
                    best_rm = grp2.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1).max()
                    evo.append({"w": int(wk2), "r": round(float(best_rm), 1)})
        muscle_data[m] = {
            "pct": round(sc[m]["pct"], 1), "col": sc[m]["col"],
            "rm": round(sc[m]["rm"], 1), "std": sc[m]["std"],
            "zid_f": MUSCLES[m]["zid_f"], "zid_b": MUSCLES[m]["zid_b"],
            "best": {"w": best_w, "r": best_r},
            "last": last_sessions, "exos": exos, "evo": evo,
        }

    data_json = json.dumps(muscle_data, ensure_ascii=False)

    # ─── SVG FACE — corps anatomique réaliste ───────────────────────────────
    svg_front = f"""<svg viewBox="0 0 200 420" width="148" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="gw" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    {grads_f}
  </defs>
  <!-- ── Silhouette ── -->
  <!-- Tête -->
  <ellipse cx="100" cy="33" rx="23" ry="27" fill="#0b1724" stroke="#1c3a58" stroke-width="1.1"/>
  <circle cx="92" cy="28" r="2" fill="#58CCFF" opacity="0.22"/>
  <circle cx="108" cy="28" r="2" fill="#58CCFF" opacity="0.22"/>
  <!-- Cou -->
  <path d="M93,58 C91,64 91,70 92,76 L108,76 C109,70 109,64 107,58 Z" fill="#0b1724" stroke="#1c3a58" stroke-width="0.9"/>
  <!-- Torso (courbes bezier — épaules, taille étroite, hanches) -->
  <path d="M92,76 C84,76 66,72 50,82 C38,88 36,102 38,116 C40,130 46,138 48,150 C50,162 48,174 50,184 L74,196 L78,208 L88,210 C92,212 96,214 100,214 C104,214 108,212 112,210 L122,208 L126,196 L150,184 C152,174 150,162 152,150 C154,138 160,130 162,116 C164,102 162,88 150,82 C134,72 116,76 108,76 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.9" opacity="0.92"/>
  <!-- Bras gauche (upper) -->
  <path d="M50,82 C42,90 36,104 36,120 C36,134 38,142 42,146 C46,150 52,150 56,144 C60,138 60,120 58,106 C56,92 54,82 50,82 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.8" opacity="0.92"/>
  <!-- Avant-bras gauche -->
  <path d="M42,148 C38,158 36,172 38,184 C40,192 44,198 48,198 C52,200 56,198 58,192 C60,186 58,172 56,160 C54,150 50,148 42,148 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <ellipse cx="50" cy="202" rx="10" ry="5.5" fill="#080e1c" stroke="#1c3a58" stroke-width="0.6" opacity="0.5"/>
  <!-- Bras droit (upper) -->
  <path d="M150,82 C158,90 164,104 164,120 C164,134 162,142 158,146 C154,150 148,150 144,144 C140,138 140,120 142,106 C144,92 146,82 150,82 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.8" opacity="0.92"/>
  <!-- Avant-bras droit -->
  <path d="M158,148 C162,158 164,172 162,184 C160,192 156,198 152,198 C148,200 144,198 142,192 C140,186 142,172 144,160 C146,150 150,148 158,148 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <ellipse cx="150" cy="202" rx="10" ry="5.5" fill="#080e1c" stroke="#1c3a58" stroke-width="0.6" opacity="0.5"/>
  <!-- Hanches -->
  <ellipse cx="100" cy="196" rx="31" ry="11" fill="#080e1c" stroke="#1c3a58" stroke-width="0.8" opacity="0.8"/>
  <!-- Cuisse gauche -->
  <path d="M70,198 C66,212 64,236 66,264 C68,286 70,300 72,312 C76,320 86,321 90,314 C94,306 92,284 90,258 C88,230 84,206 70,198 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <!-- Cuisse droite -->
  <path d="M130,198 C134,212 136,236 134,264 C132,286 130,300 128,312 C124,320 114,321 110,314 C106,306 108,284 110,258 C112,230 116,206 130,198 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <!-- Tibia gauche -->
  <path d="M72,314 C70,328 68,350 70,372 C72,384 74,392 76,396 C80,400 86,399 88,394 C90,388 90,372 88,352 C86,330 80,316 72,314 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <!-- Tibia droit -->
  <path d="M128,314 C130,328 132,350 130,372 C128,384 126,392 124,396 C120,400 114,399 112,394 C110,388 110,372 112,352 C114,330 120,316 128,314 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <ellipse cx="80" cy="401" rx="18" ry="6" fill="#080e1c" stroke="#1c3a58" stroke-width="0.6" opacity="0.4"/>
  <ellipse cx="120" cy="401" rx="18" ry="6" fill="#080e1c" stroke="#1c3a58" stroke-width="0.6" opacity="0.4"/>

  <!-- ── Zones musculaires FACE ── -->
  <!-- Deltoïdes -->
  <g id="z-epaules" class="zone" onclick="sel('Épaules')"><title>Épaules</title>
    <path d="M48,82 C38,88 34,102 36,116 C38,126 42,134 46,138 C50,134 52,118 52,106 C52,94 50,84 48,82 Z" fill="{mf('Épaules','gf')}" opacity="{mop('Épaules')}" filter="url(#gw)"/>
    <path d="M152,82 C162,88 166,102 164,116 C162,126 158,134 154,138 C150,134 148,118 148,106 C148,94 150,84 152,82 Z" fill="{mf('Épaules','gf')}" opacity="{mop('Épaules')}" filter="url(#gw)"/>
  </g>
  <!-- Pectoraux (forme en éventail) -->
  <g id="z-pecs" class="zone" onclick="sel('Pecs')"><title>Pecs</title>
    <path d="M70,80 C84,72 102,80 104,112 C88,122 72,116 66,102 C64,92 64,84 70,80 Z" fill="{mf('Pecs','gf')}" opacity="{mop('Pecs')}" filter="url(#gw)"/>
    <path d="M130,80 C116,72 98,80 96,112 C112,122 128,116 134,102 C136,92 136,84 130,80 Z" fill="{mf('Pecs','gf')}" opacity="{mop('Pecs')}" filter="url(#gw)"/>
  </g>
  <!-- Biceps (ovale allongé face antérieure du bras) -->
  <g id="z-biceps" class="zone" onclick="sel('Biceps')"><title>Biceps</title>
    <path d="M50,86 C44,98 40,114 42,128 C44,138 48,142 52,138 C56,134 58,118 56,106 C54,94 52,86 50,86 Z" fill="{mf('Biceps','gf')}" opacity="{mop('Biceps')}" filter="url(#gw)"/>
    <path d="M150,86 C156,98 160,114 158,128 C156,138 152,142 148,138 C144,134 142,118 144,106 C146,94 148,86 150,86 Z" fill="{mf('Biceps','gf')}" opacity="{mop('Biceps')}" filter="url(#gw)"/>
  </g>
  <!-- Avant-bras -->
  <g id="z-avbras" class="zone" onclick="sel('Avant-bras')"><title>Avant-bras</title>
    <path d="M42,150 C36,162 34,176 36,188 C38,196 42,200 46,198 C50,196 52,186 52,174 C52,162 48,152 42,150 Z" fill="{mf('Avant-bras','gf')}" opacity="{mop('Avant-bras')}" filter="url(#gw)"/>
    <path d="M158,150 C164,162 166,176 164,188 C162,196 158,200 154,198 C150,196 148,186 148,174 C148,162 152,152 158,150 Z" fill="{mf('Avant-bras','gf')}" opacity="{mop('Avant-bras')}" filter="url(#gw)"/>
  </g>
  <!-- Abdominaux (grille 6-pack) -->
  <g id="z-abdos" class="zone" onclick="sel('Abdos')"><title>Abdos</title>
    <rect x="85" y="110" width="13" height="15" rx="4" fill="{mf('Abdos','gf')}" opacity="{mop('Abdos')}"/>
    <rect x="102" y="110" width="13" height="15" rx="4" fill="{mf('Abdos','gf')}" opacity="{mop('Abdos')}"/>
    <rect x="85" y="129" width="13" height="14" rx="4" fill="{mf('Abdos','gf')}" opacity="{mop('Abdos')}"/>
    <rect x="102" y="129" width="13" height="14" rx="4" fill="{mf('Abdos','gf')}" opacity="{mop('Abdos')}"/>
    <rect x="86" y="147" width="12" height="13" rx="3" fill="{mf('Abdos','gf')}" opacity="{mop('Abdos')}"/>
    <rect x="102" y="147" width="12" height="13" rx="3" fill="{mf('Abdos','gf')}" opacity="{mop('Abdos')}"/>
  </g>
  <!-- Quadriceps (grande zone antérieure de cuisse) -->
  <g id="z-quad" class="zone" onclick="sel('Quadriceps')"><title>Quadriceps</title>
    <path d="M68,200 C64,216 62,240 64,268 C66,290 68,304 70,314 C76,322 86,322 90,314 C94,304 92,280 90,254 C88,226 84,204 68,200 Z" fill="{mf('Quadriceps','gf')}" opacity="{mop('Quadriceps')}" filter="url(#gw)"/>
    <path d="M132,200 C136,216 138,240 136,268 C134,290 132,304 130,314 C124,322 114,322 110,314 C106,304 108,280 110,254 C112,226 116,204 132,200 Z" fill="{mf('Quadriceps','gf')}" opacity="{mop('Quadriceps')}" filter="url(#gw)"/>
  </g>
  <!-- Mollets (tibialis anterior visible de face) -->
  <g id="z-mollets" class="zone" onclick="sel('Mollets')"><title>Mollets</title>
    <path d="M74,316 C70,330 68,352 70,374 C72,386 74,394 76,398 C80,402 86,401 88,396 C90,390 90,372 88,350 C86,328 80,318 74,316 Z" fill="{mf('Mollets','gf')}" opacity="{mop('Mollets')}" filter="url(#gw)"/>
    <path d="M126,316 C130,330 132,352 130,374 C128,386 126,394 124,398 C120,402 114,401 112,396 C110,390 110,372 112,350 C114,328 120,318 126,316 Z" fill="{mf('Mollets','gf')}" opacity="{mop('Mollets')}" filter="url(#gw)"/>
  </g>
</svg>"""

    # ─── SVG DOS — corps anatomique réaliste ────────────────────────────────
    svg_back = f"""<svg viewBox="0 0 200 420" width="148" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="gwb" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    {grads_b}
  </defs>
  <!-- ── Silhouette (identique face) ── -->
  <ellipse cx="100" cy="33" rx="23" ry="27" fill="#0b1724" stroke="#1c3a58" stroke-width="1.1"/>
  <path d="M93,58 C91,64 91,70 92,76 L108,76 C109,70 109,64 107,58 Z" fill="#0b1724" stroke="#1c3a58" stroke-width="0.9"/>
  <path d="M92,76 C84,76 66,72 50,82 C38,88 36,102 38,116 C40,130 46,138 48,150 C50,162 48,174 50,184 L74,196 L78,208 L88,210 C92,212 96,214 100,214 C104,214 108,212 112,210 L122,208 L126,196 L150,184 C152,174 150,162 152,150 C154,138 160,130 162,116 C164,102 162,88 150,82 C134,72 116,76 108,76 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.9" opacity="0.92"/>
  <path d="M50,82 C42,90 36,104 36,120 C36,134 38,142 42,146 C46,150 52,150 56,144 C60,138 60,120 58,106 C56,92 54,82 50,82 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.8" opacity="0.92"/>
  <path d="M42,148 C38,158 36,172 38,184 C40,192 44,198 48,198 C52,200 56,198 58,192 C60,186 58,172 56,160 C54,150 50,148 42,148 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <ellipse cx="50" cy="202" rx="10" ry="5.5" fill="#080e1c" stroke="#1c3a58" stroke-width="0.6" opacity="0.5"/>
  <path d="M150,82 C158,90 164,104 164,120 C164,134 162,142 158,146 C154,150 148,150 144,144 C140,138 140,120 142,106 C144,92 146,82 150,82 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.8" opacity="0.92"/>
  <path d="M158,148 C162,158 164,172 162,184 C160,192 156,198 152,198 C148,200 144,198 142,192 C140,186 142,172 144,160 C146,150 150,148 158,148 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <ellipse cx="150" cy="202" rx="10" ry="5.5" fill="#080e1c" stroke="#1c3a58" stroke-width="0.6" opacity="0.5"/>
  <ellipse cx="100" cy="196" rx="31" ry="11" fill="#080e1c" stroke="#1c3a58" stroke-width="0.8" opacity="0.8"/>
  <path d="M70,198 C66,212 64,236 66,264 C68,286 70,300 72,312 C76,320 86,321 90,314 C94,306 92,284 90,258 C88,230 84,206 70,198 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <path d="M130,198 C134,212 136,236 134,264 C132,286 130,300 128,312 C124,320 114,321 110,314 C106,306 108,284 110,258 C112,230 116,206 130,198 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <path d="M72,314 C70,328 68,350 70,372 C72,384 74,392 76,396 C80,400 86,399 88,394 C90,388 90,372 88,352 C86,330 80,316 72,314 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <path d="M128,314 C130,328 132,350 130,372 C128,384 126,392 124,396 C120,400 114,399 112,394 C110,388 110,372 112,352 C114,330 120,316 128,314 Z" fill="#080e1c" stroke="#1c3a58" stroke-width="0.7" opacity="0.92"/>
  <ellipse cx="80" cy="401" rx="18" ry="6" fill="#080e1c" stroke="#1c3a58" stroke-width="0.6" opacity="0.4"/>
  <ellipse cx="120" cy="401" rx="18" ry="6" fill="#080e1c" stroke="#1c3a58" stroke-width="0.6" opacity="0.4"/>

  <!-- ── Zones musculaires DOS ── -->
  <!-- Deltoïdes postérieurs -->
  <g id="z-epaules-b" class="zone" onclick="sel('Épaules')"><title>Épaules</title>
    <path d="M48,82 C38,88 34,102 36,116 C38,126 42,134 46,138 C50,134 52,118 52,106 C52,94 50,84 48,82 Z" fill="{mf('Épaules','gb')}" opacity="{mop('Épaules')}" filter="url(#gwb)"/>
    <path d="M152,82 C162,88 166,102 164,116 C162,126 158,134 154,138 C150,134 148,118 148,106 C148,94 150,84 152,82 Z" fill="{mf('Épaules','gb')}" opacity="{mop('Épaules')}" filter="url(#gwb)"/>
  </g>
  <!-- Dos : trapèze + grands dorsaux -->
  <g id="z-dos" class="zone" onclick="sel('Dos')"><title>Dos</title>
    <!-- Trapèze supérieur (losange) -->
    <path d="M88,74 C92,70 100,68 108,74 L118,94 C108,100 100,102 92,94 Z" fill="{mf('Dos','gb')}" opacity="{mop('Dos')}" filter="url(#gwb)"/>
    <!-- Grand dorsal gauche (éventail) -->
    <path d="M72,90 C64,102 60,124 64,150 C66,164 72,170 78,167 C84,162 86,148 86,128 C86,110 82,92 72,90 Z" fill="{mf('Dos','gb')}" opacity="{mop('Dos')}" filter="url(#gwb)"/>
    <!-- Grand dorsal droit -->
    <path d="M128,90 C136,102 140,124 136,150 C134,164 128,170 122,167 C116,162 114,148 114,128 C114,110 118,92 128,90 Z" fill="{mf('Dos','gb')}" opacity="{mop('Dos')}" filter="url(#gwb)"/>
    <!-- Rhomboïdes / érecteurs (colonne) -->
    <path d="M90,98 C94,94 100,92 106,98 L112,136 C108,144 100,146 92,136 Z" fill="{mf('Dos','gb')}" opacity="{mop('Dos')}" filter="url(#gwb)"/>
  </g>
  <!-- Triceps (face postérieure du bras) -->
  <g id="z-triceps" class="zone" onclick="sel('Triceps')"><title>Triceps</title>
    <path d="M50,86 C44,98 40,114 42,128 C44,138 48,142 52,138 C56,134 58,118 56,106 C54,94 52,86 50,86 Z" fill="{mf('Triceps','gb')}" opacity="{mop('Triceps')}" filter="url(#gwb)"/>
    <path d="M150,86 C156,98 160,114 158,128 C156,138 152,142 148,138 C144,134 142,118 144,106 C146,94 148,86 150,86 Z" fill="{mf('Triceps','gb')}" opacity="{mop('Triceps')}" filter="url(#gwb)"/>
  </g>
  <!-- Avant-bras dos -->
  <g id="z-avbras-b" class="zone" onclick="sel('Avant-bras')"><title>Avant-bras</title>
    <path d="M42,150 C36,162 34,176 36,188 C38,196 42,200 46,198 C50,196 52,186 52,174 C52,162 48,152 42,150 Z" fill="{mf('Avant-bras','gb')}" opacity="{mop('Avant-bras')}" filter="url(#gwb)"/>
    <path d="M158,150 C164,162 166,176 164,188 C162,196 158,200 154,198 C150,196 148,186 148,174 C148,162 152,152 158,150 Z" fill="{mf('Avant-bras','gb')}" opacity="{mop('Avant-bras')}" filter="url(#gwb)"/>
  </g>
  <!-- Fessiers (grandes fesses arrondies) -->
  <g id="z-fessiers" class="zone" onclick="sel('Fessiers')"><title>Fessiers</title>
    <path d="M68,198 C64,210 64,228 68,240 C72,252 82,258 94,254 C102,250 104,238 102,224 C100,208 94,198 80,196 Z" fill="{mf('Fessiers','gb')}" opacity="{mop('Fessiers')}" filter="url(#gwb)"/>
    <path d="M132,198 C136,210 136,228 132,240 C128,252 118,258 106,254 C98,250 96,238 98,224 C100,208 106,198 120,196 Z" fill="{mf('Fessiers','gb')}" opacity="{mop('Fessiers')}" filter="url(#gwb)"/>
  </g>
  <!-- Ischio-jambiers (face postérieure cuisse) -->
  <g id="z-ischio" class="zone" onclick="sel('Ischio-jambiers')"><title>Ischio-jambiers</title>
    <path d="M68,202 C64,218 62,242 64,270 C66,292 68,306 70,316 C76,322 86,322 90,314 C94,304 92,280 90,254 C88,226 84,206 68,202 Z" fill="{mf('Ischio-jambiers','gb')}" opacity="{mop('Ischio-jambiers')}" filter="url(#gwb)"/>
    <path d="M132,202 C136,218 138,242 136,270 C134,292 132,306 130,316 C124,322 114,322 110,314 C106,304 108,280 110,254 C112,226 116,206 132,202 Z" fill="{mf('Ischio-jambiers','gb')}" opacity="{mop('Ischio-jambiers')}" filter="url(#gwb)"/>
  </g>
  <!-- Mollets (gastrocnémien — plus proéminent de dos) -->
  <g id="z-mollets-b" class="zone" onclick="sel('Mollets')"><title>Mollets</title>
    <path d="M72,318 C68,334 66,356 68,378 C70,390 72,398 74,402 C78,406 86,405 88,400 C90,392 90,374 88,354 C86,332 80,320 72,318 Z" fill="{mf('Mollets','gb')}" opacity="{mop('Mollets')}" filter="url(#gwb)"/>
    <path d="M128,318 C132,334 134,356 132,378 C130,390 128,398 126,402 C122,406 114,405 112,400 C110,392 110,374 112,354 C114,332 120,320 128,318 Z" fill="{mf('Mollets','gb')}" opacity="{mop('Mollets')}" filter="url(#gwb)"/>
  </g>
</svg>"""

    # ─── Panel latéral : légende couleur + liste muscles ────────────────────
    legend_html = (
        '<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;padding:4px 6px;'
        'background:rgba(255,255,255,0.03);border-radius:6px;">'
        '<div style="height:5px;flex:1;border-radius:3px;'
        'background:linear-gradient(90deg,#FF453A,#FF9F0A,#58CCFF,#00FF7F);'
        'box-shadow:0 0 8px rgba(88,204,255,0.3);"></div>'
        '<span style="font-size:7px;color:#3a4a5a;letter-spacing:1px;white-space:nowrap;">progression</span>'
        '</div>'
    )

    overview_rows = ""
    for m in DISPLAY_MUSCLES:
        s = sc[m]
        pct_w = min(s['pct'], 100)
        overview_rows += (
            f'<div class="mrow" onclick="selAuto(\'{m}\')" data-m="{m}"'
            f' style="padding:5px 6px 4px;margin-bottom:3px;cursor:pointer;border-radius:6px;'
            f'border-left:3px solid {s["col"]};">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">'
            f'<span style="font-size:10px;color:{s["col"]};font-weight:700;">{m}</span>'
            f'<span style="font-size:8px;color:#3a4a5a;">{s["rm"]:.0f} kg</span>'
            f'</div>'
            f'<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:4px;">'
            f'<div style="width:{pct_w:.0f}%;height:100%;'
            f'background:linear-gradient(90deg,{s["col"]}88,{s["col"]});border-radius:3px;'
            f'box-shadow:0 0 7px {s["col"]}66;"></div></div>'
            f'</div>'
        )

    css = """<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:transparent;font-family:'Courier New',monospace;color:#ccc;overflow:hidden;}
.wrap{background:linear-gradient(150deg,#060e1e 0%,#04080f 100%);border-radius:16px;
  border:1px solid rgba(88,204,255,0.15);padding:10px;display:flex;gap:8px;
  box-shadow:0 4px 30px rgba(0,0,0,0.6),inset 0 0 60px rgba(88,204,255,0.015);}
.svg-col{display:flex;flex-direction:column;align-items:center;flex-shrink:0;}
.vtoggle{display:flex;gap:5px;margin-bottom:7px;}
.vbtn{background:rgba(255,255,255,0.04);border:1px solid rgba(88,204,255,0.22);
  color:#4a8aaa;font-family:monospace;font-size:9px;padding:4px 14px;
  border-radius:20px;cursor:pointer;transition:all 0.2s;letter-spacing:1.5px;}
.vbtn.active{background:rgba(88,204,255,0.14);border-color:#58CCFF;color:#fff;
  box-shadow:0 0 14px rgba(88,204,255,0.25);}
.vbtn:hover:not(.active){background:rgba(88,204,255,0.08);color:#7ab8d8;}
.zone{cursor:pointer;transition:filter 0.2s;}
.zone:hover{filter:brightness(2) drop-shadow(0 0 6px currentColor);}
.zone.on{filter:brightness(2.8) drop-shadow(0 0 12px currentColor);}
.mrow{transition:background 0.15s;}
.mrow:hover{background:rgba(88,204,255,0.07)!important;}
.mrow.arow{background:rgba(88,204,255,0.1)!important;}
#detail{display:none;}
.back{cursor:pointer;color:#58CCFF;font-size:10px;margin-bottom:9px;opacity:0.55;
  display:inline-block;transition:opacity 0.15s;letter-spacing:1px;}
.back:hover{opacity:1;}
.ltable{width:100%;border-collapse:collapse;font-size:9px;margin:3px 0 5px;}
.ltable th{color:#2a3a4a;font-weight:normal;padding:2px 4px;
  border-bottom:1px solid rgba(255,255,255,0.05);letter-spacing:1px;}
.ltable td{padding:2px 4px;color:#6a7a8a;}
.ltable tr:hover td{color:#aaa;}
</style>"""

    js = r"""<script>
const D = """ + data_json + r""";
let curView = 'front';

function switchView(v) {
  curView = v;
  document.getElementById('svg-front').style.display = v==='front'?'block':'none';
  document.getElementById('svg-back').style.display  = v==='back' ?'block':'none';
  document.getElementById('btn-front').classList.toggle('active', v==='front');
  document.getElementById('btn-back').classList.toggle('active',  v==='back');
  document.querySelectorAll('.zone').forEach(z=>z.classList.remove('on'));
}

function selAuto(name) {
  const d = D[name]; if (!d) return;
  if (d.zid_b && !d.zid_f) switchView('back');
  else if (d.zid_f && !d.zid_b) switchView('front');
  sel(name);
}

function sel(name) {
  document.querySelectorAll('.zone').forEach(z=>z.classList.remove('on'));
  document.querySelectorAll('.mrow').forEach(r=>r.classList.remove('arow'));
  const d = D[name]; if (!d) return;
  const zid = curView==='front' ? d.zid_f : d.zid_b;
  if (zid) { const el=document.getElementById(zid); if(el) el.classList.add('on'); }
  document.querySelectorAll('.mrow').forEach(r=>{ if(r.dataset.m===name) r.classList.add('arow'); });
  document.getElementById('ov').style.display='none';
  document.getElementById('detail').style.display='block';

  let h = '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">'
    + '<div style="width:3px;height:32px;background:'+d.col+';border-radius:2px;box-shadow:0 0 10px '+d.col+'66;"></div>'
    + '<div><div style="font-size:13px;font-weight:900;color:'+d.col+';letter-spacing:2px;">'+name.toUpperCase()+'</div>'
    + '<div style="font-size:8px;color:#3a4a5a;letter-spacing:1px;margin-top:2px;">'+d.pct.toFixed(0)+'% de l\'objectif</div>'
    + '</div></div>';

  if (d.best && d.best.w > 0) {
    h += '<div style="background:rgba(255,255,255,0.03);border-radius:8px;padding:8px;margin-bottom:8px;text-align:center;border:1px solid '+d.col+'22;">'
      + '<div style="font-size:7.5px;color:#2a3a4a;letter-spacing:1.5px;margin-bottom:4px;">RECORD PERSONNEL</div>'
      + '<div style="font-size:24px;font-weight:900;color:'+d.col+';line-height:1;">'+d.best.w.toFixed(1)
      + '<span style="font-size:12px;color:#444;"> kg</span>'
      + ' <span style="font-size:14px;color:#333;">×</span> '
      + d.best.r+'<span style="font-size:12px;color:#444;"> reps</span></div>'
      + '<div style="font-size:8.5px;color:#2a3a4a;margin-top:4px;">1RM · '+d.rm.toFixed(1)+'kg &nbsp;/&nbsp; obj. '+d.std+'kg</div>'
      + '</div>';
  } else {
    h += '<div style="font-size:10px;color:#1e2e3e;text-align:center;padding:16px 0 14px;">Pas encore de données<br><span style="font-size:22px;opacity:0.3;">💪</span></div>';
  }

  if (d.last && d.last.length) {
    h += '<div style="font-size:7.5px;color:#2a3a4a;letter-spacing:1.5px;margin-bottom:3px;">DERNIÈRES SÉANCES</div>'
      + '<table class="ltable"><tr><th>Sem.</th><th>Charge</th><th>Reps</th></tr>';
    d.last.forEach(ls => {
      h += '<tr><td style="color:#58CCFF66">S'+ls.s+'</td><td style="color:'+d.col+'">'+ls.w.toFixed(1)+'kg</td><td>'+ls.r+'</td></tr>';
    });
    h += '</table>';
  }

  if (d.exos && d.exos.length) {
    h += '<div style="font-size:7.5px;color:#2a3a4a;letter-spacing:1.5px;margin-bottom:4px;">TOP EXERCICES</div>';
    d.exos.forEach((e,i) => {
      h += '<div style="font-size:9px;margin-bottom:3px;color:#4a5a6a;">'
        + (i===0?'<span style="color:'+d.col+'">▶</span>':'<span style="color:#1e2e3e">·</span>')
        + ' '+e.name+' <span style="color:'+d.col+';font-weight:700;">'+e.w.toFixed(1)+'kg×'+e.r+'</span></div>';
    });
  }

  if (d.evo && d.evo.length>1) {
    h += '<div style="font-size:7.5px;color:#2a3a4a;letter-spacing:1.5px;margin:6px 0 4px;">ÉVOLUTION 1RM</div>'+spark(d.evo,d.col);
  }

  document.getElementById('dc').innerHTML = h;
}

function back() {
  document.querySelectorAll('.zone').forEach(z=>z.classList.remove('on'));
  document.querySelectorAll('.mrow').forEach(r=>r.classList.remove('arow'));
  document.getElementById('ov').style.display='block';
  document.getElementById('detail').style.display='none';
}

function spark(evo, col) {
  const W=160, H=50, pad=8, pts=[], cir=[];
  const rms=evo.map(e=>e.r), mn=Math.min(...rms), mx=Math.max(...rms), rng=mx-mn||1;
  evo.forEach((e,i)=>{
    const x=(i/(evo.length-1))*(W-pad*2)+pad, y=H-((e.r-mn)/rng)*(H-pad*2)-pad;
    pts.push(x+','+y);
    cir.push('<circle cx="'+x+'" cy="'+y+'" r="2.8" fill="'+col+'" stroke="#04080f" stroke-width="1.5"/>');
  });
  const area_pts = pts.join(' ')+' '+W+','+(H-1)+' '+0+','+(H-1);
  const first=evo[0], last=evo[evo.length-1];
  return '<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:50px;background:rgba(0,0,0,0.2);'
    +'border-radius:7px;border:1px solid rgba(255,255,255,0.04);">'
    +'<defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">'
    +'<stop offset="0%" stop-color="'+col+'" stop-opacity="0.2"/>'
    +'<stop offset="100%" stop-color="'+col+'" stop-opacity="0"/></linearGradient></defs>'
    +'<polygon points="'+area_pts+'" fill="url(#ag)"/>'
    +'<polyline points="'+pts.join(' ')+'" fill="none" stroke="'+col+'" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
    +cir.join('')
    +'<text x="'+pad+'" y="'+(H-2)+'" fill="#1e2e3e" font-size="7" font-family="monospace">S'+first.w+'</text>'
    +'<text x="'+(W-pad)+'" y="'+(H-2)+'" fill="#1e2e3e" font-size="7" font-family="monospace" text-anchor="end">S'+last.w+'</text>'
    +'</svg>';
}
</script>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{css}</head><body>
<div class="wrap">
  <div class="svg-col">
    <div class="vtoggle">
      <button id="btn-front" class="vbtn active" onclick="switchView('front')">FACE</button>
      <button id="btn-back"  class="vbtn"        onclick="switchView('back')">DOS</button>
    </div>
    <div id="svg-front">{svg_front}</div>
    <div id="svg-back" style="display:none">{svg_back}</div>
  </div>
  <div style="flex:1;min-width:0;overflow:hidden;">
    <div id="ov">
      {legend_html}
      {overview_rows}
    </div>
    <div id="detail">
      <div class="back" onclick="back()">← Vue d'ensemble</div>
      <div id="dc"></div>
    </div>
  </div>
</div>
{js}
</body></html>"""

    components.html(html, height=500, scrolling=False)


# --- 6. CARDIO ---
def cardio_section(df_h, s_act):
    ACTS = {"🏃 Course":["dur","dist","speed","inc"],"🚶 Marche":["dur","dist","speed","inc"],
            "🚴 Vélo":["dur","dist","speed"],"🪜 Escaliers":["dur","floors"],
            "🏊 Natation":["dur","dist"],"🔄 Elliptique":["dur","dist","res"],"💪 Autre":["dur","dist"]}
    ICONS = {"🏃 Course":"🏃","🚶 Marche":"🚶","🚴 Vélo":"🚴","🪜 Escaliers":"🪜","🏊 Natation":"🏊","🔄 Elliptique":"🔄","💪 Autre":"💪"}

    df_c = df_h[df_h["Séance"]=="CARDIO"].copy() if not df_h.empty else pd.DataFrame()

    # Stats semaine
    if not df_c.empty:
        dw = df_c[df_c["Semaine"]==s_act]
        c1,c2,c3 = st.columns(3)
        c1.metric("⏱️ Cette semaine",f"{int(dw['Reps'].sum())} min")
        c2.metric("📍 Distance",f"{dw['Poids'].sum():.1f} km")
        c3.metric("🔥 Sessions",len(dw))
        # Streak cardio
        all_dates = sorted(df_c["Date"].dropna().unique(), reverse=True)
        streak=0
        prev=None
        for d in all_dates:
            try:
                dt = datetime.strptime(d,"%Y-%m-%d")
                if prev is None or (prev-dt).days==1: streak+=1; prev=dt
                else: break
            except: pass
        if streak>1: st.caption(f"🔥 Streak : {streak} jours consécutifs !")

    st.markdown("### ➕ Nouvelle session")
    if "cardio_act" not in st.session_state: st.session_state.cardio_act="🏃 Course"
    ac = st.columns(len(ACTS))
    for col,(act,_) in zip(ac,ACTS.items()):
        if col.button(ICONS[act],key=f"ca_{act}",type="primary" if st.session_state.cardio_act==act else "secondary",use_container_width=True):
            st.session_state.cardio_act=act; st.rerun()
    st.caption(f"**{st.session_state.cardio_act}**")
    fields = ACTS[st.session_state.cardio_act]

    col1,col2 = st.columns(2)
    dur = col1.number_input("⏱️ Durée (min)",1,300,30,key="cd_dur")
    dist = col2.number_input("📍 Distance (km)",0.0,300.0,0.0,step=0.1,key="cd_dist") if "dist" in fields else 0.0
    col3,col4 = st.columns(2)
    speed = col3.number_input("⚡ Vitesse (km/h)",0.0,50.0,0.0,step=0.1,key="cd_spd") if "speed" in fields else 0.0
    inc = col4.number_input("📐 Inclinaison (%)",0.0,30.0,0.0,step=0.5,key="cd_inc") if "inc" in fields else 0.0
    floors = col3.number_input("🪜 Étages",0,500,0,key="cd_fl") if "floors" in fields else 0
    res = col4.number_input("💪 Résistance",0,20,5,key="cd_res") if "res" in fields else 0
    feel = st.select_slider("💭 Ressenti",options=["😴 Facile","😊 Correct","💪 Intense","🔥 Max"],value="😊 Correct",key="cd_feel")
    note = st.text_input("📝 Note",key="cd_note",placeholder="Optionnel...")

    if st.button("✅ Enregistrer",type="primary",use_container_width=True,key="save_cardio"):
        if dist==0.0 and speed>0: dist=round((speed*dur)/60,2)
        detail = json.dumps({"speed":speed,"inc":inc,"floors":floors,"res":res,"feel":feel,"note":note},ensure_ascii=False)
        row = pd.DataFrame([{"Semaine":s_act,"Séance":"CARDIO","Exercice":st.session_state.cardio_act,
            "Série":1,"Reps":dur,"Poids":dist,"Remarque":detail,"Muscle":"Cardio",
            "Date":today_paris_str()}])
        save_hist(pd.concat([df_h,row],ignore_index=True))
        st.success(f"✅ {dur} min · {dist:.1f} km enregistrés !")
        st.rerun()

    if not df_c.empty:
        st.markdown("### 📊 Progression")
        weekly = df_c.groupby("Semaine").agg(minutes=("Reps","sum"),km=("Poids","sum")).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=weekly["Semaine"],y=weekly["minutes"],name="Min",marker_color="#58CCFF",opacity=0.75))
        fig.add_trace(go.Scatter(x=weekly["Semaine"],y=weekly["km"],name="km",yaxis="y2",
            mode="markers+lines",line=dict(color="#00FF7F",width=2),marker=dict(size=7,color="#00FF7F")))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0,r=0,t=5,b=0),height=200,showlegend=False,
            xaxis=dict(color="#aaa"),yaxis=dict(color="#58CCFF"),
            yaxis2=dict(color="#00FF7F",overlaying="y",side="right"))
        st.plotly_chart(fig,use_container_width=True,config={'staticPlot':True,'displayModeBar':False})

        st.markdown("### 🗓️ Sessions récentes")
        for _,row in df_c.sort_values("Date",ascending=False).head(8).iterrows():
            try: d=json.loads(row["Remarque"]) if row["Remarque"] else {}
            except: d={}
            fi = d.get("feel","")[:2] if d.get("feel") else ""
            sp = f" · {d.get('speed',0):.1f}km/h" if d.get("speed",0)>0 else ""
            ic = f" · {d.get('inc',0):.0f}%" if d.get("inc",0)>0 else ""
            fl = f" · {d.get('floors',0)}étages" if d.get("floors",0)>0 else ""
            st.markdown(f"""<div style="background:rgba(255,255,255,0.03);border-radius:8px;padding:8px 12px;
margin:3px 0;border-left:3px solid #58CCFF44;font-size:12px;">
<span style="color:#58CCFF">{row['Exercice']}</span>
<span style="color:#ccc"> · S{int(row['Semaine'])} · {int(row['Reps'])}min · {float(row['Poids']):.1f}km{sp}{ic}{fl}</span>
<span style="float:right;color:#666">{row['Date']} {fi}</span></div>""",unsafe_allow_html=True)


# --- 7. CONNEXION ---
import os

@st.cache_resource
def get_gs():
    try:
        if os.getenv('GCP_PROJECT_ID'):
            private_key = os.getenv('GCP_PRIVATE_KEY', '').replace('\\n', '\n')
            
            creds = {
                "type": os.getenv('GCP_TYPE'),
                "project_id": os.getenv('GCP_PROJECT_ID'),
                "private_key_id": os.getenv('GCP_PRIVATE_KEY_ID'),
                "private_key": private_key,
                "client_email": os.getenv('GCP_CLIENT_EMAIL'),
                "client_id": os.getenv('GCP_CLIENT_ID'),
                "auth_uri": os.getenv('GCP_AUTH_URI'),
                "token_uri": os.getenv('GCP_TOKEN_URI'),
                "auth_provider_x509_cert_url": os.getenv('GCP_AUTH_PROVIDER_CERT'),
                "client_x509_cert_url": os.getenv('GCP_CLIENT_CERT')
            }
        else:
            creds = dict(st.secrets["gcp_service_account"])
        
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open("Muscu_App")
        return sh.get_worksheet(0), sh.worksheet("Programme")
    except Exception as e:
        st.error(f"Erreur de connexion Google Sheets: {e}")
        return None, None

ws_h, ws_p = get_gs()

@st.cache_data(ttl=300)
def get_prog():
    """Récupère le programme depuis Google Sheets avec cache"""
    try:
        prog_raw = ws_p.acell('A1').value if ws_p else "{}"
        return json.loads(prog_raw)
    except:
        return {}

@st.cache_data(ttl=30)
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
    get_hist.clear()

def save_prog(prog_dict):
    ws_p.update_acell('A1', json.dumps(prog_dict))
    get_prog.clear()

df_h = get_hist()
prog = get_prog()

# Init du planning hebdo si absent (jour -> nom de séance assignée, "" = repos)
_DAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
if '_planning' not in prog:
    prog['_planning'] = {j: "" for j in _DAYS_FR}
else:
    # Garantit que les 7 jours existent (compatibilité ascendante)
    for _j in _DAYS_FR:
        prog['_planning'].setdefault(_j, "")

# Clés réservées aux données internes (pas des séances)
prog_seances = {k: v for k, v in prog.items() if not k.startswith('_')}
muscle_mapping = {ex["name"]: ex.get("muscle", "Autre") for s in prog_seances for ex in prog_seances[s]}
df_h["Muscle"] = df_h["Exercice"].apply(get_base_name).map(muscle_mapping).fillna(df_h["Muscle"]).replace("", "Autre")
df_h["Muscle"] = df_h.apply(lambda r: fix_muscle(r["Exercice"], r["Muscle"]), axis=1).astype(str)



# Calcul df_p global (partagé entre onglets)
arch_rows = prog.get('_archive', [])
if arch_rows:
    df_arch = pd.DataFrame(arch_rows)
    df_arch['Poids'] = pd.to_numeric(df_arch['Poids'], errors='coerce').fillna(0.0)
    df_arch['Reps'] = pd.to_numeric(df_arch['Reps'] if 'Reps' in df_arch.columns else 1, errors='coerce').fillna(1).astype(int)
    df_arch['Semaine'] = pd.to_numeric(df_arch['Semaine'] if 'Semaine' in df_arch.columns else 0, errors='coerce').fillna(0).astype(int)
    # Remapper les muscles archivés via muscle_mapping (comme df_h)
    df_arch["Muscle"] = df_arch["Exercice"].apply(get_base_name).map(muscle_mapping).fillna(df_arch["Muscle"]).replace("", "Autre")
    df_arch["Muscle"] = df_arch.apply(lambda r: fix_muscle(r["Exercice"], r["Muscle"]), axis=1).astype(str)
    df_live = df_h[df_h["Reps"] > 0].copy() if not df_h.empty else pd.DataFrame(columns=df_arch.columns)
    df_p = pd.concat([df_live, df_arch[df_arch['Reps'] > 0]], ignore_index=True)
else:
    df_p = df_h[df_h["Reps"] > 0].copy() if not df_h.empty else pd.DataFrame()
if not df_p.empty:
    df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)

# Onglets
tab_home, tab_p, tab_s, tab_st, tab_cardio, tab_g = st.tabs([
    ":material/home: ACCUEIL",
    ":material/settings: GESTION",
    ":material/fitness_center: MA SÉANCE",
    ":material/trending_up: PROGRÈS",
    ":material/directions_run: CARDIO",
    ":material/sports_esports: ARCADE",
])

# ============================================================
# ONGLET ACCUEIL : dashboard, sélection séance, statut semaine
# ============================================================
with tab_home:

    # Intercepte un clic sur une fenêtre de jour (lien ?day_click=N)
    _clicked = st.query_params.get("day_click")
    if _clicked is not None:
        try:
            _idx_clicked = int(_clicked)
            _tp_click = today_paris()
            _mon_click = _tp_click - timedelta(days=_tp_click.weekday())
            st.session_state.seance_target_date = (_mon_click + timedelta(days=_idx_clicked)).strftime("%Y-%m-%d")
            st.session_state.view = 'choix_seance'
        except (ValueError, TypeError):
            pass
        st.query_params.clear()
        st.rerun()

    s_act = int(df_h["Semaine"].max() if not df_h.empty else 1)

    # Helpers date
    days_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    months_fr = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                 "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    today = now_paris()
    day_name = days_fr[today.weekday()]
    date_str = f"{today.day} {months_fr[today.month - 1]} {today.year}"

    def get_next_session():
        for seance in prog_seances.keys():
            seance_data = df_h[(df_h["Séance"] == seance) & (df_h["Semaine"] == s_act)]
            if seance_data.empty:
                return seance
            if not seance_data[seance_data["Exercice"] == "SESSION"].empty:
                continue
            exos_prog = len([ex for ex in prog[seance]])
            exos_done_or_skipped = len(seance_data[(seance_data["Poids"] > 0) | (seance_data["Remarque"].str.contains("SKIP", na=False))]["Exercice"].unique())
            if exos_done_or_skipped < exos_prog:
                return seance
        return list(prog_seances.keys())[0] if prog_seances else None

    # JS switch to séance tab (déclenché après sélection)
    if st.session_state.switch_to_seance:
        st.session_state.switch_to_seance = False
        components.html("""<script>
        setTimeout(function(){
            var tabs = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
            for (var i=0; i<tabs.length; i++){
                if (tabs[i].textContent.indexOf('SÉANCE') !== -1){
                    tabs[i].click(); break;
                }
            }
        }, 120);
        </script>""", height=0)

    # ══════════════════════════════════════════
    # VUE : PAGE DE SÉLECTION INTERMÉDIAIRE
    # ══════════════════════════════════════════
    if st.session_state.view == 'choix_seance':

        if st.button("← Retour", key="back_accueil"):
            st.session_state.seance_target_date = None
            st.session_state.view = 'accueil'
            st.rerun()

        _tgt = st.session_state.seance_target_date
        _JOURS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
        _MOIS_FR  = ["jan","fév","mar","avr","mai","juin","juil","août","sep","oct","nov","déc"]
        # Statut du jour cible → titre dynamique
        _cs_done_name = None
        if _tgt:
            from datetime import datetime as _dt
            _tgt_d = _dt.strptime(_tgt, "%Y-%m-%d").date()
            _tgt_label = f"{_JOURS_FR[_tgt_d.weekday()]} {_tgt_d.day} {_MOIS_FR[_tgt_d.month-1]}"

            _day_rows_cs = df_h[df_h["Date"] == _tgt]
            _real_cs = _day_rows_cs[
                (_day_rows_cs["Exercice"] != "SESSION") &
                ((_day_rows_cs["Poids"] > 0) | (_day_rows_cs["Reps"] > 0) |
                 _day_rows_cs["Remarque"].fillna("").str.contains("SKIP", na=False))
            ]
            _tp_now_cs = today_paris()
            if not _real_cs.empty:
                _cs_done_name = str(
                    _real_cs.groupby("Séance")["Exercice"].nunique().sort_values(ascending=False).index[0]
                )
                _titre_cs = f"Séance réalisée · {_cs_done_name}"
                _sub_color, _sub_text = "#00FF7F", "RÉALISÉE"
            elif _tgt_d < _tp_now_cs:
                _titre_cs = "Séance manquée"
                _sub_color, _sub_text = "#FF453A", "MANQUÉE"
            else:
                _titre_cs = "Séance à faire"
                _sub_color, _sub_text = "#58CCFF", "À FAIRE"
            _subtitle_cs = f'<div style="font-size:0.75rem; color:{_sub_color}; letter-spacing:2px; margin-top:4px;">{_sub_text}</div>'
        else:
            _tgt_label = f"{day_name.upper()} · {date_str}"
            _titre_cs = "Quelle séance aujourd'hui ?"
            _subtitle_cs = ""
        st.markdown(f"""
        <div style="text-align:center; padding:12px 8px 6px; margin-bottom:20px;">
            <div style="font-size:0.8rem; color:#5a7a9a; letter-spacing:3px;">{_tgt_label.upper() if not _tgt else _tgt_label}</div>
            <div style="font-size:1.6rem; color:#fff; font-weight:900; margin-top:4px;">{_titre_cs}</div>
            {_subtitle_cs}
        </div>
        """, unsafe_allow_html=True)

        # ── Mode consultation/modification si séance déjà réalisée ─────────────
        if _cs_done_name:
            st.markdown(f"""
            <div style="border:1px solid rgba(0,255,127,0.4); border-radius:14px; padding:16px 14px; margin-bottom:16px; background:rgba(0,255,127,0.05);">
                <div style="font-size:0.75rem; color:#00FF7F; letter-spacing:3px; margin-bottom:6px;">✅ SÉANCE ENREGISTRÉE</div>
                <div style="font-size:0.85rem; color:#8aaa9a;">Tu peux consulter ou modifier « {_cs_done_name} ».</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(":material/edit: Consulter / Modifier cette séance",
                         type="primary", use_container_width=True, key="cs_consult_btn"):
                if _cs_done_name in prog_seances:
                    st.session_state.seance_selectionnee = _cs_done_name
                    st.session_state.mode_seance = 'prefaite'
                    st.session_state.home_selected_session = _cs_done_name
                else:
                    # Reconstitue les exos libres depuis l'historique
                    _rows_done = _real_cs.copy()
                    _exos_rebuild = []
                    for _exo_n in _rows_done["Exercice"].drop_duplicates().tolist():
                        _m = _rows_done[_rows_done["Exercice"] == _exo_n]["Muscle"].iloc[0] if "Muscle" in _rows_done.columns else "Autre"
                        _exos_rebuild.append({"exo": _exo_n, "muscle": _m})
                    st.session_state.seance_libre_exos = _exos_rebuild
                    st.session_state.mode_seance = 'libre'
                    if "nom_libre" in st.session_state:
                        del st.session_state["nom_libre"]
                    st.session_state["_nom_libre_preset"] = _cs_done_name
                st.session_state.switch_to_seance = True
                st.session_state.view = 'accueil'
                st.rerun()
            st.divider()

        seance_list_cs = list(prog_seances.keys())
        _MUSCLE_LIST = ["Pecs","Dos","Épaules","Biceps","Triceps","Avant-bras","Abdos",
                        "Quadriceps","Ischio-jambiers","Fessiers","Mollets","Autre"]

        # ── OPTION A : Séance pré-faite ────────────────────────────────────────
        st.markdown("""
        <div style="border:1px solid rgba(88,204,255,0.3); border-radius:14px; padding:16px 14px 10px; margin-bottom:16px;">
            <div style="font-size:0.75rem; color:#58CCFF; letter-spacing:3px; margin-bottom:12px;">📋 SÉANCE PRÉ-FAITE</div>
        """, unsafe_allow_html=True)

        for sname in seance_list_cs:
            n_exos = len(prog_seances[sname])
            jours_s = prog.get('_jours', {}).get(sname, "")
            jours_label = f" · {jours_s}" if jours_s else ""
            next_marker = " " if sname == get_next_session() else ""

            c_info, c_btn = st.columns([3, 1])
            with c_info:
                st.markdown(
                    f"<div style='padding:8px 0 4px;'>"
                    f"<span style='font-weight:700; color:#fff;'>{sname}</span>"
                    f"<span style='color:#58CCFF;'>{next_marker}</span>"
                    f"<br><span style='font-size:11px; color:#4a6a8a;'>{n_exos} exercices{jours_label}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with c_btn:
                if st.button("Choisir →", key=f"cs_pref_{sname}", use_container_width=True):
                    st.session_state.seance_selectionnee = sname
                    st.session_state.mode_seance = 'prefaite'
                    st.session_state.home_selected_session = sname
                    st.session_state.switch_to_seance = True
                    st.session_state.view = 'accueil'
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # ── OPTION B : Séance personnalisée ───────────────────────────────────
        st.markdown("""
        <div style="border:1px solid rgba(0,255,127,0.3); border-radius:14px; padding:16px 14px;">
            <div style="font-size:0.75rem; color:#00FF7F; letter-spacing:3px; margin-bottom:8px;">✏️ SÉANCE PERSONNALISÉE</div>
            <div style="font-size:0.85rem; color:#5a8a6a; margin-bottom:12px;">
                Construis ta séance exercice par exercice,<br>en piochant dans ton programme ou en créant du nouveau.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button(":material/edit_note: Créer ma séance", type="primary", use_container_width=True, key="cs_libre"):
            st.session_state.seance_libre_exos = []
            st.session_state.mode_seance = 'libre'
            st.session_state.switch_to_seance = True
            st.session_state.view = 'accueil'
            st.rerun()

        # ── OPTION C : Passer / Séance manquée ────────────────────────────────
        st.markdown("""
        <div style="border:1px solid rgba(255,69,58,0.25); border-radius:14px; padding:16px 14px; margin-top:16px;">
            <div style="font-size:0.75rem; color:#FF453A; letter-spacing:3px; margin-bottom:8px;">🚩 PASSER UNE SÉANCE</div>
        </div>
        """, unsafe_allow_html=True)

        # Semaine ISO calée sur la date cible (pas sur aujourd'hui)
        _miss_date = _tgt or today_paris_str()
        try:
            _s_act_cs = datetime.strptime(_miss_date, "%Y-%m-%d").isocalendar().week
        except Exception:
            _s_act_cs = int(df_h["Semaine"].max() if not df_h.empty else 1)

        if st.button(":material/flag: Marquer comme manquée", use_container_width=True, key="cs_miss_btn"):
            _already = df_h[
                (df_h["Date"] == _miss_date) &
                (df_h["Exercice"] == "SESSION")
            ]
            if _already.empty:
                _mrec = pd.DataFrame([{
                    "Semaine": _s_act_cs, "Séance": "Séance manquée",
                    "Exercice": "SESSION", "Série": 1, "Reps": 0, "Poids": 0.0,
                    "Remarque": "SÉANCE MANQUÉE 🚩", "Muscle": "Autre",
                    "Date": _miss_date
                }])
                save_hist(pd.concat([df_h, _mrec], ignore_index=True))
            st.session_state.seance_target_date = None
            st.session_state.view = 'accueil'
            st.rerun()

    # ══════════════════════════════════════════
    # VUE : DASHBOARD ACCUEIL NORMAL
    # ══════════════════════════════════════════
    else:
        st.markdown("<h1 style='text-align:center; margin-top:5px; margin-bottom:16px;'>MUSCU TRACKER PRO</h1>",
                    unsafe_allow_html=True)

        # Date + semaine
        st.markdown(f"""
        <div style="text-align:center; padding:14px 12px 10px; margin-bottom:14px;
            background:linear-gradient(135deg,rgba(88,204,255,0.07),rgba(0,255,127,0.05));
            border:1px solid rgba(88,204,255,0.25); border-radius:16px;">
            <div style="font-size:0.85rem; color:#5a7a9a; letter-spacing:3px;">{day_name.upper()}</div>
            <div style="font-size:1.5rem; color:#58CCFF; font-weight:900; letter-spacing:2px;">{date_str}</div>
            <div style="font-size:0.75rem; color:#3a5a7a; margin-top:4px; letter-spacing:2px;">SEMAINE {s_act}</div>
        </div>
        """, unsafe_allow_html=True)

        # ══════════════════════════════════════════
        # GRILLE CALENDRIER 7 JOURS (semaine en cours, lundi -> dimanche)
        # ══════════════════════════════════════════
        # Calcul du lundi de la semaine en cours en heure de Paris
        _today_p = today_paris()
        _monday = _today_p - timedelta(days=_today_p.weekday())
        _week_dates = [(_monday + timedelta(days=k)) for k in range(7)]

        # Helper : calcule le statut d'une journée à partir des données réelles
        def _day_status(day_date):
            """Renvoie {status, title, badge, color} basé sur les perfs réelles."""
            d_str = day_date.strftime("%Y-%m-%d")
            day_rows = df_h[df_h["Date"] == d_str]
            real = day_rows[
                (day_rows["Exercice"] != "SESSION") &
                ((day_rows["Poids"] > 0) | (day_rows["Reps"] > 0) |
                 day_rows["Remarque"].fillna("").str.contains("SKIP", na=False))
            ]
            if not real.empty:
                top = real.groupby("Séance")["Exercice"].nunique().sort_values(ascending=False)
                return {"status": "done", "title": str(top.index[0]),
                        "badge": "FAIT", "color": "#00FF7F"}
            if day_date < _today_p:
                return {"status": "missed", "title": "Manquée",
                        "badge": "MANQUÉE", "color": "#FF453A"}
            if day_date == _today_p:
                return {"status": "today", "title": "Séance à faire",
                        "badge": "AUJOURD'HUI", "color": "#58CCFF"}
            return {"status": "upcoming", "title": "Séance à faire",
                    "badge": "À VENIR", "color": "#5a7a9a"}

        st.markdown("### :material/calendar_view_week: Cette semaine")

        for _i, _d in enumerate(_week_dates):
            _day_label = _DAYS_FR[_i]
            _stinfo = _day_status(_d)
            _date_short = f"{_d.day:02d}/{_d.month:02d}"
            _is_today = (_d == _today_p)

            _border = "2px" if _is_today else "1px"
            _bg_card = f"rgba({','.join(['88','204','255'])},0.08)" if _is_today else "rgba(255,255,255,0.03)"

            # Carte entière cliquable via <a href="?day_click=N">
            st.markdown(
                f"""<a href="?day_click={_i}" target="_self" style="text-decoration:none; display:block;">
                 <div style='background:{_bg_card}; border:{_border} solid {_stinfo['color']}66;
                     border-radius:12px; padding:10px 14px; margin-bottom:6px;
                     display:flex; align-items:center; justify-content:space-between;
                     cursor:pointer;'>
                     <div>
                       <div style='font-size:11px; color:#5a7a9a; letter-spacing:2px;'>{_day_label.upper()} · {_date_short}</div>
                       <div style='font-size:1rem; color:#fff; font-weight:700; margin-top:2px;'>{_stinfo['title']}</div>
                     </div>
                     <div style='font-size:11px; color:{_stinfo['color']}; font-weight:800; letter-spacing:1px;'>
                       {_stinfo['badge']}
                     </div>
                 </div>
                </a>""",
                unsafe_allow_html=True
            )

        st.divider()

        # Stats semaine
        vol_week = int((df_h[df_h["Semaine"] == s_act]["Poids"] * df_h[df_h["Semaine"] == s_act]["Reps"]).sum())
        vol_week_formatted = f"{vol_week:,}".replace(',', ' ')
        sessions_done = len(df_h[(df_h["Semaine"] == s_act) & (df_h["Poids"] > 0)]["Séance"].unique())
        total_sessions = len(prog_seances.keys())

        if not df_h.empty:
            weeks_with_data = sorted(df_h[df_h["Poids"] > 0]["Semaine"].unique(), reverse=True)
            streak = 0
            for i, week in enumerate(weeks_with_data):
                if i == 0 or week == weeks_with_data[i-1] - 1:
                    streak += 1
                else:
                    break
        else:
            streak = 0

        widget_html = f"""<!DOCTYPE html><html><head><style>
        body{{margin:0;padding:6px;background:transparent;overflow:hidden;font-family:'Courier New',monospace;}}
        </style></head><body>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;">
            <div style="background:rgba(88,204,255,0.06);border:1px solid rgba(88,204,255,0.25);border-radius:12px;padding:14px;text-align:center;">
                <div style="font-size:0.75rem;color:#5a8aaa;letter-spacing:2px;">SÉANCES</div>
                <div style="font-size:2rem;color:#58CCFF;font-weight:900;">{sessions_done}/{total_sessions}</div>
            </div>
            <div style="background:rgba(0,255,127,0.06);border:1px solid rgba(0,255,127,0.25);border-radius:12px;padding:14px;text-align:center;">
                <div style="font-size:0.75rem;color:#3a8a5a;letter-spacing:2px;">VOLUME</div>
                <div style="font-size:2rem;color:#00FF7F;font-weight:900;">{vol_week_formatted}</div>
                <div style="font-size:0.7rem;color:#3a6a4a;">kg cette semaine</div>
            </div>
        </div>
        <div style="background:rgba(255,215,0,0.07);border:1px solid rgba(255,215,0,0.25);border-radius:12px;padding:12px;text-align:center;">
            <div style="font-size:0.75rem;color:#8a7a2a;letter-spacing:2px;">🔥 STREAK</div>
            <div style="font-size:1.6rem;color:#FFD700;font-weight:900;">{streak} SEMAINE{"S" if streak > 1 else ""}</div>
        </div>
        </body></html>"""
        components.html(widget_html, height=185, scrolling=False)

        st.markdown("### :material/analytics: DÉTAIL")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric(":material/fitness_center: Exercices", len(df_h[(df_h["Semaine"] == s_act) & (df_h["Poids"] > 0)]["Exercice"].unique()))
        with col_m2:
            st.metric(":material/format_list_numbered: Séries", len(df_h[(df_h["Semaine"] == s_act) & (df_h["Poids"] > 0)]))
        with col_m3:
            total_reps = int(df_h[df_h["Semaine"] == s_act]["Reps"].sum())
            st.metric(":material/track_changes: Reps", total_reps)

# --- ONGLET GESTION ---
with tab_p:
    st.markdown("# :material/settings: GESTION")
    st.caption("Tous les réglages, le programme et les opérations admin sont regroupés ici.")

    # ══════════════════════════════════════════
    # SECTION 1 : PARAMÈTRES VISUELS
    # ══════════════════════════════════════════
    with st.expander(":material/tune: Paramètres d'affichage", expanded=False):
        _s = st.session_state.settings
        _s['auto_collapse'] = st.toggle(
            "Replier automatiquement les exercices terminés",
            value=_s.get('auto_collapse', True),
            key="set_auto_collapse"
        )
        _s['show_1rm'] = st.toggle(
            "Afficher l'estimation 1RM",
            value=_s.get('show_1rm', True),
            key="set_show_1rm"
        )
        _s['theme_animations'] = st.toggle(
            "Animations du thème (cartes, glow, pulse)",
            value=_s.get('theme_animations', True),
            key="set_theme_anim",
            help="Désactive si l'app est lente sur ton mobile"
        )
        _s['show_previous_weeks'] = st.number_input(
            "Nombre de semaines précédentes affichées dans la séance",
            min_value=0, max_value=10,
            value=int(_s.get('show_previous_weeks', 2)),
            key="set_prev_weeks"
        )

    st.divider()

    # ══════════════════════════════════════════
    # SECTION 2 : PLANNING HEBDOMADAIRE
    # ══════════════════════════════════════════
    st.markdown("## :material/event: Planning hebdomadaire")
    st.caption("Assigne une séance à chaque jour de la semaine. Laisser vide = jour de repos.")
    _seance_options = ["— Repos —"] + list(prog_seances.keys())
    _planning_changed = False
    for _day in _DAYS_FR:
        _curr_assigned = prog['_planning'].get(_day, "")
        _idx = _seance_options.index(_curr_assigned) if _curr_assigned in _seance_options else 0
        _new = st.selectbox(_day, _seance_options, index=_idx, key=f"plan_{_day}")
        _new_val = "" if _new == "— Repos —" else _new
        if _new_val != _curr_assigned:
            prog['_planning'][_day] = _new_val
            _planning_changed = True
    if _planning_changed:
        save_prog(prog)
        st.toast("Planning sauvegardé", icon="✅")

    st.divider()

    # ══════════════════════════════════════════
    # SECTION 3 : PROGRAMME & EXERCICES
    # ══════════════════════════════════════════
    st.markdown("## :material/calendar_month: Programme & exercices")
    jours = list(prog_seances.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"📦 {j}"):
            c_s1, c_s2 = st.columns(2)
            if c_s1.button("⬆️ Monter Séance", key=f"up_s_{j}") and idx_j > 0:
                jours[idx_j], jours[idx_j-1] = jours[idx_j-1], jours[idx_j]
                save_prog({**{k: v for k, v in prog.items() if k.startswith('_')}, **{k: prog[k] for k in jours}})
                st.rerun()
            if c_s2.button("🗑️ Supprimer Séance", key=f"del_s_{j}"):
                del prog[j]
                save_prog(prog)
                st.rerun()
            for i, ex in enumerate(prog[j]):
                c1, c2, c3, c4, c5, c6 = st.columns([3, 1.5, 1.5, 0.7, 0.7, 0.7])
                c1.write(f"**{ex['name']}**")
                ex['sets'] = c2.number_input("Sets", 1, 15, ex.get('sets', 3), key=f"p_s_{j}_{i}")
                _ML = ["Pecs","Dos","Épaules","Biceps","Triceps","Avant-bras","Abdos","Quadriceps","Ischio-jambiers","Fessiers","Mollets","Autre"]
                _mv = ex.get("muscle","Autre")
                # Rétro-compat : valeur peut être "Bras","Jambes" ou multi "Pecs,Triceps"
                _cur = [v.strip() for v in _mv.split(",") if v.strip() in _ML] or ["Autre"]
                _sel = c3.multiselect("Muscle(s)", _ML, default=_cur, key=f"m_{j}_{i}")
                ex['muscle'] = ",".join(_sel) if _sel else "Autre"
                if c4.button("⬆️", key=f"ue_{j}_{i}"):
                    if i > 0: prog[j][i], prog[j][i-1] = prog[j][i-1], prog[j][i]; save_prog(prog); st.rerun()
                if c5.button("⬇️", key=f"de_{j}_{i}"):
                    if i < len(prog[j])-1: prog[j][i], prog[j][i+1] = prog[j][i+1], prog[j][i]; save_prog(prog); st.rerun()
                if c6.button("🗑️", key=f"rm_{j}_{i}"):
                    prog[j].pop(i); save_prog(prog); st.rerun()
            st.divider()
            cx, cm, cs = st.columns([3, 2, 1])
            _ML2 = ["Pecs","Dos","Épaules","Biceps","Triceps","Avant-bras","Abdos","Quadriceps","Ischio-jambiers","Fessiers","Mollets","Autre"]
            ni, ns = cx.text_input("Nouvel exo", key=f"ni_{j}"), cs.number_input("Séries", 1, 15, 3, key=f"ns_{j}")
            _nm_sel = cm.multiselect("Muscle(s)", _ML2, default=["Autre"], key=f"nm_{j}")
            nm = ",".join(_nm_sel) if _nm_sel else "Autre"
            if st.button("➕ Ajouter", key=f"ba_{j}") and ni:
                prog[j].append({"name": ni, "sets": ns, "muscle": nm}); save_prog(prog); st.rerun()
    nvs = st.text_input("➕ Créer séance")
    if st.button("🎯 Valider") and nvs: prog[nvs] = []; save_prog(prog); st.rerun()

    st.divider()

    # ══════════════════════════════════════════
    # SECTION 3 : OPÉRATIONS AVANCÉES (DANGER)
    # ══════════════════════════════════════════
    st.markdown("## :material/build: Opérations avancées")
    with st.expander(":material/auto_fix_high: Auto-assigner les muscles"):
        if st.button(":material/auto_fix_high: Lancer l'auto-assignation", type="primary", use_container_width=True, help="Assigne automatiquement les muscles selon le nom de chaque exercice"):
            updated, skipped = [], []
            for s in prog_seances:
                for ex in prog[s]:
                    new_m = auto_muscles(ex["name"])
                    if new_m:
                        ex["muscle"] = new_m
                        updated.append(f"{ex['name']} → {new_m}")
                    else:
                        skipped.append(ex["name"])
            save_prog(prog)
            if updated:
                st.success(f"✅ {len(updated)} exercice(s) mis à jour")
                with st.expander("Détail"):
                    for line in updated: st.caption(line)
            if skipped:
                st.warning(f":material/warning: {len(skipped)} exercice(s) non reconnus : {', '.join(skipped)}")
            st.rerun()

    with st.expander(":material/restart_alt: Réinitialiser les séances (soft, conserve l'archive)"):
        st.warning("Remet à zéro l'historique. Les records sont conservés dans l'archive et resteront visibles dans l'onglet Progrès.")
        if st.button(":material/warning: Confirmer le reset soft", type="primary", key="reset_all"):
            v_tot_save = int((df_h['Poids'] * df_h['Reps']).sum()) if not df_h.empty else 0
            prog['_legacy_volume'] = prog.get('_legacy_volume', 0) + v_tot_save
            if not df_h.empty:
                arch_src = df_h[df_h['Reps'] > 0].copy()
                if not arch_src.empty:
                    weekly_max = arch_src.groupby(['Exercice', 'Semaine']).apply(
                        lambda g: pd.Series({'Poids': g['Poids'].max(), 'Reps': int(g.loc[g['Poids'].idxmax(), 'Reps']), 'Muscle': g['Muscle'].iloc[0]})
                    ).reset_index()
                    existing = prog.get('_archive', [])
                    existing.extend(weekly_max.to_dict('records'))
                    prog['_archive'] = existing[-2000:]
            save_prog(prog)
            save_hist(pd.DataFrame(columns=["Semaine","Séance","Exercice","Série","Reps","Poids","Remarque","Muscle","Date"]))
            st.success("Reset soft effectué. Reprends en semaine 1.")
            st.rerun()

    with st.expander(":material/delete_forever: RESET TOTAL (efface tout, sans retour)"):
        st.error("⚠️ Efface DÉFINITIVEMENT : historique + archive + records + extras. "
                 "Le programme et le planning hebdo sont conservés.")
        _confirm_total = st.checkbox("Je comprends, je veux tout effacer", key="reset_total_chk")
        if st.button(":material/delete_forever: RESET TOTAL", type="primary", key="reset_total_btn",
                     disabled=not _confirm_total):
            # 1. Vide l'historique Sheet
            save_hist(pd.DataFrame(columns=["Semaine","Séance","Exercice","Série","Reps","Poids","Remarque","Muscle","Date"]))
            # 2. Vide l'archive et le volume legacy dans le programme
            prog.pop('_archive', None)
            prog.pop('_legacy_volume', None)
            save_prog(prog)
            # 3. Vide les caches
            get_hist.clear()
            get_prog.clear()
            # 4. Vide les états transitoires de la session
            st.session_state.extra_exos = {}
            st.session_state.editing_exo = set()
            st.session_state.seance_libre_exos = []
            st.session_state.seance_target_date = None
            st.session_state.seance_selectionnee = None
            st.session_state.mode_seance = None
            # Purge tous les compteurs extra_sets_*
            for _k in list(st.session_state.keys()):
                if isinstance(_k, str) and (_k.startswith("extra_sets_") or _k.startswith("conf_reset_")):
                    del st.session_state[_k]
            st.success("Reset total effectué. Tout est vide.")
            st.rerun()

    with st.expander(":material/delete_sweep: Vider uniquement l'archive"):
        st.warning("Supprime les records historiques archivés mais garde l'historique en cours.")
        if st.button(":material/warning: Confirmer la suppression de l'archive", type="primary", key="clear_archive"):
            prog.pop('_archive', None)
            prog.pop('_legacy_volume', None)
            save_prog(prog)
            st.success("Archive vidée.")
            st.rerun()

# ============================================================
# ONGLET MA SÉANCE : trois modes -> libre, aucun, pré-faite
# ============================================================
with tab_s:
    _MUSCLE_LIST_S = ["Pecs","Dos","Épaules","Biceps","Triceps","Avant-bras","Abdos",
                      "Quadriceps","Ischio-jambiers","Fessiers","Mollets","Autre"]

    # ══════════════════════════════════════════════════════════
    # MODE LIBRE : séance personnalisée construite à la volée
    # ══════════════════════════════════════════════════════════
    if st.session_state.mode_seance == 'libre':

        c_tl, c_tr = st.columns([3, 1])
        with c_tl:
            st.markdown("### :material/edit_note: SÉANCE PERSONNALISÉE")
        with c_tr:
            if st.button(":material/close: Annuler la séance", key="libre_fin", use_container_width=True):
                # Mode libre = pas d'enregistrement "manquée" : on ferme juste
                st.session_state.mode_seance = None
                st.session_state.seance_libre_exos = []
                st.session_state.seance_selectionnee = None
                st.session_state.seance_target_date = None
                st.session_state.view = 'accueil'
                st.rerun()

        # Date cible (rattrapage) capturée une fois pour toute la séance libre
        _libre_target = st.session_state.seance_target_date
        _libre_date = _libre_target or today_paris_str()

        # Banderole visible si rattrapage
        if _libre_target:
            try:
                _lt_dt = datetime.strptime(_libre_target, "%Y-%m-%d").date()
                _lt_lbl = f"{_DAYS_FR[_lt_dt.weekday()]} {_lt_dt.day:02d}/{_lt_dt.month:02d}/{_lt_dt.year}"
                st.markdown(
                    f"<div style='background:rgba(255,149,0,0.12); border:1px solid rgba(255,149,0,0.4);"
                    f" border-radius:10px; padding:8px 12px; margin-bottom:10px;'>"
                    f"<span style='font-size:11px; color:#FF9500; letter-spacing:2px;'>RATTRAPAGE · </span>"
                    f"<span style='font-size:13px; color:#fff; font-weight:700;'>{_lt_lbl}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            except Exception:
                pass

        # Calcule la semaine ISO correspondant à la date cible (pour un rattrapage cohérent)
        try:
            _iso_w_libre = datetime.strptime(_libre_date, "%Y-%m-%d").isocalendar().week
        except Exception:
            _iso_w_libre = int(df_h["Semaine"].max() if not df_h.empty else 1)

        s_act_l = st.number_input("Semaine", 1, 52, _iso_w_libre, key=f"semaine_libre_{_libre_date}")
        nom_libre = st.text_input("Nom de la séance", value="Séance Libre", key="nom_libre")

        st.divider()

        # Afficher les exercices déjà ajoutés
        for li, exo_obj in enumerate(st.session_state.seance_libre_exos):
            exo_base_l = exo_obj['name']
            muscle_grp_l = exo_obj.get('muscle', 'Autre')
            p_sets_l = exo_obj.get('sets', 3)

            # Calcul précoce de exo_final_l à partir de la valeur déjà en session_state
            # (la selectbox met à jour la clé dès le 1er render)
            _var_pre_l = st.session_state.get(f"vl_{exo_base_l}_{li}", "Standard")
            exo_final_l_pre = f"{exo_base_l} ({_var_pre_l})" if _var_pre_l != "Standard" else exo_base_l

            # Auto-collapse : on referme l'exo quand il a déjà des données saisies
            # Correspondance exacte sur la variante pour ne pas croiser deux variantes du même exo
            _curr_check_l = df_h[
                (df_h["Exercice"] == exo_final_l_pre) &
                (df_h["Séance"] == nom_libre) &
                (df_h["Semaine"] == s_act_l)
            ]
            _has_data_l = (not _curr_check_l.empty) and (
                _curr_check_l["Poids"].sum() > 0
                or _curr_check_l["Reps"].sum() > 0
                or _curr_check_l["Remarque"].str.contains("SKIP", na=False).any()
            )
            _expanded_l = (not _has_data_l) or (exo_final_l_pre in st.session_state.editing_exo)

            with st.expander(f"🔹 {exo_base_l.upper()}", expanded=_expanded_l):
                col_rm = st.columns([4, 1])
                with col_rm[1]:
                    if st.button("✕", key=f"rm_libre_{li}", help="Retirer cet exercice"):
                        st.session_state.seance_libre_exos.pop(li)
                        st.rerun()

                variants_l = ["Standard", "Barre", "Haltères", "Banc", "Poulie", "Machine", "Lesté"]
                var_l = col_rm[0].selectbox("Équipement", variants_l, key=f"vl_{exo_base_l}_{li}")
                exo_final_l = f"{exo_base_l} ({var_l})" if var_l != "Standard" else exo_base_l

                # Record perso toutes séances, spécifique à la variante sélectionnée
                _BW_EXOS = {"Dips", "Tractions"}
                _is_bw_l = (exo_base_l in _BW_EXOS and var_l != "Lesté")
                f_h_l = df_h[df_h["Exercice"] == exo_final_l]
                if not f_h_l.empty and not f_h_l[f_h_l["Reps"] > 0].empty:
                    if _is_bw_l:
                        _best_reps_l = int(f_h_l[f_h_l["Reps"] > 0]["Reps"].max())
                        st.caption(f"🏆 Record : **{_best_reps_l} reps**")
                    else:
                        best_w_l = f_h_l["Poids"].max()
                        best_1rm_l = f_h_l[f_h_l["Reps"] > 0].apply(
                            lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1).max()
                        st.caption(f"🏆 Record : **{best_w_l:g}kg** | ⚡ 1RM estimé : **{best_1rm_l:.1f}kg**")

                curr_l = df_h[(df_h["Exercice"] == exo_final_l) &
                              (df_h["Séance"] == nom_libre) &
                              (df_h["Semaine"] == s_act_l)]

                # Compteur de séries supplémentaires (survit au rerun)
                _ek_extra_l = f"extra_sets_libre_{exo_final_l}_{s_act_l}_{li}"
                extra_n_l = int(st.session_state.get(_ek_extra_l, 0))
                if st.button(":material/add: +1 série", key=f"add_set_libre_{li}", use_container_width=True):
                    st.session_state[_ek_extra_l] = extra_n_l + 1
                    st.rerun()

                _n_rows_l = max(p_sets_l, len(curr_l)) if not curr_l.empty else p_sets_l
                _n_rows_l += extra_n_l
                if _is_bw_l:
                    df_base_l = pd.DataFrame({"Reps": [0]*_n_rows_l, "Remarque": [""]*_n_rows_l},
                                             index=pd.RangeIndex(1, _n_rows_l + 1, name="Série"))
                    if not curr_l.empty:
                        for _, rl in curr_l.iterrows():
                            idx_l = int(rl["Série"])
                            if idx_l in df_base_l.index:
                                df_base_l.loc[idx_l, ["Reps","Remarque"]] = [rl["Reps"], rl["Remarque"]]
                    ed_l = st.data_editor(df_base_l, num_rows="dynamic", key=f"edl_{exo_final_l}_{s_act_l}_{li}",
                                          use_container_width=True, hide_index=False)
                else:
                    df_base_l = pd.DataFrame({"Reps": [0]*_n_rows_l, "Poids": [0.0]*_n_rows_l, "Remarque": [""]*_n_rows_l},
                                             index=pd.RangeIndex(1, _n_rows_l + 1, name="Série"))
                    if not curr_l.empty:
                        for _, rl in curr_l.iterrows():
                            idx_l = int(rl["Série"])
                            if idx_l in df_base_l.index:
                                df_base_l.loc[idx_l, ["Reps","Poids","Remarque"]] = [rl["Reps"], rl["Poids"], rl["Remarque"]]
                    ed_l = st.data_editor(df_base_l, num_rows="dynamic", key=f"edl_{exo_final_l}_{s_act_l}_{li}",
                                          use_container_width=True, hide_index=False,
                                          column_config={"Poids": st.column_config.NumberColumn(format="%g")})

                c_sv_l, c_sk_l = st.columns(2)
                if c_sv_l.button(":material/save: Enregistrer", key=f"svl_{exo_final_l}_{li}"):
                    vl = ed_l.reset_index()
                    vl["Série"] = range(1, len(vl) + 1)
                    if _is_bw_l:
                        vl["Poids"] = 0.0
                    vl["Semaine"] = s_act_l
                    vl["Séance"] = nom_libre
                    vl["Exercice"] = exo_final_l
                    vl["Muscle"] = muscle_grp_l
                    vl["Date"] = _libre_date
                    mask = ~((df_h["Semaine"] == s_act_l) & (df_h["Exercice"] == exo_final_l) & (df_h["Séance"] == nom_libre))
                    save_hist(pd.concat([df_h[mask], vl], ignore_index=True))
                    st.session_state.pop(_ek_extra_l, None)
                    st.rerun()
                if c_sk_l.button(":material/skip_next: Skip", key=f"skl_{exo_final_l}_{li}"):
                    vsk = pd.DataFrame([{"Semaine": s_act_l, "Séance": nom_libre,
                                         "Exercice": exo_final_l, "Série": 1,
                                         "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫",
                                         "Muscle": muscle_grp_l,
                                         "Date": _libre_date}])
                    mask = ~((df_h["Semaine"] == s_act_l) & (df_h["Exercice"] == exo_final_l) & (df_h["Séance"] == nom_libre))
                    save_hist(pd.concat([df_h[mask], vsk], ignore_index=True))
                    st.rerun()

        # ── Recommencer la séance libre (confirmation inline) ────────────────
        if st.session_state.get('confirming_reset_libre'):
            st.warning("Effacer toutes les données de cette séance ?")
            _rl1, _rl2, _rl3 = st.columns(3)
            if _rl1.button(":material/check: Effacer données", type="primary", key="libre_conf_data"):
                save_hist(df_h[~((df_h["Semaine"] == s_act_l) & (df_h["Séance"] == nom_libre))])
                st.session_state.confirming_reset_libre = False
                st.rerun()
            if _rl2.button(":material/delete: Tout recommencer", key="libre_conf_all"):
                save_hist(df_h[~((df_h["Semaine"] == s_act_l) & (df_h["Séance"] == nom_libre))])
                st.session_state.seance_libre_exos = []
                st.session_state.confirming_reset_libre = False
                st.rerun()
            if _rl3.button(":material/close: Annuler", key="libre_conf_cancel"):
                st.session_state.confirming_reset_libre = False
                st.rerun()
        else:
            if st.button(":material/refresh: Recommencer cette séance", use_container_width=True, key="libre_reset_btn"):
                st.session_state.confirming_reset_libre = True
                st.rerun()

        # ── Bouton ajouter exercice ────────────────────────────────────────────
        with st.expander(":material/add_circle: Ajouter un exercice", expanded=len(st.session_state.seance_libre_exos) == 0):
            mode_ajout = st.radio("", ["Depuis mes programmes", "Nouvel exercice"],
                                  horizontal=True, key="libre_mode_ajout")

            if mode_ajout == "Depuis mes programmes":
                # Tous les exercices de tous les programmes (dédupliqués)
                all_prog_exos = {}
                for _sn, _exos in prog_seances.items():
                    for _e in _exos:
                        if _e['name'] not in all_prog_exos:
                            all_prog_exos[_e['name']] = _e

                muscle_filter = st.selectbox("Filtrer par muscle",
                                             ["Tous"] + _MUSCLE_LIST_S,
                                             key="libre_muscle_filter")
                filtered_exos = [e for e in all_prog_exos.values()
                                 if muscle_filter == "Tous"
                                 or muscle_filter in str(e.get('muscle', ''))]

                # Pas de dédup : on autorise le même exercice plusieurs fois
                # (l'utilisateur choisira ensuite une variante différente par bloc)
                for _fe in filtered_exos:
                    _col_n, _col_b = st.columns([3, 1])
                    _col_n.write(f"**{_fe['name']}** · {_fe.get('muscle','')}")
                    if _col_b.button("+ Ajouter", key=f"add_prog_{_fe['name']}"):
                        st.session_state.seance_libre_exos.append({
                            "name": _fe['name'],
                            "muscle": _fe.get('muscle', 'Autre'),
                            "sets": _fe.get('sets', 3)
                        })
                        st.rerun()

            else:  # Nouvel exercice
                new_name = st.text_input("Nom de l'exercice", key="libre_new_name")
                new_muscle = st.selectbox("Muscle principal", _MUSCLE_LIST_S, key="libre_new_muscle")
                new_sets = st.number_input("Nombre de séries", 1, 10, 3, key="libre_new_sets")
                if st.button(":material/add: Ajouter cet exercice", key="libre_add_new",
                             disabled=not new_name.strip()):
                    # Auto-détect muscle si non renseigné. Doublons autorisés.
                    detected = auto_muscles(new_name.strip())
                    muscle_final = detected if detected else new_muscle
                    st.session_state.seance_libre_exos.append({
                        "name": new_name.strip(),
                        "muscle": muscle_final,
                        "sets": int(new_sets)
                    })
                    st.rerun()

        # ── Bouton Terminer la séance libre ───────────────────────────────────
        if st.session_state.seance_libre_exos:
            st.divider()
            if st.button(":material/check_circle: Terminer la séance", type="primary",
                         use_container_width=True, key="libre_done"):
                st.session_state.mode_seance = None
                st.session_state.seance_libre_exos = []
                st.session_state.seance_selectionnee = None
                st.session_state.seance_target_date = None
                st.session_state.view = 'accueil'
                st.rerun()

    # ══════════════════════════════════════════════════════════
    # AUCUNE SÉANCE SÉLECTIONNÉE
    # ══════════════════════════════════════════════════════════
    elif st.session_state.mode_seance is None:
        st.markdown("""
        <div style="text-align:center; padding:60px 20px;">
            <div style="font-size:3rem; margin-bottom:16px;">🏋️</div>
            <div style="font-size:1.2rem; color:#fff; font-weight:700; margin-bottom:8px;">Aucune séance en cours</div>
            <div style="font-size:0.9rem; color:#5a7a9a;">Retourne sur l'accueil et clique sur<br><b style="color:#58CCFF;">COMMENCER UNE SÉANCE</b></div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("← Aller à l'accueil", use_container_width=True, key="seance_back_home"):
            st.session_state.view = 'accueil'
            components.html("""<script>
            setTimeout(function(){
                var tabs = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
                for (var i=0; i<tabs.length; i++){
                    if (tabs[i].textContent.indexOf('ACCUEIL') !== -1){
                        tabs[i].click(); break;
                    }
                }
            }, 120);
            </script>""", height=0)

    # ══════════════════════════════════════════════════════════
    # MODE PRÉ-FAITE
    # ══════════════════════════════════════════════════════════
    elif prog:
        # Date cible (rattrapage) capturée une fois pour toute la séance
        _pf_target = st.session_state.seance_target_date
        _pf_date = _pf_target or today_paris_str()

        c_h1, c_h2, c_h3 = st.columns([2, 1, 1])
        # Semaine pré-remplie = semaine ISO de la date cible (rattrapage cohérent)
        try:
            _pf_iso_w = datetime.strptime(_pf_date, "%Y-%m-%d").isocalendar().week
        except Exception:
            _pf_iso_w = int(df_h["Semaine"].max() if not df_h.empty else 1)
        s_act = c_h2.number_input("Semaine actuelle", 1, 52, _pf_iso_w, key=f"semaine_pf_{_pf_date}")
        
        # AUTO-SÉLECTION AVEC SKIP
        def get_current_session():
            for seance in prog_seances.keys():
                seance_data = df_h[(df_h["Séance"] == seance) & (df_h["Semaine"] == s_act)]
                if seance_data.empty:
                    return seance
                # Skip si marquée comme manquée
                if not seance_data[seance_data["Exercice"] == "SESSION"].empty:
                    continue
                exos_prog = len([ex for ex in prog_seances[seance]])
                exos_done_or_skipped = len(seance_data[(seance_data["Poids"] > 0) | (seance_data["Remarque"].str.contains("SKIP", na=False))]["Exercice"].unique())
                if exos_done_or_skipped < exos_prog:
                    return seance
            return list(prog_seances.keys())[0] if prog_seances else None

        # Priorité : séance choisie depuis l'accueil → legacy home_selected_session → auto
        if st.session_state.seance_selectionnee and st.session_state.seance_selectionnee in prog_seances:
            choix_s = st.session_state.seance_selectionnee
            # Banderole : nom + date cible (utile en cas de rattrapage)
            _td = st.session_state.seance_target_date
            _td_label = ""
            if _td:
                try:
                    _td_dt = datetime.strptime(_td, "%Y-%m-%d").date()
                    _td_label = f" · {_DAYS_FR[_td_dt.weekday()]} {_td_dt.day:02d}/{_td_dt.month:02d}"
                except Exception:
                    pass
            with c_h1:
                st.markdown(
                    f"<div style='padding:6px 4px 0;'>"
                    f"<div style='font-size:11px; color:#5a7a9a; letter-spacing:2px;'>SÉANCE{_td_label.upper()}</div>"
                    f"<div style='font-size:1.05rem; color:#58CCFF; font-weight:800;'>{choix_s}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                if st.button("↺ Changer de séance", key="changer_seance", use_container_width=True):
                    st.session_state.seance_selectionnee = None
                    st.session_state.mode_seance = None
                    st.session_state.seance_target_date = None
                    st.session_state.view = 'accueil'
                    st.rerun()
        else:
            default_s = st.session_state.pop('home_selected_session', None) or get_current_session()
            s_index = list(prog_seances.keys()).index(default_s) if default_s and default_s in prog_seances.keys() else 0
            choix_s = c_h1.selectbox("Séance :", list(prog_seances.keys()), index=s_index)
        
        if c_h3.button(":material/flag: Séance Manquée", use_container_width=True):
            # Évite le doublon si déjà marquée
            _already_miss = df_h[
                (df_h["Séance"] == choix_s) &
                (df_h["Semaine"] == s_act) &
                (df_h["Exercice"] == "SESSION")
            ]
            if _already_miss.empty:
                m_rec = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": "SESSION", "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SÉANCE MANQUÉE 🚩", "Muscle": "Autre", "Date": _pf_date}])
                save_hist(pd.concat([df_h, m_rec], ignore_index=True))
            # Ferme la séance et revient à l'accueil
            st.session_state.mode_seance = None
            st.session_state.seance_selectionnee = None
            st.session_state.seance_target_date = None
            st.session_state.extra_exos.pop(choix_s, None)
            st.session_state.view = 'accueil'
            st.rerun()
        
        # Recommencer séance — confirmation inline
        current_session_data = df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]
        if st.session_state.get('confirming_reset_seance') == choix_s:
            st.warning(f"⚠️ Effacer **{choix_s}** semaine **{s_act}** ?")
            _cr1, _cr2 = st.columns(2)
            if _cr1.button(":material/check: Recommencer", type="primary", key="seance_confirm_yes"):
                save_hist(df_h[~((df_h["Semaine"] == s_act) & (df_h["Séance"] == choix_s))])
                st.session_state.confirming_reset_seance = None
                st.rerun()
            if _cr2.button(":material/close: Annuler", key="seance_confirm_no"):
                st.session_state.confirming_reset_seance = None
                st.rerun()
        else:
            if not current_session_data.empty:
                if st.button(":material/refresh: Recommencer cette séance", use_container_width=True, key="reset_seance_btn"):
                    st.session_state.confirming_reset_seance = choix_s
                    st.rerun()

        st.markdown("### :material/battery_charging_full: RÉCUPÉRATION")
        recup_cols = ["Pecs","Dos","Épaules","Biceps","Triceps","Abdos","Quadriceps","Mollets"]
        html_recup = "<div class='recup-container'>"
        for m in recup_cols:
            trained_this_week = df_h[df_h["Muscle"].str.contains(m, regex=False, na=False) & (df_h["Semaine"] == s_act)]
            sc, lab = "#00FF7F", "PRET"
            if not trained_this_week.empty:
                last_d = trained_this_week["Date"].max()
                if pd.notna(last_d) and last_d != "":
                    try:
                        diff = (now_paris().replace(tzinfo=None) - datetime.strptime(last_d, "%Y-%m-%d")).days
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

        # Combine programme + extras (exos ajoutés à la volée pour cette séance)
        _extras_seance = st.session_state.extra_exos.get(choix_s, [])
        _exos_seance = list(prog[choix_s]) + list(_extras_seance)
        _n_prog = len(prog[choix_s])
        for i, ex_obj in enumerate(_exos_seance):
            exo_base, p_sets, muscle_grp = ex_obj["name"], ex_obj.get("sets", 3), ex_obj.get("muscle", "Autre")
            _is_extra = i >= _n_prog
            
            # SAUVEGARDER VARIANTE
            variants = ["Standard", "Barre", "Haltères", "Banc", "Poulie", "Machine", "Lesté"]
            last_var_data = df_h[df_h["Exercice"].str.contains(exo_base, regex=False, na=False) & (df_h["Séance"] == choix_s)]
            if not last_var_data.empty:
                last_exo_name = last_var_data.iloc[-1]["Exercice"]
                if "(" in last_exo_name:
                    last_var = last_exo_name.split("(")[1].replace(")", "")
                    var_index = variants.index(last_var) if last_var in variants else 0
                else:
                    var_index = 0
            else:
                var_index = 0

            # Calcul précoce de exo_final à partir de la valeur déjà en session_state
            _var_pre = st.session_state.get(f"v_{exo_base}_{i}", variants[var_index])
            exo_final_pre = f"{exo_base} ({_var_pre})" if _var_pre != "Standard" else exo_base

            # Auto-collapse : exercice replié une fois complété
            # Correspondance exacte sur la variante pour ne pas croiser deux variantes du même exo
            curr_all = df_h[
                (df_h["Exercice"] == exo_final_pre) &
                (df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]
            exo_completed = not curr_all.empty and (
                (curr_all["Poids"].sum() > 0 or curr_all["Reps"].sum() > 0) or
                curr_all["Remarque"].str.contains("SKIP", na=False).any()
            )
            expanded_state = not exo_completed or exo_final_pre in st.session_state.editing_exo

            with st.expander(f"🔹 {exo_base.upper()}", expanded=expanded_state):
                # ── Bouton Recommencer (haut, confirmation inline) ──────────
                _rkey = f"conf_reset_exo_{exo_base}_{i}"
                if st.session_state.get(_rkey):
                    st.warning("Effacer les données de cet exercice ?")
                    _cy, _cn = st.columns(2)
                    if _cy.button(":material/check: Recommencer", type="primary", key=f"yes_r_{exo_base}_{i}"):
                        mask_exo = ~(
                            (df_h["Semaine"] == s_act) &
                            (df_h["Exercice"] == exo_final_pre) &
                            (df_h["Séance"] == choix_s))
                        save_hist(df_h[mask_exo])
                        st.session_state[_rkey] = False
                        st.session_state.editing_exo.discard(exo_final_pre)
                        st.rerun()
                    if _cn.button(":material/close: Annuler", key=f"no_r_{exo_base}_{i}"):
                        st.session_state[_rkey] = False
                        st.rerun()
                else:
                    if curr_all["Poids"].sum() > 0 or curr_all["Reps"].sum() > 0:
                        if st.button(":material/refresh: Recommencer cet exercice", key=f"rec_r_{exo_base}_{i}"):
                            st.session_state[_rkey] = True
                            st.rerun()

                var = st.selectbox("Équipement :", variants, index=var_index, key=f"v_{exo_base}_{i}")
                exo_final = f"{exo_base} ({var})" if var != "Standard" else exo_base
                f_h = df_h[(df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s)]

                all_variants = df_h[df_h["Exercice"].str.contains(exo_base, regex=False, na=False) & (df_h["Séance"] == choix_s)]["Exercice"].unique()
                if len(all_variants) > 1:
                    st.caption(f"ℹ️ Exercice pratiqué avec {len(all_variants)} variantes différentes")

                # Record toutes séances confondues, spécifique à la variante sélectionnée
                _BW_EXOS = {"Dips", "Tractions"}
                _is_bw = (exo_base in _BW_EXOS and var != "Lesté")
                f_h_all = df_h[df_h["Exercice"] == exo_final]
                if not f_h_all.empty:
                    _f_h_reps = f_h_all[f_h_all["Reps"] > 0]
                    if not _f_h_reps.empty:
                        if _is_bw:
                            _best_reps = int(_f_h_reps["Reps"].max())
                            st.caption(f"🏆 Record : **{_best_reps} reps**")
                        else:
                            best_w = f_h_all["Poids"].max()
                            best_1rm = _f_h_reps.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1).max()
                            if st.session_state.settings['show_1rm']:
                                st.caption(f"🏆 Record : **{best_w:g}kg** | ⚡ 1RM : **{best_1rm:.1f}kg**")
                            else:
                                st.caption(f"🏆 Record : **{best_w:g}kg**")

                hist_weeks_all = sorted(f_h[f_h["Semaine"] < s_act]["Semaine"].unique())
                hist_weeks = [w for w in hist_weeks_all if not f_h[(f_h["Semaine"] == w) & (f_h["Poids"] > 0)].empty]
                missed_weeks = set(df_h[
                    (df_h["Séance"] == choix_s) &
                    (df_h["Exercice"] == "SESSION") &
                    (df_h["Semaine"] < s_act)
                ]["Semaine"].unique())

                if hist_weeks and st.session_state.settings['show_previous_weeks'] > 0:
                    weeks_to_show = hist_weeks[-st.session_state.settings['show_previous_weeks']:]
                    min_w = weeks_to_show[0]
                    combined = sorted(set(weeks_to_show) | {w for w in missed_weeks if w >= min_w})
                    for w_num in combined:
                        if w_num in missed_weeks and w_num not in weeks_to_show:
                            st.caption(f"📅 Semaine {w_num} — 🚩 SÉANCE MANQUÉE")
                        else:
                            h_data = f_h[(f_h["Semaine"] == w_num) & (f_h["Poids"] > 0)]
                            if not h_data.empty:
                                st.caption(f"📅 Semaine {w_num}")
                                render_table(h_data[["Série", "Reps", "Poids", "Remarque"]].reset_index(drop=True))
                elif not hist_weeks:
                    st.info("Semaine 1 : Établis tes marques !")

                curr = f_h[f_h["Semaine"] == s_act]
                last_w_num = hist_weeks[-1] if hist_weeks else None
                hist_prev_df = f_h[(f_h["Semaine"] == last_w_num) & (f_h["Poids"] > 0)] if last_w_num is not None else pd.DataFrame()
                is_reset = not curr.empty and (curr["Poids"].sum() == 0 and curr["Reps"].sum() == 0) and "SKIP" not in str(curr["Remarque"].iloc[0])
                editor_key = f"ed_{exo_final}_{s_act}"

                # Clé du compteur d'extra-séries (persistant via session_state)
                _ek_extra = f"extra_sets_{exo_final}_{s_act}"

                if not curr.empty and not is_reset and exo_final not in st.session_state.editing_exo:
                    st.markdown("##### ✅ Validé")
                    render_table(curr[["Série", "Reps", "Poids", "Remarque"]].reset_index(drop=True), hist_prev=hist_prev_df)
                    _cm1, _cm2 = st.columns(2)
                    if _cm1.button(":material/edit: Modifier", key=f"m_{exo_final}_{i}", use_container_width=True):
                        st.session_state.editing_exo.add(exo_final)
                        st.rerun()
                    if _cm2.button(":material/add: +1 série", key=f"add_set_v_{exo_final}_{i}", use_container_width=True):
                        # Passe en mode édition ET ajoute une ligne d'un coup
                        st.session_state.editing_exo.add(exo_final)
                        st.session_state[_ek_extra] = int(st.session_state.get(_ek_extra, 0)) + 1
                        st.rerun()
                else:
                    extra_n = int(st.session_state.get(_ek_extra, 0))
                    if st.button(":material/add: +1 série", key=f"add_set_{exo_final}_{i}", use_container_width=True):
                        st.session_state[_ek_extra] = extra_n + 1
                        st.rerun()

                    # Fix : df_base taille = max(séries programme, séries déjà sauvegardées) + extras
                    n_rows = max(p_sets, len(curr)) if not curr.empty else p_sets
                    n_rows += extra_n
                    if _is_bw:
                        df_base = pd.DataFrame(
                            {"Reps": [0]*n_rows, "Remarque": [""]*n_rows},
                            index=pd.RangeIndex(1, n_rows + 1, name="Série"))
                        if not curr.empty:
                            for _, r in curr.iterrows():
                                idx = int(r["Série"])
                                if idx in df_base.index:
                                    df_base.loc[idx, ["Reps", "Remarque"]] = [r["Reps"], r["Remarque"]]
                        ed = st.data_editor(df_base, num_rows="dynamic", key=editor_key,
                                            use_container_width=True, hide_index=False)
                    else:
                        df_base = pd.DataFrame(
                            {"Reps": [0]*n_rows, "Poids": [0.0]*n_rows, "Remarque": [""]*n_rows},
                            index=pd.RangeIndex(1, n_rows + 1, name="Série"))
                        if not curr.empty:
                            for _, r in curr.iterrows():
                                idx = int(r["Série"])
                                if idx in df_base.index:
                                    df_base.loc[idx, ["Reps", "Poids", "Remarque"]] = [r["Reps"], r["Poids"], r["Remarque"]]
                        ed = st.data_editor(df_base, num_rows="dynamic", key=editor_key,
                                            use_container_width=True, hide_index=False,
                                            column_config={"Poids": st.column_config.NumberColumn(format="%g")})

                    c_save, c_skip = st.columns(2)
                    if c_save.button(":material/save: Enregistrer", key=f"sv_{exo_final}_{i}"):
                        v = ed.reset_index()
                        v["Série"] = range(1, len(v) + 1)
                        if _is_bw:
                            v["Poids"] = 0.0
                        v["Semaine"], v["Séance"], v["Exercice"], v["Muscle"], v["Date"] = s_act, choix_s, exo_final, muscle_grp, _pf_date
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s))], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo_final)
                        st.session_state.pop(_ek_extra, None)
                        st.rerun()

                    if c_skip.button(":material/skip_next: Skip Exo", key=f"sk_{exo_final}_{i}"):
                        v_skip = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": exo_final, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫", "Muscle": muscle_grp, "Date": _pf_date}])
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s))], v_skip], ignore_index=True))
                        st.session_state.pop(_ek_extra, None)
                        st.rerun()

                # Bouton retirer un extra (uniquement pour les exos ajoutés à la volée)
                if _is_extra:
                    if st.button(":material/delete: Retirer cet exercice", key=f"rm_extra_{choix_s}_{i}"):
                        _idx_extra = i - _n_prog
                        st.session_state.extra_exos[choix_s].pop(_idx_extra)
                        st.rerun()

        # ── Ajouter un exercice à la séance pré-faite ─────────────────────────
        with st.expander(":material/add_circle: Ajouter un exercice à cette séance",
                         expanded=False):
            _mode_pref = st.radio("", ["Depuis mes programmes", "Nouvel exercice"],
                                  horizontal=True, key=f"pref_mode_ajout_{choix_s}")

            if _mode_pref == "Depuis mes programmes":
                _all_exos_p = {}
                for _sn, _exos in prog_seances.items():
                    for _e in _exos:
                        if _e['name'] not in _all_exos_p:
                            _all_exos_p[_e['name']] = _e

                _muscle_filter_p = st.selectbox("Filtrer par muscle",
                                                ["Tous"] + _MUSCLE_LIST_S,
                                                key=f"pref_muscle_filter_{choix_s}")
                _filtered_p = [e for e in _all_exos_p.values()
                               if _muscle_filter_p == "Tous"
                               or _muscle_filter_p in str(e.get('muscle', ''))]

                for _fe in _filtered_p:
                    _cn, _cb = st.columns([3, 1])
                    _cn.write(f"**{_fe['name']}** · {_fe.get('muscle','')}")
                    if _cb.button("+ Ajouter", key=f"pref_add_prog_{choix_s}_{_fe['name']}"):
                        st.session_state.extra_exos.setdefault(choix_s, []).append({
                            "name": _fe['name'],
                            "muscle": _fe.get('muscle', 'Autre'),
                            "sets": _fe.get('sets', 3)
                        })
                        st.rerun()

            else:  # Nouvel exercice
                _new_name_p = st.text_input("Nom de l'exercice", key=f"pref_new_name_{choix_s}")
                _new_muscle_p = st.selectbox("Muscle principal", _MUSCLE_LIST_S, key=f"pref_new_muscle_{choix_s}")
                _new_sets_p = st.number_input("Nombre de séries", 1, 10, 3, key=f"pref_new_sets_{choix_s}")
                if st.button(":material/add: Ajouter cet exercice", key=f"pref_add_new_{choix_s}",
                             disabled=not _new_name_p.strip()):
                    _detected_p = auto_muscles(_new_name_p.strip())
                    _muscle_final_p = _detected_p if _detected_p else _new_muscle_p
                    st.session_state.extra_exos.setdefault(choix_s, []).append({
                        "name": _new_name_p.strip(),
                        "muscle": _muscle_final_p,
                        "sets": int(_new_sets_p)
                    })
                    st.rerun()


# ============================================================
# ONGLET PROGRÈS : carte du corps, hall of fame, zoom mouvement
# ============================================================
with tab_st:
    st.markdown("### 🫁 Carte du Corps")
    body_map_section(df_p)

    if not df_p.empty:
        st.markdown("### 🏅 Hall of Fame")
        _FILT_ALL = ["Pecs","Dos","Épaules","Biceps","Triceps","Avant-bras","Abdos","Quadriceps","Ischio-jambiers","Fessiers","Mollets","Autre"]
        m_filt = st.multiselect("Filtrer par muscle :", _FILT_ALL, default=_FILT_ALL)
        df_p_filt = df_p[df_p["Muscle"].apply(lambda x: any(m in str(x) for m in m_filt) if pd.notna(x) else False)]
        if not df_p_filt.empty:
            podium = df_p_filt.groupby("Exercice").agg({"1RM": "max"}).sort_values(by="1RM", ascending=False).head(3)
            p_cols = st.columns(3); meds, clss = ["🥇 OR", "🥈 ARGENT", "🥉 BRONZE"], ["podium-gold", "podium-silver", "podium-bronze"]
            for idx, (ex_n, row) in enumerate(podium.iterrows()):
                with p_cols[idx]: st.markdown(f"<div class='podium-card {clss[idx]}'><small>{meds[idx]}</small><br><b>{ex_n}</b><br><span style='color:#58CCFF; font-size:22px;'>{row['1RM']:.1f}kg</span></div>", unsafe_allow_html=True)
        
        if not df_p.empty:
            st.divider()
            sel_e = st.selectbox("🎯 Zoom mouvement :", sorted(df_p["Exercice"].unique()))
            df_e = df_p[df_p["Exercice"] == sel_e].copy()
            df_rec = df_e[(df_e["Poids"] > 0) | (df_e["Reps"] > 0)].copy()
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
                st.plotly_chart(fig_l, use_container_width=True, config={'staticPlot': True, 'displayModeBar': False})
            render_table(df_e[["Semaine", "Reps", "Poids", "Muscle"]].sort_values("Semaine", ascending=False).reset_index(drop=True))

with tab_cardio:
    st.markdown("## 🏃 CARDIO")
    s_act_cardio = int(df_h["Semaine"].max() if not df_h.empty else 1)
    cardio_section(df_h, s_act_cardio)

with tab_g:
    st.markdown("## 🎮 ARCADE CYBER-FITNESS")
    
    if 'selected_game' not in st.session_state:
        st.session_state.selected_game = "flappy"
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💪 MUSCLE FLAPPY", key="select_flappy", 
                     use_container_width=True,
                     type="primary" if st.session_state.selected_game == "flappy" else "secondary"):
            st.session_state.selected_game = "flappy"
            st.rerun()
    
    with col2:
        if st.button("🏋️ REP CRUSHER", key="select_crusher", 
                     use_container_width=True,
                     type="primary" if st.session_state.selected_game == "crusher" else "secondary"):
            st.session_state.selected_game = "crusher"
            st.rerun()
    
    st.markdown("---")
    
    if st.session_state.selected_game == "flappy":
        muscle_flappy_game()
    else:
        rep_crusher_game()
    
    st.markdown("---")
    st.caption("💡 Records sauvegardés dans le navigateur")
