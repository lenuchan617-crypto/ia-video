"""
build.py — сборка 10-секундного ролика «ЗОМБИ-АПОКАЛИПСИС».
5 сцен, полностью процедурные: туман, силуэты, оптика, зерно.
"""
import os
import sys
import math
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import *  # noqa
import engine
import audio

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(OUT_DIR, "work")
os.makedirs(WORK, exist_ok=True)

HOR = 0.615 * RH   # линия горизонта на полотне

IMPACTS = [5.55, 5.95, 6.32, 6.66, 6.95, 7.20, 7.42]
CUTS = [2.60, 5.00, 7.60, 8.60]


# ══════════════════════════════════════════════════════════════════════════
#  общая «визуальная грамматика»: туманный город, мокрый асфальт, силуэты
# ══════════════════════════════════════════════════════════════════════════
ROAD_RGB = RW, RH


def skyline_layer(rng, base_h, col, hmax=0.30, seed=None, gap=6, windows=False,
                  detail=True):
    """Слой руин: тёмные силуэты с окнами и обломками. RGB + маска."""
    a = Image.new("L", (RW, RH), 0)
    w = Image.new("RGBA", (RW, RH), (0, 0, 0, 0))
    d = ImageDraw.Draw(a)
    dw = ImageDraw.Draw(w)
    base = int(base_h * RH)
    x = -60
    while x < RW * 1.0 + 80:
        bw = int(rng.integers(45, 165))
        bh = int(rng.integers(int(hmax * RH * 0.15), int(hmax * RH)))
        top = base - bh
        r = rng.random()
        if r < 0.42:
            d.rectangle([x, top, x + bw, base + 8], fill=255)
        elif r < 0.78:
            d.polygon([(x, base + 8), (x, top + bh * 0.58),
                       (x + bw * 0.30, top), (x + bw * 0.52, top + bh * 0.50),
                       (x + bw * 0.78, top + bh * 0.22),
                       (x + bw, top + bh * 0.68), (x + bw, base + 8)], fill=255)
        else:
            d.rectangle([x, top + bh * 0.45, x + bw, base + 8], fill=255)
            d.polygon([(x + bw * 0.1, top + bh * 0.45), (x + bw * 0.4, top),
                       (x + bw * 0.55, top + bh * 0.45)], fill=255)
        if detail and r < 0.42:
            # обломки на крыше
            for _ in range(int(rng.integers(0, 3))):
                bx = x + rng.uniform(0, max(1, bw - 20))
                bhh = rng.uniform(6, 26)
                d.rectangle([bx, top - bhh, bx + rng.uniform(6, 20), top + 3], fill=255)
        if detail and r < 0.42:
            # антенна
            if rng.random() < 0.35:
                axx = x + rng.uniform(10, max(11, bw - 10))
                d.line([(axx, top), (axx, top - rng.uniform(20, 70))], fill=255, width=3)
        if detail and windows:
            # окна
            if True:
                for wy in np.arange(top + 18, base - 14, 26):
                    for wx in np.arange(x + 10, x + bw - 12, 22):
                        if rng.random() < 0.07:
                            dw.rectangle([wx, wy, wx + 8, wy + 11],
                                         fill=(255, int(rng.uniform(168, 216)),
                                               int(rng.uniform(110, 150)), 240))
        x += bw + int(rng.integers(-gap, gap + 26))
    mask = np.asarray(a, F32) / 255.0
    rgb = np.zeros((RH, RW, 3), F32) + np.array(col, F32)
    # немного блика сверху построек
    rgb += (mask * (1 - np.roll(mask, 5, axis=0)))[..., None] * np.array(
        [0.25, 0.27, 0.25], F32) * 0.55
    wa = np.asarray(w, F32) / 255.0
    rgb = rgb + wa[..., :3] * 1.1
    return rgb, mask


