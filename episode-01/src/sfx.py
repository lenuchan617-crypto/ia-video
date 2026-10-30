# -*- coding: utf-8 -*-
"""Синтез звуковой партитуры эпизода: ветер, цепи, колокол, суб-дрон, удары.
Никакой эпической музыки — только воздух, металл и тишина. 48 kHz, stereo."""
import numpy as np, wave, os, sys, math

FS = 48000
DUR = 780.0
N = int(DUR * FS)
RNG = np.random.default_rng(20251030)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(ROOT, "build", "audio")   # тяжёлый WAV — вне снапшота


# ------------------------------------------------------------------ primitives
def band(n, lo, hi, seed=None, tilt=-0.5):
    """Полосовой шум через FFT-маску (мягкие края)."""
    r = np.random.default_rng(seed if seed is not None else RNG.integers(1 << 30))
    x = r.standard_normal(n).astype(np.float32)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / FS) + 1e-6
    # плавный колокол в лог-шкале
    a = np.log(np.maximum(f, 20.0))
    llo, lhi = np.log(max(lo, 20.0)), np.log(max(hi, 21.0))
    wide = max((lhi - llo) * 0.45, 0.12)
    mask = np.exp(-((a - (llo + lhi) / 2) ** 2) / (2 * wide ** 2))
    mask[f < lo * 0.5] = 0
    mask[f > hi * 2.0] = 0
    mask *= (f / 1000.0) ** tilt
    y = np.fft.irfft(X * mask, n).astype(np.float32)
    m = np.max(np.abs(y)) + 1e-9
    return y / m


def boxsmooth(x, w):
    """Быстрое сглаживание через cumsum (вместо свёртки)."""
    if w < 2:
        return x
    w = int(w) | 1
    pad = w // 2
    xp = np.pad(x.astype(np.float64), (pad, pad), mode="edge")
    cs = np.cumsum(xp)
    cs = np.concatenate(([0.0], cs))
    y = (cs[w:] - cs[:-w]) / w
    return y[:len(x)].astype(np.float32)


def env_gust(n, rate=0.35, low=0.25, high=1.0, seed=1):
    """Медленно гуляющая огибающая (порывы ветра)."""
    r = np.random.default_rng(seed)
    k = max(4, int(n / FS * rate))
    pts = r.random(k) ** 1.6
    xs = np.linspace(0, 1, k)
    e = np.interp(np.linspace(0, 1, n), xs, low + (high - low) * pts).astype(np.float32)
    return boxsmooth(boxsmooth(e, int(FS * 0.22)), int(FS * 0.22))


def add(L, R, t, sig, gain=1.0, pan=0.0):
    i = int(t * FS)
    if i >= N:
        return
    if i < 0:
        sig = sig[-i:]; i = 0
    s = sig[: max(0, N - i)]
    gl = gain * math.cos((pan + 1) * math.pi / 4)
    gr = gain * math.sin((pan + 1) * math.pi / 4)
    L[i:i + len(s)] += s * gl
    R[i:i + len(s)] += s * gr


def addbed(L, R, t0, t1, lo, hi, gain=0.6, gust=(0.3, 1.0), seed=7, pan=0.0):
    n = int((t1 - t0) * FS)
    if n <= 0: return
    y = band(n, lo, hi, seed=seed) * env_gust(n, seed=seed + 1, low=gust[0], high=gust[1])
    add(L, R, t0, y, gain, pan)


# ------------------------------------------------------------------- ornaments
def metal(f0=520, dur=0.5, seed=3, bright=1.0):
    n = int(dur * FS); t = np.arange(n) / FS
    r = np.random.default_rng(seed)
    parts = [1.0, 1.71, 2.43, 3.11, 4.27, 5.91]
    amp = [1.0, 0.62, 0.42, 0.3, 0.18, 0.1]
    y = np.zeros(n, dtype=np.float32)
    for p, a in zip(parts, amp):
        d = np.exp(-t * (5.0 + p * 2.2))
        y += (a * d * np.sin(2 * np.pi * f0 * p * t + r.random() * 6.28)).astype(np.float32)
    att = band(int(0.045 * FS), 1800 * bright, 7000 * bright, seed=seed + 5)
    y[:len(att)] += att * np.linspace(1, 0, len(att)) ** 2 * 0.9
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def bell(f0=1720.0, dur=6.0, seed=11):
    n = int(dur * FS); t = np.arange(n) / FS
    r = np.random.default_rng(seed)
    parts = [(1.0, 1.0, 1.6), (2.01, 0.55, 2.4), (2.94, 0.42, 3.1),
             (4.13, 0.28, 3.8), (5.44, 0.18, 4.6), (6.82, 0.12, 5.4)]
    y = np.zeros(n, dtype=np.float32)
    for p, a, dec in parts:
        y += (a * np.exp(-t * dec) * np.sin(2 * np.pi * f0 * p * t + r.random() * 6.28)).astype(np.float32)
    y *= np.minimum(1.0, t / 0.004)
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def thud(f0=58, dur=0.55, seed=5, grit=0.35):
    n = int(dur * FS); t = np.arange(n) / FS
    body = np.sin(2 * np.pi * f0 * (1 - 0.35 * t / dur) * t) * np.exp(-t * 11)
    g = band(n, 180, 1400, seed=seed) * np.exp(-t * 26) * grit
    y = (body + g).astype(np.float32)
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def step(seed=1, hard=0.5):
    return thud(f0=70, dur=0.35, seed=seed, grit=hard)


