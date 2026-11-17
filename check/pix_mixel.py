# SPDX-License-Identifier: AGPL-3.0-or-later
"""pix_mixel.py - find "mixels": pixels of different sizes mixed in one picture (a 2 px outline next to 3 px shading, a tiny 1 px sprite on a 3 px grid, a resized image). Only measures, never edits.
  python pix_mixel.py image.png [more.png ...] [--json] [--strict] [--native] [--scale N] [--map OUT]      python pix_mixel.py selftest
  --strict   exit 1 if any image has a flag (cannot read a file: exit 2; no file: usage, exit 2)
  --native   the art really is drawn at 1 px per pixel: do not flag "no pixel grid"
  --scale N  test against a pixel size you already know (e.g. 3 for a 48 px sprite shown at 3x) instead of finding it
  --map OUT  also draw WHERE the mixels are: one PNG per image (OUT is a file for one image, or a folder). Blue = 1 px detail, orange = blocks of 3 px or more, red frame = fine detail right next to
             coarse blocks. `fine_coarse_contacts` in the output counts the red frames. Needs only Pillow. Advisory: it points at places to look at (a 1 px eye on a 3 px face is a mixed pixel size even when deliberate).
How it works (our own code): every clear colour change (more than 16 in any channel, or a change of transparency) is an "edge". On a true pixel grid of size c all edges sit at multiples of c.
  purity(c)   share of edges on the best phase of a c-pixel grid, per axis, the worse axis counts. Chance level is 1/c; a clean grid gives 1.0. c runs from 2 to min(32, shorter side / 8).
  scale       the pixel size: the largest c with purity of at least 0.97 and enough edges to say so. If no c reaches 0.97 but one is far above chance (purity of at least 0.75 and 0.4 above 1/c), that c is used and the picture
              is judged on it ("mixels" / "off-grid edges"). 1 = no grid found. null = too few edges to say (flat, empty or tiny picture).
  Tiles       the picture is cut into tiles (the last ones reach the edge); a tile with enough edges is "bad" when 6 or more of its edges, and more than 3% of them, sit off the picture's grid and phase.
              In `tile_scales`, a bad tile is listed under its own pixel size, "none" (no grid of its own) or "offset" (same size, shifted).
Flags (advisory):
  no pixel grid     scale is 1 and the picture is at least 96 px on a side: a resized image, or pixel sizes mixed everywhere. A sprite really drawn at 1 px per pixel: pass --native.
  mixels            more than 3% of the tiles are bad: pieces drawn at another pixel size or shifted.
  off-grid edges    purity at the scale is under 0.99 (a few stray pieces, or single pixels off the grid).
  no edges          too few clear colour changes to measure.
Limits: flat or gradient backgrounds are ignored (only clear edges count); JPEG noise reads as "no pixel grid"; a 2x picture whose art only uses even coordinates reads as 4x (pass --scale 2); art on a grid larger than 32 px is not found.
Run it on the native-size file: a 4x upscale of a mixed picture shows a clean scale of 4 and hides the mixels inside.
Reading it: scale 3, mixel_tiles 0.00 = a clean 3x upscale. scale 1 with purity(2) 0.55 and purity(3) 0.40 on a 144 px icon = no common grid. Repair: redraw on one grid, or `pix_snap --cells W H` to the grid the art was meant for (it costs detail), then run this check again."""
import sys, os, json
import numpy as np
from PIL import Image

PURE = 0.97
CONTRAST = 16        # smallest colour change that counts as an edge
TILE_GATE = 30       # edges a tile needs before it is judged
TILE_BAD = 6         # off-grid edges a tile needs before it can be bad
MIN_EDGES = 24       # edges a picture needs before it can be measured


def load(p):
    return np.array(Image.open(p).convert("RGBA"))


def _edges(a):
    """ex[y, x]: column x differs clearly from x-1; ey[y, x]: row y differs clearly from y-1. Transparent pixels all count as one colour."""
    b = a.astype(int)
    b[b[..., 3] == 0] = 0
    ex = np.zeros(b.shape[:2], bool)
    ey = np.zeros(b.shape[:2], bool)
    ex[:, 1:] = np.abs(b[:, 1:] - b[:, :-1]).max(axis=2) > CONTRAST
    ey[1:, :] = np.abs(b[1:] - b[:-1]).max(axis=2) > CONTRAST
    return ex, ey


