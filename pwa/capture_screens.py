"""Capture des écrans VIP de l'app (données seedées) en PNG haute résolution.

Prérequis : le serveur fake doit tourner sur http://127.0.0.1:5123
  cd pwa && python run_local_fake.py   (dans un autre terminal)
Puis : python capture_screens.py
Sortie : pwa/static/promo/promo_*.png
"""
import json
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5123"
OUT = Path(__file__).resolve().parent / "static" / "promo"
OUT.mkdir(parents=True, exist_ok=True)

# Récupère un conversation_id frais (et amorce la base)
seed = json.loads(urllib.request.urlopen(f"{BASE}/test-seed").read().decode())
conv = seed["conversation_id"]
print("seed:", seed)

INIT_JS = """
try {
  localStorage.setItem('lastSeenVersion','v38');
  localStorage.setItem('tuto_done','1');
  localStorage.setItem('notif_asked','1');
  localStorage.setItem('tuto_seance_done','1');
} catch(e) {}
"""

CLEAN_JS = """
document.querySelectorAll('[id*="patchnotes"],[id*="tuto"],.tuto-overlay,#page-loader')
  .forEach(function(e){ try{e.remove()}catch(x){} });
"""

# (url, fichier, scroll_js)
SHOTS = [
    ("/accueil", "promo_1_accueil.png", "window.scrollTo(0,0)"),
    ("/coach?c=%s" % conv, "promo_2_coach.png", "window.scrollTo(0,0)"),
    ("/nutrition", "promo_3_nutrition.png", "window.scrollTo(0,0)"),
    ("/progres", "promo_4_progres.png", "window.scrollTo(0,0)"),
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=2,
    )
    ctx.add_init_script(INIT_JS)
    # Pose le cookie de session via /test-seed dans ce contexte
    page = ctx.new_page()
    page.goto(f"{BASE}/test-seed", wait_until="networkidle")
    for url, fname, scroll in SHOTS:
        page.goto(BASE + url, wait_until="networkidle")
        page.wait_for_timeout(2600)  # laisse passer le délai du changelog (2s)
        page.evaluate(CLEAN_JS)
        page.evaluate(scroll)
        page.wait_for_timeout(700)
        page.evaluate(CLEAN_JS)  # re-nettoie juste avant la capture
        page.screenshot(path=str(OUT / fname))
        print("ok:", fname)

    # Body map : capture de l'élément (carte) directement, cadrage net.
    page.goto(BASE + "/progres", wait_until="networkidle")
    page.wait_for_timeout(2600)
    page.evaluate(CLEAN_JS)
    tagged = page.evaluate(
        "() => { var s=document.getElementById('svg-front')||document.getElementById('svg-back');"
        " if(s){(s.closest('.card')||s).id='__bm'; return true;} return false; }"
    )
    if tagged:
        page.locator("#__bm").screenshot(path=str(OUT / "promo_5_bodymap.png"))
        print("ok: promo_5_bodymap.png (element)")
    browser.close()

print("DONE ->", OUT)
