# -*- coding: utf-8 -*-
"""Партитура эпизода: события по таймлайну 0:00-13:00."""
import numpy as np, wave, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sfx import *   # noqa

L = np.zeros(N, dtype=np.float32)
R = np.zeros(N, dtype=np.float32)


DUR_REQ = ("drone", "riser", "rumble", "crowd", "whoosh")


def S(t, name, gain=0.35, pan=0.0, dur=None, **kw):
    if name in DUR_REQ and dur is None:
        dur, gain = gain, 0.32          # 3-й позиционный аргумент = длительность
    if dur is not None:
        kw["dur"] = dur
    add(L, R, t, globals()[name](**kw), gain, pan)


def B(t0, t1, lo, hi, gain=0.2, gust=(0.3, 1.0), seed=7, pan=0.0):
    addbed(L, R, t0, t1, lo, hi, gain, gust, seed, pan)


# ============================================================ СЦЕНА 1 — кофе
B(0, 112, 55, 520, 0.30, (0.25, 1.0), 11, 0.0)        # серый утренний ветер
B(0, 112, 90, 190, 0.10, (0.6, 1.0), 12, -0.2)        # гул города
B(0, 112, 900, 3000, 0.030, (0.4, 1.0), 13, 0.2)      # далёкая жесть/птицы
S(0.3, "drone", 2.0, 0, f=37.5)                        # суб-тон с первой секунды
S(18.2, "paper", 0.35, 0.1, seed=31)                   # стакан в руках
S(19.6, "drink", 0.30, 0.05)                           # глоток
S(21.4, "drink", 0.18, 0.05)
S(24.0, "breath", 0.16, 0.0)                           # выдох
# офицер подходит: шаги 25.0-27.4
for i, t in enumerate(np.arange(25.0, 27.6, 0.62)):
    S(float(t), "step", 0.22 + 0.03 * (i % 2), 0.35, seed=200 + i, hard=0.35)
S(33.9, "breath", 0.14, 0.0, dur=1.9, seed=44)
S(46.0, "drone", 3.2, 0, f=44.0)                       # флешбэк: тон памяти
B(46, 63, 400, 6000, 0.06, (0.5, 1.0), 14, 0.0)        # «дождь» памяти
S(48.0, "whoosh", 0.16, 0.0, dur=1.2, up=False)
S(60.0, "whoosh", 0.12, 0.0, dur=1.4, up=True)
S(66.2, "paper", 0.28, 0.1, seed=33)                   # ставит стакан
S(66.6, "metal", 0.10, 0.15, f0=340, dur=0.35, seed=7)  # скрип скамейки
for i, t in enumerate(np.arange(78.0, 95.0, 0.66)):
    S(float(t), "step", 0.16, -0.25, seed=300 + i, hard=0.25)
B(96, 110, 1200, 6000, 0.022, (0.3, 1.0), 15, 0.0)
S(104.0, "riser", 0.10, 0.0, dur=5.0, lo=80, hi=900)   # затяжной вход в темноту

# ============================================================ СЦЕНА 2 — кресло
B(110, 200, 45, 200, 0.16, (0.7, 1.0), 16, 0.0)
S(110.5, "thud", 0.35, 0.0, f0=45, dur=1.4)            # дверь подвала
S(112.0, "hiss", 0.10, 0.0, dur=1.0, lo=2000, hi=9000, dec=2.0)
# лампа: гул 100 Гц с мерцанием
t_h = 110.0
hum = 0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 0.21 * np.arange(int(90 * FS)) / FS))
hum[::int(FS * 1.7)] *= 0.15
hum = boxsmooth(hum, 900)
hz = (np.sin(2 * np.pi * 100 * np.arange(len(hum)) / FS) * 0.7 +
      np.sin(2 * np.pi * 200 * np.arange(len(hum)) / FS) * 0.3).astype(np.float32)
add(L, R, t_h, hz * hum, 0.075, 0.0)
for i, t in enumerate(np.arange(115.0, 129.0, 0.7)):
    S(float(t), "step", 0.30, 0.25, seed=400 + i, hard=0.55)     # грузят
S(128.3, "metal", 0.30, 0.1, f0=410, dur=0.45, seed=17)          # пряжка
S(131.0, "metal", 0.26, -0.1, f0=470, dur=0.35, seed=18)
S(133.6, "metal", 0.30, 0.05, f0=380, dur=0.5, seed=19)
S(136.2, "metal", 0.34, 0.0, f0=520, dur=0.7, seed=20)           # финальный щелчок
S(140.0, "breath", 0.20, 0.0, dur=2.2, seed=45)
S(146.0, "breath", 0.16, 0.0, dur=2.6, seed=46)
S(144.0, "drone", 6.0, 0, f=36.0)
# сердцебиение
for t in np.arange(150.0, 176.0, 1.55):
    S(float(t), "thud", 0.30, 0.0, f0=55, dur=0.45, seed=500 + int(t))
    S(float(t) + 0.30, "thud", 0.18, 0.0, f0=48, dur=0.40, seed=600 + int(t))
