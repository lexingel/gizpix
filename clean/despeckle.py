# SPDX-License-Identifier: AGPL-3.0-or-later
"""despeckle.py - clear lone pixels from animation frames. Free.

Generated in-between frames leave single pixels that match none of their neighbours: a white dot on a black coat, a
pink dot on a hair edge. On dark outfits they read as holes and noise. This takes each pixel that is unlike all 8 of
its neighbours and gives it their median colour; an opaque pixel with no opaque neighbour (a stray) goes
transparent. Two or more alike pixels together (a highlight, an eye glint) stay.

    python despeckle.py frames/*.png [--out dir] [--tol 90]

--tol: colour distance (sum of |dR|+|dG|+|dB|) under which a neighbour counts as alike. Writes in place unless --out.
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

for _s in (sys.stdout, sys.stderr):   # Windows consoles: never crash on non-ASCII text
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('frames', nargs='+')
ap.add_argument('--out')
ap.add_argument('--tol', type=int, default=90)
a = ap.parse_args()
files = [g for f in a.frames for g in (sorted(glob.glob(f)) if any(c in f for c in '*?') else [f])]
if not a.out: print('despeckle: editing %d file(s) IN PLACE (pass --out DIR to keep the originals)' % len(files), file=sys.stderr)
OFF = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
for f in files:
    im = np.array(Image.open(f).convert('RGBA'))
    h, w = im.shape[:2]
    pad = np.zeros((h + 2, w + 2, 4), np.int32)
    pad[1:-1, 1:-1] = im
    op = im[..., 3] > 0
    nb = np.stack([pad[1 + dy:h + 1 + dy, 1 + dx:w + 1 + dx] for dy, dx in OFF])     # 8 x h x w x 4
    nb_op = nb[..., 3] > 0
    alike = nb_op & (np.abs(nb[..., :3] - im[None, ..., :3].astype(np.int32)).sum(-1) < a.tol)
    stray = op & (nb_op.sum(0) == 0)   # (one neighbour is a line end - a whip tip, a hair strand - and stays)
    speck = op & ~stray & (alike.sum(0) == 0)
    out = im.copy()
    if speck.any():
        cols = np.where(nb_op[..., None], nb[..., :3], np.nan)                         # median of the opaque ones
        med = np.nanmedian(cols[:, speck], axis=0)
        out[speck, :3] = np.round(med).astype(np.uint8)
    out[stray, 3] = 0
    dst = os.path.join(a.out, os.path.basename(f)) if a.out else f
    if a.out:
        os.makedirs(a.out, exist_ok=True)
    Image.fromarray(out).save(dst)
    print('%s: %d specks, %d strays' % (os.path.basename(f), int(speck.sum()), int(stray.sum())))
