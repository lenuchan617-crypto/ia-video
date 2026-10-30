# -*- coding: utf-8 -*-
"""Рендер эпизода: шоты (zoompan) -> промежуточные клипы -> concat -> грейд+сабы+звук."""
import argparse, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from shots import SCENES, SHOTS, TOTAL, FPS, W, H

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "images")
TMP = os.path.join(ROOT, "build", "tmp")
OUT = os.path.join(ROOT, "out")
FFMPEG = "/home/user/.venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
UPW, UPH = 3840, 2160          # рабочее разрешение камеры (запас на движение)


def run(cmd, quiet=True):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        sys.stderr.write(" ".join(cmd[:6]) + " ...\n" + p.stderr[-3000:])
        raise SystemExit(f"ffmpeg failed ({p.returncode})")
    return p


def cam_expr(cam, frames):
    z0, z1, cx0, cy0, cx1, cy1 = cam
    n = max(frames - 1, 1)
    k = f"(on/{n})"
    z = f"({z0}+({z1-z0})*{k})"
    cx = f"({cx0}+({cx1-cx0})*{k})"
    cy = f"({cy0}+({cy1-cy0})*{k})"
    x = f"clip(({cx})*iw-(iw/zoom)/2,0,iw-iw/zoom)"
    y = f"clip(({cy})*ih-(ih/zoom)/2,0,ih-ih/zoom)"
    return z, x, y


def render_shot(shot, idx, force=False):
    dur = shot["dur"]
    frames = int(round(dur * FPS))
    out = os.path.join(TMP, f"shot_{idx:03d}.mp4")
    if os.path.exists(out) and not force:
        return out
    src = os.path.join(IMG, shot["image"] + ".png")
    if not os.path.exists(src):
        alt = os.path.join(IMG, shot["image"] + ".jpg")
        if os.path.exists(alt):
            src = alt
        else:
            raise SystemExit(f"нет плейта: {src}")
    z, x, y = cam_expr(shot["cam"], frames)
    vf = [
        f"scale={UPW}:{UPH}:flags=lanczos",
        "setsar=1",
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS}",
    ]
    fi = shot.get("fade_in", 0.0)
    fo = shot.get("fade_out", 0.0)
    if fi > 0:
        vf.append(f"fade=t=in:st=0:d={fi}")
    if fo > 0:
        vf.append(f"fade=t=out:st={dur-fo:.3f}:d={fo}")
    vf.append("format=yuv420p")
    run([FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-i", src,
         "-t", f"{dur:.3f}", "-vf", ",".join(vf), "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
         "-x264-params", "keyint=48:min-keyint=24:scenecut=0",
         "-an", out])
    return out


def render_range(lo, hi, force=False):
    os.makedirs(TMP, exist_ok=True)
    parts = []
    t0 = time.time()
    sel = [s for s in SHOTS if lo <= s["start"] < hi]
    for i, s in enumerate(sel):
        p = render_shot(s, SHOTS.index(s), force)
        parts.append(p)
        el = time.time() - t0
        done = sum(x["dur"] for x in sel[:i + 1])
        print(f"  [{done:6.1f}/{sum(x['dur'] for x in sel):6.1f}s] "
              f"shot {SHOTS.index(s):03d} {s['image']:16s} {s['dur']:5.1f}s  "
              f"(elapsed {el:5.0f}s, {done/max(el,0.01):4.2f}x realtime)", flush=True)
    return parts


def concat(parts, out_path):
    lst = out_path + ".txt"
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", out_path])
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="all")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--probe", action="store_true", help="только 1 шот, замер скорости")
    a = ap.parse_args()
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    if a.probe:
        t0 = time.time()
        render_shot(SHOTS[0], 0, force=True)
        print(f"probe: 1 шот {SHOTS[0]['dur']}s -> {time.time()-t0:.1f}s")
        sys.exit(0)
    if a.scenes == "all":
        lo, hi = 0.0, 1e9
    else:
        ids = a.scenes.split(",")
        lo = min(next(s[2] for s in SCENES if s[0] == i) for i in ids)
        hi = max(next(s[3] for s in SCENES if s[0] == i) for i in ids)
    parts = render_range(lo, hi, a.force)
    name = "video_silent.mp4" if a.scenes == "all" else f"video_s{a.scenes.replace(',','_')}.mp4"
    p = concat(parts, os.path.join(OUT, name))
    print("готово:", p)
