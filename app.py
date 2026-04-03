import streamlit as st
import pandas as pd
import json
import gspread
from datetime import datetime, timedelta
import plotly.graph_objects as go
import streamlit.components.v1 as components

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

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = 'seance'

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


# --- 3. FONCTIONS TECHNIQUES ---
def calc_1rm(weight, reps):
    return weight * (1 + reps / 30) if reps > 0 else 0

def get_rep_estimations(one_rm):
    return {r: round(one_rm * pct, 1) for r, pct in {1: 1.0, 3: 0.94, 5: 0.89, 8: 0.81, 10: 0.75, 12: 0.71}.items()}

def get_base_name(full_name):
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
        (["curl marteau","hammer curl","marteau"], ["Biceps","Avant-bras"]),
        (["reverse curl","curl inversé"], ["Biceps","Avant-bras"]),
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


# --- 4. JEUX CYBER (ADAPTATIFS MOBILE/DESKTOP) ---
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


# --- 5. CARTE DU CORPS INTERACTIVE ---
def body_map_section(df_p):
    MUSCLES = {
        "Pecs":            {"std": 80,  "zid_f": "z-pecs",    "zid_b": None},
        "Dos":             {"std": 90,  "zid_f": None,         "zid_b": "z-dos"},
        "Épaules":         {"std": 55,  "zid_f": "z-epaules",  "zid_b": "z-epaules-b"},
        "Biceps":          {"std": 30,  "zid_f": "z-biceps",   "zid_b": None},
        "Triceps":         {"std": 35,  "zid_f": None,         "zid_b": "z-triceps"},
        "Avant-bras":      {"std": 20,  "zid_f": "z-avbras",   "zid_b": "z-avbras-b"},
        "Abdos":           {"std": 25,  "zid_f": "z-abdos",    "zid_b": None},
        "Quadriceps":      {"std": 100, "zid_f": "z-quad",     "zid_b": None},
        "Ischio-jambiers": {"std": 60,  "zid_f": None,         "zid_b": "z-ischio"},
        "Fessiers":        {"std": 80,  "zid_f": None,         "zid_b": "z-fessiers"},
        "Mollets":         {"std": 60,  "zid_f": "z-mollets",  "zid_b": "z-mollets-b"},
        "Bras":            {"std": 30,  "zid_f": "z-biceps",   "zid_b": None},   # legacy
        "Jambes":          {"std": 100, "zid_f": "z-quad",     "zid_b": None},   # legacy
    }
    DISPLAY_MUSCLES = [m for m in MUSCLES if m not in ("Bras", "Jambes")]

    def get_col(pct):
        if pct == 0:    return "#1e2d3d"
        elif pct < 40:  return "#FF453A"
        elif pct < 70:  return "#FF9F0A"
        elif pct < 95:  return "#58CCFF"
        else:           return "#00FF7F"

    def muscle_df(m):
        if df_p.empty: return pd.DataFrame()
        return df_p[df_p["Muscle"].str.contains(m, regex=False, na=False)]

    # Stats par muscle
    sc = {}
    for m, info in MUSCLES.items():
        md = muscle_df(m)
        rm = md["1RM"].max() if not md.empty else 0
        pct = min((rm / info["std"]) * 100, 120) if info["std"] > 0 else 0
        sc[m] = {"pct": pct, "lvl": min(int(pct / 20), 5), "col": get_col(pct), "rm": rm, "std": info["std"]}

    def mc(m): return sc[m]["col"]
    def mop(m): return "0.9" if sc[m]["pct"] > 0 else "0.2"

    # Données JS par muscle : record réel + dernières séances + top exos
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
            "pct": round(sc[m]["pct"], 1), "lvl": sc[m]["lvl"],
            "col": sc[m]["col"], "rm": round(sc[m]["rm"], 1), "std": sc[m]["std"],
            "zid_f": MUSCLES[m]["zid_f"], "zid_b": MUSCLES[m]["zid_b"],
            "best": {"w": best_w, "r": best_r},
            "last": last_sessions, "exos": exos, "evo": evo,
        }

    data_json = json.dumps(muscle_data, ensure_ascii=False)

    # SVG FACE (FRONT)
    svg_front = f"""<svg viewBox="0 0 200 370" width="148" xmlns="http://www.w3.org/2000/svg">
  <defs><filter id="gw"><feGaussianBlur stdDeviation="3" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
  <!-- Silhouette -->
  <ellipse cx="100" cy="32" rx="21" ry="25" fill="#0d1b2a" stroke="#1e3a5f" stroke-width="1.2"/>
  <circle cx="92" cy="27" r="2" fill="#58CCFF" opacity="0.35"/>
  <circle cx="108" cy="27" r="2" fill="#58CCFF" opacity="0.35"/>
  <rect x="92" y="55" width="16" height="14" rx="5" fill="#0d1b2a" stroke="#1e3a5f" stroke-width="0.8"/>
  <path d="M79,68 L121,68 L126,175 L74,175 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.8" opacity="0.8"/>
  <path d="M57,72 L75,72 L70,132 L55,132 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <path d="M53,134 L69,134 L65,192 L50,192 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <ellipse cx="54" cy="196" rx="9" ry="6" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.5"/>
  <path d="M143,72 L125,72 L130,132 L145,132 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <path d="M147,134 L131,134 L135,192 L150,192 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <ellipse cx="146" cy="196" rx="9" ry="6" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.5"/>
  <ellipse cx="100" cy="177" rx="28" ry="10" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.8" opacity="0.7"/>
  <path d="M72,183 L96,183 L94,265 L70,265 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <path d="M71,267 L92,267 L90,345 L69,345 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <ellipse cx="78" cy="350" rx="16" ry="6" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.4"/>
  <path d="M128,183 L104,183 L106,265 L130,265 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <path d="M129,267 L108,267 L110,345 L131,345 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <ellipse cx="122" cy="350" rx="16" ry="6" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.4"/>
  <!-- Zones muscles FACE -->
  <g id="z-epaules" class="zone" onclick="sel('Épaules')"><title>Épaules</title>
    <ellipse cx="60" cy="82" rx="19" ry="13" fill="{mc('Épaules')}" opacity="{mop('Épaules')}" filter="url(#gw)"/>
    <ellipse cx="140" cy="82" rx="19" ry="13" fill="{mc('Épaules')}" opacity="{mop('Épaules')}" filter="url(#gw)"/>
  </g>
  <g id="z-pecs" class="zone" onclick="sel('Pecs')"><title>Pecs</title>
    <path d="M80,72 Q93,90 100,102 Q87,96 79,83 Z" fill="{mc('Pecs')}" opacity="{mop('Pecs')}" filter="url(#gw)"/>
    <path d="M120,72 Q107,90 100,102 Q113,96 121,83 Z" fill="{mc('Pecs')}" opacity="{mop('Pecs')}" filter="url(#gw)"/>
  </g>
  <g id="z-biceps" class="zone" onclick="sel('Biceps')"><title>Biceps</title>
    <rect x="58" y="74" width="16" height="46" rx="8" fill="{mc('Biceps')}" opacity="{mop('Biceps')}" filter="url(#gw)"/>
    <rect x="126" y="74" width="16" height="46" rx="8" fill="{mc('Biceps')}" opacity="{mop('Biceps')}" filter="url(#gw)"/>
  </g>
  <g id="z-avbras" class="zone" onclick="sel('Avant-bras')"><title>Avant-bras</title>
    <rect x="54" y="126" width="14" height="60" rx="7" fill="{mc('Avant-bras')}" opacity="0.75" filter="url(#gw)"/>
    <rect x="132" y="126" width="14" height="60" rx="7" fill="{mc('Avant-bras')}" opacity="0.75" filter="url(#gw)"/>
  </g>
  <g id="z-abdos" class="zone" onclick="sel('Abdos')"><title>Abdos</title>
    <rect x="83" y="106" width="14" height="18" rx="4" fill="{mc('Abdos')}" opacity="{mop('Abdos')}"/>
    <rect x="103" y="106" width="14" height="18" rx="4" fill="{mc('Abdos')}" opacity="{mop('Abdos')}"/>
    <rect x="84" y="128" width="13" height="18" rx="4" fill="{mc('Abdos')}" opacity="{mop('Abdos')}"/>
    <rect x="103" y="128" width="13" height="18" rx="4" fill="{mc('Abdos')}" opacity="{mop('Abdos')}"/>
    <rect x="86" y="149" width="11" height="15" rx="4" fill="{mc('Abdos')}" opacity="{mop('Abdos')}"/>
    <rect x="103" y="149" width="11" height="15" rx="4" fill="{mc('Abdos')}" opacity="{mop('Abdos')}"/>
  </g>
  <g id="z-quad" class="zone" onclick="sel('Quadriceps')"><title>Quadriceps</title>
    <rect x="72" y="186" width="23" height="68" rx="11" fill="{mc('Quadriceps')}" opacity="{mop('Quadriceps')}" filter="url(#gw)"/>
    <rect x="105" y="186" width="23" height="68" rx="11" fill="{mc('Quadriceps')}" opacity="{mop('Quadriceps')}" filter="url(#gw)"/>
  </g>
  <g id="z-mollets" class="zone" onclick="sel('Mollets')"><title>Mollets</title>
    <rect x="72" y="270" width="19" height="62" rx="9" fill="{mc('Mollets')}" opacity="{mop('Mollets')}" filter="url(#gw)"/>
    <rect x="109" y="270" width="19" height="62" rx="9" fill="{mc('Mollets')}" opacity="{mop('Mollets')}" filter="url(#gw)"/>
  </g>
</svg>"""

    # SVG DOS (BACK)
    svg_back = f"""<svg viewBox="0 0 200 370" width="148" xmlns="http://www.w3.org/2000/svg">
  <defs><filter id="gwb"><feGaussianBlur stdDeviation="3" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
  <!-- Silhouette -->
  <ellipse cx="100" cy="32" rx="21" ry="25" fill="#0d1b2a" stroke="#1e3a5f" stroke-width="1.2"/>
  <rect x="92" y="55" width="16" height="14" rx="5" fill="#0d1b2a" stroke="#1e3a5f" stroke-width="0.8"/>
  <path d="M79,68 L121,68 L126,175 L74,175 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.8" opacity="0.8"/>
  <path d="M57,72 L75,72 L70,132 L55,132 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <path d="M53,134 L69,134 L65,192 L50,192 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <ellipse cx="54" cy="196" rx="9" ry="6" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.5"/>
  <path d="M143,72 L125,72 L130,132 L145,132 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <path d="M147,134 L131,134 L135,192 L150,192 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <ellipse cx="146" cy="196" rx="9" ry="6" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.5"/>
  <ellipse cx="100" cy="177" rx="28" ry="10" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.8" opacity="0.7"/>
  <path d="M72,183 L96,183 L94,265 L70,265 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <path d="M71,267 L92,267 L90,345 L69,345 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <ellipse cx="78" cy="350" rx="16" ry="6" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.4"/>
  <path d="M128,183 L104,183 L106,265 L130,265 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <path d="M129,267 L108,267 L110,345 L131,345 Z" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.8"/>
  <ellipse cx="122" cy="350" rx="16" ry="6" fill="#0a1520" stroke="#1e3a5f" stroke-width="0.7" opacity="0.4"/>
  <!-- Zones muscles DOS -->
  <g id="z-epaules-b" class="zone" onclick="sel('Épaules')"><title>Épaules</title>
    <ellipse cx="60" cy="82" rx="19" ry="13" fill="{mc('Épaules')}" opacity="{mop('Épaules')}" filter="url(#gwb)"/>
    <ellipse cx="140" cy="82" rx="19" ry="13" fill="{mc('Épaules')}" opacity="{mop('Épaules')}" filter="url(#gwb)"/>
  </g>
  <g id="z-dos" class="zone" onclick="sel('Dos')"><title>Dos</title>
    <path d="M92,68 L108,68 L116,90 L84,90 Z" fill="{mc('Dos')}" opacity="{mop('Dos')}" filter="url(#gwb)"/>
    <path d="M80,92 L96,92 L100,160 L76,148 Z" fill="{mc('Dos')}" opacity="{mop('Dos')}" filter="url(#gwb)"/>
    <path d="M120,92 L104,92 L100,160 L124,148 Z" fill="{mc('Dos')}" opacity="{mop('Dos')}" filter="url(#gwb)"/>
  </g>
  <g id="z-triceps" class="zone" onclick="sel('Triceps')"><title>Triceps</title>
    <rect x="58" y="74" width="16" height="46" rx="8" fill="{mc('Triceps')}" opacity="{mop('Triceps')}" filter="url(#gwb)"/>
    <rect x="126" y="74" width="16" height="46" rx="8" fill="{mc('Triceps')}" opacity="{mop('Triceps')}" filter="url(#gwb)"/>
  </g>
  <g id="z-avbras-b" class="zone" onclick="sel('Avant-bras')"><title>Avant-bras</title>
    <rect x="54" y="126" width="14" height="60" rx="7" fill="{mc('Avant-bras')}" opacity="0.75" filter="url(#gwb)"/>
    <rect x="132" y="126" width="14" height="60" rx="7" fill="{mc('Avant-bras')}" opacity="0.75" filter="url(#gwb)"/>
  </g>
  <g id="z-fessiers" class="zone" onclick="sel('Fessiers')"><title>Fessiers</title>
    <ellipse cx="86" cy="185" rx="21" ry="16" fill="{mc('Fessiers')}" opacity="{mop('Fessiers')}" filter="url(#gwb)"/>
    <ellipse cx="114" cy="185" rx="21" ry="16" fill="{mc('Fessiers')}" opacity="{mop('Fessiers')}" filter="url(#gwb)"/>
  </g>
  <g id="z-ischio" class="zone" onclick="sel('Ischio-jambiers')"><title>Ischio-jambiers</title>
    <rect x="72" y="202" width="23" height="58" rx="11" fill="{mc('Ischio-jambiers')}" opacity="{mop('Ischio-jambiers')}" filter="url(#gwb)"/>
    <rect x="105" y="202" width="23" height="58" rx="11" fill="{mc('Ischio-jambiers')}" opacity="{mop('Ischio-jambiers')}" filter="url(#gwb)"/>
  </g>
  <g id="z-mollets-b" class="zone" onclick="sel('Mollets')"><title>Mollets</title>
    <rect x="72" y="270" width="19" height="62" rx="9" fill="{mc('Mollets')}" opacity="{mop('Mollets')}" filter="url(#gwb)"/>
    <rect x="109" y="270" width="19" height="62" rx="9" fill="{mc('Mollets')}" opacity="{mop('Mollets')}" filter="url(#gwb)"/>
  </g>
</svg>"""

    # Overview rows
    overview_rows = ""
    for m in DISPLAY_MUSCLES:
        s = sc[m]
        pct_w = min(s['pct'], 100)
        if MUSCLES[m]["zid_f"] is None:
            view_hint = "DOS · "
        elif MUSCLES[m]["zid_b"] is None:
            view_hint = "FACE · "
        else:
            view_hint = ""
        overview_rows += (
            f'<div class="mrow" onclick="selAuto(\'{m}\')" '
            f'style="border-left:2px solid {s["col"]}55;padding:3px 0 3px 7px;margin-bottom:4px;cursor:pointer;border-radius:0 6px 6px 0;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="font-size:10px;color:{s["col"]};font-weight:700;">{m.upper()}</span>'
            f'<span style="font-size:8px;color:#444;">{view_hint}{s["rm"]:.0f}kg 1RM</span>'
            f'</div>'
            f'<div style="background:rgba(255,255,255,0.07);border-radius:2px;height:3px;margin-top:2px;">'
            f'<div style="width:{pct_w:.0f}%;height:100%;background:{s["col"]};border-radius:2px;'
            f'box-shadow:0 0 5px {s["col"]};transition:width 0.4s;"></div></div></div>'
        )

    css = """<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:transparent;font-family:monospace;color:#ccc;overflow:hidden;}
.wrap{background:linear-gradient(160deg,#060e1e,#050A18);border-radius:16px;
  border:1px solid rgba(88,204,255,0.2);padding:10px;display:flex;gap:10px;
  box-shadow:inset 0 0 50px rgba(88,204,255,0.03);}
.svg-col{display:flex;flex-direction:column;align-items:center;flex-shrink:0;}
.vtoggle{display:flex;gap:4px;margin-bottom:6px;}
.vbtn{background:rgba(255,255,255,0.05);border:1px solid rgba(88,204,255,0.3);
  color:#58CCFF;font-family:monospace;font-size:9px;padding:3px 12px;
  border-radius:4px;cursor:pointer;transition:all 0.15s;letter-spacing:1px;}
.vbtn.active{background:rgba(88,204,255,0.15);border-color:#58CCFF;color:#fff;}
.vbtn:hover{background:rgba(88,204,255,0.1);}
.zone{cursor:pointer;transition:filter 0.15s;}
.zone:hover{filter:brightness(1.6);}
.zone.on{filter:brightness(2.2) drop-shadow(0 0 6px currentColor);}
.mrow:hover{background:rgba(88,204,255,0.06)!important;}
.scard{background:rgba(255,255,255,0.04);border-radius:8px;padding:6px;text-align:center;flex:1;min-width:0;}
#detail{display:none;}
.back{cursor:pointer;color:#58CCFF;font-size:10px;margin-bottom:8px;opacity:0.7;display:inline-block;}
.back:hover{opacity:1;}
.ltable{width:100%;border-collapse:collapse;font-size:9px;margin:4px 0 6px;}
.ltable th{color:#444;font-weight:normal;padding:1px 3px;border-bottom:1px solid rgba(255,255,255,0.08);}
.ltable td{padding:2px 3px;color:#aaa;}
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
  const d = D[name]; if (!d) return;
  const zid = curView==='front' ? d.zid_f : d.zid_b;
  if (zid) { const el=document.getElementById(zid); if(el) el.classList.add('on'); }
  document.getElementById('ov').style.display='none';
  document.getElementById('detail').style.display='block';

  let h = '<div style="color:'+d.col+';font-size:13px;font-weight:700;letter-spacing:2px;margin-bottom:8px;">⬡ '+name.toUpperCase()+'</div>';

  if (d.best && d.best.w > 0) {
    h += '<div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:8px;margin-bottom:8px;text-align:center;border:1px solid '+d.col+'33;">'
      + '<div style="font-size:8px;color:#555;letter-spacing:1px;margin-bottom:3px;">RECORD PERSONNEL</div>'
      + '<div style="font-size:22px;font-weight:900;color:'+d.col+';">'+d.best.w.toFixed(1)+'<span style="font-size:12px;color:#666;">kg</span>'
      + ' <span style="font-size:15px;color:#555;">×</span> '
      + d.best.r+'<span style="font-size:12px;color:#666;"> reps</span></div>'
      + '<div style="font-size:9px;color:#444;margin-top:2px;">1RM est. '+d.rm.toFixed(1)+'kg &nbsp;·&nbsp; std '+d.std+'kg</div>'
      + '</div>';
  } else {
    h += '<div style="font-size:10px;color:#333;text-align:center;padding:14px 0;">Pas encore de données.<br><span style="font-size:20px;">💪</span></div>';
  }

  if (d.last && d.last.length) {
    h += '<div style="font-size:8px;color:#555;letter-spacing:1px;margin-bottom:2px;">DERNIÈRES SÉANCES</div>'
      + '<table class="ltable"><tr><th>Sem.</th><th>Charge</th><th>Reps</th></tr>';
    d.last.forEach(ls => {
      h += '<tr><td style="color:#58CCFF">S'+ls.s+'</td><td style="color:'+d.col+'">'+ls.w.toFixed(1)+'kg</td><td>'+ls.r+'</td></tr>';
    });
    h += '</table>';
  }

  if (d.exos && d.exos.length) {
    h += '<div style="font-size:8px;color:#555;letter-spacing:1px;margin-bottom:3px;">TOP EXERCICES</div>';
    d.exos.forEach((e,i) => {
      h += '<div style="font-size:9px;margin-bottom:2px;color:#666;">'+(i===0?'▶':'·')+' '+e.name
        +' <span style="color:'+d.col+';font-weight:700;">'+e.w.toFixed(1)+'kg × '+e.r+'</span></div>';
    });
  }

  if (d.evo && d.evo.length>1) {
    h += '<div style="font-size:8px;color:#555;letter-spacing:1px;margin:5px 0 3px;">ÉVOLUTION 1RM</div>'+spark(d.evo,d.col);
  }

  document.getElementById('dc').innerHTML = h;
}

function back() {
  document.querySelectorAll('.zone').forEach(z=>z.classList.remove('on'));
  document.getElementById('ov').style.display='block';
  document.getElementById('detail').style.display='none';
}

function spark(evo,col){
  const W=155,H=46,pts=[],cir=[];
  const rms=evo.map(e=>e.r), mn=Math.min(...rms), mx=Math.max(...rms), rng=mx-mn||1;
  evo.forEach((e,i)=>{
    const x=(i/(evo.length-1))*(W-14)+7, y=H-((e.r-mn)/rng)*(H-14)-7;
    pts.push(x+','+y); cir.push('<circle cx="'+x+'" cy="'+y+'" r="2.5" fill="'+col+'" stroke="#060e1e" stroke-width="1.5"/>');
  });
  const first=evo[0],last=evo[evo.length-1];
  return '<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:46px;background:rgba(0,0,0,0.18);border-radius:6px;">'
    +'<polyline points="'+pts.join(' ')+'" fill="none" stroke="'+col+'" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
    +cir.join('')
    +'<text x="7" y="'+(H-2)+'" fill="#444" font-size="7">S'+first.w+'</text>'
    +'<text x="'+(W-7)+'" y="'+(H-2)+'" fill="#444" font-size="7" text-anchor="end">S'+last.w+'</text>'
    +'</svg>';
}
</script>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{css}</head><body>
<div style="text-align:center;font-family:monospace;font-size:9px;color:#58CCFF;letter-spacing:2px;margin-bottom:4px;opacity:0.45;">◈ SCAN CORPOREL ◈</div>
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
      <div style="font-size:8px;color:#444;letter-spacing:1px;margin-bottom:6px;">↓ CLIQUE SUR UN MUSCLE</div>
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

    components.html(html, height=460, scrolling=False)


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
            "Date":datetime.now().strftime("%Y-%m-%d")}])
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

# Clés réservées aux données internes (pas des séances)
prog_seances = {k: v for k, v in prog.items() if not k.startswith('_')}
muscle_mapping = {ex["name"]: ex.get("muscle", "Autre") for s in prog_seances for ex in prog_seances[s]}
df_h["Muscle"] = df_h["Exercice"].apply(get_base_name).map(muscle_mapping).fillna(df_h["Muscle"]).replace("", "Autre")
df_h["Muscle"] = df_h.apply(lambda r: fix_muscle(r["Exercice"], r["Muscle"]), axis=1)

# Logo toujours visible en haut
col_l1, col_l2, col_l3 = st.columns([1, 1.8, 1])
with col_l2:
    st.image("logo.png")

# Calcul df_p global (partagé entre onglets)
arch_rows = prog.get('_archive', [])
if arch_rows:
    df_arch = pd.DataFrame(arch_rows)
    df_arch['Poids'] = pd.to_numeric(df_arch['Poids'], errors='coerce').fillna(0.0)
    df_arch['Reps'] = pd.to_numeric(df_arch['Reps'] if 'Reps' in df_arch.columns else 1, errors='coerce').fillna(1).astype(int)
    df_arch['Semaine'] = pd.to_numeric(df_arch['Semaine'] if 'Semaine' in df_arch.columns else 0, errors='coerce').fillna(0).astype(int)
    # Remapper les muscles archivés via muscle_mapping (comme df_h)
    df_arch["Muscle"] = df_arch["Exercice"].apply(get_base_name).map(muscle_mapping).fillna(df_arch["Muscle"]).replace("", "Autre")
    df_arch["Muscle"] = df_arch.apply(lambda r: fix_muscle(r["Exercice"], r["Muscle"]), axis=1)
    df_live = df_h[df_h["Reps"] > 0].copy() if not df_h.empty else pd.DataFrame(columns=df_arch.columns)
    df_p = pd.concat([df_live, df_arch[df_arch['Reps'] > 0]], ignore_index=True)
else:
    df_p = df_h[df_h["Reps"] > 0].copy() if not df_h.empty else pd.DataFrame()
if not df_p.empty:
    df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)

# Onglets
tab_home, tab_p, tab_s, tab_st, tab_cardio, tab_g = st.tabs(["🏠 ACCUEIL", "📅 PROGRAMME", "🏋️‍♂️ MA SÉANCE", "📈 PROGRÈS", "🏃 CARDIO", "🎮 ARCADE"])

# --- ONGLET ACCUEIL / WIDGET ---
with tab_home:
    
    st.markdown("<h1 style='text-align: center; margin-top: 5px; margin-bottom: 20px;'>💪 MUSCU TRACKER PRO</h1>", unsafe_allow_html=True)
    
    st.markdown("## 🎯 TABLEAU DE BORD")
    
    # Calculer les stats
    s_act = int(df_h["Semaine"].max() if not df_h.empty else 1)
    
    # Prochaine séance à faire
    def get_next_session():
        for seance in prog_seances.keys():
            seance_data = df_h[(df_h["Séance"] == seance) & (df_h["Semaine"] == s_act)]
            if seance_data.empty:
                return seance
            exos_prog = len([ex for ex in prog[seance]])
            exos_done_or_skipped = len(seance_data[(seance_data["Poids"] > 0) | (seance_data["Remarque"].str.contains("SKIP", na=False))]["Exercice"].unique())
            if exos_done_or_skipped < exos_prog:
                return seance
        return list(prog_seances.keys())[0] if prog_seances else None

    next_session = get_next_session()

    # Volume cette semaine - Formaté avec espaces
    vol_week = int((df_h[df_h["Semaine"] == s_act]["Poids"] * df_h[df_h["Semaine"] == s_act]["Reps"]).sum())
    vol_week_formatted = f"{vol_week:,}".replace(',', ' ')  # Format avec espaces

    # Séances cette semaine
    sessions_done = len(df_h[(df_h["Semaine"] == s_act) & (df_h["Poids"] > 0)]["Séance"].unique())
    total_sessions = len(prog_seances.keys())
    
    # Streak (semaines consécutives avec au moins une séance)
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
    
    # WIDGET PRINCIPAL - Design Cyber (via components.html)
    import streamlit.components.v1 as components
    
    widget_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ 
                margin: 0; 
                padding: 10px; 
                background: transparent;
                overflow: hidden;
            }}
        </style>
    </head>
    <body>
        <div style="background: linear-gradient(135deg, rgba(88, 204, 255, 0.1), rgba(0, 255, 127, 0.1)); border: 2px solid #58CCFF; border-radius: 20px; padding: 30px; margin: 10px; box-shadow: 0 0 20px rgba(88, 204, 255, 0.4);">
            <div style="text-align: center; margin-bottom: 25px;">
                <h1 style="font-size: 2.5rem; color: #58CCFF; text-shadow: 0 0 20px rgba(88, 204, 255, 0.8); margin: 0; letter-spacing: 3px;">SEMAINE {s_act}</h1>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px;">
                <div style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(88, 204, 255, 0.3); border-radius: 12px; padding: 20px; text-align: center;">
                    <div style="font-size: 0.9rem; color: #aaa; margin-bottom: 5px;">SÉANCES</div>
                    <div style="font-size: 2.5rem; color: #58CCFF; font-weight: 900;">{sessions_done}/{total_sessions}</div>
                </div>
                <div style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(0, 255, 127, 0.3); border-radius: 12px; padding: 20px; text-align: center;">
                    <div style="font-size: 0.9rem; color: #aaa; margin-bottom: 5px;">VOLUME</div>
                    <div style="font-size: 2.5rem; color: #00FF7F; font-weight: 900;">{vol_week_formatted}</div>
                    <div style="font-size: 0.8rem; color: #888;">kg</div>
                </div>
            </div>
            <div style="background: rgba(255, 215, 0, 0.1); border: 1px solid rgba(255, 215, 0, 0.3); border-radius: 12px; padding: 15px; text-align: center; margin-bottom: 20px;">
                <div style="font-size: 0.9rem; color: #aaa; margin-bottom: 5px;">🔥 STREAK</div>
                <div style="font-size: 2rem; color: #FFD700; font-weight: 900;">{streak} SEMAINES</div>
            </div>
            <div style="background: rgba(255, 69, 58, 0.1); border: 2px solid #FF453A; border-radius: 15px; padding: 20px; text-align: center;">
                <div style="font-size: 1rem; color: #FF453A; margin-bottom: 10px; font-weight: bold;">📍 PROCHAINE SÉANCE</div>
                <div style="font-size: 1.8rem; color: white; font-weight: 900; letter-spacing: 2px;">{next_session if next_session else "TERMINÉ ✅"}</div>
            </div>
        </div>
    </body>
    </html>
    """
    
    components.html(widget_html, height=650, scrolling=True)
    
    # Stats rapides en bas
    st.divider()
    st.markdown("### 📊 CETTE SEMAINE")
    
    col_m1, col_m2, col_m3 = st.columns(3)
    
    with col_m1:
        st.metric("💪 Exercices", len(df_h[(df_h["Semaine"] == s_act) & (df_h["Poids"] > 0)]["Exercice"].unique()))
    
    with col_m2:
        st.metric("🔢 Séries", len(df_h[(df_h["Semaine"] == s_act) & (df_h["Poids"] > 0)]))
    
    with col_m3:
        total_reps = int(df_h[df_h["Semaine"] == s_act]["Reps"].sum())
        st.metric("🎯 Reps", total_reps)

