# -*- coding: utf-8 -*-
"""Финальный проход v2: грейд + атмосфера (screen) + зерно + субтитры + звук."""
import os, sys, subprocess, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
BUILD = os.path.join(ROOT, "build")
FFMPEG = "/home/user/.venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=os.path.join(OUT, "video_silent_v2.mp4"))
    ap.add_argument("--particles", default=os.path.join(BUILD, "particles.mp4"))
    ap.add_argument("--audio", default=os.path.join(BUILD, "audio", "master.wav"))
    ap.add_argument("--crf", default="28")
    ap.add_argument("--preset", default="veryfast")
    ap.add_argument("--name", default="_final_v2.mp4")
    a = ap.parse_args()

    subs = os.path.join(BUILD, "subs.ass").replace("\\", "/")
    fc = (
        "[0:v]eq=contrast=1.06:saturation=0.86:brightness=-0.012:gamma=0.99,"
        "colorbalance=rs=-0.02:gs=0.0:bs=0.035:rh=0.02:bh=-0.03,"
        "curves=r=0/0 0.28/0.25 0.72/0.76 1/1:b=0/0.02 0.3/0.285 0.72/0.75 1/0.98,"
        "vignette=angle=PI/4.6:mode=forward,format=gbrp[g];"
        "[1:v]scale=1280:720,format=gbrp[p];"
        "[g][p]blend=all_mode=screen:all_opacity=0.85[b];"
        f"[b]noise=alls=7:allf=t,format=yuv420p,"
        f"subtitles={subs}:fontsdir=/usr/share/fonts/truetype/dejavu,format=yuv420p[v]"
    )
    cmd = [FFMPEG, "-y", "-loglevel", "error",
           "-i", a.video, "-i", a.particles, "-i", a.audio,
           "-filter_complex", fc, "-map", "[v]", "-map", "2:a",
           "-c:v", "libx264", "-preset", a.preset, "-crf", a.crf,
           "-profile:v", "high", "-level", "4.0", "-r", "24",
           "-x264-params", "keyint=48:min-keyint=24:scenecut=0:aq-mode=3",
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
           "-shortest", "-movflags", "+faststart",
           os.path.join(OUT, a.name)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-2500:]); raise SystemExit("ffmpeg fail")
    out = os.path.join(OUT, a.name)
    print(out, round(os.path.getsize(out) / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
