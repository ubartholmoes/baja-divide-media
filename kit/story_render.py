#!/usr/bin/env python3
"""Baja Divide Instagram story (1080x1920 JPEG) from a photo.

KM, day, time and place come automatically from the photo's EXIF:
  time  = DateTimeOriginal (local time of capture, as the phone stored it)
  day   = date - 29.12.2026 (30.12. = DAY 1)
  km    = GPS position snapped onto the route (route_data.json "track", needs <= 15 km off-track)
Overrides: --km 417 --day 3 --time 15:39 --place "Vicente Guerrero"
Usage: story_render.py PHOTO OUT.jpg [--focus 0.5] [--hfocus 0.5] [--grade 1.0] [overrides]
"""
import argparse, datetime as dt, json, math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageOps
KIT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, KIT)
try:
    import pillow_heif; pillow_heif.register_heif_opener()
except ImportError:
    pass

W, H = 1080, 1920
TERRA, SAND, GOLD, NIGHT, CACTUS = (217, 98, 43), (242, 211, 160), (244, 184, 96), (26, 18, 11), (143, 176, 122)
START = dt.date(2026, 12, 30)
D = json.load(open(os.path.join(KIT, "route_data.json"), encoding="utf-8"))
ROUTE_KM = D["route_km"]
FONTDIR = os.path.join(KIT, "fonts")
FILES = {"Anton": "anton-latin-400-normal.woff", "Archivo Black": "archivo-black-latin-400-normal.woff",
         "Inter ExtraBold": "inter-latin-800-normal.woff", "Inter Bold": "inter-latin-700-normal.woff"}
def font(name, size):
    p = os.path.join(FONTDIR, FILES[name])
    if not os.path.isfile(p): p = subprocess.check_output(["fc-match", "-f", "%{file}", name]).decode()
    return ImageFont.truetype(p, int(size))

ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("out")
ap.add_argument("--km", type=float); ap.add_argument("--day", type=int); ap.add_argument("--time"); ap.add_argument("--place")
ap.add_argument("--focus", type=float, default=0.5); ap.add_argument("--hfocus", type=float, default=0.5)
ap.add_argument("--grade", type=float, default=1.0)
ap.add_argument("--live", choices=["A", "B"], help="live-tracking story instead of the KM stamp (every 5th story)")
ap.add_argument("--live-url", default="WWW.UBA-CYCLING.DE/LIVE")
ap.add_argument("--minimap", action="store_true", help="small route map (from the GPX) bottom right")
ap.add_argument("--ghost", action="store_true", help="race the FKT record: ghost marker on the route bar + time delta")
ap.add_argument("--record-h", type=float, default=253.4, help="FKT record in hours (10 d 13 h 24 min)")
ap.add_argument("--start", default="2026-12-30 07:00", help="start time in Tecate (local)")
a = ap.parse_args()

src = Image.open(a.photo); ex = src.getexif()
sub, gps = ex.get_ifd(0x8769), ex.get_ifd(0x8825)
# ---- time / day from EXIF ----
shot = None
if sub.get(36867):
    try: shot = dt.datetime.strptime(sub[36867], "%Y:%m:%d %H:%M:%S")
    except ValueError: pass
time_s = a.time or (shot.strftime("%H:%M") if shot else None)
day = a.day if a.day is not None else ((shot.date() - START).days + 1 if shot and shot.date() >= START else None)
# ---- km / place from GPS ----
km, place = a.km, a.place
if km is None and gps.get(2) and "track" in D:
    to_deg = lambda v, ref: (float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600) * (-1 if ref in ("S", "W") else 1)
    lat, lon = to_deg(gps[2], gps.get(1, "N")), to_deg(gps[4], gps.get(3, "E"))
    best = min(D["track"], key=lambda t: (t[1] - lat) ** 2 + ((t[2] - lon) * math.cos(math.radians(lat))) ** 2)
    off = 111.2 * math.hypot(best[1] - lat, (best[2] - lon) * math.cos(math.radians(lat)))
    if off <= 15: km = best[0]
if km is not None and not place:
    near = min(D["places"], key=lambda p: abs(p["km"] - km))
    if abs(near["km"] - km) <= 12: place = near["name"]

# ---- photo: cover-crop 9:16, grade ----
im = ImageOps.exif_transpose(src).convert("RGB"); r = W / H
if im.width / im.height > r:
    nw = round(im.height * r); x0 = round((im.width - nw) * a.hfocus); im = im.crop((x0, 0, x0 + nw, im.height))
