# -*- coding: utf-8 -*-
"""Процедурное звёздное небо для финала сцены 6 (плейт f5_stars)."""
import numpy as np, os
from PIL import Image, ImageFilter

W, H = 1672, 941
rng = np.random.default_rng(777)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- фон-туманность
def fractal(shape, octaves=6, seed=1):
    r = np.random.default_rng(seed)
    out = np.zeros(shape, dtype=np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        h = max(2, shape[0] // (2 ** (octaves - o)))
        w = max(2, shape[1] // (2 ** (octaves - o)))
        n = r.random((h, w)).astype(np.float32)
        n = np.array(Image.fromarray((n * 255).astype(np.uint8)).resize(
            (shape[1], shape[0]), Image.BICUBIC), dtype=np.float32) / 255.0
        out += n * amp
        total += amp
        amp *= 0.55
    return out / total


img = np.zeros((H, W, 3), dtype=np.float32)

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
nx, ny = xx / W, yy / H

# млечный путь: диагональная полоса
band = np.exp(-((ny - 0.42 - 0.30 * (nx - 0.5)) ** 2) / (2 * 0.20 ** 2))
neb = fractal((H, W), 6, 3) ** 1.7
neb2 = fractal((H, W), 5, 9) ** 2.0
glow = band * (0.55 * neb + 0.45 * neb2)
img += np.stack([glow * 0.10, glow * 0.11, glow * 0.16], axis=2)          # холодный газ
img += np.stack([band * 0.02, band * 0.016, band * 0.024], axis=2)        # общий ореол
# тёплый пылевой след
img += np.stack([glow * 0.05, glow * 0.025, glow * 0.012], axis=2)

# ---------------------------------------------------------------------- звёзды
def splat(x, y, sigma, amp, col):
    r = int(sigma * 4) + 2
    x0, x1 = max(0, x - r), min(W, x + r + 1)
    y0, y1 = max(0, y - r), min(H, y + r + 1)
    if x0 >= x1 or y0 >= y1:
        return
    gy, gx = np.mgrid[y0:y1, x0:x1]
    k = np.exp(-(((gx - x) ** 2 + (gy - y) ** 2) / (2 * sigma ** 2))) * amp
    for c in range(3):
        img[y0:y1, x0:x1, c] += k * col[c]

N_STARS = 1500
for _ in range(N_STARS):
    x = rng.uniform(0, W); y = rng.uniform(0, H)
    b = rng.random() ** 3.4                       # распределение яркости
    dens = 0.35 + 0.65 * band[int(np.clip(y, 0, H - 1)), int(np.clip(x, 0, W - 1))]
    amp = (0.06 + 1.5 * b) * dens
    sigma = 0.55 + 1.5 * b
    t = rng.random()
    col = (np.array([0.80, 0.86, 1.00]) if t < 0.55 else
           np.array([1.00, 0.97, 0.90]) if t < 0.88 else
           np.array([1.00, 0.82, 0.62]))
    splat(int(x), int(y), sigma, amp, col)

# крупные звёзды с ореолом
for _ in range(26):
    x = int(rng.uniform(0, W)); y = int(rng.uniform(0, H))
    amp = rng.uniform(0.7, 1.5)
    splat(x, y, 1.5, amp, np.array([1.0, 1.0, 1.0]))
    splat(x, y, 5.0, amp * 0.22, np.array([0.80, 0.86, 1.0]))
    splat(x, y, 13.0, amp * 0.05, np.array([0.55, 0.62, 0.85]))

# ------------------------------------------------------------------- виньетка
vig = 1.0 - 0.55 * (((nx - 0.5) ** 2 + (ny - 0.5) ** 2) / 0.5) ** 1.25
img *= np.clip(vig, 0, 1)[:, :, None]

img = np.clip(img, 0, 1)
# мягкое свечение
base = Image.fromarray((img ** 0.92 * 255).astype(np.uint8))
halo = base.filter(ImageFilter.GaussianBlur(9))
arr = np.array(base, dtype=np.float32) + np.array(halo, dtype=np.float32) * 0.55
# зерно
arr += rng.normal(0, 3.2, arr.shape)
out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
p = os.path.join(ROOT, "images", "f5_stars.png")
os.makedirs(os.path.dirname(p), exist_ok=True)
out.save(p)
print("stars ->", p, out.size)
