#!/usr/bin/env python3
""""Story FKT" – full-screen info board (1080x1920): the GPX route fills the screen, the photo is only a dark
blurred backdrop. Shows position, the FKT-record ghost, time delta, km, climbing, day/time.
Only on explicit request ("Story FKT").

KM/day/time come from the photo EXIF like story_render.py (GPS snapped to the track); overrides possible.
Usage: fkt_board.py PHOTO OUT.jpg [--km 640 --day 3 --time 16:12] [--record-h 253.4] [--start "2026-12-30 07:00"]
"""
import argparse, datetime as dt, json, math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
KIT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, KIT)
try:
    import pillow_heif; pillow_heif.register_heif_opener()
except ImportError:
    pass

W, H, SS = 1080, 1920, 3
TERRA, SAND, GOLD, NIGHT, CACTUS = (217, 98, 43), (242, 211, 160), (244, 184, 96), (26, 18, 11), (143, 176, 122)
GREEN, RED = (170, 214, 140), (238, 120, 70)
START = dt.date(2026, 12, 30)
D = json.load(open(os.path.join(KIT, "route_data.json"), encoding="utf-8")); ROUTE = D["route_km"]
FILES = {"Anton": "anton-latin-400-normal.woff", "Archivo Black": "archivo-black-latin-400-normal.woff",
         "Inter ExtraBold": "inter-latin-800-normal.woff", "Inter Bold": "inter-latin-700-normal.woff"}
def font(name, size):
    p = os.path.join(KIT, "fonts", FILES[name])
    if not os.path.isfile(p): p = subprocess.check_output(["fc-match", "-f", "%{file}", name]).decode()
    return ImageFont.truetype(p, int(size))

ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("out")
ap.add_argument("--km", type=float); ap.add_argument("--day", type=int); ap.add_argument("--time")
ap.add_argument("--record-h", type=float, default=253.4); ap.add_argument("--start", default="2026-12-30 10:00")
a = ap.parse_args()

# ---------- data from EXIF (same logic as story_render) ----------
src = Image.open(a.photo); ex = src.getexif(); sub, gps = ex.get_ifd(0x8769), ex.get_ifd(0x8825)
shot = None
if sub.get(36867):
    try: shot = dt.datetime.strptime(sub[36867], "%Y:%m:%d %H:%M:%S")
    except ValueError: pass
time_s = a.time or (shot.strftime("%H:%M") if shot else None)
day = a.day if a.day is not None else ((shot.date() - START).days + 1 if shot and shot.date() >= START else None)
km = a.km
if km is None and gps.get(2):
    to_deg = lambda v, ref: (float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600) * (-1 if ref in ("S", "W") else 1)
    lat, lon = to_deg(gps[2], gps.get(1, "N")), to_deg(gps[4], gps.get(3, "E"))
    best = min(D["track"], key=lambda t: (t[1] - lat) ** 2 + ((t[2] - lon) * math.cos(math.radians(lat))) ** 2)
    if 111.2 * math.hypot(best[1] - lat, (best[2] - lon) * math.cos(math.radians(lat))) <= 15: km = best[0]
km = km or 0
ghost_km = delta = None
if day and time_s:
    t0 = dt.datetime.strptime(a.start, "%Y-%m-%d %H:%M")
    now = dt.datetime.combine(START + dt.timedelta(days=day - 1), dt.datetime.strptime(time_s, "%H:%M").time())
    el = (now - t0).total_seconds() / 3600
    ghost_km = max(0, min(ROUTE, el / a.record_h * ROUTE)); delta = el - km / ROUTE * a.record_h