else:
    nh = round(im.width / r); y0 = round((im.height - nh) * a.focus); im = im.crop((0, y0, im.width, y0 + nh))
im = im.resize((W, H), Image.LANCZOS)
if a.grade > 0:
    from desert_grade import apply_grade; im = apply_grade(im, a.grade)
im = im.convert("RGBA")

# ---- compact stamp + footer, low in the frame (Instagram covers ~the bottom 230 px) ----
FOOT_Y = 1672          # route bar centre line
STAMP_Y = 1600         # baseline of the KM figure
GH = 560
g = Image.new("L", (1, GH))
for y in range(GH): g.putpixel((0, y), int(235 * (y / (GH - 1)) ** 1.25))
grad = Image.new("RGBA", (W, GH), NIGHT + (0,)); grad.putalpha(g.resize((W, GH))); im.alpha_composite(grad, (0, H - GH))

SS = 4
def spaced(d, xy, text, f, fill, track):
    x, y = xy
    for ch in text: d.text((x, y), ch, font=f, fill=fill, anchor="ls"); x += d.textlength(ch, font=f) + track
    return x - track
def text_w(d, text, f, track): return sum(d.textlength(c, font=f) for c in text) + track * (len(text) - 1)

def draw_cactus(d, ox, oy, k, mirror):
    def qb(p0, p1, p2, n=12): return [((1-t)**2*p0[0]+2*(1-t)*t*p1[0]+t*t*p2[0], (1-t)**2*p0[1]+2*(1-t)*t*p1[1]+t*t*p2[1]) for t in [i/n for i in range(n+1)]]
    f = lambda x, y: (ox + x * k, oy + y * k)
    d.rectangle([f(43.4, 29.4), f(76.6, 184.7)], fill=CACTUS + (255,))
    cx, cy = f(60, 29.4); rr = 16.6 * k; d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=CACTUS + (255,))
    arms = [((50,132),(32,132),(20,132),(20,120),(20,74)), ((70,106),(88,106),(100,106),(100,94),(100,52))]
    if mirror: arms = [((70,124),(88,124),(100,124),(100,112),(100,66)), ((50,98),(32,98),(20,98),(20,86),(20,48))]
    w = 24 * k
    for a0, a1, ac, a2, a3 in arms:
        pts = [f(*p) for p in [a0, a1] + qb(a1, ac, a2)[1:] + [a3]]
        d.line(pts, fill=CACTUS + (255,), width=int(w), joint="curve")
        for p in (pts[0], pts[-1]): d.ellipse([p[0]-w/2, p[1]-w/2, p[0]+w/2, p[1]+w/2], fill=CACTUS + (255,))

def make_logo(cap):
    S = cap / 0.859 * SS; k = S / 200; fa = font("Anton", S)
    seq = ["D", "C1", "V", "C2", "D", "E"]
    wid = sum(fa.getlength(s) if s[0] != "C" else 108 * k for s in seq)
    bcap = cap * 0.30 * SS; fb = font("Archivo Black", bcap / 0.72); gap = cap * 0.22 * SS
    img = Image.new("RGBA", (int(wid + 4 * SS), int(bcap + gap + cap * SS + 4 * SS)), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    nat = sum(d.textlength(c, font=fb) for c in "BAJA"); spaced(d, (0, bcap), "BAJA", fb, TERRA + (255,), (wid - nat) / 3)
    base = bcap + gap + cap * SS; x = 0
    for s in seq:
        if s[0] == "C": draw_cactus(d, x - 6 * k, base - 184.7 * k, k, s == "C2"); x += 108 * k
        else: d.text((x, base), s, font=fa, fill=SAND + (255,), anchor="ls"); x += fa.getlength(s)
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS), (bcap + gap + cap * SS / 2) / SS

# ---- race against the record (linear record pace over the route) ----
ghost_km = delta_h = None
if a.ghost and km is not None and day and time_s:
    t0 = dt.datetime.strptime(a.start, "%Y-%m-%d %H:%M")
    now = dt.datetime.combine(START + dt.timedelta(days=day - 1), dt.datetime.strptime(time_s, "%H:%M").time())
    el = (now - t0).total_seconds() / 3600
    ghost_km = max(0, min(ROUTE_KM, el / a.record_h * ROUTE_KM))
    delta_h = el - km / ROUTE_KM * a.record_h          # > 0: behind record pace
