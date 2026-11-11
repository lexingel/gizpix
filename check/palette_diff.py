#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""palette_diff.py - compare the colours of sprites (directions, states, frames) against a reference. Measures only.

  palette_diff.py REF.png OTHER.png [OTHER2.png ...] [--tol 24] [--json] [--strict PCT]
  palette_diff.py selftest

For every OTHER: its number of colours, how many pixels use a colour that is exactly in REF, how many are within --tol of a REF colour (L1 over RGB, default 24: the same colour,
re-shaded) and how many are farther (a NEW colour), plus the new colours with their pixel count and the nearest REF colour. Use it to see whether directions or animation frames
drifted off the character's palette, or what an outfit state added. --strict PCT: exit 1 when any OTHER has more than PCT percent of its pixels farther than --tol.
Transparent pixels are ignored. Exit 2 on a missing file or bad option; otherwise 0."""
import collections, json, os, sys
import numpy as np
from PIL import Image


def colours(path):
    a = np.array(Image.open(path).convert("RGBA")); return collections.Counter(map(tuple, a[a[..., 3] > 0][:, :3].tolist()))


def diff(ref, other, tol=24):
    """dict of numbers for one OTHER against REF (both Counters)"""
    if not ref: raise ValueError("the reference has no opaque pixels")
    R = np.array(list(ref), int); tot = sum(other.values()); exact = near = far = 0; new = []
    for c, n in other.items():
        d = np.abs(R - np.array(c)).sum(1); k = int(d.argmin())
        if d[k] == 0: exact += n
        elif d[k] <= tol: near += n
        else: far += n; new.append((n, "#%02x%02x%02x" % c, "#%02x%02x%02x" % tuple(R[k]), int(d[k])))
    return {"colors": len(other), "pixels": tot, "exact_pct": round(100 * exact / max(1, tot), 1), "near_pct": round(100 * near / max(1, tot), 1), "new_pct": round(100 * far / max(1, tot), 1),
            "new_colors": [{"px": n, "color": c, "nearest_ref": r, "dist": d} for n, c, r, d in sorted(new, reverse=True)[:8]]}


def selftest():
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as t:
        a = np.zeros((6, 6, 4), np.uint8); a[:3] = (10, 20, 30, 255); a[3:5] = (200, 100, 50, 255); Image.fromarray(a).save(t + "/ref.png")
        b = a.copy(); b[0, 0, :3] = (14, 22, 30); b[5, 0] = (0, 250, 0, 255); Image.fromarray(b).save(t + "/o.png")
        d = diff(colours(t + "/ref.png"), colours(t + "/o.png")); assert d["near_pct"] > 0 and d["new_pct"] > 0 and d["new_colors"][0]["color"] == "#00fa00", d
        assert diff(colours(t + "/ref.png"), colours(t + "/ref.png"))["exact_pct"] == 100.0
    print("selftest ok")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0 if argv else 2
    if argv == ["selftest"]: selftest(); return 0
    import argparse
    ap = argparse.ArgumentParser(prog="palette_diff.py", add_help=False); ap.add_argument("files", nargs="+"); ap.add_argument("--tol", type=int, default=24); ap.add_argument("--json", action="store_true"); ap.add_argument("--strict", type=float)
    try: a = ap.parse_args(argv)
    except SystemExit: print("palette_diff: bad options (see -h)", file=sys.stderr); return 2
    if len(a.files) < 2: print("palette_diff: give REF.png and at least one OTHER.png", file=sys.stderr); return 2
    miss = [f for f in a.files if not os.path.isfile(f)]
    if miss: print(f"palette_diff: no such file: {miss[0]}", file=sys.stderr); return 2
    if a.tol < 0: print("palette_diff: --tol must be 0 or more", file=sys.stderr); return 2
    noa = [f for f in a.files if Image.open(f).mode in ("RGB", "L", "P") and "transparency" not in Image.open(f).info]
    if noa: print(f"palette_diff: note: {len(noa)} input(s) have no alpha channel (first: {noa[0]}); every pixel counts as opaque", file=sys.stderr)

    try:
        ref = colours(a.files[0]); oth = {f: colours(f) for f in a.files[1:]}
        empty = [f for f, c in oth.items() if not c]
        if empty: raise ValueError(f"{empty[0]} has no opaque pixels")
        res = {f: diff(ref, c, a.tol) for f, c in oth.items()}
    except ValueError as e: print(f"palette_diff: {e}", file=sys.stderr); return 2
    if a.json: print(json.dumps({"reference": a.files[0], "colors": len(ref), "tol": a.tol, "others": res}, indent=1))
    else:
        print(f"reference {a.files[0]}: {len(ref)} colours; tol {a.tol}")
        for f, r in res.items():
            print(f"{f}: {r['colors']} colours, exact {r['exact_pct']}% near {r['near_pct']}% NEW {r['new_pct']}%" + ("  new: " + ", ".join(f"{c['color']}x{c['px']}(~{c['nearest_ref']})" for c in r["new_colors"][:4]) if r["new_colors"] else ""))
    return 1 if a.strict is not None and any(r["new_pct"] > a.strict for r in res.values()) else 0


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
