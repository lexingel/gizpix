# SPDX-License-Identifier: AGPL-3.0-or-later
"""rig_walk.py - first test: walk a standing south sprite with code, and move every outfit layer with the same part transforms.
python rig_walk.py BASE.png OUT_DIR layer1.png [layer2.png ...]    (layers stacked in the order given)
Parts are row/column bands of the sprite (head, torso, left leg, right leg); each frame moves a band by whole pixels, the same
for the base and every layer, so the layers cannot drift off the body by construction. Local, free."""
import sys as _sys
if any(_a in ("-h", "--help") for _a in _sys.argv[1:]): print(__doc__); _sys.exit(0)     # -h always prints the documentation, exit 0
import sys, os, math
import numpy as np
from PIL import Image

def parts(a, y_head, y_legs, x_mid):
    H, W = a.shape[:2]; yy, xx = np.mgrid[0:H, 0:W]
    return {"legs_l": (yy >= y_legs) & (xx < x_mid), "legs_r": (yy >= y_legs) & (xx >= x_mid),
            "torso": (yy > y_head) & (yy < y_legs), "head": yy <= y_head}

def shift(a, m, dx, dy):
    out = np.zeros_like(a); ys, xs = np.nonzero(m & (a[..., 3] > 0)); ys2, xs2 = ys + dy, xs + dx
    ok = (ys2 >= 0) & (ys2 < a.shape[0]) & (xs2 >= 0) & (xs2 < a.shape[1]); out[ys2[ok], xs2[ok]] = a[ys[ok], xs[ok]]; return out

def pose(t, step=2):
    """t in 0..1 of the cycle. Returns {part: (dx, dy)}. Facing the camera: legs lift alternately, body bobs twice per cycle."""
    s = math.sin(2 * math.pi * t); bob = -1 if abs(s) > 0.7 else 0
    lift_l = -step if s > 0.5 else 0; lift_r = -step if s < -0.5 else 0
    sway = 1 if s > 0.5 else (-1 if s < -0.5 else 0)
    return {"legs_l": (0, lift_l), "legs_r": (0, lift_r), "torso": (0, bob), "head": (sway // 1 * 0, bob)}

def frame(layers, P, t):
    pz = pose(t); comp = None
    for a in layers:
        out = np.zeros_like(a)
        for part in ("legs_l", "legs_r", "torso", "head"):
            dx, dy = pz[part]; sh = shift(a, P[part], dx, dy); m = sh[..., 3] > 0; out[m] = sh[m]
        if comp is None: comp = out
        else: m = out[..., 3] > 0; comp[m] = out[m]
    return comp

if __name__ == "__main__":
    base, outd, *lay = sys.argv[1:]; os.makedirs(outd, exist_ok=True)
    A = [np.array(Image.open(p).convert("RGBA")) for p in [base] + lay]
    ys, xs = np.nonzero(A[0][..., 3]); y0, y1 = ys.min(), ys.max(); x_mid = int(round((xs.min() + xs.max() + 1) / 2))
    P = parts(A[0], y0 + int(0.40 * (y1 - y0)), y0 + int(0.82 * (y1 - y0)), x_mid)
    for n in (0, 1):
        for i in range(8):
            Image.fromarray(frame(A[:1] if n == 0 else A, P, i / 8)).save(os.path.join(outd, f"{'base' if n == 0 else 'dressed'}_{i}.png"))
    print("wrote 8 base + 8 dressed frames to", outd)
