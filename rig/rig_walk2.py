# SPDX-License-Identifier: AGPL-3.0-or-later
"""rig_walk2.py - rig_walk with a real part tree (xform.py): pelvis (root, bobs) -> torso (leans) -> head, pelvis -> left leg / right leg (rotate about the hip).
python rig_walk2.py BASE.png OUT_DIR layer1.png [layer2.png ...] [--swing DEG] [--lean DEG]
The same part masks and transforms are applied to the base and to every layer, so layers stay attached. Reports pixel counts per frame (nearest-neighbour
rotation can lose or double pixels) and holes (background pixels enclosed by the figure)."""
import sys as _sys
if any(_a in ("-h", "--help") for _a in _sys.argv[1:]): print(__doc__); _sys.exit(0)     # -h always prints the documentation, exit 0
import sys, os, math
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xform as X
from scipy.ndimage import binary_fill_holes

def build(base):
    a = base[..., 3] > 0; ys, xs = np.nonzero(a); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max(); h = y1 - y0 + 1; cx = (x0 + x1 + 1) / 2
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]; hip_y = y0 + 0.55 * h; head_y = y0 + 0.30 * h
    legs = a & (yy >= hip_y + 0.12 * h)
    parts = {"head": a & (yy < head_y), "torso": a & (yy >= head_y) & ~legs, "leg_l": legs & (xx < cx), "leg_r": legs & (xx >= cx)}
    piv = {"head": (cx, head_y), "torso": (cx, hip_y), "leg_l": (cx - 0.12 * h, hip_y + 0.12 * h), "leg_r": (cx + 0.12 * h, hip_y + 0.12 * h)}
    return parts, piv

def mats(t, piv, swing, lean):
    s = math.sin(2 * math.pi * t); bob = X.translate(0, -1 if abs(s) > 0.7 else 0)           # pelvis = root
    torso = bob @ X.rot_about(lean * s, *piv["torso"]); head = X.chain(torso, X.rot_about(-lean * s * 0.5, *piv["head"]))
    return {"torso": torso, "head": head, "leg_l": bob @ X.rot_about(swing * s, *piv["leg_l"]), "leg_r": bob @ X.rot_about(-swing * s, *piv["leg_r"])}

def render(arrs, parts, M):
    comp = None
    for a in arrs:
        out = np.zeros_like(a)
        for k in ("leg_l", "leg_r", "torso", "head"):
            part = np.where(parts[k][..., None], a, 0).astype(np.uint8); m = X.apply(part, M[k]); ok = m[..., 3] > 0; out[ok] = m[ok]
        if comp is None: comp = out
        else: ok = out[..., 3] > 0; comp[ok] = out[ok]
    return comp

if __name__ == "__main__":
    A = sys.argv[1:]; swing = float(A[A.index("--swing") + 1]) if "--swing" in A else 8.0; lean = float(A[A.index("--lean") + 1]) if "--lean" in A else 3.0
    A = [x for i, x in enumerate(A) if x not in ("--swing", "--lean") and (i == 0 or A[i - 1] not in ("--swing", "--lean"))]
    base, outd, *lay = A; os.makedirs(outd, exist_ok=True)
    arrs = [np.array(Image.open(p).convert("RGBA")) for p in [base] + lay]; parts, piv = build(arrs[0]); n0 = int((arrs[0][..., 3] > 0).sum())
    for i in range(8):
        M = mats(i / 8, piv, swing, lean); b = render(arrs[:1], parts, M); d = render(arrs, parts, M)
        Image.fromarray(b).save(os.path.join(outd, f"base_{i}.png")); Image.fromarray(d).save(os.path.join(outd, f"dressed_{i}.png"))
        m = b[..., 3] > 0; holes = int((binary_fill_holes(m) & ~m).sum()); print(f"frame {i}: base px {int(m.sum())} (standing {n0}), holes {holes}")
