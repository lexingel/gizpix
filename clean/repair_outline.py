#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Close breaks in the dark 1 px outline of generated sprites. Recolours, never adds or removes pixels, so the silhouette is unchanged.

  repair_outline.py fix IN_DIR OUT_DIR [--min-dark 2] [--y-min ROW]   (second pass for the legs: --min-dark 1 --y-min 88)
  repair_outline.py selftest

A body-edge pixel (opaque, with a transparent 4-neighbour) that is not outline-dark and not steel is recoloured to the most common
outline colour among its 8 neighbours when at least --min-dark of those neighbours are dark outline pixels, i.e. it sits in a gap of
the outline. Single dark neighbour (end of a line, toe tips, finger tips) is left alone. Steel-coloured edge pixels that are not part of the blade (blade ghosts hugging the outline) are recoloured to the outline colour, or removed when they sit outside an existing dark outline. Reports per frame. Label: locally repaired.
Needs numpy + Pillow.
"""
import sys, os, glob, re, json, argparse
import numpy as np
from PIL import Image


def load(p): return np.array(Image.open(p).convert("RGBA"))


def frame_paths(d):
    return sorted(glob.glob(os.path.join(d, "*.png")), key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)) or 0))


def _comps(m):
    h, w = m.shape; seen = np.zeros_like(m); out = []
    for y in range(h):
        for x in range(w):
            if m[y, x] and not seen[y, x]:
                st = [(y, x)]; seen[y, x] = True; c = []
                while st:
                    cy, cx = st.pop(); c.append((cy, cx))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True; st.append((ny, nx))
                out.append(c)
    return out


def repair(a, min_dark=2, skip_steel=True, y_min=0, grey_edge=True):
    a = a.copy(); op = a[..., 3] > 0; h, w = op.shape
    rgb = a[..., :3].astype(int); br = rgb.sum(2); sat = rgb.max(2) - rgb.min(2)
    P = np.pad(op, 1)
    edge = op & ~(P[0:h, 1:w + 1] & P[2:h + 2, 1:w + 1] & P[1:h + 1, 0:w] & P[1:h + 1, 2:w + 2])
    dark = edge & (br < 150)
    steel = op & (sat < 30) & (br > 200) & (br < 740)
    cand = edge & ~dark & ~(steel if skip_steel else np.zeros_like(steel))
    cand[:y_min] = False
    n = 0
    if grey_edge:                                   # steel-coloured edge pixels that are not part of the blade: blade ghosts on the outline
        blade = np.zeros_like(steel)
        for c in _comps(steel):
            if len(c) >= 25:                        # a real blade is 40+ px; ghost columns on the outline are shorter
                for y, x in c: blade[y, x] = True
        ghost = edge & steel & ~blade; ghost[:y_min] = False
        for y, x in zip(*np.where(ghost)):
            cols = [tuple(a[y + dy, x + dx, :3]) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy or dx) and 0 <= y + dy < h and 0 <= x + dx < w and dark[y + dy, x + dx]]
            if cols:
                a[y, x, :3] = max(set(cols), key=cols.count); n += 1
            elif any(op[y + dy, x + dx] and br[y + dy, x + dx] < 150 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                     if (dy or dx) and 0 <= y + dy < h and 0 <= x + dx < w):   # a grey layer outside the dark outline: remove it
                a[y, x] = 0; n += 1
    for y, x in zip(*np.where(cand)):
        cols = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if (dy or dx) and 0 <= y + dy < h and 0 <= x + dx < w and dark[y + dy, x + dx]:
                    cols.append(tuple(a[y + dy, x + dx, :3]))
        if len(cols) >= min_dark:
            a[y, x, :3] = max(set(cols), key=cols.count); n += 1
    return a, n


def run(src, dst, min_dark=2, skip_steel=True, y_min=0, grey_edge=True):
    os.makedirs(dst, exist_ok=True); rep = {}
    for p in frame_paths(src):
        a, n = repair(load(p), min_dark, skip_steel, y_min, grey_edge); rep[os.path.basename(p)] = n
        Image.fromarray(a).save(os.path.join(dst, os.path.basename(p)))
    json.dump(rep, open(os.path.join(dst, "outline_report.json"), "w"), indent=1)
    return rep


def selftest():
    a = np.zeros((16, 16, 4), np.uint8)
    a[4:12, 4:12] = (200, 150, 120, 255)
    a[3, 4:12] = (10, 5, 3, 255); a[12, 4:12] = (10, 5, 3, 255); a[4:12, 3] = (10, 5, 3, 255); a[4:12, 12] = (10, 5, 3, 255)
    a[3, 7] = (200, 150, 120, 255)                                     # a gap in the top outline
    b, n = repair(a)
    assert n == 1 and tuple(b[3, 7, :3]) == (10, 5, 3), (n, b[3, 7])
    assert (b[..., 3] == a[..., 3]).all(), "silhouette must not change"
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    else:
        ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("src"); ap.add_argument("dst")
        ap.add_argument("--min-dark", type=int, default=2); ap.add_argument("--y-min", type=int, default=0); a = ap.parse_args()
        print(run(a.src, a.dst, a.min_dark, True, a.y_min))
