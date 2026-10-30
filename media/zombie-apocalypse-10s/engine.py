"""
engine.py — маленький процедурный кинематографический движок на Pillow + NumPy.
Никаких внешних ассетов: всё (туман, силуэты, оптика, зерно) считается кодом.
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── формат ────────────────────────────────────────────────────────────────
W, H = 1920, 804          # активная зона кадра (2.39:1)
RW, RH = 2400, 1005       # «полотно» под панораму/наезд камеры
FPS = 24
DUR = 10.0
BARS = (1080 - H) // 2    # чёрные полосы сверху/снизу

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

F32 = np.float32


# ── мелочи ────────────────────────────────────────────────────────────────
def clamp(x, lo=0.0, hi=1.0):
    return np.clip(x, lo, hi)


def smoothstep(a, b, x):
    t = np.clip((x - a) / max(1e-6, (b - a)), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ease_out(x):
    x = float(np.clip(x, 0, 1))
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = float(np.clip(x, 0, 1))
    return 3 * x * x - 2 * x * x * x


def lerp(a, b, t):
    return a + (b - a) * t


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], F32)


# ── градиенты и шум ───────────────────────────────────────────────────────
def vgrad(w, h, stops):
    """Вертикальный градиент. stops = [(pos0..1, '#rrggbb'|array), ...]."""
    ys = np.zeros(h, F32)
    cols = []
    pos = [s[0] for s in stops]
    col = [hexc(s[1]) if isinstance(s[1], str) else np.array(s[1], F32) for s in stops]
    for y in range(h):
        p = y / max(1, h - 1)
        i = 0
        while i < len(pos) - 2 and p > pos[i + 1]:
            i += 1
        span = max(1e-6, pos[i + 1] - pos[i])
        t = float(np.clip((p - pos[i]) / span, 0, 1))
        t = t * t * (3 - 2 * t)
        cols.append(col[i] + (col[i + 1] - col[i]) * t)
    arr = np.array(cols, F32)                     # h,3
    return np.repeat(arr[:, None, :], w, axis=1)   # h,w,3


def value_noise(h, w, cells, rng):
    gh = max(2, int(h / cells))
    gw = max(2, int(w / cells))
    g = (rng.random((gh, gw)) * 255).astype(np.uint8)
    im = Image.fromarray(g, "L").resize((w, h), Image.BICUBIC)
    return np.asarray(im, F32) / 255.0


def fbm(h, w, cells, rng, octaves=6, persistence=0.55):
    total = np.zeros((h, w), F32)
    amp, norm, c = 1.0, 0.0, float(cells)
    for _ in range(octaves):
        total += amp * value_noise(h, w, c, rng)
        norm += amp
        amp *= persistence
        c = max(2.0, c * 0.5)
    return total / norm


def radial(w, h, cx, cy, rx, ry, power=1.0):
    y, x = np.mgrid[0:h, 0:w].astype(F32)
    d = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    return np.clip(1 - d, 0, 1) ** power


# ── работа с изображениями ────────────────────────────────────────────────
def to_img(arr, mode="RGB"):
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), mode)


def to_arr(img):
    return np.asarray(img, F32) / 255.0


def blank_rgba(w, h, rgb=(0, 0, 0), a=0):
    return Image.new("RGBA", (w, h), tuple(int(v) for v in rgb) + (a,))


def rgba_arrays(img):
    a = np.asarray(img, F32) / 255.0
    return a[..., :3].copy(), a[..., 3].copy()


def over(dst, rgb, alpha):
    if alpha.ndim == 2:
        alpha = alpha[..., None]
    return dst * (1 - alpha) + rgb * alpha


def screen(dst, src, strength=1.0):
    s = np.clip(src * strength, 0, 1)
    return 1 - (1 - dst) * (1 - s)


def view(img, z=1.0, dx=0.0, dy=0.0, p=1.0):
    """Камера: наезд z, сдвиг dx/dy (в пикселях полотна), параллакс p."""
    zz = 1.0 + (z - 1.0) * p
    ccx = RW / 2 + dx * p
    ccy = RH / 2 + dy * p
    a = 1.0 / zz
    c = ccx - (W / 2) / zz
    f = ccy - (H / 2) / zz
    return img.transform((W, H), Image.AFFINE, (a, 0, c, 0, a, f),
                         resample=Image.BICUBIC)


# ── текст ─────────────────────────────────────────────────────────────────
def text_img(text, size, color="#ffffff", tracking=0.0, font=FONT_BOLD, ss=2,
             alpha=1.0):
    """Строка с трекингом, отрендеренная в 2x для чёткости."""
    f = ImageFont.truetype(font, size * ss)
    tmp = Image.new("L", (10, 10))
    d = ImageDraw.Draw(tmp)
    widths = []
    for ch in text:
        widths.append(d.textlength(ch, font=f) + tracking * size * ss)
    total = int(sum(widths)) + 4
    asc, desc = f.getmetrics()
    hgt = asc + desc + 4
    mask = Image.new("L", (max(4, total), hgt), 0)
    md = ImageDraw.Draw(mask)
    x = 2
    for ch, adv in zip(text, widths):
        md.text((x, 2), ch, font=f, fill=255)
        x += adv
    mask = mask.resize((max(2, mask.width // ss), max(2, mask.height // ss)),
                       Image.LANCZOS)
    rgb = np.zeros((mask.height, mask.width, 4), F32)
    c = hexc(color) if isinstance(color, str) else np.array(color, F32)
    rgb[..., :3] = c
    rgb[..., 3] = np.asarray(mask, F32) / 255.0 * alpha
    return Image.fromarray((rgb * 255).astype(np.uint8), "RGBA")


def _blit(canvas, rgb, alpha, x0, y0):
    """alpha: (h,w) или (h,w,1). Накладывает с обрезкой по границам."""
    ch, cw = canvas.shape[:2]
    if alpha.ndim == 3:
        alpha = alpha[..., 0]
    ih, iw = alpha.shape[:2]
    sx0, sy0 = max(0, x0), max(0, y0)
    sx1, sy1 = min(cw, x0 + iw), min(ch, y0 + ih)
    if sx0 >= sx1 or sy0 >= sy1:
        return
    ox, oy = sx0 - x0, sy0 - y0
    hh, ww = sy1 - sy0, sx1 - sx0
    canvas[sy0:sy1, sx0:sx1] = over(
        canvas[sy0:sy1, sx0:sx1],
        rgb[oy:oy + hh, ox:ox + ww],
        alpha[oy:oy + hh, ox:ox + ww][..., None])


def blit_arr(canvas, rgba, x0, y0, alpha_mul=1.0, rgb_mul=1.0):
    """Накладывает RGBA (h,w,4) в canvas (RGB или RGBA float) с обрезкой."""
    h, w = rgba.shape[:2]
    ch, cw = canvas.shape[:2]
    sx0, sy0 = max(0, x0), max(0, y0)
    sx1, sy1 = min(cw, x0 + w), min(ch, y0 + h)
    if sx0 >= sx1 or sy0 >= sy1:
        return
    ox, oy = sx0 - x0, sy0 - y0
    hh, ww = sy1 - sy0, sx1 - sx0
    sub = rgba[oy:oy + hh, ox:ox + ww]
    if canvas.shape[2] == 4:
        a0 = canvas[sy0:sy1, sx0:sx1, 3:4]
        a1 = np.clip(sub[..., 3:4] * alpha_mul, 0, 1)
        canvas[sy0:sy1, sx0:sx1, :3] = over(canvas[sy0:sy1, sx0:sx1, :3],
                                            sub[..., :3] * rgb_mul, a1)
        canvas[sy0:sy1, sx0:sx1, 3:4] = a1 + a0 * (1 - a1)
    else:
        canvas[sy0:sy1, sx0:sx1] = over(canvas[sy0:sy1, sx0:sx1],
                                        sub[..., :3] * rgb_mul,
                                        sub[..., 3:4] * alpha_mul)


def max_alpha(dst, alpha, x0, y0):
    """dst *= max(dst, alpha), с обрезкой."""
    h, w = alpha.shape[:2]
    ch, cw = dst.shape[:2]
    sx0, sy0 = max(0, x0), max(0, y0)
    sx1, sy1 = min(cw, x0 + w), min(ch, y0 + h)
    if sx0 >= sx1 or sy0 >= sy1:
        return
    ox, oy = sx0 - x0, sy0 - y0
    hh, ww = sy1 - sy0, sx1 - sx0
    dst[sy0:sy1, sx0:sx1] = np.maximum(dst[sy0:sy1, sx0:sx1],
                                       alpha[oy:oy + hh, ox:ox + ww])


def _screen_blit(canvas, rgb, alpha, x0, y0):
    ch, cw = canvas.shape[:2]
    ih, iw = alpha.shape[:2]
    sx0, sy0 = max(0, x0), max(0, y0)
    sx1, sy1 = min(cw, x0 + iw), min(ch, y0 + ih)
    if sx0 >= sx1 or sy0 >= sy1:
        return
    ox, oy = sx0 - x0, sy0 - y0
    hh, ww = sy1 - sy0, sx1 - sx0
    dst = canvas[sy0:sy1, sx0:sx1]
    src = rgb[oy:oy + hh, ox:ox + ww]
    k = alpha[oy:oy + hh, ox:ox + ww][..., None]
    canvas[sy0:sy1, sx0:sx1] = dst + (1 - (1 - dst) * (1 - src * k)) * 0 + \
        (np.clip(k, 0, 1) * (src - dst * src))


def paste_center(canvas, im, cx, cy, scale=1.0, opacity=1.0, glow=0.0,
                 glow_color=None, glow_blur=18):
    """Накладывает RGBA по центру кадра с масштабом и свечением."""
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                       Image.LANCZOS)
    if glow > 0:
        gc = np.array(glow_color if glow_color is not None else (0.75, 0.85, 0.95), F32)
        g = im.filter(ImageFilter.GaussianBlur(glow_blur))
        ga = np.asarray(g, F32)[..., 3] / 255.0
        k = np.clip(ga * glow * opacity, 0, 1)
        _screen_blit(canvas, np.ones((g.height, g.width, 3), F32) * gc, k,
                     int(cx - g.width / 2), int(cy - g.height / 2))
    a = np.asarray(im, F32) / 255.0
    _blit(canvas, a[..., :3], a[..., 3] * opacity,
          int(cx - im.width / 2), int(cy - im.height / 2))
    return canvas



def periodic_fbm(h, w, base, rng, octaves=4, persistence=0.55, waves=18, aniso=1.0):
    """Бесшовная (тайлится по обеим осям) облачная текстура."""
    yy = np.arange(h, dtype=F32)[:, None] / h * (2 * math.pi)
    xx = np.arange(w, dtype=F32)[None, :] / w * (2 * math.pi)
    total = np.zeros((h, w), F32)
    norm = 0.0
    amp = 1.0
    for o in range(octaves):
        n = max(1, int(round(base * (2 ** o))))
        acc = np.zeros((h, w), F32)
        for _ in range(waves):
            kx = int(rng.integers(1, n + 1)) * int(rng.choice([-1, 1]))
            ky = int(rng.integers(1, max(2, int(n * aniso)) + 1)) * int(rng.choice([-1, 1]))
            ph = float(rng.random()) * 2 * math.pi
            acc += np.sin(kx * xx + ky * yy + ph)
        total += amp * (acc / waves * 0.5 + 0.5)
        norm += amp
        amp *= persistence
    return total / norm


def fog_texture(rng, w, h, base, contrast=0.55, octaves=4, aniso=1.6):
    n = periodic_fbm(h, w, base, rng, octaves=octaves, aniso=aniso)
    n = (n - 0.5) * (1.0 + contrast * 2.0) + 0.5
    return np.clip(n, 0, 1) ** 1.15


def god_rays(img, cx, cy, n=9, length=1.4, spread=0.55, strength=0.22,
             color=(1.0, 0.86, 0.62), t=0.0, angle=0.35):
    """Мягкие объёмные лучи из точки (screen-блендинг)."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(F32)
    dx = (xx - cx) / w
    dy = (yy - cy) / h
    ang = np.arctan2(dy, dx)
    dist = np.sqrt(dx * dx + dy * dy)
    acc = np.zeros((h, w), F32)
    for i in range(n):
        a0 = angle + (i / n - 0.5) * spread * math.pi + 0.10 * math.sin(t * 0.7 + i)
        d = np.abs(np.angle(np.exp(1j * (ang - a0))))
        acc += np.exp(-(d / 0.05) ** 2) * (0.55 + 0.45 * math.sin(t * 1.7 + i * 2.3))
    acc = np.clip(acc / n, 0, 1)
    falloff = np.clip(1.0 - dist / length, 0, 1) ** 2.2
    return screen(img, np.array(color, F32)[None, None, :] * (acc * falloff)[..., None],
                  strength)


