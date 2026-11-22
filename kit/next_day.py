#!/usr/bin/env python3
""""Story next day" – teaser story for what's coming (1080x1920). No current km, no record, no time.
Top half: photo. Bottom half: light sand panel with UP NEXT headline, from -> to, distance / climbing / high point,
elevation profile of the next ~250 km with places, and 2-3 short teaser lines.

The window starts at the current position (--km, or the photo's GPS snapped to the track) and ends at the
place closest to km+250 within 200..300 km (or --to-km).
Teaser lines come from the caller (Claude writes them from route_context.py / the guide sections):
  --line "No water for 200 km" --line "Wild Pacific coast" --line "Fish camps, no shops"
Usage: next_day.py PHOTO OUT.jpg [--km 688] [--to-km 881] [--line ...]x3 [--focus 0.5] [--hfocus 0.5]
"""
import argparse, json, math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
KIT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, KIT)
try:
    import pillow_heif; pillow_heif.register_heif_opener()
except ImportError:
    pass

W, H, SS = 1080, 1920, 3
TERRA, SAND, GOLD, NIGHT, CACTUS = (217, 98, 43), (242, 211, 160), (244, 184, 96), (26, 18, 11), (143, 176, 122)
INK, PAPER, MUTED = (38, 26, 16), (243, 226, 196), (120, 92, 66)
D = json.load(open(os.path.join(KIT, "route_data.json"), encoding="utf-8")); ROUTE = D["route_km"]
FILES = {"Anton": "anton-latin-400-normal.woff", "Archivo Black": "archivo-black-latin-400-normal.woff",
         "Inter ExtraBold": "inter-latin-800-normal.woff", "Inter Bold": "inter-latin-700-normal.woff"}
def font(name, size):
    p = os.path.join(KIT, "fonts", FILES[name])
    if not os.path.isfile(p): p = subprocess.check_output(["fc-match", "-f", "%{file}", name]).decode()
    return ImageFont.truetype(p, int(size))

ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("out")
ap.add_argument("--km", type=float); ap.add_argument("--to-km", type=float)
ap.add_argument("--line", action="append", default=[])
ap.add_argument("--overlay", type=int, default=224)
ap.add_argument("--focus", type=float, default=0.5); ap.add_argument("--hfocus", type=float, default=0.5)
a = ap.parse_args()

src = Image.open(a.photo)
km = a.km
if km is None:
    gps = src.getexif().get_ifd(0x8825)
    if gps.get(2):
        to_deg = lambda v, ref: (float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600) * (-1 if ref in ("S", "W") else 1)
        lat, lon = to_deg(gps[2], gps.get(1, "N")), to_deg(gps[4], gps.get(3, "E"))
        best = min(D["track"], key=lambda t: (t[1] - lat) ** 2 + ((t[2] - lon) * math.cos(math.radians(lat))) ** 2)
        if 111.2 * math.hypot(best[1] - lat, (best[2] - lon) * math.cos(math.radians(lat))) <= 15: km = best[0]
if km is None: sys.exit("need --km (no usable GPS in photo)")
places = D["places"]
if a.to_km: k1 = min(ROUTE, a.to_km)
else:
    cands = [p for p in places if km + 200 <= p["km"] <= km + 300 and not p.get("near")] or [p for p in places if km + 200 <= p["km"] <= km + 300]
    cands = [p for p in cands if p["note"]] or cands   # prefer real towns/landmarks
    k1 = min(cands, key=lambda p: abs(p["km"] - (km + 250)))["km"] if cands else min(ROUTE, km + 250)