S(182.0, "riser", 0.16, 0.0, dur=14.0, lo=40, hi=700)
S(196.5, "hiss", 0.09, 0.0, dur=3.0, lo=3000, hi=12000, dec=0.8)

# ============================================================ СЦЕНА 3 — цепи
B(200, 332, 180, 1500, 0.24, (0.2, 1.0), 21, 0.0)       # холодный горный ветер
B(200, 332, 30, 120, 0.16, (0.6, 1.0), 22, 0.0)
S(203.0, "drone", 30.0, 0, f=31.0)
# караван: шаги + ритм цепей
for t in np.arange(202.0, 330.0, 2.15):
    S(float(t), "metal", 0.10, float(np.clip(np.sin(t * 0.7) * 0.6, -0.6, 0.6)),
      f0=float(430 + 90 * np.sin(t)), dur=0.55, seed=int(t * 13) % 9999)
for i, t in enumerate(np.arange(203.0, 330.0, 0.74)):
    S(float(t), "step", 0.10 + 0.05 * (i % 3 == 0), -0.3, seed=700 + i % 40, hard=0.7)
S(214.0, "breath", 0.14, 0.0, dur=2.0, seed=47)          # пар изо рта
S(222.0, "breath", 0.12, 0.0, dur=2.2, seed=48)
S(228.0, "whoosh", 0.13, -0.4, dur=2.2, up=True)         # порыв
S(244.0, "riser", 0.12, 0.0, dur=8.0, lo=60, hi=600)
S(300.0, "rumble", 0.30, 0.5, dur=4.0, seed=72)          # камень наверху
S(316.0, "rumble", 0.22, -0.4, dur=5.0, seed=73)

# ============================================================ СЦЕНА 4 — Король
S(330.2, "rumble", 0.55, 0.0, dur=6.0, seed=74)
S(330.4, "crack", 0.35, 0.3, seed=90, dur=0.6)
S(331.2, "crack", 0.30, -0.3, seed=91, dur=0.5)
S(333.0, "crowd", 0.30, 0.0, dur=3.0, seed=82)           # паника
S(336.0, "crack", 0.30, 0.4, seed=92, dur=0.4)
S(338.0, "rumble", 0.35, -0.2, dur=3.0, seed=75)
S(341.0, "crowd", 0.22, 0.2, dur=2.4, seed=83)
B(330, 452, 200, 1800, 0.20, (0.3, 1.0), 23, 0.0)
B(330, 452, 25, 90, 0.20, (0.7, 1.0), 24, 0.0)
# появление твари: инфразвуковой «выдох»
S(345.0, "drone", 14.0, 0, f=27.0)
S(345.2, "riser", 0.26, 0.0, dur=6.0, lo=25, hi=400)
S(349.0, "thud", 0.55, 0.0, f0=38, dur=1.6, seed=77)     # шаг
S(353.0, "thud", 0.45, 0.1, f0=34, dur=1.8, seed=78)
S(357.0, "crack", 0.24, 0.0, seed=93, dur=1.0, lo=150, hi=3000)
S(360.0, "breath", 0.30, 0.0, dur=3.0, seed=49, bright=1400)
for i, t in enumerate(np.arange(361.0, 380.0, 0.42)):
    S(float(t), "metal", 0.09, 0.0, f0=float(300 + 120 * np.sin(t * 3)),
      dur=0.4, seed=int(t * 7) % 999)
for t in np.arange(398.0, 446.0, 1.15):
    S(float(t), "thud", 0.20, 0.0, f0=52, dur=0.35, seed=800 + int(t))
# тишина после
S(430.0, "hiss", 0.055, 0.0, dur=18.0, lo=3800, hi=11000, dec=0.10)  # тиннитус
S(440.0, "drone", 12.0, 0, f=33.0)

# ============================================================ СЦЕНА 5 — яд/колокол
B(450, 592, 220, 1600, 0.16, (0.2, 0.9), 25, 0.0)
B(450, 592, 30, 110, 0.10, (0.6, 1.0), 26, 0.0)
S(452.0, "breath", 0.16, 0.0, dur=3.0, seed=50)
S(463.0, "paper", 0.10, 0.0, seed=34)
S(470.0, "hiss", 0.05, 0.0, dur=1.4, lo=700, hi=5000, dec=3.0)   # вода плещет
S(471.2, "drink", 0.14, 0.0, seed=22)
for t in (476.0, 479.0, 482.4, 486.0):                            # кашель
    S(t, "crack", 0.22, 0.15, seed=int(t), dur=0.35, lo=180, hi=2200)
