#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
"""QA for 8-direction sprite sets. Read-only: it measures, reports and draws previews; it never edits art.

  check_8dir.py stills DIR            8 PNGs named north, north-east, east, south-east, south, south-west, west, north-west
  check_8dir.py walk DIR              DIR/<direction>/0.png 1.png ... (one folder per direction, same frame count)
  check_8dir.py swing CLIP [TWIN]     attack clip (one direction): turn/step, return to first pose, painted effect pixels,
                                      and pose match against a weapon-less twin clip
  check_8dir.py compass DIR OUT.png   ring preview with shared guide lines (head top, feet, pivot)
  check_8dir.py mirror SRC DST [PIVOT_X]  west/south-west/north-west from east/south-east/north-east (stills or clips),
                                      flipped about the pivot column (default: canvas centre), labelled in mirror_manifest.json
  check_8dir.py light DIR              shading direction per direction (rows/columns brightness slope); flags directions lit from a different side
  check_8dir.py selftest

Needs numpy + Pillow. Thresholds are starting points taken from reference sheets, not laws.
"""
import sys, os, glob
import numpy as np
from PIL import Image, ImageDraw

DIRS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
PAIRS = [("north-east", "north-west"), ("east", "west"), ("south-east", "south-west")]
RING = {"north": (1, 0), "north-east": (2, 0), "east": (2, 1), "south-east": (2, 2),
        "south": (1, 2), "south-west": (0, 2), "west": (0, 1), "north-west": (0, 0)}


def load(path):
    return np.array(Image.open(path).convert("RGBA"))


def bbox(a):
    ys, xs = np.where(a[..., 3] > 0)
    return ys.min(), ys.max(), xs.min(), xs.max()


