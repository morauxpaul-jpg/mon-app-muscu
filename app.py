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


# --- 5. CONNEXION ---
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
    get_prog.clear()

df_h = get_hist()
prog = get_prog()

muscle_mapping = {ex["name"]: ex.get("muscle", "Autre") for s in prog for ex in prog[s]}
df_h["Muscle"] = df_h["Exercice"].apply(get_base_name).map(muscle_mapping).fillna(df_h["Muscle"]).replace("", "Autre")

# Tabs - AVEC WIDGET ACCUEIL
tab_home, tab_p, tab_s, tab_st, tab_g = st.tabs(["🏠 ACCUEIL", "📅 PROGRAMME", "🏋️‍♂️ MA SÉANCE", "📈 PROGRÈS", "🎮 ARCADE"])

# --- ONGLET ACCUEIL / WIDGET ---
with tab_home:
    # Logo et titre UNIQUEMENT sur la page d'accueil
    col_l1, col_l2, col_l3 = st.columns([1, 1.8, 1])
    with col_l2: 
        st.image("logo.png")
    
    st.markdown("<h1 style='text-align: center; margin-top: 5px; margin-bottom: 20px;'>💪 MUSCU TRACKER PRO</h1>", unsafe_allow_html=True)
    
    st.markdown("## 🎯 TABLEAU DE BORD")
    
    # Calculer les stats
    s_act = int(df_h["Semaine"].max() if not df_h.empty else 1)
    
    # Prochaine séance à faire
    def get_next_session():
        for seance in prog.keys():
            seance_data = df_h[(df_h["Séance"] == seance) & (df_h["Semaine"] == s_act)]
            if seance_data.empty:
                return seance
            exos_prog = len([ex for ex in prog[seance]])
            exos_done_or_skipped = len(seance_data[(seance_data["Poids"] > 0) | (seance_data["Remarque"].str.contains("SKIP", na=False))]["Exercice"].unique())
            if exos_done_or_skipped < exos_prog:
                return seance
        return list(prog.keys())[0] if prog else None
    
    next_session = get_next_session()
    
    # Volume cette semaine - Formaté avec espaces
    vol_week = int((df_h[df_h["Semaine"] == s_act]["Poids"] * df_h[df_h["Semaine"] == s_act]["Reps"]).sum())
    vol_week_formatted = f"{vol_week:,}".replace(',', ' ')  # Format avec espaces
    
    # Séances cette semaine
    sessions_done = len(df_h[(df_h["Semaine"] == s_act) & (df_h["Poids"] > 0)]["Séance"].unique())
    total_sessions = len(prog.keys())
    
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
    jours = list(prog.keys())
    for idx_j, j in enumerate(jours):
        with st.expander(f"📦 {j}"):
            c_s1, c_s2 = st.columns(2)
            if c_s1.button("⬆️ Monter Séance", key=f"up_s_{j}") and idx_j > 0:
                jours[idx_j], jours[idx_j-1] = jours[idx_j-1], jours[idx_j]
                save_prog({k: prog[k] for k in jours})
                st.rerun()
            if c_s2.button("🗑️ Supprimer Séance", key=f"del_s_{j}"):
                del prog[j]
                save_prog(prog)
                st.rerun()
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
        s_act = c_h2.number_input("Semaine actuelle", 1, 52, int(df_h["Semaine"].max() if not df_h.empty else 1))
        
        # AUTO-SÉLECTION AVEC SKIP
        def get_current_session():
            for seance in prog.keys():
                seance_data = df_h[(df_h["Séance"] == seance) & (df_h["Semaine"] == s_act)]
                if seance_data.empty:
                    return seance
                
                exos_prog = len([ex for ex in prog[seance]])
                exos_done_or_skipped = len(seance_data[(seance_data["Poids"] > 0) | (seance_data["Remarque"].str.contains("SKIP", na=False))]["Exercice"].unique())
                
                if exos_done_or_skipped < exos_prog:
                    return seance
            return list(prog.keys())[0] if prog else None

        default_s = get_current_session()
        s_index = list(prog.keys()).index(default_s) if default_s and default_s in prog.keys() else 0
        choix_s = c_h1.selectbox("Séance :", list(prog.keys()), index=s_index)
        
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

                # HISTORIQUE : Chercher les semaines NON-SKIP
                hist_weeks_all = sorted(f_h[f_h["Semaine"] < s_act]["Semaine"].unique())
                hist_weeks = [w for w in hist_weeks_all if not f_h[(f_h["Semaine"] == w) & (f_h["Poids"] > 0)].empty]
                
                if hist_weeks and st.session_state.settings['show_previous_weeks'] > 0:
                    weeks_to_show = hist_weeks[-st.session_state.settings['show_previous_weeks']:]
                    for w_num in weeks_to_show:
                        h_data = f_h[(f_h["Semaine"] == w_num) & (f_h["Poids"] > 0)]
                        if not h_data.empty:
                            st.caption(f"📅 Semaine {w_num}")
                            st.dataframe(h_data[["Série", "Reps", "Poids", "Remarque"]], hide_index=True, use_container_width=True)
                elif not hist_weeks:
                    st.info("Semaine 1 : Établis tes marques !")

                curr = f_h[f_h["Semaine"] == s_act]
                last_w_num = hist_weeks[-1] if hist_weeks else None
                hist_prev_df = f_h[(f_h["Semaine"] == last_w_num) & (f_h["Poids"] > 0)] if last_w_num is not None else pd.DataFrame()
                
                is_reset = not curr.empty and (curr["Poids"].sum() == 0 and curr["Reps"].sum() == 0) and "SKIP" not in str(curr["Remarque"].iloc[0])

                editor_key = f"ed_{exo_final}_{s_act}"

                if not curr.empty and not is_reset and exo_final not in st.session_state.editing_exo:
                    st.markdown("##### ✅ Validé")
                    st.dataframe(curr[["Série", "Reps", "Poids", "Remarque"]].style.apply(style_comparaison, axis=1, hist_prev=hist_prev_df).format({"Poids": "{:g}"}), hide_index=True, use_container_width=True)
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
    if not df_h.empty:
        v_tot = int((df_h['Poids'] * df_h['Reps']).sum())
        v_tot_formatted = f"{v_tot:,}".replace(',', ' ')  # Format avec espaces
        paliers, noms = [0, 5000, 25000, 75000, 200000, 500000], ["RECRUE NÉON", "CYBER-SOLDAT", "ÉLITE DE CHROME", "TITAN D'ACIER", "LÉGENDE CYBER", "DIEU DU FER"]
        idx = next((i for i, p in enumerate(paliers[::-1]) if v_tot >= p), 0)
        idx = len(paliers) - 1 - idx
        prev_r, curr_r, next_r = (noms[idx-1] if idx > 0 else "DÉBUT"), noms[idx], (noms[idx+1] if idx < len(noms)-1 else "MAX")
        next_p = paliers[idx+1] if idx < len(paliers)-1 else paliers[-1]
        next_p_formatted = f"{next_p:,}".replace(',', ' ')  # Format avec espaces
        xp_ratio = min((v_tot - paliers[idx]) / (next_p - paliers[idx]), 1.0) if next_p > paliers[idx] else 1.0
        st.markdown(f"""<div class='rank-ladder'><div class='rank-step completed'><small>PASSÉ</small><br>{prev_r}</div><div style='font-size: 20px; color: #58CCFF;'>➡️</div><div class='rank-step active'><small>ACTUEL</small><br><span style='font-size:18px;'>{curr_r}</span></div><div style='font-size: 20px; color: #58CCFF;'>➡️</div><div class='rank-step'><small>PROCHAIN</small><br>{next_r}</div></div><div class='xp-container'><div class='xp-bar-bg'><div class='xp-bar-fill' style='width:{xp_ratio*100}%;'></div></div><div style='display:flex; justify-content: space-between;'><small style='color:#00FF7F;'>{v_tot_formatted} kg</small><small style='color:#58CCFF;'>Objectif : {next_p_formatted} kg</small></div></div>""", unsafe_allow_html=True)
        
        st.markdown("### 🕸️ Radar d'Équilibre")
        standards = {"Jambes": 150, "Dos": 120, "Pecs": 100, "Épaules": 75, "Bras": 50, "Abdos": 40}
        df_p = df_h[df_h["Reps"] > 0].copy(); df_p["1RM"] = df_p.apply(lambda x: calc_1rm(x["Poids"], x["Reps"]), axis=1)
        scores, labels = [], list(standards.keys())
        for m in labels:
            m_max = df_p[df_p["Muscle"] == m]["1RM"].max() if not df_p[df_p["Muscle"] == m].empty else 0
            scores.append(min((m_max / standards[m]) * 100, 110))
        
        # Radar optimisé mobile
        fig_r = go.Figure(data=go.Scatterpolar(
            r=scores + [scores[0]], 
            theta=labels + [labels[0]], 
            fill='toself', 
            line=dict(color='#58CCFF', width=3), 
            fillcolor='rgba(88, 204, 255, 0.2)'
        ))
        fig_r.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 110], showticklabels=False, gridcolor="rgba(255,255,255,0.1)"), 
                angularaxis=dict(color="white")
            ), 
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)', 
            margin=dict(l=20, r=20, t=10, b=10),
            height=300
        )
        st.plotly_chart(fig_r, use_container_width=True, config={'staticPlot': True, 'displayModeBar': False})

        if any(s > 0 for s in scores):
            top_m = labels[scores.index(max(scores))]
            valid_scores = [(s, labels[idx]) for idx, s in enumerate(scores) if s > 0 and labels[idx] != "Jambes"]
            if valid_scores:
                min_val, low_m = min(valid_scores, key=lambda x: x[0])
                lvl = "Faible" if (max(scores)-min_val) < 15 else ("Moyen" if (max(scores)-min_val) < 30 else "Élevé")
                msg = f"🛡️ Profil : Dominé par {top_m}. Point faible : {low_m}. Déséquilibre {lvl}."
            else: msg = f"🛡️ Profil dominé par {top_m}."
            if scores[labels.index("Jambes")] == 0: msg += " Pense aux jambes !"
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
            st.plotly_chart(fig_l, use_container_width=True, config={'staticPlot': True, 'displayModeBar': False})
        st.dataframe(df_e[["Semaine", "Série", "Reps", "Poids", "Remarque", "Muscle"]].sort_values("Semaine", ascending=False), hide_index=True)

# --- ONGLET ARCADE ---
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
