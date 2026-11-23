#!/usr/bin/env python3
""""Story Text" – short race update as an Instagram story (1080x1920 JPEG).

Ulrich sends a few keywords ("bad day, 3 flats, peanut butter mud"); Claude writes a short headline (2-4 words)
and 2-3 sentences (dramatic, epic, optimistic). This script lays them out as a "dispatch from the road":
photo full-bleed, warm-dark gradient from the middle down, terracotta tag "DISPATCH · DAY 4 · 16:12",
big headline (Anton, sand), body text (Inter ExtraBold, white) next to a terracotta rule, place/km line,
and the usual footer (logo + route bar Tecate -> San José del Cabo).

KM, day, time and place come from the photo's EXIF exactly like story_render.py; overrides --km --day --time --place.
Usage: text_story.py PHOTO OUT.jpg --headline "PEANUT BUTTER HELL" --text "..." [--focus F | --hfocus F] [--grade 1.0]
The output reports headline_lines / text_lines: keep headline <= 2 and text <= 4 lines.
"""
import argparse, datetime as dt, json, math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
KIT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, KIT)
try:
    import pillow_heif; pillow_heif.register_heif_opener()
except ImportError:
    pass

W, H, SS = 1080, 1920, 4
TERRA, SAND, GOLD, NIGHT, CACTUS = (217, 98, 43), (242, 211, 160), (244, 184, 96), (26, 18, 11), (143, 176, 122)
START = dt.date(2026, 12, 30)
D = json.load(open(os.path.join(KIT, "route_data.json"), encoding="utf-8")); ROUTE_KM = D["route_km"]
FILES = {"Anton": "anton-latin-400-normal.woff", "Archivo Black": "archivo-black-latin-400-normal.woff",
         "Inter ExtraBold": "inter-latin-800-normal.woff", "Inter Bold": "inter-latin-700-normal.woff"}
def font(name, size):
    p = os.path.join(KIT, "fonts", FILES[name])
    if not os.path.isfile(p): p = subprocess.check_output(["fc-match", "-f", "%{file}", name]).decode()
    return ImageFont.truetype(p, int(size))
SYMBOLS = "▲▼→●"
_fb = {}
def gf(ch, f):
    if ch not in SYMBOLS: return f
    if f.size not in _fb:
        _fb[f.size] = ImageFont.truetype(subprocess.check_output(["fc-match", "-f", "%{file}", "DejaVu Sans:bold"]).decode(), int(f.size * 0.8))
    return _fb[f.size]
def spaced(d, xy, text, f, fill, track):
    x, y = xy
    for ch in text: d.text((x, y), ch, font=gf(ch, f), fill=fill, anchor="ls"); x += d.textlength(ch, font=gf(ch, f)) + track
    return x - track
def text_w(d, text, f, track): return sum(d.textlength(c, font=gf(c, f)) for c in text) + track * (len(text) - 1)
def wrap(d, text, f, maxw, track=0):
    words, lines, cur = text.split(), [], ""
    # never split a number from its unit ("600 m", "3 flats" stays together only if it fits – numbers glue to next word)
    toks = []
    for w in words:
        if toks and toks[-1].replace(".", "").replace(",", "").isdigit(): toks[-1] += " " + w
        else: toks.append(w)
    for t in toks:
        cand = (cur + " " + t).strip()
        if text_w(d, cand.replace(" ", " "), f, track) <= maxw: cur = cand
        else: lines.append(cur); cur = t
    if cur: lines.append(cur)
    return [l.replace(" ", " ") for l in lines]

ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("out")
ap.add_argument("--headline", required=True); ap.add_argument("--text", required=True)
ap.add_argument("--km", type=float); ap.add_argument("--day", type=int); ap.add_argument("--time"); ap.add_argument("--place")
ap.add_argument("--tag", default="DISPATCH")
ap.add_argument("--focus", type=float, default=0.4); ap.add_argument("--hfocus", type=float, default=0.5)
ap.add_argument("--grade", type=float, default=1.0)
a = ap.parse_args()

# ---- km / day / time / place from EXIF (same rules as story_render.py) ----
src = Image.open(a.photo); ex = src.getexif(); sub, gps = ex.get_ifd(0x8769), ex.get_ifd(0x8825)
shot = None
if sub.get(36867):
    try: shot = dt.datetime.strptime(sub[36867], "%Y:%m:%d %H:%M:%S")
    except ValueError: pass
