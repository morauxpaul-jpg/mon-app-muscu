"""Génère les icônes PWA (192, 512, maskable) depuis logo.png à la racine du repo.

Usage :
    cd pwa
    python generate_icons.py

Dépend de Pillow (non listé dans requirements.txt car outil one-shot de dev) :
    pip install pillow
"""
import os
from PIL import Image

HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, "..", "logo.png")
OUT = os.path.join(HERE, "static", "icons")
BG = (5, 10, 24, 255)  # #050A18


def fit_on_bg(img, size, padding_ratio=0.0):
    """Colle le logo centré sur un fond opaque de la taille voulue."""
    canvas = Image.new("RGBA", (size, size), BG)
    pad = int(size * padding_ratio)
    target = size - 2 * pad
    logo = img.copy()
    logo.thumbnail((target, target), Image.LANCZOS)
    x = (size - logo.width) // 2
    y = (size - logo.height) // 2
    canvas.paste(logo, (x, y), logo if logo.mode == "RGBA" else None)
    return canvas


def main():
    if not os.path.exists(SRC):
        raise SystemExit(f"logo.png introuvable : {SRC}")
    os.makedirs(OUT, exist_ok=True)
    src = Image.open(SRC).convert("RGBA")

    fit_on_bg(src, 192).save(os.path.join(OUT, "icon-192.png"))
    fit_on_bg(src, 512).save(os.path.join(OUT, "icon-512.png"))
    # Maskable : safe zone de ~20% tout autour
    fit_on_bg(src, 512, padding_ratio=0.18).save(os.path.join(OUT, "icon-maskable.png"))
    print("Icônes générées dans", OUT)


if __name__ == "__main__":
    main()