def soft_dof(im, radius):
    if radius <= 0.3:
        return im
    return im.filter(ImageFilter.GaussianBlur(radius))


# ── силуэты людей ─────────────────────────────────────────────────────────
def _limb(d, pts, width, fill):
    d.line(pts, fill=fill, width=int(width), joint="curve")
    for p in (pts[0], pts[-1]):
        r = width / 2
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=fill)


def _rim_rgba(mask, dark, rimc, rim_strength=0.9, glowc=(0.08, 0.11, 0.13),
              glow_blur=6):
    """Маска силуэта → RGBA с контровым светом и рассеянным свечением."""
    alpha = mask
    m = Image.fromarray((np.clip(mask, 0, 1) * 255).astype(np.uint8), "L")
    core = np.asarray(m.filter(ImageFilter.MinFilter(5)), F32) / 255.0
    shifted = np.roll(np.roll(core, -3, axis=1), 2, axis=0)
    rim = np.clip(core - shifted, 0, 1)
    glow = np.asarray(m.filter(ImageFilter.GaussianBlur(glow_blur)), F32) / 255.0
    out = np.zeros(mask.shape + (4,), F32)
    out[..., :3] = np.array(dark, F32)
    out[..., :3] += rim[..., None] * np.array(rimc, F32) * rim_strength
    out[..., :3] += glow[..., None] * np.array(glowc, F32)
    out[..., 3] = alpha
    return np.clip(out, 0, 1)