def hm(h): h = abs(h); return f"{int(h)}:{int(round((h - int(h)) * 60)) % 60:02d} H"
d = ImageDraw.Draw(im)
L = 60
# stamp: KM figure, and right of it two small lines (DAY · TIME / NEAR PLACE)
fkm, fsub, fpl = font("Anton", 88), font("Inter ExtraBold", 27), font("Inter Bold", 21)
def soft(xy, text, f, fill, track):  # small text with a soft dark halo for bright backgrounds
    from PIL import ImageFilter
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0)); hd = ImageDraw.Draw(halo)
    spaced(hd, xy, text, f, NIGHT + (235,), track)
    h_ = halo.filter(ImageFilter.GaussianBlur(4)); im.alpha_composite(h_); im.alpha_composite(h_)
    spaced(ImageDraw.Draw(im), xy, text, f, fill, track)
def dot(x, cy, r):
    dd = ImageDraw.Draw(im)
    dd.ellipse([x, cy - r, x + 2 * r, cy + r], fill=TERRA + (255,), outline=(255, 255, 255, 255), width=3)
    return x + 2 * r
if a.live == "A":   # big LIVE TRACKING, URL + "Link in Bio" to the right
    x = dot(L, STAMP_Y - 32, 13) + 16
    t = "LIVE TRACKING"
    d.text((x + 2, STAMP_Y + 2), t, font=fkm, fill=(0, 0, 0, 90), anchor="ls"); d.text((x, STAMP_Y), t, font=fkm, fill=(255, 255, 255, 255), anchor="ls")
    xs = x + d.textlength(t, font=fkm) + 26
    d.line([(xs - 13, STAMP_Y - 66), (xs - 13, STAMP_Y - 2)], fill=TERRA + (255,), width=4)
    soft((xs, STAMP_Y - 34), a.live_url.upper(), font("Inter ExtraBold", 25), GOLD + (255,), 1)
    soft((xs, STAMP_Y - 6), "LINK IN BIO", font("Inter Bold", 17), SAND + (235,), 2)
elif a.live == "B":  # small LIVE TRACKING label, big URL, tiny "Link in Bio" underneath
    x = dot(L, STAMP_Y - 112, 9) + 12
    soft((x, STAMP_Y - 102), "LIVE TRACKING", font("Inter ExtraBold", 27), GOLD + (255,), 3)
    fu = font("Anton", 70); t = a.live_url.lower().replace("www.", "")
    d = ImageDraw.Draw(im)
    d.text((L + 2, STAMP_Y - 18), t, font=fu, fill=(0, 0, 0, 90), anchor="ls"); d.text((L, STAMP_Y - 20), t, font=fu, fill=(255, 255, 255, 255), anchor="ls")
    soft((L + 2, STAMP_Y + 6), "LINK IN BIO", font("Inter Bold", 16), SAND + (235,), 2.5)
else:
    km_txt = f"KM {int(round(km)):,}".replace(",", ".") if km is not None else "ROAD TO BAJA"
    d.text((L + 2, STAMP_Y + 2), km_txt, font=fkm, fill=(0, 0, 0, 90), anchor="ls")
    d.text((L, STAMP_Y), km_txt, font=fkm, fill=(255, 255, 255, 255), anchor="ls")
    xs = L + d.textlength(km_txt, font=fkm) + 26
    d.line([(xs - 13, STAMP_Y - 66), (xs - 13, STAMP_Y - 2)], fill=TERRA + (255,), width=4)
    parts = ([f"DAY {day}"] if day else []) + ([time_s] if time_s else [])
    line1 = "  ·  ".join(parts)
    lines = []
    if line1: lines.append((line1, fsub, GOLD + (255,), 2))
    if place: lines.append((("NEAR " + place).upper(), fpl, SAND + (245,), 1.5))
    if delta_h is not None:
        txt = ("▲ " + hm(delta_h) + " AHEAD OF FKT PACE") if delta_h <= 0 else ("▼ " + hm(delta_h) + " BEHIND FKT PACE")
        lines.append((txt, font("Inter ExtraBold", 20), ((170, 214, 140) if delta_h <= 0 else (238, 120, 70)) + (255,), 1.5))
    ys = {1: [-18], 2: [-34, -3], 3: [-52, -26, 0]}[len(lines)] if lines else []
    for (t_, f_, c_, tr_), yy in zip(lines, ys):
        soft((xs, STAMP_Y + yy), t_, f_, c_, tr_)

