#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""hue_shift.py - recolour sprites by turning the hue, optionally scaling saturation and value, optionally only for one hue range. Pixels keep their place on the light-to-dark ramp.

  hue_shift.py IN.png [IN2.png ...] --out DIR --hue DEGREES [--sat MUL] [--val MUL] [--range LO,HI] [--keep-dark V]
  hue_shift.py selftest

--hue    degrees to turn the hue, -180..180 (e.g. 120: red -> green). --sat / --val: multipliers (default 1).
--range  only recolour pixels whose hue (0..1 on the colour wheel: red 0, yellow .17, green .33, cyan .5, blue .67) lies in LO..HI (wraps round 1 if LO > HI), and which are not grey (saturation > 0.12).
--keep-dark V  leave pixels darker than value V alone (default 0.12, the black outline).
The mapping is a function of the colour alone: the same colour always gets the same result, in every file, so the frames of one animation stay consistent when you pass them together or one by
one with the same options. Alpha is untouched. Writes DIR/<same names>; never edits the input. Exit 2 on a missing file or bad option.
For named colour groups (skin, neutrals, a hue family to a chosen colour) use recolor_groups."""
import colorsys, os, sys
import numpy as np
from PIL import Image


def shift_rgb(a, hue_deg, sat=1.0, val=1.0, rng=None, keep_dark=0.12):
    """RGBA array -> RGBA array"""
    a = a.copy(); op = a[..., 3] > 0; rgb = a[op][:, :3].astype(np.int32); key = (rgb[:, 0] << 16) | (rgb[:, 1] << 8) | rgb[:, 2]
    ukeys, inv = np.unique(key, return_inverse=True); out = np.empty((len(ukeys), 3), np.uint8)       # one mapping per unique colour
    for i, k in enumerate(ukeys):
        c = ((k >> 16) & 255, (k >> 8) & 255, k & 255); h, s, v = colorsys.rgb_to_hsv(*(q / 255.0 for q in c))
        in_rng = True if not rng else (s > 0.12 and ((rng[0] <= h <= rng[1]) if rng[0] <= rng[1] else (h >= rng[0] or h <= rng[1])))
        if v < keep_dark or not in_rng: out[i] = c; continue
        out[i] = [int(round(q * 255)) for q in colorsys.hsv_to_rgb((h + hue_deg / 360.0) % 1.0, min(1, s * sat), min(1, v * val))]
    a[op, :3] = out[inv.reshape(-1)]
    return a


def selftest():
    a = np.zeros((4, 4, 4), np.uint8); a[:2] = (200, 40, 40, 255); a[2] = (30, 30, 200, 255); a[3, 0] = (5, 5, 5, 255)
    b = shift_rgb(a, 120); assert b[0, 0, 1] > b[0, 0, 0] and b[0, 0, 1] > b[0, 0, 2], b[0, 0]                      # red -> green
    assert tuple(b[3, 0]) == (5, 5, 5, 255) and (b[..., 3] == a[..., 3]).all()                                     # outline and alpha untouched
    c = shift_rgb(a, 120, rng=(0.95, 0.05)); assert tuple(c[2, 0]) == (30, 30, 200, 255) and c[0, 0, 1] > c[0, 0, 0]  # only the red range (wraps round 1)
    assert (shift_rgb(a, 0) == a).all()
    print("selftest ok")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0 if argv else 2
    if argv == ["selftest"]: selftest(); return 0
    import argparse
    ap = argparse.ArgumentParser(prog="hue_shift.py", add_help=False); ap.add_argument("files", nargs="+"); ap.add_argument("--out"); ap.add_argument("--hue", type=float); ap.add_argument("--sat", type=float, default=1.0)
    ap.add_argument("--val", type=float, default=1.0); ap.add_argument("--range"); ap.add_argument("--keep-dark", type=float, default=0.12)
    try: a = ap.parse_args(argv)
    except SystemExit: print("hue_shift: bad options (see -h)", file=sys.stderr); return 2
    if not a.out or a.hue is None: print("hue_shift: --out DIR and --hue DEGREES are required", file=sys.stderr); return 2
    try:
        rng = tuple(float(v) for v in a.range.split(",")) if a.range else None
        assert rng is None or len(rng) == 2
    except (ValueError, AssertionError): print("hue_shift: --range wants LO,HI (0..1)", file=sys.stderr); return 2
    if a.sat < 0 or a.val < 0 or not -360 <= a.hue <= 360: print("hue_shift: --sat and --val must be 0 or more, --hue within -360..360 degrees", file=sys.stderr); return 2
    if rng and not (0 <= rng[0] <= 1 and 0 <= rng[1] <= 1): print("hue_shift: --range values must be within 0..1", file=sys.stderr); return 2
    miss = [f for f in a.files if not os.path.isfile(f)]
    if miss: print(f"hue_shift: no such file: {miss[0]}", file=sys.stderr); return 2
    names = [os.path.basename(f) for f in a.files]; dup = sorted({n for n in names if names.count(n) > 1})
    if dup: print(f"hue_shift: two inputs share the file name {dup[0]!r}; the second would overwrite the first in --out. Rename them or run once per folder", file=sys.stderr); return 2
    noa = [f for f in a.files if Image.open(f).mode in ("RGB", "L", "P") and "transparency" not in Image.open(f).info]
    if noa: print(f"hue_shift: note: {len(noa)} input(s) have no alpha channel (first: {noa[0]}); every pixel counts as opaque", file=sys.stderr)

    os.makedirs(a.out, exist_ok=True)
    for f in a.files:
        im = np.array(Image.open(f).convert("RGBA")); out = shift_rgb(im, a.hue, a.sat, a.val, rng, a.keep_dark); Image.fromarray(out).save(os.path.join(a.out, os.path.basename(f)))
        print(os.path.basename(f), "recoloured", int(((out[..., :3] != im[..., :3]).any(-1) & (im[..., 3] > 0)).sum()), "pixels")
    return 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
