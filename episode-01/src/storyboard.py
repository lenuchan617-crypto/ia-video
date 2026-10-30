# -*- coding: utf-8 -*-
"""Генерация storyboard.md из единого источника (shots.py + lines.py)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shots import SCENES, SHOTS, TOTAL, FPS
from cuts import CUTS
from lines import LINES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tc(s):
    return f"{int(s//60):02d}:{s%60:06.3f}".replace(".", ":")


def tc2(s):
    m = int(s // 60); sec = s - m * 60
    return f"{m:02d}:{sec:05.2f}"


def move_name(cam):
    z0, z1, cx0, cy0, cx1, cy1 = cam
    if abs(z1 - z0) > 0.02 and abs(cx1 - cx0) < 0.02 and abs(cy1 - cy0) < 0.02:
        return "наезд" if z1 > z0 else "отъезд"
    if abs(cx1 - cx0) > 0.03 and abs(z1 - z0) < 0.02:
        return "панорама →" if cx1 > cx0 else "панорама ←"
    if abs(cy1 - cy0) > 0.03 and abs(z1 - z0) < 0.02:
        return "тилт ↓" if cy1 > cy0 else "тилт ↑"
    return "дрейф"


def main():
    lines_out = []
    a = lines_out.append
    a("# РАСКАДРОВКА — «Теневой раб», Эпизод 1\n")
    a(f"**Длительность:** 13:00.000 · **Склеек:** {len(CUTS)} · "
      f"**fps:** {FPS} · **кадр:** 1280×720 (16:9)\n")
    a("Монтаж: средняя склейка 2.6 с. Каждая склейка — своя кадровая рамка внутри плейта "
      "(зум/сдвиг), своё микродвижение камеры (push / pull / pan / tilt), «кипение» кадра "
      "(субпиксельная дрожь линий) и, в сцене 4, тряска на ударах. Интеркадры — соседние "
      "планы той же сцены.\n")
    li = 0
    for sid, title, s0, s1, shots in SCENES:
        a(f"\n## Сцена {sid}. {title}\n")
        a(f"*{tc2(s0)} — {tc2(s1)} · {s1-s0:.0f} сек · {len(shots)} шотов*\n")
        a("| # | TC | Длит. | Плейт | Кадр (зум) | Движение | Комментарий |")
        a("|---|---|---|---|---|---|---|")
        cs = [c for c in CUTS if c["scene"] == sid]
        for i, c in enumerate(cs, 1):
            a(f"| {sid}.{i} | {tc2(c['t'])} | {c['frames']/FPS:.2f} | {c['plate']} | "
              f"{c['zoom']:.2f} | {c['move']} | {c['note']} |")
        ls = [l for l in LINES if s0 <= l[3] < s1]
        if ls:
            a("\n**Реплики в сцене**\n")
            a("| TC | Кто | Текст |")
            a("|---|---|---|")
            for lid, spk, text, t0, d, kind in ls:
                tag = " (за кадром)" if kind == "vo" else ""
                a(f"| {tc2(t0)} | {spk}{tag} | {text} |")
    txt = "\n".join(lines_out) + "\n"
    with open(os.path.join(ROOT, "storyboard.md"), "w", encoding="utf-8") as f:
        f.write(txt)
    print("storyboard.md:", len(txt), "символов")


if __name__ == "__main__":
    main()
