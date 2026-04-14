"""Compresse static/icon.png (2 Mo) en icônes PWA légères :
static/icon-512.png (512x512) et static/icon-192.png (192x192).

Usage :
    cd pwa
    python compress_icon.py
"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "static", "icon.png")
OUT_512 = os.path.join(HERE, "static", "icon-512.png")
OUT_192 = os.path.join(HERE, "static", "icon-192.png")


def _save_compact(img, out):
    """Sauve en PNG agressivement compressé : quantize 8-bit palette si possible,
    sinon fallback RGBA optimize."""
    try:
        # quantize nécessite une image RGBA propre ; si résultat illisible,
        # on tombe sur l'image d'origine.
        q = img.convert("RGBA").quantize(colors=256, method=Image.Quantize.FASTOCTREE)
        q.save(out, optimize=True)
    except Exception:
        img.save(out, optimize=True)


def main():
    if not os.path.exists(SRC):
        raise SystemExit(f"icon source introuvable : {SRC}")
    img = Image.open(SRC)
    _save_compact(img.resize((512, 512), Image.LANCZOS), OUT_512)
    _save_compact(img.resize((192, 192), Image.LANCZOS), OUT_192)
    for p in (OUT_512, OUT_192):
        print(f"{p}: {os.path.getsize(p) // 1024} Ko")


if __name__ == "__main__":
    main()
