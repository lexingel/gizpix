# SPDX-License-Identifier: AGPL-3.0-or-later
"""ground_snap.py <standing_sprite.png> <pad_x,pad_y> <frame.png>... [--out DIR] [--check]

Generated key poses and their in-betweens are often drawn a few to ~20 px higher on the padded
canvas than the standing sprite (kneels, lunges, crouches), so in the game the character hops off
the ground. For grounded moves (a foot or knee always on the floor) this moves each frame down so
its lowest opaque pixel sits exactly on the standing sprite's feet line (pad_y + sprite height - 1).
Frames already on or below the line are left alone. Writes in place unless --out is given (then every frame goes there, moved or not).
--fx 5,6 leaves frames with no feet on purpose (smoke-only frames of a vanish) alone. The numbers are positions in
the frame list, counting from 1 (with 0.png ... 9.png, --fx 5,6 means 4.png and 5.png).
--check only prints each frame's gap (negative = floating) and changes nothing.
Don't use it on jumps, leaps or flying characters.

  python ground_snap.py hero.png 24,56 out/hero_attack_*.png --check
  python ground_snap.py hero.png 24,56 out/hero_attack_*.png
"""
import argparse
import sys
for _s in (sys.stdout, sys.stderr):   # Windows consoles: never crash on non-ASCII text
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def _expand(paths):
    """cmd/PowerShell pass *.png literally: expand * and ? here (natural order, so 2.png comes before 10.png)."""
    import glob
    import re
    out = []
    for p in paths:
        hits = glob.glob(p) if ('*' in p or '?' in p) else []
        out += sorted(hits, key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)]) or [p]
    return out

import os
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('sprite')
ap.add_argument('pad')
ap.add_argument('frames', nargs='+')
ap.add_argument('--out')
ap.add_argument('--check', action='store_true')
ap.add_argument('--fx', default='', help='frames with no feet on purpose, e.g. smoke-only frames: left alone. Numbers are positions in the frame list you gave, counting from 1 (not file names: 0.png is 1)')
a = ap.parse_args()
a.frames = _expand(a.frames)
st = np.array(Image.open(a.sprite).convert('RGBA'))[..., 3] > 0
pad_y = int(a.pad.split(',')[1])
feet = pad_y + int(np.nonzero(st.any(1))[0].max())
fx = {int(v) - 1 for v in a.fx.split(',') if v.strip()}
if not a.out and not a.check: print('ground_snap: moving frames IN PLACE where needed (pass --out DIR to keep the originals, --check to only measure)', file=__import__('sys').stderr)
for n, f in enumerate(a.frames):
    im = Image.open(f).convert('RGBA')
    al = np.array(im)[..., 3] > 0
    if not al.any():
        print('EMPTY', f)
        continue
    if n in fx:   # smoke-only frames have no feet to judge
        print('  fx  %s' % f)
        if a.out and not a.check:
            os.makedirs(a.out, exist_ok=True)
            im.save(os.path.join(a.out, os.path.basename(f)))
        continue
    gap = int(np.nonzero(al.any(1))[0].max()) - feet
    print('%+4d  %s%s' % (gap, f, '   below the feet line: something hangs lower (a robe, an effect?) - not moved, look at it' if gap > 0 else ''))
    if a.check or (gap >= 0 and not a.out):
        continue
    out = Image.new('RGBA', im.size)
    out.alpha_composite(im, (0, -min(gap, 0)))
    if a.out:   # --out gets every frame, moved or not, so it holds the whole clip
        os.makedirs(a.out, exist_ok=True)
    dst = os.path.join(a.out, os.path.basename(f)) if a.out else f
    out.save(dst)
