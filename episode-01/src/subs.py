# -*- coding: utf-8 -*-
"""Генерация .ass субтитров и титров."""
import os, sys
from lines import LINES, SPEAKERS, TITLE_CARD

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 720


def t_ass(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


HEAD = f"""[Script Info]
Title: Shadow Slave — Episode 1
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dialog,DejaVu Sans,27,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0.3,0,1,1.6,1.4,2,60,60,42,1
Style: VO,DejaVu Sans,27,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,-1,0,0,100,100,0.3,0,1,1.6,1.4,2,60,60,42,1
Style: Title,DejaVu Serif,64,&H00E8E8E4,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,7.0,0,1,0.0,3.0,5,60,60,0,1
Style: Sub,DejaVu Serif,24,&H00C0C0BC,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,4.0,0,1,0.0,2.0,5,60,60,0,1
Style: Note,DejaVu Sans,19,&H00909090,&H00FFFFFF,&H00000000,&H00000000,0,-1,0,0,100,100,0.5,0,1,1.0,0.8,2,60,60,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build(durs=None, out=None):
    """durs: {id: фактическая длительность озвучки} — уточняет, когда гаснет субтитр."""
    ev = []
    for t0, t1, txt in TITLE_CARD:
        st = "Title" if txt.isupper() and len(txt) < 20 else "Sub"
        y = 300 if st == "Title" else (368 if t0 < 100 else 330)
        ev.append(f"Dialogue: 1,{t_ass(t0)},{t_ass(t1)},{st},,0,0,0,,"
                  f"{{\\an5\\pos({W//2},{y})\\fad(600,700)}}{txt}")
    for lid, spk, text, t0, dur, kind in LINES:
        d = (durs or {}).get(lid, dur)
        st = "VO" if kind == "vo" else "Dialog"
        col = SPEAKERS[spk]["col"]
        fad = 220 if kind != "god" else 700
        ev.append(f"Dialogue: 0,{t_ass(t0)},{t_ass(t0 + d + 0.55)},{st},"
                  f"{spk},0,0,0,,{{\\fad({fad},{fad})\\c{col}}}{text}")
    body = HEAD + "\n".join(ev) + "\n"
    out = out or os.path.join(ROOT, "build", "subs.ass")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(body)
    return out


if __name__ == "__main__":
    import json
    d = {}
    p = os.path.join(ROOT, "build", "durs.json")
    if os.path.exists(p):
        d = json.load(open(p))
    print("subs:", build(d))