def crack(seed=9, dur=0.5, lo=250, hi=4500):
    n = int(dur * FS); t = np.arange(n) / FS
    y = band(n, lo, hi, seed=seed) * np.exp(-t * (9 / dur * 0.5))
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def drink(seed=21, dur=0.9):
    n = int(dur * FS); t = np.arange(n) / FS
    y = band(n, 400, 2600, seed=seed) * (np.exp(-((t - dur * 0.35) ** 2) / 0.02)
                                         + 0.5 * np.exp(-((t - dur * 0.7) ** 2) / 0.03))
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def paper(seed=31, dur=0.6):
    n = int(dur * FS); t = np.arange(n) / FS
    y = band(n, 1200, 6500, seed=seed) * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * t)) * np.exp(-t * 3)
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def breath(seed=41, dur=1.6, bright=900):
    n = int(dur * FS); t = np.arange(n) / FS
    e = np.exp(-((t - dur * 0.45) ** 2) / (2 * (dur * 0.22) ** 2))
    y = band(n, 220, bright, seed=seed) * e
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def drone(dur, f=41.0, gain=1.0, seed=51):
    n = int(dur * FS); t = np.arange(n) / FS
    y = (np.sin(2 * np.pi * f * t) * 1.0
         + 0.55 * np.sin(2 * np.pi * (f * 1.5 + 0.13) * t)
         + 0.3 * np.sin(2 * np.pi * (f * 2.02) * t)
         + 0.22 * np.sin(2 * np.pi * (f * 3.01 + 0.4) * t))
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * 0.045 * t)
    y = (y * lfo).astype(np.float32)
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def riser(dur, f0=120, f1=90, seed=61, lo=60, hi=2000):
    n = int(dur * FS); t = np.arange(n) / FS
    y = band(n, lo, hi, seed=seed) * (t / dur) ** 2.2
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def rumble(dur, seed=71, lo=18, hi=110):
    n = int(dur * FS); t = np.arange(n) / FS
    e = np.minimum(1, t / (dur * 0.25)) * np.exp(-t * 2.2 / dur)
    y = band(n, lo, hi, seed=seed) * e
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def crowd(dur, seed=81):
    n = int(dur * FS); t = np.arange(n) / FS
    y = band(n, 280, 1300, seed=seed)
    mod = 0.4 + 0.6 * np.abs(np.sin(2 * np.pi * (3.1 + 0.7 * np.sin(t * 2)) * t))
    return (y * mod * np.exp(-t * 0.8)).astype(np.float32)


def whoosh(dur, seed=91, up=True):
    n = int(dur * FS); t = np.arange(n) / FS
    a = band(n, 200, 900, seed=seed)
    b = band(n, 900, 4200, seed=seed + 1)
    k = np.clip(t / dur, 0, 1) if up else 1 - np.clip(t / dur, 0, 1)
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    return ((a * (1 - k) + b * k) * e).astype(np.float32)


def hiss(dur, seed=101, lo=1800, hi=9000, dec=3.0):
    n = int(dur * FS); t = np.arange(n) / FS
    y = band(n, lo, hi, seed=seed) * np.exp(-t * dec)
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def drip(seed=111):
    n = int(0.25 * FS); t = np.arange(n) / FS
    f = 900 * np.exp(-t * 14) + 320
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 22)
    return y.astype(np.float32)


def gasp(seed=121, dur=1.1):
    n = int(dur * FS); t = np.arange(n) / FS
    e = np.exp(-((t - 0.25) ** 2) / 0.02) + 0.7 * np.exp(-((t - 0.62) ** 2) / 0.03)
    y = band(n, 300, 2200, seed=seed) * e
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)