def centred(m):
    """Shift a mask so its bbox centre sits on the middle column (compares shape, not placement)."""
    xs = np.where(m.any(0))[0]
    return np.roll(m, m.shape[1] // 2 - (xs.min() + xs.max()) // 2, axis=1)


def iou(a, b):
    u = (a | b).sum()
    return (a & b).sum() / u if u else 1.0


def stills(d):
    got = {n: load(os.path.join(d, n + ".png")) for n in DIRS if os.path.exists(os.path.join(d, n + ".png"))}
    flags = []
    miss = [n for n in DIRS if n not in got]
    if miss:
        flags.append(f"missing directions: {miss}")
    sizes = {a.shape[:2] for a in got.values()}
    if len(sizes) > 1:
        flags.append(f"canvas sizes differ: {sizes}")
    rows = {}
    for n, a in got.items():
        t, b, l, r = bbox(a)
        al = a[..., 3]
        rows[n] = dict(top=t, bottom=b, h=b - t + 1, w=r - l + 1, cx=(l + r) / 2 - a.shape[1] / 2,
                       semi=int(((al > 0) & (al < 255)).sum()))
    sw = rows["south"]["w"] if "south" in rows else max(r["w"] for r in rows.values())
    print(f"{'dir':11s} top bot   h   w  w/south  cx-off  semi-alpha")
    for n in DIRS:
        if n in rows:
            r = rows[n]
            print(f"{n:11s} {r['top']:3d} {r['bottom']:3d} {r['h']:3d} {r['w']:3d}  {r['w']/sw:5.2f}  {r['cx']:6.1f}  {r['semi']}")
    spread = lambda k: max(r[k] for r in rows.values()) - min(r[k] for r in rows.values())
    if spread("bottom") > 1:
        flags.append(f"feet line drifts {spread('bottom')} px across directions (keep top and bottom aligned in every pose; shift whole sprites by whole pixels)")
    if spread("h") > 2:
        flags.append(f"height varies {spread('h')} px")
    if spread("cx") > 2:
        flags.append(f"horizontal centre varies {spread('cx'):.1f} px")
    if any(r["semi"] for r in rows.values()):
        flags.append("semi-transparent pixels present (guide wants alpha 0 or 255)")
    for n in ("east", "west"):
        if n in rows and rows[n]["w"] / sw > 0.75:
            flags.append(f"{n} is {rows[n]['w']/sw:.2f} of south width: a side view is usually 0.5-0.6")
    for n in ("north-east", "north-west", "south-east", "south-west"):
        if n in rows and not 0.6 <= rows[n]["w"] / sw <= 1.0:
            flags.append(f"{n} is {rows[n]['w']/sw:.2f} of south width: diagonals are usually 0.6-1.0 (check the turn)")
    print("\nmirror pairs (flip B, re-centre, silhouette IoU; 1.0 = exact mirror):")
    for a, b in PAIRS:
        if a in got and b in got:
            print(f"  {a:10s} / {b:10s} {iou(centred(got[a][..., 3] > 0), centred(got[b][..., 3][:, ::-1] > 0)):.2f}")
    print("\nFLAGS:" if flags else "\nno flags")
    for f in flags:
        print(" -", f)
    return flags


def walk(d):
    curves = {}
    for n in DIRS:
        fr = sorted(glob.glob(os.path.join(d, n, "*.png")), key=lambda p: int(os.path.splitext(os.path.basename(p))[0]))
        if not fr:
            continue
        top, bot, stance = [], [], []
        for p in fr:
            a = load(p)
            t, b, _, _ = bbox(a)
            low = a[t + int((b - t) * 0.6): b + 1, :, 3] > 0
            xs = np.where(low.any(0))[0]
            top.append(t); bot.append(b); stance.append(xs.max() - xs.min() + 1)
        curves[n] = (np.array(top, float), np.array(bot, float), np.array(stance, float))
    if not curves:
        print("no frames found")
        return []
    flags = []
    counts = {k: len(v[0]) for k, v in curves.items()}
    if len(set(counts.values())) > 1:
        flags.append(f"frame counts differ: {counts}")
    z = lambda v: (v - v.mean()) / (v.std() or 1.0)

    def signal(t, b, s):
        """Gait curve: leg spread (side views) plus feet height (front/back views, where the legs foreshorten).
        A feature is used only if it moves enough to mean something."""
        parts = [z(s)] if s.std() >= 2 else []
        parts += [z(b)] if b.std() >= 1.2 else []
        return sum(parts) if parts else None

    sigs = {k: signal(*v) for k, v in curves.items()}
    ref = max((k for k in sigs if sigs[k] is not None and len(sigs[k]) == counts[k]),
              key=lambda k: curves[k][2].std(), default=None)
    n = counts[ref] if ref else 0
    half = max(n // 2, 1)  # a gait repeats twice per cycle, so phase is only known mod n/2
    print(f"{'dir':11s} frames  feet-line  bob  phase vs {ref} (frames, mod {half})")
    for k, (t, b, s) in curves.items():
        if len(t) != n:
            continue
        sg = sigs[k]
        if sg is None or ref is None:
            best = "?"
            flags.append(f"{k}: no usable gait signal (legs barely move in the frames); judge it by eye at 6x")
        else:
            best = max(range(half), key=lambda sh: float(np.dot(sigs[ref], np.roll(sg, sh))))
            if best:
                flags.append(f"{k}: gait curve is {best} frame(s) out of phase with {ref}; contact poses should land on the same frame indices in every direction")
        print(f"{k:11s} {n:6d}  {int(b.min())}..{int(b.max())}      {int(t.max() - t.min()):3d}  {best}")
        if b.max() - b.min() > 2:
            flags.append(f"{k}: feet line moves {int(b.max() - b.min())} px during the walk (check it is a step, not a hop or a drifting canvas)")
    bobs = {k: int(v[0].max() - v[0].min()) for k, v in curves.items()}
    if max(bobs.values()) - min(bobs.values()) > 1:
        flags.append(f"head bob differs between directions {bobs}; keep the bounce consistent on the same frames in all directions")
    print("\nFLAGS:" if flags else "\nno flags")
    for f in flags:
        print(" -", f)
    return flags


def _components(m):
    h, w = m.shape
    seen = np.zeros_like(m)
    sizes = []
    for y in range(h):
        for x in range(w):
            if m[y, x] and not seen[y, x]:
                st, n = [(y, x)], 0
                seen[y, x] = True
                while st:
                    cy, cx = st.pop()
                    n += 1
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True
                                st.append((ny, nx))
                sizes.append(n)
    return sizes


def swing(clip, twin=None):
    """Checks the Pip doctor does not make on an attack clip (a folder of 0.png, 1.png ... for ONE direction):
    the body must not turn or step, the clip must return to its first pose, painted effect pixels are reported,
    and an optional twin clip (same moves without the weapon) must be pose-matched for a layer diff.
    Written for a back or front view with the weapon hand on the right of the image; the 'left side' box is the
    side without the weapon."""
    def frames(d):
        fr = sorted(glob.glob(os.path.join(d, "*.png")), key=lambda p: int(os.path.splitext(os.path.basename(p))[0]))
        return [load(p) for p in fr]
    fr = frames(clip)
    tw = frames(twin) if twin else None
    a0 = fr[0][..., 3] > 0
    ys, xs = np.where(a0)
    t, b, cx = ys.min(), ys.max(), int(np.median(xs))
    h = b - t + 1
    feet = (slice(t + int(0.82 * h), b + 1), slice(None))
    left = (slice(t, b + 1), slice(max(cx - 16, 0), cx))
    flags = []
    print(f"{'frame':5s} feetXOR leftXOR effect-px" + ("  twin-leftXOR twin-feetXOR" if tw else ""))
    turned, fx_frames, mismatched = [], [], []
    for i, f in enumerate(fr):
        a = f[..., 3] > 0
        fe, le = int((a[feet] ^ a0[feet]).sum()), int((a[left] ^ a0[left]).sum())
        rgb = f[..., :3].astype(int)
        light = a & (rgb.min(2) >= 195) & ((rgb.max(2) - rgb.min(2)) < 40)
        fx = sum(s for s in _components(light) if s >= 12)
        row = f"{i:5d} {fe:7d} {le:7d} {fx:9d}"
        if tw:
            ta = tw[i][..., 3] > 0
            tl, tf = int((a[left] ^ ta[left]).sum()), int((a[feet] ^ ta[feet]).sum())
            row += f"  {tl:11d} {tf:12d}"
            if tl > 30 or tf > 30:
                mismatched.append(i + 1)
        print(row)
        if fe > 30 or le > 120:
            turned.append(i + 1)
        if fx >= 20:
            fx_frames.append(i + 1)
    last = fr[-1][..., 3] > 0
    back = int((last ^ a0).sum())
    print(f"\nlast frame vs first: {back} px differ ({back / max(a0.sum(), 1):.1%} of the first frame)")
    if back / max(a0.sum(), 1) > 0.06:
        flags.append("the clip does not return to its first pose (name the end pose in the wording)")
    if turned:
        flags.append(f"torso turned or feet moved on frames {turned}: compare facing with frame 1 by eye")
    if fx_frames:
        flags.append(f"painted effect pixels on frames {fx_frames}: a baked crescent or flash; keep as the slash effect, replace with a separate effect sheet, or drop")
    if tw:
        if mismatched:
            flags.append(f"twin is not pose-matched on frames {mismatched}: a layer diff against it will fail those frames")
    print("\nFLAGS:" if flags else "\nno flags")
    for f in flags:
        print(" -", f)
    return flags


MIRROR_OF = {"west": "east", "south-west": "south-east", "north-west": "north-east"}


def flip_about(a, pivot):
    """Mirror an RGBA array about column `pivot` (x -> 2*pivot - x), same canvas. Pixels leaving the canvas must be empty."""
    w = a.shape[1]
    shift = int(round(2 * pivot - (w - 1)))
    if abs(2 * pivot - (w - 1) - shift) > 1e-6:
        raise SystemExit("pivot must be a whole or half pixel column")
    out = np.zeros_like(a)
    f = a[:, ::-1]
    if shift >= 0:
        if shift and f[:, w - shift:, 3].any():
            raise SystemExit("mirroring about that pivot would cut pixels off the canvas")
        out[:, shift:] = f[:, :w - shift]
    else:
        if f[:, :-shift, 3].any():
            raise SystemExit("mirroring about that pivot would cut pixels off the canvas")
        out[:, :w + shift] = f[:, -shift:]
    return out


def mirror(src, dst, pivot=None):
    """Write west, south-west, north-west from east, south-east, north-east: stills (<dir>.png) and clips (<dir>/N.png).
    Labelled in mirror_manifest.json as 'mirrored derivative'. Run the doctor on the output clips and show the user
    the compass sheet before accepting."""
    import json, shutil
    os.makedirs(dst, exist_ok=True)
    made = []
    for n in DIRS:
        if n in MIRROR_OF:
            continue
        s = os.path.join(src, n + ".png")
        if os.path.exists(s):
            shutil.copy(s, os.path.join(dst, n + ".png"))
        if os.path.isdir(os.path.join(src, n)):
            shutil.copytree(os.path.join(src, n), os.path.join(dst, n), dirs_exist_ok=True)
    for tgt, base in MIRROR_OF.items():
        files = []
        if os.path.exists(os.path.join(src, base + ".png")):
            files.append((os.path.join(src, base + ".png"), os.path.join(dst, tgt + ".png")))
        if os.path.isdir(os.path.join(src, base)):
            os.makedirs(os.path.join(dst, tgt), exist_ok=True)
            files += [(p, os.path.join(dst, tgt, os.path.basename(p))) for p in glob.glob(os.path.join(src, base, "*.png"))]
        for p, q in files:
            a = load(p)
            Image.fromarray(flip_about(a, (a.shape[1] - 1) / 2 if pivot is None else pivot)).save(q)
            made.append({"file": os.path.relpath(q, dst), "mirror_of": os.path.relpath(p, src), "pivot_x": pivot, "label": "mirrored derivative"})
    json.dump(made, open(os.path.join(dst, "mirror_manifest.json"), "w"), indent=1)
    print(f"mirrored {len(made)} files into {dst}")


def compass(d, out, scale=3):
    got = {n: Image.open(os.path.join(d, n + ".png")).convert("RGBA") for n in DIRS if os.path.exists(os.path.join(d, n + ".png"))}
    w, h = next(iter(got.values())).size
    box = {n: bbox(np.array(i)) for n, i in got.items()}
    top = int(np.median([v[0] for v in box.values()]))
    bot = int(np.median([v[1] for v in box.values()]))
    sheet = Image.new("RGBA", (3 * w * scale, 3 * h * scale), (200, 200, 205, 255))
    dr = ImageDraw.Draw(sheet)
    for n, im in got.items():
        ox, oy = RING[n][0] * w * scale, RING[n][1] * h * scale
        sheet.alpha_composite(im.resize((w * scale, h * scale), Image.NEAREST), (ox, oy))
        for y, c in ((top, (255, 0, 0, 255)), (bot, (0, 120, 255, 255))):
            dr.line([(ox, oy + y * scale), (ox + w * scale, oy + y * scale)], fill=c)
        dr.line([(ox + w * scale // 2, oy), (ox + w * scale // 2, oy + h * scale)], fill=(0, 160, 0, 255))
        dr.text((ox + 3, oy + 3), n, fill=(0, 0, 0, 255))
    sheet.save(out)
    print("wrote", out, f"(red = median head top {top}, blue = median feet {bot}, green = pivot column)")


def shade_slopes(a):
    """Brightness slope inside the silhouette: gx = left->right per row, gy = top->bottom per column (y grows downward, so gy < 0 means lit from above).
    Slopes are taken per row/column so material colour changes between rows cancel out. Returns (gx, gy) as a share of full brightness over the sprite."""
    op = a[..., 3] > 0; lum = a[..., :3].astype(float).mean(-1); ys, xs = np.nonzero(op)
    cx, hx = (xs.min() + xs.max()) / 2, max((xs.max() - xs.min()) / 2, 1); cy, hy = (ys.min() + ys.max()) / 2, max((ys.max() - ys.min()) / 2, 1)
    def mean_slope(mask2d, vals, axis, c, h):
        s, w = [], []
        for i in range(mask2d.shape[axis]):
            m = mask2d[i] if axis == 0 else mask2d[:, i]
            if m.sum() >= 4:
                p = np.nonzero(m)[0]; l = (vals[i] if axis == 0 else vals[:, i])[m]; s.append(np.polyfit((p - c) / h, l, 1)[0]); w.append(m.sum())
        return float(np.average(s, weights=w) / 255) if s else 0.0
    return mean_slope(op, lum, 0, cx, hx), mean_slope(op, lum, 1, cy, hy)


def light(d, tol=0.12):
    """Shading direction check. In AI-generated sets every direction is lit from above (gy < 0); a direction with a clearly different vertical slope
    (or the opposite sign) was probably shaded for another light, or flipped upside down. Horizontal slope is reported only (it changes with the
    body's turn, so no flag)."""
    got = {n: load(os.path.join(d, n + ".png")) for n in DIRS if os.path.exists(os.path.join(d, n + ".png"))}
    sl = {n: shade_slopes(a) for n, a in got.items()}; med = float(np.median([v[1] for v in sl.values()])); flags = []
    for n, (gx, gy) in sl.items():
        bad = abs(gy - med) > tol or (med < -0.03 and gy > 0.03)
        print(f"{n:11s} gx {gx:+.2f}  gy {gy:+.2f}" + ("   <-- different vertical light" if bad else ""))
        if bad: flags.append(f"{n}: vertical shading {gy:+.2f} vs set median {med:+.2f}")
    print("FLAGS:", flags or "none"); return flags


def selftest():
    import tempfile, io, contextlib
    t = tempfile.mkdtemp()
    for n in DIRS:
        a = np.zeros((32, 32, 4), np.uint8)
        wd = {"north": 12, "south": 12, "east": 7, "west": 7}.get(n, 9)
        x0 = 16 - wd // 2
        a[6:30, x0:x0 + wd] = (200, 150, 100, 255)
        if n in ("north-east", "east", "south-east"):
            a[10:14, x0 + wd - 2:x0 + wd] = (50, 50, 50, 255)
        if n == "west":
            a[28:, :] = 0  # feet line drift
        Image.fromarray(a).save(os.path.join(t, n + ".png"))
    with contextlib.redirect_stdout(io.StringIO()):
        fl = stills(t)
    assert any("feet line" in f for f in fl), fl
    assert not any("semi" in f for f in fl), fl
    # walk: south in phase, east shifted by one frame
    for n, sh in (("south", 0), ("east", 1)):
        os.makedirs(os.path.join(t, "w", n))
        for i in range(8):
            a = np.zeros((32, 32, 4), np.uint8)
            k = (i + sh) % 4
            wide = (1, 5, 1, 3)[k]
            a[8 + (k == 1):30, 14:18] = (9, 9, 9, 255)
            a[24:30, 16 - wide:16 + wide + 1] = (9, 9, 9, 255)
            Image.fromarray(a).save(os.path.join(t, "w", n, f"{i}.png"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fl = walk(os.path.join(t, "w"))
    assert any("east" in f and "out of phase" in f for f in fl), (buf.getvalue(), fl)
    # mirror: flip about the canvas centre and back is the identity; a pivot off the centre moves the figure
    src = os.path.join(t, "m_src"); os.makedirs(src)
    a = np.zeros((16, 16, 4), np.uint8); a[2:14, 5:8] = (9, 9, 9, 255); a[4, 8] = (200, 0, 0, 255)
    Image.fromarray(a).save(os.path.join(src, "east.png"))
    with contextlib.redirect_stdout(io.StringIO()):
        mirror(src, os.path.join(t, "m_dst"))
        mirror(src, os.path.join(t, "m_dst2"), 7.0)
    b = load(os.path.join(t, "m_dst", "west.png"))
    assert (b[:, ::-1] == a).all()
    c2 = load(os.path.join(t, "m_dst2", "west.png"))
    assert c2[4, 6, 0] == 200  # x' = 2*7 - 8 = 6
    # light: one direction shaded from below is flagged, the rest are not
    lt = os.path.join(t, "lit"); os.makedirs(lt)
    for n in DIRS:
        a = np.zeros((32, 32, 4), np.uint8); ramp = np.linspace(230, 90, 24).astype(np.uint8)[:, None]
        a[6:30, 10:22, :3] = (ramp if n != "east" else ramp[::-1])[:, :, None]; a[6:30, 10:22, 3] = 255
        Image.fromarray(a).save(os.path.join(lt, n + ".png"))
    with contextlib.redirect_stdout(io.StringIO()):
        fl = light(lt)
    assert len(fl) == 1 and "east" in fl[0], fl
    print("selftest ok")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    if c == "stills":
        stills(sys.argv[2])
    elif c == "walk":
        walk(sys.argv[2])
    elif c == "compass":
        compass(sys.argv[2], sys.argv[3])
    elif c == "swing":
        swing(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif c == "mirror":
        mirror(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else None)
    elif c == "light":
        light(sys.argv[2])
    elif c == "selftest":
        selftest()
    else:
        print(__doc__)
