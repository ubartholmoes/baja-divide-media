#!/usr/bin/env python3
"""Baja Divide audiogram renderer: photo + voice memo -> 4:5 feed video (1080x1350).

Usage:
  baja_render.py PHOTO AUDIO WORDS_JSON OUT.mp4 [--day 4 --km 1130] [--focus 0.5] [--hfocus 0.5] [--grade 1.0]
WORDS_JSON: transcribe.mjs output ({"chunks":[{"text","timestamp":[s,e]}]}); fix misheard words in it before rendering.
--focus / --hfocus: crop position 0..1 (top/left .. bottom/right) when the photo is taller / wider than 4:5.
--km: total km ridden (marker position, label "KM 1.130"); --day: shown under it. Omit both before the start.
"""
import argparse, json, subprocess, numpy as np, os, tempfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

W, H, FPS = 1080, 1350, 30
ROUTE_KM = 2489  # Ulrich's Baja Divide track, Tecate -> San José del Cabo

# ---- palette: "desert dusk" ----
TERRA = (217, 98, 43)     # terracotta  #D9622B
SAND = (242, 211, 160)    # sand        #F2D3A0
GOLD = (244, 184, 96)     # gold        #F4B860
NIGHT = (26, 18, 11)      # warm dark   #1A120B

KIT = os.path.dirname(os.path.abspath(__file__))
FONTDIR = os.path.join(KIT, "fonts")
FONT_FILES = {"Anton": "anton-latin-400-normal.woff", "Archivo Black": "archivo-black-latin-400-normal.woff",
              "Inter ExtraBold": "inter-latin-800-normal.woff", "Inter Bold": "inter-latin-700-normal.woff"}
FONT_SUB = "Inter ExtraBold"

def find_font(name):
    p = os.path.join(FONTDIR, FONT_FILES.get(name, ""))
    if os.path.isfile(p): return p
    return subprocess.check_output(["fc-match", "-f", "%{file}", name]).decode()

ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("audio"); ap.add_argument("words"); ap.add_argument("out")
ap.add_argument("--day", type=int, default=None)
ap.add_argument("--km", type=float, default=None)
ap.add_argument("--focus", type=float, default=0.5)
ap.add_argument("--hfocus", type=float, default=0.5)
ap.add_argument("--grade", type=float, default=1.0, help="Terracotta grade strength 0..1 (0 = off)")
a = ap.parse_args()
tmp = tempfile.mkdtemp()

# ---------- photo: cover-crop to 4:5 ----------
try:
    import pillow_heif; pillow_heif.register_heif_opener()
except ImportError:
    pass
im = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB")
r = W / H
if im.width / im.height > r:  # too wide -> crop sides (centre)
    nw = round(im.height * r); x0 = round((im.width - nw) * a.hfocus)
    im = im.crop((x0, 0, x0 + nw, im.height))
else:                          # too tall -> crop vertically at focus
    nh = round(im.width / r); y0 = round((im.height - nh) * a.focus)
    im = im.crop((0, y0, im.width, y0 + nh))
im = im.resize((W * 2, H * 2), Image.LANCZOS)
import sys; sys.path.insert(0, KIT)
if a.grade > 0:
    from desert_grade import apply_grade
    im = apply_grade(im, a.grade)
im.save(f"{tmp}/bg.jpg", quality=95)

# ---------- static overlay: bottom gradient + footer (logo A + bold route bar) ----------
ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
GH = 640
g = Image.new("L", (1, GH))
for y in range(GH):
    g.putpixel((0, y), int(225 * (y / (GH - 1)) ** 1.4))
grad = Image.new("RGBA", (W, GH), NIGHT + (0,)); grad.putalpha(g.resize((W, GH)))
ov.alpha_composite(grad, (0, H - GH))

CACTUS = (143, 176, 122)  # #8FB07A
SS = 4
ANTON = find_font("Anton"); ARCH = find_font("Archivo Black")
INTER_XB = find_font("Inter ExtraBold"); INTER_B = find_font("Inter Bold")

def qbez(p0, p1, p2, n=12):
    return [((1-t)**2*p0[0]+2*(1-t)*t*p1[0]+t*t*p2[0], (1-t)**2*p0[1]+2*(1-t)*t*p1[1]+t*t*p2[1]) for t in [i/n for i in range(n+1)]]

def draw_cactus(d, ox, oy, k, mirror):
    # geometry in a 120x200 box matching Anton at font-size 200 (cap 12.8..184.7)
    f = lambda x, y: (ox + x * k, oy + y * k)
    d.rectangle([f(43.4, 29.4), f(76.6, 184.7)], fill=CACTUS + (255,))
    cx, cy = f(60, 29.4); r = 16.6 * k; d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CACTUS + (255,))
    arms = [((50, 132), (32, 132), (20, 132), (20, 120), (20, 74)), ((70, 106), (88, 106), (100, 106), (100, 94), (100, 52))]
    if mirror:
        arms = [((70, 124), (88, 124), (100, 124), (100, 112), (100, 66)), ((50, 98), (32, 98), (20, 98), (20, 86), (20, 48))]
    w = 24 * k
    for a0, a1, ac, a2, a3 in arms:
        pts = [a0, a1] + qbez(a1, ac, a2)[1:] + [a3]
        pts = [f(*p) for p in pts]
        d.line(pts, fill=CACTUS + (255,), width=int(w), joint="curve")
        for p in (pts[0], pts[-1]):
            d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=CACTUS + (255,))