def _phase_counts(m, axis, c):
    cnt = m.sum(axis=axis)                                   # edges per column (axis 0) / per row (axis 1)
    return np.bincount(np.arange(len(cnt)) % c, weights=cnt, minlength=c), float(cnt.sum())


def _purity(ex, ey, c):
    out = []
    for m, axis in ((ex, 0), (ey, 1)):
        ph, tot = _phase_counts(m, axis, c)
        out.append(float(ph.max() / tot) if tot else 0.0)
    return min(out)


def _enough(ex, ey, c):
    """each axis has enough edges to tell a c-grid from chance"""
    return ex.sum() >= 8 * c and ey.sum() >= 8 * c


def _cmax(h, w):
    return max(2, min(32, min(h, w) // 8))


def _scale(ex, ey, cmax):
    """(scale, purity dict, mode) with scale None (too few edges), 1 (no grid) or c >= 2; mode 'grid' or 'approx'"""
    if int(ex.sum() + ey.sum()) < MIN_EDGES:
        return None, {}, "none"
    pur = {c: _purity(ex, ey, c) for c in range(2, cmax + 1)}
    ok = [c for c in pur if pur[c] >= PURE and _enough(ex, ey, c)]
    if ok:
        return max(ok), pur, "grid"
    best = max(pur, key=lambda c: pur[c] - 1 / c)
    if pur[best] >= 0.75 and pur[best] - 1 / best >= 0.4 and _enough(ex, ey, best):
        near = [c for c in pur if pur[c] >= pur[best] - 0.03 and _enough(ex, ey, c)]
        return max(near), pur, "approx"
    return 1, pur, "none"


def _phases(ex, ey, s):
    r = []
    for m, axis in ((ex, 0), (ey, 1)):
        ph, _ = _phase_counts(m, axis, s)
        r.append(int(ph.argmax()))
    return r


def analyse(a, tile=None, scale=None):
    h, w = a.shape[:2]
    ex, ey = _edges(a)
    cmax = _cmax(h, w)
    s, pur, mode = _scale(ex, ey, cmax)
    if scale:                                              # a grid given by the user
        pur = {c: _purity(ex, ey, c) for c in range(2, max(cmax, scale) + 1)}
        s, mode = scale, "given"
    res = {"size": f"{w}x{h}", "scale": s, "mode": mode,
           "purity": {str(c): round(v, 3) for c, v in pur.items() if c <= 12 or c == s},
           "purity_at_scale": round(pur[s], 3) if (s and s > 1 and s in pur) else None,
           "edges": int(ex.sum() + ey.sum())}
    t = tile or max(24, min(w, h) // 5)
    bad, own = [], {}
    used = 0
    if s and s > 1:
        r0 = _phases(ex, ey, s)
    ys = list(range(0, max(h - t // 2, 1), t))
    xs = list(range(0, max(w - t // 2, 1), t))
    for yi, y0 in enumerate(ys):
        y1 = h if yi == len(ys) - 1 else y0 + t              # the last tile reaches the edge
        for xi, x0 in enumerate(xs):
            x1 = w if xi == len(xs) - 1 else x0 + t
            sx, sy = ex[y0:y1, x0:x1], ey[y0:y1, x0:x1]
            n = int(sx.sum() + sy.sum())
            if n < TILE_GATE:
                continue
            used += 1
            if not s or s == 1:
                continue
            onx = sx[:, [i for i in range(sx.shape[1]) if (x0 + i) % s == r0[0]]].sum()
            ony = sy[[i for i in range(sy.shape[0]) if (y0 + i) % s == r0[1]], :].sum()
            off = n - int(onx + ony)
            if off >= TILE_BAD and off / n > 1 - PURE:
                ts, _, _ = _scale(sx, sy, cmax)
                label = "none" if not ts or ts == 1 else ("offset" if ts == s else str(ts))
                bad.append([x0, y0, label])
                own[label] = own.get(label, 0) + 1
    res["tiles_checked"] = used
    res["mixel_tiles"] = round(len(bad) / used, 3) if used else 0.0
    res["mixel_tile_boxes"] = [{"x": b[0], "y": b[1], "w": t, "h": t, "tile_scale": b[2]} for b in bad[:8]]
    res["tile_scales"] = dict(sorted(own.items()))
    return res


BLUE, ORANGE, RED = (40, 120, 255), (255, 150, 30), (255, 40, 40)


def _runs_inside(blk):
    """lengths of opaque colour runs in a block that do not touch the block's edge (rows and columns)"""
    lens = []
    for arr in (blk, blk.transpose(1, 0, 2)):
        for row in arr:
            ch = np.any(row[1:] != row[:-1], axis=1)
            cuts = np.concatenate([[0], np.flatnonzero(ch) + 1, [len(row)]])
            for i in range(1, len(cuts) - 2):
                if row[cuts[i], 3] > 0:
                    lens.append(int(cuts[i + 1] - cuts[i]))
    return lens


def mixel_map(a, out_path=None):
    """fine/coarse map. Returns (contacts, areas) and writes a PNG when out_path is given."""
    from PIL import ImageDraw
    h, w = a.shape[:2]
    win = 12 if max(h, w) <= 200 else 16
    step = win // 2
    b = a.astype(int)
    b[b[..., 3] == 0] = 0
    share = {}
    for y in range(0, h - win + 1, step):
        for x in range(0, w - win + 1, step):
            lens = _runs_inside(b[y:y + win, x:x + win])
            if len(lens) >= 12:
                l = np.array(lens)
                share[(x, y)] = (float((l == 1).mean()), float((l >= 3).mean()))
    fine = {k for k, (f, c) in share.items() if f >= 0.45}
    coarse = {k for k, (f, c) in share.items() if c >= 0.55}
    near = lambda k, S: any(abs(k[0] - j[0]) <= win and abs(k[1] - j[1]) <= win for j in S)
    both = {k for k in fine if near(k, coarse)} | {k for k in coarse if near(k, fine)}
    if out_path:
        z = int(max(1, min(8, -(-720 // max(h, w)))))
        base = Image.new("RGBA", (w * z, h * z), (70, 70, 78, 255))
        base.alpha_composite(Image.fromarray(a.astype(np.uint8)).resize((w * z, h * z), Image.NEAREST))
        ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        def box(k, fill, outline=None):
            x0, y0 = (k[0] + (win - step) // 2) * z, (k[1] + (win - step) // 2) * z
            d.rectangle([x0, y0, x0 + step * z - 1, y0 + step * z - 1], fill=fill, outline=outline)
        for k in fine:
            box(k, BLUE + (110,))
        for k in coarse:
            box(k, ORANGE + (90,))
        for k in both:
            box(k, None, RED + (255,))
        base.alpha_composite(ov)
        base.convert("RGB").save(out_path)
    return len(both), len(share)


def check(p, native=False, scale=None, map_to=None):
    a = load(p)
    r = analyse(a, scale=scale)
    fl = []
    if r["scale"] is None:
        fl.append("no edges")
    elif r["scale"] == 1 and min(a.shape[:2]) >= 96 and not native:
        fl.append("no pixel grid")
    elif r["scale"] and r["scale"] > 1:
        if r["mixel_tiles"] > 0.03:
            fl.append("mixels")
        if r["purity_at_scale"] is not None and r["purity_at_scale"] < 0.99:
            fl.append("off-grid edges")
    if map_to:
        r["fine_coarse_contacts"], r["map_areas"] = mixel_map(a, map_to)
    r["flags"] = fl
    return r


def _synth(scale=3, n=48, seed=1, patch=False):
    rng = np.random.RandomState(seed)
    small = np.zeros((n, n, 4), np.uint8)
    pal = np.array([[30, 20, 40], [140, 160, 140], [240, 225, 190], [220, 110, 100]], np.uint8)
    for _ in range(40):
        x, y = rng.randint(0, n - 8, 2)
        ww, hh = rng.randint(4, 14, 2)
        small[y:y + hh, x:x + ww, :3] = pal[rng.randint(0, 4)]
        small[y:y + hh, x:x + ww, 3] = 255
    a = np.kron(small, np.ones((scale, scale, 1), np.uint8))
    if patch:                                   # a region redrawn at 2x instead of 3x
        p = np.kron(small[:24 // 2, :24 // 2], np.ones((2, 2, 1), np.uint8))
        a[48:72, 48:72] = p[:24, :24]
    return a


def selftest():
    clean = analyse(_synth())
    assert clean["scale"] == 3 and clean["mixel_tiles"] == 0.0 and clean["purity_at_scale"] == 1.0, clean
    pat = analyse(_synth(patch=True))
    assert pat["scale"] == 3 and pat["mixel_tiles"] > 0.0 and pat["tile_scales"], pat
    big = Image.fromarray(_synth(3, 48)).resize((216, 216), Image.BILINEAR)            # non-integer resize: no grid
    rs = analyse(np.array(big))
    assert rs["scale"] == 1, rs
    assert analyse(_synth(1, 64))["scale"] == 1
    for flat in (np.full((200, 200, 4), 120, np.uint8), np.zeros((200, 200, 4), np.uint8), np.zeros((2, 2, 4), np.uint8)):
        assert analyse(flat)["scale"] is None                                          # flat, empty, tiny: no scale (used to say 12)
    a = _synth()                                                                       # a wide off-grid bar: still "scale 3 + mixels", not "no grid"
    a[70:74, 20:110] = (0, 0, 0, 255)
    r = analyse(a)
    assert r["scale"] == 3 and r["mixel_tiles"] > 0.0, r
    a = _synth()                                                                       # a patch in the last rows is inside the tiles
    a[138:144, 20:100] = (0, 0, 0, 255)
    a[139:142, 20:100] = (200, 0, 0, 255)
    r = analyse(a)
    assert r["scale"] == 3 and r["mixel_tiles"] > 0.0, r
    a = _synth()                                                                       # one stray pixel is not a mixel tile
    a[100, 100] = (0, 0, 0, 255)
    r = analyse(a)
    assert r["scale"] == 3 and r["mixel_tiles"] == 0.0, r
    a = _synth().astype(int)                                                           # a smooth gradient behind a clean 3x sprite
    g = np.linspace(0, 40, a.shape[1]).astype(int)
    bg = a[..., 3] == 0
    for ch in range(3):
        a[..., ch] = np.where(bg, np.broadcast_to(g, a.shape[:2]), a[..., ch])
    a[..., 3] = 255
    assert analyse(a.astype(np.uint8))["scale"] == 3
    assert analyse(_synth(16, 16))["scale"] == 16                                      # a 16x upscale is found
    assert analyse(_synth(2, 48), scale=2)["purity_at_scale"] == 1.0                   # a given scale
    import tempfile                                                                    # --map: clean 3x has no fine/coarse contact, 1 px detail beside 3 px blocks has
    a = _synth()
    with tempfile.TemporaryDirectory() as t:
        c0, _ = mixel_map(a, os.path.join(t, "m.png"))
        assert os.path.getsize(os.path.join(t, "m.png")) > 0 and c0 == 0, c0
    a[60:84, 60:84] = 0
    a[60:84:2, 60:84:2] = (240, 225, 190, 255)
    a[61:84:2, 61:84:2] = (30, 20, 40, 255)
    c1, _ = mixel_map(a)
    assert c1 > 0, c1
    print("selftest ok", {"clean": clean["mixel_tiles"], "patched": pat["mixel_tiles"], "resized_scale": rs["scale"]})


def main(argv):
    import argparse
    if argv == ["selftest"]:
        selftest()
        return 0
    ap = argparse.ArgumentParser(prog="pix_mixel.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--native", action="store_true")
    ap.add_argument("--scale", type=int, default=None)
    ap.add_argument("--map", default=None, metavar="OUT")
    a = ap.parse_args(argv)
    if not a.files:
        print(__doc__)
        return 2
    out, bad = {}, []
    mdir = a.map if (a.map and (len(a.files) > 1 or not a.map.lower().endswith(".png"))) else None
    if mdir:
        os.makedirs(mdir, exist_ok=True)
    for f in a.files:
        try:
            mp = os.path.join(mdir, os.path.splitext(os.path.basename(f))[0] + "_mixels.png") if mdir else a.map
            out[f] = check(f, a.native, a.scale, mp)
        except (OSError, ValueError) as e:
            bad.append(f)
            print(f"{f}: cannot read ({type(e).__name__})", file=sys.stderr)
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        for f, r in out.items():
            ps = r["purity"]
            print(f"{os.path.basename(f)}: scale {r['scale'] if r['scale'] is not None else '-'}  purity@scale {r['purity_at_scale'] if r['purity_at_scale'] is not None else '-'}  "
                  f"purity(2,3)={ps.get('2', '-')},{ps.get('3', '-')}  mixel_tiles {r['mixel_tiles']} of {r['tiles_checked']}  tile scales {r['tile_scales']}"
                  + (f"  fine/coarse contacts {r['fine_coarse_contacts']} of {r['map_areas']}" if 'fine_coarse_contacts' in r else ""))
        flagged = [f"{os.path.basename(f)}: {', '.join(r['flags'])}" for f, r in out.items() if r["flags"]]
        print("FLAGS:", "; ".join(flagged) if flagged else "none")
    if bad:
        return 2
    return 1 if (a.strict and any(v["flags"] for v in out.values())) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
