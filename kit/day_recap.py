#!/usr/bin/env python3
""""Story day" – evening recap of one race day (1080x1920), built from the Garmin MapShare feed.
Photo full-bleed under a dark overlay. Content: DAY n RECAP, from -> to, km today / climbing / riding time / total,
a chart of the gap to the FKT record over the whole race so far, and the route bar with today's stretch highlighted.

Feed: Garmin MapShare KML (https://share.garmin.com/Feed/Share/<user>?d1=2026-12-30T00:00z) – URL or local file.
Local time: Baja California = UTC-8, Baja California Sur (south of 28°N, track km >= 1180) = UTC-7.
Usage: day_recap.py PHOTO OUT.jpg --feed URL|FILE [--day N] [--focus F | --hfocus F] [--overlay 215]
       (without --feed: --km-from/--km-to/--ride-h/--day give the numbers by hand; no gap chart)
"""
import argparse, datetime as dt, json, math, os, re, subprocess, sys, urllib.request
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
KIT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, KIT)
try:
    import pillow_heif; pillow_heif.register_heif_opener()
except ImportError:
    pass
from fkt_splits import record_h_at

W, H, SS = 1080, 1920, 3
TERRA, SAND, GOLD, NIGHT, CACTUS = (217, 98, 43), (242, 211, 160), (244, 184, 96), (26, 18, 11), (143, 176, 122)
GREEN, RED = (170, 214, 140), (238, 120, 70)
D = json.load(open(os.path.join(KIT, "route_data.json"), encoding="utf-8")); ROUTE = D["route_km"]; TR = D["track"]
START_UTC = dt.datetime(2026, 12, 30, 18, 0, tzinfo=dt.timezone.utc)      # 30.12.2026 10:00 PST, Tecate
RECORD_H, BCS_KM = 253.4, 1180
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
def spaced(dr, xy, text, f, fill, track, anchor="ls"):
    x, y = xy
    w = sum(dr.textlength(c, font=gf(c, f)) for c in text) + track * (len(text) - 1)
    if anchor == "rs": x -= w
    if anchor == "ms": x -= w / 2
    for ch in text: dr.text((x, y), ch, font=gf(ch, f), fill=fill, anchor="ls"); x += dr.textlength(ch, font=gf(ch, f)) + track
    return x - track
nk = lambda x: f"{int(round(x)):,}".replace(",", ".")
def hm(h): h = abs(h); return f"{int(h)}:{int(round((h - int(h)) * 60)):02d}"

ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("out")
ap.add_argument("--feed"); ap.add_argument("--day", type=int)
ap.add_argument("--km-from", type=float); ap.add_argument("--km-to", type=float); ap.add_argument("--ride-h", type=float)
ap.add_argument("--overlay", type=int, default=215)
ap.add_argument("--focus", type=float, default=0.5); ap.add_argument("--hfocus", type=float, default=0.5)
a = ap.parse_args()

# ---------- feed -> points (utc, lat, lon) -> km on track ----------
def load_feed(src):
    raw = urllib.request.urlopen(src, timeout=30).read() if src.startswith("http") else open(src, "rb").read()
    ns = {"k": "http://www.opengis.net/kml/2.2"}; out = []
    for pm in ET.fromstring(raw).iter("{http://www.opengis.net/kml/2.2}Placemark"):
        w, c = pm.find(".//k:TimeStamp/k:when", ns), pm.find(".//k:Point/k:coordinates", ns)
        if w is None or c is None: continue
        lon, lat = map(float, c.text.strip().split(",")[:2])
        out.append((dt.datetime.fromisoformat(w.text.strip().replace("Z", "+00:00")), lat, lon))
    return sorted(out)
def proj(la, lo, p, q):
    c = math.cos(math.radians(la)); ax, ay = (p[2] - lo) * c, p[1] - la; bx, by = (q[2] - lo) * c, q[1] - la
    dx, dy = bx - ax, by - ay; t = max(0, min(1, -(ax * dx + ay * dy) / ((dx * dx + dy * dy) or 1e-12)))
    return 111.2 * math.hypot(ax + t * dx, ay + t * dy), p[0] + t * (q[0] - p[0])
def snap(pts):
    prev, res = 0.0, []
    for t, la, lo in pts:
        best = min((proj(la, lo, TR[i], TR[i + 1]) for i in range(len(TR) - 1) if prev - 6 <= TR[i][0] <= prev + 160), default=None)
        if best is None or best[0] > 15: continue                     # off route (hotel, detour): skip
        prev = max(prev, best[1]); res.append((t, prev))
    return res
def local(t, km): return t + dt.timedelta(hours=-7 if km >= BCS_KM else -8)
def day_of(t, km): return (local(t, km).date() - dt.date(2026, 12, 29)).days