SYMBOLS = "▲▼→●"           # not in the latin woff subsets -> draw these with DejaVu Sans Bold
_fb = {}
def gf(ch, f):
    if ch not in SYMBOLS: return f
    if f.size not in _fb:
        _fb[f.size] = ImageFont.truetype(subprocess.check_output(["fc-match", "-f", "%{file}", "DejaVu Sans:bold"]).decode(), int(f.size * 0.8))
    return _fb[f.size]
def spaced(d, xy, text, font, fill, track):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=gf(ch, font), fill=fill, anchor="ls"); x += d.textlength(ch, font=gf(ch, font)) + track
    return x - track

def make_logo(cap):
    S = cap / 0.859 * SS            # Anton font size (supersampled)
    k = S / 200
    fa = ImageFont.truetype(ANTON, int(S))
    seq = ["D", "C1", "V", "C2", "D", "E"]
    wid = sum(fa.getlength(s) if s[0] != "C" else (120 - 12) * k for s in seq)
    bcap = cap * 0.30 * SS
    fb = ImageFont.truetype(ARCH, int(bcap / 0.72))
    gap1 = cap * 0.22 * SS
    Wl = int(wid + 4 * SS); Hl = int(bcap + gap1 + cap * SS + 4 * SS)
    img = Image.new("RGBA", (Wl, Hl), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    # BAJA, tracked to the width of DIVIDE
    nat = sum(d.textlength(c, font=fb) for c in "BAJA")
    spaced(d, (0, bcap), "BAJA", fb, TERRA + (255,), (wid - nat) / 3)
    # DIVIDE with cactus I's
    base = bcap + gap1 + cap * SS; x = 0; top = base - 184.7 * k
    for s in seq:
        if s[0] == "C":
            draw_cactus(d, x - 6 * k, top, k, s == "C2"); x += (120 - 12) * k
        else:
            d.text((x, base), s, font=fa, fill=SAND + (255,), anchor="ls"); x += fa.getlength(s)
    img = img.resize((Wl // SS, Hl // SS), Image.LANCZOS)
    return img, (bcap + gap1 + cap * SS / 2) / SS  # img, DIVIDE mid-y

logo, mid_y = make_logo(58)
lx = 56; ly = round(H - 72 - mid_y)
ov.alpha_composite(logo, (lx, ly))

# bold route bar, centred on DIVIDE, running out of the logo like a continuation of the word
big = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(big)
x0 = (lx + logo.width + 38) * SS; x1 = (W - 64) * SS; ry = (ly + mid_y) * SS; th = 13 * SS
prog = 0 if a.km is None else max(0, min(1, a.km / ROUTE_KM))
d.rounded_rectangle([x0, ry - th / 2, x1, ry + th / 2], radius=th / 2, fill=SAND + (95,))
xm = x0 + (x1 - x0) * prog
d.rounded_rectangle([x0, ry - th / 2, max(xm, x0 + th), ry + th / 2], radius=th / 2, fill=TERRA + (255,))
re = 14 * SS  # finish ring
d.ellipse([x1 - re, ry - re, x1 + re, ry + re], fill=NIGHT + (255,), outline=SAND + (255,), width=5 * SS)
rm = 19 * SS  # position marker
d.ellipse([xm - rm, ry - rm, xm + rm, ry + rm], fill=TERRA + (255,), outline=(255, 255, 255, 255), width=6 * SS)
big = big.resize((W, H), Image.LANCZOS); ov.alpha_composite(big)
d = ImageDraw.Draw(ov)
fl = ImageFont.truetype(INTER_B, 17); fk = ImageFont.truetype(INTER_XB, 21)
lab_y = ry / SS + 36
spaced(d, (x0 / SS, lab_y), "TECATE", fl, SAND + (230,), 1.5)
t = "SAN JOSÉ DEL CABO"; tw = sum(d.textlength(c, font=fl) for c in t) + 1.5 * (len(t) - 1)
spaced(d, (x1 / SS - tw, lab_y), t, fl, SAND + (230,), 1.5)
fd = ImageFont.truetype(INTER_XB, 17)
if a.km is not None:
    t = f"KM {int(a.km):,}".replace(",", ".")
    ky = ry / SS - 30 - (24 if a.day is not None else 0)
    d.text((xm / SS, ky), t, font=fk, fill=(255, 255, 255, 255), anchor="ms")
    if a.day is not None:
        t = f"DAY {a.day}"; tw = sum(d.textlength(c, font=fd) for c in t) + 2 * (len(t) - 1)
        spaced(d, (xm / SS - tw / 2, ry / SS - 30), t, fd, GOLD + (255,), 2)
ov.save(f"{tmp}/overlay.png")
# ---------- audio ----------
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.audio, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-ar", "48000", "-ac", "1", f"{tmp}/audio.wav"], check=True)
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f"{tmp}/audio.wav"]))
nframes = int(np.ceil(dur * FPS))

