#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local clean-up of generated sprite frames. Removes and moves pixels only; it never draws (--snap recolours, see below).

  clean_frames.py clean IN_DIR OUT_DIR --ref REF.png [REF2.png ...] [options]
  clean_frames.py selftest

Steps, in order (all reported per frame in clean_report.json):
  1. binary alpha                      alpha >= 128 -> 255, else 0
  2. palette key (--ref)               drop opaque pixels farther than --tol (L1 over RGB) from every colour used by the
                                       reference sprites: kills white fill, cream and cyan crescents, glow, smears
                                       --snap: recolour them to the nearest reference colour instead of dropping them.
                                       Use --snap on painterly sprites (100+ colours, soft shading): there the drop
                                       punches 1-40 px holes into cloth that read as white dots on screen. For holes,
                                       cracks and lone bright pixels left by the generator, use the separate painterly clean-up first (not part of Gizpix).
  3. specks                            drop components under --min-px unless within 2 px of a component of >= --keep-px
  4. ground (--ground-row ROW)         shift the whole frame vertically (whole pixels) so its lowest row lands on ROW
  5. weapon check (--steel-ref)        count steel-coloured pixels; frames with under half the median are flagged
                                       (--hold-bad copies the previous kept frame over a flagged frame; labelled in the report)

What it cannot fix: a weapon in the wrong hand, an arm stuck to the back, a wrong pose. Those need a re-roll.
Needs numpy + Pillow. Frames are 0.png, 1.png, ... in IN_DIR (or any *.png, sorted by the number in the name).
"""
import sys, os, glob, json, re, argparse
import numpy as np
from PIL import Image


def load(p):
    return np.array(Image.open(p).convert("RGBA"))


def frame_paths(d):
    fr = [p for p in glob.glob(os.path.join(d, "*.png")) if re.search(r"\d", os.path.basename(p))]  # skips sheets, reports
    return sorted(fr, key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)) or 0))


def palette_of(paths):
    cols = set()
    for p in paths:
        a = load(p)
        m = a[..., 3] >= 128
        cols |= {tuple(c) for c in np.unique(a[m][:, :3], axis=0)}
    return np.array(sorted(cols), dtype=int)


def components(mask):
    try:  # scipy is ~1000x faster than the pure-Python fill on 256 px frames
        from scipy import ndimage
        lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
        return lab, [0] + [int(c) for c in np.bincount(lab.ravel(), minlength=n + 1)[1:]]
    except ImportError:
        pass
    h, w = mask.shape
    lab = np.zeros((h, w), int)
    sizes = [0]
    n = 0
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not lab[y, x]:
                n += 1
                st = [(y, x)]
                lab[y, x] = n
                c = 0
                while st:
                    cy, cx = st.pop()
                    c += 1
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                                lab[ny, nx] = n
                                st.append((ny, nx))
                sizes.append(c)
    return lab, sizes


def dilate(m, r=2):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def nearest(rgb, pal, chunk=4096):
    """L1 distance to, and index of, the nearest palette colour for each row of rgb (N x 3), in chunks: a painterly
    reference has 1000+ colours and one broadcast over a 256 px frame needs gigabytes."""
    d, idx = np.empty(len(rgb), int), np.empty(len(rgb), int)
    for i in range(0, len(rgb), chunk):
        dd = np.abs(rgb[i:i + chunk, None, :] - pal[None, :, :]).sum(2)
        idx[i:i + chunk] = dd.argmin(1)
        d[i:i + chunk] = dd[np.arange(len(dd)), idx[i:i + chunk]]
    return d, idx


def clean_frame(a, pal, tol, min_px, keep_px, steel_pal=None, steel_tol=40, snap=False):
    info = {}
    a = a.copy()
    a[..., 3] = np.where(a[..., 3] >= 128, 255, 0)
    op = a[..., 3] > 0
    info["opaque_in"] = int(op.sum())
    if pal is not None and len(pal):
        ys, xs = np.nonzero(op)
        d, idx = nearest(a[ys, xs, :3].astype(int), pal.astype(int))
        bad = d > tol
        if snap:
            a[ys[bad], xs[bad], :3] = pal[idx[bad]]
        else:
            a[ys[bad], xs[bad]] = 0
        info["off_palette"] = int(bad.sum())
    op = a[..., 3] > 0
    lab, sizes = components(op)
    big = np.zeros_like(op)
    for i, s in enumerate(sizes):
        if i and s >= keep_px:
            big |= lab == i
    near = dilate(big, 2)
    dropped = 0
    for i, s in enumerate(sizes):
        if i and s < min_px and not (near & (lab == i)).any():
            a[lab == i] = 0
            dropped += s
    info["specks"] = int(dropped)
    op = a[..., 3] > 0
    info["opaque_out"] = int(op.sum())
    if steel_pal is not None:
        ys, xs = np.nonzero(op)
        info["steel"] = int((nearest(a[ys, xs, :3].astype(int), steel_pal.astype(int))[0] <= steel_tol).sum())
    return a, info


def shift_v(a, dy):
    if dy == 0:
        return a
    out = np.zeros_like(a)
    h = a.shape[0]
    if dy > 0:
        if a[h - dy:, :, 3].any():
            return a
        out[dy:] = a[:h - dy]
    else:
        if a[:-dy, :, 3].any():
            return a
        out[:h + dy] = a[-dy:]
    return out


def run(src, dst, refs, tol=40, min_px=6, keep_px=40, ground_row=None, steel_refs=None, hold_bad=False, snap=False):
    os.makedirs(dst, exist_ok=True)
    pal = palette_of(refs) if refs else None
    steel = palette_of(steel_refs) if steel_refs else None
    paths = frame_paths(src)
    cleaned, infos = [], []
    for p in paths:
        a, info = clean_frame(load(p), pal, tol, min_px, keep_px, steel, snap=snap)
        ys = np.where((a[..., 3] > 0).any(1))[0]
        if ground_row is not None and len(ys):
            dy = ground_row - ys.max()
            b = shift_v(a, dy)
            info["ground_shift"] = int(dy) if b is not a else 0
            a = b
        cleaned.append(a)
        infos.append(info)
    flagged = []
    if steel is not None:
        med = float(np.median([i["steel"] for i in infos])) or 1.0
        for k, i in enumerate(infos):
            if i["steel"] < 0.5 * med:
                flagged.append(k)
                i["flag"] = f"weapon pixels {i['steel']} vs median {med:.0f}"
    kept_prev = None
    for k, a in enumerate(cleaned):
        if k in flagged and hold_bad and kept_prev is not None:
            infos[k]["held"] = f"copied frame {kept_prev} (local hold, not a new frame)"
            a = cleaned[kept_prev]
        elif k not in flagged:
            kept_prev = k
        Image.fromarray(a).save(os.path.join(dst, os.path.basename(paths[k])))
    json.dump(infos, open(os.path.join(dst, "clean_report.json"), "w"), indent=1)
    return infos, flagged


def selftest():
    import tempfile
    t = tempfile.mkdtemp()
    ref = np.zeros((16, 16, 4), np.uint8)
    ref[4:14, 5:10] = (200, 150, 100, 255)
    Image.fromarray(ref).save(os.path.join(t, "ref.png"))
    os.makedirs(os.path.join(t, "in"))
    f = ref.copy()
    f[0:3, 0:6] = (255, 255, 255, 255)       # white fill
    f[1, 14] = (200, 150, 100, 255)           # detached speck, right colour
    f[6, 10:13] = (200, 150, 100, 255)        # attached limb (kept)
    f[4:14] = np.roll(f[4:14], 1, 0) if False else f[4:14]
    Image.fromarray(f).save(os.path.join(t, "in", "0.png"))
    infos, flagged = run(os.path.join(t, "in"), os.path.join(t, "out"), [os.path.join(t, "ref.png")], ground_row=15)
    o = load(os.path.join(t, "out", "0.png"))
    assert not o[0:3, 0:6, 3].any(), "white fill should be gone"
    assert not o[:, 14, 3].any(), "speck should be gone"
    assert infos[0]["ground_shift"] == 2, infos
    assert o[6 + 2, 10:13, 3].all(), "attached limb kept after the ground shift"
    infos, _ = run(os.path.join(t, "in"), os.path.join(t, "snap"), [os.path.join(t, "ref.png")], snap=True)
    o = load(os.path.join(t, "snap", "0.png"))
    assert o[0:3, 0:6, 3].all() and (o[0, 0, :3] == (200, 150, 100)).all(), "--snap recolours instead of dropping"
    print("selftest ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) > 1 and sys.argv[1] == "clean":
        ap = argparse.ArgumentParser()
        ap.add_argument("cmd"); ap.add_argument("src"); ap.add_argument("dst")
        ap.add_argument("--ref", nargs="+", required=True)
        ap.add_argument("--tol", type=int, default=40)
        ap.add_argument("--min-px", type=int, default=6)
        ap.add_argument("--keep-px", type=int, default=40)
        ap.add_argument("--ground-row", type=int, default=None)
        ap.add_argument("--steel-ref", nargs="+", default=None)
        ap.add_argument("--hold-bad", action="store_true")
        ap.add_argument("--snap", action="store_true")
        a = ap.parse_args()
        infos, flagged = run(a.src, a.dst, a.ref, a.tol, a.min_px, a.keep_px, a.ground_row, a.steel_ref, a.hold_bad, a.snap)
        for k, i in enumerate(infos):
            print(k, {x: y for x, y in i.items()})
        print("flagged:", flagged)
    else:
        print(__doc__)