def _smin(a, b, k):
    m = np.minimum(a, b)
    return m - k * np.log1p(np.exp(-np.abs(a - b) / k))


def _sdf_capsule(px, py, a, b, r0, r1=None):
    """Конус-капсула (радиус меняется от r0 к r1)."""
    if r1 is None:
        r1 = r0
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    den = dx * dx + dy * dy + 1e-12
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / den, 0.0, 1.0)
    d = np.sqrt((px - (ax + t * dx)) ** 2 + (py - (ay + t * dy)) ** 2)
    return d - (r0 + (r1 - r0) * t)


def _sdf_ellipse(px, py, c, rx, ry):
    q = np.sqrt(((px - c[0]) / rx) ** 2 + ((py - c[1]) / ry) ** 2)
    return (q - 1.0) * min(rx, ry)



# ── векторный «ходячий» силуэт в профиль ─────────────────────────────────
def _pack(pts):
    return [(float(a), float(b)) for a, b in pts]


def _poly(d, pts, S, fill=255):
    d.polygon([(x * S, y * S) for x, y in pts], fill=fill)


def _taper(d, a, b, w0, w1, S, fill=255):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy) + 1e-9
    nx, ny = -dy / L, dx / L
    d.polygon([((ax + nx * w0 / 2) * S, (ay + ny * w0 / 2) * S),
               ((bx + nx * w1 / 2) * S, (by + ny * w1 / 2) * S),
               ((bx - nx * w1 / 2) * S, (by - ny * w1 / 2) * S),
               ((ax - nx * w0 / 2) * S, (ay - ny * w0 / 2) * S)], fill=fill)
    for (px, py), w in ((a, w0), (b, w1)):
        d.ellipse([(px - w / 2) * S, (py - w / 2) * S,
                   (px + w / 2) * S, (py + w / 2) * S], fill=fill)