step = D["profile_step_km"]; climb = D["climb_cum_m"]
def at(arr, k):
    i = min(int(k // step), len(arr) - 2); f = (k - i * step) / step; return arr[i] + (arr[i + 1] - arr[i]) * f

track = []
if a.feed:
    track = [(t, k) for t, k in snap(load_feed(a.feed)) if t >= START_UTC - dt.timedelta(minutes=30)]
    if not track: sys.exit("feed has no points on the route since the start")
    day = a.day or day_of(*track[-1])
    today = [(t, k) for t, k in track if day_of(t, k) == day]
    if not today: sys.exit(f"no points for day {day}")
    before = [k for t, k in track if day_of(t, k) < day]
    k0, k1 = (before[-1] if before else 0.0), today[-1][1]
    ride = sum((t2 - t1).total_seconds() for (t1, ka), (t2, kb) in zip(today, today[1:])
               if kb - ka > 0.5 and (t2 - t1).total_seconds() < 3 * 3600) / 3600
    end_local = local(*today[-1])
else:
    if a.km_from is None or a.km_to is None or not a.day: sys.exit("need --feed, or --day --km-from --km-to [--ride-h]")
    day, k0, k1, ride, end_local = a.day, a.km_from, a.km_to, a.ride_h, None
gain = at(climb, k1) - at(climb, k0)
# gap to the record at every feed point (h > 0 = ahead)
gap = [((t - START_UTC).total_seconds() / 3600, record_h_at(k, ROUTE, RECORD_H) - (t - START_UTC).total_seconds() / 3600)
       for t, k in track if k > 3 and (not a.feed or t <= today[-1][0])]
if len(gap) > 4:
    sm = [(gap[i][0], sorted(g for _, g in gap[max(0, i - 2):i + 3])[len(gap[max(0, i - 2):i + 3]) // 2]) for i in range(len(gap))]
    gap = sm[:-1] + [gap[-1]]
places = D["places"]
def place_at(k, tol=15):
    p = min(places, key=lambda p: abs(p["km"] - k)); return p["name"] if abs(p["km"] - k) <= tol and not p.get("near") else None

# ---------- background: photo under a dark overlay ----------
src = Image.open(a.photo); im = ImageOps.exif_transpose(src).convert("RGB"); r = W / H
if im.width / im.height > r:
    nw = round(im.height * r); x0 = round((im.width - nw) * a.hfocus); im = im.crop((x0, 0, x0 + nw, im.height))
else:
    nh = round(im.width / r); y0 = round((im.height - nh) * a.focus); im = im.crop((0, y0, im.width, y0 + nh))
im = im.resize((W, H), Image.LANCZOS)
from desert_grade import apply_grade
im = apply_grade(im, 1.0)
# text block is anchored to the route bar at the bottom: no empty gap, more photo on top
BY = 1712
HAS_CHART = len(gap) >= 2
PH = BY - (750 if HAS_CHART else 520)
soft = im.filter(ImageFilter.GaussianBlur(7)); m = Image.new("L", (W, H), 0)
ImageDraw.Draw(m).rectangle([0, PH, W, H], fill=255); im.paste(soft, (0, 0), m.filter(ImageFilter.GaussianBlur(40)))
canvas = im.convert("RGBA")
ov = Image.new("L", (1, H))
for yy in range(H):
    t = min(1, max(0, (yy - (PH - 280)) / 320)); top = max(0, 1 - yy / 380)            # darker under the IG header too
    ov.putpixel((0, yy), int(max(60 + (a.overlay - 60) * (t * t * (3 - 2 * t)), 150 * top ** 1.5)))
ol = Image.new("RGBA", (W, H), NIGHT + (0,)); ol.putalpha(ov.resize((W, H))); canvas.alpha_composite(ol)
d = ImageDraw.Draw(canvas); L, R_ = 64, W - 64

# ---------- headline ----------
d.rectangle([L, PH, L + 90, PH + 5], fill=GOLD + (255,))
x = spaced(d, (L, PH + 132), f"DAY {day}", font("Anton", 132), SAND + (255,), 0)
spaced(d, (x + 24, PH + 132), "RECAP", font("Anton", 56), GOLD + (255,), 4)
date_s = end_local.strftime("%d.%m.%Y") if end_local else (dt.date(2026, 12, 29) + dt.timedelta(days=day)).strftime("%d.%m.%Y")
spaced(d, (R_, PH + 132), date_s, font("Inter Bold", 22), SAND + (190,), 3, "rs")
def where(k):
    n = place_at(k)
    if n: return n.upper()
    p = min(places, key=lambda p: abs(p["km"] - k))
    return f"NEAR {p['name'].upper()}" if abs(p["km"] - k) <= 40 else f"KM {nk(k)}"
spaced(d, (L, PH + 182), f"{where(k0)}  →  {where(k1)}", font("Inter ExtraBold", 27), TERRA + (255,), 2)

# ---------- 2x2 stats ----------
cells = [(nk(k1 - k0), "KM", "TODAY"), (nk(gain), "M", "CLIMBED TODAY"),
         ((hm(ride) if ride else "–"), "H", "RIDING TIME"), (nk(k1), "KM", f"TOTAL · {k1 / ROUTE * 100:.0f} %")]
cw = (R_ - L) / 2
for i, (v, unit, lbl) in enumerate(cells):
    x, y = L + (i % 2) * cw, PH + 292 + (i // 2) * 128
    xe = spaced(d, (x, y), v, font("Anton", 80), (255, 255, 255, 255), 0)
    spaced(d, (xe + 10, y), unit, font("Anton", 40), SAND + (255,), 1)
    spaced(d, (x, y + 32), lbl, font("Inter Bold", 19), SAND + (170,), 3)
d.line([(L + cw - 30, PH + 228), (L + cw - 30, PH + 452)], fill=SAND + (60,), width=2)

# ---------- gap to the record ----------
cy0, cy1 = PH + 548, PH + 668
if HAS_CHART:
    now_gap = gap[-1][1]; ahead = now_gap >= 0; col = GREEN if ahead else RED
    spaced(d, (L, cy0 - 26), "VS. FKT RECORD", font("Inter ExtraBold", 21), SAND + (200,), 3)
    spaced(d, (R_, cy0 - 26), ("▲ " if ahead else "▼ ") + hm(now_gap) + (" H AHEAD" if ahead else " H BEHIND"),
           font("Inter ExtraBold", 24), col + (255,), 2, "rs")
    X0, X1 = L, R_; days_total = 11
    gmax = max(2.0, max(abs(g) for _, g in gap)) * 1.15
    X = lambda h: X0 + h / (days_total * 24) * (X1 - X0)
    Y = lambda g: (cy0 + cy1) / 2 - g / gmax * (cy1 - cy0) / 2
    big = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); b = ImageDraw.Draw(big)
    for dd in range(1, days_total):                                          # day grid
        b.line([(X(dd * 24) * SS, cy0 * SS), (X(dd * 24) * SS, cy1 * SS)], fill=SAND + (28,), width=1 * SS)
    z = Y(0)
    pts = [(X(h) * SS, Y(g) * SS) for h, g in gap]
    up = [(x, min(y, z * SS)) for x, y in pts]; dn = [(x, max(y, z * SS)) for x, y in pts]
    b.polygon(up + [(pts[-1][0], z * SS), (pts[0][0], z * SS)], fill=GREEN + (70,))
    b.polygon(dn + [(pts[-1][0], z * SS), (pts[0][0], z * SS)], fill=RED + (70,))
    b.line([(X0 * SS, z * SS), (X1 * SS, z * SS)], fill=SAND + (150,), width=2 * SS)
    b.line(pts, fill=col + (255,), width=4 * SS, joint="curve")
    ex, ey = pts[-1]; rr = 9 * SS
    b.ellipse([ex - rr, ey - rr, ex + rr, ey + rr], fill=col + (255,), outline=(255, 255, 255, 255), width=3 * SS)
    canvas.alpha_composite(big.resize((W, H), Image.LANCZOS)); d = ImageDraw.Draw(canvas)
    spaced(d, (X1, z - 8), "FKT PACE", font("Inter Bold", 16), SAND + (170,), 2, "rs")
    fd = font("Inter Bold", 16)
    for dd in range(1, days_total + 1):
        d.text((X((dd - 0.5) * 24), cy1 + 24), str(dd), font=fd, fill=SAND + (150 if dd != day else 255,), anchor="ms")

# ---------- route bar with today's stretch ----------
by = BY; bx0, bx1 = L, R_
big = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); b = ImageDraw.Draw(big)
XB = lambda k: (bx0 + (bx1 - bx0) * k / ROUTE) * SS
b.line([(bx0 * SS, by * SS), (bx1 * SS, by * SS)], fill=SAND + (90,), width=9 * SS)
b.line([(bx0 * SS, by * SS), (XB(k0), by * SS)], fill=TERRA + (170,), width=9 * SS)
b.line([(XB(k0), by * SS), (XB(k1), by * SS)], fill=GOLD + (255,), width=9 * SS)
rr = 13 * SS; b.ellipse([XB(k1) - rr, by * SS - rr, XB(k1) + rr, by * SS + rr], fill=TERRA + (255,), outline=(255, 255, 255, 255), width=4 * SS)
canvas.alpha_composite(big.resize((W, H), Image.LANCZOS)); d = ImageDraw.Draw(canvas)
fl = font("Inter Bold", 17)
spaced(d, (bx0, by + 40), "TECATE", fl, SAND + (200,), 2)
spaced(d, (bx1, by + 40), "SAN JOSÉ DEL CABO", fl, SAND + (200,), 2, "rs")

canvas.convert("RGB").save(a.out, quality=92, subsampling=0)
print("saved", a.out, {"day": day, "km_from": round(k0), "km_to": round(k1), "km_today": round(k1 - k0), "gain": round(gain),
                       "ride_h": ride and round(ride, 2), "gap_h": gap and round(gap[-1][1], 2), "points": len(track)})
