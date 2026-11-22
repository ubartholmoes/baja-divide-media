#!/usr/bin/env python3
""""Terracotta" grade – the Baja Divide look.

Red-leaning warmth (not yellow), clean blacks, soft highlight roll-off with a rose tint,
calm yellows, olive greens, dusty-blue skies, rich terracotta/red, light vignette, optional grain (off).

Usage: desert_grade.py IN OUT [--strength 1.0]
Library: apply_grade(PIL.Image, strength=1.0) -> PIL.Image
"""
import sys, numpy as np, cv2
from PIL import Image

def _curve(x, pts):
    xs, ys = zip(*pts)
    return np.interp(x, xs, ys)

def apply_grade(img, strength=1.0, grain=False, vignette=True, seed=7):
    src = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    # 0) clean up sensor colour noise (blur only the chroma channels, keeps detail)
    ycc = cv2.cvtColor(src, cv2.COLOR_RGB2YCrCb)
    sig = max(1.0, src.shape[1] / 900)
    ycc[..., 1] = cv2.GaussianBlur(ycc[..., 1], (0, 0), sig)
    ycc[..., 2] = cv2.GaussianBlur(ycc[..., 2], (0, 0), sig)
    # light luma denoise only in flat areas (skies, walls), edges stay sharp
    Y = ycc[..., 0]; Yb = cv2.bilateralFilter(Y, 0, 0.04, sig * 2)
    ycc[..., 0] = Yb
    src = np.clip(cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB), 0, 1)
    a = src.copy()

    # 1) warm white balance
    a *= np.array([1.07, 0.985, 0.94], np.float32)  # red-leaning warmth, not yellow
    a = np.clip(a, 0, 1)

    # 2) tone: matte blacks, gentle S in the mids, soft highlight roll-off
    tone = [(0, 0.025), (0.12, 0.115), (0.35, 0.34), (0.5, 0.51), (0.7, 0.72), (0.88, 0.885), (1, 0.975)]
    a = _curve(a, tone)

    # 3) split tone: brown shadows, golden highlights
    L = (a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722)[..., None]
    sh = np.clip(1 - L / 0.45, 0, 1) ** 1.5
    hi = np.clip((L - 0.55) / 0.45, 0, 1) ** 1.2
    a += sh * np.array([0.028, 0.000, -0.008], np.float32)
    a += hi * np.array([0.022, 0.004, -0.010], np.float32)
    a = np.clip(a, 0, 1)

    # 4) colour: hue/sat/lum per band (HLS, H in degrees)
    hls = cv2.cvtColor(a.astype(np.float32), cv2.COLOR_RGB2HLS)
    H, Lh, S = hls[..., 0], hls[..., 1], hls[..., 2]
    bands = [  # centre, width, hue shift (deg), sat factor, lum shift
        (5, 30, 0, 1.12, 0.00),      # reds: richer
        (28, 22, -5, 1.10, 0.00),    # oranges / skin / sand -> towards terracotta
        (55, 25, -14, 0.78, -0.01),  # yellows -> orange-red, much calmer
        (110, 45, -25, 0.68, -0.02), # greens -> olive, muted
        (185, 30, +10, 0.70, -0.02), # aqua/cyan -> muted
        (220, 35, -2, 0.75, -0.03),  # blues / sky -> dusty, a bit darker
    ]
    dH = np.zeros_like(H); fS = np.ones_like(S); dL = np.zeros_like(Lh)
    for c, w, hs, sf, ls in bands:
        d = np.abs(((H - c + 180) % 360) - 180)
        wt = np.clip(1 - d / w, 0, 1) ** 1.2 * np.clip(S * 3, 0, 1)  # ignore near-greys
        dH += wt * hs; fS *= 1 + wt * (sf - 1); dL += wt * ls
    H = (H + dH) % 360
    S = np.clip(S * fS * 0.97, 0, 1)
    Lh = np.clip(Lh + dL, 0, 1)
    a = cv2.cvtColor(np.dstack([H, Lh, S]).astype(np.float32), cv2.COLOR_HLS2RGB)

    # 5) soft vignette
    if vignette:
        h, w = a.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
        a *= (1 - 0.12 * np.clip((r - 0.45) / 0.55, 0, 1) ** 1.6)[..., None]

    # blend with original by strength
    a = src + (a - src) * strength

    # 6) optional film grain (off by default: shows as noise in skies after Instagram compression)
    if grain:
        rng = np.random.default_rng(seed)
        h, w = a.shape[:2]
        n = rng.normal(0, 1, (h, w)).astype(np.float32)
        n = cv2.GaussianBlur(n, (0, 0), max(0.6, w / 2400))
        n = n / (n.std() + 1e-6) * 0.012 * strength
        a += n[..., None]

    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))

if __name__ == "__main__":
    try:
        import pillow_heif; pillow_heif.register_heif_opener()
    except ImportError:
        pass
    from PIL import ImageOps
    s = float(sys.argv[sys.argv.index("--strength") + 1]) if "--strength" in sys.argv else 1.0
    im = ImageOps.exif_transpose(Image.open(sys.argv[1])).convert("RGB")
    apply_grade(im, s).save(sys.argv[2], quality=95)