def _zombie_parts(stride=0.0, hunch=1.0, rng=None, arm="reach"):
    """Части фигуры в профиль (рост = 1), идёт вправо."""
    rng = rng if rng is not None else np.random.default_rng(0)
    s = float(np.clip(stride, -1, 1))
    h = float(np.clip(hunch, 0.6, 1.4))
    fwd = 0.010 + 0.028 * h        # наклон корпуса вперёд
    drop = 0.006 + 0.018 * h       # опущенная голова

    # корпус + пальто (по часовой: от затылка вниз по спине, потом вверх по груди)
    body = _pack([
        (0.086, 0.118), (0.070, 0.092),                       # затылок
        (0.082, 0.060), (0.116, 0.034), (0.152, 0.030),       # череп
        (0.176, 0.050), (0.184 + 0.010 * h, 0.072),           # лоб
        (0.198 + 0.014 * h, 0.092),                           # переносица
        (0.190 + 0.014 * h, 0.104),                           # нос
        (0.194 + 0.012 * h, 0.118),                           # губы
        (0.186 + 0.010 * h, 0.132),                           # подбородок
        (0.162, 0.140 + drop), (0.150, 0.158 + drop),         # горло, шея
        (0.164 + fwd, 0.186),                                 # ключица
        (0.170 + fwd, 0.230), (0.166 + fwd * 0.8, 0.285),     # грудь
        (0.152 + fwd * 0.6, 0.345), (0.156 + fwd * 0.4, 0.405),  # живот
        (0.168 + fwd * 0.3, 0.470), (0.180 + fwd * 0.2, 0.520),  # пола пальто
        (0.160, 0.548), (0.140, 0.532), (0.118, 0.560),       # рваный подол
        (0.096, 0.534), (0.072, 0.556), (0.050, 0.526),
        (0.038, 0.470), (0.030, 0.400), (0.024, 0.330),       # спина
        (0.032, 0.262), (0.048, 0.212), (0.070, 0.180),       # горб
        (0.080, 0.150), (0.086, 0.128),
    ])
    # черепная крышка (чтобы голова читалась отдельно от плеч)
    skull = _pack([
        (0.090, 0.030), (0.128, 0.016), (0.164, 0.024), (0.180, 0.050),
        (0.176, 0.082), (0.158, 0.104), (0.126, 0.110), (0.100, 0.098),
        (0.088, 0.068),
    ])
    neck = _pack([(0.100, 0.100), (0.150, 0.112), (0.156, 0.166),
                  (0.118, 0.170), (0.096, 0.140)])

    hip_f = (0.132 + fwd * 0.2, 0.505)
    hip_b = (0.062 + fwd * 0.1, 0.512)
    knee_f = (0.152 + 0.052 * s, 0.712 - 0.014 * max(0, s))
    ankle_f = (0.160 + 0.092 * s, 0.952 - 0.040 * max(0, s))
    knee_b = (0.058 - 0.042 * s, 0.716 + 0.008 * abs(s))
    ankle_b = (0.040 - 0.084 * s, 0.950 + 0.008 * max(0, -s))

    sh_f = (0.166 + fwd, 0.192)
    sh_b = (0.074 + fwd * 0.6, 0.202)
    if arm == "reach":
        el_f = (sh_f[0] + 0.078, sh_f[1] + 0.048 + 0.018 * s)
        ha_f = (el_f[0] + 0.108, el_f[1] - 0.016 + 0.026 * s)
    else:
        el_f = (sh_f[0] + 0.030, sh_f[1] + 0.102 + 0.014 * s)
        ha_f = (el_f[0] + 0.006, el_f[1] + 0.098 + 0.022 * s)
    el_b = (sh_b[0] - 0.026 + 0.016 * s, sh_b[1] + 0.096)
    ha_b = (el_b[0] + 0.002 + 0.036 * s, el_b[1] + 0.104)

    return dict(body=body, skull=skull, neck=neck,
                legs_b=[(hip_b, knee_b, ankle_b)], legs_f=[(hip_f, knee_f, ankle_f)],
                arm_f=(sh_f, el_f, ha_f), arm_b=(sh_b, el_b, ha_b))


