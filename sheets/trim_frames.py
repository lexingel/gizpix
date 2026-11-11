#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""trim_frames.py - crop frames to the content they share, so a sprite sheet is not full of empty margin. Only crops; pixels are never changed.

  trim_frames.py FRAME.png [FRAME2.png ...] --out DIR [--pad N] [--each]
  trim_frames.py selftest

Default: ONE box for all frames (the union of every frame's opaque pixels, plus --pad on every side), so the frames keep the same size and the same
anchor and an animation does not jump. --each trims every frame to its own box instead (sizes differ: only for loose sprites, not animations).
Prints the box as 'x0,y0,x1,y1' of the original canvas: store it if the engine needs the original offset (the trimmed frame's top-left sits at x0,y0).
Frames must have the same size when sharing a box. Exit 2 on missing files, size mismatch or a fully transparent set."""
import os, sys
import numpy as np
from PIL import Image


def box(a, pad=0):
    ys, xs = np.nonzero(a[..., 3] > 0)
    if not len(xs): return None
    h, w = a.shape[:2]; return max(0, xs.min() - pad), max(0, ys.min() - pad), min(w, xs.max() + 1 + pad), min(h, ys.max() + 1 + pad)


def trim(ims, pad=0, each=False):
    """list of RGBA images -> (list of cropped images, list of boxes)"""
    arrs = [np.array(i.convert("RGBA")) for i in ims]
    if each: bx = [box(a, pad) for a in arrs]
    else:
        if len({a.shape for a in arrs}) != 1: raise ValueError("frames have different sizes; trim them one by one with --each, or resize first")
        u = np.zeros(arrs[0].shape[:2], bool)
        for a in arrs: u |= a[..., 3] > 0
        b = box(np.dstack([u * 0, u * 0, u * 0, u * 255]).astype(np.uint8), pad); bx = [b] * len(arrs)
    if any(b is None for b in bx): raise ValueError("a frame (or the whole set) is fully transparent")
    return [Image.fromarray(a[b[1]:b[3], b[0]:b[2]]) for a, b in zip(arrs, bx)], bx


def selftest():
    a = np.zeros((20, 30, 4), np.uint8); a[5:10, 8:12] = 255; b = a.copy(); b[5:10, 8:12] = 0; b[12:15, 14:20] = 255
    out, bx = trim([Image.fromarray(a), Image.fromarray(b)], pad=1)
    assert bx[0] == bx[1] == (7, 4, 21, 16) and out[0].size == out[1].size == (14, 12), bx
    out, bx = trim([Image.fromarray(a), Image.fromarray(b)], each=True); assert out[0].size == (4, 5) and out[1].size == (6, 3)
    out, bx = trim([Image.fromarray(a), Image.fromarray(np.zeros_like(a))]); assert bx[0] == bx[1] and out[1].size == out[0].size      # one blank frame inside a shared box is fine
    for kw in ({"each": True}, {}):                                                                                                     # but an empty frame on its own, or an all-empty set, is an error
        try: trim([Image.fromarray(a), Image.fromarray(np.zeros_like(a))] if kw else [Image.fromarray(np.zeros_like(a))] * 2, **kw); raise SystemExit("accepted an empty frame")
        except ValueError: pass
    print("selftest ok")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0 if argv else 2
    if argv == ["selftest"]: selftest(); return 0
    import argparse
    ap = argparse.ArgumentParser(prog="trim_frames.py", add_help=False); ap.add_argument("frames", nargs="+"); ap.add_argument("--out"); ap.add_argument("--pad", type=int, default=0); ap.add_argument("--each", action="store_true")
    try: a = ap.parse_args(argv)
    except SystemExit: print("trim_frames: bad options (see -h)", file=sys.stderr); return 2
    files, out, pad = a.frames, a.out, a.pad
    if not out: print("trim_frames: --out DIR is required", file=sys.stderr); return 2
    if pad < 0: print("trim_frames: --pad must be 0 or more", file=sys.stderr); return 2
    miss = [f for f in files if not os.path.isfile(f)]
    if miss: print(f"trim_frames: no such file: {miss[0]}", file=sys.stderr); return 2
    names = [os.path.basename(f) for f in files]; dup = sorted({n for n in names if names.count(n) > 1})
    if dup: print(f"trim_frames: two inputs share the file name {dup[0]!r}; the second would overwrite the first in --out. Rename them or run once per folder", file=sys.stderr); return 2
    noa = [f for f in files if Image.open(f).mode in ("RGB", "L", "P") and "transparency" not in Image.open(f).info]
    if noa: print(f"trim_frames: note: {len(noa)} input(s) have no alpha channel (first: {noa[0]}); every pixel counts as opaque", file=sys.stderr)
    try: ims, bx = trim([Image.open(f) for f in files], pad, a.each)
    except ValueError as e: print(f"trim_frames: {e}", file=sys.stderr); return 2
    os.makedirs(out, exist_ok=True)
    for f, im, b in zip(files, ims, bx): im.save(os.path.join(out, os.path.basename(f))); print(os.path.basename(f), "box", ",".join(map(str, b)), "size", f"{im.width}x{im.height}")
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
