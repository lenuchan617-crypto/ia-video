# -*- coding: utf-8 -*-
"""Упаковка плейтов в JPEG (экономия места в снапшоте). PNG удаляются после рендера."""
import os, glob
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "images")
tot = 0
for p in sorted(glob.glob(os.path.join(IMG, "*.png"))):
    j = p[:-4] + ".jpg"
    Image.open(p).convert("RGB").save(j, quality=92, optimize=True, subsampling=1)
    tot += os.path.getsize(j)
    os.remove(p)
print(f"готово: {len(glob.glob(os.path.join(IMG,'*.jpg')))} jpg, {tot/1e6:.1f} MB")