def _draw_walker(d, S, parts, survivors=False):
    """Рисует фигуру (все части одним цветом) в маску."""
    # дальние конечности
    for (hip, knee, ankle) in parts["legs_b"]:
        _taper(d, hip, knee, 0.056 * S / S, 0.040, S)
        _taper(d, knee, ankle, 0.040, 0.026, S)
        _taper(d, (ankle[0] - 0.012, ankle[1] + 0.020),
               (ankle[0] + 0.052, ankle[1] + 0.026), 0.030, 0.024, S)
    sh, el, ha = parts["arm_b"]
    _taper(d, sh, el, 0.046, 0.036, S)
    _taper(d, el, ha, 0.036, 0.028, S)
    # корпус
    _poly(d, parts["body"], S)
    _poly(d, parts["neck"], S)
    _poly(d, parts["skull"], S)
    # челюсть уже в контуре черепа
    # ближние конечности
    for (hip, knee, ankle) in parts["legs_f"]:
        _taper(d, hip, knee, 0.062, 0.044, S)
        _taper(d, knee, ankle, 0.044, 0.028, S)
        _taper(d, (ankle[0] - 0.010, ankle[1] + 0.020),
               (ankle[0] + 0.058, ankle[1] + 0.028), 0.032, 0.026, S)
    sh, el, ha = parts["arm_f"]
    _taper(d, sh, el, 0.052, 0.040, S)
    _taper(d, el, ha, 0.040, 0.030, S)
    d.ellipse([(ha[0] - 0.026) * S, (ha[1] - 0.022) * S,
               (ha[0] + 0.026) * S, (ha[1] + 0.026) * S], fill=255)


