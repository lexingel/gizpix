# SPDX-License-Identifier: AGPL-3.0-or-later
"""painterly_clean.py - close holes and dull white specks in painterly sprites and frames. Free.

Soft-shaded sprites (100+ colours) come out of the generator with defects that show as white dots once they stand
on a dark background or get scaled up for a close-up:
  - holes: transparent pockets inside cloth, closed all round (the background shows through). Default up to 4 px:
    on 220 sprites 83% of enclosed pockets were 1-4 px and all looked like defects; 5-40 px pockets are often real
    gaps (between a staff and the arm, a shield and the body). Raise --max-hole only after looking at --marks;
  - cracks (--cracks): 1-2 px slits that open to the outside, so a hole fill can't reach them. Off by default: it
    also closes the notches between sunburst rays, feathers, flame tongues and fringe. Use it on a clip whose
    cracks you have seen (cloth split from the outside), not on a whole set;
  - lone bright pixels: one pixel far brighter than all 8 neighbours (generation noise in dark cloth);
  - white dots: detached bits of <= 4 px, near white;
  - trim dots (--trim): bright cream specks scattered along dark cloth, each a little brighter than its 3x3 median.
    They read as white dots too. Each takes the sprite's own gold/mid tone closest in hue. Bright blobs of 6+ px
    (fire, glow, a lit edge) are left alone, but so are small glints drawn on purpose - claw tips, eye shines,
    metal highlights - only when they are 6+ px: check --marks on creatures and armour.
On animation frames with baked-in effects use --holes-only: the white-dot drop and the lone-bright fix also take
spell sparks, embers, slash-trail dots, metal and eye glints (seen on 1,020 clips). Dithered see-through effects
(checkerboard smears) are never filled.
Holes and cracks take the median colour of their opaque neighbours, filled from the edge inward. Then, with --ref,
every pixel snaps to the nearest reference colour (luma-weighted) - a recolour, never a drop. Dropping off-palette
pixels (a palette key) is what punches these holes into painterly frames in the first place.

    python painterly_clean.py frames/*.png [--out dir] [--ref ref.png] [--trim] [--cracks] [--max-hole 4] [--marks dir] [--holes-only]
    python painterly_clean.py selftest

Writes in place unless --out. Prints one line of counts per file. --marks DIR writes <name>_marks.png per file
(before | after | what changed: red holes, yellow cracks, cyan lone bright, magenta trim) at 3x: look before keeping.
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

for _s in (sys.stdout, sys.stderr):   # Windows consoles: never crash on non-ASCII text
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

W = np.array([.3, .59, .11], np.float32)
OFF = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]


def luma(a):
    return (a[..., :3].astype(np.float32) * W).sum(-1)


def shifted(m, fill=0):
    """The 8 neighbour views of a 2-D array (padded with fill)."""
    P = np.pad(m, 1, constant_values=fill)
    h, w = m.shape
    return [P[1 + dy:h + 1 + dy, 1 + dx:w + 1 + dx] for dy, dx in OFF]


def take_median(a, pts):
    for y, x in pts:
        nb = a[max(0, y - 1):y + 2, max(0, x - 1):x + 2].reshape(-1, 4)
        nb = nb[nb[:, 3] == 255][:, :3]
        a[y, x, :3] = np.median(nb, 0).astype(np.uint8)
        a[y, x, 3] = 255


def fill_holes(a, max_px=40):
    o = a[..., 3] == 255
    lab, n = ndimage.label(~o)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    sizes = ndimage.sum(~o, lab, range(1, n + 1))
    hole = np.isin(lab, [i for i, s in enumerate(sizes, 1) if s <= max_px and i not in border])
    # dithered see-through effects (checkerboard slash smears, mist, ghost bodies) are fields of 1 px holes drawn on
    # purpose: a 1 px hole with 3+ other 1 px holes in its 7x7 neighbourhood is a pattern, not a pinhole
    one = np.isin(lab, [i for i, s in enumerate(sizes, 1) if s == 1 and i not in border])
    hole &= ~(one & (ndimage.uniform_filter(one.astype(np.float32), 7) * 49 > 3.5))
    filled = 0
    while hole.any():
        cnt = sum(v.astype(int) for v in shifted(a[..., 3] == 255))
        edge = np.argwhere(hole & (cnt > 0))
        take_median(a, edge)
        hole[tuple(edge.T)] = False
        filled += len(edge)
    return filled


def fill_cracks(a, need=5, rounds=4):
    filled = 0
    for _ in range(rounds):
        o = a[..., 3] == 255
        closed = ndimage.binary_closing(o, structure=np.ones((3, 3)))
        cnt = sum(v.astype(int) for v in shifted(o))
        pts = np.argwhere(closed & ~o & (cnt >= need))
        if not len(pts):
            break
        take_median(a, pts)
        filled += len(pts)
    return filled


def drop_white_dots(a, max_px=4, min_luma=200):
    o = a[..., 3] == 255
    lab, n = ndimage.label(o, structure=np.ones((3, 3)))
    sizes = ndimage.sum(o, lab, range(1, n + 1))
    lum = luma(a)
    gone = 0
    for i, s in enumerate(sizes, 1):
        if s <= max_px and lum[lab == i].mean() > min_luma:
            a[lab == i, 3] = 0
            gone += int(s)
    return gone


def fix_lone_bright(a, jump=60, floor=150):
    o = a[..., 3] == 255
    lum = luma(a)
    nbmax = np.max(shifted(np.where(o, lum, -1), -1), 0)
    full = sum(v.astype(int) for v in shifted(o)) == 8
    pts = np.argwhere(o & full & (lum > floor) & (lum - nbmax > jump))
    for y, x in pts:
        a[y, x, :3] = np.median(a[y - 1:y + 2, x - 1:x + 2].reshape(-1, 4)[[0, 1, 2, 3, 5, 6, 7, 8], :3], 0)
    return len(pts)


def dull_trim(a, floor=150, jump=70, blob=6, tone=(85, 125)):
    """Bright specks over a darker 3x3 median, not part of a bright blob of >= `blob` px, take the palette's mid
    tone (luma in `tone`) closest in hue."""
    o = a[..., 3] == 255
    lum = luma(a)
    med = ndimage.median_filter(np.where(o, lum, 0), size=3)
    bright = o & (lum > floor)
    lab, n = ndimage.label(bright, structure=np.ones((3, 3)))
    big = np.isin(lab, [i for i, s in enumerate(ndimage.sum(bright, lab, range(1, n + 1)), 1) if s >= blob])
    dots = bright & ~big & (lum - med > jump)
    cols = np.unique(a[o][:, :3], axis=0)
    cl = luma(cols[None])[0]
    mids = cols[(cl >= tone[0]) & (cl <= tone[1])].astype(np.float32)
    if not len(mids) or not dots.any():
        return 0
    def hue(c):
        c = c / (np.linalg.norm(c, axis=-1, keepdims=True) + 1e-6)
        return c
    px = a[dots][:, :3].astype(np.float32)
    idx = (hue(px)[:, None] * hue(mids)[None]).sum(-1).argmax(1)
    a[dots, :3] = mids[idx].astype(np.uint8)
    return int(dots.sum())


def snap(a, pal):
    m = a[..., 3] == 255
    px = a[m][:, :3].astype(np.float32)
    idx = np.concatenate([(((px[i:i + 4096, None] - pal[None]) * W) ** 2).sum(-1).argmin(1)
                          for i in range(0, len(px), 4096)] or [np.zeros(0, int)])
    a[m, :3] = pal[idx].astype(np.uint8)


def clean(a, pal=None, trim=False, max_hole=4, cracks=False, marks=None, holes_only=False):
    """Cleans a in place; returns the counts. `marks` (an int array like a's shape[:2]) gets 1-4 per changed pixel."""
    a[..., 3] = np.where(a[..., 3] >= 128, 255, 0)
    def mark(k, before):
        if marks is not None:
            marks[(a != before).any(-1) & (marks == 0)] = k
    b = a.copy(); n = dict(holes=fill_holes(a, max_hole)); mark(1, b)
    if cracks:
        b = a.copy(); n['cracks'] = fill_cracks(a); mark(2, b)
    if holes_only:
        return n
    n['white_dots'] = drop_white_dots(a)
    b = a.copy(); n['lone_bright'] = fix_lone_bright(a); mark(3, b)
    if trim:
        b = a.copy(); n['trim_dots'] = dull_trim(a); mark(4, b)
    if pal is not None:
        snap(a, pal)
    return n


def marks_sheet(a0, a, marks, path):
    bg = Image.new('RGBA', (a.shape[1], a.shape[0]), (24, 20, 28, 255))
    def on(x):
        im = bg.copy(); im.alpha_composite(Image.fromarray(x)); return np.array(im)
    mk = on(a0) // 3
    mk[..., 3] = 255
    for k, c in {1: (255, 40, 40), 2: (255, 230, 0), 3: (0, 255, 255), 4: (255, 0, 255)}.items():
        mk[marks == k, :3] = c
    im = Image.fromarray(np.concatenate([on(a0), on(a), mk], 1))
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(path)


def selftest():
    a = np.zeros((20, 20, 4), np.uint8)
    a[2:18, 2:18] = (60, 30, 30, 255)
    a[8:11, 8:11, 3] = 0              # enclosed 9 px hole
    a[2:6, 12, 3] = 0                 # crack open to the top edge of the shape
    a[14, 5] = (240, 240, 230, 255)   # lone bright pixel
    a[0, 0] = (255, 255, 255, 255)    # detached white dot
    n = clean(a, max_hole=40, cracks=True)
    assert a[8:11, 8:11, 3].all() and (a[9, 9, :3] == (60, 30, 30)).all(), n
    assert a[3:6, 12, 3].all(), ('crack', n)
    assert (a[14, 5, :3] == (60, 30, 30)).all(), n
    assert a[0, 0, 3] == 0, n
    b = np.zeros((20, 20, 4), np.uint8)
    b[2:18, 2:18] = (60, 30, 30, 255)
    b[8:11, 8:11, 3] = 0              # a 9 px gap: kept by default (could be a gap between staff and arm)
    b[2:6, 12, 3] = 0                 # a notch from outside: kept without --cracks
    clean(b)
    assert not b[9, 9, 3] and not b[4, 12, 3], 'defaults keep gaps and notches'
    c = np.zeros((20, 20, 4), np.uint8)
    c[2:18, 2:18] = (230, 240, 255, 255)
    c[4:16:2, 4:16:2, 3] = 0          # a checkerboard dither (a see-through slash smear): kept
    c[17, 10] = (240, 240, 235, 255)  # a lone near-white pixel on the shape's edge - with holes_only nothing else runs
    c0 = c.copy(); clean(c, holes_only=True)
    assert (c == c0).all(), 'dither kept, holes_only touches nothing but pinholes'
    print('selftest ok', n)


if __name__ == '__main__':
    if sys.argv[1:] == ['selftest']:
        selftest()
        sys.exit()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', nargs='+')
    ap.add_argument('--out')
    ap.add_argument('--ref', nargs='+', help='snap every pixel to the colours of these sprites')
    ap.add_argument('--trim', action='store_true', help='dull bright trim dots to the sprite\'s own mid tone')
    ap.add_argument('--cracks', action='store_true', help='also fill 1-2 px slits open to the outside (look first)')
    ap.add_argument('--max-hole', type=int, default=4)
    ap.add_argument('--marks', help='write <name>_marks.png (before | after | changes) here')
    ap.add_argument('--holes-only', action='store_true',
                    help='only fill pinholes (the safe set for animation frames with baked-in sparks, embers, trails)')
    ar = ap.parse_args()
    files = [g for f in ar.frames for g in (sorted(glob.glob(f)) if any(c in f for c in '*?') else [f])]
    pal = None
    if ar.ref:
        rs = [np.asarray(Image.open(r).convert('RGBA')) for r in ar.ref]
        pal = np.unique(np.concatenate([r[r[..., 3] >= 128][:, :3] for r in rs]), axis=0).astype(np.float32)
    if not ar.out: print('painterly_clean: editing %d file(s) IN PLACE (pass --out DIR to keep the originals)' % len(files), file=sys.stderr)
    if ar.out:
        os.makedirs(ar.out, exist_ok=True)
    for f in files:
        a = np.array(Image.open(f).convert('RGBA'))
        a0, mk = a.copy(), np.zeros(a.shape[:2], int)
        n = clean(a, pal, ar.trim, ar.max_hole, ar.cracks, mk, ar.holes_only)
        if ar.marks:
            os.makedirs(ar.marks, exist_ok=True)
            marks_sheet(a0, a, mk, os.path.join(ar.marks, os.path.splitext(os.path.basename(f))[0] + '_marks.png'))
        Image.fromarray(a).save(os.path.join(ar.out, os.path.basename(f)) if ar.out else f)
        print(os.path.basename(f), ' '.join(f'{k} {v}' for k, v in n.items()))
