# -*- coding: utf-8 -*-
"""Сведение: эмбиент (bed.wav) + озвучка -> master.wav, плюс замеры длительностей реплик."""
import os, sys, json, re, subprocess, wave
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lines import LINES, SPEAKERS
from sfx import FS, N, band

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(ROOT, "build", "audio")
VO = os.path.join(ROOT, "audio", "vo")
TMP = os.path.join(ROOT, "build", "tmp")
FFMPEG = "/home/user/.venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"

# группы озвучки: один файл = несколько реплик через длинные паузы
GROUPS = {
    "g_officer": ("support", ["L01", "L03", "L05"]),
    "g_sunny_a": ("sunny",   ["L02", "L04", "L06"]),
    "g_guard":   ("support", ["L07"]),
    "g_sunny_b": ("sunny",   ["L08", "L10"]),
    "g_scholar": ("support", ["L09"]),
    "g_slave":   ("support", ["L11"]),
    "g_sunny_c": ("sunny",   ["L12", "L13", "L15", "L17", "L19"]),
    "g_curse":   ("curse",   ["L14"]),
    "g_jet":     ("jet",     ["L16", "L18"]),
}
BY_ID = {l[0]: l for l in LINES}


def decode(src, dst, sr=FS, ch=1):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", src,
                    "-ac", str(ch), "-ar", str(sr), "-c:a", "pcm_s16le", dst], check=True)
    return dst


def read_mono(path):
    with wave.open(path, "rb") as w:
        n = w.getnframes(); ch = w.getnchannels()
        a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return a


def detect_silences(path, thr=-38, mind=0.14):
    p = subprocess.run([FFMPEG, "-hide_banner", "-i", path, "-af",
                        f"silencedetect=n={thr}dB:d={mind}", "-f", "null", "-"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    txt = p.stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", txt)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", txt)]
    return list(zip(starts, ends))


def split_audio(a, sil, n_expected):
    """Берём N-1 самые длинные паузы как точки разреза реплик."""
    dur = len(a) / FS
    cand = [(s, e) for s, e in sil if s > 0.05 and e < dur - 0.05 and e > s]
    if n_expected == 1:
        return [(0.0, dur)]
    if len(cand) < n_expected - 1:
        return None
    cand.sort(key=lambda p: -(p[1] - p[0]))
    cuts = sorted((s + e) / 2 for s, e in cand[:n_expected - 1])
    segs, prev = [], 0.0
    for c in cuts:
        segs.append((prev, c)); prev = c
    segs.append((prev, dur))
    return [s for s in segs if s[1] - s[0] > 0.18]


def trim_edges(a, thr_db=-42.0, pad=0.06):
    """Срезает тишину по краям реплики по огибающей (блоки 20 мс)."""
    blk = int(0.02 * FS)
    n = len(a) // blk
    if n < 3:
        return a
    env = np.abs(a[:n * blk].reshape(n, blk)).max(axis=1) + 1e-9
    db = 20 * np.log10(env)
    idx = np.where(db > thr_db)[0]
    if len(idx) == 0:
        return a
    p = int(pad * FS)
    i0 = max(0, idx[0] * blk - p)
    i1 = min(len(a), (idx[-1] + 1) * blk + p)
    return a[i0:i1]


def load_vo():
    """-> {line_id: audio}. Приоритет — отдельный файл vo/<ID>.mp3 (точный тайминг)."""
    out = {}
    for lid, spk, text, t0, plan, kind in LINES:
        p = os.path.join(VO, lid + ".mp3")
        if os.path.exists(p):
            wavp = os.path.join(TMP, "vo_" + lid + ".wav")
            decode(p, wavp)
            a = read_mono(wavp)
            rms = float(np.sqrt(np.mean(a ** 2)) + 1e-9)
            a = a * (0.185 / rms)
            np.clip(a, -1.0, 1.0, out=a)
            a = trim_edges(a)
            f = int(0.02 * FS)
            if len(a) > 2 * f:
                a[:f] *= np.linspace(0, 1, f); a[-f:] *= np.linspace(1, 0, f)
            out[lid] = a
    missing = [l[0] for l in LINES if l[0] not in out]
    if not missing:
        print("  (индивидуальные файлы: все", len(out), "реплик)")
        return out
    print("  (догружаю группы для:", ", ".join(missing), ")")
    for gname, (voice, ids) in GROUPS.items():
        if all(i in out for i in ids):
            continue                      # все реплики уже есть отдельными файлами
        src = os.path.join(VO, gname + ".mp3")
        if not os.path.exists(src):
            raise SystemExit(f"нет озвучки: {src}")
        wavp = os.path.join(TMP, "vo_" + gname + ".wav")
        decode(src, wavp)
        a = read_mono(wavp)
        # нормализация громкости вложенного файла
        rms = float(np.sqrt(np.mean(a ** 2)) + 1e-9)
        a = a * (0.185 / rms) if rms > 0 else a
        np.clip(a, -1.0, 1.0, out=a)
        segs = split_audio(a, detect_silences(wavp), len(ids))
        if segs is None:
            # режем на равные куски по найденным паузам, добивая пропорционально
            sil = detect_silences(wavp, thr=-42, mind=0.08)
            segs = split_audio(a, sil, len(ids))
        if segs is None:
            total = len(a) / FS
            w = [len(BY_ID[i][2]) for i in ids]
            acc = 0.0
            segs = []
            for wi in w:
                d = total * wi / sum(w)
                segs.append((acc, acc + d)); acc += d
            print(f"  ! {gname}: паузы не разрезались, делю по длине текста")
        print(f"  {gname}: {len(segs)} сегм. -> " +
              ", ".join(f"{i}:{s:.2f}-{e:.2f}" for i, (s, e) in zip(ids, segs)))
        for lid, (s, e) in zip(ids, segs):
            seg = a[int(s * FS):int(e * FS)].copy()
            # микроплавные края
            f = int(0.02 * FS)
            if len(seg) > 2 * f:
                seg[:f] *= np.linspace(0, 1, f)
                seg[-f:] *= np.linspace(1, 0, f)
            out[lid] = seg
    return out