step = D["profile_step_km"]; climb = D["climb_cum_m"]
def at(arr, k):
    i = min(int(k // step), len(arr) - 2); f = (k - i * step) / step; return arr[i] + (arr[i + 1] - arr[i]) * f
climbed, climb_total = at(climb, km), climb[-1]
nk = lambda x: f"{int(round(x)):,}".replace(",", ".")
def hm(h): h = abs(h); m = int(round(h * 60)); return f"{m // 60}:{m % 60:02d}"

# ---------- backdrop: photo blurred + dark warm overlay ----------
im = ImageOps.exif_transpose(src).convert("RGB"); r = W / H
if im.width / im.height > r:
    nw = round(im.height * r); x0 = (im.width - nw) // 2; im = im.crop((x0, 0, x0 + nw, im.height))
else:
    nh = round(im.width / r); y0 = (im.height - nh) // 2; im = im.crop((0, y0, im.width, y0 + nh))
im = im.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(3))
from desert_grade import apply_grade
im = apply_grade(im, 1.0).convert("RGBA")
im.alpha_composite(Image.new("RGBA", (W, H), NIGHT + (115,)))       # light overall veil – the photo stays recognisable
# extra soft shade only where text sits: top-left (logo), top-right (KM), bottom-left (delta), bottom (bar)
shade = Image.new("L", (W, H), 0); sd = ImageDraw.Draw(shade)
for box in [(-200, 150, 560, 760), (380, 380, 1280, 900), (-200, 1120, 700, 1580), (-100, 1600, 1180, 2100)]:
    sd.ellipse(box, fill=150)
shade = shade.filter(ImageFilter.GaussianBlur(110))
im.alpha_composite(Image.merge("RGBA", [Image.new("L", (W, H), c) for c in NIGHT] + [shade]))
d = ImageDraw.Draw(im)

def spaced(dr, xy, text, f, fill, track, anchor="ls"):
    x, y = xy
    if anchor == "rs": x -= sum(dr.textlength(c, font=f) for c in text) + track * (len(text) - 1)
    for ch in text: dr.text((x, y), ch, font=f, fill=fill, anchor="ls"); x += dr.textlength(ch, font=f) + track
    return x - track

# ---------- logo (top) ----------
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
    S4 = 4; S = cap / 0.859 * S4; k = S / 200; fa = font("Anton", S)
    seq = ["D", "C1", "V", "C2", "D", "E"]; wid = sum(fa.getlength(s) if s[0] != "C" else 108 * k for s in seq)
    bcap = cap * 0.30 * S4; fb = font("Archivo Black", bcap / 0.72); gap = cap * 0.22 * S4
    img = Image.new("RGBA", (int(wid + 4 * S4), int(bcap + gap + cap * S4 + 4 * S4)), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
    nat = sum(dr.textlength(c, font=fb) for c in "BAJA"); spaced(dr, (0, bcap), "BAJA", fb, TERRA + (255,), (wid - nat) / 3)
    base = bcap + gap + cap * S4; x = 0
    for s in seq:
        if s[0] == "C": draw_cactus(dr, x - 6 * k, base - 184.7 * k, k, s == "C2"); x += 108 * k
        else: dr.text((x, base), s, font=fa, fill=SAND + (255,), anchor="ls"); x += fa.getlength(s)
    return img.resize((img.width // S4, img.height // S4), Image.LANCZOS)
L = 64
logo = make_logo(62); im.alpha_composite(logo, (L, 270))
d = ImageDraw.Draw(im)
spaced(d, (L, 270 + logo.height + 40), "FKT ATTEMPT", font("Inter ExtraBold", 26), GOLD + (255,), 5)
if day or time_s:
    t = "  ·  ".join(([f"DAY {day}"] if day else []) + ([time_s] if time_s else []))
    spaced(d, (L, 270 + logo.height + 78), t, font("Inter Bold", 24), SAND + (230,), 3)

# ---------- map: the GPX line fills the screen diagonally ----------
tr = D["track"]; lat0 = sum(t[1] for t in tr) / len(tr); cx = math.cos(math.radians(lat0))
X = [t[2] * cx for t in tr]; Y = [-t[1] for t in tr]
top, bot = 470, 1640
sc = (bot - top) / (max(Y) - min(Y)); mw = (max(X) - min(X)) * sc
ox = (W - mw) / 2 + 40
P = lambda i: ((ox + (X[i] - min(X)) * sc) * SS, (top + (Y[i] - min(Y)) * sc) * SS)
kidx = lambda k: max(0, min(len(tr) - 1, int(round(k / 2))))
lay = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); m = ImageDraw.Draw(lay)
m.line([P(i) for i in range(len(tr))], fill=SAND + (150,), width=5 * SS, joint="curve")
ki = kidx(km)
if ki > 0: m.line([P(i) for i in range(ki + 1)], fill=TERRA + (255,), width=9 * SS, joint="curve")
# a few landmarks along the line
fpl = font("Inter Bold", 17 * SS)
for name in ["Tecate", "Cataviña", "Bahía de los Ángeles", "San Ignacio", "Mulegé", "Ciudad Constitución", "La Paz", "San José del Cabo"]:
    p = next(pp for pp in D["places"] if pp["name"] == name); x, y = P(kidx(p["km"]))
    rr = 5 * SS; m.ellipse([x-rr, y-rr, x+rr, y+rr], fill=SAND + (230,))
    lbl = name.upper(); w_ = m.textlength(lbl, font=fpl)
    right = name in ("Tecate", "Cataviña", "San Ignacio", "Ciudad Constitución", "La Paz", "San José del Cabo")   # label side away from the line
    tx = x - 16 * SS - w_ if right else x + 16 * SS
    m.text((tx, y + 6 * SS), lbl, font=fpl, fill=SAND + (210,))
if ghost_km is not None:
    gx, gy = P(kidx(ghost_km)); rg = 15 * SS
    m.ellipse([gx-rg, gy-rg, gx+rg, gy+rg], fill=(255, 255, 255, 40), outline=(255, 255, 255, 235), width=3 * SS)
    m.text((gx + 22 * SS, gy - 10 * SS), "FKT", font=font("Inter ExtraBold", 18 * SS), fill=(255, 255, 255, 235))
px, py = P(ki)
glow = Image.new("RGBA", lay.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow); rr = 60 * SS
gd.ellipse([px-rr, py-rr, px+rr, py+rr], fill=TERRA + (170,)); glow = glow.filter(ImageFilter.GaussianBlur(30 * SS))
lay = Image.alpha_composite(glow, lay); m = ImageDraw.Draw(lay); rr = 19 * SS
m.ellipse([px-rr, py-rr, px+rr, py+rr], fill=TERRA + (255,), outline=(255, 255, 255, 255), width=5 * SS)
shadow = lay.split()[3].filter(ImageFilter.GaussianBlur(8 * SS)).point(lambda v: min(255, int(v * 1.3)))
sh = Image.new("RGBA", lay.size, NIGHT + (0,)); sh.putalpha(shadow)
im.alpha_composite(Image.alpha_composite(sh, lay).resize((W, H), Image.LANCZOS))
d = ImageDraw.Draw(im)

# ---------- stats in the empty triangles ----------
R_ = W - L
# top-right: position
spaced(d, (R_, 640), "KM " + nk(km), font("Anton", 150), (255, 255, 255, 255), 0, "rs")
spaced(d, (R_, 690), f"OF {nk(ROUTE)} KM  ·  {km / ROUTE * 100:.0f} %", font("Inter ExtraBold", 26), SAND + (235,), 2, "rs")
spaced(d, (R_, 760), f"{nk(climbed)} / {nk(climb_total)} M CLIMBED", font("Inter Bold", 22), SAND + (200,), 2, "rs")
# bottom-left: race against the record
yb = 1330
if delta is not None:
    ahead = delta <= 0; col = GREEN if ahead else RED
    spaced(d, (L, yb), ("▲ " if ahead else "▼ ") + hm(delta) + " H", font("Anton", 112), col + (255,), 0)
    spaced(d, (L, yb + 46), "AHEAD OF FKT PACE" if ahead else "BEHIND FKT PACE", font("Inter ExtraBold", 28), col + (255,), 3)
    spaced(d, (L, yb + 92), "RECORD  10 D 13 H 24 MIN", font("Inter Bold", 22), SAND + (200,), 2)
    spaced(d, (L, yb + 124), f"FKT GHOST AT KM {nk(ghost_km)}", font("Inter Bold", 22), SAND + (200,), 2)

# ---------- footer: progress bar with ghost ----------
FY = 1700; x0, x1 = L * SS, (W - L) * SS; ry = FY * SS; th = 10 * SS
bl = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); b = ImageDraw.Draw(bl)
b.rounded_rectangle([x0, ry - th/2, x1, ry + th/2], radius=th/2, fill=SAND + (90,))
xm = x0 + (x1 - x0) * km / ROUTE
b.rounded_rectangle([x0, ry - th/2, max(xm, x0 + th), ry + th/2], radius=th/2, fill=TERRA + (255,))
if ghost_km is not None:
    xg = x0 + (x1 - x0) * ghost_km / ROUTE; rg = 12 * SS
    b.ellipse([xg-rg, ry-rg, xg+rg, ry+rg], fill=(255, 255, 255, 50), outline=(255, 255, 255, 230), width=3 * SS)
rm = 15 * SS; b.ellipse([xm-rm, ry-rm, xm+rm, ry+rm], fill=TERRA + (255,), outline=(255, 255, 255, 255), width=4 * SS)
im.alpha_composite(bl.resize((W, H), Image.LANCZOS)); d = ImageDraw.Draw(im); fl = font("Inter Bold", 16)
spaced(d, (L, FY + 34), "TECATE", fl, SAND + (220,), 1.5); spaced(d, (W - L, FY + 34), "SAN JOSÉ DEL CABO", fl, SAND + (220,), 1.5, "rs")

im.convert("RGB").save(a.out, quality=92, subsampling=0)
print("saved", a.out, {"km": km, "day": day, "time": time_s, "ghost_km": ghost_km and round(ghost_km), "delta_h": delta and round(delta, 2)})
