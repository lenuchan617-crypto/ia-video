# -*- coding: utf-8 -*-
"""Слой атмосферы на весь эпизод: пыль в лучах, пепел, позёмка, искры.
Пишется как видео на чёрном фоне; в финальном проходе накладывается режимом screen."""
import numpy as np, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = "/home/user/.venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
FPS, DUR = 24, 780.0
CW, CH = 640, 360                      # рабочее разрешение (потом апскейл — частицы мягче)
NF = int(DUR * FPS)
rng = np.random.default_rng(4242)

# эмиттеры: (число, окно старт, окно конец, режим)
EMITTERS = [
    (110, 0, 780, "mote"),        # пылинки в воздухе — весь фильм
    (70, 200, 340, "blow"),       # позёмка на перевале
    (330, 330, 455, "ash"),       # пепел и обломки в панике
    (60, 112, 205, "mote2"),      # тяжёлая пыль подвала
    (260, 588, 702, "ash2"),      # пепел на вершине
    (70, 620, 702, "ember"),      # искры у храма
    (40, 700, 780, "mote2"),      # пыль коридора
]


class Pop:
    def __init__(self, n, t0, t1, mode):
        self.n, self.t0, self.t1, self.mode = n, t0, t1, mode
        self.x = rng.uniform(0, CW, n)
        self.y = rng.uniform(0, CH, n)
        self.sp = rng.uniform(0.25, 1.0, n)
        self.ph = rng.uniform(0, 6.28, n)
        self.al = rng.uniform(0.25, 1.0, n)
        self.sz = rng.choice([0, 0, 0, 1, 1, 2], n)   # 0->1px, 1->2px, 2->3px footprint

    def step(self, dt, t):
        m = self.mode
        if m in ("mote", "mote2"):
            k = 6.0 if m == "mote" else 3.0
            self.x += (np.sin(t * 0.4 + self.ph) * 0.35 + 0.10) * dt * FPS * self.sp * 0.35
            self.y += (np.cos(t * 0.33 + self.ph) * 0.30 - k * 0.02) * dt * FPS * self.sp * 0.35
        elif m == "blow":
            self.x += 3.4 * self.sp * dt * FPS * 0.35
            self.y += np.sin(t * 1.7 + self.ph) * 0.25
        elif m in ("ash", "ash2"):
            self.x += (0.55 + np.sin(t * 0.9 + self.ph) * 0.5) * self.sp
            self.y += (0.30 if m == "ash2" else 0.75) * self.sp
        elif m == "ember":
            self.x += np.sin(t * 1.3 + self.ph) * 0.35
            self.y -= 0.55 * self.sp
        # перерождение
        self.x = np.where(self.x > CW + 4, -4, self.x)
        self.x = np.where(self.x < -4, CW + 4, self.x)
        self.y = np.where(self.y > CH + 4, -4, self.y)
        self.y = np.where(self.y < -4, CH + 4, self.y)

    def weight(self, t):
        if t < self.t0 or t > self.t1:
            return 1.0 if self.mode in ("mote", "mote2") else 0.0
        if self.mode in ("mote", "mote2"):
            return 1.0
        # мягкое появление/уход у краёв окна
        a = min(1.0, (t - self.t0) / 6.0)
        b = min(1.0, (self.t1 - t) / 6.0)
        return max(0.0, min(a, b))


POPS = [Pop(*e) for e in EMITTERS]

# цвет и профиль по типу
COL = {"mote": (1.00, 0.96, 0.90), "mote2": (0.90, 0.92, 1.00),
       "blow": (0.95, 0.92, 0.86), "ash": (0.88, 0.88, 0.92),
       "ash2": (0.95, 0.93, 0.90), "ember": (1.00, 0.66, 0.30)}

KERNEL = np.array([0.35, 0.7, 1.0, 0.7, 0.35], dtype=np.float32)
K2 = np.outer(KERNEL, KERNEL)


def splat(buf, xs, ys, amp, size):
    """Добавляет частицы в буфер (5x5 гауссово ядро, векторно)."""
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            w = K2[dy + 2, dx + 2]
            xi = (xs.astype(np.int32) + dx)
            yi = (ys.astype(np.int32) + dy)
            ok = (xi >= 0) & (xi < CW) & (yi >= 0) & (yi < CH)
            if not ok.any():
                continue
            np.add.at(buf, (yi[ok], xi[ok]), (amp[ok] * w))


def main():
    cmd = [FFMPEG, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{CW}x{CH}", "-r", str(FPS), "-i", "-",
           "-vf", "scale=1280:720:flags=bicubic,format=yuv420p",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-x264-params", "keyint=48:scenecut=0", "-an",
           os.path.join(ROOT, "build", "particles.mp4")]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    dt = 1.0 / FPS
    for f in range(NF):
        t = f / FPS
        buf = np.zeros((CH, CW), dtype=np.float32)
        cb = np.zeros(3, dtype=np.float32)
        wsum = 1e-6
        for pop in POPS:
            w = pop.weight(t)
            if w <= 0.01:
                continue
            pop.step(dt, t)
            flick = 1.0 if pop.mode != "ember" else (0.55 + 0.45 * np.sin(t * 9 + pop.ph) ** 2)
            amp = pop.al * w * flick * (0.55 if pop.mode in ("mote", "mote2") else 0.9)
            amp = amp * np.where(pop.sz == 0, 0.9, np.where(pop.sz == 1, 1.6, 2.4))
            splat(buf, pop.x, pop.y, amp.astype(np.float32), pop.sz)
            cb += np.array(COL[pop.mode], dtype=np.float32) * float(w)
            wsum += float(w)
        out = np.clip(buf * 26.0, 0, 255)
        frame = np.repeat(out[:, :, None], 3, axis=2) * (cb / wsum)[None, None, :]
        p.stdin.write(frame.astype(np.uint8).tobytes())
        if f % 2400 == 0:
            print(f"  {t:6.1f}s / {DUR:.0f}s", flush=True)
    p.stdin.close()
    p.wait()
    print("particles.mp4 готов", p.returncode)


if __name__ == "__main__":
    main()