# --- ONGLET PROGRAMME ---
with tab_p:
    st.markdown("## ⚙️ Configuration")
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
    with st.expander("⚙️ Avancé — Gestion"):
        if st.button("🤖 Auto-assigner les muscles", type="primary", use_container_width=True, help="Assigne automatiquement les muscles selon le nom de chaque exercice"):
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
                st.warning(f"⚠️ {len(skipped)} exercice(s) non reconnus : {', '.join(skipped)}")
            st.rerun()

        with st.expander("⚠️ Réinitialiser les séances"):
            st.warning("Remet à zéro toutes les séances (semaine 1, historique vide). L'historique est archivé.")
            if st.button("🔴 Confirmer la réinitialisation", type="primary", key="reset_all"):
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
                st.success("Réinitialisation effectuée. Reprends en semaine 1 !")
                st.rerun()

        with st.expander("🗑️ Vider l'archive"):
            st.warning("Supprime toutes les données archivées (records historiques et volume cumulé).")
            if st.button("🔴 Confirmer la suppression de l'archive", type="primary", key="clear_archive"):
                prog.pop('_archive', None)
                prog.pop('_legacy_volume', None)
                save_prog(prog)
                st.success("Archive vidée.")
                st.rerun()

# --- ONGLET MA SÉANCE ---
with tab_s:
    if prog:
        c_h1, c_h2, c_h3 = st.columns([2, 1, 1])
        s_act = c_h2.number_input("Semaine actuelle", 1, 52, int(df_h["Semaine"].max() if not df_h.empty else 1))
        
        # AUTO-SÉLECTION AVEC SKIP
        def get_current_session():
            for seance in prog_seances.keys():
                seance_data = df_h[(df_h["Séance"] == seance) & (df_h["Semaine"] == s_act)]
                if seance_data.empty:
                    return seance
                exos_prog = len([ex for ex in prog_seances[seance]])
                exos_done_or_skipped = len(seance_data[(seance_data["Poids"] > 0) | (seance_data["Remarque"].str.contains("SKIP", na=False))]["Exercice"].unique())
                if exos_done_or_skipped < exos_prog:
                    return seance
            return list(prog_seances.keys())[0] if prog_seances else None

        default_s = get_current_session()
        s_index = list(prog_seances.keys()).index(default_s) if default_s and default_s in prog_seances.keys() else 0
        choix_s = c_h1.selectbox("Séance :", list(prog_seances.keys()), index=s_index)
        
        if c_h3.button("🚩 Séance Manquée", use_container_width=True):
            m_rec = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": "SESSION", "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SÉANCE MANQUÉE 🚩", "Muscle": "Autre", "Date": datetime.now().strftime("%Y-%m-%d")}])
            save_hist(pd.concat([df_h, m_rec], ignore_index=True))
            st.rerun()
        
        # Expander TOUJOURS visible pour éviter erreur DOM
        current_session_data = df_h[(df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]
        has_data = not current_session_data.empty
        
        with st.expander("⚠️ Recommencer cette séance", expanded=False):
            if has_data:
                st.warning(f"⚠️ Effacer **{choix_s}** semaine **{s_act}** ? (L'historique sera conservé)")
                if st.button("🔄 Confirmer", type="primary", key="reset_confirm"):
                    df_filtered = df_h[~((df_h["Semaine"] == s_act) & (df_h["Séance"] == choix_s))]
                    save_hist(df_filtered)
                    st.rerun()
            else:
                st.info("ℹ️ Aucune donnée pour cette séance.")

        st.markdown("### 🔋 RÉCUPÉRATION")
        recup_cols = ["Pecs","Dos","Épaules","Biceps","Triceps","Abdos","Quadriceps","Mollets"]
        html_recup = "<div class='recup-container'>"
        for m in recup_cols:
            trained_this_week = df_h[df_h["Muscle"].str.contains(m, regex=False, na=False) & (df_h["Semaine"] == s_act)]
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
            
            # AUTO-RÉDUIRE
            curr_all = df_h[(df_h["Exercice"].str.contains(exo_base, regex=False, na=False)) & (df_h["Séance"] == choix_s) & (df_h["Semaine"] == s_act)]
            exo_completed = not curr_all.empty and ((curr_all["Poids"].sum() > 0 or curr_all["Reps"].sum() > 0) or curr_all["Remarque"].str.contains("SKIP", na=False).any())
            
            if st.session_state.settings['auto_collapse']:
                expanded_state = not exo_completed or exo_base in [e.split("(")[0].strip() for e in st.session_state.editing_exo]
            else:
                expanded_state = True
            
            with st.expander(f"🔹 {exo_base.upper()}", expanded=expanded_state):
                var = st.selectbox("Équipement :", variants, index=var_index, key=f"v_{exo_base}_{i}")
                exo_final = f"{exo_base} ({var})" if var != "Standard" else exo_base
                f_h = df_h[(df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s)]
                
                # Message variante
                all_variants = df_h[df_h["Exercice"].str.contains(exo_base, regex=False, na=False) & (df_h["Séance"] == choix_s)]["Exercice"].unique()
                if len(all_variants) > 1:
                    st.caption(f"ℹ️ Exercice pratiqué avec {len(all_variants)} variantes différentes")
                
                if not f_h.empty:
                    best_w = f_h["Poids"].max()
                    best_1rm = f_h.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1).max()
                    
                    if st.session_state.settings['show_1rm']:
                        st.caption(f"🏆 Record : **{best_w:g}kg** | ⚡ 1RM : **{best_1rm:.1f}kg**")
                    else:
                        st.caption(f"🏆 Record : **{best_w:g}kg**")

                # HISTORIQUE : 2 dernières séances faites + séances manquées
                hist_weeks_all = sorted(f_h[f_h["Semaine"] < s_act]["Semaine"].unique())
                hist_weeks = [w for w in hist_weeks_all if not f_h[(f_h["Semaine"] == w) & (f_h["Poids"] > 0)].empty]

                # Semaines où la séance entière a été manquée
                missed_weeks = set(df_h[
                    (df_h["Séance"] == choix_s) &
                    (df_h["Exercice"] == "SESSION") &
                    (df_h["Semaine"] < s_act)
                ]["Semaine"].unique())

                if hist_weeks and st.session_state.settings['show_previous_weeks'] > 0:
                    weeks_to_show = hist_weeks[-st.session_state.settings['show_previous_weeks']:]
                    min_w = weeks_to_show[0]
                    # Timeline combinée : séances faites + manquées dans la plage
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

                if not curr.empty and not is_reset and exo_final not in st.session_state.editing_exo:
                    st.markdown("##### ✅ Validé")
                    render_table(curr[["Série", "Reps", "Poids", "Remarque"]].reset_index(drop=True), hist_prev=hist_prev_df)
                    if st.button("🔄 Modifier", key=f"m_{exo_final}_{i}"): 
                        st.session_state.editing_exo.add(exo_final)
                        st.rerun()
                else:
                    df_base = pd.DataFrame({"Série": range(1, p_sets + 1), "Reps": [0]*p_sets, "Poids": [0.0]*p_sets, "Remarque": [""]*p_sets})
                    if not curr.empty:
                        for _, r in curr.iterrows():
                            if r["Série"] <= p_sets: df_base.loc[df_base["Série"] == r["Série"], ["Reps", "Poids", "Remarque"]] = [r["Reps"], r["Poids"], r["Remarque"]]
                    
                    ed = st.data_editor(
                        df_base, 
                        num_rows="dynamic",
                        key=editor_key, 
                        use_container_width=True,
                        column_config={
                            "Série": st.column_config.NumberColumn(disabled=True), 
                            "Poids": st.column_config.NumberColumn(format="%g")
                        },
                        column_order=["Série", "Reps", "Poids", "Remarque"],
                        hide_index=True
                    )
                    
                    # MODE MANUEL UNIQUEMENT
                    c_save, c_skip = st.columns(2)
                    if c_save.button("💾 Enregistrer", key=f"sv_{exo_final}"):
                        v = ed.copy()
                        v["Semaine"], v["Séance"], v["Exercice"], v["Muscle"], v["Date"] = s_act, choix_s, exo_final, muscle_grp, datetime.now().strftime("%Y-%m-%d")
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s))], v], ignore_index=True))
                        st.session_state.editing_exo.discard(exo_final)
                        st.rerun()
                        
                    if c_skip.button("⏩ Skip Exo", key=f"sk_{exo_final}"):
                        v_skip = pd.DataFrame([{"Semaine": s_act, "Séance": choix_s, "Exercice": exo_final, "Série": 1, "Reps": 0, "Poids": 0.0, "Remarque": "SKIP 🚫", "Muscle": muscle_grp, "Date": datetime.now().strftime("%Y-%m-%d")}])
                        save_hist(pd.concat([df_h[~((df_h["Semaine"] == s_act) & (df_h["Exercice"] == exo_final) & (df_h["Séance"] == choix_s))], v_skip], ignore_index=True))
                        st.rerun()


# --- ONGLET PROGRÈS (OPTIMISÉ MOBILE) ---
with tab_st:
    st.markdown("### 🫁 Carte du Corps")
    body_map_section(df_p)

    if not df_h.empty:
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