def walker_rgba(hs, seed=0, phase=0.0, rim=(0.55, 0.66, 0.68),
                rim_strength=1.0, surface=0.02, survivor=False):
    """RGBA-силуэт идущего (профиль): тёмное тело + контровой свет."""
    rng = np.random.default_rng(seed)
    stride = math.sin(phase * math.tau)
    hunch = float(rng.uniform(0.75, 1.3))
    arm = "reach" if rng.random() < 0.66 else "hang"
    if survivor:
        hunch, arm = 0.25, "hang"
    parts = _zombie_parts(stride=stride, hunch=hunch, arm=arm, rng=rng)

    SS = 3
    Wp = int(hs * 1.05) + 8
    Hp = int(hs * 1.05) + 8
    S = hs * SS
    mask = Image.new("L", (Wp * SS, Hp * SS), 0)
    d = ImageDraw.Draw(mask)
    ox = -0.02 * S
    oy = 0.012 * S
    d.ellipse([0, 0, 0, 0], fill=0)
    # сдвиг начала координат
    class _Shift:
        def __init__(self, d, ox, oy):
            self.d, self.ox, self.oy = d, ox, oy

        def polygon(self, pts, fill=255):
            self.d.polygon([(x + self.ox, y + self.oy) for x, y in pts], fill=fill)

        def ellipse(self, box, fill=255):
            self.d.ellipse([box[0] + self.ox, box[1] + self.oy,
                            box[2] + self.ox, box[3] + self.oy], fill=fill)

    _draw_walker(_Shift(d, ox, oy), S, parts, survivors=survivor)
    mask = mask.resize((Wp, Hp), Image.LANCZOS)
    alpha = np.asarray(mask, F32) / 255.0
    gy, gx = np.gradient(alpha)
    nz = np.sqrt(gx * gx + gy * gy) + 1e-6
    nx, ny = gx / nz, gy / nz
    lit = np.clip(nx * 0.9 - ny * 0.2, 0, 1)
    m_er = np.asarray(Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8), "L")
                      .filter(ImageFilter.MinFilter(3)), F32) / 255.0
    edge = np.clip(alpha - m_er * 0.92, 0, 1) * 2.2
    body = np.array([0.008, 0.011, 0.013], F32)[None, None, :] * np.ones((Hp, Wp, 1), F32)
    body = body + (0.030 + surface) * lit[..., None] * np.array([0.42, 0.48, 0.48], F32)
    body = body + edge[..., None] * np.clip(nx * 1.0 + 0.2, 0, 1)[..., None] \
        * np.array(rim, F32) * rim_strength * 0.8
    m = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8), "L")
    glow = np.asarray(m.filter(ImageFilter.GaussianBlur(max(2, int(hs * 0.010)))),
                      F32) / 255.0
    body = body + glow[..., None] * np.array([0.03, 0.04, 0.045], F32)
    out = np.dstack([np.clip(body, 0, 1), np.clip(alpha, 0, 1)])
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


def zombie_rgba(hs, seed=0, phase=0.0, arm="reach", rim=(0.55, 0.66, 0.68),
                rim_strength=1.0, surface=0.02):
    return walker_rgba(hs, seed=seed, phase=phase, rim=rim,
                       rim_strength=rim_strength, surface=surface)