S(490.0, "thud", 0.28, 0.2, f0=62, dur=0.6, seed=79)              # тело падает
S(497.0, "breath", 0.12, 0.0, dur=3.2, seed=51)
S(504.0, "bell", 0.34, 0.1, f0=1720.0, dur=7.0, seed=12)          # первый звон
S(512.0, "bell", 0.20, -0.15, f0=1720.0, dur=6.0, seed=13)
S(520.0, "bell", 0.26, 0.15, f0=1610.0, dur=7.0, seed=14)
B(520, 592, 4000, 12000, 0.020, (0.3, 1.0), 27, 0.0)
S(532.0, "drone", 16.0, 0, f=29.0)
S(545.0, "thud", 0.50, 0.0, f0=33, dur=2.0, seed=80)              # тяжёлый шаг
S(556.0, "thud", 0.55, -0.1, f0=31, dur=2.2, seed=81)
S(568.0, "thud", 0.60, 0.1, f0=29, dur=2.4, seed=82)
S(570.0, "crack", 0.18, -0.3, seed=94, dur=1.2, lo=300, hi=4000)
S(580.0, "riser", 0.22, 0.0, dur=10.0, lo=40, hi=800)
S(586.0, "paper", 0.14, 0.0, seed=35)

# ============================================================ СЦЕНА 6 — оценка
B(590, 700, 150, 2400, 0.18, (0.25, 1.0), 28, 0.0)
S(590.2, "whoosh", 0.20, 0.0, dur=3.0, up=True)
S(592.0, "drone", 40.0, 0, f=26.0)
for t in np.arange(594.0, 640.0, 1.35):                            # капли крови
    S(float(t), "drip", 0.20, float(np.sin(t) * 0.4), seed=int(t) % 500)
S(598.0, "crack", 0.10, 0.2, seed=95, dur=0.6, lo=400, hi=3000)
S(604.0, "breath", 0.18, 0.0, dur=2.6, seed=52)
for i, t in enumerate(np.arange(636.0, 664.0, 2.4)):               # шаги твари
    S(float(t), "thud", 0.40 + 0.03 * i, 0.0, f0=30, dur=2.2, seed=900 + i)
S(660.0, "riser", 0.30, 0.0, dur=12.0, lo=60, hi=1400)
S(662.0, "whoosh", 0.30, 0.0, dur=2.5, up=False)
S(668.0, "rumble", 0.60, 0.0, dur=8.0, seed=76)                    # тени рвут
S(668.4, "crack", 0.40, 0.2, seed=96, dur=1.2, lo=80, hi=6000)
S(672.0, "drone", 26.0, 0, f=34.0)
S(674.0, "whoosh", 0.24, 0.0, dur=6.0, up=True)                    # мир растворяется
B(672, 700, 3000, 12000, 0.030, (0.2, 1.0), 29, 0.0)               # «звёздный» воздух
S(688.0, "bell", 0.16, 0.0, f0=2300.0, dur=9.0, seed=15)

# ============================================================ СЦЕНА 7 — после
B(700, 780, 50, 400, 0.10, (0.5, 1.0), 30, 0.0)
hz2 = (np.sin(2 * np.pi * 120 * np.arange(int(80 * FS)) / FS) * 0.8 +
       np.sin(2 * np.pi * 240 * np.arange(int(80 * FS)) / FS) * 0.2).astype(np.float32)
add(L, R, 700.0, hz2, 0.030, 0.0)                                   # люминесцентный гул
S(701.5, "thud", 0.30, 0.0, f0=48, dur=1.0, seed=83)                # капсула
S(702.0, "hiss", 0.14, 0.0, dur=2.6, lo=1200, hi=9000, dec=1.4)     # шипение
for i, t in enumerate(np.arange(705.0, 724.0, 0.68)):
    S(float(t), "step", 0.18 + 0.04 * (i % 2), 0.0, seed=1000 + i, hard=0.3)
S(716.0, "metal", 0.06, 0.3, f0=600, dur=0.3, seed=22)
S(736.0, "paper", 0.08, 0.2, seed=36)
for i, t in enumerate(np.arange(744.0, 762.0, 0.66)):
    S(float(t), "step", 0.14, 0.2, seed=1100 + i, hard=0.25)
S(760.0, "riser", 0.14, 0.0, dur=8.0, lo=45, hi=500)
S(766.0, "drone", 14.0, 0, f=31.0)
S(774.0, "hiss", 0.06, 0.0, dur=6.0, lo=5000, hi=12000, dec=0.4)

# ------------------------------------------------------------------- master
np.clip(L, -4, 4, out=L); np.clip(R, -4, 4, out=R)
peak = max(np.max(np.abs(L)), np.max(np.abs(R)))
L *= 0.50 / peak; R *= 0.50 / peak
# мягкая компрессия пиков
for a in (L, R):
    np.tanh(a * 1.6, out=a); a *= 0.62

out = os.path.join(AUD, "bed.wav")
os.makedirs(AUD, exist_ok=True)
pcm = np.empty((len(L), 2), dtype=np.int16)
pcm[:, 0] = np.clip(L * 32767, -32768, 32767).astype(np.int16)
pcm[:, 1] = np.clip(R * 32767, -32768, 32767).astype(np.int16)
with wave.open(out, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(FS)
    w.writeframes(pcm.tobytes())
rms = float(np.sqrt(np.mean((L.astype(np.float64) ** 2 + R.astype(np.float64) ** 2) / 2)))
print(f"bed.wav: {DUR:.1f}s  RMS={20*np.log10(rms+1e-12):.1f} dBFS  "
      f"peak={20*np.log10(max(np.max(np.abs(L)),np.max(np.abs(R)))+1e-12):.1f} dBFS")
