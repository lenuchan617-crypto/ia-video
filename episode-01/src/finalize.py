# -*- coding: utf-8 -*-
"""Финальный проход: грейд + зерно + виньетка + субтитры + звук."""
import os, sys, subprocess, argparse, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shots import TOTAL, FPS, W, H

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
BUILD = os.path.join(ROOT, "build")
FFMPEG = "/home/user/.venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=os.path.join(OUT, "video_silent.mp4"))
    ap.add_argument("--audio", default=os.path.join(ROOT, "build", "audio", "master.wav"))
    ap.add_argument("--crf", default="29")
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--name", default="Shadow_Slave_E01_Cherished_Light.mp4")
    ap.add_argument("--nosubs", action="store_true")
    ap.add_argument("--nograin", action="store_true")
    a = ap.parse_args()

    subs = os.path.join(BUILD, "subs.ass").replace("\\", "/")
    vf = [
        # грейд: приглушённость, холодные тени, тёплые света
        "eq=contrast=1.06:saturation=0.86:brightness=-0.012:gamma=0.99",
        "colorbalance=rs=-0.02:gs=0.0:bs=0.035:rh=0.02:bh=-0.03",
        "curves=r=0/0 0.28/0.25 0.72/0.76 1/1:b=0/0.02 0.3/0.285 0.72/0.75 1/0.98",
        "vignette=angle=PI/4.6:mode=forward",
    ]
    if not a.nograin:
        vf.append("noise=alls=7:allf=t")
    if not a.nosubs:
        vf.append(f"subtitles={subs}:fontsdir=/usr/share/fonts/truetype/dejavu")
    vf.append("format=yuv420p")

    cmd = [FFMPEG, "-y", "-i", a.video, "-i", a.audio,
           "-vf", ",".join(vf),
           "-c:v", "libx264", "-preset", a.preset, "-crf", a.crf,
           "-profile:v", "high", "-level", "4.0", "-r", str(FPS),
           "-x264-params", "keyint=48:min-keyint=24:scenecut=0:aq-mode=3",
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
           "-shortest", "-movflags", "+faststart",
           os.path.join(OUT, a.name)]
    print(" ".join(cmd[:3]), "...")
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-2500:]); raise SystemExit("ffmpeg fail")
    p = os.path.join(OUT, a.name)
    dur = subprocess.run([FFMPEG, "-v", "error",
                          "-i", p, "-hide_banner",
                          "json", p], capture_output=True, text=True)
    print(p, os.path.getsize(p) / 1e6, "MB")
    print(dur.stdout)


if __name__ == "__main__":
    main()
