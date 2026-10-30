# -*- coding: utf-8 -*-
"""Рендер 305 склеек: плавная (eased) камера, «кипение» кадра, тряска на ударах."""
import argparse, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cuts import CUTS, TOTAL
from shots import FPS, W, H

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "images")
TMP = os.path.join(ROOT, "build", "tmp2")
OUT = os.path.join(ROOT, "out")
FFMPEG = "/home/user/.venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
UPW, UPH = 3840, 2160


def plate_path(name):
    for ext in (".jpg", ".png"):
        p = os.path.join(IMG, name + ext)
        if os.path.exists(p):
            return p
    raise SystemExit("нет плейта: " + name)


def move_vec(move, amp=0.055):
    """Микродвижение в терминах (z0,z1,cx0,cx1,cy0,cy1)."""
    z = 1.10
    if move == "push":
        return (1.00, 1.00 + amp * 1.5, 0.5, 0.5, 0.5, 0.5)
    if move == "pull":
        return (1.00 + amp * 1.6, 1.00, 0.5, 0.5, 0.5, 0.5)
    if move == "panL":
        return (z, z, 0.5 + amp, 0.5 - amp, 0.5, 0.5)
    if move == "panR":
        return (z, z, 0.5 - amp, 0.5 + amp, 0.5, 0.5)
    if move == "tiltU":
        return (z, z, 0.5, 0.5, 0.5 + amp, 0.5 - amp * 0.8)
    return (z, z, 0.5, 0.5, 0.5, 0.5)


def render_cut(c, idx, force=False):
    out = os.path.join(TMP, f"c_{idx:04d}.mp4")
    if os.path.exists(out) and not force:
        return out
    F = c["frames"]
    n = max(F - 1, 1)
    u = f"(on/{n})"
    e = f"(3*{u}*{u}-2*{u}*{u}*{u})"          # smoothstep
    z0, z1, cx0, cx1, cy0, cy1 = move_vec(c["move"])
    base_z = c["zoom"]
    z = f"({base_z:.4f}*({z0:.4f}+({z1 - z0:.4f})*{e}))"
    cx = f"(clip({cx0:.3f}+({cx1 - cx0:.3f})*{e}+{c['off'][0]:.3f},0,1))"
    cy = f"(clip({cy0:.3f}+({cy1 - cy0:.3f})*{e}+{c['off'][1]:.3f},0,1))"
    # «кипение»: микро-дрожание в пикселях входного кадра (3840) ≈ 1.5 px на выходе
    boil = f"(4.5*sin(on*0.79+{idx % 7})+2.5*sin(on*2.13+{idx % 5}))"
    if c.get("shake"):
        boil += f"+(9*exp(-on/7.0)*(sin(on*3.9)+0.6*sin(on*6.7)))"
    x = f"clip(({cx})*iw-(iw/zoom)/2+{boil},0,iw-iw/zoom)"
    y = f"clip(({cy})*ih-(ih/zoom)/2+({boil}*0.7),0,ih-ih/zoom)"
    vf = [f"scale={UPW}:{UPH}:flags=lanczos", "setsar=1",
          f"zoompan=z='{z}':x='{x}':y='{y}':d={F}:s={W}x{H}:fps={FPS}"]
    dur = F / FPS
    fi = min(c.get("fade_in", 0.0), dur * 0.9)
    fo = min(c.get("fade_out", 0.0), dur * 0.9)
    if fi > 0.02:
        vf.append(f"fade=t=in:st=0:d={fi:.3f}")
    if fo > 0.02:
        vf.append(f"fade=t=out:st={max(0.0, dur - fo):.3f}:d={fo:.3f}")
    vf.append("format=yuv420p")
    p = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", plate_path(c["plate"]),
                        "-vf", ",".join(vf), "-r", str(FPS),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                        "-x264-params", "keyint=48:min-keyint=24:scenecut=0",
                        "-an", out], capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr[-1500:])
        raise SystemExit("ffmpeg fail on cut " + str(idx))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="a", type=int, default=0)
    ap.add_argument("--to", dest="b", type=int, default=len(CUTS))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--concat", action="store_true")
    a = ap.parse_args()
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    parts = []
    for i in range(a.a, a.b):
        parts.append(render_cut(CUTS[i], i, a.force))
        if i % 20 == 0:
            el = time.time() - t0
            rate = (i - a.a + 1) / max(el, 0.1)
            print(f"  [{i:3d}/{a.b}] {el:5.0f}s  {rate:4.1f} скл/с", flush=True)
    print(f"готово {len(parts)} склеек за {time.time()-t0:.0f}s")
    if a.concat:
        allp = [os.path.join(TMP, f"c_{i:04d}.mp4") for i in range(len(CUTS))]
        missing = [p for p in allp if not os.path.exists(p)]
        if missing:
            raise SystemExit(f"не хватает {len(missing)} склеек")
        lst = os.path.join(TMP, "list.txt")
        with open(lst, "w") as f:
            for p in allp:
                f.write(f"file '{p}'\n")
        out = os.path.join(OUT, "video_silent_v2.mp4")
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", lst, "-c", "copy", out], check=True)
        print("склейка:", out)


if __name__ == "__main__":
    main()
