#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Apply an explicit, auditable list of single-pixel edits to frames.

  apply_pixel_fixes.py FIXES.json FRAMES_ROOT        FRAMES_ROOT/<dir>/<frame>.png is edited in place
  apply_pixel_fixes.py selftest

FIXES.json = [{"dir": "south", "frame": 4, "op": "delete"|"set"|"fill", "x": 102, "y": 67, "color": [9, 8, 7], "why": "..."}, ...]
  delete  makes the pixel transparent
  set     paints "color" (a colour the character already uses; one pixel, labelled locally repaired)
  fill    paints the most common colour among the 4 opaque neighbours (ties: the darkest): closes a pinhole
Every edit is reported (before -> after) so the change can be reviewed. Needs numpy + Pillow.
"""
import sys as _sys
if any(_a in ("-h", "--help") for _a in _sys.argv[1:]): print(__doc__); _sys.exit(0)     # -h always prints the documentation, exit 0
import sys, os, json
import numpy as np
from PIL import Image


def apply(fixes, root, report=True):
    cache = {}; out = []
    for f in fixes:
        p = os.path.join(root, f["dir"], f"{f['frame']}.png")
        if p not in cache: cache[p] = np.array(Image.open(p).convert("RGBA"))
        a = cache[p]; x, y = f["x"], f["y"]; before = tuple(int(v) for v in a[y, x])
        if f["op"] == "delete": a[y, x] = 0
        elif f["op"] == "set": a[y, x] = (*f["color"], 255)
        elif f["op"] == "fill":
            cols = [tuple(int(v) for v in a[y + dy, x + dx, :3]) for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)) if a[y + dy, x + dx, 3] > 0]
            if not cols: out.append((f["dir"], f["frame"], x, y, before, "skipped: no opaque neighbour")); continue
            best = max(set(cols), key=lambda c: (cols.count(c), -sum(c))); a[y, x] = (*best, 255)
        out.append((f["dir"], f["frame"], x, y, before, tuple(int(v) for v in a[y, x])))
    for p, a in cache.items(): Image.fromarray(a).save(p)
    if report:
        for o in out: print(o)
    return out


def selftest():
    import tempfile
    t = tempfile.mkdtemp(); os.makedirs(t + "/d"); a = np.zeros((8, 8, 4), np.uint8)
    a[3, 2:5] = (9, 8, 7, 255); a[2, 3] = (9, 8, 7, 255); a[4, 3] = (9, 8, 7, 255); a[3, 3] = 0; a[6, 6] = (9, 8, 7, 255)
    Image.fromarray(a).save(t + "/d/0.png")
    apply([{"dir": "d", "frame": 0, "op": "fill", "x": 3, "y": 3}, {"dir": "d", "frame": 0, "op": "delete", "x": 6, "y": 6},
           {"dir": "d", "frame": 0, "op": "set", "x": 0, "y": 0, "color": [1, 2, 3]}], t, report=False)
    b = np.array(Image.open(t + "/d/0.png")); assert tuple(b[3, 3]) == (9, 8, 7, 255) and b[6, 6, 3] == 0 and tuple(b[0, 0]) == (1, 2, 3, 255)
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest": selftest()
    else: apply(json.load(open(sys.argv[1])), sys.argv[2])