time_s = a.time or (shot.strftime("%H:%M") if shot else None)
day = a.day if a.day is not None else ((shot.date() - START).days + 1 if shot and shot.date() >= START else None)
km, place = a.km, a.place
if km is None and gps.get(2) and "track" in D:
    to_deg = lambda v, ref: (float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600) * (-1 if ref in ("S", "W") else 1)
    lat, lon = to_deg(gps[2], gps.get(1, "N")), to_deg(gps[4], gps.get(3, "E"))
    best = min(D["track"], key=lambda t: (t[1] - lat) ** 2 + ((t[2] - lon) * math.cos(math.radians(lat))) ** 2)
    if 111.2 * math.hypot(best[1] - lat, (best[2] - lon) * math.cos(math.radians(lat))) <= 15: km = best[0]
if km is not None and not place:
    near = min(D["places"], key=lambda p: abs(p["km"] - km))
    if abs(near["km"] - km) <= 12: place = near["name"]

# ---- photo ----
im = ImageOps.exif_transpose(src).convert("RGB"); r = W / H
if im.width / im.height > r:
    nw = round(im.height * r); x0 = round((im.width - nw) * a.hfocus); im = im.crop((x0, 0, x0 + nw, im.height))
else:
    nh = round(im.width / r); y0 = round((im.height - nh) * a.focus); im = im.crop((0, y0, im.width, y0 + nh))
im = im.resize((W, H), Image.LANCZOS)
if a.grade > 0:
    from desert_grade import apply_grade; im = apply_grade(im, a.grade)

# ---- measure the text block (anchored to the footer, grows upwards) ----
L, R_ = 64, W - 64
FOOT_Y = 1672
meas = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
fh, fb, ft, fp = font("Anton", 116), font("Inter ExtraBold", 40), font("Inter ExtraBold", 24), font("Inter Bold", 22)
hl = wrap(meas, a.headline.upper(), fh, R_ - L, 1)
body_x = L + 34
bl = wrap(meas, a.text, fb, R_ - body_x)
HL_LH, B_LH = 114, 56
place_y = FOOT_Y - 92                              # "NEAR CATAVIÑA · KM 735" line
body_end = place_y - 62                            # baseline of the last body line
body_top = body_end - (len(bl) - 1) * B_LH         # baseline of the first body line
hl_end = body_top - 78                             # baseline of the last headline line
hl_top = hl_end - (len(hl) - 1) * HL_LH
tag_y = hl_top - 132                              # tag clear above the headline cap height
block_top = tag_y - 50

# soft blur + warm-dark gradient behind the text only
soft = im.filter(ImageFilter.GaussianBlur(6)); m = Image.new("L", (W, H), 0)
ImageDraw.Draw(m).rectangle([0, block_top + 120, W, H], fill=255); im.paste(soft, (0, 0), m.filter(ImageFilter.GaussianBlur(60)))
canvas = im.convert("RGBA")
g = Image.new("L", (1, H)); g0 = block_top - 260
for yy in range(H):
    t = min(1, max(0, (yy - g0) / 420)); top = max(0, 1 - yy / 360)
    g.putpixel((0, yy), int(max(232 * (t * t * (3 - 2 * t)), 140 * top ** 1.5)))
ol = Image.new("RGBA", (W, H), NIGHT + (0,)); ol.putalpha(g.resize((W, H))); canvas.alpha_composite(ol)
d = ImageDraw.Draw(canvas)

# ---- tag: terracotta label "DISPATCH", then DAY · TIME in gold ----
tag = a.tag.upper(); tw = text_w(d, tag, ft, 4)
d.rounded_rectangle([L, tag_y - 34, L + tw + 32, tag_y + 12], radius=6, fill=TERRA + (255,))
spaced(d, (L + 16, tag_y), tag, ft, (255, 255, 255, 255), 4)
meta = "  ·  ".join(([f"DAY {day}"] if day else []) + ([time_s] if time_s else []))
if meta: spaced(d, (L + tw + 32 + 22, tag_y), meta, ft, GOLD + (255,), 3)

# ---- headline ----
for i, line in enumerate(hl):
    y = hl_top + i * HL_LH
    spaced(d, (L + 3, y + 3), line, fh, (0, 0, 0, 90), 1); spaced(d, (L, y), line, fh, SAND + (255,), 1)

# ---- body with terracotta rule ----
d.rectangle([L, body_top - 40, L + 6, body_end + 14], fill=TERRA + (255,))
for i, line in enumerate(bl):
    d.text((body_x, body_top + i * B_LH), line, font=fb, fill=(255, 255, 255, 255), anchor="ls")