# footer: logo + route bar
d = ImageDraw.Draw(im)
logo, mid = make_logo(36); ly = round(FOOT_Y - mid); im.alpha_composite(logo, (L, ly))
big = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); b = ImageDraw.Draw(big)
x0 = (L + logo.width + 28) * SS; x1 = (W - L) * SS; ry = FOOT_Y * SS; th = 9 * SS
prog = 0 if km is None else max(0, min(1, km / ROUTE_KM)); xm = x0 + (x1 - x0) * prog
b.rounded_rectangle([x0, ry - th/2, x1, ry + th/2], radius=th/2, fill=SAND + (95,))
b.rounded_rectangle([x0, ry - th/2, max(xm, x0 + th), ry + th/2], radius=th/2, fill=TERRA + (255,))
re_ = 10 * SS; b.ellipse([x1-re_, ry-re_, x1+re_, ry+re_], fill=NIGHT + (255,), outline=SAND + (255,), width=4 * SS)
if ghost_km is not None:
    xg = x0 + (x1 - x0) * ghost_km / ROUTE_KM; rg = 11 * SS
    b.ellipse([xg-rg, ry-rg, xg+rg, ry+rg], fill=(255, 255, 255, 60), outline=(255, 255, 255, 230), width=3 * SS)
rm = 14 * SS; b.ellipse([xm-rm, ry-rm, xm+rm, ry+rm], fill=TERRA + (255,), outline=(255, 255, 255, 255), width=4 * SS)
im.alpha_composite(big.resize((W, H), Image.LANCZOS))
if ghost_km is not None:
    fg = font("Inter ExtraBold", 14); dg = ImageDraw.Draw(im)
    dg.text((xg / SS, FOOT_Y - 20), "FKT", font=fg, fill=(255, 255, 255, 230), anchor="ms")
d = ImageDraw.Draw(im); fl = font("Inter Bold", 15)
spaced(d, (x0 / SS, FOOT_Y + 30), "TECATE", fl, SAND + (220,), 1.5)
t = "SAN JOSÉ DEL CABO"; spaced(d, (x1 / SS - text_w(d, t, fl, 1.5), FOOT_Y + 30), t, fl, SAND + (220,), 1.5)

# ---- mini map: the GPX line itself draws the peninsula ----
if a.minimap and "track" in D:
    from PIL import ImageFilter
    tr = D["track"]; lat0 = sum(t[1] for t in tr) / len(tr); cx = math.cos(math.radians(lat0))
    xs_ = [t[2] * cx for t in tr]; ys_ = [-t[1] for t in tr]
    mw = 175; sc = mw / (max(xs_) - min(xs_)); mh = (max(ys_) - min(ys_)) * sc
    ox, oy = W - L - mw, STAMP_Y + 10 - mh            # bottom-right, bottom aligned with the stamp
    P = lambda i: ((ox + (xs_[i] - min(xs_)) * sc) * SS, (oy + (ys_[i] - min(ys_)) * sc) * SS)
    layer = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); m = ImageDraw.Draw(layer)
    m.line([P(i) for i in range(len(tr))], fill=SAND + (190,), width=4 * SS, joint="curve")
    ki = max(0, min(len(tr) - 1, int(round((km or 0) / 2))))
    if ki > 0: m.line([P(i) for i in range(ki + 1)], fill=TERRA + (255,), width=6 * SS, joint="curve")
    if ghost_km is not None:
        gx, gy = P(min(len(tr) - 1, int(round(ghost_km / 2)))); rg = 8 * SS
        m.ellipse([gx-rg, gy-rg, gx+rg, gy+rg], outline=(255, 255, 255, 230), width=2 * SS)
    px, py = P(ki)
    glow = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow); rr = 26 * SS
    gd.ellipse([px-rr, py-rr, px+rr, py+rr], fill=TERRA + (150,)); glow = glow.filter(ImageFilter.GaussianBlur(14 * SS))
    layer = Image.alpha_composite(glow, layer); m = ImageDraw.Draw(layer); rr = 10 * SS
    m.ellipse([px-rr, py-rr, px+rr, py+rr], fill=TERRA + (255,), outline=(255, 255, 255, 255), width=3 * SS)
    shadow = layer.split()[3].filter(ImageFilter.GaussianBlur(7 * SS)).point(lambda v: min(255, v * 1.1))
    sh = Image.new("RGBA", layer.size, NIGHT + (0,)); sh.putalpha(shadow)
    im.alpha_composite(Image.alpha_composite(sh, layer).resize((W, H), Image.LANCZOS))

im.convert("RGB").save(a.out, quality=92, subsampling=0)
print("saved", a.out, {"km": km, "day": day, "time": time_s, "place": place})
