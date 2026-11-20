"""Dev-only: build responsive WebP/JPEG files in images/ from originals in images/src/.

Usage:  python tools/images/build_images.py [--own]
--own   prefer images/src/own/<name>-own.jpg (>= 1600px wide) over the stock originals.
Output names never change, so no HTML edit is needed when swapping photos.
Requires Pillow (already in backend/requirements.txt).
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "images" / "src"
OUT = ROOT / "images"

# name -> (stock original, aspect ratio w/h, crop box as fractions l,t,r,b or None, own file, max KB at 480w)
IMAGES = {
    "hero": ("cuba.jpg", 4 / 3, None, "hero-own.jpg", 45),
    "orchard": ("kadavoor.jpg", 4 / 3, None, "orchard-own.jpg", 25),
    "farmer": ("farmers-cc0.jpg", 4 / 3, None, "farmer-own.jpg", 25),
    "market": ("koyambedu.jpg", 4 / 3, None, "market-own.jpg", 25),
    "guava-pink": ("cuba.jpg", 1.0, (0.5, 0.25, 1.0, 0.75), None, 25),
}
WIDTHS = (480, 960)


def crop_to_ratio(im, ratio, box):
    if box:
        w, h = im.size
        im = im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
    w, h = im.size
    if w / h > ratio:
        nw = int(h * ratio)
        left = (w - nw) // 2
        return im.crop((left, 0, left + nw, h))
    nh = int(w / ratio)
    top = (h - nh) // 2
    return im.crop((0, top, w, top + nh))


def save_fit(im, path, fmt, max_kb):
    q = 72
    while True:
        im.save(path, fmt, quality=q, **({"method": 6} if fmt == "WEBP" else {"optimize": True, "progressive": True}))
        if path.stat().st_size <= max_kb * 1024 or q <= 40:
            return q
        q -= 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--own", action="store_true")
    args = ap.parse_args()
    for name, (stock, ratio, box, own, max_kb) in IMAGES.items():
        src = SRC / stock
        if args.own and own and (SRC / "own" / own).exists():
            src = SRC / "own" / own
        if not src.exists():
            print(f"skip {name}: missing {src}", file=sys.stderr)
            continue
        base = crop_to_ratio(ImageOps.exif_transpose(Image.open(src)).convert("RGB"), ratio, box)
        for w in WIDTHS:
            im = base.resize((w, round(w / ratio)), Image.LANCZOS)
            kb = max_kb if w == 480 else max_kb * 3
            save_fit(im, OUT / f"{name}-{w}.webp", "WEBP", kb)
            if w == 480:
                save_fit(im, OUT / f"{name}-{w}.jpg", "JPEG", kb * 1.4)
        print(name, {p.name: p.stat().st_size for p in sorted(OUT.glob(f"{name}-*"))})


if __name__ == "__main__":
    main()
