"""Capture des COMPOSANTS UI recréés (promo_assets.html) + body map isolé +
écran accueil anonymisé. Assets destinés au motion design (Motion).

Prérequis : serveur fake sur http://127.0.0.1:5123 (python run_local_fake.py)
Sortie : pwa/static/promo/asset_*.png
"""
import json
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5123"
HERE = Path(__file__).resolve().parent
OUT = HERE / "static" / "promo"
OUT.mkdir(parents=True, exist_ok=True)

seed = json.loads(urllib.request.urlopen(f"{BASE}/test-seed").read().decode())
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
document.querySelectorAll('[id*="patchnotes"],[id*="tuto"],.tuto-overlay,#page-loader,.topbar')
  .forEach(function(e){ try{e.remove()}catch(x){} });
"""

COMPONENTS = ["asset-streak", "asset-coach", "asset-nutrition",
              "asset-volume", "asset-seance", "asset-pro"]

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 700, "height": 1200},
                              device_scale_factor=2)
    ctx.add_init_script(INIT_JS)
    page = ctx.new_page()

    # 1) Composants recréés (fond transparent autour des cartes)
    page.goto((HERE / "promo_assets.html").as_uri(), wait_until="networkidle")
    page.wait_for_timeout(400)
    page.evaluate("document.body.style.background='transparent'")
    for cid in COMPONENTS:
        page.locator(f"#{cid}").screenshot(path=str(OUT / f"{cid.replace('-', '_')}.png"),
                                           omit_background=True)
        print("ok:", cid)

    # 2) Session app seedée (cookie posé via /test-seed dans CE contexte)
    page.goto(f"{BASE}/test-seed", wait_until="networkidle")

    # 3) Body map SVG isolé (élément seul, sans la carte ni la nav)
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{BASE}/progres", wait_until="networkidle")
    page.wait_for_timeout(2600)
    page.evaluate(CLEAN_JS)
    page.evaluate("var s=document.getElementById('svg-front'); if(s){s.scrollIntoView({block:'center'});}")
    page.wait_for_timeout(500)
    page.locator("#svg-front").screenshot(path=str(OUT / "asset_bodymap.png"),
                                          omit_background=True)
    print("ok: asset_bodymap (svg)")

    # 4) Accueil anonymisé, topbar masquée (mockup téléphone)
    page.goto(f"{BASE}/accueil", wait_until="networkidle")
    page.wait_for_timeout(2600)
    page.evaluate(CLEAN_JS)
    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_timeout(500)
    page.evaluate(CLEAN_JS)
    page.screenshot(path=str(OUT / "asset_accueil.png"))
    print("ok: asset_accueil")

    browser.close()

print("DONE ->", OUT)