frm = min(places, key=lambda p: abs(p["km"] - km)); frm_name = frm["name"] if abs(frm["km"] - km) <= 15 else None
to = min(places, key=lambda p: abs(p["km"] - k1)); to_name = to["name"] if abs(to["km"] - k1) <= 15 else None
step = D["profile_step_km"]; ele, climb = D["elevation_m"], D["climb_cum_m"]
def at(arr, k):
    i = min(int(k // step), len(arr) - 2); f = (k - i * step) / step; return arr[i] + (arr[i + 1] - arr[i]) * f
dist = k1 - km; gain = at(climb, k1) - at(climb, km)
prof = [(k, at(ele, k)) for k in [km + i * (k1 - km) / 120 for i in range(121)]]
top_k, top_e = max(prof, key=lambda p: p[1])
nk = lambda x: f"{int(round(x)):,}".replace(",", ".")

# ---------- photo top ----------
PH = 860
im = ImageOps.exif_transpose(src).convert("RGB"); r = W / H
if im.width / im.height > r:
    nw = round(im.height * r); x0 = round((im.width - nw) * a.hfocus); im = im.crop((x0, 0, x0 + nw, im.height))
else:
    nh = round(im.width / r); y0 = round((im.height - nh) * a.focus); im = im.crop((0, y0, im.width, y0 + nh))
im = im.resize((W, H), Image.LANCZOS)
from desert_grade import apply_grade
im = apply_grade(im, 1.0)
# content area slightly softened so text sits on a calm surface
soft = im.filter(ImageFilter.GaussianBlur(6)); m = Image.new("L", (W, H), 0)
ImageDraw.Draw(m).rectangle([0, PH, W, H], fill=255); im.paste(soft, (0, 0), m.filter(ImageFilter.GaussianBlur(40)))
canvas = im.convert("RGBA")
# strong sand overlay: light over the top image area, strong over the content
ov = Image.new("L", (1, H))
for yy in range(H):
    t = min(1, max(0, (yy - (PH - 260)) / 300))
    ov.putpixel((0, yy), int(40 + (a.overlay - 40) * (t * t * (3 - 2 * t))))
ol = Image.new("RGBA", (W, H), PAPER + (0,)); ol.putalpha(ov.resize((W, H))); canvas.alpha_composite(ol)
# top gradient for the Instagram UI + logo
g = Image.new("L", (1, 420)); [g.putpixel((0, y), int(160 * (1 - y / 419) ** 1.5)) for y in range(420)]
tg = Image.new("RGBA", (W, 420), NIGHT + (0,)); tg.putalpha(g.resize((W, 420))); canvas.alpha_composite(tg, (0, 0))
d = ImageDraw.Draw(canvas)

def spaced(dr, xy, text, f, fill, track, anchor="ls"):
    x, y = xy
    w = sum(dr.textlength(c, font=f) for c in text) + track * (len(text) - 1)
    if anchor == "rs": x -= w
    if anchor == "ms": x -= w / 2
    for ch in text: dr.text((x, y), ch, font=f, fill=fill, anchor="ls"); x += dr.textlength(ch, font=f) + track
    return x - track

# ---------- logo on the photo ----------
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
def make_logo(cap, sand=SAND):
    S4 = 4; S = cap / 0.859 * S4; k = S / 200; fa = font("Anton", S)
    seq = ["D", "C1", "V", "C2", "D", "E"]; wid = sum(fa.getlength(s) if s[0] != "C" else 108 * k for s in seq)
    bcap = cap * 0.30 * S4; fb = font("Archivo Black", bcap / 0.72); gap = cap * 0.22 * S4
    img = Image.new("RGBA", (int(wid + 4 * S4), int(bcap + gap + cap * S4 + 4 * S4)), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
    nat = sum(dr.textlength(c, font=fb) for c in "BAJA"); spaced(dr, (0, bcap), "BAJA", fb, TERRA + (255,), (wid - nat) / 3)
    base = bcap + gap + cap * S4; x = 0
    for s in seq:
        if s[0] == "C": draw_cactus(dr, x - 6 * k, base - 184.7 * k, k, s == "C2"); x += 108 * k
        else: dr.text((x, base), s, font=fa, fill=sand + (255,), anchor="ls"); x += fa.getlength(s)
    return img.resize((img.width // S4, img.height // S4), Image.LANCZOS)
L = 64
canvas.alpha_composite(make_logo(40), (L, 250))

# ---------- panel edge: terracotta band with UP NEXT tab ----------
d.rectangle([0, PH - 3, W, PH + 3], fill=TERRA + (255,))
tab_w = 290; d.rectangle([L, PH - 52, L + tab_w, PH + 3], fill=TERRA + (255,))
spaced(d, (L + tab_w / 2, PH - 16), "UP NEXT", font("Anton", 40), (255, 255, 255, 255), 6, "ms")

# ---------- headline: distance + from -> to ----------
y = PH + 140
spaced(d, (L, y), f"NEXT {nk(dist)} KM", font("Anton", 118), INK + (255,), 0)
if frm_name or to_name:
    t = f"{frm_name.upper()}  →  {(to_name or '').upper()}".strip() if frm_name else f"TO {to_name.upper()}"
    spaced(d, (L, y + 52), t, font("Inter ExtraBold", 28), TERRA + (255,), 2)

# ---------- stat row ----------
y = PH + 290
cols = [(nk(gain) + " M", "CLIMBING"), (nk(top_e) + " M", "HIGH POINT")]
cw = (W - 2 * L) / 2.6
for i, (v, lbl) in enumerate(cols):
    x = L + i * cw
    if i: d.line([(x - 18, y - 62), (x - 18, y + 26)], fill=MUTED + (120,), width=2)
    spaced(d, (x, y), v, font("Anton", 64), INK + (255,), 0)
    spaced(d, (x, y + 28), lbl, font("Inter Bold", 19), MUTED + (255,), 3)

# ---------- elevation profile ----------
px0, px1, py0, py1 = L, W - L, PH + 390, PH + 560       # chart box
emax = max(e for _, e in prof); emin = 0; span = max(400, emax - emin)
X = lambda k: px0 + (k - km) / (k1 - km) * (px1 - px0)
Y = lambda e: py1 - (e - emin) / span * (py1 - py0)
big = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); b = ImageDraw.Draw(big)
poly = [(X(k) * SS, Y(e) * SS) for k, e in prof]
b.polygon(poly + [(px1 * SS, py1 * SS), (px0 * SS, py1 * SS)], fill=TERRA + (70,))
b.line(poly, fill=TERRA + (255,), width=5 * SS, joint="curve")
b.line([(px0 * SS, py1 * SS), (px1 * SS, py1 * SS)], fill=INK + (140,), width=2 * SS)
fpl = font("Inter Bold", 17 * SS)
shown = [p for p in places if km + 8 < p["km"] < k1 - 4 and not p.get("near") and p["note"]][:4]
for p in shown:
    x = X(p["km"]) * SS; yy = Y(at(ele, p["km"])) * SS
    b.line([(x, yy - 14 * SS), (x, py1 * SS)], fill=INK + (90,), width=2 * SS)
    b.ellipse([x - 6 * SS, yy - 6 * SS, x + 6 * SS, yy + 6 * SS], fill=PAPER + (255,), outline=INK + (255,), width=2 * SS)
    lbl = p["name"].upper(); tw = b.textlength(lbl, font=fpl)
    b.text((max(px0 * SS, min(px1 * SS - tw, x - tw / 2)), yy - 44 * SS), lbl, font=fpl, fill=INK + (255,), stroke_width=4 * SS, stroke_fill=PAPER + (255,))
# high point marker
x = X(top_k) * SS; yy = Y(top_e) * SS
b.polygon([(x, yy - 16 * SS), (x - 9 * SS, yy - 30 * SS), (x + 9 * SS, yy - 30 * SS)], fill=TERRA + (255,))
canvas.alpha_composite(big.resize((W, H), Image.LANCZOS)); d = ImageDraw.Draw(canvas)
fk = font("Inter Bold", 17)
spaced(d, (px0, py1 + 30), (frm_name or "FROM HERE").upper(), fk, MUTED + (255,), 2)
spaced(d, (px1, py1 + 30), (to_name or f"+{nk(dist)} KM").upper(), fk, MUTED + (255,), 2, "rs")

# ---------- teaser lines ----------
y = py1 + 105
for ln in a.line[:3]:
    d.ellipse([L, y - 22, L + 16, y - 6], fill=TERRA + (255,))
    spaced(d, (L + 34, y), ln.upper(), font("Inter ExtraBold", 31), INK + (255,), 1.5)
    y += 54

d.rectangle([0, H - 14, W, H], fill=TERRA + (255,))
canvas.convert("RGB").save(a.out, quality=92, subsampling=0)
print("saved", a.out, {"from_km": km, "to_km": k1, "from": frm_name, "to": to_name, "dist": round(dist), "gain": round(gain), "high": round(top_e), "lines_y_end": y})
