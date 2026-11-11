#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Snap every opaque pixel of generated frames to the nearest colour of the character's own palette (L1 distance in RGB).

  palette_lock.py lock IN_DIR OUT_DIR --ref STILL.png [STILL2.png ...] [--max-dist 60]
  palette_lock.py selftest

The palette is the set of colours of the reference stills (the 8 dressed rotations). Pose edits from the generator drift 5-35 (L1) from it, so the
same hair, skin or leather shows several shades from frame to frame; locking removes the drift and changes only colours, never the alpha or the
shape. Pixels farther than --max-dist from every palette colour are left alone and reported (a real new colour, e.g. an effect). Needs numpy + Pillow.
"""
import sys, os, glob, re, json, argparse
import numpy as np
from PIL import Image


def load(p): return np.array(Image.open(p).convert("RGBA"))


def frame_paths(d):
    return sorted(glob.glob(os.path.join(d, "*.png")), key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)) or 0))


def palette(refs):
    s = set()
    for p in refs:
        a = load(p)
        for c in np.unique(a[a[..., 3] > 0][:, :3], axis=0): s.add(tuple(int(v) for v in c))
    return np.array(sorted(s), dtype=int)


def lock(a, pal, max_dist=60):
    a = a.copy(); op = a[..., 3] > 0; ys, xs = np.where(op)
    if len(ys) == 0: return a, 0, 0
    rgb = a[ys, xs, :3].astype(int); d = np.abs(rgb[:, None, :] - pal[None, :, :]).sum(2); idx = d.argmin(1); dmin = d.min(1)
    change = (dmin > 0) & (dmin <= max_dist); far = dmin > max_dist
    a[ys[change], xs[change], :3] = pal[idx[change]].astype(np.uint8)
    return a, int(change.sum()), int(far.sum())


def run(src, dst, refs, max_dist=60):
    os.makedirs(dst, exist_ok=True); pal = palette(refs); rep = {}
    for p in frame_paths(src):
        a, ch, far = lock(load(p), pal, max_dist); rep[os.path.basename(p)] = {"snapped": ch, "left_alone": far}
        Image.fromarray(a).save(os.path.join(dst, os.path.basename(p)))
    json.dump(rep, open(os.path.join(dst, "palette_report.json"), "w"), indent=1)
    return rep


def selftest():
    pal = np.array([[10, 10, 10], [200, 100, 50]])
    a = np.zeros((4, 4, 4), np.uint8); a[1, 1] = (205, 98, 52, 255); a[2, 2] = (11, 10, 9, 255); a[3, 3] = (90, 200, 90, 255)
    b, ch, far = lock(a, pal, 30)
    assert tuple(b[1, 1, :3]) == (200, 100, 50) and tuple(b[2, 2, :3]) == (10, 10, 10) and ch == 2 and far == 1, (ch, far)
    assert (b[..., 3] == a[..., 3]).all()
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest": selftest()
    else:
        ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument("cmd"); ap.add_argument("src"); ap.add_argument("dst")
        ap.add_argument("--ref", nargs="+", required=True); ap.add_argument("--max-dist", type=int, default=60); a = ap.parse_args()
        r = run(a.src, a.dst, a.ref, a.max_dist); print(json.dumps(r))