def make_road(rng, vp_x=0.50, horizon=0.612, cam_h=0.0):
    """Мокрый асфальт с разметкой, лужами и отражениями — RGBA на полотне."""
    rgba = np.zeros((RH, RW, 4), F32)
    hz = horizon * RH
    ys = np.arange(RH, dtype=F32)[:, None]
    t = np.clip((ys - hz) / (RH - hz), 0, 1)
    # цвет: у горизонта светлый (дымка), к камере — почти чёрный
    top = np.array([0.24, 0.26, 0.245], F32)
    mid = np.array([0.13, 0.145, 0.14], F32)
    bot = np.array([0.028, 0.032, 0.033], F32)
    col = np.zeros((RH, RW, 3), F32)
    tt = t ** 0.62
    col[:] = top[None, None, :] * (1 - tt[..., None]) + mid[None, None, :] * tt[..., None]
    tt2 = np.clip((t - 0.45) / 0.55, 0, 1) ** 1.2
    col = col * (1 - tt2[..., None]) + bot[None, None, :] * tt2[..., None]
    rgba[..., :3] = col
    rgba[..., 3] = (ys > hz).astype(F32) * np.ones((1, RW), F32)
    # мягкий переход у горизонта
    soft = np.exp(-((ys - hz) / 26.0) ** 2) * (ys > hz - 26)
    rgba[..., 3] = np.clip(rgba[..., 3] + soft, 0, 1)

    im = Image.fromarray((np.clip(rgba[..., :3], 0, 1) * 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(im, "RGBA")
    vx = vp_x * RW
    # мокрые блики на асфальте (вертикальные полосы от света у горизонта)
    for i in range(26):
        p = rng.uniform(0.06, 0.85)
        y0 = hz + (RH - hz) * p
        y1 = y0 + (RH - hz) * rng.uniform(0.02, 0.10) * (1 - p)
        cx = vx + rng.uniform(-0.42, 0.42) * RW * (p ** 1.3)
        w = max(1, int(rng.uniform(2, 9) * (0.3 + p)))
        d.line([(cx, y0), (cx + rng.uniform(-4, 4), y1)],
               fill=(190, 200, 188, int(16 + 30 * (1 - p))), width=w)
    # разметка
    for i in range(9):
        p0 = (i / 9.0) ** 1.35 * 0.98
        p1 = min(1.0, p0 + 0.055 + 0.03 * p0)
        y0 = hz + (RH - hz) * p0
        y1 = hz + (RH - hz) * p1
        w0 = max(1, 6 * p0)
        d.line([(vx, y0), (vx, y1)], fill=(196, 190, 168, int(150)), width=int(w0))
    # лужи (отражают светлое небо)
    for i in range(30):
        p = rng.uniform(0.10, 1.0)
        y = hz + (RH - hz) * (p ** 1.7)
        cx = vx + rng.uniform(-0.42, 0.42) * RW * p
        w = rng.uniform(60, 340) * p ** 1.2
        h = rng.uniform(8, 46) * p
        a = int(28 + 60 * p)
        d.ellipse([cx - w / 2, y - h / 2, cx + w / 2, y + h / 2],
                  fill=(140, 155, 148, int(a * 0.45)))
    # трещины и мусор
    for i in range(120):
        p = rng.uniform(0.05, 1.0)
        y = hz + (RH - hz) * (p ** 1.55)
        cx = vx + rng.uniform(-0.55, 0.55) * RW * p
        L = rng.uniform(20, 130) * p
        d.line([(cx, y), (cx + rng.uniform(-L, L), y + rng.uniform(-6, 6) * p)],
               fill=(8, 10, 10, 120), width=max(1, int(3 * p)))
    arr = np.asarray(im, F32) / 255.0
    arr = arr * (0.92 + 0.16 * fbm(RH, RW, 26, np.random.default_rng(7), octaves=4)[..., None])
    rgba[..., :3] = arr
    return rgba


def car_sprite(rng, scale, flip=False, bus=False):
    """Силуэт разбитой машины (сбоку) с ободком света сверху."""
    S = 3
    if bus:
        w, h = 620, 260
        pts = [(0, 0.28), (0.03, 0.10), (0.30, 0.02), (0.72, 0.0), (0.96, 0.08),
               (1.0, 0.30), (1.0, 0.85), (0.96, 1.0), (0.05, 1.0), (0.0, 0.92)]
        wheels = [(0.20, 1.0), (0.74, 1.0)]
    else:
        w, h = 460, 150
        pts = [(0, 0.55), (0.04, 0.30), (0.20, 0.26), (0.32, 0.04),
               (0.62, 0.02), (0.74, 0.24), (0.92, 0.30), (0.99, 0.50),
               (1.0, 0.88), (0.05, 0.90)]
        wheels = [(0.22, 0.92), (0.78, 0.92)]
    Wd, Hd = int(w * scale), int(h * scale)
    m = Image.new("L", (Wd * S, Hd * S), 0)
    d = ImageDraw.Draw(m)
    d.polygon([(x * Wd * S, y * Hd * S) for x, y in pts], fill=255)
    for (wx, wy) in wheels:
        r = Hd * S * (0.30 if not bus else 0.22)
        cx, cy = wx * Wd * S, wy * Hd * S - r * 0.15
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    m = m.resize((Wd, Hd), Image.LANCZOS)
    alpha = np.asarray(m, F32) / 255.0
    if flip:
        alpha = alpha[:, ::-1]
    g = np.gradient(alpha)
    gy, gx = g
    nz = np.sqrt(gx ** 2 + gy ** 2) + 1e-6
    ny = gy / nz
    edge = np.exp(-(np.abs(np.clip(alpha - 0.5, -1, 1) * 0 + (alpha - 0.35)) / 0.45) ** 2)
    body = np.array([0.014, 0.018, 0.019], F32)[None, None, :] * np.ones((Hd, Wd, 1), F32)
    rim = np.clip(-ny, 0, 1) * np.clip(alpha, 0, 1)
    body = body + rim[..., None] * np.array([0.55, 0.60, 0.56], F32) * 0.55
    # блики на крыше
    body = body + (np.clip(-ny, 0, 1) ** 6)[..., None] * np.array([0.55, 0.58, 0.54], F32) * 0.7
    out = np.dstack([np.clip(body, 0, 1), np.clip(alpha, 0, 1)])
    # разбитые стёкла: сколы по контуру
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


def street_lamp(rng, scale, flip=False):
    S = 3
    w, h = 200, 760
    Wd, Hd = int(w * scale), int(h * scale)
    m = Image.new("L", (Wd * S, Hd * S), 0)
    d = ImageDraw.Draw(m)
    d.polygon([(0.46 * Wd * S, 1.0 * Hd * S), (0.54 * Wd * S, 1.0 * Hd * S),
               (0.52 * Wd * S, 0.10 * Hd * S), (0.48 * Wd * S, 0.10 * Hd * S)], fill=255)
    d.polygon([(0.48 * Wd * S, 0.14 * Hd * S), (0.86 * Wd * S, 0.06 * Hd * S),
               (0.88 * Wd * S, 0.10 * Hd * S), (0.50 * Wd * S, 0.18 * Hd * S)], fill=255)
    d.rectangle([0.82 * Wd * S, 0.03 * Hd * S, 0.98 * Wd * S, 0.10 * Hd * S], fill=255)
    m = m.resize((Wd, Hd), Image.LANCZOS)
    alpha = np.asarray(m, F32) / 255.0
    if flip:
        alpha = alpha[:, ::-1]
    gy, gx = np.gradient(alpha)
    nz = np.sqrt(gx ** 2 + gy ** 2) + 1e-6
    ny = gy / nz
    body = np.array([0.012, 0.016, 0.017], F32)[None, None, :] * np.ones((Hd, Wd, 1), F32)
    body = body + np.clip(-ny, 0, 1)[..., None] * np.array([0.45, 0.50, 0.47], F32) * 0.6
    # мёртвая лампа: чуть тлеет
    out = np.dstack([np.clip(body, 0, 1), np.clip(alpha, 0, 1)])
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


# ══════════════════════════════════════════════════════════════════════════
#  СЦЕНА 1 — мёртвый город, туман, «ДЕНЬ 47»
# ══════════════════════════════════════════════════════════════════════════
class CityScene:
    dur = 2.60
    grade = dict(exposure=1.02, contrast=1.12, saturation=0.68,
                 lift=(0.010, 0.018, 0.024), high=(1.10, 1.01, 0.86), bloom=0.30)

    def __init__(self):
        rng = np.random.default_rng(11)
        self.sky = self._sky()
        self.far = skyline_layer(rng, 0.612, (0.075, 0.092, 0.094), hmax=0.20, gap=22, windows=True)
        self.mid = skyline_layer(rng, 0.625, (0.030, 0.038, 0.040), hmax=0.14, gap=10, windows=True)
        self.near = skyline_layer(rng, 0.640, (0.014, 0.018, 0.019), hmax=0.085, gap=-4)
        self.road = make_road(rng, vp_x=0.50, horizon=0.612)
        self.fogA = fog_texture(rng, 820, 320, 4, contrast=0.55, aniso=3.0)
        self.fogB = fog_texture(rng, 900, 340, 6, contrast=0.75, aniso=2.6)
        self.fogC = fog_texture(rng, 640, 240, 11, contrast=0.95, aniso=2.2)
        # реквизит на дороге (рисуем в отдельный слой полотна)
        self.props = np.zeros((RH, RW, 4), F32)
        self.parts = Particles(rng, 60, y_range=(0.30, 0.95), size=(0.6, 1.7),
                               speed=(0.004, 0.02), drift=0.8,
                               color=(0.92, 0.86, 0.70), brightness=(0.04, 0.26))
        self.txt = text_img("ДЕНЬ 47", 46, "#e6dccb", tracking=0.40)
        self.txt_small = text_img("ЗОНА КАРАНТИНА · МОСКВА", 14, "#a8b0a6", tracking=0.58)

    def _sky(self):
        sky = vgrad(RW, RH, [(0.00, "#05090b"), (0.16, "#0a1216"),
                             (0.33, "#152428"), (0.46, "#2c4142"),
                             (0.545, "#5c7472"), (0.585, "#93a79c"),
                             (0.604, "#bcc6b6"), (0.620, "#66756e"),
                             (0.665, "#1d2828"), (1.00, "#05090a")])
        glow = radial(RW, RH, RW * 0.50, 0.585 * RH, RW * 0.55, RH * 0.15, 1.8)
        return screen(sky, np.array([1.0, 0.93, 0.76], F32) * glow[..., None], 0.55)

    def _props(self, rng):
        layer = np.zeros((RH, RW, 4), F32)
        hz = 0.612 * RH

        def place(img, cx, base_y, alpha_mul=1.0):
            a = np.asarray(img, F32) / 255.0
            canvas = layer[..., :3]
            tmp = np.zeros((a.shape[0], a.shape[1], 3), F32)
            x0 = int(cx - a.shape[1] / 2)
            y0 = int(base_y - a.shape[0])
            ch, cw = canvas.shape[:2]
            sx0, sy0 = max(0, x0), max(0, y0)
            sx1, sy1 = min(cw, x0 + a.shape[1]), min(ch, y0 + a.shape[0])
            if sx0 >= sx1 or sy0 >= sy1:
                return
            ox_, oy_ = sx0 - x0, sy0 - y0
            hh, ww = sy1 - sy0, sx1 - sx0
            sub = a[oy_:oy_ + hh, ox_:ox_ + ww]
            canvas[sy0:sy1, sx0:sx1] = over(canvas[sy0:sy1, sx0:sx1], sub[..., :3],
                                           sub[..., 3:4] * alpha_mul)
            layer[sy0:sy1, sx0:sx1, 3] = np.maximum(layer[sy0:sy1, sx0:sx1, 3],
                                                   sub[..., 3] * alpha_mul)

        # тушa автобуса на боку — средний план
        bus = car_sprite(rng, 0.62, flip=False, bus=True)
        place(bus, RW * 0.27, hz + (RH - hz) * 0.30)
        # машины
        place(car_sprite(rng, 0.34, flip=True), RW * 0.66, hz + (RH - hz) * 0.20)
        place(car_sprite(rng, 0.55, flip=False), RW * 0.72, hz + (RH - hz) * 0.44)
        place(car_sprite(rng, 0.95, flip=True), RW * 0.16, hz + (RH - hz) * 0.78)
        place(car_sprite(rng, 1.30, flip=False), RW * 0.90, hz + (RH - hz) * 1.06)
        # фонарь
        place(street_lamp(rng, 0.48, flip=False), RW * 0.60, hz + (RH - hz) * 0.34)
        place(street_lamp(rng, 1.15, flip=True), RW * 0.03, hz + (RH - hz) * 1.12)
        return layer

    def render(self, t):
        p = t / self.dur
        z = 1.0 + 0.05 * ease_out(p)
        dx = 10 - 20 * p
        dy = 4 - 6 * p
        img = to_arr(view(to_img(self.sky), z, dx, dy, 0.08))

        # дальние руины — тёмные силуэты в дымке
        for (rgb, m), par, alpha_k in ((self.far, 0.16, 0.92), (self.mid, 0.28, 1.0),
                                       (self.near, 0.40, 1.0)):
            lay = view(Image.fromarray((np.dstack([rgb, m[..., None]]) * 255).astype(np.uint8), "RGBA"),
                       z, dx, dy, par)
            lr, la = rgba_arrays(lay)
            img = over(img, lr, la * alpha_k)
            if par < 0.2:
                img = over(img, lr * 0.9, la * 0.10)

        # светящаяся стена тумана у горизонта
        n = np.roll(self.fogA, int(t * 18) % self.fogA.shape[1], axis=1)
        tex = np.asarray(Image.fromarray((n * 255).astype(np.uint8), "L").resize((W, H),
                                                                              Image.BICUBIC), F32) / 255.0
        yv = (np.arange(H, dtype=F32) / H)[:, None]
        band = np.exp(-((yv - 0.600) / 0.095) ** 2)
        img = over(img, np.array([0.60, 0.64, 0.58], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   np.clip((0.20 + 0.60 * tex) * band * 0.42, 0, 0.62)[..., None])

        # дорога
        road = view(Image.fromarray((np.clip(self.road, 0, 1) * 255).astype(np.uint8), "RGBA"),
                    z, dx, dy, 0.66)
        rr, ra = rgba_arrays(road)
        img = over(img, rr, ra)

        # одинокие зомби в тумане на дороге
        zs = zombie_atlas()
        for k, (fx, fd, var) in enumerate(((0.30, 0.30, 1), (0.42, 0.34, 4),
                                            (0.68, 0.22, 7), (0.58, 0.52, 2))):
            spr = zs[var][(k + int(t * 3)) % 4]
            hpx = int(48 + 150 * fd)
            sc = hpx / spr.height
            s2 = spr.resize((max(3, int(spr.width * sc)), hpx), Image.LANCZOS)
            a = np.asarray(s2, F32) / 255.0
            # куда ставим: чуть выше дорожного полотна
            px = int(W * fx + int(t * 6 * (k + 1)) % 40 + 8 * math.sin(t + k))
            py = int(H * (0.585 + 0.075 * fd))
            fogk = float(np.clip(0.85 - fd * 0.8, 0, 1))
            rgbm = a[..., :3] * (1 - fogk) + np.array([0.52, 0.55, 0.51], F32) * fogk
            blit_arr(img, np.dstack([rgbm, a[..., 3] * (0.45 + 0.5 * (1 - fogk))]),
                     px, py - hpx)

        # туман по земле
        n2 = np.roll(self.fogB, -int(t * 30) % self.fogB.shape[1], axis=1)
        tex2 = np.asarray(Image.fromarray((n2 * 255).astype(np.uint8), "L").resize((W, H),
                                                                                Image.BICUBIC), F32) / 255.0
        band2 = np.clip((yv - 0.66) / 0.34, 0, 1) ** 1.2
        img = over(img, np.array([0.40, 0.44, 0.40], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   np.clip((0.06 + 0.52 * tex2) * band2 * 0.55, 0, 0.85)[..., None])
        n3 = np.roll(self.fogC, int(t * 46) % self.fogC.shape[1], axis=1)
        tex3 = np.asarray(Image.fromarray((n3 * 255).astype(np.uint8), "L").resize((W, H),
                                                                                Image.BICUBIC), F32) / 255.0
        band3 = np.clip((yv - 0.88) / 0.14, 0, 1) ** 1.1
        img = over(img, np.array([0.20, 0.23, 0.22], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   np.clip((0.14 + 0.55 * tex3) * band3 * 0.80, 0, 0.92)[..., None])

        img = god_rays(img, W * 0.50, H * 0.60, n=9, length=0.95, spread=0.55,
                       strength=0.07, color=(1.0, 0.94, 0.80), t=t, angle=0.30)
        # тёмные массы по краям кадра — эффект «смотрим из-за угла»
        yv2 = (np.arange(H, dtype=F32) / H)[:, None]
        xv2 = (np.arange(W, dtype=F32) / W)[None, :]
        left = np.clip((0.20 - xv2) / 0.20, 0, 1) ** 1.4
        right = np.clip((xv2 - 0.82) / 0.18, 0, 1) ** 1.4
        fore = np.clip(left + right, 0, 1) * np.clip((yv2 - 0.10) / 0.55, 0, 1) ** 0.5
        img = img * (1 - fore[..., None] * 0.92)

        img = self.parts.draw(img, t, alpha=0.45)

        fade = smoothstep(0.20, 0.75, t) * (1 - smoothstep(2.32, 2.58, t))
        if fade > 0.003:
            yy = H * 0.40 - 4 * (1 - fade)
            img = paste_center(img, self.txt, W / 2, yy, opacity=min(1.0, fade * 1.3),
                               glow=0.75, glow_color=(0.92, 0.96, 0.86), glow_blur=26)
            img = paste_center(img, self.txt_small, W / 2, yy + 58,
                               opacity=fade * 0.8)
        return np.clip(img, 0, 1)


# ══════════════════════════════════════════════════════════════════════════
#  СЦЕНА 2 — орда выходит из тумана
# ══════════════════════════════════════════════════════════════════════════
ZSPR = None


def zombie_atlas():
    global ZSPR
    if ZSPR is None:
        ZSPR = [[zombie_rgba(620, seed=s * 7 + 3, phase=p / 4.0) for p in range(4)]
                for s in range(9)]
    return ZSPR


class HordeScene:
    """Орда выходит из тумана: контровой свет, глубина, объёмные лучи."""
    dur = 2.40
    grade = dict(exposure=1.03, contrast=1.14, saturation=0.72,
                 lift=(0.012, 0.018, 0.024), high=(1.10, 1.00, 0.86), bloom=0.26)

    def __init__(self):
        rng = np.random.default_rng(2023)
        self.zspr = zombie_atlas()
        n = 46
        self.n = n
        self.var = rng.integers(0, 9, n)
        d = rng.random(n)
        self.depth0 = np.where(d < 0.60, rng.random(n) ** 2.0 * 0.40,
                               rng.random(n) * 0.9 + 0.06)
        self.x = rng.uniform(-0.06, 1.06, n)
        self.speed = rng.uniform(0.018, 0.055, n)
        self.ph = rng.random(n)
        self.hw = rng.uniform(0.86, 1.14, n)
        self.far = self._skyline(rng)
        self.sky = self._sky()
        self.fogA = fog_texture(rng, 760, 300, 5, contrast=0.5, aniso=2.2)
        self.fogB = fog_texture(rng, 900, 340, 4, contrast=0.7, aniso=2.8)
        self.fogC = fog_texture(rng, 640, 240, 9, contrast=0.9, aniso=2.0)
        self.parts = Particles(rng, 40, y_range=(0.35, 0.95), size=(0.5, 1.4),
                               speed=(0.008, 0.03), drift=0.55,
                               color=(0.95, 0.72, 0.45), brightness=(0.04, 0.20))

    def _sky(self):
        sky = vgrad(RW, RH, [(0.00, "#04080b"), (0.18, "#08131a"),
                             (0.34, "#12232a"), (0.46, "#26403f"),
                             (0.545, "#5d7a72"), (0.585, "#93a89c"),
                             (0.605, "#b6c2b4"), (0.622, "#5d6c66"),
                             (0.665, "#1b2727"), (1.00, "#05090a")])
        glow = radial(RW, RH, RW * 0.50, 0.585 * RH, RW * 0.62, RH * 0.16, 1.8)
        sky = screen(sky, np.array([1.0, 0.92, 0.74], F32) * glow[..., None], 0.55)
        return sky

    def _skyline(self, rng):
        a = Image.new("L", (RW, RH), 0)
        d = ImageDraw.Draw(a)
        base = int(0.612 * RH)
        x = -50
        while x < RW + 60:
            w = int(rng.integers(50, 170))
            h = int(rng.integers(24, 210))
            if rng.random() < 0.45:
                d.rectangle([x, base - h, x + w, base + 6], fill=255)
            else:
                d.polygon([(x, base + 6), (x, base - h * 0.42),
                           (x + w * 0.30, base - h * 0.90),
                           (x + w * 0.52, base - h * 0.50),
                           (x + w * 0.78, base - h * 0.75),
                           (x + w, base - h * 0.30), (x + w, base + 6)], fill=255)
            for k in range(int(rng.integers(0, 2))):
                bx = x + rng.uniform(0, max(1, w - 24))
                bh = rng.uniform(8, 30)
                d.rectangle([bx, base - h - bh, bx + rng.uniform(6, 20), base - h + 3],
                            fill=255)
            x += w + int(rng.integers(-6, 30))
        mask = np.asarray(a, F32) / 255.0
        rgb = np.zeros((RH, RW, 3), F32) + np.array([0.030, 0.038, 0.038], F32)
        return rgb, mask

    @staticmethod
    def _scroll(tex, t, sx, sy=0):
        n = np.roll(tex, int(t * sx) % tex.shape[1], axis=1)
        return np.roll(n, int(t * sy) % tex.shape[0], axis=0)

    def render(self, t):
        p = t / self.dur
        z = 1.0 + 0.075 * ease_out(p)
        dx = -8 + 14 * p
        dy = 3

        img = to_arr(view(to_img(self.sky), z, dx, dy, 0.10))

        rgb, m = self.far
        far = view(Image.fromarray((np.dstack([rgb, m[..., None]]) * 255).astype(np.uint8), "RGBA"),
                   z, dx, dy, 0.32)
        fr, fa = rgba_arrays(far)
        img = over(img, fr, fa * 0.92)

        # 1. светящаяся стена тумана у горизонта
        n = self._scroll(self.fogA, t, 26, 8)
        tex = np.asarray(Image.fromarray((n * 255).astype(np.uint8), "L").resize((W, H),
                                                                                Image.BICUBIC), F32) / 255.0
        yv = np.arange(H, dtype=F32) / H
        band = np.exp(-((yv - 0.585) / 0.115) ** 2)[:, None]
        a = np.clip((0.35 + 0.85 * tex) * band * 0.95, 0, 0.97)
        img = over(img, np.array([0.66, 0.70, 0.64], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   a[..., None])

        # 2. объёмные лучи из-за горизонта
        img = god_rays(img, W * 0.50, H * 0.56, n=11, length=1.05, spread=0.62,
                       strength=0.10, color=(1.0, 0.90, 0.72), t=t, angle=0.28)

        # тёмная земля
        yv2 = (np.arange(H, dtype=F32) / H)[:, None]
        ground = np.clip((yv2 - 0.615) / 0.385, 0, 1) ** 0.75
        img = img * (1 - ground[..., None] * 0.92) + ground[..., None] * np.array([0.045, 0.052, 0.050], F32) * 0.92
        # отражённый свет от тумана на земле у горизонта
        gl = np.exp(-((yv2 - 0.615) / 0.035) ** 2)
        img = screen(img, np.array([0.30, 0.32, 0.28], F32) * gl[..., None], 0.55)

        # 3. орда
        order = np.argsort(self.depth0)
        hz = 0.612 * H
        for i in order:
            d = float((self.depth0[i] + self.speed[i] * t) % 1.0)
            base_y = hz + (H * 1.04 - hz) * (d ** 2.4)
            hpx = (18 + 560 * (d ** 1.7)) * self.hw[i]
            # ближние уходят к краям кадра
            edge_pull = (self.x[i] - 0.5) * 1.35 + 0.5
            xx0 = lerp(self.x[i], edge_pull, d ** 1.5)
            xpx = W * (xx0 * 1.20 - 0.10) + dx * (0.2 + 0.8 * d)
            xpx += 18 * math.sin(t * 0.7 + self.ph[i] * 6.28) * d
            ypx = base_y + 5 * math.sin(t * 4.4 + self.ph[i] * 6.28) * d
            scale = hpx / 620.0
            spr = self.zspr[self.var[i]][int(t * 3.2 + self.ph[i] * 4) % 4]
            sw = max(2, int(spr.width * scale))
            sh = max(2, int(spr.height * scale))
            if sh < 8:
                continue
            cx0 = xpx - sw / 2
            if cx0 > W - sw * 0.08 or cx0 + sw < sw * 0.08:
                continue
            if sh > 26 and xpx < sw * 0.30 or sh > 26 and xpx > W - sw * 0.30:
                continue
            s2 = spr.resize((sw, sh), Image.LANCZOS if sh < 360 else Image.BILINEAR)
            # глубина резкости: ближние мягче
            blur = 0.0 if d < 0.55 else (d - 0.55) * 9.0
            s2 = soft_dof(s2, blur)
            a2 = np.asarray(s2, F32) / 255.0
            fogk = float(np.clip(1.0 - d ** 1.2, 0.0, 1.0)) * 0.90
            rgbm = a2[..., :3] * (1 - fogk) + np.array([0.46, 0.50, 0.46], F32) * fogk
            blit_arr(img, np.dstack([rgbm, a2[..., 3] * (0.62 + 0.38 * (1 - fogk))]),
                     int(xpx - sw / 2), int(ypx - sh))

        # 4. нижний туман — ноги тонут
        n2 = self._scroll(self.fogB, t, 42, 6)
        tex2 = np.asarray(Image.fromarray((n2 * 255).astype(np.uint8), "L").resize((W, H),
                                                                                 Image.BICUBIC), F32) / 255.0
        band2 = np.clip((yv - 0.70) / 0.30, 0, 1)[:, None] ** 1.1
        img = over(img, np.array([0.42, 0.46, 0.41], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   np.clip((0.25 + 0.8 * tex2) * band2 * 0.95, 0, 0.97)[..., None])
        n3 = self._scroll(self.fogC, t + 3, 66, 10)
        tex3 = np.asarray(Image.fromarray((n3 * 255).astype(np.uint8), "L").resize((W, H),
                                                                                 Image.BICUBIC), F32) / 255.0
        band3 = np.clip((yv - 0.86) / 0.16, 0, 1)[:, None]
        img = over(img, np.array([0.18, 0.20, 0.19], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   np.clip((0.25 + 0.7 * tex3) * band3 * 0.9, 0, 0.95)[..., None])

        img = self.parts.draw(img, t, alpha=0.5)
        return np.clip(img, 0, 1)


# ══════════════════════════════════════════════════════════════════════════
#  СЦЕНА 3 — переулок: орда идёт из туманного проёма на камеру
# ══════════════════════════════════════════════════════════════════════════
class DoorScene:
    dur = 2.60
    grade = dict(exposure=1.04, contrast=1.16, saturation=0.74,
                 lift=(0.010, 0.014, 0.018), high=(1.14, 1.00, 0.84), bloom=0.30)
    CX, CY = 0.50, 0.555          # центр проёма
    OW, OH = 0.085, 0.155         # полуразмеры проёма (доли кадра)

    def __init__(self):
        rng = np.random.default_rng(41)
        self.zspr = zombie_atlas()
        self.fogA = fog_texture(rng, 700, 300, 3, contrast=0.4, aniso=2.2)
        self.fogB = fog_texture(rng, 800, 320, 5, contrast=0.75, aniso=2.0)
        self.walltex = fbm(H, W, 55, np.random.default_rng(6), octaves=5)
        self.grain = fbm(H, W, 120, np.random.default_rng(8), octaves=4)
        self.dust = Particles(rng, 170, y_range=(0.1, 1.0), size=(0.5, 1.7),
                              speed=(0.002, 0.010), drift=0.9,
                              color=(1.0, 0.90, 0.72), brightness=(0.05, 0.36))
        n = 20
        self.var = rng.integers(0, 9, n)
        self.z0 = rng.random(n) ** 1.5
        self.x0 = rng.uniform(-1.0, 1.0, n)
        self.sp = rng.uniform(0.025, 0.065, n)
        self.ph = rng.random(n)
        self.corridor = self._corridor()

    def _rect(self):
        cx, cy = self.CX * W, self.CY * H
        hw, hh = self.OW * W, self.OH * H
        return cx - hw, cy - hh, cx + hw, cy + hh

    def _corridor(self):
        """Коридор: стены, потолок, пол + перспективные рёбра."""
        im = Image.new("RGB", (W, H), (6, 7, 7))
        d = ImageDraw.Draw(im, "RGBA")
        l, tp, r, bt = self._rect()

        wall_col = (26, 26, 24, 255)
        d.polygon([(0, 0), (l, tp), (l, bt), (0, H)], fill=wall_col)          # левая стена
        d.polygon([(W, 0), (r, tp), (r, bt), (W, H)], fill=(30, 30, 27, 255))  # правая
        d.polygon([(0, 0), (l, tp), (r, tp), (W, 0)], fill=(14, 15, 15, 255))  # потолок
        d.polygon([(0, H), (l, bt), (r, bt), (W, H)], fill=(20, 21, 20, 255))  # пол

        # перспективные рёбра (дверные проёмы вдоль стен)
        n_steps = 9
        for k in range(n_steps):
            f = (k / n_steps) ** 1.55
            lx = l * f
            rx = W - (W - r) * f
            ty = tp * f
            by = H - (H - bt) * f
            a = int(150 * (1 - f) + 60)
            d.line([(lx, ty), (lx, by)], fill=(8, 9, 9, a), width=max(1, int(7 * (1 - f))))
            d.line([(rx, ty), (rx, by)], fill=(8, 9, 9, a), width=max(1, int(7 * (1 - f))))
            d.line([(lx, ty), (rx, ty)], fill=(6, 7, 7, a), width=max(1, int(5 * (1 - f))))
            d.line([(lx, by), (rx, by)], fill=(6, 7, 7, a), width=max(1, int(5 * (1 - f))))
            # окна/двери — тёплые пятна
            if k % 2 == 0 and k < 7:
                wx = lx + (rx - lx) * 0.02
                d.rectangle([lx + 6, ty + (by - ty) * 0.35, lx + 18, ty + (by - ty) * 0.55],
                            fill=(120, 96, 60, int(70 * (1 - f) + 20)))
        arr = np.asarray(im, F32) / 255.0
        # фактура стен
        arr = arr * (0.75 + 0.6 * self.walltex[..., None])
        return arr

    def render(self, t):
        p = t / self.dur
        l, tp, r, bt = self._rect()
        cx, cy = (l + r) / 2, (tp + bt) / 2
        z = 1.0 + 0.05 * ease_out(p)
        dx = 4 * math.sin(t * 0.8)
        dy = 2

        img = to_arr(view(to_img(self.corridor), z, dx, dy, 0.75))
        # сдвиг после кропа/зума — держим проём на месте
        l2, tp2, r2, bt2 = self._rect()
        l2 += (z - 1) * -W * 0.5 + dx * 0.75 + W * 0.5
        r2 += (z - 1) * -W * 0.5 + dx * 0.75 + W * 0.5

        # ── проём: яркий свет в конце ──
        opening = Image.new("L", (W, H), 0)
        od = ImageDraw.Draw(opening)
        od.rectangle([l, tp, r, bt], fill=255)
        om = np.asarray(opening.filter(ImageFilter.GaussianBlur(9)), F32) / 255.0
        om = np.clip(om * 0.92, 0, 1) * (0.82 + 0.18 * self.grain)
        glow = radial(W, H, cx, cy, W * 0.22, H * 0.34, 1.4)
        img = over(img, np.array([0.94, 0.88, 0.74], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   om[..., None] * 0.95)
        img = screen(img, np.array([1.0, 0.90, 0.68], F32) * glow[..., None], 0.90)

        # ── орда из проёма ──
        order = np.argsort(self.z0)
        for i in order:
            zz = float((self.z0[i] + self.sp[i] * t) % 1.0)
            depth = 0.05 + 0.95 * zz ** 1.6
            hpx = 34 + 560 * (depth ** 2.2)
            spr = self.zspr[self.var[i]][int(t * 3.4 + self.ph[i] * 4) % 4]
            sc = hpx / spr.height
            sw, sh = max(2, int(spr.width * sc)), max(2, int(spr.height * sc))
            if sh < 10:
                continue
            s2 = spr.resize((sw, sh), Image.LANCZOS if sh < 320 else Image.BILINEAR)
            if depth > 0.5:
                s2 = s2.filter(ImageFilter.GaussianBlur((depth - 0.5) * 6))
            a = np.asarray(s2, F32) / 255.0
            xpx = cx + self.x0[i] * W * 0.40 * depth ** 1.7
            ypx = cy + (H * 1.04 - cy) * depth ** 2.0
            fogk = float(np.clip(1.0 - depth ** 0.85, 0, 1))
            rgbm = a[..., :3] * (1 - fogk) + np.array([0.62, 0.64, 0.58], F32) * fogk
            blit_arr(img, np.dstack([rgbm, a[..., 3] * (0.72 + 0.28 * (1 - fogk))]),
                     int(xpx - sw / 2), int(ypx - sh))

        # ── объёмные лучи из проёма ──
        img = god_rays(img, cx, cy, n=15, length=1.6, spread=1.5, strength=0.115,
                       color=(1.0, 0.94, 0.80), t=t, angle=0.0)

        # ── туман: в глубине и у пола ──
        yv = (np.arange(H, dtype=F32) / H)[:, None]
        n = np.roll(self.fogA, int(t * 26) % self.fogA.shape[1], axis=1)
        tex = np.asarray(Image.fromarray((n * 255).astype(np.uint8), "L").resize(
            (W, H), Image.BICUBIC), F32) / 255.0
        band = np.exp(-((yv - self.CY) / 0.20) ** 2)
        img = over(img, np.array([0.78, 0.79, 0.72], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   np.clip((0.22 + 0.7 * tex) * band * 0.55, 0, 0.85)[..., None])
        n2 = np.roll(self.fogB, -int(t * 44) % self.fogB.shape[1], axis=1)
        tex2 = np.asarray(Image.fromarray((n2 * 255).astype(np.uint8), "L").resize(
            (W, H), Image.BICUBIC), F32) / 255.0
        band2 = np.clip((yv - 0.70) / 0.30, 0, 1) ** 1.2
        img = over(img, np.array([0.34, 0.35, 0.32], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   np.clip((0.16 + 0.7 * tex2) * band2 * 0.8, 0, 0.95)[..., None])

        img = self.dust.draw(img, t, alpha=0.8)
        edge = radial(W, H, W * 0.5, H * 0.52, W * 0.62, H * 0.75, 1.7)
        img = img * (0.45 + 0.80 * edge[..., None])
        return np.clip(img, 0, 1)


# ══════════════════════════════════════════════════════════════════════════
#  СЦЕНА 4 — выживший против орды
# ══════════════════════════════════════════════════════════════════════════
class SurvivorScene:
    dur = 1.00
    grade = dict(exposure=1.04, contrast=1.14, saturation=0.66,
                 lift=(0.010, 0.016, 0.022), high=(1.12, 1.01, 0.84), bloom=0.28)

    def __init__(self):
        rng = np.random.default_rng(77)
        self.hero = hero_sprite(760)
        self.sky = HordeScene._sky(None) if False else vgrad(RW, RH, [
            (0.00, "#04080b"), (0.18, "#08131a"), (0.34, "#12232a"),
            (0.46, "#26403f"), (0.545, "#5d7a72"), (0.585, "#93a89c"),
            (0.605, "#b6c2b4"), (0.622, "#5d6c66"), (0.665, "#1b2727"),
            (1.00, "#05090a")])
        glow = radial(RW, RH, RW * 0.50, 0.585 * RH, RW * 0.62, RH * 0.16, 1.8)
        self.sky = screen(self.sky, np.array([1.0, 0.92, 0.74], F32) * glow[..., None], 0.55)
        self.far = skyline_layer(rng, 0.615, (0.20, 0.24, 0.235), hmax=0.17, gap=16)
        self.fogA = fog_texture(rng, 800, 320, 4, contrast=0.5, aniso=2.6)
        self.fogB = fog_texture(rng, 760, 300, 7, contrast=0.8, aniso=2.4)
        self.fogC = fog_texture(rng, 620, 240, 12, contrast=1.0, aniso=2.0)
        self.parts = Particles(rng, 44, y_range=(0.35, 0.95), size=(0.5, 1.4),
                               speed=(0.004, 0.02), drift=0.7,
                               color=(0.95, 0.76, 0.50), brightness=(0.04, 0.20))
        r2 = np.random.default_rng(19)
        self.horde = [(r2.uniform(-0.05, 1.05), r2.uniform(0.02, 0.28),
                       int(r2.integers(0, 9)), int(r2.integers(0, 4)),
                       r2.uniform(0.75, 1.1)) for _ in range(26)]

    def render(self, t):
        z = 1.0 + 0.035 * (t / self.dur)
        dx = 8 - 5 * (t / self.dur)
        dy = 2
        img = to_arr(view(to_img(self.sky), z, dx, dy, 0.1))

        rgb, m = self.far
        far = view(Image.fromarray((np.dstack([rgb, m[..., None]]) * 255).astype(np.uint8), "RGBA"),
                   z, dx, dy, 0.3)
        fr, fa = rgba_arrays(far)
        img = over(img, fr, fa * 0.75)

        yv = (np.arange(H, dtype=F32) / H)[:, None]
        n = np.roll(self.fogA, int(t * 22) % self.fogA.shape[1], axis=1)
        tex = np.asarray(Image.fromarray((n * 255).astype(np.uint8), "L").resize((W, H),
                                                                              Image.BICUBIC), F32) / 255.0
        band = np.exp(-((yv - 0.585) / 0.11) ** 2)
        img = over(img, np.array([0.60, 0.64, 0.59], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   np.clip((0.30 + 0.80 * tex) * band * 0.9, 0, 0.96)[..., None])

        # земля
        ground = np.clip((yv - 0.60) / 0.40, 0, 1) ** 0.9
        img = img * (1 - ground[..., None] * 0.7) + ground[..., None] * np.array([0.05, 0.06, 0.058], F32) * 0.7
        gl = np.exp(-((yv - 0.612) / 0.03) ** 2)
        img = screen(img, np.array([0.34, 0.36, 0.32], F32) * gl[..., None], 0.6)

        # орда позади — мелкие силуэты, идущие к нам
        zs = zombie_atlas()
        for (hx, hd, var, ph, hw) in self.horde:
            spr = zs[var][(ph + int(t * 4)) % 4]
            hpx = int((28 + 150 * hd) * hw)
            sc = hpx / spr.height
            s2 = spr.resize((max(3, int(spr.width * sc)), hpx), Image.LANCZOS)
            a = np.asarray(s2, F32) / 255.0
            px = int(W * hx + 10 * math.sin(t * 1.4 + hx * 9))
            py = int(0.612 * H + (H * 0.66 - 0.612 * H) * (hd / 0.30) + hpx * 0.02)
            fogk = float(np.clip(0.35 + 0.65 * (1 - hd / 0.30), 0, 1))
            rgbm = a[..., :3] * (1 - fogk) + np.array([0.42, 0.46, 0.42], F32) * fogk
            blit_arr(img, np.dstack([rgbm, a[..., 3] * (0.55 + 0.35 * (1 - fogk))]), px, py - hpx)

        # герой — крупным планом, спиной
        hs = self.hero
        sc = (H * 0.92) / hs.height
        sw, sh = int(hs.width * sc), int(hs.height * sc)
        s2 = hs.resize((sw, sh), Image.LANCZOS)
        a = np.asarray(s2, F32) / 255.0
        blit_arr(img, a, int(W * 0.46 - sw / 2 + 6 * (t / self.dur)),
                 int(H * 1.02 - sh + 3 * math.sin(t * 2.2)))

        # туман по низу
        n2 = np.roll(self.fogB, -int(t * 34) % self.fogB.shape[1], axis=1)
        tex2 = np.asarray(Image.fromarray((n2 * 255).astype(np.uint8), "L").resize((W, H),
                                                                                Image.BICUBIC), F32) / 255.0
        band2 = np.clip((yv - 0.72) / 0.28, 0, 1) ** 1.1
        img = over(img, np.array([0.34, 0.37, 0.34], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   np.clip((0.18 + 0.7 * tex2) * band2 * 0.85, 0, 0.95)[..., None])
        n3 = np.roll(self.fogC, int(t * 55) % self.fogC.shape[1], axis=1)
        tex3 = np.asarray(Image.fromarray((n3 * 255).astype(np.uint8), "L").resize((W, H),
                                                                                Image.BICUBIC), F32) / 255.0
        band3 = np.clip((yv - 0.90) / 0.12, 0, 1)
        img = over(img, np.array([0.16, 0.19, 0.18], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   np.clip((0.22 + 0.6 * tex3) * band3 * 0.85, 0, 0.95)[..., None])

        img = self.parts.draw(img, t, alpha=0.5)
        return np.clip(img, 0, 1)


# ══════════════════════════════════════════════════════════════════════════
#  СЦЕНА 5 — титр
# ══════════════════════════════════════════════════════════════════════════
class TitleScene:
    dur = 1.40
    grade = dict(exposure=1.0, contrast=1.16, saturation=0.85,
                 lift=(0.010, 0.012, 0.016), high=(1.06, 0.98, 0.92), bloom=0.55)

    def __init__(self):
        rng = np.random.default_rng(91)
        self.smoke = fog_texture(rng, 700, 300, 3, contrast=0.5, aniso=2.4)
        self.smoke2 = fog_texture(rng, 640, 260, 5, contrast=0.8, aniso=2.0)
        self.title = text_img("ЗОМБИ-АПОКАЛИПСИС", 92, "#efe6d6", tracking=0.16)
        self.sub = text_img("НЕ ОСТАНАВЛИВАЙСЯ", 22, "#b98a6a", tracking=0.62)
        self.parts = Particles(rng, 90, y_range=(0.1, 1.05), size=(0.6, 2.0),
                               speed=(0.01, 0.04), drift=0.6,
                               color=(1.0, 0.42, 0.16), brightness=(0.05, 0.5))

    def render(self, t):
        z = 1.0 + 0.05 * (t / self.dur)
        img = vgrad(W, H, [(0.0, "#050505"), (0.45, "#0a0807"),
                           (0.62, "#160a08"), (1.0, "#040404")])
        # красная подсветка в дымке
        g = radial(W, H, W * 0.5, H * 0.62, W * 0.42, H * 0.5, 2.0)
        img = screen(img, np.array([0.55, 0.10, 0.06], F32) * g[..., None], 0.9)
        n = np.roll(self.smoke, int(t * 60) % self.smoke.shape[1], axis=1)
        sm = np.asarray(Image.fromarray((n * 255).astype(np.uint8), "L").resize((W, H), Image.BICUBIC), F32) / 255
        prof = np.exp(-((np.arange(H) - H * 0.55) / (H * 0.45)) ** 2)[:, None]
        img = over(img, np.array([0.22, 0.13, 0.11], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   (sm * prof * 0.75)[..., None])
        n2 = np.roll(self.smoke2, -int(t * 90) % self.smoke2.shape[1], axis=1)
        sm2 = np.asarray(Image.fromarray((n2 * 255).astype(np.uint8), "L").resize((W, H), Image.BICUBIC), F32) / 255
        img = over(img, np.array([0.06, 0.04, 0.035], F32)[None, None, :] * np.ones((H, W, 1), F32),
                   (sm2 * 0.55)[..., None])
        img = self.parts.draw(img, t, alpha=0.9)

        f = smoothstep(0.10, 0.75, t)
        sc = 1.0 + 0.035 * (1 - ease_out(t / 0.9))
        img = paste_center(img, self.title, W / 2, H * 0.46 - 6 * (1 - f),
                           scale=sc, opacity=min(1.0, f * 1.15),
                           glow=0.85, glow_color=(0.85, 0.24, 0.14), glow_blur=26)
        f2 = smoothstep(0.55, 1.05, t)
        if f2 > 0.002:
            img = paste_center(img, self.sub, W / 2, H * 0.46 + 92, opacity=f2 * 0.85)
        # прощальная виньетка
        edge = radial(W, H, W / 2, H / 2, W * 0.62, H * 0.8, 2.0)
        img = img * (0.45 + 0.85 * edge[..., None])
        return np.clip(img, 0, 1)


# ══════════════════════════════════════════════════════════════════════════
#  СБОРКА
# ══════════════════════════════════════════════════════════════════════════
SCENES = [CityScene(), HordeScene(), DoorScene(), SurvivorScene(), TitleScene()]
BOUNDS = [(0.0, 2.60), (2.60, 5.00), (5.00, 7.60), (7.60, 8.60), (8.60, 10.0)]


def pick(t):
    for sc, (a, b) in zip(SCENES, BOUNDS):
        if a <= t < b:
            return sc, t - a
    return SCENES[-1], t - BOUNDS[-1][0]


def make_frame(i):
    t = i / FPS
    sc, lt = pick(t)
    img = sc.render(lt)
    img = grade(img, **sc.grade)
    if t < 0.45:
        img *= smoothstep(0.0, 0.45, t)
    if t > 9.62:
        img *= 1 - smoothstep(9.62, 9.99, t)
    for cut in CUTS:
        d = abs(t - cut)
        if d < 1.5 / FPS:
            k = 0.35 * (1 - d * FPS / 1.5)
            img = img + k * np.array([0.9, 0.92, 0.95], F32)
    arr = finish(img, t)
    return arr


def find_ffmpeg():
    env = os.environ.get("FFMPEG")
    if env:
        return env
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    from shutil import which
    for name in ("ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        p = which(name) if "/" not in name else (name if os.path.exists(name) else None)
        if p:
            return p
    raise SystemExit("ffmpeg не найден: задайте переменную FFMPEG")


def make_poster(path):
    from engine import text_img, paste_center, radial, BARS
    base = make_frame(int(4.6 * FPS)).astype(F32) / 255.0
    img = base[BARS:BARS + H, :, :].copy()
    edge = radial(W, H, W * 0.5, H * 0.5, W * 0.70, H * 0.80, 1.5)
    img = img * (0.55 + 0.65 * edge[..., None])
    t1 = text_img("ЗОМБИ-АПОКАЛИПСИС", 108, "#efe6d6", tracking=0.14)
    t2 = text_img("10 СЕКУНД · КОРОТКОМЕТРАЖНЫЙ ХОРРОР", 18, "#b98a6a", tracking=0.55)
    img = paste_center(img, t1, W / 2, H * 0.44, glow=0.95,
                       glow_color=(0.85, 0.22, 0.12), glow_blur=30)
    img = paste_center(img, t2, W / 2, H * 0.44 + 112, opacity=0.9)
    out = np.zeros((1080, W, 3), F32)
    out[BARS:BARS + H] = np.clip(img, 0, 1)
    Image.fromarray((out * 255).astype(np.uint8)).save(path)
    print("постер:", path)


def main():
    ffmpeg = find_ffmpeg()
    n = int(round(DUR * FPS))
    raw = os.path.join(WORK, "video_raw.mp4")
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{1080}",
           "-r", str(FPS), "-i", "-", "-an",
           "-c:v", "libx264", "-preset", "slow", "-crf", "17",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
           raw]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        arr = make_frame(i)
        p.stdin.write(arr.tobytes())
        if i % 12 == 0:
            print(f"  кадр {i + 1}/{n}", flush=True)
    p.stdin.close()
    p.wait()

    wav = os.path.join(WORK, "audio.wav")
    audio.build(wav)
    final = os.path.join(OUT_DIR, "final", "zombie_apocalypse_10s.mp4")
    os.makedirs(os.path.dirname(final), exist_ok=True)
    subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", raw, "-i", wav, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", final],
                   check=True)
    print("готово:", final)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "still":
        for ts in sys.argv[2:]:
            i = int(round(float(ts) * FPS))
            arr = make_frame(i)
            Image.fromarray(arr).save(os.path.join(WORK, f"still_{float(ts):.2f}.png"))
            print("saved", ts)
    elif len(sys.argv) > 1 and sys.argv[1] == "audio":
        audio.build(os.path.join(WORK, "audio.wav"))
        print("audio ok")
    elif len(sys.argv) > 1 and sys.argv[1] == "poster":
        make_poster(os.path.join(OUT_DIR, "final", "poster.png"))
    else:
        main()
