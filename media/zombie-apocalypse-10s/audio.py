"""
audio.py — синтез саундтрека 10 с: гул, ветер, рычание орды, удары в доски,
подъёмы напряжения, финальный «брэм». Всё генерируется кодом.
"""
import math
import wave
import numpy as np

SR = 48000
DUR = 10.0
N = int(SR * DUR)
t = np.arange(N) / SR

IMPACTS = [5.55, 5.95, 6.32, 6.66, 6.95, 7.20, 7.42]
CUTS = [2.60, 5.00, 7.60, 8.60]

rng = np.random.default_rng(2024)


# ── DSP ───────────────────────────────────────────────────────────────────
def lp(x, fc, order=2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    H = 1.0 / np.sqrt(1.0 + (np.maximum(f, 1e-3) / fc) ** (2 * order))
    return np.fft.irfft(X * H, len(x))


def hp(x, fc, order=2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    H = 1.0 / np.sqrt(1.0 + (fc / np.maximum(f, 1e-3)) ** (2 * order))
    return np.fft.irfft(X * H, len(x))


def bp(x, lo, hi, order=2):
    return hp(lp(x, hi, order), lo, order)


def noise(n, seed=None):
    r = np.random.default_rng(seed) if seed is not None else rng
    return r.standard_normal(n)


def env_ad(n, attack, decay, curve=5.0):
    tt = np.arange(n) / SR
    a = np.clip(tt / max(1e-4, attack), 0, 1)
    d = np.exp(-np.clip(tt - attack, 0, None) / max(1e-4, decay) * curve)
    return a * d


def sweep(f0, f1, n, curve=1.0):
    x = np.linspace(0, 1, n) ** curve
    f = f0 + (f1 - f0) * x
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def place(buf, sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= N:
        return
    sig = sig[:N - i]
    l = math.sqrt((1 - pan) / 2)
    r = math.sqrt((1 + pan) / 2)
    buf[0, i:i + len(sig)] += sig * gain * l
    buf[1, i:i + len(sig)] += sig * gain * r


def reverb(x, decay=1.1, wet=0.25, seed=7):
    n_ir = int(SR * decay)
    ir = noise(n_ir, seed) * np.exp(-np.arange(n_ir) / (SR * decay * 0.32))
    ir = lp(ir, 5200, 2)
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    size = 1
    while size < len(x) + n_ir:
        size *= 2
    X = np.fft.rfft(x, size)
    H = np.fft.rfft(ir, size)
    y = np.fft.irfft(X * H, size)[:len(x)]
    return x * (1 - wet) + y * wet


# ── инструменты ───────────────────────────────────────────────────────────
def drone(dur, f0=44.0, gain=1.0):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    sig = np.zeros(n)
    for k, (mul, amp, det) in enumerate([(1.0, 0.55, 0.0), (1.5, 0.28, 0.12),
                                         (2.02, 0.16, -0.09), (3.01, 0.07, 0.2)]):
        lfo = 1 + 0.18 * np.sin(2 * np.pi * (0.13 + k * 0.05) * tt + k)
        sig += amp * np.sin(2 * np.pi * (f0 * mul + det) * tt) * lfo
    # «дыхание» из шума
    breath = bp(noise(n), 80, 900, 2) * 0.22
    sig = sig + breath
    return sig * gain


def hit(gain=1.0, punch=1.0, bright=0.4):
    n = int(1.9 * SR)
    sub = sweep(95 * punch, 34, n, 0.5) * env_ad(n, 0.004, 0.42, 4.2)
    body = bp(noise(n), 90, 1400, 2) * env_ad(n, 0.002, 0.16, 5)
    crack = hp(noise(n), 2600, 1) * env_ad(n, 0.001, 0.035, 6) * bright
    metal = (np.sin(2 * np.pi * 420 * np.arange(n) / SR)
             + 0.6 * np.sin(2 * np.pi * 673 * np.arange(n) / SR)) \
        * env_ad(n, 0.002, 0.10, 6) * 0.12 * bright
    return (sub * 1.0 + body * 0.55 + crack * 0.5 + metal) * gain


def thud(gain=1.0):
    n = int(0.6 * SR)
    low = sweep(120, 55, n, 0.6) * env_ad(n, 0.002, 0.12, 5)
    wood = bp(noise(n), 300, 2400, 2) * env_ad(n, 0.001, 0.07, 6)
    crack = hp(noise(n), 3200, 1) * env_ad(n, 0.001, 0.02, 7)
    return (low * 0.95 + wood * 0.8 + crack * 0.35) * gain


def moan(dur=1.6, f0=104.0, formants=((480, 1.0), (1150, 0.6), (2500, 0.25)),
         seed=1, gain=1.0):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    r = np.random.default_rng(seed)
    vib = 1 + 0.035 * np.sin(2 * np.pi * (4.6 + r.uniform(-1, 1)) * tt)
    glide = 1 - 0.16 * (tt / dur)
    f = f0 * vib * glide
    sig = np.zeros(n)
    for k in range(1, 16):
        fk = k * f
        amp = np.zeros(n)
        for (fc, a) in formants:
            bw = 190.0
            amp += a * np.exp(-((fk - fc) ** 2) / (2 * bw ** 2))
        amp += 0.02 / k
        sig += amp * np.sin(2 * np.pi * np.cumsum(fk) / SR + r.uniform(0, 6.28))
    sig += bp(noise(n, seed + 5), 300, 2600, 2) * 0.10
    # рваная огибающая — как будто не хватает воздуха
    shaky = 0.65 + 0.35 * np.sin(2 * np.pi * 6.2 * tt + r.uniform(0, 6.28))
    env = np.clip(np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 0.8, 0, 1)
    sig = sig * env * shaky
    return sig / (np.max(np.abs(sig)) + 1e-9) * gain


def riser(dur=2.4, gain=1.0, seed=11):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    x = tt / dur
    sw = sweep(120, 900, n, 2.0) * 0.5
    nz = noise(n, seed)
    # шум, «открывающийся» по частоте
    nz = bp(nz, 400, 9000, 2)
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * (2 + 16 * x) * tt)
    sig = (sw * 0.35 + nz * 0.55) * (x ** 2.4) * trem
    return sig * gain


def wind(dur=10.0, gain=1.0, seed=31):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    nz = bp(noise(n, seed), 90, 1700, 2)
    nz = nz / (np.max(np.abs(nz)) + 1e-9)
    lfo = (0.55 + 0.45 * np.sin(2 * np.pi * 0.11 * tt)
           * np.sin(2 * np.pi * 0.037 * tt + 1.2))
    whistle = np.sin(2 * np.pi * (610 + 90 * np.sin(2 * np.pi * 0.08 * tt)) * tt) * 0.05
    return (nz * lfo + whistle) * gain


def boom(gain=1.0):
    n = int(2.6 * SR)
    sub = sweep(58, 26, n, 0.8) * env_ad(n, 0.01, 0.85, 3.4)
    sub2 = sweep(120, 40, n, 0.5) * env_ad(n, 0.005, 0.4, 4)
    air = bp(noise(n), 120, 3000, 2) * env_ad(n, 0.004, 0.25, 5)
    return (sub * 1.2 + sub2 * 0.4 + air * 0.35) * gain


def braam(gain=1.0):
    n = int(2.2 * SR)
    tt = np.arange(n) / SR
    sig = np.zeros(n)
    for f in (55, 82.4, 110, 164.8, 221):
        for d in (-0.6, 0.6):
            sig += np.sin(2 * np.pi * (f + d) * tt) * (55.0 / f) ** 0.5
    sig *= env_ad(n, 0.02, 0.55, 4.0)
    sig = np.tanh(sig * 1.6)
    return sig / (np.max(np.abs(sig)) + 1e-9) * gain


# ── сборка ────────────────────────────────────────────────────────────────
def build(path):
    buf = np.zeros((2, N), np.float32)

    # 1) низкий гул-подушка, дышит по сценам
    d = drone(DUR, 43.0, 1.0)
    env = np.interp(t, [0, 0.7, 2.55, 2.66, 4.9, 5.02, 7.55, 7.64, 8.5, 8.64, 9.5, 10],
                    [0.0, 0.45, 0.62, 0.85, 0.9, 0.62, 0.62, 0.38, 0.38, 0.95, 0.55, 0.0])
    place(buf, d * env, 0, 0.60, 0.0)

    # 2) ветер
    w = wind(DUR, 1.0)
    wenv = np.interp(t, [0, 0.9, 5.0, 7.6, 8.6, 10], [0.0, 0.30, 0.26, 0.12, 0.26, 0.0])
    place(buf, w * wenv, 0, 0.55, 0.18)
    place(buf, w * wenv, 0, 0.45, -0.40)

    # 3) удары на монтажных склейках
    place(buf, hit(1.0, 1.05, 0.25), 2.60, 0.80, 0.0)     # город -> орда
    place(buf, hit(1.0, 0.95, 0.45), 5.00, 0.88, -0.08)   # орда -> коридор
    place(buf, braam(1.0), 8.60, 0.70, 0.0)               # финал -> титр

    # 4) подъёмы напряжения
    place(buf, riser(2.50, 1.0), 0.10, 0.26, 0.22)
    place(buf, riser(2.30, 1.0), 2.66, 0.34, -0.20)
    place(buf, riser(2.40, 1.0), 5.05, 0.38, 0.10)
    place(buf, riser(0.90, 1.0), 7.66, 0.40, 0.0)

    # 5) сцена 1: далёкий вой и одинокие шаги
    for i, (at, dur, f0, g) in enumerate([(0.55, 1.5, 92, 0.22), (1.75, 1.5, 118, 0.18)]):
        place(buf, moan(dur, f0, seed=i + 11, gain=1.0), at, g,
              0.4 if i % 2 else -0.4)
    for i, at in enumerate((0.9, 1.35, 1.85, 2.3)):
        place(buf, thud(0.30), at, 0.34, 0.1 * (-1) ** i)

    # 6) сцена 2: рычание всей орды
    ms = [(2.72, 1.9, 88, 0.34), (3.15, 2.0, 74, 0.30), (3.60, 1.7, 104, 0.28),
          (4.00, 1.9, 82, 0.34), (4.40, 1.6, 126, 0.26), (4.70, 1.4, 96, 0.30)]
    for i, (at, dur, f0, g) in enumerate(ms):
        place(buf, moan(dur, f0, seed=i + 3, gain=1.0), at, g,
              0.38 if i % 2 else -0.38)
        place(buf, moan(dur * 0.85, f0 * 1.6, seed=i + 40, gain=0.75), at + 0.12,
              g * 0.55, -0.55 if i % 2 else 0.55)
    # тяжёлые шаги орды
    for i, at in enumerate(np.arange(2.8, 5.0, 0.28)):
        place(buf, thud(0.45 + 0.12 * (i % 2)), float(at), 0.34,
              0.30 * math.sin(i * 1.7))

    # 7) сцена 3: шаги в коридоре, нарастание
    for i, at in enumerate(np.arange(5.08, 7.55, 0.22)):
        k = (at - 5.0) / 2.6
        place(buf, thud(0.55 + 0.5 * k), float(at), 0.30 + 0.22 * k,
              0.34 * math.sin(i * 1.3))
    for i, (at, dur, f0, g) in enumerate([(5.4, 2.0, 70, 0.30), (6.1, 2.0, 62, 0.34),
                                          (6.9, 1.9, 58, 0.36)]):
        place(buf, moan(dur, f0, seed=i + 70, gain=1.0), at, g, 0.45 if i % 2 else -0.45)

    # 8) сцена 4: сердцебиение
    for i, at in enumerate((7.70, 7.88, 8.06, 8.24, 8.42)):
        g = 0.42 - i * 0.02
        hb = sweep(70, 42, int(0.20 * SR), 0.7) * env_ad(int(0.20 * SR), 0.004, 0.08, 5)
        place(buf, hb, at, g, 0.0)
        place(buf, hb * 0.6, at + 0.15, g, 0.0)

    # 9) финальный удар и хвост
    place(buf, boom(1.0), 8.60, 0.95, 0.0)
    place(buf, boom(0.55), 8.60, 0.45, 0.35)
    tail = bp(noise(int(1.6 * SR), 909), 80, 2000, 2) * env_ad(int(1.6 * SR), 0.02, 0.6, 3)
    place(buf, tail, 8.62, 0.15, 0.0)

    # 10) реверб и мастеринг
    out = np.vstack([reverb(buf[0], 1.35, 0.30, 3), reverb(buf[1], 1.35, 0.30, 4)])
    out = np.tanh(out * 1.12)
    fade = np.interp(t, [0, 0.12, 9.55, 9.98], [0.0, 1.0, 1.0, 0.0])
    out *= fade
    out /= (np.max(np.abs(out)) + 1e-9)
    out *= 0.90

    data = (out.T * 32767).astype(np.int16)
    with wave.open(path, "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(data.tobytes())
    return path


if __name__ == "__main__":
    build("/tmp/audio_test.wav")
    print("ok")
