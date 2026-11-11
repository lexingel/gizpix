#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""align_frames.py - move frames by whole pixels so one anchor point sits at the same place in every frame (feet on one line, body on one column). Never resamples or recolours.

  align_frames.py FRAME.png [FRAME2.png ...] --out DIR [--y feet|top|none] [--x mass|bbox|none] [--to X,Y] [--allow-clip]
  align_frames.py selftest

Anchor per frame:  --y feet = the lowest opaque row (default; a walk keeps one foot planted, so the line is steady) | top = the highest row | none.
                   --x mass = the centre of mass of the opaque pixels | bbox = the middle of the opaque bounding box | none = leave x (default).
Target: the first frame's anchor, or --to X,Y (either coordinate may be left empty: --to ,95 only sets the feet row).
Frames keep their canvas size. A frame whose content would be pushed off the canvas is an error (exit 2) unless --allow-clip (the clipped pixels are lost).
Note: in a walk the lowest row moves by 1-2 px as the feet swap (the natural bob; measured on the skeleton-v3 walk), so aligning feet there flattens that bob: use it for frames whose ground line drifted
(key poses, in-betweens), not to 'fix' a walk that already looks right.
Prints the shift of every frame as 'dx,dy': keep it if the engine needs the original offsets. Frames must have the same size. Exit 2 on a missing file or bad option."""
import os, sys
import numpy as np
from PIL import Image


def anchor(a, y, x):
    """(ax, ay) of an RGBA array; None parts for 'none'. Raises ValueError for an empty frame."""
    ys, xs = np.nonzero(a[..., 3] > 0)
    if not len(xs): raise ValueError("a frame is fully transparent")
    ay = {"feet": int(ys.max()), "top": int(ys.min()), "none": None}[y]
    ax = {"mass": int(round(xs.mean())), "bbox": int((xs.min() + xs.max()) // 2), "none": None}[x]
    return ax, ay


def shift(a, dx, dy):
    """a shifted by whole pixels (dx right, dy down); returns (array, lost_pixels)"""
    h, w = a.shape[:2]; out = np.zeros_like(a); op = a[..., 3] > 0
    ys, xs = np.nonzero(op); ny, nx = ys + dy, xs + dx; keep = (ny >= 0) & (ny < h) & (nx >= 0) & (nx < w)
    out[ny[keep], nx[keep]] = a[ys[keep], xs[keep]]; return out, int((~keep).sum())


def align(ims, y="feet", x="none", to=(None, None), allow_clip=False):
    """list of RGBA images -> (aligned images, shifts); raises ValueError on size mismatch, empty frames or clipping"""
    arrs = [np.array(i.convert("RGBA")) for i in ims]
    if len({a.shape for a in arrs}) != 1: raise ValueError("frames have different sizes")
    anc = [anchor(a, y, x) for a in arrs]; tx = to[0] if to[0] is not None else anc[0][0]; ty = to[1] if to[1] is not None else anc[0][1]
    out, sh = [], []
    for k, (a, (ax, ay)) in enumerate(zip(arrs, anc)):
        dx = (tx - ax) if (tx is not None and ax is not None) else 0
        dy = (ty - ay) if (ty is not None and ay is not None) else 0
        b, lost = shift(a, dx, dy)
        if lost and not allow_clip: raise ValueError(f"frame {k}: shifting by {dx},{dy} would push {lost} pixels off the canvas (use --allow-clip, or a bigger canvas)")
        out.append(Image.fromarray(b)); sh.append((dx, dy))
    return out, sh


def selftest():
    def fr(x0, y0):
        a = np.zeros((40, 30, 4), np.uint8); a[y0:y0 + 10, x0:x0 + 6] = (9, 9, 9, 255); return Image.fromarray(a)
    ims = [fr(10, 15), fr(12, 12), fr(8, 18)]
    out, sh = align(ims); ys = [int(np.nonzero(np.array(i)[..., 3])[0].max()) for i in out]; assert len(set(ys)) == 1 and sh[0] == (0, 0), (ys, sh)
    out, sh = align(ims, x="bbox"); xs = [np.nonzero(np.array(i)[..., 3])[1] for i in out]; assert len({(q.min(), q.max()) for q in xs}) == 1
    out, sh = align(ims, to=(None, 30)); assert all(int(np.nonzero(np.array(i)[..., 3])[0].max()) == 30 for i in out)
    out, sh = align(ims, y="none", x="none"); assert sh == [(0, 0)] * 3
    try: align(ims, to=(None, 45)); raise SystemExit("accepted clipping")
    except ValueError: pass
    align(ims, to=(None, 45), allow_clip=True)
    try: align([ims[0], Image.new("RGBA", (5, 5))]); raise SystemExit("accepted a size mismatch")
    except ValueError: pass
    print("selftest ok")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0 if argv else 2
    if argv == ["selftest"]: selftest(); return 0
    import argparse
    ap = argparse.ArgumentParser(prog="align_frames.py", add_help=False); ap.add_argument("frames", nargs="+"); ap.add_argument("--out"); ap.add_argument("--y", default="feet", choices=("feet", "top", "none"))
    ap.add_argument("--x", default="none", choices=("mass", "bbox", "none")); ap.add_argument("--to", default=","); ap.add_argument("--allow-clip", action="store_true")
    try: a = ap.parse_args(argv)
    except SystemExit: print("align_frames: bad options (see -h)", file=sys.stderr); return 2
    if not a.out: print("align_frames: --out DIR is required", file=sys.stderr); return 2
    miss = [f for f in a.frames if not os.path.isfile(f)]
    if miss: print(f"align_frames: no such file: {miss[0]}", file=sys.stderr); return 2
    names = [os.path.basename(f) for f in a.frames]; dup = sorted({n for n in names if names.count(n) > 1})
    if dup: print(f"align_frames: two inputs share the file name {dup[0]!r}; the second would overwrite the first in --out. Rename them or run once per folder", file=sys.stderr); return 2
    noa = [f for f in a.frames if Image.open(f).mode in ("RGB", "L", "P") and "transparency" not in Image.open(f).info]
    if noa: print(f"align_frames: note: {len(noa)} input(s) have no alpha channel (first: {noa[0]}); every pixel counts as opaque", file=sys.stderr)
    try: tx, ty = (int(v) if v.strip() else None for v in (a.to.split(",") + [""])[:2])
    except ValueError: print("align_frames: --to wants X,Y numbers (either may be empty)", file=sys.stderr); return 2
    try: ims, sh = align([Image.open(f) for f in a.frames], a.y, a.x, (tx, ty), a.allow_clip)
    except ValueError as e: print(f"align_frames: {e}", file=sys.stderr); return 2
    os.makedirs(a.out, exist_ok=True)
    for f, im, s in zip(a.frames, ims, sh): im.save(os.path.join(a.out, os.path.basename(f))); print(os.path.basename(f), "shift", f"{s[0]},{s[1]}")
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