# ---------- equalizer ----------
raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", f"{tmp}/audio.wav", "-f", "f32le", "-"])
sig = np.frombuffer(raw, np.float32); SR, NB, win = 48000, 26, 2048
edges = np.geomspace(90, 6000, NB + 1); freqs = np.fft.rfftfreq(win, 1 / SR); hann = np.hanning(win)
mags = np.zeros((nframes, NB))
for f in range(nframes):
    c = int(f / FPS * SR); seg = sig[max(0, c - win // 2): c + win // 2]
    if len(seg) < win: seg = np.pad(seg, (0, win - len(seg)))
    sp = np.abs(np.fft.rfft(seg * hann))
    for b in range(NB):
        m = (freqs >= edges[b]) & (freqs < edges[b + 1]); mags[f, b] = sp[m].mean() if m.any() else 0
db = 20 * np.log10(mags + 1e-6); lo, hi = np.percentile(db, 30), np.percentile(db, 99.5)
lvl = np.clip((db - lo) / (hi - lo), 0, 1) ** 1.3
lvl = np.concatenate([lvl[:, ::-1], lvl], axis=1)
sm = np.zeros_like(lvl)
for f in range(nframes):
    p = sm[f - 1] if f else 0
    sm[f] = np.where(lvl[f] > p, p + (lvl[f] - p) * 0.75, p + (lvl[f] - p) * 0.25)
BH, nb = 110, sm.shape[1]; margin = 150; step = (W - 2 * margin) / nb; bw = step * 0.5
def bars(v):
    img = Image.new("RGBA", (W, BH), (0, 0, 0, 0)); dd = ImageDraw.Draw(img); cy = BH / 2
    for i, x in enumerate(v):
        h = 7 + x * (BH - 10 - 7); xx = margin + i * step + (step - bw) / 2
        dd.rounded_rectangle([xx, cy - h / 2, xx + bw, cy + h / 2], radius=bw / 2, fill=SAND + (240,))
    return img.tobytes()

# ---------- subtitles ----------
words = []
for c in json.load(open(a.words))["chunks"]:
    s, e = c["timestamp"]; e = e if e is not None else s + 0.2
    w = c["text"].strip()
    if not w: continue
    words.append({"s": s, "e": max(e, s + 0.15), "w": w})
chunks, cur = [], []
for i, w in enumerate(words):
    cur.append(w); gap = words[i + 1]["s"] - w["e"] if i + 1 < len(words) else 9
    if len(cur) >= 4 or w["w"][-1:] in ".,!?" or gap > 0.6: chunks.append(cur); cur = []
if cur: chunks.append(cur)
ts = lambda t: f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"
bgr = lambda c: f"&H00{c[2]:02X}{c[1]:02X}{c[0]:02X}&"
ev = []
for ci, ch in enumerate(chunks):
    endc = min(chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) else ch[-1]["e"] + 0.6, ch[-1]["e"] + 0.8)
    for wi, w in enumerate(ch):
        en = ch[wi + 1]["s"] if wi + 1 < len(ch) else endc
        txt = " ".join(("{\\c" + bgr(GOLD) + "}" + x["w"] + "{\\c&H00FFFFFF&}") if k == wi else x["w"] for k, x in enumerate(ch))
        ev.append(f"Dialogue: 0,{ts(w['s'])},{ts(en)},Sub,,0,0,0,,{txt}")
open(f"{tmp}/subs.ass", "w").write(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT_SUB},56,&H00FFFFFF,&H00FFFFFF,&H000B121A,&H80000000,0,0,0,0,100,100,0,0,1,3,2,2,80,80,318,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(ev) + "\n")

# ---------- render ----------
bar_y = H - 300
fc = (f"[0:v]scale={W*2}:{H*2},zoompan=z='min(1+0.00003*on,1.035)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nframes}:s={W}x{H}:fps={FPS},format=rgba[bg];"
      f"[bg][1:v]overlay=0:0[b1];[2:v]format=rgba[bars];[b1][bars]overlay=0:{bar_y},ass={tmp}/subs.ass:fontsdir={FONTDIR},format=yuv420p[v]")
cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", f"{tmp}/bg.jpg",
       "-loop", "1", "-framerate", str(FPS), "-i", f"{tmp}/overlay.png",
       "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{BH}", "-r", str(FPS), "-i", "-",
       "-i", f"{tmp}/audio.wav", "-filter_complex", fc, "-map", "[v]", "-map", "3:a",
       "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-frames:v", str(nframes), "-shortest", a.out]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for f in range(nframes): p.stdin.write(bars(sm[f]))
p.stdin.close(); p.wait()
print("done", a.out, p.returncode, f"{dur:.1f}s")