def place(L, R, t, sig, gain=1.0, pan=0.0):
    i = int(t * FS)
    if i >= N: return
    if i + len(sig) > N:
        sig = sig[:N - i]
    import math
    gl = gain * math.cos((pan + 1) * math.pi / 4)
    gr = gain * math.sin((pan + 1) * math.pi / 4)
    L[i:i + len(sig)] += sig * gl
    R[i:i + len(sig)] += sig * gr


def reverb_curse(sig):
    """Дешёвый «вселенский» эхо-хвост для голоса Заклятия."""
    n = len(sig) + int(2.4 * FS)
    out = np.zeros(n, dtype=np.float32)
    out[:len(sig)] += sig
    for d, g in ((0.11, 0.55), (0.23, 0.42), (0.41, 0.33), (0.73, 0.22), (1.19, 0.14)):
        k = int(d * FS)
        out[k:k + len(sig)] += sig * g
    # мягкий низ
    try:
        out = 0.65 * out + 0.35 * np.convolve(out, np.ones(9) / 9, mode="same").astype(np.float32)
    except Exception:
        pass
    return out.astype(np.float32)


def main():
    os.makedirs(TMP, exist_ok=True)
    with wave.open(os.path.join(AUD, "bed.wav"), "rb") as w:
        n = w.getnframes()
        bed = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32).reshape(-1, 2) / 32768
    L = np.zeros(N, dtype=np.float32); R = np.zeros(N, dtype=np.float32)
    L[:min(len(bed), N)] = bed[:N, 0]; R[:min(len(bed), N)] = bed[:N, 1]

    print("озвучка:")
    vo = load_vo()
    durs, speech = {}, []
    for lid, spk, text, t0, plan, kind in LINES:
        sig = vo.get(lid)
        if sig is None:
            continue
        d = len(sig) / FS
        durs[lid] = round(d, 3)
        speech.append((t0, t0 + d))
        pan = {"SUNNY": 0.0, "OFFICER": 0.10, "GUARD": -0.10, "SCHOLAR": 0.14,
               "SLAVE": -0.18, "JET": 0.12, "CURSE": 0.0}.get(spk, 0.0)
        if kind == "god":
            sig = reverb_curse(sig) * 0.85
        elif kind == "vo":
            sig = sig * 0.9
        place(L, R, t0, sig, 1.0, pan)

    # лёгкий дакинг эмбиента под речью
    duck = np.ones(N, dtype=np.float32)
    for s, e in speech:
        a, b = int(max(0, s - 0.25) * FS), int(min(N, e + 0.35) * FS)
        if b > a:
            duck[a:b] *= 0.50
    k = int(0.12 * FS)
    duck = np.convolve(duck, np.ones(k, dtype=np.float32) / k, mode="same")[:N].astype(np.float32)
    L *= duck; R *= duck

    peak = max(np.max(np.abs(L)), np.max(np.abs(R))) + 1e-9
    L *= 0.97 / peak; R *= 0.97 / peak
    pcm = np.empty((N, 2), dtype=np.int16)
    pcm[:, 0] = np.clip(L * 32767, -32768, 32767).astype(np.int16)
    pcm[:, 1] = np.clip(R * 32767, -32768, 32767).astype(np.int16)
    out = os.path.join(AUD, "master.wav")
    with wave.open(out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(FS)
        w.writeframes(pcm.tobytes())
    json.dump(durs, open(os.path.join(ROOT, "build", "durs.json"), "w"), indent=1)
    rms = float(np.sqrt(np.mean(L.astype(np.float64) ** 2)))
    print(f"master.wav {N/FS:.1f}s  RMS={20*np.log10(rms+1e-12):.1f} dBFS  реплик={len(durs)}")


if __name__ == "__main__":
    main()
