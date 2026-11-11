#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fill one-pixel pinholes: a transparent pixel whose four neighbours are all opaque (a missing pixel inside the sprite, usually in the outline).

  fill_pinholes.py PATH [PATH2 ...] [--out DIR]
      PATH = a PNG file, a folder of PNGs, or a ROOT whose sub-folders hold PNGs (ROOT/<dir>/<n>.png).
      Without --out the PNGs are edited IN PLACE; with --out DIR the fixed copies go to DIR (same file names; for a ROOT, DIR/<dir>/<n>.png) and the originals stay untouched.
      Prints a count per path; exit 2 when a path does not exist or holds no PNG.
  fill_pinholes.py selftest

The pixel takes the most common colour among its four neighbours (ties: the darkest). 2-3 px slivers between limbs are NOT touched (they can be real gaps). Needs numpy + Pillow.
"""
import sys, os, glob
import numpy as np
from PIL import Image


def enclosed(op):
    h, w = op.shape; seen = np.zeros_like(op)
    st = [(y, x) for x in range(w) for y in (0, h - 1)] + [(y, x) for y in range(h) for x in (0, w - 1)]
    while st:
        y, x = st.pop()
        if 0 <= y < h and 0 <= x < w and not seen[y, x] and not op[y, x]:
            seen[y, x] = True; st += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    return (~op) & (~seen)


def fill(a):
    a = a.copy(); op = a[..., 3] > 0; h, w = op.shape; n = 0
    for y, x in zip(*np.where((~op) & enclosed(op))):
        if 0 < y < h - 1 and 0 < x < w - 1 and all(op[y + dy, x + dx] for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))):
            cols = [tuple(int(v) for v in a[y + dy, x + dx, :3]) for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))]
            a[y, x] = (*max(set(cols), key=lambda c: (cols.count(c), -sum(c))), 255); n += 1
    return a, n


def pngs(path):
    """(file, name relative to path) for a PNG file, a folder of PNGs, or a ROOT/<dir>/*.png layout"""
    if os.path.isfile(path): return [(path, os.path.basename(path))]
    hits = sorted(glob.glob(os.path.join(path, "*.png"))) or sorted(glob.glob(os.path.join(path, "*", "*.png")))
    return [(p, os.path.relpath(p, path)) for p in hits]


def run(path, out=None):
    tot = 0
    for p, rel in pngs(path):
        a, n = fill(np.array(Image.open(p).convert("RGBA")))
        if out: dst = os.path.join(out, rel); os.makedirs(os.path.dirname(dst) or ".", exist_ok=True); Image.fromarray(a).save(dst)
        elif n: Image.fromarray(a).save(p)
        tot += n
    return tot


def selftest():
    a = np.zeros((8, 8, 4), np.uint8); a[2:5, 2:5] = (9, 8, 7, 255); a[3, 3] = 0
    b, n = fill(a); assert n == 1 and tuple(b[3, 3]) == (9, 8, 7, 255)
    import tempfile
    with tempfile.TemporaryDirectory() as t:                                  # file, folder, ROOT layout, --out keeps the original
        os.makedirs(t + "/r/a"); Image.fromarray(a).save(t + "/r/a/0.png"); Image.fromarray(a).save(t + "/one.png")
        assert run(t + "/one.png") == 1 and run(t + "/r") == 1 and run(t + "/r") == 0
        Image.fromarray(a).save(t + "/two.png"); assert run(t + "/two.png", t + "/o") == 1 and os.path.exists(t + "/o/two.png") and fill(np.array(Image.open(t + "/two.png")))[1] == 1
    a[3, 4] = 0; b, n = fill(a); assert n == 0     # a 2 px hole is left alone
    print("selftest ok")


if __name__ == "__main__":
    A = sys.argv[1:]
    if not A or A[0] in ("-h", "--help"): print(__doc__); sys.exit(0 if A else 2)
    if A == ["selftest"]: selftest()
    else:
        out = A[A.index("--out") + 1] if "--out" in A and A.index("--out") + 1 < len(A) else None
        paths = [x for i, x in enumerate(A) if x != "--out" and (i == 0 or A[i - 1] != "--out")]
        bad = [x for x in paths if not pngs(x)]
        if "--out" in A and not out or not paths or bad: print("fill_pinholes: " + ("--out needs a folder" if "--out" in A and not out else f"no PNG found at {bad}" if bad else "no path given") + "  (see: fill_pinholes.py -h)", file=sys.stderr); sys.exit(2)
        if not out: print("fill_pinholes: editing PNGs IN PLACE (pass --out DIR to keep the originals)", file=sys.stderr)
        for r in paths: print(r, run(r, out), "pinholes filled")
