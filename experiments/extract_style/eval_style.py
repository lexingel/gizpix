# SPDX-License-Identifier: AGPL-3.0-or-later
"""eval_style.py - how well does `extract_style` carry a set of real sprites' look into pixdraw buildings?
For every input sprite (alone) and for the whole set: extract a style, render house / inn / keep / tower (iso), and measure
  cover   = share of the sprites' opaque pixels that have a rendered colour within TOL (RGB L2)   - does the render use the sprites' colours?
  purity  = share of the rendered opaque pixels that have a sprite colour within TOL            - does the render stay inside the sprites' colours?
  bands   = mean RGB distance between the average colour of the silhouette's top / middle / bottom third in the sprites and in the render (roof / walls / base should match); lower is better.
Prints the mean of each. Same sprites, so two versions of extract_style can be compared. python eval_style.py [GLOB ...]"""
import glob, os, sys, tempfile
import numpy as np
from PIL import Image
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from pixdraw import render, extract_style
TOL = 40.0
def cols(im):
    a = np.array(im.convert("RGBA")); return np.unique(a[a[..., 3] > 0][:, :3], axis=0).astype(float), a[a[..., 3] > 0][:, :3].astype(float)
def near(px, pal):
    return (np.sqrt(((px[:, None] - pal[None]) ** 2).sum(-1)).min(1) <= TOL)
def band_means(im):
    a = np.array(im.convert("RGBA")); ys = np.nonzero((a[..., 3] > 0).any(1))[0]; y0, y1 = ys.min(), ys.max() + 1; out = []
    for k in range(3):
        lo, hi = y0 + (y1 - y0) * k // 3, y0 + (y1 - y0) * (k + 1) // 3; b = a[lo:hi]; m = b[..., 3] > 0
        out.append(b[m][:, :3].astype(float).mean(0) if m.any() else np.zeros(3))
    return np.array(out)
def score(paths, tmp):
    st = os.path.join(tmp, "s.json"); extract_style(paths, st)
    src = np.concatenate([cols(Image.open(p))[1] for p in paths]); spal = np.unique(src, axis=0)
    cov, pur, bd = [], [], []
    sb = np.mean([band_means(Image.open(p)) for p in paths], 0)
    for t in ("house", "inn", "keep", "tower"):
        rim = render({"type": t, "proj": "iso"}, st)[0]; rp, rpx = cols(rim)
        cov.append(near(src, rp).mean()); pur.append(near(rpx, spal).mean()); bd.append(float(np.linalg.norm(band_means(rim) - sb, axis=1).mean()))
    return float(np.mean(cov)), float(np.mean(pur)), float(np.mean(bd))
if __name__ == "__main__":
    pats = sys.argv[1:]
    if not pats: print("usage: python eval_style.py 'sprites/*.png' [more globs]   (building sprites to extract a style from)", file=sys.stderr); sys.exit(2)
    files = sorted(sum((glob.glob(p) for p in pats), [])); tmp = tempfile.mkdtemp(); rows = []
    for f in files:
        c, p, b = score([f], tmp); rows.append((c, p, b)); print(f"{os.path.basename(f):22s} cover {c:.2f} bands {b:5.1f}")
    c, p, b = score(files, tmp)
    print(f"MEAN single: cover {np.mean([r[0] for r in rows]):.3f} bands {np.mean([r[2] for r in rows]):.1f}   | all {len(files)} together: cover {c:.3f} bands {b:.1f}")
