# -*- coding: utf-8 -*-
"""Разбивка 80 «битов» на ~240 монтажных склеек (2-4 сек) с интеркадрами.

Ключевая идея: аниме — это не один рисунок на 10 секунд, а смена кадров
каждые 2-4 секунды, с чередованием планов: крупный -> деталь -> общий.
Каждая склейка получает собственную кадровую рамку и собственное движение.
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shots import SCENES, FPS

# средняя длина склейки по сценам (сек). Сцена 4 (паника) — рваный монтаж.
TARGET = {"1": 2.9, "2": 3.3, "3": 2.9, "4": 1.6, "5": 2.5, "6": 3.2, "7": 2.6}

# пулы планов для интеркадров (только внутри своей сцены — чтобы не рвать пространство)
POOLS = {
    "1": ["a1_street_wide", "a2_bench_sunny", "a3_eyes", "a4_cup", "a7_stand"],
    "2": ["b1_basement", "b2_strapped", "b3_strap", "b4_bulb"],
    "3": ["c1_road_wide", "c2_shackles", "c3_scholar", "c4_mountain", "c6_berries"],
    "4": ["d1_panic", "d2_king_reveal", "d3_kill", "d4_hide", "d6_run", "d7_king_head"],
    "5": ["e1_dawn", "e2_hero", "e3_collapse", "e5_bell", "e6_silhouette"],
    "6": ["f1_temple", "f2_crawl", "d2_king_reveal", "f4_shadows", "f5_stars", "f6_eyes_final"],
    "7": ["g1_corridor", "g2_jet", "g3_mirror", "g4_back_corridor"],
}

# биты, которым нельзя подмешивать чужой план (интимные / аффективные кадры)
NO_IC = {(1, 7), (5, 9), (5, 11), (6, 7), (6, 8), (6, 9), (6, 10), (7, 6), (7, 7), (2, 6)}

# кадровые рамки внутри одного плейта: (зум, сдвиг cx, сдвиг cy)
FRAMES = [
    (1.00, 0.00, 0.00),
    (1.30, 0.10, -0.05),
    (1.14, -0.13, 0.07),
    (1.52, 0.06, 0.10),
    (1.22, -0.05, -0.10),
]

# типы микродвижения внутри склейки (амплитуда намеренно маленькая — 3 сек не хватает на длинный проезд)
MOVES = ["push", "pull", "panL", "panR", "tiltU", "hold"]


def ease(u):
    """smoothstep-строка для выражений ffmpeg."""
    return f"(3*{u}*{u}-2*{u}*{u}*{u})"


def build():
    cuts, t_frames = [], 0
    for sid, title, s0, s1, shots in SCENES:
        target = TARGET[sid]
        pool = POOLS[sid]
        for bi, (plate, dur, cam, opt) in enumerate(shots, 1):
            total_f = int(round(dur * FPS))
            n = max(1, int(round(dur / target)))
            # режем на n частей, поровну, но не короче 1.1 сек
            n = min(n, max(1, int(dur / 1.1)))
            base = total_f // n
            rem = total_f - base * n
            for k in range(n):
                f = base + (1 if k < rem else 0)
                # какой плейт
                if (sid, bi) in NO_IC or k == 0:
                    pl = plate
                else:
                    cand = [p for p in pool if p != plate]
                    pl = cand[(bi * 3 + k) % len(cand)] if cand else plate
                z, dx, dy = FRAMES[(bi + k) % len(FRAMES)]
                mv = MOVES[(bi * 2 + k) % len(MOVES)]
                cuts.append(dict(scene=sid, beat=bi, k=k, plate=pl,
                                 frames=f, zoom=z * (cam[0] ** 0.35), off=(dx, dy),
                                 move=mv, shake=(sid == "4") or (sid == "6" and bi >= 5),
                                 note=opt.get("note", ""), fade_in=opt.get("fade_in", 0.0) if k == 0 else 0.0,
                                 fade_out=opt.get("fade_out", 0.0) if k == n - 1 else 0.0))
                t_frames += f
    for c in cuts:
        c["start"] = c.get("start", 0)
    # абсолютные таймкоды
    t = 0.0
    for c in cuts:
        c["t"] = t
        t += c["frames"] / FPS
    return cuts, t


CUTS, TOTAL = build()


if __name__ == "__main__":
    from collections import Counter
    print(f"склеек: {len(CUTS)}   суммарно: {TOTAL:.3f}s ({int(TOTAL//60)}:{TOTAL%60:06.3f})")
    assert abs(TOTAL - 780.0) < 1e-6, TOTAL
    for sid, *_ in SCENES:
        cs = [c for c in CUTS if c["scene"] == sid]
        d = [c["frames"] / FPS for c in cs]
        print(f"  сцена {sid}: {len(cs):3d} склеек, средняя {sum(d)/len(d):4.2f}s, "
              f"мин {min(d):.2f}, макс {max(d):.2f}")
    print("плейтов задействовано:", len(Counter(c["plate"] for c in CUTS)))
    print("OK: 13:00 ровно")
