#!/usr/bin/env python3
"""Photo -> 4:5 crop -> Terracotta grade (1080x1350 JPEG) for the Instagram feed.
Usage: baja_photo.py IN OUT.jpg [--grade 1.0] [--focus 0.5] [--hfocus 0.5] [--width 1080]"""
import argparse, os, sys
from PIL import Image, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import pillow_heif; pillow_heif.register_heif_opener()
except ImportError:
    pass
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--focus", type=float, default=0.5); ap.add_argument("--hfocus", type=float, default=0.5)
ap.add_argument("--width", type=int, default=1080)
ap.add_argument("--grade", type=float, default=1.0, help="Terracotta grade strength 0..1 (0 = off)")
a = ap.parse_args()
im = ImageOps.exif_transpose(Image.open(a.inp)).convert("RGB")
r = 4 / 5
if im.width / im.height > r:
    nw = round(im.height * r); x0 = round((im.width - nw) * a.hfocus); im = im.crop((x0, 0, x0 + nw, im.height))
else:
    nh = round(im.width / r); y0 = round((im.height - nh) * a.focus); im = im.crop((0, y0, im.width, y0 + nh))
im = im.resize((a.width, round(a.width * 5 / 4)), Image.LANCZOS)  # grade at output size (grain scale)
if a.grade > 0:
    from desert_grade import apply_grade; im = apply_grade(im, a.grade)
im.save(a.out, quality=93, subsampling=0)
print("saved", a.out)