# ---- place / km line ----
pl = []
if place: pl.append(("NEAR " + place).upper())
if km is not None: pl.append(f"KM {int(round(km)):,}".replace(",", "."))
if not pl: pl.append("ROAD TO BAJA")
spaced(d, (L, place_y), "  ·  ".join(pl), fp, SAND + (210,), 2.5)

# ---- footer: logo + route bar (as in story_render.py) ----
def draw_cactus(dr, ox, oy, k, mirror):
    def qb(p0, p1, p2, n=12): return [((1-t)**2*p0[0]+2*(1-t)*t*p1[0]+t*t*p2[0], (1-t)**2*p0[1]+2*(1-t)*t*p1[1]+t*t*p2[1]) for t in [i/n for i in range(n+1)]]
    f = lambda x, y: (ox + x * k, oy + y * k)
    dr.rectangle([f(43.4, 29.4), f(76.6, 184.7)], fill=CACTUS + (255,))
    cx, cy = f(60, 29.4); rr = 16.6 * k; dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=CACTUS + (255,))
    arms = [((50,132),(32,132),(20,132),(20,120),(20,74)), ((70,106),(88,106),(100,106),(100,94),(100,52))]
    if mirror: arms = [((70,124),(88,124),(100,124),(100,112),(100,66)), ((50,98),(32,98),(20,98),(20,86),(20,48))]
    w = 24 * k
    for a0, a1, ac, a2, a3 in arms:
        pts = [f(*p) for p in [a0, a1] + qb(a1, ac, a2)[1:] + [a3]]
        dr.line(pts, fill=CACTUS + (255,), width=int(w), joint="curve")
        for p in (pts[0], pts[-1]): dr.ellipse([p[0]-w/2, p[1]-w/2, p[0]+w/2, p[1]+w/2], fill=CACTUS + (255,))
def make_logo(cap):
    S = cap / 0.859 * SS; k = S / 200; fa = font("Anton", S)
    seq = ["D", "C1", "V", "C2", "D", "E"]
    wid = sum(fa.getlength(s) if s[0] != "C" else 108 * k for s in seq)
    bcap = cap * 0.30 * SS; fbj = font("Archivo Black", bcap / 0.72); gap = cap * 0.22 * SS
    img = Image.new("RGBA", (int(wid + 4 * SS), int(bcap + gap + cap * SS + 4 * SS)), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
    nat = sum(dr.textlength(c, font=fbj) for c in "BAJA"); spaced(dr, (0, bcap), "BAJA", fbj, TERRA + (255,), (wid - nat) / 3)
    base = bcap + gap + cap * SS; x = 0
    for s in seq:
        if s[0] == "C": draw_cactus(dr, x - 6 * k, base - 184.7 * k, k, s == "C2"); x += 108 * k
        else: dr.text((x, base), s, font=fa, fill=SAND + (255,), anchor="ls"); x += fa.getlength(s)
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS), (bcap + gap + cap * SS / 2) / SS
logo, mid = make_logo(36); canvas.alpha_composite(logo, (L, round(FOOT_Y - mid)))
big = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); b = ImageDraw.Draw(big)
x0 = (L + logo.width + 28) * SS; x1 = (W - L) * SS; ry = FOOT_Y * SS; th = 9 * SS
prog = 0 if km is None else max(0, min(1, km / ROUTE_KM)); xm = x0 + (x1 - x0) * prog
b.rounded_rectangle([x0, ry - th/2, x1, ry + th/2], radius=th/2, fill=SAND + (95,))
b.rounded_rectangle([x0, ry - th/2, max(xm, x0 + th), ry + th/2], radius=th/2, fill=TERRA + (255,))
re_ = 10 * SS; b.ellipse([x1-re_, ry-re_, x1+re_, ry+re_], fill=NIGHT + (255,), outline=SAND + (255,), width=4 * SS)
rm = 14 * SS; b.ellipse([xm-rm, ry-rm, xm+rm, ry+rm], fill=TERRA + (255,), outline=(255, 255, 255, 255), width=4 * SS)
canvas.alpha_composite(big.resize((W, H), Image.LANCZOS))
d = ImageDraw.Draw(canvas); fl = font("Inter Bold", 15)
spaced(d, (x0 / SS, FOOT_Y + 30), "TECATE", fl, SAND + (220,), 1.5)
t = "SAN JOSÉ DEL CABO"; spaced(d, (x1 / SS - text_w(d, t, fl, 1.5), FOOT_Y + 30), t, fl, SAND + (220,), 1.5)

canvas.convert("RGB").save(a.out, quality=92, subsampling=0)
print("saved", a.out, {"km": km, "day": day, "time": time_s, "place": place,
                       "headline_lines": len(hl), "text_lines": len(bl), "block_top": block_top})
