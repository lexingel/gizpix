# SPDX-License-Identifier: AGPL-3.0-or-later
"""preview_gif.py <out.gif> <still.png> <frame1.png> ... [--step 0.1] [--scale 2] [--offset X,Y]
A shareable preview of a swing with the default rhythm, straight from the frames (no engine):
stand, a short hold on the wind-up, every frame at ~60 ms, a short hold on the hit, settle (--beat heavy
for the boss rhythm with long holds, --beat even --fps 12 for plain even timing, --durations 100,100,300,…
in ms, one per given frame, e.g. the timing an analysis step measured).
--offset places a smaller standing sprite on the padded canvas (the recorded pad offset).
--vfx <sheet.png> (an effect-sheet export; its .json next to it) plays that effect with its origin at
--vfx-at X,Y on the canvas, starting on frame --vfx-on K (index into the given frames; default the hit
= the frame before last, shots use 1). The canvas grows to fit it.

--faithful: exactly the given frames and nothing else - no standing beat, no holds, transparent background,
1:1 unless --scale is given, each frame at --durations (ms) or --fps; still is ignored (pass any file or -).

  python preview_gif.py slash.gif hero.png raw/0.png raw/2.png raw/3.png raw/4.png raw/6.png --offset 24,56
  python preview_gif.py check.gif - raw/*.png --faithful --durations 100,100,200,100
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

from PIL import Image

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('out')
ap.add_argument('still')
ap.add_argument('frames', nargs='+')
ap.add_argument('--step', type=float, default=0.1)
ap.add_argument('--scale', type=int, default=2)
ap.add_argument('--offset', default='')
ap.add_argument('--beat', default='light', choices=['light', 'heavy', 'even'], help='light = hero timing (default), heavy = boss holds, even = --fps')
ap.add_argument('--fps', type=float, default=12)
ap.add_argument('--durations')
ap.add_argument('--vfx')
ap.add_argument('--vfx-at', default='0,0')
ap.add_argument('--vfx-on', type=int)
ap.add_argument('--faithful', action='store_true', help='only the given frames, transparent, 1:1, their own timing')
a = ap.parse_args()
a.frames = _expand(a.frames)
if a.faithful:   # a frame-exact copy for checking, not a presentation
    fs = [Image.open(p).convert('RGBA') for p in a.frames]
    k = a.scale if '--scale' in sys.argv else 1
    ms = [int(x) for x in a.durations.split(',')] if a.durations else [round(1000 / a.fps)] * len(fs)
    if len(ms) != len(fs):
        sys.exit('--durations has %d values for %d frames: give one duration per frame' % (len(ms), len(fs)))
    fs = [f.resize((f.width * k, f.height * k), Image.NEAREST) for f in fs]
    import numpy as np
    arrs = [np.array(f) for f in fs]
    cols = np.unique(np.concatenate([x[x[..., 3] >= 128][:, :3] for x in arrs] or [np.zeros((0, 3), np.uint8)]), axis=0)
    if len(cols) > 255:   # more colours than a GIF holds: one shared 255-colour palette, no dithering
        strip = Image.fromarray(np.concatenate([x[..., :3] for x in arrs], 1)).quantize(255, method=Image.MEDIANCUT, dither=0)
        cols = np.array(strip.getpalette()[:255 * 3], np.uint8).reshape(-1, 3)
    pal = np.concatenate([[[0, 0, 0]], cols]).astype(np.uint8)   # index 0 = transparent
    out = []
    for x in arrs:
        idx = np.zeros(x.shape[:2], np.uint8)
        on = x[..., 3] >= 128
        if on.any():
            d = ((x[on][:, None, :3].astype(int) - cols[None].astype(int)) ** 2).sum(-1)
            idx[on] = d.argmin(1) + 1
        im = Image.fromarray(idx, 'P')
        im.putpalette(pal.ravel().tolist())
        out.append(im)
    out[0].save(a.out, save_all=True, append_images=out[1:], duration=ms, loop=0, disposal=2, transparency=0)
    print('faithful preview: %d frames -> %s' % (len(fs), a.out))
    sys.exit(0)

fs = [Image.open(p).convert('RGBA') for p in a.frames]
W, H = fs[0].size
still = Image.open(a.still).convert('RGBA')
if still.size != (W, H):
    x, y = (int(v) for v in a.offset.split(',')) if a.offset else ((W - still.width) // 2, H - still.height)
    c = Image.new('RGBA', (W, H))
    c.alpha_composite(still, (x, y))
    still = c
seq = [still] + fs
n = len(seq)
if a.durations:
    secs = [0.06] + [int(x) / 1000.0 for x in a.durations.split(',')]
    assert len(secs) == n, 'need one duration per frame'
elif a.beat == 'even':
    secs = [1.0 / a.fps] * n
elif a.beat == 'light':   # 60 ms a frame, short holds on wind-up and hit (feedback: big holds read as freezing)
    secs = [0.06] * n
    secs[1], secs[n - 2], secs[n - 1] = 0.16, 0.14, 0.12
else:
    beat = [0.8] * n
    beat[0], beat[1], beat[n - 2], beat[n - 1] = 0.6, 4.0, 3.2, 1.4
    secs = [a.step * b for b in beat]
frames = [(still, 0.4)] + list(zip(seq, secs)) + [(still, 0.4)]
bg = (24, 19, 36, 255)
ox = oy = 0
CW, CH = W, H
if a.vfx:   # re-cut the timeline at every sprite or effect frame change
    import json
    meta = json.load(open(a.vfx[:-4] + '.json'))
    sheet = Image.open(a.vfx).convert('RGBA')
    vf = [(sheet.crop((r['frame']['x'], r['frame']['y'], r['frame']['x'] + r['frame']['w'], r['frame']['y'] + r['frame']['h'])),
           r['duration'] / 1000.0, r.get('pivot', {'x': 0, 'y': 0})) for r in meta['frames']]
    vw, vh = vf[0][0].size
    px, py = round(vf[0][2]['x'] * vw), round(vf[0][2]['y'] * vh)
    ax, ay = (int(v) for v in a.vfx_at.split(','))
    vx, vy = ax - px, ay - py
    ox, oy = max(0, -vx), max(0, -vy)
    CW, CH = max(W, vx + vw) + ox, max(H, vy + vh) + oy
    on = (len(fs) - 2 if a.vfx_on is None else a.vfx_on) + 2   # frames[] = [hold, still, fs...]
    t0 = sum(t for _, t in frames[:on])
    sp, t = [], 0.0
    for img, d in frames:
        sp.append((t, img)); t += d
    vt, t = [], t0
    for img, d, _ in vf:
        vt.append((t, img)); t += d
    end = max(sum(d for _, d in frames), t)
    cuts = sorted({c for c, _ in sp} | {c for c, _ in vt} | {t})
    def at(tl, x):
        cur = None
        for c, img in tl:
            if c <= x + 1e-9:
                cur = img
        return cur
    out = []
    for i, c in enumerate(cuts[:-1]):
        f = at(sp, c)
        v = at(vt, c) if t0 <= c < t else None
        out.append(((f, v), cuts[i + 1] - c))
    frames = out
else:
    frames = [((f, None), d) for f, d in frames]
imgs = []
for (f, v), _ in frames:
    c = Image.new('RGBA', (CW, CH), bg)
    c.alpha_composite(f, (ox, oy))
    if v is not None:
        c.alpha_composite(v, (vx + ox, vy + oy))
    W2, H2 = c.size
    imgs.append(c.resize((W2 * a.scale, H2 * a.scale), Image.NEAREST).convert('RGB').quantize(colors=255, method=0, dither=0))
imgs[0].save(a.out, save_all=True, append_images=imgs[1:], duration=[max(20, round(t * 100) * 10) for _, t in frames], loop=0, disposal=1)
print(a.out, len(imgs), 'frames')
