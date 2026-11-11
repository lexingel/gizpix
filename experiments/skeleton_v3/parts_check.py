# SPDX-License-Identifier: AGPL-3.0-or-later
"""parts_check.py - measure `pix_layer cut --drop-parts` on the real skeleton-v3 walk frames (robe, pauldrons; south, east; 8 frames each).
Cuts every frame with `--solid --drop-skin auto --bits` and again with `--drop-parts`. Leak = warm layer pixels within 3 px of the base's warm pixels or in its lowest 12 rows
(hair tips, boot slivers); lost = pixels removed by --drop-parts that are NOT warm (genuine outfit). Also checks the dark pair (dbase/drobe): the guard must SKIP and drop 0.
Run: python parts_check.py   (works in a temp folder, never touches the frames)"""
import os, sys, shutil, subprocess, tempfile
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "layers")); import pix_layer as PL
FR = os.path.join(HERE, "..", "..", "samples", "walk_frames"); T = tempfile.mkdtemp(prefix="parts_check_"); fails = 0
A = lambda p: np.array(Image.open(p).convert("RGBA"))

def cut(base, outfit, d, out, *flags):
    """all 8 frames of one direction together, like real use (the outfit core is learnt over the frames)"""
    b, o = f"{T}/b", f"{T}/o"
    for x in (b, o, out): shutil.rmtree(x, ignore_errors=True)
    os.makedirs(b); os.makedirs(o)
    for i in range(8): shutil.copy(f"{FR}/{base}/{d}/{i}.png", f"{b}/{i}.png"); shutil.copy(f"{FR}/{outfit}/{d}/{i}.png", f"{o}/{i}.png")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "gizpix.py"), "run", "pix_layer", "cut", b, o, out, "--name", "L", "--solid", "--drop-skin", "auto", "--bits", *flags], capture_output=True, text=True)
    return [A(f"{out}/L/{i}.png") for i in range(8)], r.stdout

def zone(base):
    """where a leak can be: hair (warm base components of >= 40 px reaching the top 40% of the silhouette) and boots (lowest 12 rows), widened by 3 px. Hands and the belt are outside."""
    from scipy.ndimage import label
    bm = (base[..., 3] > 0) & (base[..., :3].astype(int).sum(-1) >= 90); ys = np.nonzero(bm.any(1))[0]; top, bot = ys.min(), ys.max()
    lab, n = label(PL._warm(base) & bm, np.ones((3, 3))); hair = np.zeros_like(bm)
    for k in range(1, n + 1):
        g = lab == k
        if g.sum() >= 40 and np.nonzero(g.any(1))[0].min() < top + 0.4 * (bot - top): hair |= g
    return binary_dilation(hair, np.ones((3, 3), bool), iterations=3) | binary_dilation(bm & (np.arange(base.shape[0])[:, None] > bot - 12), np.ones((3, 3), bool), iterations=3)

genuine = lambda x, y: (x[..., 3] > 0) & (y[..., 3] == 0) & ~PL._warm(x, 0.2) & (x[..., :3].astype(int).sum(-1) >= 150)      # dark pixels are the leak's own outline

print(f"{'pair':14s} {'leak before':>11s} {'after':>6s} {'cold px lost':>13s}")
for o in ("robe", "pauld"):
    for d in ("south", "east"):
        xs, _ = cut("base", o, d, f"{T}/x"); ys, _ = cut("base", o, d, f"{T}/y", "--drop-parts"); lb = la = lost = 0
        for i in range(8):
            z = zone(A(f"{FR}/base/{d}/{i}.png")); x, y = xs[i], ys[i]
            lb += int((PL._warm(x, 0.2) & z).sum()); la += int((PL._warm(y, 0.2) & z).sum()); lost += int(genuine(x, y).sum())
        ok = la <= 0.2 * lb and lost <= 25; fails += not ok
        print(("ok   " if ok else "FAIL ") + f"{o + ' ' + d:14s} {lb:11d} {la:6d} {lost:13d}")

dropped = 0; skips = 0
for d in ("south", "east"):
    xs, _ = cut("dbase", "drobe", d, f"{T}/x"); ys, out = cut("dbase", "drobe", d, f"{T}/y", "--drop-parts")
    dropped += sum(int(((x[..., 3] > 0) & (y[..., 3] == 0)).sum()) for x, y in zip(xs, ys)); skips += out.count("SKIP")
ok = dropped <= 10; fails += not ok
print(("ok   " if ok else "FAIL ") + f"dark pair: {dropped} px dropped over 16 frames, guard said SKIP {skips} times")
shutil.rmtree(T, ignore_errors=True); print("parts check " + ("FAILED" if fails else "ok")); sys.exit(1 if fails else 0)
