# SPDX-License-Identifier: AGPL-3.0-or-later
"""apply_palette.py <palette> <image.png>... [--out DIR] [--colors N]
Snaps every opaque pixel to the nearest colour of a fixed palette (no dithering), so generated art
obeys a profile's colour rule. <palette> = an analysis.json from analyze_style.py, a palette.png of
swatches, a .hex/.txt file (one #rrggbb per line) or comma-separated hex. --colors N first reduces
the palette to the N most used colours of the given palette (or, with <palette> = "auto", to the image's
own N main colours). Transparent pixels stay transparent. Writes in place unless --out is given.

  python apply_palette.py style_analysis/analysis.json out/hero.png
  python apply_palette.py auto out/frames/*.png --colors 16
"""
import sys as _sys
if any(_a in ("-h", "--help") for _a in _sys.argv[1:]): print(__doc__); _sys.exit(0)     # -h always prints the documentation, exit 0
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

if len(sys.argv) < 3 or sys.argv[1] in ('-h', '--help'):
    sys.exit(__doc__)
import json
import os
import numpy as np
from PIL import Image

args = sys.argv[1:]
out = None
n = 0
if '--out' in args:
    i = args.index('--out'); out = args[i + 1]; del args[i:i + 2]; os.makedirs(out, exist_ok=True)
if '--colors' in args:
    i = args.index('--colors'); n = int(args[i + 1]); del args[i:i + 2]
pal_arg, files = args[0], _expand(args[1:])
if not out: print('apply_palette: editing %d file(s) IN PLACE (pass --out DIR to keep the originals)' % len(files), file=sys.stderr)


def hexes(h):
    toks = [x.strip() for x in h if x.strip()]
    bad = [t for t in toks if not __import__('re').fullmatch(r'#?[0-9a-fA-F]{6}', t)]
    if bad or not toks:
        print('apply_palette: ' + ('no colours in the palette' if not toks else 'not a #rrggbb colour: %r' % bad[0]), file=sys.stderr); sys.exit(2)
    return [tuple(int(x.lstrip('#')[j:j + 2], 16) for j in (0, 2, 4)) for x in toks]


def _die(msg):
    print('apply_palette: ' + msg, file=sys.stderr); sys.exit(2)


if pal_arg != 'auto' and not os.path.isfile(pal_arg):
    import re
    if pal_arg.lower().endswith(('.json', '.png', '.hex', '.txt')) or os.sep in pal_arg or '/' in pal_arg: _die('palette file not found: ' + pal_arg)
    if not all(re.fullmatch(r'#?[0-9a-fA-F]{6}', t.strip()) for t in pal_arg.split(',')): _die('%r is not a palette file and not a comma-separated list of #rrggbb colours' % pal_arg)
for _f in files:
    if not os.path.isfile(_f): _die('no such image: ' + _f)
if pal_arg == 'auto':
    px = np.concatenate([np.array(Image.open(f).convert('RGBA')).reshape(-1, 4) for f in files])
    px = px[px[:, 3] > 0][:, :3]
    q = Image.fromarray(px.reshape(1, -1, 3).astype(np.uint8)).quantize(colors=n or 16, method=Image.MEDIANCUT, dither=0)
    pal = np.array(q.getpalette()[:3 * (n or 16)]).reshape(-1, 3)
elif pal_arg.endswith('.json'):
    pal = np.array(hexes(json.load(open(pal_arg))['colours']['palette']))
elif pal_arg.endswith('.png'):
    pal = np.unique(np.array(Image.open(pal_arg).convert('RGB')).reshape(-1, 3), axis=0)
elif os.path.isfile(pal_arg):
    pal = np.array(hexes(open(pal_arg).read().split()))
else:
    pal = np.array(hexes(pal_arg.split(',')))
if n and pal_arg != 'auto':
    pal = pal[:n]   # analysis palettes are sorted most-used first
pal = pal.astype(np.int32)
for f in files:
    a = np.array(Image.open(f).convert('RGBA'))
    m = a[..., 3] > 0
    px = a[m][:, :3].astype(np.int32)
    idx = ((px[:, None, :] - pal[None, :, :]) ** 2).sum(-1).argmin(1)
    a[..., :3][m] = pal[idx]
    dst = os.path.join(out, os.path.basename(f)) if out else f
    Image.fromarray(a).save(dst)
    print(dst, '%d colours' % len(np.unique(pal[idx], axis=0)))