def hero_sprite(hs, seed=5):
    """Выживший спиной к камере: капюшон, рюкзак, бита на плече, фонарь в руке."""
    SS = 3
    Wp = int(hs * 0.78)
    Hp = int(hs * 1.04)
    S = hs * SS
    mask = Image.new("L", (Wp * SS, Hp * SS), 0)
    d = ImageDraw.Draw(mask)
    ox = Wp * SS * 0.5
    oy = 0.010 * S

    class _Sh:
        def polygon(self, pts, fill=255):
            d.polygon([(x + ox, y + oy) for x, y in pts], fill=fill)

        def ellipse(self, box, fill=255):
            d.ellipse([box[0] + ox, box[1] + oy, box[2] + ox, box[3] + oy], fill=fill)

    sh = _Sh()

    def taper(a, b, w0, w1, fill=255):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) + 1e-9
        nx, ny = -dy / L, dx / L
        sh.polygon([((ax + nx * w0 / 2) * S, (ay + ny * w0 / 2) * S),
                    ((bx + nx * w1 / 2) * S, (by + ny * w1 / 2) * S),
                    ((bx - nx * w1 / 2) * S, (by - ny * w1 / 2) * S),
                    ((ax - nx * w0 / 2) * S, (ay - ny * w0 / 2) * S)], fill=fill)
        for (px, py), w in ((a, w0), (b, w1)):
            sh.ellipse([(px - w / 2) * S, (py - w / 2) * S,
                        (px + w / 2) * S, (py + w / 2) * S], fill=fill)

    # ноги
    for side in (-1, 1):
        taper((side * 0.052, 0.640), (side * 0.062, 0.800), 0.070, 0.056)
        taper((side * 0.062, 0.800), (side * 0.070, 0.952), 0.056, 0.046)
        # ботинок
        sh.ellipse([(side * 0.070 - 0.044) * S, 0.938 * S,
                    (side * 0.070 + 0.050) * S, 0.985 * S], fill=255)
    # пальто (трапеция с небольшим клёшем)
    sh.polygon([(-0.108 * S, 0.185 * S), (0.108 * S, 0.185 * S),
                (0.120 * S, 0.300 * S), (0.132 * S, 0.430 * S),
                (0.142 * S, 0.560 * S), (0.150 * S, 0.640 * S),
                (0.100 * S, 0.660 * S), (-0.100 * S, 0.660 * S),
                (-0.150 * S, 0.640 * S), (-0.142 * S, 0.560 * S),
                (-0.132 * S, 0.430 * S), (-0.120 * S, 0.300 * S)], fill=255)
    # плечи
    sh.ellipse([-0.126 * S, 0.168 * S, 0.126 * S, 0.238 * S], fill=255)
    # рюкзак
    sh.ellipse([-0.092 * S, 0.232 * S, 0.092 * S, 0.300 * S], fill=255)
    sh.polygon([(-0.098 * S, 0.260 * S), (0.098 * S, 0.260 * S),
                (0.104 * S, 0.400 * S), (0.092 * S, 0.462 * S),
                (-0.092 * S, 0.462 * S), (-0.104 * S, 0.400 * S)], fill=255)
    # лямки
    taper((-0.062, 0.250), (-0.070, 0.420), 0.020, 0.020)
    taper((0.062, 0.250), (0.070, 0.420), 0.020, 0.020)
    # капюшон
    sh.ellipse([-0.072 * S, 0.060 * S, 0.072 * S, 0.190 * S], fill=255)
    sh.polygon([(-0.078 * S, 0.150 * S), (0.078 * S, 0.150 * S),
                (0.062 * S, 0.196 * S), (-0.062 * S, 0.196 * S)], fill=255)
    # левая рука вдоль тела
    taper((-0.115, 0.215), (-0.140, 0.360), 0.046, 0.036)
    taper((-0.140, 0.360), (-0.132, 0.480), 0.036, 0.030)
    sh.ellipse([-0.152 * S, 0.470 * S, -0.112 * S, 0.512 * S], fill=255)
    # правая рука поднята к бите
    taper((0.115, 0.215), (0.168, 0.250), 0.046, 0.040)
    taper((0.168, 0.250), (0.196, 0.128), 0.040, 0.032)
    # бита на плече
    taper((0.180, 0.170), (0.300, 0.010), 0.030, 0.042)

    mask = mask.resize((Wp, Hp), Image.LANCZOS)
    alpha = np.asarray(mask, F32) / 255.0
    m_er = np.asarray(Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8), "L")
                      .filter(ImageFilter.MinFilter(3)), F32) / 255.0
    edge = np.clip(alpha - m_er * 0.92, 0, 1) * 2.2
    gy, gx = np.gradient(alpha)
    nz = np.sqrt(gx * gx + gy * gy) + 1e-6
    nx = gx / nz
    side_light = np.clip(nx * 0.8 + 0.2, 0, 1)
    body = np.array([0.008, 0.011, 0.013], F32)[None, None, :] * np.ones((Hp, Wp, 1), F32)
    body = body + 0.10 * side_light[..., None] * np.array([0.55, 0.48, 0.40], F32)
    body = body + edge[..., None] * side_light[..., None] * np.array([1.0, 0.74, 0.42], F32) * 1.25
    m = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8), "L")
    glow = np.asarray(m.filter(ImageFilter.GaussianBlur(max(2, int(hs * 0.012)))),
                      F32) / 255.0
    body = body + glow[..., None] * np.array([0.05, 0.045, 0.04], F32)
    out = np.dstack([np.clip(body, 0, 1), np.clip(alpha, 0, 1)])
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


def survivor_sprite(height, seed=3, ss=2):
    return survivor_rgba(height)


def survivor_rgba(hs):
    return walker_rgba(hs, seed=4, phase=0.02, rim=(0.92, 0.72, 0.44),
                       rim_strength=1.35, surface=0.10, survivor=True)


# ── постобработка ─────────────────────────────────────────────────────────
_VIGNETTE = None
_GRAIN = None


def _init_post():
    global _VIGNETTE, _GRAIN
    if _VIGNETTE is not None:
        return
    y, x = np.mgrid[0:H, 0:W].astype(F32)
    nx = (x - W / 2) / (W / 2)
    ny = (y - H / 2) / (H / 2)
    r = np.sqrt(nx ** 2 * 0.85 + ny ** 2)
    v = np.clip(1.0 - 0.55 * np.clip(r - 0.25, 0, None) ** 1.6, 0, 1)
    _VIGNETTE = v[..., None].astype(F32)
    rng = np.random.default_rng(99)
    _GRAIN = (rng.standard_normal((12, H, W)).astype(np.float16))


def grade(img, exposure=1.0, contrast=1.07, saturation=0.85, lift=(0.010, 0.020, 0.030),
          high=(1.06, 1.00, 0.90), bloom=0.35):
    img = np.clip(img, 0, 4)
    # тонмаппинг мягкий
    img = img / (1.0 + img * 0.28)
    img = np.clip(img * exposure, 0, 2)
    # сплит-тонирование
    lum = img.mean(axis=2, keepdims=True)
    sh = np.clip(1.0 - lum * 2.2, 0, 1)
    hi = np.clip((lum - 0.45) * 2.0, 0, 1)
    img = img + sh * np.array(lift, F32) * 1.0 + hi * (np.array(high, F32) - 1.0) * 0.20
    # контраст
    img = (img - 0.5) * contrast + 0.5
    # насыщенность
    g = img.mean(axis=2, keepdims=True)
    img = g + (img - g) * saturation
    img = np.clip(img, 0, 1)
    # bloom
    if bloom > 0:
        small = to_img(img).resize((W // 4, H // 4), Image.BILINEAR)
        small = small.filter(ImageFilter.GaussianBlur(5))
        b = to_arr(small.resize((W, H), Image.BILINEAR))
        img = screen(img, b, bloom)
    return np.clip(img, 0, 1)


def finish(img, t, grain=0.045, ca=1.0, flicker=0.012):
    """Зерно, хроматика, виньетка, мерцание, лоттербокс → 1920x1080 uint8."""
    _init_post()
    # лёгкая хроматическая аберрация
    if ca > 0:
        sh = int(round(ca))
        img[..., 0] = np.roll(img[..., 0], sh, axis=1)
        img[..., 2] = np.roll(img[..., 2], -sh, axis=1)
    img *= _VIGNETTE
    # мерцание экспозиции
    fl = 1.0 + flicker * math.sin(t * 31.7) * math.sin(t * 7.3 + 1.1)
    img *= fl
    # зерно
    if grain > 0:
        idx = int(t * FPS * 1.7) % _GRAIN.shape[0]
        g = _GRAIN[idx].astype(F32) / 255.0
        img = img + g[..., None] * grain
    img = np.clip(img, 0, 1)
    out = np.zeros((1080, W, 3), np.uint8)
    out[BARS:BARS + H] = (img * 255).astype(np.uint8)
    return out


# ── частицы ───────────────────────────────────────────────────────────────
class Particles:
    def __init__(self, rng, count, y_range=(0.0, 1.0), size=(0.6, 2.2),
                 speed=(0.005, 0.03), drift=0.35, color=(1.0, 0.62, 0.28),
                 brightness=(0.15, 0.85)):
        self.n = count
        self.x0 = rng.random(count)
        self.y0 = rng.uniform(*y_range, count)
        self.sp = rng.uniform(*speed, count)
        self.ph = rng.random(count) * math.tau
        self.sz = rng.uniform(*size, count)
        self.br = rng.uniform(*brightness, count)
        self.drift = drift
        self.color = np.array(color, F32)

    def draw(self, img, t, alpha=1.0, scale=1.0):
        h, w = img.shape[:2]
        yy, xx = np.mgrid[-3:4, -3:4].astype(F32)
        for i in range(self.n):
            x = (self.x0[i] + self.drift * 0.06 * math.sin(t * 0.9 + self.ph[i])
                 + 0.004 * t) % 1.0
            y = (self.y0[i] - self.sp[i] * t) % 1.0
            px, py = int(x * w), int(y * h)
            s = self.sz[i] * scale
            if s < 0.4:
                s = 0.4
            g = np.exp(-((xx ** 2 + yy ** 2) / (2 * s * s))) * self.br[i] * alpha
            x0, y0 = px - 3, py - 3
            if x0 < 0 or y0 < 0 or x0 + 7 > w or y0 + 7 > h:
                continue
            patch = img[y0:y0 + 7, x0:x0 + 7]
            img[y0:y0 + 7, x0:x0 + 7] = patch + g[..., None] * self.color
        return img
